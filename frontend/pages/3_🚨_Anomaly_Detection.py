"""
🚨  Anomaly Detection
======================
Compare forecast vs actuals to surface demand deviations.
Shows interactive chart, severity donut, and detailed results table.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from utils.styles import inject_css, page_header, section_title, kpi_card, offline_banner
from utils.api_client import check_health, get_metrics, detect_anomalies
from utils.formatting import fmt_num, fmt_pct, severity_color
from utils.charts import anomaly_chart, severity_donut

CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
MODELS     = ["arima", "sarima"]


def _badge_html(text: str, severity: str) -> str:
    color = severity_color(severity)
    return (
        f'<span style="background:{color}22; color:{color}; border:1px solid {color}55; '
        f'border-radius:5px; padding:2px 8px; font-size:0.72rem; font-weight:700;">{text}</span>'
    )


def render():
    inject_css()
    is_connected = check_health()
    page_header(
        "🚨 Anomaly Detection",
        "Identify demand deviations — compare ML forecast vs actual historical sales",
        connected=is_connected,
    )

    if not is_connected:
        offline_banner()
        return

    # ── Sidebar Controls ──────────────────────────────────────────────────────
    st.sidebar.markdown("## ⚙️ Controls")
    category = st.sidebar.selectbox("Drug Category", CATEGORIES)
    model    = st.sidebar.selectbox("Model", MODELS, format_func=str.upper)
    SEVERITY_OPTIONS = {
        "🟢 Normal (<10%)": "normal",
        "🟡 Moderate (10–25%)": "moderate",
        "🟠 Medium (25–50%)": "medium",
        "🔴 High (>50%)": "high",
    }

    selected_pills = st.sidebar.pills(
        "Filter by Severity",
        options=list(SEVERITY_OPTIONS.keys()),
        default=["🟡 Moderate (10–25%)", "🟠 Medium (25–50%)", "🔴 High (>50%)"],
        selection_mode="multi",
    )
    severity_filter = [SEVERITY_OPTIONS[k] for k in selected_pills] if selected_pills else []

    if st.sidebar.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # ── Load Data ─────────────────────────────────────────────────────────────
    with st.spinner("Detecting anomalies…"):
        data = detect_anomalies(category, model)

    if not data:
        st.error("❌ Could not retrieve anomaly data. Ensure forecast CSVs and processed data exist.")
        return

    results = data.get("results", [])
    total   = data.get("total_days", 0)
    a_count = data.get("anomaly_count", 0)
    high    = sum(1 for r in results if r.get("severity") == "high")
    med     = sum(1 for r in results if r.get("severity") == "medium")

    # ── KPI Row ───────────────────────────────────────────────────────────────
    section_title("📊", "Anomaly Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("📅", "Days Compared", str(total), accent="#00D9FF")
    with c2: kpi_card("🚨", "Total Anomalies", str(a_count),
                       accent="#FF4444" if a_count > 0 else "#00FF88")
    with c3: kpi_card("🔴", "High Severity", str(high),
                       accent="#FF4444" if high > 0 else "#00FF88")
    with c4: kpi_card("🟡", "Medium Severity", str(med),
                       accent="#FFD700" if med > 0 else "#00FF88")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Chart + Donut ─────────────────────────────────────────────────────────
    chart_col, donut_col = st.columns([3, 1])

    with chart_col:
        section_title("📉", "Forecast vs Actuals with Anomaly Markers")
        fig = anomaly_chart(results, category, model)
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

    with donut_col:
        section_title("🍩", "Severity Split")
        donut = severity_donut(results)
        donut.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(donut, use_container_width=True)

    # ── Results Table ─────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_title("📋", "Detailed Results Table")

    if not results:
        st.info("No overlapping date range found between forecast and actual sales data.")
        return

    df = pd.DataFrame(results)

    # Apply severity filter
    if severity_filter:
        # map "medium" & "high" through severity; "normal" and "moderate" through status
        allowed_sev  = {s for s in severity_filter if s in ("medium", "high")}
        allowed_stat = {s for s in severity_filter if s in ("normal", "moderate")}
        mask = df["severity"].isin(allowed_sev) | df["status"].isin(allowed_stat)
        df = df[mask]

    if df.empty:
        st.info("No results match the selected severity filters.")
        return

    # Rename & format
    df = df.rename(columns={
        "date": "Date",
        "actual_sales": "Actual Sales",
        "forecast_sales": "Forecast Sales",
        "deviation_percent": "Deviation %",
        "status": "Status",
        "severity": "Severity",
    })
    df["Actual Sales"]   = df["Actual Sales"].apply(lambda v: fmt_num(v, 2))
    df["Forecast Sales"] = df["Forecast Sales"].apply(lambda v: fmt_num(v, 2))
    df["Deviation %"]    = df["Deviation %"].apply(lambda v: f"{float(v):.2f}%")

    def _color_severity(val):
        c = severity_color(val)
        return f"color: {c}; font-weight: 700;"

    def _color_status(val):
        c = severity_color(val)
        return f"color: {c};"

    styled = df.style.map(_color_severity, subset=["Severity"]).map(_color_status, subset=["Status"])
    st.dataframe(styled, use_container_width=True, height=450, hide_index=True)

    # Download button
    st.markdown("<br>", unsafe_allow_html=True)
    csv_bytes = df.to_csv(index=False).encode()
    st.download_button(
        label="⬇️  Download Results as CSV",
        data=csv_bytes,
        file_name=f"anomaly_{category}_{model}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    render()
