"""
recommendation_service.py
=========================
Loads teammate's forecast, actual sales, and model evaluation
from disk — then generates rule-based recommendations.

Pipeline:
    1. Load forecast from disk  → compute trend
    2. Load actuals from disk   → run anomaly detection internally
    3. Load MAPE from eval CSV  → assess model reliability
    4. Load MAE from eval CSV   → expose model error information
    5. Apply rules              → return prioritised recommendations

Rules:
    Forecast trend > +10%          → RESTOCK_ALERT      (HIGH)
    Forecast trend < -10%          → OVERSTOCK_RISK     (MEDIUM)
    High-severity anomalies exist  → DEMAND_SPIKE       (HIGH)
    Model MAPE > 30%               → HIGH_UNCERTAINTY   (MEDIUM)
    Otherwise                      → STABLE_SUPPLY      (LOW)
"""

from backend.data_loader import (
    load_forecast,
    load_test_period,
    load_actuals,
    load_mape,
    load_mae,
)

from backend.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    Recommendation,
)


TREND_UP = 10.0
TREND_DOWN = -10.0
HIGH_MAPE = 30.0
ANOMALY_HIGH_THRESHOLD = 50.0


def _compute_trend(forecast_df) -> float:
    """
    Calculate percentage change from the first 5 forecast
    days to the last 5 forecast days.
    """

    if len(forecast_df) < 2:
        return 0.0

    first = forecast_df["predicted_sales"].iloc[:5].mean()
    last = forecast_df["predicted_sales"].iloc[-5:].mean()

    if first == 0:
        return 0.0

    return round(
        (last - first) / first * 100,
        2,
    )


def _count_anomalies(forecast_df, actuals_df):
    """
    Calculate anomaly counts by comparing forecasted sales
    against actual sales.

    Returns:
        total anomaly count
        high-severity anomaly count
    """

    merged = forecast_df.merge(
        actuals_df,
        on="date",
        how="inner",
    )

    total = 0
    high = 0

    for _, row in merged.iterrows():

        forecast = float(row["predicted_sales"])
        actual = float(row["actual_sales"])

        if forecast == 0:
            deviation = (
                0.0
                if actual == 0
                else 100.0
            )
        else:
            deviation = (
                abs(actual - forecast)
                / forecast
                * 100
            )

        if deviation >= 25.0:
            total += 1

        if deviation > ANOMALY_HIGH_THRESHOLD:
            high += 1

    return total, high


def generate_recommendations(
    request: RecommendationRequest,
) -> RecommendationResponse:

    # ---------------------------------------------------------
    # 1. Load data
    # ---------------------------------------------------------

    forecast_df = load_forecast(
        request.category,
        request.model,
    )

    test_df = load_test_period(
        request.category,
        request.model,
    )

    actuals_df = load_actuals(
        request.category,
    )

    mape = load_mape(
        request.category,
        request.model,
    )

    mae = load_mae(
        request.category,
        request.model,
    )

    # ---------------------------------------------------------
    # 2. Calculate trend and anomalies
    # ---------------------------------------------------------

    trend = _compute_trend(
        forecast_df,
    )

    anomaly_count, high_severity_count = _count_anomalies(
        test_df,
        actuals_df,
    )

    recs = []

    # ---------------------------------------------------------
    # 3. Trend signal
    # ---------------------------------------------------------

    if trend >= TREND_UP:

        recs.append(
            Recommendation(
                signal="RESTOCK_ALERT",
                priority="HIGH",
                recommendation=(
                    f"Increase stock levels for {request.category}. "
                    f"Demand is projected to grow by {trend:.1f}% — "
                    "ensure adequate inventory to avoid stockouts."
                ),
                rationale=(
                    f"Forecast trend is +{trend:.1f}% "
                    "over the forecast horizon."
                ),
            )
        )

    elif trend <= TREND_DOWN:

        recs.append(
            Recommendation(
                signal="OVERSTOCK_RISK",
                priority="MEDIUM",
                recommendation=(
                    f"Consider reducing procurement for {request.category}. "
                    f"Demand is projected to decline by "
                    f"{abs(trend):.1f}% — excess inventory may lead "
                    "to waste or write-offs."
                ),
                rationale=(
                    f"Forecast trend is {trend:.1f}% "
                    "over the forecast horizon."
                ),
            )
        )

    else:

        recs.append(
            Recommendation(
                signal="STABLE_SUPPLY",
                priority="LOW",
                recommendation=(
                    f"Maintain current procurement strategy for "
                    f"{request.category}. Demand is stable within "
                    "the normal range."
                ),
                rationale=(
                    f"Forecast trend is {trend:+.1f}% — "
                    "within the ±10% stable threshold."
                ),
            )
        )

    # ---------------------------------------------------------
    # 4. Anomaly signal
    # ---------------------------------------------------------

    if high_severity_count > 0:

        recs.append(
            Recommendation(
                signal="DEMAND_SPIKE",
                priority="HIGH",
                recommendation=(
                    f"Investigate demand spikes for {request.category}. "
                    f"{high_severity_count} high-severity anomaly days "
                    "detected — review safety stock and supply "
                    "chain resilience."
                ),
                rationale=(
                    f"{high_severity_count} high-severity anomalies "
                    f"(deviation > 50%) out of "
                    f"{anomaly_count} total anomaly days."
                ),
            )
        )

    elif anomaly_count > 3:

        recs.append(
            Recommendation(
                signal="DEMAND_SPIKE",
                priority="MEDIUM",
                recommendation=(
                    f"Monitor demand irregularities for "
                    f"{request.category}. {anomaly_count} anomaly "
                    "days detected in the overlapping period."
                ),
                rationale=(
                    f"{anomaly_count} days with deviation "
                    "> 25% detected."
                ),
            )
        )

    # ---------------------------------------------------------
    # 5. Model reliability signal
    # ---------------------------------------------------------

    if mape is not None and mape > HIGH_MAPE:

        recs.append(
            Recommendation(
                signal="HIGH_UNCERTAINTY",
                priority="MEDIUM",
                recommendation=(
                    f"Use caution when planning for "
                    f"{request.category}. The {request.model} model "
                    f"MAPE is {mape:.1f}% — supplement forecasts "
                    "with domain expertise before procurement decisions."
                ),
                rationale=(
                    f"Model MAPE {mape:.1f}% exceeds the "
                    f"{HIGH_MAPE}% reliability threshold."
                ),
            )
        )

    # ---------------------------------------------------------
    # 6. Sort recommendations
    # ---------------------------------------------------------

    order = {
        "HIGH": 0,
        "MEDIUM": 1,
        "LOW": 2,
    }

    recs.sort(
        key=lambda r: order.get(
            r.priority,
            3,
        )
    )

    # ---------------------------------------------------------
    # 7. Return response
    # ---------------------------------------------------------

    return RecommendationResponse(
        category=request.category,
        model=request.model,
        forecast_trend_pct=trend,
        model_mape=mape,
        model_mae=mae,
        anomaly_count=anomaly_count,
        recommendations=recs,
    )