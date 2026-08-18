"""
train_lstm.py — LSTM forecasting pipeline for pharmaceutical sales.

Trains one LSTM model per drug category using the daily sales CSV.
Produces forecasts, evaluation metrics, training-history plots, and
serialised model / scaler artefacts.

Required packages (pip install line):
    pip install pandas numpy scikit-learn tensorflow joblib matplotlib

Usage examples
--------------
    # All categories, default settings
    python src/models/train_lstm.py

    # Custom horizon, lookback, and categories
    python src/models/train_lstm.py --horizon 60 --lookback 90 --categories M01AB,N05B

    # More epochs, larger network, retrain on full data
    python src/models/train_lstm.py --epochs 100 --units 128 --retrain-final

    # Verbose mode (saves test-set prediction plots)
    python src/models/train_lstm.py --verbose --seed 42
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for server / CI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler

# ---------------------------------------------------------------------------
# TensorFlow — import and silence noisy logs
# ---------------------------------------------------------------------------
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf  # noqa: E402
from tensorflow import keras  # noqa: E402
from tensorflow.keras import layers, callbacks as kcb  # noqa: E402

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_CSV = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle" / "salesdaily.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"
FORECAST_DIR = OUTPUT_DIR / "forecasts"
PLOT_DIR = FORECAST_DIR / "plots"
MODEL_DIR = OUTPUT_DIR / "trained_models"

ALL_CATEGORIES: List[str] = [
    "M01AB", "M01AE", "N02BA", "N02BE",
    "N05B", "N05C", "R03", "R06",
]

logger = logging.getLogger(__name__)


# ===================================================================
# 0. REPRODUCIBILITY HELPERS
# ===================================================================

def set_seeds(seed: int = 42) -> None:
    """Pin random seeds for NumPy and TensorFlow for reproducibility."""
    np.random.seed(seed)
    tf.random.set_seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    logger.info("Random seed set to %d", seed)


def log_device_info() -> None:
    """Log whether TensorFlow sees a GPU."""
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        logger.info("TF detected %d GPU(s): %s", len(gpus), gpus)
    else:
        logger.info("No GPU detected — training will use CPU.")


# ===================================================================
# 1. DATA LOADING
# ===================================================================

def load_data(path: Path = DATA_CSV) -> pd.DataFrame:
    """Load the raw daily-sales CSV and parse the date column.

    Parameters
    ----------
    path : Path
        Location of ``salesdaily.csv``.

    Returns
    -------
    pd.DataFrame
        Sorted chronologically with ``datum`` as datetime.
    """
    logger.info("Loading data from %s", path)
    df = pd.read_csv(path)
    df["datum"] = pd.to_datetime(df["datum"])
    df.sort_values("datum", inplace=True)
    df.reset_index(drop=True, inplace=True)
    logger.info(
        "Loaded %d rows  |  date range: %s -> %s",
        len(df), df["datum"].min().date(), df["datum"].max().date(),
    )
    return df


# ===================================================================
# 2. SERIES PREPARATION
# ===================================================================

def prepare_series(
    df: pd.DataFrame,
    category: str,
    fill_method: str = "ffill",
) -> pd.Series:
    """Extract a single category as a daily-frequency Series.

    Parameters
    ----------
    df : pd.DataFrame
        Full daily-sales DataFrame (output of :func:`load_data`).
    category : str
        ATC drug-category code (e.g. ``"M01AB"``).
    fill_method : str
        How to fill missing dates after resampling:
        * ``'ffill'`` — forward-fill (carry last known value).
          Good default for LSTM because it avoids artificial zero spikes
          that can confuse gradient-based learning.
        * ``'zero'`` — fill with 0 (pharmacy closed / no sale).

    Returns
    -------
    pd.Series
        Named ``category``, daily DatetimeIndex, no NaNs.
    """
    ts = df.set_index("datum")[category].copy()
    ts = ts.resample("D").sum()

    if fill_method == "ffill":
        # Forward-fill then back-fill the very first NaN(s)
        ts = ts.ffill().bfill()
    else:
        ts = ts.fillna(0.0)

    ts.name = category
    return ts


# ===================================================================
# 3. SEQUENCE CREATION (sliding windows)
# ===================================================================

def create_sequences(
    data: np.ndarray,
    lookback: int,
    horizon: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build supervised-learning samples from a 1-D array.

    For each valid position *i* the function produces:
    * **X** — the preceding ``lookback`` values  (shape per sample: ``(lookback, 1)``)
    * **y** — the next ``horizon`` values         (shape per sample: ``(horizon,)``)

    This implements *direct multi-step forecasting*: the model outputs
    all ``horizon`` future steps in one forward pass.

    Parameters
    ----------
    data : np.ndarray
        1-D scaled time-series values.
    lookback : int
        Number of past time-steps fed to the LSTM.
    horizon : int
        Number of future time-steps to predict.

    Returns
    -------
    X : np.ndarray, shape ``(n_samples, lookback, 1)``
    y : np.ndarray, shape ``(n_samples, horizon)``
    """
    X, y = [], []
    for i in range(len(data) - lookback - horizon + 1):
        X.append(data[i : i + lookback])
        y.append(data[i + lookback : i + lookback + horizon])
    X = np.array(X).reshape(-1, lookback, 1)
    y = np.array(y).reshape(-1, horizon)
    return X, y


