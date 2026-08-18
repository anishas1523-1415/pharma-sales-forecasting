"""
📈  Forecast Explorer
=====================
Interactive single-category, single-model forecast viewer.
Users can adjust horizon, toggle historical overlay, and explore
prediction tables.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from utils.styles import inject_css, page_header, section_title, kpi_card, offline_banner
from utils.api_client import check_health, get_metrics, get_forecast, detect_anomalies
from utils.formatting import fmt_num, fmt_pct, fmt_trend
from utils.charts import forecast_chart, MODEL_COLORS

CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
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
MODELS = ["prophet", "arima", "sarima", "lightgbm", "lstm"]


def _get_mae(metrics: dict | None, category: str, model: str) -> float | None:
    if not metrics:
        return None
    cat = metrics.get(category, {})
    m_data = cat.get(model, {})
    v = m_data.get("MAE")
    return float(v) if v is not None else None


def _get_rmse(metrics: dict | None, category: str, model: str) -> float | None:
    if not metrics:
        return None
    cat = metrics.get(category, {})
    m_data = cat.get(model, {})
    v = m_data.get("RMSE")
    return float(v) if v is not None else None


def render():
    inject_css()
    is_connected = check_health()
    page_header(
        "📈 Forecast Explorer",
        "Deep-dive into individual category forecasts · Adjust horizon · Compare against actuals",
        connected=is_connected,
    )

    if not is_connected:
        offline_banner()
        return

    # ── Sidebar controls ─────────────────────────────────────────────────────
    st.sidebar.markdown("## ⚙️ Controls")
    category = st.sidebar.selectbox("Drug Category", CATEGORIES,
                                     format_func=lambda c: f"{c} — {CAT_NAMES.get(c, '')}")
    model = st.sidebar.selectbox("Forecasting Model", MODELS, format_func=str.upper)
    horizon = st.sidebar.slider("Forecast Horizon (days)", min_value=7, max_value=30, value=30, step=1)
    show_history = st.sidebar.checkbox("Show Historical Overlay", value=True)

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # ── Load data ────────────────────────────────────────────────────────────
    metrics = get_metrics()
    forecast_data = get_forecast(category, model, horizon)
    anomaly_data = detect_anomalies(category, model) if show_history else None

    if not forecast_data:
        st.error("❌ Could not load forecast data. Check that the backend is running and forecast CSVs exist.")
        return

    pts = forecast_data.get("forecast", [])
    forecast_df = pd.DataFrame(pts)

    # historical actuals from anomaly endpoint (actual_sales column)
    hist_df = None
    if anomaly_data and show_history:
        results = anomaly_data.get("results", [])
        if results:
            hist_df = pd.DataFrame(results)[["date", "actual_sales"]]

    # ── KPI Row ──────────────────────────────────────────────────────────────
    section_title("📊", "Forecast Summary")
    c1, c2, c3, c4 = st.columns(4)
    preds = [p["prediction"] for p in pts]

    with c1:
        kpi_card("📅", "Forecast Days", str(len(pts)), accent="#00D9FF")
    with c2:
        kpi_card("📦", "Total Forecast Sales", fmt_num(sum(preds), 0), accent="#00FF88")
    with c3:
        kpi_card("📈", "Avg Daily Forecast", fmt_num(sum(preds)/len(preds) if preds else 0, 2),
                 accent="#FFD700")
    with c4:
        mae = _get_mae(metrics, category, model)
        kpi_card("🎯", "Model MAE", fmt_num(mae, 2) if mae else "N/A", accent="#00FF88")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Main Chart ───────────────────────────────────────────────────────────
    section_title("📉", "Forecast Chart")
    fig = forecast_chart(forecast_df, hist_df, category, model, show_history)
    fig.update_layout(height=460)
    st.plotly_chart(fig, use_container_width=True)

    # ── Stats Panel ──────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_title("🔢", "Statistical Summary")

    col_l, col_r = st.columns([1, 2])
    with col_l:
        if preds:
            rmse = _get_rmse(metrics, category, model)
            summary_data = {
                "Metric": ["Min Forecast", "Max Forecast", "Std Dev", "MAE", "RMSE"],
                "Value": [
                    fmt_num(min(preds), 2),
                    fmt_num(max(preds), 2),
                    fmt_num(pd.Series(preds).std(), 2),
                    fmt_num(mae, 2) if mae else "N/A",
                    fmt_num(rmse, 2) if rmse else "N/A",
                ],
            }
            st.dataframe(pd.DataFrame(summary_data), hide_index=True, use_container_width=True)

    with col_r:
        st.markdown("**📋 Forecast Data Table**")
        display_df = forecast_df.copy()
        display_df.columns = ["Date", "Forecast (units)"]
        display_df["Forecast (units)"] = display_df["Forecast (units)"].apply(lambda v: fmt_num(v, 2))
        st.dataframe(display_df, use_container_width=True, height=260, hide_index=True)

    # ── Trend sparkline ──────────────────────────────────────────────────────
    if len(preds) >= 2:
        first_half = sum(preds[:len(preds)//2]) / (len(preds)//2)
        second_half = sum(preds[len(preds)//2:]) / (len(preds) - len(preds)//2)
        trend_pct = (second_half - first_half) / first_half * 100 if first_half else 0

        trend_color = "green" if trend_pct >= 0 else "red"
        trend_icon = "📈" if trend_pct >= 0 else "📉"
        st.markdown(f"""
        <div style="background:rgba(26,31,46,0.9); border:1px solid #2A2F3E; border-radius:12px;
                    padding:1rem 1.5rem; margin-top:1rem; display:flex; align-items:center; gap:1rem;">
            <span style="font-size:2rem;">{trend_icon}</span>
            <div>
                <div style="color:#B0B5C0; font-size:0.78rem; font-weight:500; text-transform:uppercase;">
                    Forecast Trend (First Half vs Second Half)
                </div>
                <div style="color:{'#00FF88' if trend_pct >= 0 else '#FF4444'};
                            font-size:1.6rem; font-weight:700; font-family:'Space Mono',monospace;">
                    {'+' if trend_pct >= 0 else ''}{trend_pct:.2f}%
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    render()
