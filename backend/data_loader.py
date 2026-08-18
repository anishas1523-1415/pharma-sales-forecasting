"""
data_loader.py
==============
Reads teammate's forecast CSVs, evaluation CSVs, and actual sales
from disk. This is the single bridge between the forecasting module
outputs and the backend services.

Teammate's forecast output format (e.g. M01AB_prophet_forecast.csv):
    ds, yhat, yhat_lower, yhat_upper

Evaluation CSV format (e.g. prophet_evaluation.csv):
    category, MAE, RMSE, MAPE_%

Actual sales (processed daily CSV):
    datum, M01AB, M01AE, N02BA, N02BE, N05B, N05C, R03, R06
"""

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FORECAST_DIR = PROJECT_ROOT / "data" / "outputs" / "forecasts"
ACTUAL_CSV = PROJECT_ROOT / "data" / "processed" / "sales_daily_processed.csv"


VALID_CATEGORIES = [
    "M01AB",
    "M01AE",
    "N02BA",
    "N02BE",
    "N05B",
    "N05C",
    "R03",
    "R06",
]

VALID_MODELS = [
    "prophet",
    "arima",
    "sarima",
    "lightgbm",
    "lstm",
]


# Map evaluation CSV column names to a standard MAPE lookup.
# Prophet uses MAPE_% while the other evaluation files use MAPE.
_EVAL_MAPE_COL = {
    "prophet": "MAPE_%",
    "arima": "MAPE",
    "sarima": "MAPE",
    "lightgbm": "MAPE",
    "lstm": "MAPE",
}


def _validate(category: str, model: str):
    """
    Validate category and model names before accessing files.
    """
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category '{category}'. Valid: {VALID_CATEGORIES}",
        )

    if model not in VALID_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{model}'. Valid: {VALID_MODELS}",
        )


def _read_forecast_csv(category: str, model: str) -> pd.DataFrame:
    """
    Read the raw forecast CSV and parse the ds column as dates.
    """
    _validate(category, model)

    path = FORECAST_DIR / f"{category}_{model}_forecast.csv"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Forecast file not found: {path.name}.",
        )

    return pd.read_csv(
        path,
        parse_dates=["ds"],
    )


def load_forecast(category: str, model: str) -> pd.DataFrame:
    """
    Load FUTURE forecast rows.

    Future rows are identified as rows where actual 'y' is null,
    or where there is no 'y' column.

    Used by:
        - what-if service
        - recommendations service
        - /forecast endpoint

    Returns:
        DataFrame with:
            date
            predicted_sales
    """

    df = _read_forecast_csv(category, model)

    # Keep only future rows where actual y is unavailable.
    if "y" in df.columns:
        df = df[df["y"].isna()].copy()

    df = df.rename(
        columns={
            "ds": "date",
            "yhat": "predicted_sales",
        }
    )

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    return (
        df[
            [
                "date",
                "predicted_sales",
            ]
        ]
        .dropna()
    )


def load_test_period(category: str, model: str) -> pd.DataFrame:
    """
    Load test-period forecast rows.

    For ARIMA/SARIMA:
        Forecast CSVs contain actual y values for the test period.

    For Prophet/LightGBM/LSTM:
        If y is not present, the forecast rows are returned and can
        later be matched against actual historical sales.

    Used by:
        - anomaly detection

    Returns:
        DataFrame with:
            date
            predicted_sales
    """

    df = _read_forecast_csv(category, model)

    # ARIMA / SARIMA:
    # Test rows contain both actual y and predicted yhat.
    if "y" in df.columns:

        test = df[df["y"].notna()].copy()

        if not test.empty:
            test = test.rename(
                columns={
                    "ds": "date",
                    "yhat": "predicted_sales",
                }
            )

            test["date"] = test["date"].dt.strftime("%Y-%m-%d")

            return (
                test[
                    [
                        "date",
                        "predicted_sales",
                    ]
                ]
                .dropna()
            )

    # Prophet / LightGBM / LSTM:
    # Forecast file does not contain actual y values.
    df = df.rename(
        columns={
            "ds": "date",
            "yhat": "predicted_sales",
        }
    )

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    return (
        df[
            [
                "date",
                "predicted_sales",
            ]
        ]
        .dropna()
    )


def load_actuals(category: str) -> pd.DataFrame:
    """
    Load actual historical sales for a category.

    Returns:
        DataFrame with:
            date
            actual_sales
    """

    if not ACTUAL_CSV.exists():
        raise HTTPException(
            status_code=500,
            detail="Processed sales CSV not found.",
        )

    df = pd.read_csv(
        ACTUAL_CSV,
        parse_dates=["datum"],
    )

    if category not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category}' not in actuals CSV.",
        )

    df = df[
        [
            "datum",
            category,
        ]
    ].rename(
        columns={
            "datum": "date",
            category: "actual_sales",
        }
    )

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    return df.dropna()


def load_mae(
    category: str,
    model: str,
) -> Optional[float]:
    """
    Load the MAE value for a category from the model's
    evaluation CSV.

    Returns:
        MAE as float if available.
        None if the evaluation file or category row is missing.
    """

    eval_path = FORECAST_DIR / f"{model}_evaluation.csv"

    if not eval_path.exists():
        return None

    try:
        df = pd.read_csv(eval_path)

        # Find category column.
        cat_col = (
            "category"
            if "category" in df.columns
            else df.columns[0]
        )

        row = df[df[cat_col] == category]

        if row.empty:
            return None

        # Read MAE.
        if "MAE" not in df.columns:
            return None

        value = row["MAE"].iloc[0]

        if pd.isna(value):
            return None

        return float(value)

    except Exception:
        return None


def load_mape(
    category: str,
    model: str,
) -> Optional[float]:
    """
    Load the MAPE value for a category from the model's
    evaluation CSV.

    Prophet uses:
        MAPE_%

    Other models use:
        MAPE

    Returns:
        MAPE as float if available.
        None if the evaluation file or category row is missing.
    """

    eval_path = FORECAST_DIR / f"{model}_evaluation.csv"

    if not eval_path.exists():
        return None

    try:
        df = pd.read_csv(eval_path)

        # Find category column.
        cat_col = (
            "category"
            if "category" in df.columns
            else df.columns[0]
        )

        row = df[df[cat_col] == category]

        if row.empty:
            return None

        # Determine the expected MAPE column for this model.
        mape_col = _EVAL_MAPE_COL.get(
            model,
            "MAPE",
        )

        # Fallback:
        # Find any column containing "MAPE".
        if mape_col not in df.columns:

            mape_cols = [
                column
                for column in df.columns
                if "MAPE" in column.upper()
            ]

            if not mape_cols:
                return None

            mape_col = mape_cols[0]

        value = row[mape_col].iloc[0]

        if pd.isna(value):
            return None

        return float(value)

    except Exception:
        return None