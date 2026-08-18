"""
export_feature_importance.py
=============================
Extracts LightGBM feature importances from the trained model pickles and
writes them as a single git-tracked JSON — the same "precomputed artifact,
not live model" pattern the rest of the backend already follows (forecast
CSVs, metrics.json).

Why this needs to exist: the .pkl files under data/outputs/trained_models/
are gitignored (correctly — they're large binaries) and only exist on
whichever machine trained them. Feature-importance PNGs get generated too,
but as images, not queryable data — nothing the API can serve. This
extracts the actual importance *values* into a small JSON the backend can
read at request time, same as it already does for metrics.json.

Run after any LightGBM retrain:
    python src/models/export_feature_importance.py
"""
import json
from pathlib import Path

import joblib

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "data" / "outputs" / "trained_models"
OUT_FILE = PROJECT_ROOT / "data" / "outputs" / "forecasts" / "lightgbm_feature_importance.json"

CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
TOP_N = 10


def main():
    result = {}
    for cat in CATEGORIES:
        path = MODEL_DIR / f"{cat}_lightgbm.pkl"
        if not path.exists():
            print(f"  {cat}: no trained model file, skipping")
            continue
        model = joblib.load(path)
        pairs = sorted(zip(model.feature_name_, model.feature_importances_.tolist()), key=lambda p: -p[1])
        top = [{"feature": name, "importance": int(imp)} for name, imp in pairs[:TOP_N] if imp > 0]
        total = sum(imp for _, imp in pairs) or 1
        for row in top:
            row["importance_pct"] = round(row["importance"] / total * 100, 2)
        result[cat] = top
        print(f"  {cat}: top feature = {top[0]['feature'] if top else 'n/a'}")

    OUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {OUT_FILE}")


if __name__ == "__main__":
    main()
