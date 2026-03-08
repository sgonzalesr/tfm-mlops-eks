FROM python:3.11-slim

WORKDIR /app

# Dependencias
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] \
    pandas numpy scikit-learn joblib \
    mlflow boto3 psycopg2-binary \
    prometheus-client

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","2"]
