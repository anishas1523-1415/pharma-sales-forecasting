from typing import List, Optional

from pydantic import BaseModel

from backend.schemas.recommendation import Recommendation


class DashboardForecastPoint(BaseModel):
    date: str
    prediction: float


class DashboardCategorySummary(BaseModel):
    category: str
    best_model: str
    forecast: List[DashboardForecastPoint]
    validation_model: str
    total_days: int
    anomaly_count: int
    high_severity_count: int
    forecast_trend_pct: float
    model_mae: Optional[float] = None
    recommendations: List[Recommendation]


class DashboardSummaryResponse(BaseModel):
    categories: List[DashboardCategorySummary]
