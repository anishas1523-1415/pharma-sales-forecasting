"""
dashboard_service.py
=====================
Single aggregated call for everything the Dashboard page needs across all
8 categories. Replaces what used to be 24 separate HTTP round trips from
the browser (forecast + anomaly + recommendations, per category) — those
queued up behind the browser's per-host connection limit and were the
real cause of the Dashboard's slow initial paint. Same underlying
service functions as the individual endpoints; just called in one loop,
server-side, where there's no per-request connection overhead.
"""
import logging

from backend.data_loader import VALID_CATEGORIES, load_forecast
from backend.schemas.anomaly import AnomalyRequest
from backend.schemas.dashboard import DashboardCategorySummary, DashboardForecastPoint, DashboardSummaryResponse
from backend.schemas.recommendation import RecommendationRequest
from backend.services.anomaly_service import detect_anomalies
from backend.services.model_service import model_service
from backend.services.recommendation_service import generate_recommendations

logger = logging.getLogger(__name__)

VALIDATION_MODELS = ("arima", "sarima")
HORIZON = 30


def _best_model(category: str) -> str:
    cat_metrics = model_service.metrics.get(category, {})
    best = cat_metrics.get("best_model")
    if best:
        return best
    # Fall back to lowest MAE across whatever models are present.
    candidates = {k: v for k, v in cat_metrics.items() if isinstance(v, dict) and "MAE" in v}
    if not candidates:
        return "prophet"
    return min(candidates, key=lambda m: candidates[m]["MAE"])


def _best_validation_model(category: str) -> str:
    cat_metrics = model_service.metrics.get(category, {})
    candidates = {m: cat_metrics[m]["MAE"] for m in VALIDATION_MODELS if m in cat_metrics and "MAE" in cat_metrics[m]}
    if not candidates:
        return "arima"
    return min(candidates, key=candidates.get)


def _category_summary(category: str) -> DashboardCategorySummary:
    best_model = _best_model(category)
    validation_model = _best_validation_model(category)

    try:
        forecast_df = load_forecast(category, best_model).head(HORIZON)
        forecast = [
            DashboardForecastPoint(date=row["date"], prediction=round(float(row["predicted_sales"]), 2))
            for _, row in forecast_df.iterrows()
        ]
    except Exception as e:
        logger.warning("Dashboard summary: forecast failed for %s/%s (%s)", category, best_model, e)
        forecast = []

    try:
        anomaly_resp = detect_anomalies(AnomalyRequest(category=category, model=validation_model))
        total_days = anomaly_resp.total_days
        anomaly_count = anomaly_resp.anomaly_count
        high_severity_count = sum(1 for r in anomaly_resp.results if r.severity == "high")
    except Exception as e:
        logger.warning("Dashboard summary: anomalies failed for %s/%s (%s)", category, validation_model, e)
        total_days = anomaly_count = high_severity_count = 0

    try:
        rec = generate_recommendations(RecommendationRequest(category=category, model=validation_model))
        trend = rec.forecast_trend_pct
        mae = rec.model_mae
        recommendations = rec.recommendations
    except Exception as e:
        logger.warning("Dashboard summary: recommendations failed for %s/%s (%s)", category, validation_model, e)
        trend = 0.0
        mae = None
        recommendations = []

    return DashboardCategorySummary(
        category=category,
        best_model=best_model,
        forecast=forecast,
        validation_model=validation_model,
        total_days=total_days,
        anomaly_count=anomaly_count,
        high_severity_count=high_severity_count,
        forecast_trend_pct=trend,
        model_mae=mae,
        recommendations=recommendations,
    )


def build_dashboard_summary() -> DashboardSummaryResponse:
    return DashboardSummaryResponse(categories=[_category_summary(c) for c in VALID_CATEGORIES])
