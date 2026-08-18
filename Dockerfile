# Backend container image — Cloud Run target.
#
# Slim, single-purpose image: only requirements-backend.txt (fastapi,
# uvicorn, pydantic, pandas, joblib). Training-only libraries (prophet,
# statsmodels, lightgbm, tensorflow) are never installed here — the
# backend serves pre-generated forecast CSVs, it doesn't train or load
# live models at runtime (see backend/services/model_service.py).

FROM python:3.11-slim AS base

WORKDIR /app

# System deps for pandas' C extensions; kept minimal on purpose.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

COPY main.py .
COPY backend/ backend/
COPY models/metrics.json models/metrics.json
COPY data/outputs/forecasts/ data/outputs/forecasts/
COPY data/processed/ data/processed/

# Cloud Run injects $PORT at runtime; default to 8080 for local `docker run`.
ENV PORT=8080
EXPOSE 8080

# Non-root user — standard container hardening.
RUN useradd --create-home appuser
USER appuser

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
