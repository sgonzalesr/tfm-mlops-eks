import os
import joblib
import numpy as np
import pandas as pd

import mlflow
import mlflow.sklearn

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


def load_data(csv_path: str) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(csv_path)

    if "kredit" not in df.columns:
        raise ValueError("No se encontró la columna 'kredit' en el CSV.")

    # Mapeo recomendado:
    # kredit=1 -> "buen crédito" (bajo riesgo)
    # kredit=0 -> "mal crédito" (alto riesgo)
    y = (df["kredit"] == 0).astype(int)  # 1 = alto riesgo
    X = df.drop(columns=["kredit"])

    return X, y


def eval_binary(y_true: np.ndarray, y_proba: np.ndarray, threshold: float = 0.5) -> dict:
    y_pred = (y_proba >= threshold).astype(int)

    return {
        "auc": float(roc_auc_score(y_true, y_proba)),
        "f1": float(f1_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
    }


def main() -> None:
    # ---- Config ----
    csv_path = os.getenv("DATASET_PATH", "ml/train/data/south_german_credit.csv")

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    experiment_name = os.getenv("MLFLOW_EXPERIMENT", "tfm-south-german-credit")

    # Umbral para convertir probabilidad a clase
    threshold = float(os.getenv("THRESHOLD", "0.5"))

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    # ---- Load data ----
    X, y = load_data(csv_path)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    # ---- Models ----
    # Modelo principal (robusto y fácil de explicar)
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced"
    )

    # Baseline opcional (logística) - ayuda a discusión/benchmark
    lr = Pipeline(steps=[
        ("scaler", StandardScaler(with_mean=True, with_std=True)),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))
    ])

    # ---- Entrenamiento + logging MLflow ----
    for model_name, model in [("RandomForest", rf), ("LogisticRegression", lr)]:
        with mlflow.start_run(run_name=f"{model_name}_baseline"):
            # Params (lo más relevante)
            mlflow.log_param("dataset", "South German Credit (UCI)")
            mlflow.log_param("target_mapping", "is_high_risk = (kredit==0)")
            mlflow.log_param("model_name", model_name)
            mlflow.log_param("threshold", threshold)
            mlflow.log_param("train_size", int(len(X_train)))
            mlflow.log_param("test_size", int(len(X_test)))

            if model_name == "RandomForest":
                mlflow.log_param("n_estimators", rf.n_estimators)
                mlflow.log_param("class_weight", str(rf.class_weight))

            # Fit
            model.fit(X_train, y_train)

            # Predict proba
            if hasattr(model, "predict_proba"):
                y_proba = model.predict_proba(X_test)[:, 1]
            else:
                # fallback: decision_function -> sigmoid
                scores = model.decision_function(X_test)
                y_proba = 1 / (1 + np.exp(-scores))

            metrics = eval_binary(y_test.to_numpy(), y_proba, threshold=threshold)
            mlflow.log_metrics(metrics)

            # Guardar artefacto local
            out_model = f"model_{model_name}.joblib"
            joblib.dump(model, out_model)

            # Log artifact + log_model (ambos)
            mlflow.log_artifact(out_model)

            # Log del modelo (sirve para registry/serving)
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="model",
                registered_model_name=None
            )

            print(f"[OK] {model_name} metrics:", metrics)

    print("\nListo. Revisa MLflow UI para ver runs y artefactos.")


if __name__ == "__main__":
    main()
