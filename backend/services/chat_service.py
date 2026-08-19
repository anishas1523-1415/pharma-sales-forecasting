"""
chat_service.py
================
Conversational assistant embedded in the dashboard. Handles two kinds of
turns:
    1. Normal conversation — greetings, small talk, general knowledge.
       Answered like any ordinary assistant.
    2. Questions about the portfolio — sales totals, peak days, trends,
       model accuracy, recommendations. These are answered ONLY from the
       DATA SNAPSHOT built below, which is computed from the same data
       and service functions the rest of the dashboard uses (real
       historical actuals, real anomaly detection, real metrics.json —
       not the LLM inventing plausible-sounding numbers).

Two providers, tried in order:
    1. Gemini (GEMINI_API_KEY)  — primary
    2. Groq   (GROQ_API_KEY)    — fallback if Gemini errors or isn't
                                   configured (rate limit, outage, etc.)
Both are free-tier LLM APIs; keeping both wired up means a single
provider's quota or downtime doesn't take the assistant offline.
"""
import logging
import os

import httpx

from backend.data_loader import VALID_CATEGORIES, load_actuals
from backend.schemas.anomaly import AnomalyRequest
from backend.schemas.recommendation import RecommendationRequest
from backend.services.anomaly_service import detect_anomalies
from backend.services.model_service import model_service
from backend.services.recommendation_service import generate_recommendations

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    # flash-lite, not the default flash — the latter runs extended "thinking"
    # on this API that blows well past a chat-appropriate response time
    # (30-40s+) for no quality benefit on grounded, snapshot-only Q&A.
    "gemini-3.5-flash-lite:generateContent"
)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"

SYSTEM_INSTRUCTION = (
    "You are the domain expert embedded in PharmaForecast, a "
    "pharmaceutical sales forecasting & business-intelligence platform. "
    "You are knowledgeable and genuinely useful across everything this "
    "product and its domain touch — don't narrow yourself to reciting "
    "numbers. That includes, without limit to:\n"
    "  - the real data: sales volumes, forecasts, trends, anomalies, "
    "model accuracy, recommendations for all 8 categories (M01AB, M01AE, "
    "N02BA, N02BE, N05B, N05C, R03, R06)\n"
    "  - how the app itself works: the 5 models (Prophet, ARIMA, SARIMA, "
    "LightGBM, LSTM), what MAE/RMSE/MAPE mean, why a category's best "
    "model was chosen, what the anomaly severity levels mean, what ATC "
    "drug-category codes are\n"
    "  - business strategy grounded in the data: inventory/restocking "
    "decisions, supply-chain risk, promotional or marketing timing, "
    "pricing or procurement implications — reason qualitatively from the "
    "real trend direction and anomaly severity in the snapshot (e.g. a "
    "category trending down is a candidate for reduced procurement or a "
    "promotional push; a category with a demand spike is a restocking "
    "priority). This is a natural extension of what the Recommendations "
    "page already does — don't refuse it.\n"
    "  - general pharma/forecasting knowledge and ordinary conversation "
    "— greetings, small talk, or questions unrelated to this product. "
    "Reply naturally, like any helpful assistant.\n\n"
    "The one hard rule: never invent a specific NUMBER that isn't in the "
    "DATA SNAPSHOT below. Qualitative reasoning and strategic advice "
    "built on top of the real numbers is encouraged; a fabricated MAE, "
    "sales total, or date is not. If a data question falls outside the "
    "snapshot, say so plainly instead of guessing — but that's about "
    "missing numbers, not a reason to decline strategy or how-it-works "
    "questions, which you should always engage with.\n\n"
    "Plain, concise, business-friendly language — a couple of sentences "
    "unless the question genuinely needs more — leading with the direct "
    "answer before supporting detail."
)


def _category_sales_summary(category: str) -> dict:
    df = load_actuals(category)
    total = float(df["actual_sales"].sum())
    avg = float(df["actual_sales"].mean())
    peak_idx = df["actual_sales"].idxmax()
    return {
        "total": total,
        "avg": avg,
        "peak_value": float(df.loc[peak_idx, "actual_sales"]),
        "peak_date": df.loc[peak_idx, "date"],
        "date_range": f"{df['date'].iloc[0]} to {df['date'].iloc[-1]}",
    }


