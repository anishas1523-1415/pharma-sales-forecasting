"""
what_if.py
==========
What-If scenario analysis for pharmaceutical sales forecasts.

Loads a saved Prophet or LightGBM forecast and re-simulates it under
user-defined scenarios:
  - demand_shock_pct   : % change in overall demand (e.g. +20 or -15)
  - supply_disruption  : list of date ranges where supply drops to zero
  - trend_multiplier   : scale the forecast trend (e.g. 1.1 = 10% growth)

Outputs a side-by-side comparison: baseline vs scenario forecast.

Usage
-----
    python src/features/what_if.py --category M01AB --demand-shock 20
    python src/features/what_if.py --category N02BE --demand-shock -30 --trend-multiplier 0.9
    python src/features/what_if.py --category R03 --disruption-start 2020-01-01 --disruption-end 2020-01-15
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORECAST_DIR = PROJECT_ROOT / "data" / "outputs" / "forecasts"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs" / "what_if"

ALL_CATEGORIES: List[str] = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
SUPPORTED_MODELS = ["prophet", "arima", "sarima", "lightgbm", "lstm"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load baseline forecast
# ---------------------------------------------------------------------------
def load_baseline_forecast(category: str, model: str = "prophet") -> pd.DataFrame:
    """
    Load a previously saved forecast CSV for a given category and model.

    Returns DataFrame with columns: ds, yhat, yhat_lower, yhat_upper
    Falls back to next available model if the requested one is missing.
    """
    for m in [model] + [x for x in SUPPORTED_MODELS if x != model]:
        path = FORECAST_DIR / f"{category}_{m}_forecast.csv"
        if path.exists():
            df = pd.read_csv(path, parse_dates=["ds"])
            # Keep only future rows (where y is NaN = true forecast)
            future = df[df["y"].isna()].copy() if "y" in df.columns else df.copy()
            if len(future) == 0:
                future = df.copy()  # fallback: use all rows
            logger.info("Loaded %s forecast for %s (%d rows)", m, category, len(future))
            return future[["ds", "yhat", "yhat_lower", "yhat_upper"]].reset_index(drop=True)

    raise FileNotFoundError(
        f"No forecast file found for category '{category}'. "
        f"Run a forecasting model first."
    )


# ---------------------------------------------------------------------------
# Scenario application
# ---------------------------------------------------------------------------
def apply_scenario(
    baseline: pd.DataFrame,
    demand_shock_pct: float = 0.0,
    trend_multiplier: float = 1.0,
    disruption_periods: Optional[List[Tuple[str, str]]] = None,
    floor: float = 0.0,
) -> pd.DataFrame:
    """
    Apply what-if scenario adjustments to a baseline forecast.

    Parameters
    ----------
    baseline : pd.DataFrame
        Columns: ds, yhat, yhat_lower, yhat_upper
    demand_shock_pct : float
        Percentage change applied uniformly to all forecast values.
        e.g. 20 → +20%, -15 → -15%
    trend_multiplier : float
        Linearly scales the forecast over time.
        1.0 = no change, 1.1 = 10% growth by end of horizon.
    disruption_periods : list of (start_date, end_date) tuples
        Date ranges where supply is forced to zero (e.g. stockout).
    floor : float
        Minimum value for yhat (sales can't go below this).

    Returns
    -------
    pd.DataFrame with same columns as baseline, values adjusted.
    """
    scenario = baseline.copy()
    n = len(scenario)

    # 1. Demand shock: uniform % shift
    shock_factor = 1.0 + demand_shock_pct / 100.0
    for col in ["yhat", "yhat_lower", "yhat_upper"]:
        scenario[col] = scenario[col] * shock_factor

    # 2. Trend multiplier: linearly ramp from 1.0 to trend_multiplier
    if trend_multiplier != 1.0:
        ramp = np.linspace(1.0, trend_multiplier, n)
        for col in ["yhat", "yhat_lower", "yhat_upper"]:
            scenario[col] = scenario[col] * ramp

    # 3. Supply disruption: zero out specified date ranges
    if disruption_periods:
        for start, end in disruption_periods:
            mask = (scenario["ds"] >= pd.Timestamp(start)) & (scenario["ds"] <= pd.Timestamp(end))
            scenario.loc[mask, ["yhat", "yhat_lower", "yhat_upper"]] = 0.0
            logger.info("Disruption applied: %s → %s (%d days zeroed)", start, end, mask.sum())

    # 4. Floor
    for col in ["yhat", "yhat_lower", "yhat_upper"]:
        scenario[col] = scenario[col].clip(lower=floor)

    return scenario


# ---------------------------------------------------------------------------
# Comparison & metrics
# ---------------------------------------------------------------------------
def compare_scenarios(baseline: pd.DataFrame, scenario: pd.DataFrame) -> pd.DataFrame:
    """Build a side-by-side comparison DataFrame."""
    comp = pd.DataFrame({
        "ds": baseline["ds"],
        "baseline_yhat": baseline["yhat"].round(4),
        "scenario_yhat": scenario["yhat"].round(4),
        "delta": (scenario["yhat"] - baseline["yhat"]).round(4),
        "delta_pct": (
            ((scenario["yhat"] - baseline["yhat"]) / baseline["yhat"].replace(0, np.nan)) * 100
        ).round(2),
    })
    return comp


def scenario_summary(baseline: pd.DataFrame, scenario: pd.DataFrame, category: str) -> dict:
    """Compute aggregate impact metrics."""
    total_baseline = baseline["yhat"].sum()
    total_scenario = scenario["yhat"].sum()
    delta = total_scenario - total_baseline
    return {
        "category": category,
        "horizon_days": len(baseline),
        "total_baseline_sales": round(total_baseline, 2),
        "total_scenario_sales": round(total_scenario, 2),
        "total_delta": round(delta, 2),
        "total_delta_pct": round(100 * delta / total_baseline if total_baseline != 0 else 0, 2),
        "peak_baseline": round(baseline["yhat"].max(), 2),
        "peak_scenario": round(scenario["yhat"].max(), 2),
        "zero_days_scenario": int((scenario["yhat"] == 0).sum()),
    }


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_comparison(
    baseline: pd.DataFrame,
    scenario: pd.DataFrame,
    category: str,
    scenario_label: str,
    out_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 4))

    ax.plot(baseline["ds"], baseline["yhat"], label="Baseline", color="#4C72B0", linewidth=1.5)
    ax.fill_between(
        baseline["ds"], baseline["yhat_lower"], baseline["yhat_upper"],
        alpha=0.15, color="#4C72B0",
    )
    ax.plot(scenario["ds"], scenario["yhat"], label=f"Scenario: {scenario_label}",
            color="#C44E52", linewidth=1.5, linestyle="--")
    ax.fill_between(
        scenario["ds"], scenario["yhat_lower"], scenario["yhat_upper"],
        alpha=0.15, color="#C44E52",
    )

    ax.set_title(f"{category} — What-If Scenario Analysis")
    ax.set_xlabel("Date")
    ax.set_ylabel("Forecasted Sales")
    ax.legend()
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{category}_what_if.png", dpi=120)
    plt.close(fig)
    logger.info("[%s] What-if plot saved.", category)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_what_if(
    category: str,
    model: str = "prophet",
    demand_shock_pct: float = 0.0,
    trend_multiplier: float = 1.0,
    disruption_periods: Optional[List[Tuple[str, str]]] = None,
    plot: bool = False,
) -> dict:
    """
    Full what-if pipeline for one category.

    Returns a dict with keys: summary, comparison_df, baseline_df, scenario_df
    """
    baseline = load_baseline_forecast(category, model)
    scenario = apply_scenario(
        baseline,
        demand_shock_pct=demand_shock_pct,
        trend_multiplier=trend_multiplier,
        disruption_periods=disruption_periods,
    )
    comparison = compare_scenarios(baseline, scenario)
    summary = scenario_summary(baseline, scenario, category)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(OUTPUT_DIR / f"{category}_what_if_comparison.csv", index=False)

    scenario_label = f"shock={demand_shock_pct:+.0f}%, trend={trend_multiplier:.2f}x"
    if disruption_periods:
        scenario_label += f", disruptions={len(disruption_periods)}"

    if plot:
        plot_comparison(baseline, scenario, category, scenario_label, OUTPUT_DIR / "plots")

    print(f"\n{'='*60}")
    print(f"  WHAT-IF SUMMARY: {category}")
    print(f"{'='*60}")
    for k, v in summary.items():
        print(f"  {k:<30} {v}")
    print(f"{'='*60}\n")

    return {"summary": summary, "comparison_df": comparison, "baseline_df": baseline, "scenario_df": scenario}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="What-If scenario analysis for pharma forecasts.")
    p.add_argument("--category", type=str, required=True, help="ATC category code (e.g. M01AB)")
    p.add_argument("--model", type=str, default="prophet", choices=SUPPORTED_MODELS)
    p.add_argument("--demand-shock", type=float, default=0.0, dest="demand_shock",
                   help="Demand change in %% (e.g. 20 for +20%%, -15 for -15%%)")
    p.add_argument("--trend-multiplier", type=float, default=1.0, dest="trend_multiplier",
                   help="End-of-horizon trend scale factor (default: 1.0 = flat)")
    p.add_argument("--disruption-start", type=str, default=None, dest="disruption_start",
                   help="Start date of supply disruption (YYYY-MM-DD)")
    p.add_argument("--disruption-end", type=str, default=None, dest="disruption_end",
                   help="End date of supply disruption (YYYY-MM-DD)")
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
    disruptions = None
    if args.disruption_start and args.disruption_end:
        disruptions = [(args.disruption_start, args.disruption_end)]

    run_what_if(
        category=args.category,
        model=args.model,
        demand_shock_pct=args.demand_shock,
        trend_multiplier=args.trend_multiplier,
        disruption_periods=disruptions,
        plot=args.plot,
    )


if __name__ == "__main__":
    main()
