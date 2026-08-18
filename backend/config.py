from pathlib import Path

BASE_DIR      = Path(__file__).resolve().parents[1]
MODELS_DIR    = BASE_DIR / "data" / "outputs" / "trained_models"
FORECASTS_DIR = BASE_DIR / "data" / "outputs" / "forecasts"
METRICS_FILE  = BASE_DIR / "models" / "metrics.json"

MODEL_TYPES = ["prophet", "arima", "sarima", "lightgbm", "lstm"]
