"""
test_all.py
===========
Tests all 3 backend services using REAL data from disk:
  - Teammate's forecast CSVs  (data/outputs/forecasts/)
  - Actual sales CSV          (data/processed/sales_daily_processed.csv)
  - Evaluation CSVs           (data/outputs/forecasts/*_evaluation.csv)

Usage:
    python test_all.py
"""

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from backend.schemas.anomaly import AnomalyRequest
from backend.schemas.whatif import WhatIfRequest
from backend.schemas.recommendation import RecommendationRequest

from backend.services.anomaly_service import detect_anomalies
from backend.services.whatif_service import run_what_if
from backend.services.recommendation_service import generate_recommendations


PASS = "✅ PASS"
FAIL = "❌ FAIL"

all_checks = []


def check(label, condition):
    status = PASS if condition else FAIL
    print(f"  [Check] {label:<55} {status}")
    all_checks.append(condition)


def section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


# ─────────────────────────────────────────────────────────────
# TEST 1 — ANOMALY DETECTION
# Uses real M01AB prophet forecast vs real actual sales
# ─────────────────────────────────────────────────────────────

section("TEST 1: ANOMALY DETECTION  (M01AB · prophet)")


resp = detect_anomalies(
    AnomalyRequest(
        category="M01AB",
        model="prophet",
    )
)


print(f"\n  Category     : {resp.category}")
print(f"  Model        : {resp.model}")
print(f"  Matched days : {resp.total_days}")
print(f"  Anomaly days : {resp.anomaly_count}")


if resp.results:
    print(
        f"\n  {'Date':<13} "
        f"{'Actual':>8} "
        f"{'Forecast':>10} "
        f"{'Dev%':>9} "
        f"{'Status':<12} "
        f"Severity"
    )

    print("  " + "-" * 62)

    for r in resp.results[:10]:
        print(
            f"  {r.date:<13} "
            f"{r.actual_sales:>8.2f} "
            f"{r.forecast_sales:>10.4f} "
            f"{r.deviation_percent:>8.2f}% "
            f"{r.status:<12} "
            f"{r.severity}"
        )

    if resp.total_days > 10:
        print(f"  ... ({resp.total_days - 10} more rows)")


check(
    "Response structure is valid",
    isinstance(resp.total_days, int)
    and resp.total_days >= 0,
)

check(
    "Anomaly count is non-negative",
    resp.anomaly_count >= 0,
)

check(
    "All statuses are valid values",
    all(
        r.status in ("normal", "moderate", "anomaly")
        for r in resp.results
    ),
)

check(
    "All severities are valid values",
    all(
        r.severity in ("low", "medium", "high")
        for r in resp.results
    ),
)

check(
    "High deviation → anomaly/high severity",
    all(
        r.severity == "high"
        for r in resp.results
        if r.deviation_percent > 50
    ),
)


# ─────────────────────────────────────────────────────────────
# TEST 2 — WHAT-IF ANALYSIS
# Uses real M01AB prophet forecast, applies +20% demand shock
# ─────────────────────────────────────────────────────────────

section("TEST 2: WHAT-IF ANALYSIS  (M01AB · prophet · +20%)")


resp2 = run_what_if(
    WhatIfRequest(
        category="M01AB",
        model="prophet",
        change_percent=20.0,
    )
)


print(f"\n  Category         : {resp2.category}")
print(f"  Model            : {resp2.model}")
print(f"  Scenario         : +{resp2.change_percent}% demand")
print(f"  Total baseline   : {resp2.total_baseline:.4f}")
print(f"  Total adjusted   : {resp2.total_adjusted:.4f}")
print(f"  Total difference : +{resp2.total_difference:.4f}")


if resp2.results:
    print(
        f"\n  {'Date':<13} "
        f"{'Baseline':>10} "
        f"{'Adjusted':>10} "
        f"{'Diff':>8} "
        f"{'Chg%':>7}"
    )

    print("  " + "-" * 52)

    for r in resp2.results[:5]:
        print(
            f"  {r.date:<13} "
            f"{r.baseline_sales:>10.4f} "
            f"{r.adjusted_sales:>10.4f} "
            f"{r.difference:>8.4f} "
            f"{r.change_percent:>6.1f}%"
        )

    if len(resp2.results) > 5:
        print(f"  ... ({len(resp2.results) - 5} more rows)")


expected_adjusted = round(
    resp2.total_baseline * 1.20,
    2,
)

actual_adjusted = round(
    resp2.total_adjusted,
    2,
)


check(
    "Forecast rows loaded from disk",
    len(resp2.results) > 0,
)

check(
    "Adjusted total ≈ baseline × 1.20",
    abs(actual_adjusted - expected_adjusted) < 0.1,
)

check(
    "Every adjusted = baseline × 1.20",
    all(
        abs(
            r.adjusted_sales
            - round(r.baseline_sales * 1.20, 4)
        ) < 0.01
        for r in resp2.results
    ),
)

check(
    "No disruption days (none requested)",
    resp2.disruption_days == 0,
)


# ─────────────────────────────────────────────────────────────
# TEST 2b — WHAT-IF WITH SUPPLY DISRUPTION
# First 3 forecast days zeroed out
# ─────────────────────────────────────────────────────────────

section(
    "TEST 2b: WHAT-IF + SUPPLY DISRUPTION  (M01AB · prophet)"
)


first_date = resp2.results[0].date
third_date = resp2.results[2].date


