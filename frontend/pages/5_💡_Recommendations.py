"""
💡  Recommendations Engine
============================
Intelligent, actionable business recommendations per category/model.
Displays prioritised signals with rationale and trend context.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from utils.styles import inject_css, page_header, section_title, kpi_card, rec_card, offline_banner
from utils.api_client import check_health, get_recommendations
from utils.formatting import fmt_pct, signal_icon, priority_color

CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
MODELS     = ["arima", "sarima"]
CAT_NAMES = {
    "M01AB": "Anti-inflammatory (NSAID)",
    "M01AE": "Propionic Acid Derivatives",
    "N02BA": "Aspirin & Salicylates",
    "N02BE": "Paracetamol & Anilides",
    "N05B":  "Anxiolytics",
    "N05C":  "Hypnotics / Sedatives",
    "R03":   "Bronchodilators",
    "R06":   "Antihistamines",
}

SIGNAL_DESCRIPTIONS = {
    "RESTOCK_ALERT":    "Forecast shows growing demand — consider restocking inventory proactively.",
    "OVERSTOCK_RISK":   "Forecast shows declining demand — reduce procurement to avoid overstock.",
    "HIGH_UNCERTAINTY": "Model MAPE is above 30% — treat forecast with additional caution.",
    "STABLE_SUPPLY":    "No significant demand signals — supply chain appears balanced.",
    "DEMAND_SPIKE":     "High-severity anomalies detected — investigate demand drivers urgently.",
}


def _all_categories_summary(is_connected: bool) -> None:
    """Render a summary table of all categories with top signal."""
    section_title("📊", "All Categories — Signal Overview")

    rows = []
    for cat in CATEGORIES:
        data = get_recommendations(cat, "arima") if is_connected else None
        if not data:
            rows.append({"Category": cat, "Name": CAT_NAMES.get(cat,""), "Top Signal": "—",
                         "Priority": "—", "Trend %": "N/A", "MAPE": "N/A", "Anomalies": "—"})
            continue
        recs = data.get("recommendations", [])
        top = recs[0] if recs else {}
        rows.append({
            "Category": cat,
            "Name": CAT_NAMES.get(cat, ""),
            "Top Signal": top.get("signal", "—"),
            "Priority": top.get("priority", "—"),
            "Trend %": fmt_pct(data.get("forecast_trend_pct")),
            "MAE": fmt_num(data.get("model_mae"), 2) if data.get("model_mae") is not None else fmt_pct(data.get("model_mape")),
            "Anomalies": str(data.get("anomaly_count", 0)),
        })

    df = pd.DataFrame(rows)

    def _color_priority(val):
        c = priority_color(val)
        return f"color: {c}; font-weight: 700;"

    def _color_signal(val):
        if "RESTOCK" in str(val):
            return "color: #00FF88;"
        if "OVERSTOCK" in str(val) or "UNCERTAINTY" in str(val):
            return "color: #FFD700;"
        if "SPIKE" in str(val):
            return "color: #FF4444;"
        return "color: #B0B5C0;"

    st.dataframe(
        df.style
          .map(_color_priority, subset=["Priority"])
          .map(_color_signal, subset=["Top Signal"]),
        use_container_width=True,
        hide_index=True,
    )


def render():
    inject_css()
    is_connected = check_health()
    page_header(
        "💡 Recommendations Engine",
        "Intelligent supply chain signals — prioritised actions for 8 drug categories",
        connected=is_connected,
    )

    if not is_connected:
        offline_banner()
        return

    # ── Sidebar Controls ─────────────────────────────────────────────────────
    st.sidebar.markdown("## ⚙️ Controls")
    selected_view = st.sidebar.segmented_control(
        "View Mode",
        options=["🎯 Single Category", "📊 All Categories Overview"],
        default="🎯 Single Category",
    )
    view_mode = "Single Category" if (selected_view and "Single Category" in selected_view) else "All Categories Overview"

    if view_mode == "Single Category":
        category = st.sidebar.selectbox("Drug Category", CATEGORIES,
                                         format_func=lambda c: f"{c} — {CAT_NAMES.get(c,'')}")
        model = st.sidebar.selectbox("Model", MODELS, format_func=str.upper)

        PRIORITY_MAP = {
            "🔴 High": "HIGH",
            "🟡 Medium": "MEDIUM",
            "🟢 Low": "LOW",
        }
        selected_pills = st.sidebar.pills(
            "Filter by Priority",
            options=list(PRIORITY_MAP.keys()),
            default=["🔴 High", "🟡 Medium", "🟢 Low"],
            selection_mode="multi",
        )
        priority_filt = [PRIORITY_MAP[k] for k in selected_pills] if selected_pills else []
    else:
        category = model = None
        priority_filt = []

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # ── All Categories Overview ───────────────────────────────────────────────
    if view_mode == "All Categories Overview":
        _all_categories_summary(is_connected)
        return

    # ── Single Category Deep-Dive ─────────────────────────────────────────────
    with st.spinner("Generating recommendations…"):
        data = get_recommendations(category, model)

    if not data:
        st.error("❌ Could not load recommendations. Check backend connectivity.")
        return

    recs = data.get("recommendations", [])

    # Context KPIs
    section_title("📊", "Category Context")
    c1, c2, c3 = st.columns(3)
    trend = data.get("forecast_trend_pct", 0)
    mape  = data.get("model_mape")
    a_cnt = data.get("anomaly_count", 0)

    with c1:
        trend_color = "#00FF88" if (trend or 0) >= 0 else "#FF4444"
        kpi_card("📈", "Forecast Trend", fmt_pct(trend), accent=trend_color)
    with c2:
        mae = data.get("model_mae")
        mae_str = fmt_num(mae, 2) if mae is not None else fmt_pct(data.get("model_mape"))
        kpi_card("🎯", "Model MAE", mae_str, accent="#00FF88")
    with c3:
        kpi_card("🚨", "Anomaly Count", str(a_cnt),
                 accent="#FF4444" if a_cnt > 0 else "#00FF88")

    st.markdown("<br>", unsafe_allow_html=True)

    # Filter by priority
    if priority_filt:
        recs = [r for r in recs if r.get("priority") in priority_filt]

    if not recs:
        st.info("No recommendations match the selected priority filter.")
        return

    # Render recommendation cards
    section_title("💡", f"Recommendations ({len(recs)} signals)")

    for r in recs:
        rec_card(
            signal=r.get("signal", ""),
            priority=r.get("priority", "LOW"),
            text=r.get("recommendation", ""),
            rationale=r.get("rationale", ""),
            icon=signal_icon(r.get("signal", "")),
        )

    # ── Signal Explanation Table ──────────────────────────────────────────────
    with st.expander("📖 Signal Reference Guide", expanded=False):
        sig_rows = [
            {"Signal": k, "Description": v}
            for k, v in SIGNAL_DESCRIPTIONS.items()
        ]
        st.table(pd.DataFrame(sig_rows))


if __name__ == "__main__":
    render()
