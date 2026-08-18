"""
sarima_train_eval.py
====================
Train and evaluate SARIMA models (one per drug category) using the daily
pharmaceutical-sales CSV produced during EDA.

Typical usage
-------------
# Auto-ARIMA, 30-day horizon, weekly seasonality, verbose plots
python sarima_train_eval.py --use-auto --horizon 30 --verbose

# Manual grid-search, specific categories, 14-day horizon
python sarima_train_eval.py --horizon 14 --categories M01AB,N02BE --seasonal-period 7

# Fill missing values with zero instead of forward-fill
python sarima_train_eval.py --fill-method zero --verbose

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
import traceback
import warnings
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import joblib
import matplotlib
matplotlib.use("Agg")          # non-interactive backend – safe on headless systems
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller

# pmdarima is optional – guarded by the --use-auto flag
try:
    from pmdarima import auto_arima as pm_auto_arima
    PMDARIMA_AVAILABLE = True
except ImportError:
    PMDARIMA_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES: List[str] = [
    "M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"
]
DEFAULT_INPUT_PATH: str = "data/raw/pharma_sales_kaggle/salesdaily.csv"
DEFAULT_HORIZON: int = 30
DEFAULT_SEASONAL_PERIOD: int = 7   # weekly (daily data)
DEFAULT_FILL_METHOD: str = "ffill"

# Output directories (relative to the project root / working directory)
OUT_FORECAST_DIR: str  = "data/outputs/forecasts"
OUT_MODELS_DIR: str    = "data/outputs/trained_models"
OUT_PLOTS_DIR: str     = "data/outputs/forecasts/plots"


# ===========================================================================
# 1. Data loading
# ===========================================================================
def load_data(path: str) -> pd.DataFrame:
    """
    Load the daily sales CSV and parse the ``datum`` column as a datetime index.

    Parameters
    ----------
    path : str
        File-system path to ``salesdaily.csv``.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by a DatetimeIndex (daily frequency not yet enforced
        here – that is done per-series in :func:`prepare_series`).
    """
    logger.info("Loading data from: %s", path)

    df = pd.read_csv(path, parse_dates=["datum"], dayfirst=False)

    # Validate that the date column parsed correctly
    if not pd.api.types.is_datetime64_any_dtype(df["datum"]):
        raise ValueError(
            "Column 'datum' could not be parsed as datetime. "
            "Check the source file format."
        )

    df = df.sort_values("datum").reset_index(drop=True)
    logger.info(
        "Loaded %d rows spanning %s -> %s",
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
    Extract one drug-category column, set a DatetimeIndex, resample to a
    regular daily frequency, and fill gaps.

    Filling strategy rationale
    --------------------------
    * Forward-fill (``ffill``): carries the last known sale value forward.
      This is sensible for pharmaceutical sales where zero-recorded days often
      represent closed pharmacies or data-entry gaps rather than true zero
      demand.  Using the prior day's value is a conservative, smooth
      assumption that keeps the series stationary-friendly.

    * Zero-fill (``zero``): replaces gaps with 0. Appropriate when you have
      strong domain evidence that the pharmacy was genuinely open but recorded
      no sales (e.g. certain hospital-only drugs).

    In **both** strategies any *leading* NaNs (before the first observed value)
    are filled with 0, because forward-fill cannot back-propagate and using
    the overall mean for leading NaNs would introduce look-ahead bias.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame from :func:`load_data`.
    category : str
        Column name (e.g. ``'M01AB'``).
    freq : str, optional
        Pandas offset alias for resampling.  Default ``'D'`` (calendar day).
    fill_method : str, optional
        ``'ffill'`` or ``'zero'``.

    Returns
    -------
    pd.Series
        Float series with a regular DatetimeIndex and no NaN values.
    """
    if category not in df.columns:
        raise KeyError(f"Category '{category}' not found in dataset columns: {list(df.columns)}")

    series = df.set_index("datum")[category].astype(float)

    # Resample to enforce regularity; sum within any day that has duplicates
    series = series.resample(freq).sum()

    # Now apply the chosen gap-filling strategy
    if fill_method == "ffill":
        # Forward-fill interior / trailing gaps
        series = series.ffill()
    elif fill_method == "zero":
        series = series.fillna(0.0)
    else:
        raise ValueError(f"fill_method must be 'ffill' or 'zero', got '{fill_method}'")

    # Zero-fill any remaining leading NaNs (see docstring rationale)
    series = series.fillna(0.0)

    logger.info(
        "[%s] Series prepared: %d daily observations, %.1f%% zero-days",
        category,
        len(series),
        100.0 * (series == 0).mean(),
    )
    return series


