"""
whatif_service.py
=================
Loads teammate's forecast CSV from disk, then applies
a user-defined scenario (% demand change + optional disruption).

The forecast from disk is the baseline.
The service returns baseline vs adjusted side-by-side.
"""

from backend.data_loader import load_forecast
from backend.schemas.whatif import WhatIfRequest, WhatIfResponse, WhatIfPoint


def run_what_if(request: WhatIfRequest) -> WhatIfResponse:
    # Load teammate's forecast from disk
    forecast_df = load_forecast(request.category, request.model)

    factor = 1.0 + request.change_percent / 100.0
    disruption_days = 0
    results = []

    for _, row in forecast_df.iterrows():
        baseline = float(row["predicted_sales"])
        adjusted = baseline * factor

        # Zero out supply disruption range
        if request.disruption_start and request.disruption_end:
            if request.disruption_start <= row["date"] <= request.disruption_end:
                adjusted = 0.0
                disruption_days += 1

        adjusted = max(adjusted, 0.0)
        difference = round(adjusted - baseline, 4)
        row_pct = round((adjusted - baseline) / baseline * 100, 2) if baseline != 0 else 0.0

        results.append(WhatIfPoint(
            date=row["date"],
            baseline_sales=round(baseline, 4),
            adjusted_sales=round(adjusted, 4),
            difference=difference,
            change_percent=row_pct,
        ))

    total_baseline   = round(sum(r.baseline_sales for r in results), 4)
    total_adjusted   = round(sum(r.adjusted_sales for r in results), 4)
    total_difference = round(total_adjusted - total_baseline, 4)

    return WhatIfResponse(
        category=request.category,
        model=request.model,
        change_percent=request.change_percent,
        total_baseline=total_baseline,
        total_adjusted=total_adjusted,
        total_difference=total_difference,
        disruption_days=disruption_days,
        results=results,
    )