resp2b = run_what_if(
    WhatIfRequest(
        category="M01AB",
        model="prophet",
        change_percent=0.0,
        disruption_start=first_date,
        disruption_end=third_date,
    )
)


print(f"\n  Disruption window : {first_date} → {third_date}")
print(f"  Disruption days   : {resp2b.disruption_days}")

print(
    f"\n  {'Date':<13} "
    f"{'Baseline':>10} "
    f"{'Adjusted':>10}  "
    f"Note"
)

print("  " + "-" * 55)


for r in resp2b.results[:6]:

    note = (
        "← ZEROED"
        if r.adjusted_sales == 0.0
        else ""
    )

    print(
        f"  {r.date:<13} "
        f"{r.baseline_sales:>10.4f} "
        f"{r.adjusted_sales:>10.4f}  "
        f"{note}"
    )


check(
    "Disruption days = 3",
    resp2b.disruption_days == 3,
)

check(
    "Disrupted rows have adjusted_sales = 0",
    all(
        r.adjusted_sales == 0.0
        for r in resp2b.results[:3]
    ),
)

check(
    "Non-disrupted rows unchanged",
    all(
        r.adjusted_sales == r.baseline_sales
        for r in resp2b.results[3:]
    ),
)


# ─────────────────────────────────────────────────────────────
# TEST 3 — RECOMMENDATION ENGINE
# Uses real M01AB prophet data
# ─────────────────────────────────────────────────────────────

section("TEST 3: RECOMMENDATIONS  (M01AB · prophet)")


resp3 = generate_recommendations(
    RecommendationRequest(
        category="M01AB",
        model="prophet",
    )
)


print(f"\n  Category         : {resp3.category}")
print(f"  Model            : {resp3.model}")
print(f"  Forecast trend   : {resp3.forecast_trend_pct:+.2f}%")
print(f"  Model MAPE       : {resp3.model_mape}%")
print(f"  Model MAE        : {resp3.model_mae}")
print(f"  Anomaly days     : {resp3.anomaly_count}")


print(
    f"\n  Recommendations "
    f"({len(resp3.recommendations)} total):"
)


for rec in resp3.recommendations:

    print(f"\n    [{rec.priority}] {rec.signal}")
    print(f"    → {rec.recommendation}")
    print(f"    Rationale: {rec.rationale}")


signals = [
    r.signal
    for r in resp3.recommendations
]

priorities = [
    r.priority
    for r in resp3.recommendations
]


check(
    "At least 1 recommendation returned",
    len(resp3.recommendations) >= 1,
)

check(
    "Recommendations sorted HIGH→MED→LOW",
    priorities
    == sorted(
        priorities,
        key=lambda p: {
            "HIGH": 0,
            "MEDIUM": 1,
            "LOW": 2,
        }.get(p, 3),
    ),
)

check(
    "MAPE loaded from evaluation CSV",
    resp3.model_mape is not None,
)

check(
    "MAE loaded from evaluation CSV",
    resp3.model_mae is not None,
)

check(
    "HIGH_UNCERTAINTY triggered (MAPE>30%)",
    (
        "HIGH_UNCERTAINTY" in signals
        if (resp3.model_mape or 0) > 30
        else True
    ),
)

check(
    "Trend signal present",
    any(
        s in signals
        for s in (
            "RESTOCK_ALERT",
            "OVERSTOCK_RISK",
            "STABLE_SUPPLY",
        )
    ),
)


# ─────────────────────────────────────────────────────────────
# TEST 4 — ALL 8 CATEGORIES, PROPHET MODEL
# Smoke test: every category should return a valid response
# ─────────────────────────────────────────────────────────────

section(
    "TEST 4: SMOKE TEST — ALL 8 CATEGORIES (prophet)"
)


categories = [
    "M01AB",
    "M01AE",
    "N02BA",
    "N02BE",
    "N05B",
    "N05C",
    "R03",
    "R06",
]


print(
    f"\n  {'Category':<8} "
    f"{'Days':>6} "
    f"{'Anomalies':>10} "
    f"{'Trend%':>8} "
    f"{'MAPE%':>8}  "
    f"Top Signal"
)

print("  " + "-" * 65)


all_ok = True


for cat in categories:

    try:

        r = generate_recommendations(
            RecommendationRequest(
                category=cat,
                model="prophet",
            )
        )

        top = (
            r.recommendations[0].signal
            if r.recommendations
            else "—"
        )

        mape_str = (
            f"{r.model_mape:.1f}"
            if r.model_mape
            else "N/A"
        )

        print(
            f"  {cat:<8} "
            f"{r.anomaly_count + 0:>6}* "
            f"{r.anomaly_count:>10} "
            f"{r.forecast_trend_pct:>+8.2f} "
            f"{mape_str:>8}  "
            f"{top}"
        )

    except Exception as e:

        print(
            f"  {cat:<8} ERROR: {e}"
        )

        all_ok = False


print(
    "  * anomaly_count from overlapping "
    "forecast+actual dates"
)


check(
    "All 8 categories processed without error",
    all_ok,
)


# ─────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────

section("TEST SUMMARY")


passed = sum(all_checks)
total = len(all_checks)


print(f"\n  Passed : {passed} / {total}")

print(
    f"  Status : "
    f"{'ALL TESTS PASSED ✅' if passed == total else f'{total - passed} FAILED ❌'}\n"
)