# ===========================================================================
# 3. Stationarity check
# ===========================================================================
def check_stationarity(series: pd.Series, alpha: float = 0.05) -> Tuple[bool, float, dict]:
    """
    Augmented Dickey-Fuller (ADF) test for unit-root (non-stationarity).

    The ADF null hypothesis is that the series has a unit root, i.e. it is
    **non-stationary**.  We reject H0 when p-value < ``alpha``.

    Parameters
    ----------
    series : pd.Series
        The time series to test (must have no NaN values).
    alpha : float, optional
        Significance level.  Default 0.05.

    Returns
    -------
    is_stationary : bool
        ``True`` if the series appears stationary at level ``alpha``.
    p_value : float
        ADF p-value.
    result_dict : dict
        Full ADF output (test statistic, critical values, lags used).
    """
    # Constant + trend specification; for sales data a simple constant ('c') is usually adequate.
    adf_result = adfuller(series.dropna(), autolag="AIC", regression="c")
    stat, p_value, used_lags, n_obs, crit_vals, *_ = adf_result

    is_stationary = p_value < alpha

    result_dict = {
        "adf_statistic": stat,
        "p_value": p_value,
        "used_lags": used_lags,
        "n_obs": n_obs,
        "critical_values": crit_vals,
    }

    logger.info(
        "ADF test -> stat=%.4f, p=%.4f, lags=%d | %s",
        stat,
        p_value,
        used_lags,
        "STATIONARY" if is_stationary else "NON-STATIONARY",
    )
    return is_stationary, p_value, result_dict


# ===========================================================================
# 4. Order selection
# ===========================================================================
def _grid_search_sarima(
    series: pd.Series,
    d: int,
    D: int,
    m: int,
    p_range: range = range(0, 4),
    q_range: range = range(0, 4),
    P_range: range = range(0, 2),
    Q_range: range = range(0, 2),
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int, int]]:
    """
    Light AIC-minimising grid search for SARIMA(p,d,q)(P,D,Q,m) orders.

    ``d`` and ``D`` are fixed (determined by ADF / caller) to avoid double-
    differencing and keep the search tractable.

    Parameters
    ----------
    series : pd.Series
        Training series.
    d, D : int
        Non-seasonal and seasonal integration orders.
    m : int
        Seasonal period.
    p_range, q_range, P_range, Q_range : range
        Search grids for AR/MA orders.

    Returns
    -------
    order : (p, d, q)
    seasonal_order : (P, D, Q, m)
    """
    best_aic = np.inf
    best_order = (1, d, 1)
    best_seasonal = (1, D, 1, m)

    total = len(p_range) * len(q_range) * len(P_range) * len(Q_range)
    logger.info("Grid search: %d candidate SARIMA models ...", total)

    for p in p_range:
        for q in q_range:
            for P in P_range:
                for Q in Q_range:
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            model = SARIMAX(
                                series,
                                order=(p, d, q),
                                seasonal_order=(P, D, Q, m),
                                trend="c",
                                enforce_stationarity=False,
                                enforce_invertibility=False,
                            )
                            res = model.fit(disp=False, maxiter=100)
                        if res.aic < best_aic:
                            best_aic = res.aic
                            best_order = (p, d, q)
                            best_seasonal = (P, D, Q, m)
                    except Exception:
                        # Some parameter combos are numerically unstable - skip
                        continue

    logger.info(
        "Grid search best -> order=%s, seasonal=%s, AIC=%.2f",
        best_order,
        best_seasonal,
        best_aic,
    )
    return best_order, best_seasonal


