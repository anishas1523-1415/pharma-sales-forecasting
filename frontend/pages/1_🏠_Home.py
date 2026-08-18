"""
🏠  Home / Executive Dashboard
================================
Landing page: system status KPIs, all-category forecast trend cards,
anomaly summary, and top recommendations.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.styles import inject_css, page_header, section_title, kpi_card, rec_card, offline_banner, badge
from utils.api_client import (
    check_health, get_models, get_metrics,
    get_forecast, detect_anomalies, get_recommendations,
)
from utils.formatting import fmt_num, fmt_pct, fmt_trend, mape_color, signal_icon
from utils.charts import MODEL_COLORS, _apply_dark

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

HORIZON = 30   # days for quick overview forecasts


def _best_model_for(metrics: dict, category: str) -> str:
    cat_data = metrics.get(category, {})
    best_model = cat_data.get("best_model", "prophet")
    best_mae = float("inf")
    for m in ["prophet", "arima", "sarima", "lightgbm", "lstm"]:
        m_d = cat_data.get(m, {})
        if isinstance(m_d, dict) and "MAE" in m_d:
            try:
                val = float(m_d["MAE"])
                if val < best_mae:
                    best_mae = val
                    best_model = m
            except Exception:
                pass
    return best_model


def _trend_pct(forecast_data: dict | None) -> float | None:
    if not forecast_data:
        return None
    pts = forecast_data.get("forecast", [])
    if len(pts) < 2:
        return None
    first = pts[0]["prediction"]
    last  = pts[-1]["prediction"]
    if first == 0:
        return None
    return round((last - first) / first * 100, 2)


def _render_kpis(metrics: dict | None, models_data: dict | None, is_connected: bool):
    section_title("📊", "Executive Overview")

    col1, col2, col3 = st.columns(3)

    with col1:
        kpi_card("🏥", "Drug Categories", "8", accent="#00D9FF")

    with col2:
        num_models = len(models_data) if models_data else 5
        kpi_card("🤖", "Active Models", str(num_models),
                 accent="#00FF88")

    with col3:
        if metrics:
            all_maes = []
            for cat in CATEGORIES:
                cat_d = metrics.get(cat, {})
                for m_d in cat_d.values():
                    if isinstance(m_d, dict):
                        v = m_d.get("MAE")
                        if v is not None:
                            all_maes.append(float(v))
            avg = round(sum(all_maes) / len(all_maes), 2) if all_maes else None
            kpi_card("🎯", "Avg. MAE (All)", f"{avg:.2f}" if avg else "N/A", accent="#FFD700")
        else:
            kpi_card("🎯", "Avg. MAE (All)", "N/A", accent="#FFD700")


def _render_category_grid(metrics: dict | None, is_connected: bool):
    section_title("📦", "Category Overview")
    st.caption("Best model selected automatically per category based on lowest MAE.")

    cols = st.columns(4)
    for i, cat in enumerate(CATEGORIES):
        with cols[i % 4]:
            best_model = _best_model_for(metrics, cat) if metrics else "prophet"
            model_color = MODEL_COLORS.get(best_model, "#00D9FF")

            if is_connected:
                forecast_data = get_forecast(cat, best_model, HORIZON)
                trend = _trend_pct(forecast_data)
            else:
                forecast_data = None
                trend = None

            trend_str = fmt_trend(trend) if trend is not None else "—"
            trend_color = "#00FF88" if (trend or 0) >= 0 else "#FF4444"

            html = f"""
            <div class="cat-card">
                <div style="display:flex; align-items:center; justify-content:space-between;">
                    <span class="cat-code" style="color:{model_color};">{cat}</span>
                    <span style="color:{trend_color}; font-size:0.85rem; font-weight:700;">{trend_str}</span>
                </div>
                <div class="cat-model">{CAT_NAMES.get(cat, cat)}</div>
                <div style="margin-top:0.5rem;">
                    <span style="background:{model_color}22; color:{model_color}; border:1px solid {model_color}44;
                          border-radius:6px; padding:2px 8px; font-size:0.7rem; font-weight:600;">
                        {best_model.upper()}
                    </span>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)


