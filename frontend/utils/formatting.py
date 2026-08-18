"""
utils/formatting.py
====================
Number, date, and text formatting helpers.
"""
from __future__ import annotations
import math


def fmt_num(val: float | int, decimals: int = 2) -> str:
    """Format number with thousand separators."""
    if val is None:
        return "N/A"
    try:
        return f"{float(val):,.{decimals}f}"
    except Exception:
        return str(val)


def fmt_pct(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{float(val):.{decimals}f}%"


def fmt_trend(val: float | None) -> str:
    if val is None:
        return "—"
    arrow = "▲" if val >= 0 else "▼"
    return f"{arrow} {abs(val):.2f}%"


def mape_color(mape: float | None) -> str:
    """Return CSS color class string based on MAPE level."""
    if mape is None:
        return "#B0B5C0"
    if mape <= 20:
        return "#00FF88"
    elif mape <= 30:
        return "#FFD700"
    return "#FF6B35"


def severity_color(severity: str) -> str:
    mapping = {
        "high": "#FF4444",
        "medium": "#FF6B35",
        "low": "#00FF88",
        "normal": "#00D9FF",
        "moderate": "#FFD700",
        "anomaly": "#FF6B35",
    }
    return mapping.get(severity.lower(), "#B0B5C0")


def priority_color(priority: str) -> str:
    mapping = {
        "HIGH": "#FF4444",
        "MEDIUM": "#FFD700",
        "LOW": "#00FF88",
    }
    return mapping.get(priority.upper(), "#B0B5C0")


def signal_icon(signal: str) -> str:
    mapping = {
        "RESTOCK_ALERT": "📦",
        "OVERSTOCK_RISK": "⚠️",
        "HIGH_UNCERTAINTY": "🔮",
        "STABLE_SUPPLY": "✅",
        "DEMAND_SPIKE": "🚨",
    }
    return mapping.get(signal, "📊")
