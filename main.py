"""
main.py — Unified FastAPI entry point.

All routes live under backend/routes/:
  /health, /models, /metrics, /forecast, /compare-models
  /api/anomaly, /api/what-if, /api/recommendations

Run from project root:
    uvicorn main:app --reload

Docs:
    http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from backend.services.model_service import model_service
from backend.routes import health, models, metrics, forecast, anomaly, whatif, recommendation


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_service.load_all()
    yield


app = FastAPI(
    title="Pharma Sales Forecasting & Analysis API",
    description=(
        "Model serving · Anomaly Detection · What-If Analysis · Recommendations"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# --- Model serving routes (teammate) ---
app.include_router(health.router)
app.include_router(models.router)
app.include_router(metrics.router)
app.include_router(forecast.router)

# --- Analysis layer routes ---
app.include_router(anomaly.router)
app.include_router(whatif.router)
app.include_router(recommendation.router)
