"""
rebuild_metrics_json.py
========================
Rebuilds models/metrics.json from scratch, reading directly from the
per-model evaluation CSVs in data/outputs/forecasts/.

Why this exists: metrics.json was found truncated — it only contained data
for the first category (M01AB), cut off mid-object. This broke /metrics
and /compare-models for every other category (they'd 404). test_all.py
never caught it because that suite validates the anomaly/whatif/
recommendation services, which read per-model evaluation CSVs directly
(via backend/data_loader.py's load_mae/load_mape), not metrics.json.

This script is the source of truth going forward: metrics.json is fully
regenerated from the evaluation CSVs (never hand-edited), matching the
nested schema the surviving M01AB entry demonstrated:
    {category: {model: {MAE, RMSE, MAPE, ...model-specific fields},
                 ...,
                 "best_model": <lowest-MAE model>}}

Run:
    python src/models/rebuild_metrics_json.py
"""
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = PROJECT_ROOT / "data" / "outputs" / "forecasts"
METRICS_FILE = PROJECT_ROOT / "models" / "metrics.json"

CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]


def _row(df: pd.DataFrame, cat: str) -> dict:
    match = df[df["category"] == cat]
    if match.empty:
        raise ValueError(f"No row for category {cat!r}")
    return match.iloc[0].to_dict()


def main():
    prophet_df = pd.read_csv(FORECAST_DIR / "prophet_evaluation.csv")
    arima_df = pd.read_csv(FORECAST_DIR / "arima_evaluation.csv")
    sarima_df = pd.read_csv(FORECAST_DIR / "sarima_evaluation.csv")
    lightgbm_df = pd.read_csv(FORECAST_DIR / "lightgbm_evaluation.csv")
    lstm_df = pd.read_csv(FORECAST_DIR / "lstm_evaluation.csv")

    metrics = {}

    for cat in CATEGORIES:
        p = _row(prophet_df, cat)
        a = _row(arima_df, cat)
        s = _row(sarima_df, cat)
        l = _row(lightgbm_df, cat)
        t = _row(lstm_df, cat)

        entry = {
            "prophet": {
                "MAE": p["MAE"],
                "RMSE": p["RMSE"],
                "MAPE_%": p["MAPE_%"],
                "MAPE": p["MAPE_%"],
            },
            "arima": {
                "p": a["p"], "d": a["d"], "q": a["q"],
                "MAE": a["MAE"], "RMSE": a["RMSE"], "MAPE": a["MAPE"],
                "n_zero_actuals": a["n_zero_actuals"],
                "train_end": a["train_end"], "test_start": a["test_start"],
                "lb_pvalue": a["lb_pvalue"], "adf_pvalue": a["adf_pvalue"],
            },
            "sarima": {
                "order": s["order"], "seasonal_order": s["seasonal_order"],
                "MAE": s["MAE"], "RMSE": s["RMSE"], "MAPE": s["MAPE"],
                "n_zero_actuals": s["n_zero_actuals"],
                "train_end": s["train_end"], "test_start": s["test_start"],
                "lb_pvalue": s["lb_pvalue"], "adf_pvalue": s["adf_pvalue"],
            },
            "lightgbm": {
                "MAE": l["MAE"], "RMSE": l["RMSE"], "MAPE": l["MAPE"],
                "train_end": l["train_end"], "test_start": l["test_start"],
                "model_params": l["model_params"],
            },
            "lstm": {
                "MAE": t["MAE"], "RMSE": t["RMSE"], "MAPE": t["MAPE"],
                "train_samples": t["train_samples"], "test_samples": t["test_samples"],
                "lookback": t["lookback"], "horizon": t["horizon"],
                "units": t["units"], "epochs_run": t["epochs_run"],
            },
        }

        best = min(entry, key=lambda m: entry[m]["MAE"])
        entry["best_model"] = best
        metrics[cat] = entry

        print(f"{cat:<8} best={best:<10} "
              f"prophet={entry['prophet']['MAE']:.3f} arima={entry['arima']['MAE']:.3f} "
              f"sarima={entry['sarima']['MAE']:.3f} lightgbm={entry['lightgbm']['MAE']:.3f} "
              f"lstm={entry['lstm']['MAE']:.3f}")

    METRICS_FILE.write_text(json.dumps(metrics, indent=2, default=str))
    print(f"\nWrote {METRICS_FILE} with {len(metrics)} categories.")


if __name__ == "__main__":
    main()
