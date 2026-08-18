from fastapi import APIRouter, HTTPException
from backend.data_loader import load_actuals, VALID_CATEGORIES

router = APIRouter()


@router.get("/actuals/{category}")
def get_actuals(category: str, days: int = 90):
    """
    Recent actual historical sales for a category — used by the Forecast
    Explorer's "historical overlay" so the chart shows real sales leading
    into the forecast horizon.

    Deliberately NOT sourced from /api/anomaly/detect: that endpoint's
    "actuals" are the model's held-out *validation* window (for ARIMA/
    SARIMA that's over a year before the forecast start), not the recent
    sales history a reader expects an overlay to show. Using it here
    produced a chart with a ~13-month gap between the "historical" and
    "forecast" segments.
    """
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unknown category '{category}'. Valid: {VALID_CATEGORIES}")

    df = load_actuals(category)
    tail = df.tail(days)
    return {
        "category": category,
        "results": [
            {"date": row["date"], "actual_sales": round(float(row["actual_sales"]), 4)}
            for _, row in tail.iterrows()
        ],
    }
