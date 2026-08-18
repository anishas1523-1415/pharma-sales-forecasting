"""
🤖  Model Comparison
=====================
Compare model performance metrics (MAPE, RMSE) across categories.
MAPE heatmap, avg-MAPE bar chart, and per-category detail tables.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.styles import inject_css, page_header, section_title, kpi_card, offline_banner
from utils.api_client import check_health, get_metrics, compare_models, get_forecast
from utils.formatting import fmt_num, fmt_pct, mape_color
from utils.charts import mape_heatmap, model_bar_chart, multi_model_forecast_chart, MODEL_COLORS, _apply_dark

CATEGORIES = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
MODELS     = ["prophet", "arima", "sarima", "lightgbm", "lstm"]


def _best_model_badge(best: str | None) -> str:
    if not best:
        return ""
    color = MODEL_COLORS.get(best, "#00D9FF")
    return (f'<span style="background:{color}22; color:{color}; border:1px solid {color}55; '
            f'border-radius:6px; padding:2px 8px; font-size:0.72rem; font-weight:700;">'
            f'⭐ {best.upper()}</span>')


def render():
    inject_css()
    is_connected = check_health()
    page_header(
        "🤖 Model Comparison",
        "Evaluate & compare MAPE, RMSE across Prophet · ARIMA · SARIMA · LightGBM · LSTM",
        connected=is_connected,
    )

    if not is_connected:
        offline_banner()
        return

    # ── Sidebar Controls ─────────────────────────────────────────────────────
    st.sidebar.markdown("## ⚙️ Controls")
    selected_view = st.sidebar.segmented_control(
        "View Mode",
        options=["🌡️ Global Heatmap", "🔍 Category Deep-Dive", "📈 Overlay Chart"],
        default="🌡️ Global Heatmap",
    )
    view_tab = (
        "Global Heatmap" if (not selected_view or "Global Heatmap" in selected_view)
        else ("Category Deep-Dive" if "Category Deep-Dive" in selected_view else "Overlay Chart")
    )

    if view_tab in ("Category Deep-Dive", "Overlay Chart"):
        category = st.sidebar.selectbox("Drug Category", CATEGORIES)
    else:
        category = None

    if view_tab == "Overlay Chart":
        horizon = st.sidebar.slider("Forecast Horizon (days)", 7, 30, 30)
    else:
        horizon = 30

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    metrics = get_metrics()

    # ── GLOBAL HEATMAP ────────────────────────────────────────────────────────
    if view_tab == "Global Heatmap":
        if not metrics:
            st.warning("⚠️ Metrics data unavailable. Run training to generate metrics.json.")
            return

        section_title("🌡️", "MAE Heatmap — All Categories × Models")
        fig = mape_heatmap(metrics)
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)
        section_title("📊", "Average MAE by Model (All 8 Categories)")
        bar = model_bar_chart(metrics)
        bar.update_layout(height=380)
        st.plotly_chart(bar, use_container_width=True)

        # Best-model per category table (lowest MAE)
        st.markdown("<br>", unsafe_allow_html=True)
        section_title("⭐", "Best Model per Category (Lowest MAE)")
        rows = []
        for cat in CATEGORIES:
            cat_d = metrics.get(cat, {})
            best = "prophet"
            best_mae = float("inf")
            for m in ["prophet", "arima", "sarima", "lightgbm", "lstm"]:
                m_d = cat_d.get(m, {})
                if isinstance(m_d, dict) and "MAE" in m_d:
                    try:
                        val = float(m_d["MAE"])
                        if val < best_mae:
                            best_mae = val
                            best = m
                    except Exception:
                        pass
            best_val = cat_d.get(best, {}).get("MAE") if best else None
            rows.append({"Category": cat, "Best Model": best.upper() if best else "—",
                         "MAE (units)": fmt_num(best_val, 2) if best_val is not None else "N/A"})
        df_best = pd.DataFrame(rows)

        def _color_best(val):
            c = MODEL_COLORS.get(val.lower(), "#B0B5C0")
            return f"color: {c}; font-weight: 700;"

        st.dataframe(
            df_best.style.map(_color_best, subset=["Best Model"]),
            use_container_width=True, hide_index=True,
        )

    # ── CATEGORY DEEP-DIVE ────────────────────────────────────────────────────
    elif view_tab == "Category Deep-Dive":
        section_title("🔍", f"Model Performance — {category}")

        cmp_data = compare_models(category)
        if not cmp_data:
            st.warning("⚠️ No comparison data for this category.")
            return

        # determine best model by lowest MAE
        models_data = cmp_data.get("models", {})
        best = "prophet"
        best_mae = float("inf")
        for m, m_data in models_data.items():
            if isinstance(m_data, dict) and "MAE" in m_data:
                try:
                    val = float(m_data["MAE"])
                    if val < best_mae:
                        best_mae = val
                        best = m
                except Exception:
                    pass

        st.markdown(f"Best Model (Lowest MAE): {_best_model_badge(best)}", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        rows = []
        for m, m_data in models_data.items():
            if not isinstance(m_data, dict):
                continue
            mape = m_data.get("MAPE") or m_data.get("MAPE_%")
            rmse = m_data.get("RMSE")
            mae  = m_data.get("MAE")
            rows.append({
                "Model": m.upper(),
                "MAE":    fmt_num(float(mae), 2) if mae is not None else "N/A",
                "RMSE":   fmt_num(float(rmse), 2) if rmse is not None else "N/A",
                "MAPE %": fmt_pct(float(mape)) if mape is not None else "N/A",
                "Status": "⭐ Best" if m == best else "",
            })
        df_cmp = pd.DataFrame(rows)

        def _color_model(val):
            c = MODEL_COLORS.get(val.lower().replace(" ",""), "#B0B5C0")
            return f"color: {c}; font-weight: 700;"

        st.dataframe(
            df_cmp.style.map(_color_model, subset=["Model"]),
            use_container_width=True, hide_index=True,
        )

        # Bar chart for this category (MAE)
        if rows:
            mae_vals = []
            model_names = []
            for r in rows:
                if r["MAE"] != "N/A":
                    try:
                        mae_vals.append(float(r["MAE"].replace(",","")))
                        model_names.append(r["Model"])
                    except Exception:
                        pass

            if mae_vals:
                fig = go.Figure(go.Bar(
                    x=model_names, y=mae_vals,
                    marker=dict(
                        color=[MODEL_COLORS.get(m.lower(), "#B0B5C0") for m in model_names],
                        line=dict(color="rgba(255,255,255,0.1)", width=1),
                    ),
                    text=[f"{v:.2f}" for v in mae_vals],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>MAE: %{y:.2f}<extra></extra>",
                ))
                fig.update_layout(yaxis_title="MAE (units)", height=350)
                st.plotly_chart(_apply_dark(fig, f"{category} — Model MAE Comparison"),
                                use_container_width=True)

    # ── OVERLAY CHART ─────────────────────────────────────────────────────────
    elif view_tab == "Overlay Chart":
        section_title("📈", f"All-Model Forecast Overlay — {category}")

        MODEL_PILL_OPTIONS = {
            "🔵 PROPHET": "prophet",
            "🟡 ARIMA": "arima",
            "🟢 SARIMA": "sarima",
            "🟠 LIGHTGBM": "lightgbm",
            "🟣 LSTM": "lstm",
        }

        selected_pills = st.pills(
            "Models to Overlay",
            options=list(MODEL_PILL_OPTIONS.keys()),
            default=list(MODEL_PILL_OPTIONS.keys()),
            selection_mode="multi",
        )
        selected_models = [MODEL_PILL_OPTIONS[k] for k in selected_pills] if selected_pills else []

        forecasts = {}
        for m in selected_models:
            data = get_forecast(category, m, horizon)
            if data:
                pts = data.get("forecast", [])
                if pts:
                    forecasts[m] = pd.DataFrame(pts)

        if not forecasts:
            st.info("No forecast data available for the selected models.")
            return

        fig = multi_model_forecast_chart(forecasts, None, category)
        fig.update_layout(height=480)
        st.plotly_chart(fig, use_container_width=True)

        # Numeric comparison table
        st.markdown("<br>", unsafe_allow_html=True)
        section_title("📋", "Model Totals Comparison")
        rows = []
        for m, df in forecasts.items():
            preds = df["prediction"].tolist()
            rows.append({
                "Model": m.upper(),
                "Total Forecast": fmt_num(sum(preds), 0),
                "Avg Daily": fmt_num(sum(preds)/len(preds) if preds else 0, 2),
                "Min": fmt_num(min(preds), 2),
                "Max": fmt_num(max(preds), 2),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render()