def select_sarima_order(
    series: pd.Series,
    m: int,
    use_auto: bool = True,
    is_stationary: bool = True,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int, int]]:
    """
    Determine SARIMA(p,d,q)(P,D,Q,m) orders for ``series``.

    Strategy
    --------
    * **auto_arima** path (``use_auto=True``): delegates entirely to
      ``pmdarima.auto_arima`` which performs stepwise search with
      differencing tests (KPSS/ADF) internally.

    * **Grid-search** path (``use_auto=False``): uses :func:`check_stationarity`
      result to pin ``d`` (0 if stationary, 1 otherwise, capped at 2) and
      ``D`` (1 if non-stationary and m>1, else 0), then searches p,q in [0,3]
      and P,Q in [0,1] by AIC.

    Parameters
    ----------
    series : pd.Series
        Training series (no NaNs).
    m : int
        Seasonal period.
    use_auto : bool
        Whether to use ``pmdarima.auto_arima``.
    is_stationary : bool
        Result from :func:`check_stationarity` - used only on the grid-search
        path.

    Returns
    -------
    order : (p, d, q)
    seasonal_order : (P, D, Q, m)
    """
    if use_auto:
        if not PMDARIMA_AVAILABLE:
            logger.warning(
                "pmdarima not installed - falling back to grid search. "
                "Install with: pip install pmdarima"
            )
        else:
            logger.info("Running auto_arima (m=%d, stepwise) ...", m)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    auto_res = pm_auto_arima(
                        series,
                        seasonal=True,
                        m=m,
                        stepwise=True,
                        trace=False,
                        error_action="ignore",
                        suppress_warnings=True,
                        information_criterion="aic",
                        max_p=3, max_q=3,
                        max_P=2, max_Q=2,
                        max_d=2, max_D=1,
                        trend="c",
                    )
                order = auto_res.order
                s_order = auto_res.seasonal_order
                logger.info(
                    "auto_arima selected -> order=%s, seasonal=%s",
                    order, s_order,
                )
                return order, s_order
            except Exception as exc:
                logger.warning("auto_arima failed (%s) - falling back to grid search.", exc)

    # ---- Grid-search path ----
    # Determine integration orders from stationarity test.
    # d: number of non-seasonal differences needed.
    #    0 if already stationary; 1 otherwise (cap at 2 to avoid over-differencing).
    d = 0 if is_stationary else 1
    # D: seasonal difference applied when m > 1 and data is non-stationary.
    #    One seasonal difference is usually sufficient for weekly-periodic sales data.
    D = 0 if (is_stationary or m <= 1) else 1

    logger.info(
        "Grid-search with d=%d, D=%d (is_stationary=%s)", d, D, is_stationary
    )
    return _grid_search_sarima(series, d=d, D=D, m=m)


