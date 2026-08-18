from fastapi import APIRouter
from backend.schemas.anomaly import AnomalyRequest, AnomalyResponse
from backend.services.anomaly_service import detect_anomalies

router = APIRouter(prefix="/api/anomaly", tags=["Anomaly Detection"])


@router.post("/detect", response_model=AnomalyResponse)
def detect(request: AnomalyRequest):
    """
    Compare teammate's forecast output against actual historical sales.

    Loads from disk:
    - data/outputs/forecasts/{category}_{model}_forecast.csv  (teammate's output)
    - data/processed/sales_daily_processed.csv                (actual sales)

    Thresholds:
    - deviation < 10%   → normal
    - 10 – 25%          → moderate
    - 25 – 50%          → anomaly (medium)
    - > 50%             → anomaly (high)
    """
    return detect_anomalies(request)
