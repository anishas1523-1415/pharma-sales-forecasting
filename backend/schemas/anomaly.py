from pydantic import BaseModel
from typing import List


class AnomalyRequest(BaseModel):
    category: str   # e.g. "M01AB"
    model: str      # e.g. "prophet"


class AnomalyResult(BaseModel):
    date: str
    actual_sales: float
    forecast_sales: float
    deviation_percent: float
    status: str     # "normal" | "moderate" | "anomaly"
    severity: str   # "low" | "medium" | "high"


class AnomalyResponse(BaseModel):
    category: str
    model: str
    total_days: int
    anomaly_count: int
    results: List[AnomalyResult]
