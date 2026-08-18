from fastapi import APIRouter, HTTPException
from backend.schemas.forecast import ForecastRequest, CompareRequest
from backend.services.model_service import model_service
from backend.data_loader import load_forecast

router = APIRouter()


@router.post("/forecast")
def forecast(req: ForecastRequest):
    """Serve future forecast rows directly from pre-generated CSV files."""
    try:
        df = load_forecast(req.category, req.model)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    rows = df.head(req.horizon)
    has_bounds = "lower_bound" in df.columns and "upper_bound" in df.columns
    predictions = []
    for _, row in rows.iterrows():
        point = {"date": row["date"], "prediction": round(float(row["predicted_sales"]), 2)}
        if has_bounds:
            point["lower"] = round(float(row["lower_bound"]), 2)
            point["upper"] = round(float(row["upper_bound"]), 2)
        predictions.append(point)
    return {
        "category": req.category,
        "model": req.model,
        "horizon": req.horizon,
        "forecast": predictions,
    }


@router.post("/compare-models")
def compare_models(req: CompareRequest):
    category_metrics = model_service.metrics.get(req.category)
    if category_metrics is None:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for category '{req.category}'"
        )
    models_data = {k: v for k, v in category_metrics.items() if k != "best_model"}
    best = category_metrics.get("best_model")
    return {"category": req.category, "models": models_data, "best_model": best}