# ===================================================================
# 4. MODEL ARCHITECTURE
# ===================================================================

def build_lstm(
    input_shape: Tuple[int, int],
    horizon: int,
    units: int = 64,
    dropout: float = 0.2,
    lr: float = 1e-3,
) -> keras.Model:
    """Construct and compile a Keras Sequential LSTM model.

    Architecture
    ------------
    LSTM(units, return_sequences=True)  →  Dropout
    LSTM(units // 2)                    →  Dropout
    Dense(horizon)

    The two stacked LSTM layers let the network learn both short- and
    medium-range temporal dependencies.  The final Dense layer outputs
    ``horizon`` values (direct multi-step forecast).

    Parameters
    ----------
    input_shape : tuple (lookback, n_features)
        Shape of a single input sample.
    horizon : int
        Number of future steps to predict.
    units : int
        Hidden units in the first LSTM layer.
    dropout : float
        Dropout rate applied after each LSTM layer.
    lr : float
        Learning rate for the Adam optimiser.

    Returns
    -------
    keras.Model
        Compiled Keras model.

    .. note::
       **Multivariate extension** — to add extra regressors (e.g.
       holiday flags, promotions) increase ``n_features`` in
       ``input_shape`` and adjust the ``create_sequences`` function
       to stack additional columns alongside the target series.
    """
    model = keras.Sequential([
        layers.Input(shape=input_shape),
        layers.LSTM(
            units,
            return_sequences=True,
            name="lstm_1",
        ),
        layers.Dropout(dropout, name="dropout_1"),
        layers.LSTM(
            units // 2,
            return_sequences=False,
            name="lstm_2",
        ),
        layers.Dropout(dropout, name="dropout_2"),
        layers.Dense(horizon, name="forecast_output"),
    ])

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=lr),
        loss="mse",
        metrics=["mae"],
    )
    return model


# ===================================================================
# 5. TRAINING
# ===================================================================

def train_and_evaluate(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    model: keras.Model,
    cb_list: list,
    epochs: int = 50,
    batch_size: int = 32,
) -> Tuple[keras.callbacks.History, keras.Model]:
    """Fit the LSTM model and return the training history.

    Parameters
    ----------
    X_train, y_train : np.ndarray
        Training sequences.
    X_val, y_val : np.ndarray
        Validation sequences (chronological holdout).
    model : keras.Model
        Compiled Keras model.
    cb_list : list
        List of Keras callbacks (EarlyStopping, ModelCheckpoint …).
    epochs : int
        Maximum training epochs.
    batch_size : int
        Mini-batch size.

    Returns
    -------
    history : keras.callbacks.History
    model : keras.Model
        The model with the best weights restored (via ModelCheckpoint).
    """
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=cb_list,
        verbose=0,  # we log progress ourselves
    )
    return history, model


# ===================================================================
# 6. EVALUATION METRICS
# ===================================================================

