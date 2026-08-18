from fastapi import APIRouter
from backend.schemas.recommendation import RecommendationRequest, RecommendationResponse
from backend.services.recommendation_service import generate_recommendations

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


@router.post("", response_model=RecommendationResponse)
def recommendations(request: RecommendationRequest):
    """
    Generate actionable business recommendations from teammate's forecast outputs.

    Loads from disk automatically:
    - data/outputs/forecasts/{category}_{model}_forecast.csv  → trend
    - data/processed/sales_daily_processed.csv                → anomaly detection
    - data/outputs/forecasts/{model}_evaluation.csv           → model MAPE

    Returns prioritised signals:
    - RESTOCK_ALERT     (HIGH)   — forecast growing > +10%
    - DEMAND_SPIKE      (HIGH)   — high-severity anomalies detected
    - OVERSTOCK_RISK    (MEDIUM) — forecast declining > -10%
    - HIGH_UNCERTAINTY  (MEDIUM) — model MAPE > 30%
    - STABLE_SUPPLY     (LOW)    — no significant signals
    """
    return generate_recommendations(request)
