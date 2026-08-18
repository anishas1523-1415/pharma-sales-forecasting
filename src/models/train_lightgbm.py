#!/usr/bin/env python3
"""
LightGBM Time-Series Forecasting Pipeline — Pharma Daily Sales
================================================================
Train, tune (Optuna or GridSearch), and evaluate one LightGBM model per
ATC drug category using supervised lag/rolling features.

Dependencies
------------
    pip install pandas numpy scikit-learn lightgbm joblib optuna shap matplotlib seaborn

Example Commands
----------------
    # Train all 8 categories with defaults (GridSearch fallback)
    python src/models/train_lightgbm.py

    # Single category with Optuna tuning
    python src/models/train_lightgbm.py --categories M01AB --horizon 30 --lookback 45 \\
        --use-optuna --n-trials 50 --verbose

    # Quick smoke test
    python src/models/train_lightgbm.py --categories N05C --horizon 7 --lookback 14 --seed 42

Forecasting Strategy
--------------------
By default this script uses **recursive 1-step forecasting**: a single model
is trained to predict `y(t+1)` from features at time `t`, then at inference
time the prediction is fed back as a new lag to produce `y(t+2)`, etc.

**To switch to direct multi-output forecasting** (one model per horizon step),
set `DIRECT_STRATEGY = True` in the constants section below. Direct strategy
avoids error accumulation but trains `horizon` separate models.

Author : AI Pair Programmer / Akil (Team Lead)
Date   : 2026-08-13
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ── Optional imports (graceful fallback) ────────────────────────────
try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

try:
    import seaborn as sns
    sns.set_theme(style="whitegrid")
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# ── Constants ───────────────────────────────────────────────────────
DEFAULT_CATEGORIES = [
    "M01AB", "M01AE", "N02BA", "N02BE",
    "N05B", "N05C", "R03", "R06",
]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle" / "salesdaily.csv"
MODEL_DIR = PROJECT_ROOT / "data" / "outputs" / "trained_models"
FORECAST_DIR = PROJECT_ROOT / "data" / "outputs" / "forecasts"
PLOT_DIR = FORECAST_DIR / "plots"

# Toggle: set True to train one model per horizon step (direct strategy)
DIRECT_STRATEGY = False

logger = logging.getLogger("train_lightgbm")


# =====================================================================
#  DATA LOADING & SERIES PREPARATION
# =====================================================================
def load_data(path: Path) -> pd.DataFrame:
    """Load the raw CSV, parse ``datum`` as datetime, sort chronologically."""
    df = pd.read_csv(path, parse_dates=["datum"])
    df.sort_values("datum", inplace=True)
    df.reset_index(drop=True, inplace=True)
    logger.info(
        "Loaded %d rows  |  date range: %s -> %s",
        len(df),
        df["datum"].min().date(),
        df["datum"].max().date(),
    )
    return df


def prepare_series(
    df: pd.DataFrame,
    category: str,
    freq: str = "D",
    fill_method: str = "ffill",
) -> pd.Series:
    """Extract a single category's daily series, resample, and fill gaps.

    Parameters
    ----------
    fill_method : str
        ``'ffill'`` — forward-fill then back-fill (default; smoother for
        tree models).
        ``'zero'`` — fill gaps with 0.0 (closed-pharmacy days).
    """
    ts = df.set_index("datum")[category].copy()
    ts = ts.asfreq(freq)
    if fill_method == "ffill":
        ts = ts.ffill().bfill()
    else:
        ts = ts.fillna(0.0)
    ts.name = category
    return ts


# =====================================================================
#  FEATURE ENGINEERING
# =====================================================================
def create_features(series: pd.Series, lookback: int) -> pd.DataFrame:
    """Convert a univariate series into a supervised-learning DataFrame.

    Features created
    ----------------
    - ``lag_1`` … ``lag_{lookback}``
    - Rolling mean / std / min / max for windows 7, 14, 30 (clamped to lookback)
    - Calendar: day-of-week, day-of-month, month, quarter, year, is_weekend
    - Lag-based percentage change (lag_1 vs lag_2)

    The **target** column ``y`` is the value at time *t* (i.e., the model
    predicts the current step from past lags).  For 1-step-ahead, the lags
    already represent ``t-1, t-2, …``, so there is no leakage.
    """
    df = pd.DataFrame(index=series.index)
    df["y"] = series.values

    # ── Lag features ────────────────────────────────────────────────
    for lag in range(1, lookback + 1):
        df[f"lag_{lag}"] = series.shift(lag).values

    # ── Rolling statistics ──────────────────────────────────────────
    for win in [7, 14, 30]:
        if win > lookback:
            continue
        rolled = series.shift(1).rolling(window=win, min_periods=1)
        df[f"rolling_mean_{win}"] = rolled.mean().values
        df[f"rolling_std_{win}"] = rolled.std(ddof=0).values
        df[f"rolling_min_{win}"] = rolled.min().values
        df[f"rolling_max_{win}"] = rolled.max().values

    # ── Calendar features ───────────────────────────────────────────
    idx = series.index
    df["day_of_week"] = idx.dayofweek
    df["day_of_month"] = idx.day
    df["month"] = idx.month
    df["quarter"] = idx.quarter
    df["year"] = idx.year
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)

    # ── Percentage change (lag 1 vs lag 2) ──────────────────────────
    df["pct_change_1"] = (
        (df["lag_1"] - df["lag_2"]) / df["lag_2"].replace(0, np.nan)
    ).fillna(0.0)

    # Drop rows with NaN from lagging
    df.dropna(inplace=True)

    return df


# =====================================================================
#  TRAIN / TEST SPLIT (CHRONOLOGICAL)
# =====================================================================
def time_series_train_test_split(
    X: pd.DataFrame,
    y: pd.Series,
    train_frac: float = 0.8,
):
    """80/20 chronological split — no shuffling, no leakage."""
    n = len(X)
    split_idx = int(n * train_frac)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    train_index = X_train.index
    test_index = X_test.index
    return X_train, X_test, y_train, y_test, train_index, test_index


# =====================================================================
#  MODEL TRAINING
# =====================================================================
def train_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    params: dict,
    early_stopping_rounds: int = 50,
    seed: int = 42,
) -> lgb.LGBMRegressor:
    """Train a single LGBMRegressor with early stopping on validation MAE."""
    model_params = {
        "objective": "regression",
        "metric": "mae",
        "n_jobs": -1,
        "random_state": seed,
        "verbosity": -1,
        **params,
    }
    model = lgb.LGBMRegressor(**model_params)
    model.fit(
        X_train,
        y_train,
        eval_X=X_val,
        eval_y=y_val,
        callbacks=[
            lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=False),
            lgb.log_evaluation(period=0),  # suppress per-iteration logs
        ],
    )
    return model


# =====================================================================
#  HYPERPARAMETER TUNING
# =====================================================================
def tune_hyperparameters(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    use_optuna: bool = False,
    n_trials: int = 50,
    seed: int = 42,
) -> dict:
    """Return best hyperparameters via Optuna (if available) or GridSearch."""

    if use_optuna and HAS_OPTUNA:
        return _tune_optuna(X_train, y_train, X_val, y_val, n_trials, seed)
    return _tune_grid(X_train, y_train, X_val, y_val, seed)


def _tune_optuna(
    X_train, y_train, X_val, y_val, n_trials, seed
) -> dict:
    """Optuna TPE sampler optimising validation MAE."""

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 2000),
            "num_leaves": trial.suggest_int("num_leaves", 15, 127),
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.3, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        }
        model = train_lightgbm(X_train, y_train, X_val, y_val, params, seed=seed)
        preds = model.predict(X_val)
        return mean_absolute_error(y_val, preds)

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    logger.info(
        "Optuna best MAE=%.4f  after %d trials", study.best_value, n_trials
    )
    return study.best_params


def _tune_grid(X_train, y_train, X_val, y_val, seed) -> dict:
    """Small manual grid search (time-series aware — single val set)."""
    best_mae, best_params = float("inf"), {}
    grid = {
        "n_estimators": [300, 600, 1000],
        "num_leaves": [31, 63],
        "max_depth": [5, 8],
        "learning_rate": [0.05, 0.1],
        "subsample": [0.8],
        "colsample_bytree": [0.8],
        "reg_alpha": [0.1],
        "reg_lambda": [0.1],
        "min_child_samples": [20],
    }
    # Expand grid into list of dicts
    from itertools import product as _product

    keys = list(grid.keys())
    for combo in _product(*grid.values()):
        params = dict(zip(keys, combo))
        try:
            model = train_lightgbm(
                X_train, y_train, X_val, y_val, params, seed=seed
            )
            preds = model.predict(X_val)
            mae = mean_absolute_error(y_val, preds)
            if mae < best_mae:
                best_mae, best_params = mae, params
        except Exception:
            continue

    logger.info("GridSearch best MAE=%.4f", best_mae)
    return best_params


# =====================================================================
#  FORECASTING
# =====================================================================
def forecast_recursive(
    model: lgb.LGBMRegressor,
    series: pd.Series,
    lookback: int,
    horizon: int,
    last_date: pd.Timestamp,
) -> pd.DataFrame:
    """Recursive 1-step forecasting: predict one day, feed back, repeat.

    This is the default strategy.  It can accumulate error over long
    horizons but requires only a single trained model.

    To switch to **direct multi-output**, train ``horizon`` separate
    models each targeting ``y(t+h)`` for h=1..horizon and call them
    independently (see ``DIRECT_STRATEGY`` constant at the top of the
    file).
    """
    # Build the last known feature window
    tail = series.values[-lookback - 30:]  # extra buffer for rolling
    preds = []
    history = list(tail)

    for step in range(1, horizon + 1):
        # Create feature row from current history
        feat = _build_single_row(history, lookback, last_date + pd.Timedelta(days=step))
        yhat = float(model.predict(feat)[0])
        yhat = max(yhat, 0.0)  # sales can't be negative
        preds.append(yhat)
        history.append(yhat)

    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D"
    )
    return pd.DataFrame({"ds": future_dates, "yhat": preds})


def _build_single_row(
    history: list, lookback: int, date: pd.Timestamp
) -> pd.DataFrame:
    """Construct one feature row matching ``create_features`` column order."""
    arr = np.array(history, dtype=np.float64)
    row = {}

    # Lags (lag_1 is the most recent value)
    for lag in range(1, lookback + 1):
        row[f"lag_{lag}"] = arr[-(lag)]

    # Rolling stats (computed on shifted series, i.e., from lag_1 onward)
    shifted = arr[:-0] if len(arr) > 0 else arr  # full history
    for win in [7, 14, 30]:
        if win > lookback:
            continue
        window = arr[-win:]
        row[f"rolling_mean_{win}"] = float(np.mean(window))
        row[f"rolling_std_{win}"] = float(np.std(window))
        row[f"rolling_min_{win}"] = float(np.min(window))
        row[f"rolling_max_{win}"] = float(np.max(window))

    # Calendar
    row["day_of_week"] = date.dayofweek
    row["day_of_month"] = date.day
    row["month"] = date.month
    row["quarter"] = date.quarter
    row["year"] = date.year
    row["is_weekend"] = int(date.dayofweek >= 5)

    # Pct change
    lag1 = row.get("lag_1", 0.0)
    lag2 = row.get("lag_2", 0.0)
    row["pct_change_1"] = (lag1 - lag2) / lag2 if lag2 != 0 else 0.0

    return pd.DataFrame([row])


# =====================================================================
#  EVALUATION
# =====================================================================
def evaluate_forecast(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute MAE, RMSE, and safe MAPE (excluding zero-actual days)."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    # Safe MAPE — exclude zeros in actuals
    mask = y_true != 0
    if mask.sum() > 0:
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
    else:
        mape = float("nan")
    return {"MAE": round(mae, 4), "RMSE": round(rmse, 4), "MAPE": round(mape, 2)}


# =====================================================================
#  PLOTS & ARTIFACTS
# =====================================================================
def feature_importance_plot(
    model: lgb.LGBMRegressor,
    feature_names: list[str],
    out_path: Path,
    top_n: int = 25,
):
    """Save a horizontal bar chart of LightGBM feature importances."""
    imp = model.feature_importances_
    idx = np.argsort(imp)[-top_n:]
    fig, ax = plt.subplots(figsize=(8, max(4, len(idx) * 0.35)))
    ax.barh(
        [feature_names[i] for i in idx],
        imp[idx],
        color="#3B82F6",
        edgecolor="#1E3A8A",
    )
    ax.set_xlabel("Importance (split count)")
    ax.set_title(f"LightGBM Feature Importance — Top {top_n}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    logger.info("Feature importance plot -> %s", out_path)


def shap_summary_plot(
    model: lgb.LGBMRegressor,
    X_sample: pd.DataFrame,
    out_path: Path,
):
    """Create a SHAP summary (bee-swarm) plot if shap is installed."""
    if not HAS_SHAP:
        return
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)
    fig = plt.figure()
    shap.summary_plot(shap_values, X_sample, show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("SHAP summary plot -> %s", out_path)


def save_artifacts(
    category: str,
    model: lgb.LGBMRegressor,
    forecast_df: pd.DataFrame,
    metrics: dict,
    best_params: dict,
    model_dir: Path,
    forecast_dir: Path,
):
    """Persist model binary, forecast CSV, and evaluation row."""
    model_dir.mkdir(parents=True, exist_ok=True)
    forecast_dir.mkdir(parents=True, exist_ok=True)

    # Model
    model_path = model_dir / f"{category}_lightgbm.pkl"
    joblib.dump(model, model_path)
    logger.info("[%s] Model saved  -> %s", category, model_path)

    # Forecast CSV
    csv_path = forecast_dir / f"{category}_lightgbm_forecast.csv"
    forecast_df.to_csv(csv_path, index=False)
    logger.info("[%s] Forecast CSV -> %s", category, csv_path)


# =====================================================================
#  PER-CATEGORY PIPELINE
# =====================================================================
def run_category(
    df: pd.DataFrame,
    category: str,
    lookback: int,
    horizon: int,
    fill_method: str,
    use_optuna: bool,
    n_trials: int,
    seed: int,
    verbose: bool,
) -> dict | None:
    """Full pipeline for one drug category.  Returns metrics dict or None."""
    logger.info("=" * 60)
    logger.info("Processing category: %s", category)
    logger.info("=" * 60)

    # 1. Prepare series
    series = prepare_series(df, category, fill_method=fill_method)

    # 2. Guard: sufficient history
    min_needed = lookback + horizon + 60
    if len(series) < min_needed:
        logger.warning(
            "[%s] Insufficient history (%d < %d). Skipping.", category, len(series), min_needed
        )
        return None

    # 3. Build supervised dataset
    feat_df = create_features(series, lookback)
    X = feat_df.drop(columns=["y"])
    y = feat_df["y"]
    feature_names = list(X.columns)

    # 4. Chronological split
    X_train, X_test, y_train, y_test, train_idx, test_idx = (
        time_series_train_test_split(X, y, train_frac=0.8)
    )

    # Use last 20% of train as early-stopping validation
    val_split = int(len(X_train) * 0.8)
    X_tr, X_val = X_train.iloc[:val_split], X_train.iloc[val_split:]
    y_tr, y_val = y_train.iloc[:val_split], y_train.iloc[val_split:]

    logger.info(
        "[%s] Samples: train=%d  val=%d  test=%d  |  features=%d",
        category, len(X_tr), len(X_val), len(X_test), len(feature_names),
    )

    # 5. Hyperparameter tuning
    logger.info("[%s] Tuning hyperparameters (%s) ...",
                category, "Optuna" if (use_optuna and HAS_OPTUNA) else "GridSearch")
    best_params = tune_hyperparameters(
        X_tr, y_tr, X_val, y_val, use_optuna=use_optuna, n_trials=n_trials, seed=seed
    )
    logger.info("[%s] Best params: %s", category, best_params)

    # 6. Retrain on full train set with best params
    logger.info("[%s] Training final model on full train split ...", category)
    final_model = train_lightgbm(
        X_train, y_train, X_test, y_test, best_params, early_stopping_rounds=50, seed=seed
    )

    # 7. Evaluate on test set
    y_pred_test = final_model.predict(X_test)
    y_pred_test = np.clip(y_pred_test, 0, None)  # floor at 0
    metrics = evaluate_forecast(y_test.values, y_pred_test)
    logger.info(
        "[%s] MAE=%.4f  |  RMSE=%.4f  |  MAPE=%.2f%%",
        category, metrics["MAE"], metrics["RMSE"], metrics["MAPE"],
    )

    # 8. Retrain on ALL data and produce future forecast
    logger.info("[%s] Retraining on full data for future forecast ...", category)
    # Use last 10% as validation for early stopping during full retrain
    full_val_split = int(len(X) * 0.9)
    X_full_tr, X_full_val = X.iloc[:full_val_split], X.iloc[full_val_split:]
    y_full_tr, y_full_val = y.iloc[:full_val_split], y.iloc[full_val_split:]
    full_model = train_lightgbm(
        X_full_tr, y_full_tr, X_full_val, y_full_val, best_params,
        early_stopping_rounds=50, seed=seed,
    )

    last_date = series.index[-1]
    forecast_df = forecast_recursive(full_model, series, lookback, horizon, last_date)
    logger.info("[%s] Forecast generated: %s -> %s", category,
                forecast_df["ds"].iloc[0].date(), forecast_df["ds"].iloc[-1].date())

    # 9. Feature importance plot
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fi_path = PLOT_DIR / f"{category}_lightgbm_feature_importance.png"
    feature_importance_plot(full_model, feature_names, fi_path)

    # 9b. SHAP plot (verbose only)
    if verbose and HAS_SHAP:
        shap_path = PLOT_DIR / f"{category}_lightgbm_shap.png"
        sample = X_test.sample(n=min(200, len(X_test)), random_state=seed)
        try:
            shap_summary_plot(full_model, sample, shap_path)
        except Exception as e:
            logger.warning("[%s] SHAP plot failed: %s", category, e)

    # 10. Save artifacts
    save_artifacts(
        category, full_model, forecast_df, metrics, best_params, MODEL_DIR, FORECAST_DIR
    )

    metrics["category"] = category
    metrics["train_end"] = str(train_idx[-1].date())
    metrics["test_start"] = str(test_idx[0].date())
    metrics["model_params"] = str(best_params)
    return metrics


# =====================================================================
#  CLI & MAIN
# =====================================================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train LightGBM time-series models per pharma drug category."
    )
    p.add_argument("--horizon", type=int, default=30, help="Days to forecast (default: 30)")
    p.add_argument("--lookback", type=int, default=30, help="Lag window for features (default: 30)")
    p.add_argument("--categories", type=str, default=None,
                   help="Comma-separated category list (default: all 8)")
    p.add_argument("--use-optuna", action="store_true", help="Enable Optuna hyperparameter tuning")
    p.add_argument("--n-trials", type=int, default=50, help="Optuna trials (default: 50)")
    p.add_argument("--fill-method", type=str, default="ffill", choices=["ffill", "zero"],
                   help="Missing value strategy (default: ffill)")
    p.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging & extra plots")
    return p.parse_args(argv)


def main(argv: list[str] | None = None):
    args = parse_args(argv)

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stdout,
    )
    warnings.filterwarnings("ignore", category=UserWarning)

    if not HAS_LGB:
        logger.error("lightgbm is not installed. Run: pip install lightgbm")
        sys.exit(1)

    # Reproducibility
    np.random.seed(args.seed)
    random.seed(args.seed)

    logger.info("Random seed set to %d", args.seed)

    categories = (
        [c.strip() for c in args.categories.split(",")]
        if args.categories
        else DEFAULT_CATEGORIES
    )

    # Load data
    logger.info("Loading data from %s", DEFAULT_CSV)
    df = load_data(DEFAULT_CSV)

    # Create output dirs
    for d in [MODEL_DIR, FORECAST_DIR, PLOT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Run pipeline per category
    all_metrics = []
    for cat in categories:
        try:
            result = run_category(
                df, cat,
                lookback=args.lookback,
                horizon=args.horizon,
                fill_method=args.fill_method,
                use_optuna=args.use_optuna,
                n_trials=args.n_trials,
                seed=args.seed,
                verbose=args.verbose,
            )
            if result is not None:
                all_metrics.append(result)
        except Exception as exc:
            logger.error("[%s] FAILED: %s", cat, exc, exc_info=args.verbose)

    # Evaluation summary CSV
    if all_metrics:
        eval_df = pd.DataFrame(all_metrics)
        eval_path = FORECAST_DIR / "lightgbm_evaluation.csv"
        eval_df.to_csv(eval_path, index=False)
        logger.info("Evaluation summary saved -> %s", eval_path)

        # Pretty print
        print("\n" + "=" * 70)
        print("  LIGHTGBM EVALUATION SUMMARY")
        print("=" * 70)
        display_cols = ["category", "MAE", "RMSE", "MAPE"]
        print(eval_df[display_cols].to_string(index=False))
        print("=" * 70)
        print()


if __name__ == "__main__":
    main()
