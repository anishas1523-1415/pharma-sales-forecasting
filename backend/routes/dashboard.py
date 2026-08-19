from fastapi import APIRouter

from backend.schemas.dashboard import DashboardSummaryResponse
from backend.services.dashboard_service import build_dashboard_summary

router = APIRouter()


@router.get("/api/dashboard-summary", response_model=DashboardSummaryResponse)
def dashboard_summary():
    """
    Forecast + anomaly + recommendation data for all 8 categories in one
    call — see dashboard_service.py for why this exists instead of the
    Dashboard page firing 24 separate requests.
    """
    return build_dashboard_summary()
