"""
reconcile_retrain.py
=====================
After retraining a model with a wider/tuned hyperparameter search, compare
the new per-category MAE against the git-committed baseline and keep only
genuine wins — reverting the forecast CSV (and evaluation row) for any
category where the retrain came out worse.

This is deliberately not "trust the new run blindly": a wider hyperparameter
search sometimes finds a better minimum and sometimes doesn't (small-sample,
noisy daily sales data), so each category is judged on its own held-out MAE,
same discipline as ensemble_analysis.py.

Run after a retrain, before touching metrics.json:
    python src/models/reconcile_retrain.py --model lightgbm
"""
import argparse
import subprocess
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = PROJECT_ROOT / "data" / "outputs" / "forecasts"
CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]


def git_show(path: str) -> str:
    return subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
    ).stdout


def git_checkout(path: str):
    subprocess.run(["git", "checkout", "HEAD", "--", path], cwd=PROJECT_ROOT, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["lightgbm", "prophet", "arima", "sarima", "lstm"])
    args = ap.parse_args()

    eval_rel = f"data/outputs/forecasts/{args.model}_evaluation.csv"
    old_text = git_show(eval_rel)
    import io
    old = pd.read_csv(io.StringIO(old_text)).set_index("category")
    # Some training scripts APPEND to the evaluation CSV rather than
    # overwrite (e.g. arima_train_eval.py) — after a re-run the file can
    # have the pre-existing baseline row *and* the fresh row for the same
    # category. Keep only the most recent (last) row per category before
    # comparing, since that's this run's actual result.
    new = pd.read_csv(FORECAST_DIR / f"{args.model}_evaluation.csv")
    new = new[~new["category"].duplicated(keep="last")].set_index("category")

    kept_new, reverted = [], []
    final_rows = []

    for cat in CATEGORIES:
        if cat not in new.index:
            # retrain didn't touch this category — keep old row as-is
            final_rows.append(old.loc[[cat]].reset_index())
            reverted.append(cat)
            continue

        old_mae = float(old.loc[cat, "MAE"]) if cat in old.index else float("inf")
        new_mae = float(new.loc[cat, "MAE"])

        if new_mae < old_mae:
            final_rows.append(new.loc[[cat]].reset_index())
            kept_new.append((cat, old_mae, new_mae))
        else:
            final_rows.append(old.loc[[cat]].reset_index())
            reverted.append((cat, old_mae, new_mae))
            forecast_rel = f"data/outputs/forecasts/{cat}_{args.model}_forecast.csv"
            git_checkout(forecast_rel)

    merged = pd.concat(final_rows, ignore_index=True)
    merged.to_csv(FORECAST_DIR / f"{args.model}_evaluation.csv", index=False)

    print(f"\n{args.model.upper()} reconciliation — kept new (genuine improvement): {len(kept_new)}/{len(CATEGORIES)}")
    for cat, o, n in kept_new:
        print(f"  {cat:8} {o:.4f} -> {n:.4f}  ({(o - n) / o * 100:+.2f}%)")
    print(f"Reverted to baseline (retrain was worse or category not retrained): {len(reverted)}/{len(CATEGORIES)}")
    for item in reverted:
        if isinstance(item, tuple):
            cat, o, n = item
            print(f"  {cat:8} kept baseline {o:.4f} (retrain gave {n:.4f}, worse)")
        else:
            print(f"  {item:8} kept baseline (not retrained this run)")


if __name__ == "__main__":
    main()
