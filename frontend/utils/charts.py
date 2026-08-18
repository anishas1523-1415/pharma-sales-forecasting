"""
utils/charts.py
================
Plotly chart factory functions for all dashboard pages.
All charts use a consistent dark theme matching the CSS.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Optional

# ── Dark chart theme base layout ───────────────────────────────────────────
DARK_LAYOUT = dict(
    paper_bgcolor="rgba(15,20,25,0)",
    plot_bgcolor="rgba(26,31,46,0.6)",
    font=dict(family="Inter, sans-serif", color="#F5F5F5"),
    xaxis=dict(
        gridcolor="rgba(42,47,62,0.6)",
        zerolinecolor="rgba(42,47,62,0.8)",
        showgrid=True,
    ),
    yaxis=dict(
        gridcolor="rgba(42,47,62,0.6)",
        zerolinecolor="rgba(42,47,62,0.8)",
        showgrid=True,
    ),
    legend=dict(
        bgcolor="rgba(26,31,46,0.8)",
        bordercolor="rgba(42,47,62,0.8)",
        borderwidth=1,
    ),
    margin=dict(l=10, r=10, t=40, b=10),
    hovermode="x unified",
)

MODEL_COLORS = {
    "prophet":  "#1E88E5",
    "arima":    "#FFD700",
    "sarima":   "#00FF88",
    "lightgbm": "#FF6B35",
    "lstm":     "#B388FF",
}


def hex_to_rgba(hex_str: str, alpha: float = 0.1) -> str:
    h = hex_str.lstrip('#')
    r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _apply_dark(fig: go.Figure, title: str = "") -> go.Figure:
    layout = dict(**DARK_LAYOUT)
    if title:
        layout["title"] = dict(text=title, font=dict(size=15, color="#F5F5F5"), x=0)
    fig.update_layout(**layout)
    return fig


def forecast_chart(
    forecast_df: pd.DataFrame,
    historical_df: Optional[pd.DataFrame],
    category: str,
    model: str,
    show_history: bool = True,
) -> go.Figure:
    """Main forecast line chart with optional historical overlay."""
    fig = go.Figure()

    if show_history and historical_df is not None and not historical_df.empty:
        fig.add_trace(go.Scatter(
            x=historical_df["date"],
            y=historical_df["actual_sales"],
            name="Historical",
            line=dict(color="#1E88E5", width=2),
            opacity=0.8,
        ))

    color = MODEL_COLORS.get(model.lower(), "#00D9FF")
    fig.add_trace(go.Scatter(
        x=forecast_df["date"],
        y=forecast_df["prediction"],
        name=f"{model.upper()} Forecast",
        line=dict(color=color, width=2.5),
        fill="tozeroy",
        fillcolor=hex_to_rgba(color, 0.1),
    ))

    # Vertical separator line
    if show_history and historical_df is not None and not historical_df.empty:
        sep_date = historical_df["date"].iloc[-1] if len(historical_df) > 0 else None
        if sep_date:
            fig.add_vline(
                x=str(sep_date),
                line_dash="dash",
                line_color="rgba(176,181,192,0.5)",
                annotation_text="Forecast →",
                annotation_font_color="#B0B5C0",
            )

    return _apply_dark(fig, f"{category} — {model.upper()} Forecast")


def multi_model_forecast_chart(
    forecasts: dict[str, pd.DataFrame],
    historical_df: Optional[pd.DataFrame],
    category: str,
) -> go.Figure:
    """Overlay multiple model forecasts on one chart."""
    fig = go.Figure()

    if historical_df is not None and not historical_df.empty:
        fig.add_trace(go.Scatter(
            x=historical_df["date"],
            y=historical_df["actual_sales"],
            name="Actual",
            line=dict(color="#1E88E5", width=2, dash="dot"),
            opacity=0.7,
        ))

    for model, df in forecasts.items():
        if df is None or df.empty:
            continue
        color = MODEL_COLORS.get(model.lower(), "#B0B5C0")
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["prediction"],
            name=model.upper(),
            line=dict(color=color, width=2),
        ))

    return _apply_dark(fig, f"{category} — All Models Comparison")


def anomaly_chart(
    results: list[dict],
    category: str,
    model: str,
) -> go.Figure:
    """Scatter+line chart highlighting anomalies by severity."""
    if not results:
        fig = go.Figure()
        return _apply_dark(fig, "No overlapping data for anomaly detection")

    df = pd.DataFrame(results)

    fig = go.Figure()

    # Actual sales line
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["actual_sales"],
        name="Actual Sales",
        line=dict(color="#1E88E5", width=2),
    ))

    # Forecast line
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["forecast_sales"],
        name="Forecast",
        line=dict(color="#FF6B35", width=2, dash="dot"),
    ))

    # Anomaly markers by severity
    sev_map = {
        "low":    ("#00FF88", "circle",         8),
        "medium": ("#FFD700", "circle",        10),
        "high":   ("#FF4444", "circle-open",   14),
    }
    for sev, (color, symbol, size) in sev_map.items():
        mask = df["severity"] == sev
        if mask.any():
            sub = df[mask]
            fig.add_trace(go.Scatter(
                x=sub["date"], y=sub["actual_sales"],
                mode="markers",
                name=f"{sev.capitalize()} Deviation",
                marker=dict(color=color, size=size, symbol=symbol,
                            line=dict(color=color, width=2)),
                hovertemplate="<b>%{x}</b><br>Actual: %{y:.2f}<extra></extra>",
            ))

    return _apply_dark(fig, f"{category} — {model.upper()} Anomaly Detection")


def what_if_chart(what_if_data: dict) -> go.Figure:
    """Dual-line chart comparing baseline vs adjusted forecast."""
    results = what_if_data.get("results", [])
    if not results:
        return _apply_dark(go.Figure(), "No data available")

    df = pd.DataFrame(results)

    fig = go.Figure()

    # Baseline
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["baseline_sales"],
        name="Baseline Forecast",
        line=dict(color="#1E88E5", width=2.5),
    ))

    # Adjusted
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["adjusted_sales"],
        name="Adjusted Forecast",
        line=dict(color="#00FF88", width=2.5),
        fill="tonexty",
        fillcolor="rgba(0,255,136,0.06)",
    ))

    # Disruption zone shading & zero markers
    disruption_days = what_if_data.get("disruption_days", 0)
    if disruption_days > 0:
        disrupted = [r for r in results if r["adjusted_sales"] == 0.0]
        if disrupted:
            x_start = disrupted[0]["date"]
            x_end = disrupted[-1]["date"]
            fig.add_vrect(
                x0=x_start, x1=x_end,
                fillcolor="rgba(255,68,68,0.18)",
                layer="below",
                line_width=1,
                line_color="rgba(255,68,68,0.6)",
                annotation_text=f"🚨 Supply Disruption ({disruption_days}d)",
                annotation_position="top left",
                annotation_font=dict(color="#FF4444", size=12, family="Inter, sans-serif"),
            )
            # Add zero-sales markers for disrupted points
            dis_df = pd.DataFrame(disrupted)
            fig.add_trace(go.Scatter(
                x=dis_df["date"], y=dis_df["adjusted_sales"],
                mode="markers",
                name="Stockout (0 units)",
                marker=dict(color="#FF4444", size=8, symbol="x"),
                hovertemplate="<b>%{x}</b><br>Stockout: 0 units<extra></extra>",
            ))

    return _apply_dark(fig, "What-If Scenario — Baseline vs Adjusted")


def mape_heatmap(metrics: dict) -> go.Figure:
    """Heatmap of MAE across categories × models."""
    categories = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
    models = ["prophet", "arima", "sarima", "lightgbm", "lstm"]

    z = []
    for cat in categories:
        row = []
        cat_data = metrics.get(cat, {})
        for m in models:
            m_data = cat_data.get(m, {})
            v = m_data.get("MAE")
            row.append(float(v) if v is not None else None)
        z.append(row)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[m.upper() for m in models],
        y=categories,
        colorscale=[
            [0.0,  "#00FF88"],
            [0.35, "#FFD700"],
            [0.7,  "#FF6B35"],
            [1.0,  "#FF4444"],
        ],
        text=[[f"{v:.2f}" if v is not None else "N/A" for v in row] for row in z],
        texttemplate="%{text}",
        hovertemplate="<b>%{y}</b> · <b>%{x}</b><br>MAE: %{z:.2f}<extra></extra>",
        showscale=True,
        colorbar=dict(
            title=dict(text="MAE (units)", font=dict(color="#F5F5F5")),
            tickfont=dict(color="#F5F5F5"),
        ),
    ))
    return _apply_dark(fig, "MAE Heatmap — All Categories × Models")


def model_bar_chart(metrics: dict) -> go.Figure:
    """Average MAE per model across all categories."""
    categories = ["M01AB", "M01AE", "N02BA", "N02BE", "N05B", "N05C", "R03", "R06"]
    models = ["prophet", "arima", "sarima", "lightgbm", "lstm"]

    avg_maes = []
    for m in models:
        vals = []
        for cat in categories:
            cat_data = metrics.get(cat, {})
            m_data = cat_data.get(m, {})
            v = m_data.get("MAE")
            if v is not None:
                vals.append(float(v))
        avg_maes.append(round(sum(vals) / len(vals), 2) if vals else 0)

    fig = go.Figure(go.Bar(
        x=[m.upper() for m in models],
        y=avg_maes,
        marker=dict(
            color=[MODEL_COLORS.get(m, "#B0B5C0") for m in models],
            line=dict(color="rgba(255,255,255,0.1)", width=1),
        ),
        text=[f"{v:.2f}" for v in avg_maes],
        textposition="outside",
        textfont=dict(color="#F5F5F5"),
        hovertemplate="<b>%{x}</b><br>Avg MAE: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(yaxis_title="Average MAE (units)")
    return _apply_dark(fig, "Average MAE by Model (All 8 Categories)")


def severity_donut(results: list[dict]) -> go.Figure:
    """Donut chart of anomaly severity distribution."""
    counts = {"normal": 0, "moderate": 0, "anomaly-medium": 0, "anomaly-high": 0}
    for r in results:
        s, sev = r.get("status", ""), r.get("severity", "")
        if s == "normal":
            counts["normal"] += 1
        elif s == "moderate":
            counts["moderate"] += 1
        elif s == "anomaly" and sev == "medium":
            counts["anomaly-medium"] += 1
        elif s == "anomaly" and sev == "high":
            counts["anomaly-high"] += 1

    labels = list(counts.keys())
    values = list(counts.values())
    colors = ["#00FF88", "#FFD700", "#FF6B35", "#FF4444"]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="rgba(15,20,25,0.8)", width=2)),
        textinfo="percent+label",
        textfont=dict(color="#F5F5F5", size=11),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(showlegend=False)
    return _apply_dark(fig, "Severity Distribution")
