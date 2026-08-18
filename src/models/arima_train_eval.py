"""
arima_train_eval.py
===================
Train and evaluate non-seasonal ARIMA models (one per drug category) using
the daily pharmaceutical-sales CSV produced during EDA.

Typical usage
-------------
# auto_arima order selection, 30-day horizon, verbose plots
python arima_train_eval.py --use-auto --horizon 30 --verbose

# Light grid-search (no pmdarima), specific categories
python arima_train_eval.py --horizon 14 --categories M01AB,N02BE

# Zero-fill gaps, rolling CV
python arima_train_eval.py --fill-method zero --cv --verbose

Required packages
-----------------
    pip install pandas numpy statsmodels pmdarima scikit-learn joblib matplotlib
"""

# ---------------------------------------------------------------------------
# Standard-library imports
# ---------------------------------------------------------------------------
import argparse
import logging
import os
import sys
import time
import traceback
import warnings
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import joblib
import matplotlib
matplotlib.use("Agg")          # non-interactive backend; safe on headless systems
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

# pmdarima is optional; only needed when --use-auto is passed
try:
    from pmdarima import auto_arima as pm_auto_arima
    PMDARIMA_AVAILABLE = True
except ImportError:
    PMDARIMA_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project-wide constants
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES: List[str] = [
    "M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"
]
DEFAULT_INPUT_PATH: str  = "data/raw/pharma_sales_kaggle/salesdaily.csv"
DEFAULT_HORIZON: int     = 30
DEFAULT_FILL_METHOD: str = "ffill"

OUT_FORECAST_DIR: str = "data/outputs/forecasts"
OUT_MODELS_DIR: str   = "data/outputs/trained_models"
OUT_PLOTS_DIR: str    = "data/outputs/forecasts/plots"


# ===========================================================================
# 1. Data loading
# ===========================================================================
def load_data(path: str) -> pd.DataFrame:
    """
    Load the daily sales CSV and parse the ``datum`` column as datetime.

    Parameters
    ----------
    path : str
        Filesystem path to ``salesdaily.csv``.

    Returns
    -------
    pd.DataFrame
        Rows sorted by date ascending; ``datum`` column is datetime dtype.
    """
    logger.info("Loading data from: %s", path)
    df = pd.read_csv(path, parse_dates=["datum"], dayfirst=False)

    if not pd.api.types.is_datetime64_any_dtype(df["datum"]):
        raise ValueError(
            "Column 'datum' could not be parsed as datetime. "
            "Verify the source CSV format."
        )

    df = df.sort_values("datum").reset_index(drop=True)
    logger.info(
        "Loaded %d rows | %s -> %s",
        len(df),
        df["datum"].min().date(),
        df["datum"].max().date(),
    )
    return df


