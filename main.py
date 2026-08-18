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

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.services.model_service import model_service
from backend.routes import health, models, metrics, forecast, anomaly, whatif, recommendation, actuals


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

# --- CORS ---
# Allow the local Vite dev server and the deployed frontend origin(s).
# Set FRONTEND_ORIGIN (comma-separated for multiple) once the frontend's
# deployed URL is known.
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [o.strip() for o in os.environ.get("FRONTEND_ORIGIN", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- Model serving routes (teammate) ---
app.include_router(health.router)
app.include_router(models.router)
app.include_router(metrics.router)
app.include_router(forecast.router)
app.include_router(actuals.router)

# --- Analysis layer routes ---
app.include_router(anomaly.router)
app.include_router(whatif.router)
app.include_router(recommendation.router)
