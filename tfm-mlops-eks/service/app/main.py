import os
import time
from typing import Dict

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import mlflow
import mlflow.sklearn

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response


# ===== Config =====
MODEL_URI = os.getenv("MODEL_URI")
if not MODEL_URI:
    raise RuntimeError("MODEL_URI environment variable is required")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.mlops.svc.cluster.local:5000")
THRESHOLD = float(os.getenv("THRESHOLD", "0.5"))

# Features del dataset South German Credit (sin 'kredit')
FEATURES = [
    "laufkont", "laufzeit", "moral", "verw", "hoehe",
    "sparkont", "beszeit", "rate", "famges", "buerge",
    "wohnzeit", "verm", "alter", "weitkred", "wohn",
    "bishkred", "beruf", "pers", "telef", "gastarb"
]

# ===== Prometheus metrics =====
REQS = Counter("inference_requests_total", "Total requests", ["endpoint", "status"])
LAT = Histogram("inference_request_latency_seconds", "Request latency seconds", ["endpoint"])
PRED = Counter("inference_predictions_total", "Total predictions", ["label"])
SCORE = Histogram(
    "inference_score_probability",
    "Predicted high-risk probability",
    buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

app = FastAPI(title="TFM Inference Service", version="0.1.0")

_model = None
_model_loaded_at = None


class PredictRequest(BaseModel):
    features: Dict[str, float]


def load_model():
    global _model, _model_loaded_at
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    # Cargamos el estimador sklearn para poder usar predict_proba
    _model = mlflow.sklearn.load_model(MODEL_URI)
    _model_loaded_at = time.time()


@app.on_event("startup")
def startup_event():
    load_model()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_uri": MODEL_URI,
        "mlflow_tracking_uri": MLFLOW_TRACKING_URI,
        "model_loaded": _model is not None,
        "loaded_at_epoch": _model_loaded_at
    }


@app.post("/predict")
def predict(req: PredictRequest):
    start = time.time()
    endpoint = "/predict"

    try:
        # Validación de keys
        missing = [f for f in FEATURES if f not in req.features]
        if missing:
            REQS.labels(endpoint=endpoint, status="400").inc()
            raise HTTPException(status_code=400, detail=f"Missing features: {missing}")

        # DataFrame en orden esperado
        row = {k: req.features[k] for k in FEATURES}
        df = pd.DataFrame([row], columns=FEATURES)

        proba_high = float(_model.predict_proba(df)[0][1])  # clase 1 = alto riesgo
        pred_label = int(proba_high >= THRESHOLD)

        SCORE.observe(proba_high)
        PRED.labels(label=str(pred_label)).inc()

        REQS.labels(endpoint=endpoint, status="200").inc()
        return {
            "prediction": pred_label,
            "probability_high_risk": proba_high,
            "threshold": THRESHOLD
        }

    except HTTPException:
        raise
    except Exception as e:
        REQS.labels(endpoint=endpoint, status="500").inc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        LAT.labels(endpoint=endpoint).observe(time.time() - start)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
