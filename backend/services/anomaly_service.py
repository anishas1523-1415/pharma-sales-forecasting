"""
anomaly_service.py
==================
Loads teammate's forecast CSV + actual sales CSV from disk,
joins them on date, then computes deviation-based anomaly detection.

Algorithm:
    deviation_percent = abs(actual - forecast) / forecast * 100

Thresholds (agreed team rules):
    < 10%       → normal    (low)
    10 – 25%    → moderate  (low)
    25 – 50%    → anomaly   (medium)
    > 50%       → anomaly   (high)
"""

from backend.data_loader import load_test_period, load_actuals
from backend.schemas.anomaly import AnomalyRequest, AnomalyResponse, AnomalyResult

MODERATE_THRESHOLD = 10.0
ANOMALY_THRESHOLD  = 25.0
HIGH_THRESHOLD     = 50.0


def detect_anomalies(request: AnomalyRequest) -> AnomalyResponse:
    # Load from disk — teammate's output + actual sales
    forecast_df = load_test_period(request.category, request.model)
    actuals_df  = load_actuals(request.category)

    # Join on date — only dates present in both
    merged = forecast_df.merge(actuals_df, on="date", how="inner")

    results = []
    for _, row in merged.iterrows():
        forecast = row["predicted_sales"]
        actual   = row["actual_sales"]

        if forecast == 0:
            deviation = 0.0 if actual == 0 else 100.0
        else:
            deviation = abs(actual - forecast) / forecast * 100
        deviation = round(deviation, 2)

        if deviation < MODERATE_THRESHOLD:
            status, severity = "normal", "low"
        elif deviation < ANOMALY_THRESHOLD:
            status, severity = "moderate", "low"
        elif deviation < HIGH_THRESHOLD:
            status, severity = "anomaly", "medium"
        else:
            status, severity = "anomaly", "high"

        results.append(AnomalyResult(
            date=row["date"],
            actual_sales=round(float(actual), 4),
            forecast_sales=round(float(forecast), 4),
            deviation_percent=deviation,
            status=status,
            severity=severity,
        ))

    anomaly_count = sum(1 for r in results if r.status == "anomaly")

    return AnomalyResponse(
        category=request.category,
        model=request.model,
        total_days=len(results),
        anomaly_count=anomaly_count,
        results=results,
    )
