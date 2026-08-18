"""
🔬  What-If Simulator
======================
Interactive demand scenario modelling.
Users apply % demand shifts and optional supply disruption windows,
then compare adjusted vs baseline forecasts.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from utils.styles import inject_css, page_header, section_title, kpi_card, offline_banner
from utils.api_client import check_health, run_what_if
from utils.formatting import fmt_num, fmt_pct
from utils.charts import what_if_chart

CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
MODELS     = ["prophet", "arima", "sarima", "lightgbm", "lstm"]
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


def render():
    inject_css()
    is_connected = check_health()
    page_header(
        "🔬 What-If Simulator",
        "Model demand scenarios — apply % shifts and supply disruptions to any forecast",
        connected=is_connected,
    )

    if not is_connected:
        offline_banner()
        return

    # ── Scenario Configuration Panel ──────────────────────────────────────────
    st.sidebar.markdown("## ⚙️ Scenario Configuration")
    category = st.sidebar.selectbox("Drug Category", CATEGORIES,
                                     format_func=lambda c: f"{c} — {CAT_NAMES.get(c,'')}")
    model    = st.sidebar.selectbox("Model", MODELS, format_func=str.upper)

    st.sidebar.markdown("### 📊 Demand Adjustment")
    change_pct = st.sidebar.slider(
        "Demand Change %",
        min_value=-80.0, max_value=200.0, value=20.0, step=5.0,
        help="Positive = demand increase; Negative = demand decline"
    )

    st.sidebar.markdown("### 🚨 Supply Disruption Scenario")
    use_disruption = st.sidebar.checkbox("Enable Supply Disruption", value=False)
    disruption_start = disruption_end = None

    if use_disruption:
        import datetime
        from backend.data_loader import load_forecast
        try:
            f_df = load_forecast(category, model)
            dates = pd.to_datetime(f_df["date"])
            min_d = dates.min().date()
            max_d = dates.max().date()
            default_start = min_d + datetime.timedelta(days=3)
            default_end   = min_d + datetime.timedelta(days=12)
        except Exception:
            min_d = datetime.date(2019, 10, 9)
            max_d = datetime.date(2019, 11, 7)
            default_start = datetime.date(2019, 10, 12)
            default_end   = datetime.date(2019, 10, 22)

        st.sidebar.markdown("""
        <div style="background: rgba(255, 68, 68, 0.08); border: 1px solid rgba(255, 68, 68, 0.3);
                    border-radius: 8px; padding: 0.5rem 0.8rem; margin: 0.4rem 0 0.8rem 0; font-size: 0.78rem; color: #FF6B6B;">
            ⚠️ Outage Period — Sales zeroed out
        </div>
        """, unsafe_allow_html=True)

        disruption_start = str(st.sidebar.date_input(
            "Disruption Start",
            value=default_start,
            min_value=min_d,
            max_value=max_d,
        ))
        disruption_end = str(st.sidebar.date_input(
            "Disruption End",
            value=default_end,
            min_value=min_d,
            max_value=max_d,
        ))

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Clear Cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # ── Run Simulation ─────────────────────────────────────────────────────────
    current_params = (category, model, change_pct, use_disruption, disruption_start, disruption_end)
    if ("whatif_params" not in st.session_state) or (st.session_state.get("whatif_params") != current_params):
        with st.spinner("Running simulation…"):
            data = run_what_if(
                category, model, change_pct,
                disruption_start if use_disruption else None,
                disruption_end   if use_disruption else None,
            )
        if data:
            st.session_state["whatif_data"] = data
            st.session_state["whatif_params"] = current_params
        else:
            st.error("❌ Simulation failed. Ensure the forecast CSV exists for this category/model combination.")
            return

    data = st.session_state.get("whatif_data")
    if not data:
        st.info("👈 Configure a scenario in the sidebar to view impact.")
        return

    baseline   = data.get("total_baseline", 0)
    adjusted   = data.get("total_adjusted", 0)
    difference = data.get("total_difference", 0)
    disruption_days = data.get("disruption_days", 0)

    pct_diff = (difference / baseline * 100) if baseline else 0
    direction = "increase" if pct_diff >= 0 else "decrease"
    color2 = "#00FF88" if pct_diff >= 0 else "#FF4444"

    disrupt_badge = (
        f'<span style="background:rgba(255,68,68,0.18); color:#FF4444; border:1px solid rgba(255,68,68,0.4); '
        f'border-radius:6px; padding:4px 12px; font-size:0.8rem; font-weight:700;">'
        f'🚨 Disruption: {disruption_start} → {disruption_end}</span>'
        if use_disruption else ""
    )

    # ── Top-of-Page Business Impact Executive Summary ───────────────────────────
    st.markdown(f"""
    <div style="background:linear-gradient(135deg, rgba(26,31,46,0.95) 0%, rgba(35,42,59,0.95) 100%);
                border:1px solid rgba(0,217,255,0.25); border-radius:14px; padding:1.3rem 1.6rem; margin-bottom:1.2rem;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem;">
            <div style="color:#B0B5C0; font-size:0.78rem; text-transform:uppercase; font-weight:600; letter-spacing:0.05em;">
                💡 Business Impact Executive Summary — {category} · {model.upper()}
            </div>
            <div>{disrupt_badge}</div>
        </div>
        <div style="font-size:1.35rem; font-weight:700; color:#F5F5F5; line-height:1.4;">
            A <span style="color:{color2};">{change_pct:+.0f}%</span> demand shift results in a
            <span style="color:{color2};">{abs(pct_diff):.1f}% {direction}</span>
            in total forecasted sales ({fmt_num(baseline, 0)} → {fmt_num(adjusted, 0)} units)
            {'with <span style="color:#FF4444; font-weight:700;">' + str(disruption_days) + ' disruption days zeroed out</span>.' if disruption_days > 0 else '.'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPI Cards ──────────────────────────────────────────────────────────────
    section_title("📊", "Simulation Results")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("📊", "Baseline Total", fmt_num(baseline, 0), accent="#1E88E5")
    with c2:
        kpi_card("🎯", "Adjusted Total", fmt_num(adjusted, 0),
                 accent="#00FF88" if adjusted >= baseline else "#FF4444")
    with c3:
        diff_val = f"{'+' if difference >= 0 else ''}{fmt_num(difference, 0)}"
        kpi_card("∆ Difference", "Net Impact", diff_val,
                 accent="#00FF88" if difference >= 0 else "#FF4444")
    with c4:
        kpi_card("⚡", "Disruption Days", str(disruption_days),
                 accent="#FF6B35" if disruption_days > 0 else "#B0B5C0")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Chart ──────────────────────────────────────────────────────────────────
    section_title("📉", "Baseline vs Adjusted Forecast")
    fig = what_if_chart(data)
    fig.update_layout(height=460)
    st.plotly_chart(fig, use_container_width=True)

    # ── Data Table ────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    section_title("📋", "Day-by-Day Breakdown")

    results = data.get("results", [])
    if results:
        df = pd.DataFrame(results)
        df = df.rename(columns={
            "date": "Date",
            "baseline_sales": "Baseline",
            "adjusted_sales": "Adjusted",
            "difference": "Δ",
            "change_percent": "Δ %",
        })
        df["Baseline"] = df["Baseline"].apply(lambda v: fmt_num(v, 2))
        df["Adjusted"] = df["Adjusted"].apply(lambda v: fmt_num(v, 2))
        df["Δ"] = df["Δ"].apply(lambda v: f"{'+' if float(v)>=0 else ''}{fmt_num(v, 2)}")
        df["Δ %"] = df["Δ %"].apply(lambda v: f"{float(v):+.2f}%")

        st.dataframe(df, use_container_width=True, height=350, hide_index=True)

        csv = df.to_csv(index=False).encode()
        st.download_button("⬇️  Download CSV", csv,
                           f"whatif_{category}_{model}.csv", "text/csv")


if __name__ == "__main__":
    render()