def _biggest_anomaly(category: str) -> dict | None:
    try:
        resp = detect_anomalies(AnomalyRequest(category=category, model="arima"))
    except Exception:
        return None
    if not resp.results:
        return None
    worst = max(resp.results, key=lambda r: r.deviation_percent)
    return {
        "date": worst.date,
        "deviation_percent": worst.deviation_percent,
        "severity": worst.severity,
        "actual_sales": worst.actual_sales,
        "forecast_sales": worst.forecast_sales,
    }


def _build_context_summary() -> str:
    metrics = model_service.metrics or {}
    per_category: list[tuple[str, dict]] = []

    for category in VALID_CATEGORIES:
        try:
            sales = _category_sales_summary(category)
        except Exception as e:
            logger.warning("Chat context: sales summary failed for %s (%s)", category, e)
            sales = None
        per_category.append((category, sales))

    lines: list[str] = []

    # Ranked by total historical sales volume — answers "which sold most/least".
    ranked = sorted(
        (c for c in per_category if c[1] is not None),
        key=lambda c: c[1]["total"],
        reverse=True,
    )
    if ranked:
        lines.append("SALES VOLUME RANKING (highest to lowest total units sold, full history):")
        for rank, (category, sales) in enumerate(ranked, start=1):
            lines.append(
                f"  {rank}. {category}: total={sales['total']:,.0f} units, "
                f"avg/day={sales['avg']:.2f}, peak single-day={sales['peak_value']:,.0f} "
                f"units on {sales['peak_date']}, data covers {sales['date_range']}"
            )

    lines.append("\nPER-CATEGORY DETAIL (model accuracy, forecast trend, anomalies, recommendations):")
    for category, sales in per_category:
        cat_metrics = metrics.get(category, {})
        best_model = cat_metrics.get("best_model", "unknown")
        best_mae = cat_metrics.get(best_model, {}).get("MAE") if best_model != "unknown" else None

        anomaly = _biggest_anomaly(category)
        anomaly_str = (
            f"biggest single-day deviation: {anomaly['deviation_percent']:.1f}% "
            f"({anomaly['severity']} severity) on {anomaly['date']} "
            f"(actual={anomaly['actual_sales']:.1f}, forecast={anomaly['forecast_sales']:.1f})"
            if anomaly else "anomaly detail unavailable"
        )

        try:
            rec = generate_recommendations(RecommendationRequest(category=category, model="arima"))
            signals = "; ".join(f"{r.signal} ({r.priority}): {r.recommendation}" for r in rec.recommendations)
            lines.append(
                f"- {category}: best model={best_model}"
                f"{f' (MAE={best_mae:.2f})' if best_mae is not None else ''}, "
                f"30-day forecast trend={rec.forecast_trend_pct:+.1f}%, "
                f"anomaly days={rec.anomaly_count}, {anomaly_str}, "
                f"signals=[{signals}]"
            )
        except Exception as e:
            logger.warning("Chat context: recommendations failed for %s (%s)", category, e)
            lines.append(f"- {category}: best model={best_model}, {anomaly_str} (recommendation data unavailable)")

    return "DATA SNAPSHOT (all 8 categories, computed just now from real historical sales and live model outputs):\n" + "\n".join(lines)


async def _ask_gemini(question: str, context: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": f"{context}\n\nUser message: {question}"}]}],
        "generationConfig": {"temperature": 0.4},
    }
    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def _ask_groq(question: str, context: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": f"{SYSTEM_INSTRUCTION}\n\n{context}"},
            {"role": "user", "content": question},
        ],
        "temperature": 0.4,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def get_chat_reply(question: str) -> tuple[str, str]:
    context = _build_context_summary()

    try:
        return await _ask_gemini(question, context), "gemini"
    except Exception as e:
        logger.warning("Gemini failed (%s: %s), falling back to Groq", type(e).__name__, e)

    try:
        return await _ask_groq(question, context), "groq"
    except Exception as e:
        logger.error("Groq fallback also failed (%s: %s)", type(e).__name__, e)
        raise
