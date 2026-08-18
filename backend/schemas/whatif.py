from pydantic import BaseModel
from typing import List, Optional


class WhatIfRequest(BaseModel):
    category: str           # e.g. "M01AB"
    model: str              # e.g. "prophet"
    change_percent: float   # e.g. 20 = +20%, -15 = -15%
    disruption_start: Optional[str] = None   # YYYY-MM-DD
    disruption_end: Optional[str] = None     # YYYY-MM-DD


class WhatIfPoint(BaseModel):
    date: str
    baseline_sales: float
    adjusted_sales: float
    difference: float
    change_percent: float


class WhatIfResponse(BaseModel):
    category: str
    model: str
    change_percent: float
    total_baseline: float
    total_adjusted: float
    total_difference: float
    disruption_days: int
    results: List[WhatIfPoint]