def _render_overview_chart(metrics: dict | None, is_connected: bool):
    section_title("📈", "30-Day Forecast Trends (Best Model per Category)")

    if not is_connected:
        st.info("Connect to backend to view live forecast trends.")
        return

    fig = go.Figure()

    for cat in CATEGORIES:
        best_model = _best_model_for(metrics, cat) if metrics else "prophet"
        forecast_data = get_forecast(cat, best_model, HORIZON)
        if not forecast_data:
            continue
        pts = forecast_data.get("forecast", [])
        if not pts:
            continue

        color = MODEL_COLORS.get(best_model, "#B0B5C0")
        fig.add_trace(go.Scatter(
            x=[p["date"] for p in pts],
            y=[p["prediction"] for p in pts],
            name=cat,
            line=dict(width=2),
            hovertemplate=f"<b>{cat}</b><br>Date: %{{x}}<br>Sales: %{{y:,.2f}}<extra></extra>",
        ))

    fig.update_layout(height=420)
    st.plotly_chart(_apply_dark(fig, ""), use_container_width=True)


def _render_anomaly_summary(metrics: dict | None, is_connected: bool):
    section_title("🚨", "Anomaly Summary (Across All Categories)")

    if not is_connected:
        st.info("Backend offline — anomaly data unavailable.")
        return

    total_anomalies = 0
    high_sev = 0
    cat_anomaly_data = []

    for cat in CATEGORIES:
        best_model = _best_model_for(metrics, cat) if metrics else "prophet"
        data = detect_anomalies(cat, best_model)
        if not data:
            continue
        ac = data.get("anomaly_count", 0)
        results = data.get("results", [])
        high = sum(1 for r in results if r.get("severity") == "high")
        total_anomalies += ac
        high_sev += high
        cat_anomaly_data.append({
            "Category": cat, "Total Days": data.get("total_days", 0),
            "Anomalies": ac, "High Severity": high,
            "Model": best_model.upper(),
        })

    c1, c2 = st.columns(2)
    with c1:
        kpi_card("🚨", "Total Anomalies Detected", str(total_anomalies), accent="#FF6B35")
    with c2:
        kpi_card("🔴", "High Severity Events", str(high_sev), accent="#FF4444")

    if cat_anomaly_data:
        df = pd.DataFrame(cat_anomaly_data)
        st.dataframe(
            df.style.map(
                lambda v: "color: #FF4444; font-weight:700;" if isinstance(v, int) and v > 0 else "",
                subset=["High Severity"],
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_top_recommendations(metrics: dict | None, is_connected: bool):
    section_title("💡", "Top Priority Recommendations")

    if not is_connected:
        st.info("Backend offline — recommendations unavailable.")
        return

    high_recs = []
    for cat in CATEGORIES:
        best_model = _best_model_for(metrics, cat) if metrics else "prophet"
        data = get_recommendations(cat, best_model)
        if not data:
            continue
        for r in data.get("recommendations", []):
            if r.get("priority") == "HIGH":
                high_recs.append({**r, "category": cat})

    if not high_recs:
        st.success("✅ No high-priority alerts across all categories.")
        return

    for r in high_recs[:6]:   # show top-6
        icon = signal_icon(r["signal"])
        rec_card(
            signal=f"{r['category']} — {r['signal']}",
            priority=r["priority"],
            text=r["recommendation"],
            rationale=r["rationale"],
            icon=icon,
        )


def render():
    inject_css()
    is_connected = check_health()
    page_header(
        "💊 PharmaForecast Analytics",
        "Pharmaceutical Sales Intelligence Platform · 8 Drug Categories · 5 ML Models",
        connected=is_connected,
    )

    if not is_connected:
        offline_banner()

    metrics = get_metrics() if is_connected else None
    models_data = get_models() if is_connected else None

    _render_kpis(metrics, models_data, is_connected)

    st.markdown("<br>", unsafe_allow_html=True)
    _render_overview_chart(metrics, is_connected)

    st.markdown("<br>", unsafe_allow_html=True)
    _render_category_grid(metrics, is_connected)

    col_left, col_right = st.columns([3, 2])
    with col_left:
        _render_anomaly_summary(metrics, is_connected)
    with col_right:
        _render_top_recommendations(metrics, is_connected)


if __name__ == "__main__":
    render()
