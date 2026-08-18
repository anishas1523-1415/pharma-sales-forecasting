from pydantic import BaseModel
from typing import List, Optional


class RecommendationRequest(BaseModel):
    category: str   # e.g. "M01AB"
    model: str      # e.g. "prophet"


class Recommendation(BaseModel):
    signal: str         # e.g. "RESTOCK_ALERT"
    priority: str       # "HIGH" | "MEDIUM" | "LOW"
    recommendation: str
    rationale: str


class RecommendationResponse(BaseModel):
    category: str
    model: str
    forecast_trend_pct: float
    model_mape: Optional[float] = None
    model_mae: Optional[float] = None
    anomaly_count: int
    recommendations: List[Recommendation]