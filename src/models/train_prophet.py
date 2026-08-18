"""
train_prophet.py — Prophet forecasting pipeline for pharmaceutical sales.

Trains one Prophet model per drug category using the daily sales CSV.
Produces forecasts, evaluation metrics, and serialised model artefacts.

Usage examples
--------------
    # All categories, default 30-day horizon
    python src/models/train_prophet.py

    # Specific categories and 60-day horizon
    python src/models/train_prophet.py --horizon 60 --categories M01AB,N05B

    # Enable Prophet cross-validation
    python src/models/train_prophet.py --cross-validate

Design choices documented inline (search for "DESIGN:").
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Prophet import — try the modern `prophet` package first, fall back to
# the deprecated `fbprophet` for older environments.
# ---------------------------------------------------------------------------
try:
    from prophet import Prophet
    from prophet.diagnostics import cross_validation, performance_metrics
except ImportError:
    from fbprophet import Prophet  # type: ignore[no-redef]
    from fbprophet.diagnostics import cross_validation, performance_metrics  # type: ignore[no-redef]

from sklearn.metrics import mean_absolute_error, mean_squared_error

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_CSV = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle" / "salesdaily.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"
FORECAST_DIR = OUTPUT_DIR / "forecasts"
MODEL_DIR = OUTPUT_DIR / "trained_models"

ALL_CATEGORIES: List[str] = [
    "M01AB", "M01AE", "N02BA", "N02BE",
    "N05B", "N05C", "R03", "R06",
]

# Suppress noisy Prophet / cmdstanpy logs unless user asks for DEBUG
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", message=".*The frame.append method is deprecated.*")

logger = logging.getLogger(__name__)


# ===================================================================
# 1. DATA LOADING
# ===================================================================

def load_data(csv_path: Path = DATA_CSV) -> pd.DataFrame:
    """Load the raw daily-sales CSV and parse the date column.

    Parameters
    ----------
    csv_path : Path
        Location of ``salesdaily.csv``.

    Returns
    -------
    pd.DataFrame
        Sorted chronologically with ``datum`` as datetime.
    """
    logger.info("Loading data from %s", csv_path)
    df = pd.read_csv(csv_path)
    df["datum"] = pd.to_datetime(df["datum"])
    df.sort_values("datum", inplace=True)
    df.reset_index(drop=True, inplace=True)
    logger.info("Loaded %d rows  |  date range: %s → %s",
                len(df), df["datum"].min().date(), df["datum"].max().date())
    return df


# ===================================================================
# 2. SERIES PREPARATION
# ===================================================================

def prepare_series(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """Extract a single category and build a Prophet-compatible DataFrame.

    Steps
    -----
    1. Select ``datum`` and the target ``category`` column.
    2. Set ``datum`` as index and resample to daily frequency.
       - DESIGN: missing dates are **filled with 0** rather than
         forward-fill.  Rationale: a missing date most likely means the
         pharmacy was closed (no sales), so 0 is a more honest default
         than carrying the previous day's value forward.  Forward-fill
         is available via ``fill_method='ffill'`` if preferred.
    3. Rename to Prophet's required column names ``ds`` / ``y``.

    Parameters
    ----------
    df : pd.DataFrame
        Full daily-sales DataFrame (output of :func:`load_data`).
    category : str
        ATC drug-category code (e.g. ``"M01AB"``).

    Returns
    -------
    pd.DataFrame
        Columns ``['ds', 'y']``, sorted by date, daily frequency.
    """
    ts = df[["datum", category]].copy()
    ts.set_index("datum", inplace=True)

    # Resample to a strict daily grid — fill gaps with 0
    # DESIGN: fillna(0) assumes no-sale days truly had zero volume.
    ts = ts.resample("D").sum().fillna(0)

    ts.reset_index(inplace=True)
    ts.columns = ["ds", "y"]
    return ts


# ===================================================================
# 3. TRAIN & EVALUATE
# ===================================================================

def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error that gracefully handles zero actuals.

    Rows where ``y_true == 0`` are excluded from the calculation to avoid
    division-by-zero.  Returns ``NaN`` if *all* actuals are zero.
    """
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def train_and_evaluate_prophet(
    df_prophet: pd.DataFrame,
    category: str,
    horizon_days: int = 30,
    train_frac: float = 0.80,
    run_cv: bool = False,
    yearly_seasonality: bool = True,
    weekly_seasonality: bool = True,
    daily_seasonality: bool = False,
    changepoint_prior_scale: float = 0.05,
) -> Dict:
    """Train Prophet, evaluate on a held-out test set, and forecast.

    Parameters
    ----------
    df_prophet : pd.DataFrame
        Two-column DataFrame ``['ds', 'y']``.
    category : str
        Label used for logging / file-naming.
    horizon_days : int
        Number of future days to forecast after retraining on full data.
    train_frac : float
        Fraction of data used for training (chronological split).
    run_cv : bool
        If ``True``, also run Prophet's built-in rolling cross-validation.
    yearly_seasonality, weekly_seasonality, daily_seasonality : bool
        Seasonality flags forwarded to Prophet.
        DESIGN: ``daily_seasonality=False`` because the data is already
        aggregated at the daily level — sub-daily patterns do not exist.
    changepoint_prior_scale : float
        Controls trend flexibility.  Default ``0.05`` is Prophet's own
        default and provides a good balance between under- and over-fitting.
        Increase to ~0.1–0.5 for highly volatile series.

    Returns
    -------
    dict
        Keys: ``category``, ``mae``, ``rmse``, ``mape``,
        ``forecast_df`` (future forecast), ``model`` (final Prophet),
        ``test_forecast_df``, and optionally ``cv_metrics``.
    """
    n = len(df_prophet)
    split_idx = int(n * train_frac)
    train = df_prophet.iloc[:split_idx].copy()
    test = df_prophet.iloc[split_idx:].copy()
    test_horizon = len(test)

    logger.info("[%s] Total: %d  |  Train: %d  |  Test: %d",
                category, n, len(train), test_horizon)

    # ---- Train on the training partition ----
    model = Prophet(
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        daily_seasonality=daily_seasonality,
        changepoint_prior_scale=changepoint_prior_scale,
    )
    # DESIGN: Additional regressors can be added here if needed.
    # Example (uncomment and supply the column in df_prophet):
    #   model.add_regressor('holiday_flag')
    #   model.add_regressor('promo_flag')
    model.fit(train)

    # ---- Forecast on the test horizon ----
    future_test = model.make_future_dataframe(periods=test_horizon, freq="D")
    forecast_test = model.predict(future_test)

    # Align predictions with the held-out test dates
    preds = forecast_test.set_index("ds").loc[test["ds"].values]
    y_true = test["y"].values
    y_pred = preds["yhat"].values

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mape = _safe_mape(y_true, y_pred)

    logger.info("[%s] MAE=%.4f  |  RMSE=%.4f  |  MAPE=%.2f%%",
                category, mae, rmse, mape)

    result: Dict = {
        "category": category,
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "test_forecast_df": preds.reset_index()[["ds", "yhat", "yhat_lower", "yhat_upper"]],
    }

    # ---- Optional cross-validation ----
    if run_cv:
        logger.info("[%s] Running Prophet cross-validation …", category)
        try:
            # DESIGN: initial = 365 days of training, horizon = 90 days,
            # period = 30 days between cut-offs.  Adjust if the dataset
            # is shorter or if you want finer granularity.
            total_days = (df_prophet["ds"].max() - df_prophet["ds"].min()).days
            cv_initial = max(365, int(total_days * 0.5))
            cv_horizon = min(90, int(total_days * 0.15))
            cv_period = max(30, cv_horizon // 3)

            cv_df = cross_validation(
                model,
                initial=f"{cv_initial} days",
                horizon=f"{cv_horizon} days",
                period=f"{cv_period} days",
            )
            cv_metrics = performance_metrics(cv_df)
            result["cv_metrics"] = cv_metrics
            logger.info("[%s] CV metrics:\n%s", category,
                        cv_metrics[["horizon", "mae", "rmse", "mape"]].tail(5).to_string(index=False))
        except Exception as exc:
            logger.warning("[%s] Cross-validation failed: %s", category, exc)
            result["cv_metrics"] = None

    # ---- Retrain on FULL data & forecast the future ----
    logger.info("[%s] Retraining on full data and forecasting %d days ahead …",
                category, horizon_days)
    final_model = Prophet(
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        daily_seasonality=daily_seasonality,
        changepoint_prior_scale=changepoint_prior_scale,
    )
    final_model.fit(df_prophet)

    future = final_model.make_future_dataframe(periods=horizon_days, freq="D")
    forecast = final_model.predict(future)

    # Keep only the *future* portion (beyond the historical data)
    last_date = df_prophet["ds"].max()
    future_forecast = forecast[forecast["ds"] > last_date][
        ["ds", "yhat", "yhat_lower", "yhat_upper"]
    ].copy()

    result["forecast_df"] = future_forecast
    result["model"] = final_model

    return result


# ===================================================================
# 4. SAVE OUTPUTS
# ===================================================================

def save_forecast(
    result: Dict,
    forecast_dir: Path = FORECAST_DIR,
    model_dir: Path = MODEL_DIR,
) -> None:
    """Persist forecast CSV and serialised model to disk.

    Creates output directories if they do not yet exist.

    Parameters
    ----------
    result : dict
        Output of :func:`train_and_evaluate_prophet`.
    forecast_dir : Path
        Where to write ``{category}_prophet_forecast.csv``.
    model_dir : Path
        Where to write ``{category}_prophet.pkl``.
    """
    forecast_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    cat = result["category"]

    # Forecast CSV (future predictions)
    fc_path = forecast_dir / f"{cat}_prophet_forecast.csv"
    result["forecast_df"].to_csv(fc_path, index=False)
    logger.info("[%s] Forecast saved → %s", cat, fc_path)

    # Model pickle
    model_path = model_dir / f"{cat}_prophet.pkl"
    joblib.dump(result["model"], model_path)
    logger.info("[%s] Model saved  → %s", cat, model_path)


def save_evaluation_summary(
    all_results: List[Dict],
    forecast_dir: Path = FORECAST_DIR,
) -> pd.DataFrame:
    """Write / overwrite a single evaluation CSV summarising all categories.

    Parameters
    ----------
    all_results : list[dict]
        List of dicts returned by :func:`train_and_evaluate_prophet`.
    forecast_dir : Path
        Output directory for the summary CSV.

    Returns
    -------
    pd.DataFrame
        The evaluation summary table.
    """
    forecast_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in all_results:
        rows.append({
            "category": r["category"],
            "MAE": round(r["mae"], 4),
            "RMSE": round(r["rmse"], 4),
            "MAPE_%": round(r["mape"], 2) if not np.isnan(r["mape"]) else "N/A",
        })
    eval_df = pd.DataFrame(rows)
    eval_path = forecast_dir / "prophet_evaluation.csv"
    eval_df.to_csv(eval_path, index=False)
    logger.info("Evaluation summary saved → %s", eval_path)
    return eval_df


# ===================================================================
# 5. MAIN PIPELINE
# ===================================================================

def run_pipeline(
    categories: Optional[List[str]] = None,
    horizon_days: int = 30,
    run_cv: bool = False,
    csv_path: Path = DATA_CSV,
    changepoint_prior_scale: float = 0.05,
) -> List[Dict]:
    """End-to-end pipeline: load → prepare → train → evaluate → save.

    This function is the main entry point for programmatic use (e.g.
    from a Streamlit dashboard or a larger ML pipeline).

    Parameters
    ----------
    categories : list[str] | None
        ATC codes to model.  ``None`` → all 8 default categories.
    horizon_days : int
        Future days to forecast after final retraining.
    run_cv : bool
        Whether to run Prophet cross-validation.
    csv_path : Path
        Path to the input CSV.
    changepoint_prior_scale : float
        Prophet changepoint flexibility parameter.

    Returns
    -------
    list[dict]
        One result dict per category (see :func:`train_and_evaluate_prophet`).
    """
    if categories is None:
        categories = ALL_CATEGORIES

    df = load_data(csv_path)
    all_results: List[Dict] = []

    for cat in categories:
        if cat not in df.columns:
            logger.error("Category '%s' not found in data — skipping.", cat)
            continue

        try:
            logger.info("=" * 60)
            logger.info("Processing category: %s", cat)
            logger.info("=" * 60)

            df_prophet = prepare_series(df, cat)

            result = train_and_evaluate_prophet(
                df_prophet,
                category=cat,
                horizon_days=horizon_days,
                run_cv=run_cv,
                changepoint_prior_scale=changepoint_prior_scale,
            )

            save_forecast(result)
            all_results.append(result)

        except Exception:
            logger.exception("Failed to process category '%s'", cat)

    # ---- Summary ----
    if all_results:
        eval_df = save_evaluation_summary(all_results)
        print("\n" + "=" * 60)
        print("  PROPHET EVALUATION SUMMARY")
        print("=" * 60)
        print(eval_df.to_string(index=False))
        print("=" * 60 + "\n")
    else:
        logger.warning("No categories were successfully processed.")

    return all_results


# ===================================================================
# 6. CLI
# ===================================================================

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Train Prophet models for pharma sales categories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/models/train_prophet.py
  python src/models/train_prophet.py --horizon 60 --categories M01AB,N05B
  python src/models/train_prophet.py --cross-validate --changepoint-prior 0.1
        """,
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=30,
        help="Number of future days to forecast (default: 30).",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated list of ATC category codes (default: all 8).",
    )
    parser.add_argument(
        "--cross-validate",
        action="store_true",
        default=False,
        help="Run Prophet rolling cross-validation for each category.",
    )
    parser.add_argument(
        "--changepoint-prior",
        type=float,
        default=0.05,
        help="Prophet changepoint_prior_scale (default: 0.05).",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Override path to the input salesdaily.csv.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    categories = (
        [c.strip() for c in args.categories.split(",")]
        if args.categories
        else None
    )

    csv_path = Path(args.csv) if args.csv else DATA_CSV

    run_pipeline(
        categories=categories,
        horizon_days=args.horizon,
        run_cv=args.cross_validate,
        csv_path=csv_path,
        changepoint_prior_scale=args.changepoint_prior,
    )


if __name__ == "__main__":
    main()