# ===========================================================================
# 2. Series preparation
# ===========================================================================
def prepare_series(
    df: pd.DataFrame,
    category: str,
    freq: str = "D",
    fill_method: str = "ffill",
) -> pd.Series:
    """
    Extract one drug-category column, enforce a regular daily DatetimeIndex,
    and fill any gaps.

    Gap-filling rationale
    ---------------------
    ``ffill`` (default)
        Carries the most-recent observed value forward.  Pharmaceutical sales
        are typically non-zero on any business day; a recorded gap more likely
        reflects a data-entry issue than genuine zero demand.  Forward-fill
        preserves the local level without introducing look-ahead information.

    ``zero``
        Replaces gaps with literal zero.  Appropriate when there is strong
        domain evidence that no sales occurred (e.g. a drug dispensed only in
        a hospital ward that was closed).

    *Leading NaNs* (before the first observed value) are filled with 0 in
    both strategies because forward-fill cannot back-propagate, and using the
    global mean would constitute look-ahead bias.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame from :func:`load_data`.
    category : str
        Column name, e.g. ``'N02BE'``.
    freq : str
        Pandas offset alias.  Default ``'D'`` (calendar day).
    fill_method : str
        ``'ffill'`` or ``'zero'``.

    Returns
    -------
    pd.Series
        Float series with a regular DatetimeIndex; no NaN values.
    """
    if category not in df.columns:
        raise KeyError(
            f"Category '{category}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    series = df.set_index("datum")[category].astype(float)
    # Sum any duplicate dates (data quality guard)
    series = series.resample(freq).sum()

    if fill_method == "ffill":
        series = series.ffill()
    elif fill_method == "zero":
        series = series.fillna(0.0)
    else:
        raise ValueError(f"fill_method must be 'ffill' or 'zero', got '{fill_method}'")

    # Zero-fill any remaining leading NaNs (see docstring)
    series = series.fillna(0.0)

    zero_pct = 100.0 * (series == 0).mean()
    logger.info(
        "[%s] Series: %d obs | %.1f%% zero-days",
        category, len(series), zero_pct,
    )
    return series


# ===========================================================================
# 3. Stationarity test
# ===========================================================================
def check_stationarity(
    series: pd.Series,
    alpha: float = 0.05,
) -> Tuple[bool, float, dict]:
    """
    Augmented Dickey-Fuller (ADF) test for unit-root / non-stationarity.

    H₀: series has a unit root (non-stationary).
    We reject H₀ (conclude stationary) when p-value < ``alpha``.

    The ``'c'`` regression (constant, no trend) is standard for economic /
    sales data where a deterministic trend is not expected.

    Parameters
    ----------
    series : pd.Series
        Series to test (no NaN values required).
    alpha : float
        Significance level.  Default 0.05.

    Returns
    -------
    is_stationary : bool
    p_value : float
    result_dict : dict
        Full ADF output dictionary for reference.
    """
    adf_out = adfuller(series.dropna(), autolag="AIC", regression="c")
    stat, p_value, used_lags, n_obs, crit_vals = adf_out[:5]

    is_stationary = bool(p_value < alpha)
    result_dict = {
        "adf_statistic":   stat,
        "p_value":         p_value,
        "used_lags":       used_lags,
        "n_obs":           n_obs,
        "critical_values": crit_vals,
    }
    logger.info(
        "ADF: stat=%.4f | p=%.4f | lags=%d -> %s",
        stat, p_value, used_lags,
        "STATIONARY" if is_stationary else "NON-STATIONARY",
    )
    return is_stationary, p_value, result_dict


# ===========================================================================
# 4. Order selection
# ===========================================================================
def _grid_search_arima(
    series: pd.Series,
    d: int,
    p_max: int = 5,
    q_max: int = 5,
) -> Tuple[int, int, int]:
    """
    Light AIC-minimising grid search over ARIMA(p, d, q).

    ``d`` is fixed by the caller (derived from the ADF test) so the search
    covers only AR and MA orders, keeping the total number of fits to at most
    ``(p_max+1) * (q_max+1)`` — 36 by default — making it fast enough for
    interactive use without pmdarima.

    Parameters
    ----------
    series : pd.Series
    d : int
        Integration order (0 if stationary, 1 otherwise, max 2).
    p_max, q_max : int
        Upper bounds for the AR and MA order search.

    Returns
    -------
    (p, d, q) : Tuple[int, int, int]
    """
    best_aic = np.inf
    best_order = (1, d, 1)
    n_fits = (p_max + 1) * (q_max + 1)
    logger.info("Grid search: %d ARIMA(p,%d,q) candidates ...", n_fits, d)

    for p in range(p_max + 1):
        for q in range(q_max + 1):
            if p == 0 and q == 0:
                # ARIMA(0,d,0) is a random-walk/differenced mean; valid but
                # almost always dominated — keep as fallback, not skip.
                pass
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = ARIMA(
                        series,
                        order=(p, d, q),
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    ).fit(
                        method="innovations_mle",
                    )
                if res.aic < best_aic:
                    best_aic   = res.aic
                    best_order = (p, d, q)
            except Exception:
                continue   # numerically unstable combo; skip silently

    logger.info(
        "Grid search best: ARIMA%s | AIC=%.2f", best_order, best_aic
    )
    return best_order


def select_arima_order(
    series: pd.Series,
    use_auto: bool = True,
    is_stationary: bool = True,
) -> Tuple[int, int, int]:
    """
    Return the ARIMA ``(p, d, q)`` order for ``series``.

    Strategy
    --------
    **auto_arima path** (``use_auto=True``, pmdarima installed):
        Delegates to ``pmdarima.auto_arima`` with ``seasonal=False`` for a
        pure non-seasonal ARIMA search.  The library internally runs
        differencing tests (KPSS/ADF) to determine ``d`` and then performs
        a stepwise search over ``p`` and ``q``.

    **Grid-search path** (``use_auto=False`` or pmdarima missing):
        Pins ``d`` from the ADF result:
        - ``d = 0`` if already stationary (ADF p < 0.05)
        - ``d = 1`` otherwise (one difference is almost always enough for
          pharmaceutical sales; ``d = 2`` is reserved for highly integrated
          series and rarely needed)
        Then searches ``p, q ∈ [0, 5]`` by AIC.

    Parameters
    ----------
    series : pd.Series
        Training series (no NaN values).
    use_auto : bool
        Whether to attempt pmdarima auto_arima.
    is_stationary : bool
        ADF result from :func:`check_stationarity`.

    Returns
    -------
    (p, d, q) : Tuple[int, int, int]
    """
    # ---- auto_arima path ----
    if use_auto:
        if not PMDARIMA_AVAILABLE:
            logger.warning(
                "pmdarima not installed -> falling back to grid search. "
                "pip install pmdarima to enable auto_arima."
            )
        else:
            logger.info("Running auto_arima (seasonal=False, stepwise) ...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = pm_auto_arima(
                        series,
                        seasonal=False,
                        stepwise=True,
                        error_action="ignore",
                        suppress_warnings=True,
                        information_criterion="aic",
                        max_p=5, max_q=5, max_d=2,
                        trace=False,
                    )
                order = result.order
                logger.info("auto_arima selected: ARIMA%s", order)
                return order
            except Exception as exc:
                logger.warning(
                    "auto_arima failed (%s) -> falling back to grid search.", exc
                )

    # ---- grid-search path ----
    # d: 0 if ADF confirms stationarity, 1 otherwise.
    # Using d=2 is deliberately avoided unless auto_arima chooses it, because
    # double-differencing can remove meaningful signal and inflate variance.
    d = 0 if is_stationary else 1
    logger.info("Grid-search: d=%d (is_stationary=%s)", d, is_stationary)
    return _grid_search_arima(series, d=d)


# ===========================================================================
# 5. Model fitting
# ===========================================================================
def fit_arima(
    train_series: pd.Series,
    order: Tuple[int, int, int],
    exog: Optional[np.ndarray] = None,
) -> object:
    """
    Fit a ``statsmodels`` ARIMA model on the training series.

    Configuration notes
    -------------------
    * ``enforce_stationarity=False``: the optimiser is not hard-constrained to
      the stationary region.  Real sales data can sit near the boundary; a
      soft constraint lets the model converge to a useful local optimum.
    * ``enforce_invertibility=False``: same rationale for the MA polynomial.
    * ``method='lbfgs'``: limited-memory BFGS is robust and fast for moderate
      parameter counts.

    Parameters
    ----------
    train_series : pd.Series
        Training series (DatetimeIndex, no NaN).
    order : (p, d, q)
    exog : np.ndarray, optional
        Exogenous regressors aligned with ``train_series`` rows.

    Returns
    -------
    ARIMAResultsWrapper
        Fitted model object.
    """
    logger.info("Fitting ARIMA%s ...", order)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ARIMA(
            train_series,
            exog=exog,
            order=order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        result = model.fit(method="innovations_mle")

    logger.info(
        "Fitted | AIC=%.2f  BIC=%.2f",
        result.aic, result.bic,
    )
    return result


# ===========================================================================
# 6. Forecast and evaluation
# ===========================================================================
def _safe_mape(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> Tuple[float, int]:
    """
    Mean Absolute Percentage Error excluding zero actuals.

    Zero-valued actuals cause division-by-zero in standard MAPE.  The
    pharmaceutical convention is to report MAPE only over non-zero days and
    document the count of excluded zeros for transparency.

    Returns
    -------
    mape : float
        MAPE in percentage points (0-100 scale), or NaN if all actuals are 0.
    n_zeros : int
        Number of zero actuals excluded.
    """
    mask   = actual != 0
    n_zero = int((~mask).sum())
    if mask.sum() == 0:
        return np.nan, n_zero
    mape = float(
        np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100
    )
    return mape, n_zero


def forecast_and_evaluate(
    model,
    train_index: pd.DatetimeIndex,
    test_series: pd.Series,
    horizon: int,
    exog_test: Optional[np.ndarray] = None,
) -> Tuple[pd.DataFrame, dict]:
    """
    Produce out-of-sample forecasts and compute evaluation metrics.

    Uses ``get_prediction()`` which returns point forecasts **and** prediction
    intervals in a single call.  ``dynamic=True`` simulates true out-of-sample
    forecasting from the first test step onward.

    Parameters
    ----------
    model : ARIMAResultsWrapper
        Fitted ARIMA model.
    train_index : pd.DatetimeIndex
        Index of the training series (for reference only).
    test_series : pd.Series
        Held-out actuals.
    horizon : int
        Number of steps to forecast (capped at len(test_series)).
    exog_test : np.ndarray, optional
        Exogenous regressors for the test period.

    Returns
    -------
    forecast_df : pd.DataFrame
        Columns: ds, y, yhat, yhat_lower, yhat_upper.
    eval_dict : dict
        MAE, RMSE, MAPE, n_zero_actuals.
    """
    steps = min(horizon, len(test_series))

    pred_obj = model.get_prediction(
        start=test_series.index[0],
        end=test_series.index[steps - 1],
        exog=exog_test[:steps] if exog_test is not None else None,
        dynamic=True,       # true out-of-sample from step 1
    )
    summary = pred_obj.summary_frame(alpha=0.05)   # 95% prediction interval

    actual = test_series.values[:steps]
    yhat   = summary["mean"].values
    lower  = summary["mean_ci_lower"].values
    upper  = summary["mean_ci_upper"].values

    mae            = float(mean_absolute_error(actual, yhat))
    rmse           = float(np.sqrt(mean_squared_error(actual, yhat)))
    mape, n_zeros  = _safe_mape(actual, yhat)

    logger.info(
        "Eval -> MAE=%.3f | RMSE=%.3f | MAPE=%.2f%% | zeros excl. from MAPE: %d",
        mae, rmse,
        mape if not np.isnan(mape) else -1,
        n_zeros,
    )

    forecast_df = pd.DataFrame({
        "ds":         test_series.index[:steps],
        "y":          actual,
        "yhat":       yhat,
        "yhat_lower": lower,
        "yhat_upper": upper,
    })
    eval_dict = {
        "MAE":            mae,
        "RMSE":           rmse,
        "MAPE":           mape,
        "n_zero_actuals": n_zeros,
    }
    return forecast_df, eval_dict


# ===========================================================================
# 7. Residual diagnostics
# ===========================================================================
def residual_diagnostics(
    model,
    category: str,
    verbose: bool = False,
    plots_dir: str = OUT_PLOTS_DIR,
) -> dict:
    """
    Compute residual diagnostics; optionally save ACF/PACF and residual plots.

    Tests
    -----
    * **Ljung-Box** (lag=10): collective zero-autocorrelation of residuals.
      p > 0.05 indicates the model has captured the autocorrelation structure.
    * **Shapiro-Wilk**: normality of residuals (informational; ARIMA inference
      is asymptotically valid without strict normality).

    Parameters
    ----------
    model : ARIMAResultsWrapper
    category : str
    verbose : bool
        Save diagnostic PNGs when ``True``.
    plots_dir : str

    Returns
    -------
    dict : lb_pvalue, resid_mean, resid_std, sw_pvalue
    """
    residuals = model.resid.dropna()

    lb     = acorr_ljungbox(residuals, lags=[10], return_df=True)
    lb_p   = float(lb["lb_pvalue"].iloc[-1])

    sw_p = np.nan
    if len(residuals) < 5000:
        _, sw_p = stats.shapiro(residuals)

    diag = {
        "lb_pvalue":  lb_p,
        "resid_mean": float(residuals.mean()),
        "resid_std":  float(residuals.std()),
        "sw_pvalue":  float(sw_p) if not np.isnan(sw_p) else None,
    }
    logger.info(
        "[%s] Diagnostics: LB p=%.4f | resid mean=%.4f std=%.4f",
        category, lb_p, diag["resid_mean"], diag["resid_std"],
    )

    if verbose:
        os.makedirs(plots_dir, exist_ok=True)

        # --- Residual time-series + histogram ---
        fig, axes = plt.subplots(2, 1, figsize=(11, 6))
        axes[0].plot(residuals.index, residuals.values, linewidth=0.8, color="#4C72B0")
        axes[0].axhline(0, color="red", linestyle="--", linewidth=0.8)
        axes[0].set_title(f"{category} ARIMA Residuals")
        axes[0].set_ylabel("Residual")
        axes[1].hist(residuals.values, bins=40, color="#4C72B0", edgecolor="white")
        axes[1].set_title(f"{category} Residual Distribution")
        axes[1].set_xlabel("Residual value")
        plt.tight_layout()
        fig.savefig(os.path.join(plots_dir, f"{category}_arima_residuals.png"), dpi=120)
        plt.close(fig)

        # --- ACF / PACF of residuals ---
        fig2, axes2 = plt.subplots(2, 1, figsize=(10, 6))
        plot_acf(residuals, lags=40, ax=axes2[0],
                 title=f"{category} Residual ACF")
        plot_pacf(residuals, lags=40, ax=axes2[1],
                  title=f"{category} Residual PACF", method="ywm")
        plt.tight_layout()
        fig2.savefig(
            os.path.join(plots_dir, f"{category}_arima_acf_pacf.png"), dpi=120
        )
        plt.close(fig2)
        logger.info("[%s] Diagnostic plots saved -> %s", category, plots_dir)

    return diag


# ===========================================================================
# 8. Save outputs
# ===========================================================================
def save_forecast_and_model(
    category: str,
    forecast_df: pd.DataFrame,
    model,
    eval_row: dict,
    forecast_dir: str = OUT_FORECAST_DIR,
    models_dir: str   = OUT_MODELS_DIR,
) -> None:
    """
    Persist all outputs for one category.

    Files written
    -------------
    ``{forecast_dir}/{category}_arima_forecast.csv``
        Columns: ds, y, yhat, yhat_lower, yhat_upper.

    ``{models_dir}/{category}_arima.pkl``
        joblib-pickled fitted ARIMA model.

    ``{forecast_dir}/arima_evaluation.csv``
        One row appended per category; created with header on first write.
        A retry loop (up to 5 × 2 s) handles Windows file-lock errors when
        the CSV is open in Excel.

    Parameters
    ----------
    category : str
    forecast_df : pd.DataFrame
    model : ARIMAResultsWrapper
    eval_row : dict
    forecast_dir, models_dir : str
    """
    os.makedirs(forecast_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)

    # 1. Forecast CSV
    fc_path = os.path.join(forecast_dir, f"{category}_arima_forecast.csv")
    forecast_df.to_csv(fc_path, index=False, date_format="%Y-%m-%d")
    logger.info("[%s] Forecast CSV -> %s", category, fc_path)

    # 2. Model pickle
    pkl_path = os.path.join(models_dir, f"{category}_arima.pkl")
    joblib.dump(model, pkl_path)
    logger.info("[%s] Model pickle -> %s", category, pkl_path)

    # 3. Evaluation CSV (append; retry on Windows file-lock)
    eval_path    = os.path.join(forecast_dir, "arima_evaluation.csv")
    eval_df      = pd.DataFrame([eval_row])
    write_header = not os.path.exists(eval_path)
    for attempt in range(5):
        try:
            eval_df.to_csv(eval_path, mode="a", header=write_header, index=False)
            logger.info("[%s] Evaluation appended -> %s", category, eval_path)
            break
        except PermissionError:
            logger.warning(
                "[%s] arima_evaluation.csv locked (attempt %d/5). "
                "Close it in Excel and retrying in 2 s ...",
                category, attempt + 1,
            )
            time.sleep(2)
    else:
        logger.error(
            "[%s] Could not write eval row after 5 attempts. Row: %s",
            category, eval_row,
        )


# ===========================================================================
# 9. Rolling-origin cross-validation (optional)
# ===========================================================================
def rolling_origin_cv(
    series: pd.Series,
    order: Tuple[int, int, int],
    horizon: int,
    n_folds: int = 5,
) -> dict:
    """
    Rolling-origin (expanding-window) cross-validation for ARIMA.

    For each fold the model is re-fit on all data up to the fold boundary and
    then forecasts the next ``horizon`` steps.  No look-ahead bias because
    each training window only contains data available at that point in time.

    Parameters
    ----------
    series : pd.Series
    order : (p, d, q)
    horizon : int
    n_folds : int

    Returns
    -------
    dict : cv_mae, cv_rmse, cv_mape, n_folds_completed
    """
    n         = len(series)
    min_train = max(30, 3 * (max(order) + 1))   # heuristic minimum window
    step_size = max((n - min_train) // (n_folds + 1), 1)

    fold_mae, fold_rmse, fold_mape = [], [], []
    logger.info("Rolling-origin CV: %d folds, horizon=%d", n_folds, horizon)

    for fold in range(n_folds):
        cutoff = min_train + fold * step_size
        if cutoff + horizon > n:
            logger.warning("CV fold %d: insufficient data, skipping.", fold)
            break
        train_cv = series.iloc[:cutoff]
        test_cv  = series.iloc[cutoff: cutoff + horizon]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cv_model = ARIMA(
                    train_cv, order=order,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                ).fit(
                    method="innovations_mle",
                )

            _, ev = forecast_and_evaluate(cv_model, train_cv.index, test_cv, horizon)
            fold_mae.append(ev["MAE"])
            fold_rmse.append(ev["RMSE"])
            if not np.isnan(ev["MAPE"]):
                fold_mape.append(ev["MAPE"])
        except Exception as exc:
            logger.warning("CV fold %d failed: %s", fold, exc)

    return {
        "cv_mae":            float(np.mean(fold_mae))  if fold_mae  else np.nan,
        "cv_rmse":           float(np.mean(fold_rmse)) if fold_rmse else np.nan,
        "cv_mape":           float(np.mean(fold_mape)) if fold_mape else np.nan,
        "n_folds_completed": len(fold_mae),
    }


# ===========================================================================
# 10. Per-category pipeline
# ===========================================================================
def run_category(
    df: pd.DataFrame,
    category: str,
    horizon: int,
    use_auto: bool,
    fill_method: str,
    verbose: bool,
    run_cv: bool = False,
) -> Optional[dict]:
    """
    End-to-end ARIMA pipeline for one drug category.

    Steps
    -----
    1.  Prepare daily series (resample + fill).
    2.  80/20 chronological train-test split.
    3.  ADF stationarity test on the training portion only (no look-ahead).
    4.  ARIMA order selection (auto_arima or grid search).
    5.  Fit ARIMA on training data.
    6.  Evaluate on test set (MAE, RMSE, MAPE, prediction intervals).
    7.  Residual diagnostics; optional diagnostic plots.
    8.  Retrain on full history; produce ``horizon``-day future forecast.
    9.  (Optional) rolling-origin cross-validation.
    10. Save all outputs; return evaluation row.

    Per-category exceptions are caught and logged so that one failure does
    not abort processing of subsequent categories.

    Parameters
    ----------
    df : pd.DataFrame
    category : str
    horizon : int
    use_auto : bool
    fill_method : str
    verbose : bool
    run_cv : bool

    Returns
    -------
    dict or None
        Evaluation row dict, or ``None`` on failure.
    """
    logger.info("=" * 60)
    logger.info("Category: %s", category)
    logger.info("=" * 60)

    try:
        # Step 1 – prepare series
        series = prepare_series(df, category, fill_method=fill_method)

        # Step 2 – train/test split (80/20 chronological)
        split = int(len(series) * 0.80)
        train, test = series.iloc[:split], series.iloc[split:]
        logger.info(
            "Train: %d obs (%s -> %s) | Test: %d obs (%s -> %s)",
            len(train), train.index[0].date(), train.index[-1].date(),
            len(test),  test.index[0].date(),  test.index[-1].date(),
        )

        # Step 3 – stationarity (training data only; avoids look-ahead)
        is_stationary, adf_p, _ = check_stationarity(train)

        # Step 4 – order selection
        order = select_arima_order(train, use_auto=use_auto, is_stationary=is_stationary)
        p, d, q = order

        # Step 5 – fit on training data
        trained_model = fit_arima(train, order)

        # Step 6 – evaluate on test set
        test_horizon = min(horizon, len(test))
        forecast_df, eval_dict = forecast_and_evaluate(
            trained_model, train.index, test.iloc[:test_horizon], test_horizon
        )

        # Step 7 – residual diagnostics (+ optional plots)
        diag = residual_diagnostics(
            trained_model, category, verbose=verbose, plots_dir=OUT_PLOTS_DIR
        )

        # Step 7b – forecast-vs-actual plot (verbose)
        if verbose:
            os.makedirs(OUT_PLOTS_DIR, exist_ok=True)
            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(
                train.index[-90:], train.values[-90:],
                label="Train (last 90d)", color="#4C72B0", linewidth=0.9,
            )
            ax.plot(
                forecast_df["ds"], forecast_df["y"],
                label="Actual", color="#55A868",
            )
            ax.plot(
                forecast_df["ds"], forecast_df["yhat"],
                label="Forecast", color="#C44E52", linestyle="--",
            )
            ax.fill_between(
                forecast_df["ds"],
                forecast_df["yhat_lower"],
                forecast_df["yhat_upper"],
                alpha=0.25, color="#C44E52", label="95% PI",
            )
            ax.set_title(f"{category} – ARIMA{order} Test Forecast")
            ax.set_xlabel("Date")
            ax.set_ylabel("Sales (units)")
            ax.legend()
            plt.tight_layout()
            fig.savefig(
                os.path.join(OUT_PLOTS_DIR, f"{category}_arima_forecast_vs_actual.png"),
                dpi=120,
            )
            plt.close(fig)
            logger.info("[%s] Forecast plot saved.", category)

        # Step 8 – retrain on full history; future forecast
        logger.info("[%s] Retraining on full history (%d obs) ...", category, len(series))
        final_model = fit_arima(series, order)

        future_idx  = pd.date_range(
            start=series.index[-1] + pd.Timedelta(days=1),
            periods=horizon,
            freq="D",
        )
        fut_pred    = final_model.get_forecast(steps=horizon)
        fut_summary = fut_pred.summary_frame(alpha=0.05)

        future_df = pd.DataFrame({
            "ds":         future_idx,
            "y":          np.nan,    # actuals unknown for future
            "yhat":       fut_summary["mean"].values,
            "yhat_lower": fut_summary["mean_ci_lower"].values,
            "yhat_upper": fut_summary["mean_ci_upper"].values,
        })

        # Combine test-period eval forecast + future forecast
        combined_fc = pd.concat([forecast_df, future_df], ignore_index=True)

        # Step 9 – optional rolling-origin CV
        cv_results: dict = {}
        if run_cv:
            cv_results = rolling_origin_cv(train, order, horizon)

        # Step 10 – build and save evaluation row
        mape_val = eval_dict["MAPE"]
        eval_row = {
            "category":       category,
            "p": p, "d": d, "q": q,
            "MAE":            round(eval_dict["MAE"],  4),
            "RMSE":           round(eval_dict["RMSE"], 4),
            "MAPE":           round(mape_val, 4) if not np.isnan(mape_val) else None,
            "n_zero_actuals": eval_dict["n_zero_actuals"],
            "train_end":      str(train.index[-1].date()),
            "test_start":     str(test.index[0].date()),
            "lb_pvalue":      round(diag["lb_pvalue"], 4),
            "adf_pvalue":     round(adf_p, 4),
            **({f"cv_{k}": round(v, 4) if not np.isnan(v) else None
                for k, v in cv_results.items()} if cv_results else {}),
        }

        save_forecast_and_model(category, combined_fc, final_model, eval_row)
        logger.info("[%s] Complete.", category)
        return eval_row

    except Exception:
        logger.error("[%s] Failed:\n%s", category, traceback.format_exc())
        return None


# ===========================================================================
# 11. CLI
# ===========================================================================
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Examples
    --------
    # auto_arima, 30-day horizon, verbose plots
    python arima_train_eval.py --use-auto --horizon 30 --verbose

    # grid-search, two categories, zero-fill
    python arima_train_eval.py --categories M01AB,N02BE --fill-method zero

    # rolling CV on all categories
    python arima_train_eval.py --use-auto --cv --verbose
    """
    p = argparse.ArgumentParser(
        description="Non-seasonal ARIMA forecaster for pharma daily sales.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--input",       default=DEFAULT_INPUT_PATH,
                   metavar="PATH",  help="Path to salesdaily.csv")
    p.add_argument("--horizon",     type=int, default=DEFAULT_HORIZON,
                   help="Forecast horizon in days (default: 30)")
    p.add_argument("--categories",  default=",".join(DEFAULT_CATEGORIES),
                   help="Comma-separated drug categories")
    p.add_argument("--use-auto",    action="store_true", dest="use_auto",
                   help="Use pmdarima.auto_arima for order selection")
    p.add_argument("--fill-method", choices=["ffill", "zero"],
                   default=DEFAULT_FILL_METHOD, dest="fill_method",
                   help="Gap-fill strategy (default: ffill)")
    p.add_argument("--cv",          action="store_true",
                   help="Run rolling-origin cross-validation")
    p.add_argument("--verbose",     action="store_true",
                   help="Save diagnostic + forecast plots")
    return p.parse_args(argv)


# ===========================================================================
# 12. Main
# ===========================================================================
def main(argv: Optional[List[str]] = None) -> None:
    """
    Driver function: load data, iterate over categories, print summary.

    Each category is processed independently; exceptions in one do not abort
    the remaining ones.
    """
    args       = parse_args(argv)
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 52)
    logger.info("   Non-Seasonal ARIMA Pharma Sales Forecaster")
    logger.info("=" * 52)
    logger.info("Categories    : %s", categories)
    logger.info("Horizon       : %d days", args.horizon)
    logger.info("Order select  : %s", "auto_arima" if args.use_auto else "grid-search")
    logger.info("Fill method   : %s", args.fill_method)
    logger.info("Rolling CV    : %s", args.cv)
    logger.info("Verbose plots : %s", args.verbose)

    df      = load_data(args.input)
    results = []

    for cat in categories:
        row = run_category(
            df          = df,
            category    = cat,
            horizon     = args.horizon,
            use_auto    = args.use_auto,
            fill_method = args.fill_method,
            verbose     = args.verbose,
            run_cv      = args.cv,
        )
        if row:
            results.append(row)

    if results:
        cols = ["category", "p", "d", "q", "MAE", "RMSE", "MAPE", "lb_pvalue"]
        summary = pd.DataFrame(results)[[c for c in cols if c in pd.DataFrame(results).columns]]
        logger.info("\n\n%s\n\n%s\n", "-" * 76, summary.to_string(index=False))
    else:
        logger.warning("No categories processed successfully.")

    logger.info("Outputs in: %s", os.path.abspath(OUT_FORECAST_DIR))


# ===========================================================================
# Minimal unit-test style examples (run with: python -m doctest arima_train_eval.py)
# ===========================================================================
def _demo_check_stationarity() -> None:
    """
    Quick smoke-test for :func:`check_stationarity`.

    >>> import numpy as np, pandas as pd
    >>> rng = pd.date_range("2020-01-01", periods=200, freq="D")
    >>> s = pd.Series(np.random.randn(200), index=rng)   # I(0) white noise
    >>> ok, pval, _ = check_stationarity(s)
    >>> assert ok, f"Expected stationary, got p={pval:.4f}"
    """


def _demo_select_order() -> None:
    """
    Smoke-test for :func:`select_arima_order` without pmdarima.

    >>> import numpy as np, pandas as pd
    >>> rng = pd.date_range("2020-01-01", periods=100, freq="D")
    >>> s = pd.Series(np.random.randn(100), index=rng)
    >>> order = select_arima_order(s, use_auto=False, is_stationary=True)
    >>> assert len(order) == 3 and order[1] == 0  # d=0 for stationary series
    """


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # CLI examples (uncomment one block to hard-code args for testing):
    #
    # Example 1 – auto_arima, full run, verbose plots:
    #   python arima_train_eval.py --use-auto --horizon 30 --verbose
    #
    # Example 2 – grid-search, two categories, 14-day horizon:
    #   python arima_train_eval.py --categories M01AB,N02BE --horizon 14
    #
    # Example 3 – zero-fill, rolling CV, all categories:
    #   python arima_train_eval.py --fill-method zero --cv --verbose
    #
    # Example 4 – minimal defaults (grid-search, ffill, 30-day horizon):
    #   python arima_train_eval.py
    # -----------------------------------------------------------------------
    main()
