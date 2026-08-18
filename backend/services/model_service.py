import joblib
import json
import logging
from pathlib import Path
from typing import Any, Dict

from backend.config import MODELS_DIR, METRICS_FILE, MODEL_TYPES

logger = logging.getLogger(__name__)


class ModelService:
    def __init__(self):
        # { model_type: { category: model } }
        self.models: Dict[str, Dict[str, Any]] = {m: {} for m in MODEL_TYPES}
        # LSTM needs its scaler to inverse-transform predictions
        self.scalers: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = {}

    def load_all(self):
        if MODELS_DIR.exists():
            for pkl_file in MODELS_DIR.glob("*.pkl"):
                self._load_pkl(pkl_file)
            for keras_file in MODELS_DIR.glob("*.keras"):
                self._load_keras(keras_file)
            logger.info("Loaded models: %s", {k: list(v) for k, v in self.models.items() if v})
        else:
            logger.warning("Models directory not found: %s — skipping model loading", MODELS_DIR)

        self._load_metrics()

    def _load_pkl(self, path: Path):
        # filename pattern: {category}_{model_type}.pkl or {category}_scaler.pkl
        stem = path.stem  # e.g. "M01AB_prophet" or "M01AB_scaler"
        parts = stem.rsplit("_", 1)
        if len(parts) != 2:
            return
        category, model_type = parts[0], parts[1]

        if model_type == "scaler":
            try:
                self.scalers[category] = joblib.load(path)
                logger.info("Loaded scaler for '%s'", category)
            except Exception as e:
                logger.error("Failed to load scaler %s: %s", path.name, e)
            return

        if model_type not in self.models:
            return
        try:
            self.models[model_type][category] = joblib.load(path)
            logger.info("Loaded %s model for '%s'", model_type, category)
        except Exception as e:
            logger.error("Failed to load %s: %s", path.name, e)

    def _load_keras(self, path: Path):
        # filename pattern: {category}_lstm.keras
        stem = path.stem
        parts = stem.rsplit("_", 1)
        if len(parts) != 2 or parts[1] != "lstm":
            return
        category = parts[0]
        try:
            import tensorflow as tf
            self.models["lstm"][category] = tf.keras.models.load_model(path)
            logger.info("Loaded lstm model for '%s'", category)
        except Exception as e:
            logger.error("Failed to load lstm model %s: %s", path.name, e)

    def _load_metrics(self):
        if not METRICS_FILE.exists():
            logger.warning("metrics.json not found at %s", METRICS_FILE)
            return
        try:
            with open(METRICS_FILE) as f:
                self.metrics = json.load(f)
        except Exception as e:
            logger.error("Failed to load metrics.json: %s", e)

    def get_model(self, model_type: str, category: str):
        return self.models.get(model_type, {}).get(category)

    def get_scaler(self, category: str):
        return self.scalers.get(category)

    @property
    def available_categories(self):
        cats = set()
        for store in self.models.values():
            cats.update(store.keys())
        return sorted(cats)

    @property
    def available_models(self):
        return [m for m, store in self.models.items() if store]


model_service = ModelService()
