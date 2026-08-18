"""
anomaly_detection.py
====================
Detects anomalies in daily pharmaceutical sales using three methods:
  1. Z-Score  — flags values > threshold standard deviations from the mean
  2. IQR      — flags values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
  3. Isolation Forest — unsupervised ML-based anomaly detection

Usage
-----
    python src/features/anomaly_detection.py
    python src/features/anomaly_detection.py --categories M01AB,N02BE --zscore-threshold 2.5
    python src/features/anomaly_detection.py --method all --plot
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_CSV = PROJECT_ROOT / "data" / "raw" / "pharma_sales_kaggle" / "salesdaily.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs" / "anomalies"

ALL_CATEGORIES: List[str] = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_series(csv_path: Path = DATA_CSV) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["datum"])
    df.sort_values("datum", inplace=True)
    df.set_index("datum", inplace=True)
    df = df[ALL_CATEGORIES].resample("D").sum().ffill()
    return df


# ---------------------------------------------------------------------------
# Detection methods
# ---------------------------------------------------------------------------
def detect_zscore(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    """Return boolean mask: True where |z-score| > threshold."""
    z = (series - series.mean()) / series.std()
    return z.abs() > threshold


def detect_iqr(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    """Return boolean mask: True where value is outside IQR fence."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    return (series < q1 - multiplier * iqr) | (series > q3 + multiplier * iqr)


def detect_isolation_forest(series: pd.Series, contamination: float = 0.05, seed: int = 42) -> pd.Series:
    """Return boolean mask using Isolation Forest (-1 → anomaly)."""
    X = series.values.reshape(-1, 1)
    clf = IsolationForest(contamination=contamination, random_state=seed, n_jobs=-1)
    preds = clf.fit_predict(X)
    return pd.Series(preds == -1, index=series.index)


# ---------------------------------------------------------------------------
# Per-category pipeline
# ---------------------------------------------------------------------------
def detect_anomalies(
    series: pd.Series,
    category: str,
    method: str = "all",
    zscore_threshold: float = 3.0,
    iqr_multiplier: float = 1.5,
    if_contamination: float = 0.05,
) -> pd.DataFrame:
    """
    Run anomaly detection on one category series.

    Returns a DataFrame with columns:
        date, value, zscore_flag, iqr_flag, iforest_flag, anomaly, severity
    """
    result = pd.DataFrame({"date": series.index, "value": series.values})
    result.set_index("date", inplace=True)

    result["zscore_flag"] = False
    result["iqr_flag"] = False
    result["iforest_flag"] = False

    if method in ("zscore", "all"):
        result["zscore_flag"] = detect_zscore(series, zscore_threshold).values

    if method in ("iqr", "all"):
        result["iqr_flag"] = detect_iqr(series, iqr_multiplier).values

    if method in ("iforest", "all"):
        result["iforest_flag"] = detect_isolation_forest(series, if_contamination).values

    # Consensus: anomaly if flagged by ≥2 methods (or any single method if not "all")
    if method == "all":
        flag_sum = result[["zscore_flag", "iqr_flag", "iforest_flag"]].sum(axis=1)
        result["anomaly"] = flag_sum >= 2
        result["severity"] = flag_sum.map({0: "normal", 1: "low", 2: "medium", 3: "high"})
    else:
        col = f"{method}_flag" if method != "iforest" else "iforest_flag"
        result["anomaly"] = result[col]
        result["severity"] = result["anomaly"].map({True: "high", False: "normal"})

    result["category"] = category
    logger.info(
        "[%s] Anomalies detected: %d / %d (%.1f%%)",
        category,
        result["anomaly"].sum(),
        len(result),
        100 * result["anomaly"].mean(),
    )
    return result.reset_index()


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------
def build_summary(all_results: List[pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for df in all_results:
        cat = df["category"].iloc[0]
        anomalies = df[df["anomaly"]]
        rows.append({
            "category": cat,
            "total_days": len(df),
            "anomaly_count": len(anomalies),
            "anomaly_pct": round(100 * len(anomalies) / len(df), 2),
            "high_severity": int((anomalies["severity"] == "high").sum()),
            "medium_severity": int((anomalies["severity"] == "medium").sum()),
            "low_severity": int((anomalies["severity"] == "low").sum()),
            "max_anomaly_value": round(anomalies["value"].max(), 2) if len(anomalies) else None,
            "mean_normal_value": round(df[~df["anomaly"]]["value"].mean(), 2),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_anomalies(result_df: pd.DataFrame, out_dir: Path) -> None:
    cat = result_df["category"].iloc[0]
    fig, ax = plt.subplots(figsize=(14, 4))

    normal = result_df[~result_df["anomaly"]]
    anomalies = result_df[result_df["anomaly"]]

    ax.plot(result_df["date"], result_df["value"], color="#4C72B0", linewidth=0.7, label="Sales")
    ax.scatter(anomalies["date"], anomalies["value"], color="red", s=20, zorder=5, label="Anomaly")

    ax.set_title(f"{cat} — Anomaly Detection")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sales (units)")
    ax.legend()
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{cat}_anomalies.png", dpi=120)
    plt.close(fig)
    logger.info("[%s] Anomaly plot saved.", cat)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline(
    categories: Optional[List[str]] = None,
    method: str = "all",
    zscore_threshold: float = 3.0,
    iqr_multiplier: float = 1.5,
    if_contamination: float = 0.05,
    plot: bool = False,
    csv_path: Path = DATA_CSV,
) -> pd.DataFrame:
    if categories is None:
        categories = ALL_CATEGORIES

    df = load_series(csv_path)
    all_results = []

    for cat in categories:
        if cat not in df.columns:
            logger.warning("Category '%s' not found, skipping.", cat)
            continue
        result = detect_anomalies(
            df[cat], cat, method, zscore_threshold, iqr_multiplier, if_contamination
        )
        all_results.append(result)

        if plot:
            plot_anomalies(result, OUTPUT_DIR / "plots")

    if not all_results:
        logger.warning("No categories processed.")
        return pd.DataFrame()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save detailed anomaly records
    combined = pd.concat(all_results, ignore_index=True)
    anomaly_records = combined[combined["anomaly"]].copy()
    anomaly_records.to_csv(OUTPUT_DIR / "anomaly_records.csv", index=False)
    logger.info("Anomaly records saved -> %s", OUTPUT_DIR / "anomaly_records.csv")

    # Save summary
    summary = build_summary(all_results)
    summary.to_csv(OUTPUT_DIR / "anomaly_summary.csv", index=False)

    print("\n" + "=" * 65)
    print("  ANOMALY DETECTION SUMMARY")
    print("=" * 65)
    print(summary.to_string(index=False))
    print("=" * 65 + "\n")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Anomaly detection for pharma sales.")
    p.add_argument("--categories", type=str, default=None, help="Comma-separated ATC codes")
    p.add_argument("--method", choices=["zscore", "iqr", "iforest", "all"], default="all")
    p.add_argument("--zscore-threshold", type=float, default=3.0, dest="zscore_threshold")
    p.add_argument("--iqr-multiplier", type=float, default=1.5, dest="iqr_multiplier")
    p.add_argument("--contamination", type=float, default=0.05)
    p.add_argument("--plot", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    cats = [c.strip() for c in args.categories.split(",")] if args.categories else None
    run_pipeline(
        categories=cats,
        method=args.method,
        zscore_threshold=args.zscore_threshold,
        iqr_multiplier=args.iqr_multiplier,
        if_contamination=args.contamination,
        plot=args.plot,
    )


if __name__ == "__main__":
    main()