def evaluate_forecast(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Compute MAE, RMSE, and MAPE (zero-safe) on original-scale values.

    Rows where ``y_true == 0`` are excluded from MAPE to avoid
    division-by-zero.  Returns ``NaN`` if *all* actuals are zero.

    Parameters
    ----------
    y_true, y_pred : np.ndarray
        Flattened arrays of actual and predicted values.

    Returns
    -------
    dict
        ``{'MAE': …, 'RMSE': …, 'MAPE': …}``
    """
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))

    mask = y_true != 0
    if mask.sum() == 0:
        mape = float("nan")
    else:
        mape = float(
            np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
        )

    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


# ===================================================================
# 7. PLOTTING HELPERS
# ===================================================================

def plot_training_history(
    history: keras.callbacks.History,
    category: str,
    save_path: Path,
) -> None:
    """Save a loss / val_loss training curve to disk."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(history.history["loss"], label="Train Loss")
    ax.plot(history.history["val_loss"], label="Val Loss")
    ax.set_title(f"{category} — LSTM Training History")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MSE Loss")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    logger.info("[%s] Training plot saved -> %s", category, save_path)


def plot_test_predictions(
    dates: pd.DatetimeIndex,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    category: str,
    save_path: Path,
) -> None:
    """Save an actual-vs-predicted overlay for the test set."""
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(dates, y_true, label="Actual", alpha=0.8)
    ax.plot(dates, y_pred, label="Predicted", alpha=0.8)
    ax.set_title(f"{category} — Test-Set Predictions vs Actuals")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sales")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    logger.info("[%s] Test prediction plot saved -> %s", category, save_path)


# ===================================================================
# 8. SAVE ARTIFACTS
# ===================================================================

def save_artifacts(
    category: str,
    model: keras.Model,
    scaler: MinMaxScaler,
    forecast_df: pd.DataFrame,
    model_dir: Path = MODEL_DIR,
    forecast_dir: Path = FORECAST_DIR,
) -> None:
    """Persist Keras model, scaler, and forecast CSV.

    Parameters
    ----------
    category : str
        Drug-category label.
    model : keras.Model
        Trained Keras LSTM model.
    scaler : MinMaxScaler
        Fitted scaler (to inverse-transform future predictions).
    forecast_df : pd.DataFrame
        Forecast DataFrame to write as CSV.
    model_dir, forecast_dir : Path
        Output directories (created if missing).
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    forecast_dir.mkdir(parents=True, exist_ok=True)

    # Keras model (HDF5)
    model_path = model_dir / f"{category}_lstm.keras"
    model.save(model_path)
    logger.info("[%s] Model saved  -> %s", category, model_path)

    # Scaler
    scaler_path = model_dir / f"{category}_scaler.pkl"
    joblib.dump(scaler, scaler_path)
    logger.info("[%s] Scaler saved -> %s", category, scaler_path)

    # Forecast CSV
    fc_path = forecast_dir / f"{category}_lstm_forecast.csv"
    forecast_df.to_csv(fc_path, index=False)
    logger.info("[%s] Forecast CSV  -> %s", category, fc_path)


# ===================================================================
# 9. PER-CATEGORY PIPELINE
# ===================================================================

def run_category(
    df: pd.DataFrame,
    category: str,
    lookback: int = 60,
    horizon: int = 30,
    epochs: int = 50,
    batch_size: int = 32,
    units: int = 64,
    dropout: float = 0.2,
    lr: float = 1e-3,
    patience: int = 5,
    fill_method: str = "ffill",
    retrain_final: bool = False,
    verbose: bool = False,
) -> Optional[Dict]:
    """Full LSTM pipeline for a single drug category.

    Returns
    -------
    dict or None
        Result dict with metrics, or None if the category was skipped.
    """
    # ---- 1. Prepare series ----
    series = prepare_series(df, category, fill_method=fill_method)
    n_days = len(series)
    min_required = lookback + horizon + 10
    if n_days < min_required:
        logger.warning(
            "[%s] Only %d days available (need >= %d). Skipping.",
            category, n_days, min_required,
        )
        return None

    values = series.values.astype(np.float32)

    # ---- 2. Scale ----
    # DESIGN: MinMaxScaler fit ONLY on training portion to avoid data leakage.
    split_idx = int(len(values) * 0.8)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaler.fit(values[:split_idx].reshape(-1, 1))
    scaled = scaler.transform(values.reshape(-1, 1)).flatten()

    # ---- 3. Create sequences ----
    X, y = create_sequences(scaled, lookback, horizon)
    n_samples = len(X)
    train_size = int(n_samples * 0.8)

    X_train, y_train = X[:train_size], y[:train_size]
    X_val, y_val = X[train_size:], y[train_size:]

    logger.info(
        "[%s] Sequences: total=%d  train=%d  val=%d  |  lookback=%d  horizon=%d",
        category, n_samples, len(X_train), len(X_val), lookback, horizon,
    )

    # ---- 4. Build model ----
    model = build_lstm(
        input_shape=(lookback, 1),
        horizon=horizon,
        units=units,
        dropout=dropout,
        lr=lr,
    )

    # ---- 5. Callbacks ----
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    best_ckpt = MODEL_DIR / f"{category}_lstm_best.keras"
    cb_list = [
        kcb.EarlyStopping(
            monitor="val_loss",
            patience=patience,
            restore_best_weights=True,
            verbose=0,
        ),
        kcb.ModelCheckpoint(
            str(best_ckpt),
            monitor="val_loss",
            save_best_only=True,
            verbose=0,
        ),
    ]

    # ---- 6. Train ----
    logger.info("[%s] Training LSTM (%d epochs max, patience=%d) ...",
                category, epochs, patience)
    history, model = train_and_evaluate(
        X_train, y_train, X_val, y_val,
        model, cb_list, epochs, batch_size,
    )
    stopped_epoch = len(history.history["loss"])
    best_val = min(history.history["val_loss"])
    logger.info("[%s] Stopped at epoch %d  |  best val_loss=%.6f",
                category, stopped_epoch, best_val)

    # ---- 7. Evaluate on validation set ----
    y_pred_scaled = model.predict(X_val, verbose=0)

    # Inverse-transform: scaler expects shape (-1, 1)
    y_val_orig = scaler.inverse_transform(y_val.reshape(-1, 1)).flatten()
    y_pred_orig = scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()

    metrics = evaluate_forecast(y_val_orig, y_pred_orig)
    logger.info(
        "[%s] MAE=%.4f  |  RMSE=%.4f  |  MAPE=%.2f%%",
        category, metrics["MAE"], metrics["RMSE"], metrics["MAPE"],
    )

    # ---- 8. Plots ----
    plot_training_history(
        history, category,
        PLOT_DIR / f"{category}_lstm_training.png",
    )

    if verbose:
        # For the test-prediction plot, use the first predicted step
        # from each validation window to form a continuous series.
        first_step_preds_scaled = y_pred_scaled[:, 0]
        first_step_actuals_scaled = y_val[:, 0]
        first_step_preds = scaler.inverse_transform(
            first_step_preds_scaled.reshape(-1, 1)
        ).flatten()
        first_step_actuals = scaler.inverse_transform(
            first_step_actuals_scaled.reshape(-1, 1)
        ).flatten()
        # Date indices for validation windows (each starts at lookback + train_size + i)
        val_dates = series.index[lookback + train_size : lookback + train_size + len(first_step_preds)]
        if len(val_dates) == len(first_step_preds):
            plot_test_predictions(
                val_dates, first_step_actuals, first_step_preds,
                category,
                PLOT_DIR / f"{category}_lstm_test_predictions.png",
            )

    # ---- 9. Retrain on full data & produce future forecast ----
    if retrain_final:
        logger.info("[%s] Retraining on full data ...", category)
        X_full, y_full = create_sequences(scaled, lookback, horizon)
        final_model = build_lstm(
            input_shape=(lookback, 1),
            horizon=horizon,
            units=units,
            dropout=dropout,
            lr=lr,
        )
        final_model.fit(
            X_full, y_full,
            epochs=stopped_epoch,  # use same number of epochs as best run
            batch_size=batch_size,
            verbose=0,
        )
    else:
        final_model = model

    # Use last lookback window to forecast the future
    last_window = scaled[-lookback:].reshape(1, lookback, 1)
    future_scaled = final_model.predict(last_window, verbose=0).flatten()
    future_values = scaler.inverse_transform(
        future_scaled.reshape(-1, 1)
    ).flatten()

    # Build forecast DataFrame
    last_date = series.index[-1]
    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=horizon,
        freq="D",
    )
    forecast_df = pd.DataFrame({
        "ds": future_dates,
        "yhat": future_values,
        "horizon_index": list(range(horizon)),
    })

    # ---- 10. Save artifacts ----
    save_artifacts(category, final_model, scaler, forecast_df)

    # Clean up checkpoint file
    if best_ckpt.exists():
        best_ckpt.unlink()

    return {
        "category": category,
        **metrics,
        "train_samples": len(X_train),
        "test_samples": len(X_val),
        "lookback": lookback,
        "horizon": horizon,
        "units": units,
        "epochs_run": stopped_epoch,
        "best_val_loss": best_val,
        "forecast_df": forecast_df,
    }


# ===================================================================
# 10. FULL PIPELINE
# ===================================================================

def run_pipeline(
    categories: Optional[List[str]] = None,
    csv_path: Path = DATA_CSV,
    **kwargs,
) -> List[Dict]:
    """Run the LSTM pipeline for all requested categories.

    This is the main programmatic entry point — callable from a
    Streamlit dashboard or an external pipeline.

    Parameters
    ----------
    categories : list[str] | None
        ATC codes to model.  ``None`` -> all 8 default categories.
    csv_path : Path
        Path to the input CSV.
    **kwargs
        Forwarded to :func:`run_category`.

    Returns
    -------
    list[dict]
        One result dict per successfully processed category.
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
            result = run_category(df, cat, **kwargs)
            if result is not None:
                all_results.append(result)
        except Exception:
            logger.exception("Failed to process category '%s'", cat)

    # ---- Evaluation summary CSV ----
    if all_results:
        FORECAST_DIR.mkdir(parents=True, exist_ok=True)
        rows = []
        for r in all_results:
            rows.append({
                "category": r["category"],
                "MAE": round(r["MAE"], 4),
                "RMSE": round(r["RMSE"], 4),
                "MAPE": round(r["MAPE"], 2) if not np.isnan(r["MAPE"]) else "N/A",
                "train_samples": r["train_samples"],
                "test_samples": r["test_samples"],
                "lookback": r["lookback"],
                "horizon": r["horizon"],
                "units": r["units"],
                "epochs_run": r["epochs_run"],
            })
        eval_df = pd.DataFrame(rows)
        eval_path = FORECAST_DIR / "lstm_evaluation.csv"
        eval_df.to_csv(eval_path, index=False)
        logger.info("Evaluation summary saved -> %s", eval_path)

        print("\n" + "=" * 70)
        print("  LSTM EVALUATION SUMMARY")
        print("=" * 70)
        print(eval_df.to_string(index=False))
        print("=" * 70 + "\n")
    else:
        logger.warning("No categories were successfully processed.")

    return all_results


# ===================================================================
# 11. CLI
# ===================================================================

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Train LSTM models for pharma sales forecasting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/models/train_lstm.py
  python src/models/train_lstm.py --horizon 60 --lookback 90 --categories M01AB,N05B
  python src/models/train_lstm.py --epochs 100 --units 128 --retrain-final --verbose
        """,
    )
    parser.add_argument("--horizon", type=int, default=30,
                        help="Future days to predict (default: 30).")
    parser.add_argument("--lookback", type=int, default=60,
                        help="LSTM input window in days (default: 60).")
    parser.add_argument("--epochs", type=int, default=50,
                        help="Max training epochs (default: 50).")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Mini-batch size (default: 32).")
    parser.add_argument("--units", type=int, default=64,
                        help="LSTM hidden units (default: 64).")
    parser.add_argument("--dropout", type=float, default=0.2,
                        help="Dropout rate (default: 0.2).")
    parser.add_argument("--lr", type=float, default=1e-3,
                        help="Learning rate (default: 1e-3).")
    parser.add_argument("--patience", type=int, default=5,
                        help="Early stopping patience (default: 5).")
    parser.add_argument("--categories", type=str, default=None,
                        help="Comma-separated ATC codes (default: all 8).")
    parser.add_argument("--fill-method", type=str, default="ffill",
                        choices=["ffill", "zero"],
                        help="How to fill missing dates (default: ffill).")
    parser.add_argument("--retrain-final", action="store_true", default=False,
                        help="Retrain on full data before final forecast.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42).")
    parser.add_argument("--csv", type=str, default=None,
                        help="Override path to input CSV.")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Enable DEBUG logging and save test-prediction plots.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    set_seeds(args.seed)
    log_device_info()

    categories = (
        [c.strip() for c in args.categories.split(",")]
        if args.categories else None
    )
    csv_path = Path(args.csv) if args.csv else DATA_CSV

    run_pipeline(
        categories=categories,
        csv_path=csv_path,
        lookback=args.lookback,
        horizon=args.horizon,
        epochs=args.epochs,
        batch_size=args.batch_size,
        units=args.units,
        dropout=args.dropout,
        lr=args.lr,
        patience=args.patience,
        fill_method=args.fill_method,
        retrain_final=args.retrain_final,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
