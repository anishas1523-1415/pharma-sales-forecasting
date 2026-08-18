import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

_PATH = Path(__file__).resolve().parents[2] / "data" / "outputs" / "forecasts" / "lightgbm_feature_importance.json"
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_PATH.read_text()) if _PATH.exists() else {}
    return _cache


@router.get("/feature-importance/{category}")
def get_feature_importance(category: str):
    """
    Top LightGBM feature importances for a category — which lag/rolling/
    calendar features actually drive its forecast. Extracted offline from
    the trained model (src/models/export_feature_importance.py), same
    precomputed-artifact pattern as /forecast and /metrics: no live model
    loaded at request time.
    """
    data = _load()
    if category not in data:
        raise HTTPException(status_code=404, detail=f"No feature importance data for '{category}'")
    return {"category": category, "features": data[category]}