# ===========================================================================
# 5. Model fitting
# ===========================================================================
def fit_sarimax(
    train_series: pd.Series,
    order: Tuple[int, int, int],
    seasonal_order: Tuple[int, int, int, int],
    exog: Optional[np.ndarray] = None,
) -> object:
    """
    Fit a ``statsmodels`` SARIMAX model on the training series.

    Settings
    --------
    * ``trend='c'``: includes a constant term (intercept), which is sensible
      for pharmaceutical demand data that has a non-zero baseline.
    * ``enforce_stationarity=False`` / ``enforce_invertibility=False``:
      prevents the solver from hard-rejecting slightly boundary-crossing
      parameters - common with real-world messy series; the model can still
      converge to a good fit.

    Parameters
    ----------
    train_series : pd.Series
        Training portion of the series (datetime-indexed, no NaNs).
    order : (p, d, q)
        Non-seasonal ARIMA order.
    seasonal_order : (P, D, Q, m)
        Seasonal ARIMA order with period m.
    exog : np.ndarray, optional
        Exogenous regressors aligned with ``train_series``.

    Returns
    -------
    SARIMAXResultsWrapper
        Fitted model results object.
    """
    logger.info(
        "Fitting SARIMAX%s x %s ...", order, seasonal_order
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(
            train_series,
            exog=exog,
            order=order,
            seasonal_order=seasonal_order,
            trend="c",
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        result = model.fit(disp=False, maxiter=200, method="lbfgs")

    # Check for convergence (attribute varies by statsmodels version)
    converged = "N/A"
    if hasattr(result, "mle_retvals") and isinstance(result.mle_retvals, dict):
        converged = result.mle_retvals.get("converged", "N/A")

    logger.info(
        "Model fitted | AIC=%.2f  BIC=%.2f  converged=%s",
        result.aic,
        result.bic,
        converged,
    )
    return result


# ===========================================================================
# 6. Forecast and evaluation
# ===========================================================================
def _safe_mape(actual: np.ndarray, predicted: np.ndarray) -> Tuple[float, int]:
    """
    Mean Absolute Percentage Error that safely handles zeros in ``actual``.

    Zeros are excluded from the MAPE calculation (common pharmaceutical-sales
    practice when zeros represent closures rather than true demand), and the
    count of excluded zeros is reported for transparency.

    Parameters
    ----------
    actual, predicted : np.ndarray

    Returns
    -------
    mape : float
        MAPE in percentage points (0-100 scale).
    n_zeros : int
        Number of zero-actual observations excluded from MAPE.
    """
    nonzero_mask = actual != 0
    n_zeros = int((~nonzero_mask).sum())
    if nonzero_mask.sum() == 0:
        return np.nan, n_zeros
    mape = (
        np.mean(np.abs((actual[nonzero_mask] - predicted[nonzero_mask]) / actual[nonzero_mask]))
        * 100
    )
    return float(mape), n_zeros


def forecast_and_eval(
    model,
    train_index: pd.DatetimeIndex,
    test_series: pd.Series,
    horizon: int,
    exog_test: Optional[np.ndarray] = None,
) -> Tuple[pd.DataFrame, dict]:
    """
    Generate in-sample / out-of-sample forecasts and compute evaluation metrics.

    The function uses ``get_prediction()`` which returns point forecasts **and**
    prediction intervals in a single call, avoiding repeated model re-fits.

    Parameters
    ----------
    model : SARIMAXResultsWrapper
        Fitted SARIMAX model.
    train_index : pd.DatetimeIndex
        Index of the training series (used only for slice reference).
    test_series : pd.Series
        Held-out test series (actuals).
    horizon : int
        Number of steps to forecast (must equal ``len(test_series)``).
    exog_test : np.ndarray, optional
        Exogenous test-period features.

    Returns
    -------
    forecast_df : pd.DataFrame
        Columns: ds, y, yhat, yhat_lower, yhat_upper.
    eval_dict : dict
        Keys: MAE, RMSE, MAPE, n_zero_actuals.
    """
    steps = min(horizon, len(test_series))

    # get_prediction returns an object with summary_frame() for intervals
    pred_obj = model.get_prediction(
        start=test_series.index[0],
        end=test_series.index[steps - 1],
        exog=exog_test[:steps] if exog_test is not None else None,
        dynamic=True,          # true out-of-sample simulation from first test step
    )
    summary = pred_obj.summary_frame(alpha=0.05)   # 95% PI

    actual = test_series.values[:steps]
    yhat   = summary["mean"].values
    lower  = summary["mean_ci_lower"].values
    upper  = summary["mean_ci_upper"].values

    # --- Metrics ---
    mae  = float(mean_absolute_error(actual, yhat))
    rmse = float(np.sqrt(mean_squared_error(actual, yhat)))
    mape, n_zeros = _safe_mape(actual, yhat)

    logger.info(
        "Eval -> MAE=%.3f  RMSE=%.3f  MAPE=%.2f%%  (zeros excluded from MAPE: %d)",
        mae, rmse, mape if not np.isnan(mape) else -1, n_zeros,
    )

    forecast_df = pd.DataFrame({
        "ds":         test_series.index[:steps],
        "y":          actual,
        "yhat":       yhat,
        "yhat_lower": lower,
        "yhat_upper": upper,
    })

    eval_dict = {
        "MAE": mae,
        "RMSE": rmse,
        "MAPE": mape,
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
    Compute residual diagnostics and optionally save ACF/PACF plots.

    Tests performed
    ---------------
    * **Ljung-Box test** (lags=10): tests whether residual autocorrelations are
      collectively zero (i.e., residuals are white noise).  A large p-value
      (> 0.05) indicates a well-specified model.
    * **Shapiro-Wilk normality test** on residuals (informational only).

    Parameters
    ----------
    model : SARIMAXResultsWrapper
        Fitted model.
    category : str
        Used in plot file names.
    verbose : bool
        If ``True``, save ACF/PACF diagnostic PNG files.
    plots_dir : str
        Directory for plot output.

    Returns
    -------
    dict
        ``lb_pvalue``: minimum Ljung-Box p-value across tested lags.
        ``resid_mean``, ``resid_std``: residual statistics.
        ``sw_pvalue``: Shapiro-Wilk p-value (NaN if too many obs).
    """
    residuals = model.resid.dropna()

    # Ljung-Box on lags 1..10
    lb_result = acorr_ljungbox(residuals, lags=[10], return_df=True)
    lb_pvalue = float(lb_result["lb_pvalue"].values[-1])

    # Shapiro-Wilk (only reliable for n < 5000)
    sw_pvalue = np.nan
    if len(residuals) < 5000:
        _, sw_pvalue = stats.shapiro(residuals)

    diag = {
        "lb_pvalue":   lb_pvalue,
        "resid_mean":  float(residuals.mean()),
        "resid_std":   float(residuals.std()),
        "sw_pvalue":   float(sw_pvalue) if not np.isnan(sw_pvalue) else None,
    }
    logger.info(
        "[%s] Diagnostics -> LB p=%.4f | resid mean=%.4f std=%.4f",
        category, lb_pvalue, diag["resid_mean"], diag["resid_std"],
    )

    if verbose:
        os.makedirs(plots_dir, exist_ok=True)

        # ACF / PACF of residuals
        fig, axes = plt.subplots(2, 1, figsize=(10, 6))
        plot_acf(residuals, lags=40, ax=axes[0], title=f"{category} Residual ACF")
        plot_pacf(residuals, lags=40, ax=axes[1], title=f"{category} Residual PACF", method="ywm")
        plt.tight_layout()
        acf_path = os.path.join(plots_dir, f"{category}_residual_acf_pacf.png")
        fig.savefig(acf_path, dpi=120)
        plt.close(fig)
        logger.info("Saved ACF/PACF plot -> %s", acf_path)

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
    Persist the forecast DataFrame, the trained model, and the evaluation row.

    Output files
    ------------
    * ``{forecast_dir}/{category}_sarima_forecast.csv``
      Columns: ``ds, y, yhat, yhat_lower, yhat_upper``

    * ``{models_dir}/{category}_sarima.pkl``
      Pickled ``SARIMAXResultsWrapper`` via joblib.

    * ``{forecast_dir}/sarima_evaluation.csv``
      Appended row with per-category metrics and metadata.

    Parameters
    ----------
    category : str
    forecast_df : pd.DataFrame
    model : SARIMAXResultsWrapper
    eval_row : dict
        Must contain at minimum: category, order, seasonal_order, MAE, RMSE,
        MAPE, train_end, test_start.
    forecast_dir, models_dir : str
        Output directories (created if missing).
    """
    os.makedirs(forecast_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)

    # 1. Forecast CSV
    fc_path = os.path.join(forecast_dir, f"{category}_sarima_forecast.csv")
    forecast_df.to_csv(fc_path, index=False, date_format="%Y-%m-%d")
    logger.info("[%s] Forecast CSV -> %s", category, fc_path)

    # 2. Model pickle
    model_path = os.path.join(models_dir, f"{category}_sarima.pkl")
    joblib.dump(model, model_path)
    logger.info("[%s] Model pickle -> %s", category, model_path)

    # 3. Evaluation CSV (append mode) – retry loop handles Windows file-lock
    #    (e.g. the file is open in Excel). Retries up to 5 times, 2 s apart.
    eval_path = os.path.join(forecast_dir, "sarima_evaluation.csv")
    eval_df   = pd.DataFrame([eval_row])
    write_header = not os.path.exists(eval_path)
    for _attempt in range(5):
        try:
            eval_df.to_csv(eval_path, mode="a", header=write_header, index=False)
            logger.info("[%s] Evaluation appended -> %s", category, eval_path)
            break
        except PermissionError:
            import time
            logger.warning(
                "[%s] sarima_evaluation.csv is locked (attempt %d/5). "
                "Close the file in Excel and retrying in 2 s ...",
                category, _attempt + 1,
            )
            time.sleep(2)
    else:
        logger.error(
            "[%s] Could not write evaluation row after 5 attempts – "
            "sarima_evaluation.csv may still be open. Eval row: %s",
            category, eval_row,
        )


# ===========================================================================
# 9. Rolling-origin cross-validation (optional extra)
# ===========================================================================
def rolling_origin_cv(
    series: pd.Series,
    order: Tuple[int, int, int],
    seasonal_order: Tuple[int, int, int, int],
    horizon: int,
    n_folds: int = 5,
) -> dict:
    """
    Rolling-origin (time-series) cross-validation.

    The series is split into ``n_folds`` folds.  For each fold the model is
    retrained on all data up to the fold boundary and forecasts the next
    ``horizon`` steps.  Average metrics across folds are returned.

    This avoids look-ahead bias: each training window only contains
    data available at that point in time.

    Parameters
    ----------
    series : pd.Series
    order : (p, d, q)
    seasonal_order : (P, D, Q, m)
    horizon : int
        Forecast horizon per fold.
    n_folds : int
        Number of rolling folds.

    Returns
    -------
    dict
        ``cv_mae``, ``cv_rmse``, ``cv_mape``: average metrics across folds.
    """
    n = len(series)
    fold_maes, fold_rmses, fold_mapes = [], [], []

    # Minimum training size: at least 2 seasonal cycles worth of data
    min_train = max(2 * (seasonal_order[3] or 1) * 2, 30)
    step_size = max((n - min_train) // (n_folds + 1), 1)

    logger.info("Rolling-origin CV: %d folds, horizon=%d", n_folds, horizon)

    for fold in range(n_folds):
        cutoff = min_train + fold * step_size
        if cutoff + horizon > n:
            logger.warning("CV fold %d: not enough data - skipping.", fold)
            break

        train_cv = series.iloc[:cutoff]
        test_cv  = series.iloc[cutoff: cutoff + horizon]

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cv_model = SARIMAX(
                    train_cv,
                    order=order,
                    seasonal_order=seasonal_order,
                    trend="c",
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                ).fit(disp=False, maxiter=100)

            _, eval_d = forecast_and_eval(cv_model, train_cv.index, test_cv, horizon)
            fold_maes.append(eval_d["MAE"])
            fold_rmses.append(eval_d["RMSE"])
            if not np.isnan(eval_d["MAPE"]):
                fold_mapes.append(eval_d["MAPE"])
        except Exception as exc:
            logger.warning("CV fold %d failed: %s", fold, exc)

    cv_results = {
        "cv_mae":  float(np.mean(fold_maes))  if fold_maes  else np.nan,
        "cv_rmse": float(np.mean(fold_rmses)) if fold_rmses else np.nan,
        "cv_mape": float(np.mean(fold_mapes)) if fold_mapes else np.nan,
        "n_folds_completed": len(fold_maes),
    }
    logger.info("CV results: %s", cv_results)
    return cv_results


# ===========================================================================
# 10. Per-category pipeline
# ===========================================================================
def run_category(
    df: pd.DataFrame,
    category: str,
    horizon: int,
    seasonal_period: int,
    use_auto: bool,
    fill_method: str,
    verbose: bool,
    run_cv: bool = False,
) -> Optional[dict]:
    """
    End-to-end SARIMA pipeline for a single drug category.

    Steps
    -----
    1.  Prepare daily series.
    2.  Chronological 80/20 train-test split.
    3.  ADF stationarity test on training series.
    4.  Order selection (auto_arima or grid search).
    5.  Fit SARIMAX on train.
    6.  Evaluate on test (MAE, RMSE, MAPE + prediction intervals).
    7.  Residual diagnostics + optional plots.
    8.  Retrain on full history; forecast ``horizon`` future days.
    9.  Save outputs.
    10. (Optional) Rolling-origin CV.

    Parameters
    ----------
    df : pd.DataFrame
        Raw data from :func:`load_data`.
    category : str
    horizon : int
    seasonal_period : int
    use_auto : bool
    fill_method : str
    verbose : bool
    run_cv : bool
        If ``True``, also run rolling-origin CV.

    Returns
    -------
    dict or None
        Evaluation row dict, or ``None`` if the category failed.
    """
    logger.info("=" * 60)
    logger.info("Processing category: %s", category)
    logger.info("=" * 60)

    try:
        # -----------------------------------------------------------------
        # Step 1: Prepare series
        # -----------------------------------------------------------------
        series = prepare_series(df, category, freq="D", fill_method=fill_method)

        # -----------------------------------------------------------------
        # Step 2: Train / test split (80 / 20 chronological)
        # -----------------------------------------------------------------
        split_idx = int(len(series) * 0.80)
        train = series.iloc[:split_idx]
        test  = series.iloc[split_idx:]

        logger.info(
            "Train: %d obs (%s -> %s) | Test: %d obs (%s -> %s)",
            len(train), train.index[0].date(), train.index[-1].date(),
            len(test),  test.index[0].date(),  test.index[-1].date(),
        )

        # -----------------------------------------------------------------
        # Step 3: Stationarity (on training series only - no look-ahead)
        # -----------------------------------------------------------------
        is_stationary, adf_pvalue, _ = check_stationarity(train)

        # -----------------------------------------------------------------
        # Step 4: Order selection
        # -----------------------------------------------------------------
        order, seasonal_order = select_sarima_order(
            train,
            m=seasonal_period,
            use_auto=use_auto,
            is_stationary=is_stationary,
        )

        # -----------------------------------------------------------------
        # Step 5: Fit on training data
        # -----------------------------------------------------------------
        trained_model = fit_sarimax(train, order, seasonal_order)

        # -----------------------------------------------------------------
        # Step 6: Evaluate on test set
        # -----------------------------------------------------------------
        test_horizon = min(horizon, len(test))
        forecast_df, eval_dict = forecast_and_eval(
            trained_model, train.index, test.iloc[:test_horizon], test_horizon
        )

        # -----------------------------------------------------------------
        # Step 7: Residual diagnostics
        # -----------------------------------------------------------------
        diag = residual_diagnostics(
            trained_model, category, verbose=verbose, plots_dir=OUT_PLOTS_DIR
        )

        # -----------------------------------------------------------------
        # Step 7b (verbose): Forecast vs Actuals plot
        # -----------------------------------------------------------------
        if verbose:
            os.makedirs(OUT_PLOTS_DIR, exist_ok=True)
            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(train.index[-90:], train.values[-90:], label="Train (last 90d)", color="#4C72B0")
            ax.plot(forecast_df["ds"], forecast_df["y"],    label="Actual",          color="#55A868")
            ax.plot(forecast_df["ds"], forecast_df["yhat"], label="Forecast",        color="#C44E52", linestyle="--")
            ax.fill_between(
                forecast_df["ds"],
                forecast_df["yhat_lower"],
                forecast_df["yhat_upper"],
                alpha=0.25, color="#C44E52", label="95% PI",
            )
            ax.set_title(f"{category} - SARIMA{order}x{seasonal_order} Test Forecast")
            ax.set_xlabel("Date")
            ax.set_ylabel("Sales (units)")
            ax.legend()
            plt.tight_layout()
            plot_path = os.path.join(OUT_PLOTS_DIR, f"{category}_forecast_vs_actual.png")
            fig.savefig(plot_path, dpi=120)
            plt.close(fig)
            logger.info("Saved forecast plot -> %s", plot_path)

        # -----------------------------------------------------------------
        # Step 8: Retrain on FULL series -> produce future forecast
        # -----------------------------------------------------------------
        logger.info("[%s] Retraining on full history (%d obs) ...", category, len(series))
        final_model = fit_sarimax(series, order, seasonal_order)

        # Build future date index
        last_date    = series.index[-1]
        future_index = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
            freq="D",
        )

        future_pred = final_model.get_forecast(steps=horizon)
        fut_summary = future_pred.summary_frame(alpha=0.05)

        future_df = pd.DataFrame({
            "ds":         future_index,
            "y":          np.nan,           # actuals unknown for future period
            "yhat":       fut_summary["mean"].values,
            "yhat_lower": fut_summary["mean_ci_lower"].values,
            "yhat_upper": fut_summary["mean_ci_upper"].values,
        })

        # Combine test-period evaluation forecast + future forecast
        combined_forecast = pd.concat([forecast_df, future_df], ignore_index=True)

        # -----------------------------------------------------------------
        # Step 9: Optional rolling-origin CV
        # -----------------------------------------------------------------
        cv_results: dict = {}
        if run_cv:
            cv_results = rolling_origin_cv(train, order, seasonal_order, horizon)

        # -----------------------------------------------------------------
        # Step 10: Build evaluation row and save
        # -----------------------------------------------------------------
        eval_row = {
            "category":        category,
            "order":           str(order),
            "seasonal_order":  str(seasonal_order),
            "MAE":             round(eval_dict["MAE"], 4),
            "RMSE":            round(eval_dict["RMSE"], 4),
            "MAPE":            round(eval_dict["MAPE"], 4) if not np.isnan(eval_dict["MAPE"]) else None,
            "n_zero_actuals":  eval_dict["n_zero_actuals"],
            "train_end":       str(train.index[-1].date()),
            "test_start":      str(test.index[0].date()),
            "lb_pvalue":       round(diag["lb_pvalue"], 4),
            "adf_pvalue":      round(adf_pvalue, 4),
            **({f"cv_{k}": round(v, 4) if not np.isnan(v) else None for k, v in cv_results.items()}
               if cv_results else {}),
        }

        save_forecast_and_model(category, combined_forecast, final_model, eval_row)

        logger.info("[%s] Complete.", category)
        return eval_row

    except Exception:
        logger.error("[%s] Failed:\n%s", category, traceback.format_exc())
        return None


# ===========================================================================
# 11. CLI argument parsing
# ===========================================================================
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Example invocations
    -------------------
    # Auto-ARIMA, 30-day horizon, verbose
    python sarima_train_eval.py --use-auto --horizon 30 --verbose

    # Grid search, specific categories, 14-day horizon, zero-fill
    python sarima_train_eval.py --horizon 14 --categories M01AB,N02BE --fill-method zero

    # Run rolling-origin CV as well
    python sarima_train_eval.py --use-auto --cv --verbose
    """
    parser = argparse.ArgumentParser(
        description="Train and evaluate SARIMA models for pharmaceutical daily sales.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_PATH,
        metavar="PATH",
        help=f"Path to salesdaily.csv (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=DEFAULT_HORIZON,
        help=f"Days to forecast (default: {DEFAULT_HORIZON})",
    )
    parser.add_argument(
        "--categories",
        default=",".join(DEFAULT_CATEGORIES),
        help="Comma-separated list of drug categories (default: all 8)",
    )
    parser.add_argument(
        "--seasonal-period",
        type=int,
        default=DEFAULT_SEASONAL_PERIOD,
        dest="seasonal_period",
        help=f"Seasonal period m (default: {DEFAULT_SEASONAL_PERIOD} -> weekly)",
    )
    parser.add_argument(
        "--use-auto",
        action="store_true",
        default=False,
        dest="use_auto",
        help="Use pmdarima.auto_arima for order selection (requires pmdarima)",
    )
    parser.add_argument(
        "--fill-method",
        choices=["ffill", "zero"],
        default=DEFAULT_FILL_METHOD,
        dest="fill_method",
        help=f"Gap-filling method (default: {DEFAULT_FILL_METHOD})",
    )
    parser.add_argument(
        "--cv",
        action="store_true",
        default=False,
        help="Also run rolling-origin cross-validation",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Save diagnostic plots (ACF/PACF, forecast vs actual)",
    )
    return parser.parse_args(argv)


# ===========================================================================
# 12. Main entry point
# ===========================================================================
def main(argv: Optional[List[str]] = None) -> None:
    """
    Main driver: load data, run per-category SARIMA pipeline, print summary.

    Each category is processed sequentially; exceptions in one category do
    **not** abort the others (robust per-category exception handling).
    """
    args = parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    categories: List[str] = [c.strip() for c in args.categories.split(",") if c.strip()]

    logger.info("=" * 50)
    logger.info("  SARIMA Pharmaceutical Sales Forecaster")
    logger.info("=" * 50)
    logger.info("Categories    : %s", categories)
    logger.info("Horizon       : %d days", args.horizon)
    logger.info("Seasonal m    : %d",       args.seasonal_period)
    logger.info("Order selector: %s",        "auto_arima" if args.use_auto else "grid-search")
    logger.info("Fill method   : %s",        args.fill_method)
    logger.info("Verbose plots : %s",        args.verbose)
    logger.info("Rolling CV    : %s",        args.cv)

    # Load once - share across categories
    df = load_data(args.input)

    results = []
    for cat in categories:
        row = run_category(
            df=df,
            category=cat,
            horizon=args.horizon,
            seasonal_period=args.seasonal_period,
            use_auto=args.use_auto,
            fill_method=args.fill_method,
            verbose=args.verbose,
            run_cv=args.cv,
        )
        if row:
            results.append(row)

    # ---- Summary table ----
    if results:
        summary_df = pd.DataFrame(results)[
            ["category", "order", "seasonal_order", "MAE", "RMSE", "MAPE", "lb_pvalue"]
        ]
        logger.info("\n\n%s\n\n%s\n", "-" * 80, summary_df.to_string(index=False))
    else:
        logger.warning("No categories processed successfully.")

    logger.info("Done. Outputs in: %s", os.path.abspath(OUT_FORECAST_DIR))


# ===========================================================================
# Entry point guard
# ===========================================================================
if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # Example CLI demonstrations (edit sys.argv list to test programmatically)
    # -----------------------------------------------------------------------
    #
    # Example 1 - full auto run with verbose plots:
    #   python sarima_train_eval.py --use-auto --horizon 30 --verbose
    #
    # Example 2 - grid search, two categories, 14-day horizon:
    #   python sarima_train_eval.py --horizon 14 --categories M01AB,N02BE --seasonal-period 7
    #
    # Example 3 - zero-fill, rolling CV, all categories:
    #   python sarima_train_eval.py --fill-method zero --cv --verbose
    #
    # Example 4 - minimal run (grid search defaults):
    #   python sarima_train_eval.py
    # -----------------------------------------------------------------------
    main()
