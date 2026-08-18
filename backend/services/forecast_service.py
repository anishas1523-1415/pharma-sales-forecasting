import pandas as pd
from typing import Any, List, Dict

from backend.config import FORECASTS_DIR


def generate_forecast(model: Any, model_type: str, horizon: int, category: str = None, scaler=None) -> List[Dict]:
    if model_type == "prophet":
        return _prophet_forecast(model, horizon)
    elif model_type in ("arima", "sarima"):
        return _statsmodels_forecast(model, horizon)
    elif model_type in ("lightgbm", "lstm"):
        return _csv_forecast(model_type, category, horizon)
    raise ValueError(f"Unknown model type: {model_type}")


def _prophet_forecast(model: Any, horizon: int) -> List[Dict]:
    future = model.make_future_dataframe(periods=horizon)
    forecast = model.predict(future).tail(horizon)
    return [
        {
            "date": str(row["ds"].date()),
            "prediction": round(row["yhat"], 2),
            "lower": round(row["yhat_lower"], 2),
            "upper": round(row["yhat_upper"], 2),
        }
        for _, row in forecast.iterrows()
    ]


def _statsmodels_forecast(model: Any, horizon: int) -> List[Dict]:
    pred = model.get_forecast(steps=horizon)
    summary = pred.summary_frame(alpha=0.05)
    return [
        {
            "date": str(summary.index[i].date()) if hasattr(summary.index[i], "date") else f"step_{i+1}",
            "prediction": round(float(summary["mean"].iloc[i]), 2),
            "lower": round(float(summary["mean_ci_lower"].iloc[i]), 2),
            "upper": round(float(summary["mean_ci_upper"].iloc[i]), 2),
        }
        for i in range(min(horizon, len(summary)))
    ]


def _csv_forecast(model_type: str, category: str, horizon: int) -> List[Dict]:
    csv_path = FORECASTS_DIR / f"{category}_{model_type}_forecast.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Forecast CSV not found: {csv_path.name}")

    df = pd.read_csv(csv_path)
    if "y" in df.columns:
        df = df[df["y"].isna()].reset_index(drop=True)

    df = df.head(horizon)

    return [
        {
            "date": str(row.get("ds", f"step_{i+1}")),
            "prediction": round(float(row["yhat"]), 2),
            "lower": round(float(row["yhat_lower"]), 2) if "yhat_lower" in row and not pd.isna(row.get("yhat_lower")) else None,
            "upper": round(float(row["yhat_upper"]), 2) if "yhat_upper" in row and not pd.isna(row.get("yhat_upper")) else None,
        }
        for i, row in df.iterrows()
    ]
