"""
utils/styles.py
================
Global CSS injection for the dark glassmorphism theme.
Call inject_css() once in the main app entry point.
"""
import streamlit as st


DARK_CSS = """
<style>
/* ── Google Fonts ──────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');

/* ── Root Variables ────────────────────────────── */
:root {
    --primary:        #0F1419;
    --surface:        #1A1F2E;
    --surface-light:  #232A3B;
    --border:         #2A2F3E;
    --cyan:           #00D9FF;
    --orange:         #FF6B35;
    --green:          #00FF88;
    --gold:           #FFD700;
    --red:            #FF4444;
    --text:           #F5F5F5;
    --text-muted:     #B0B5C0;
    --chart-blue:     #1E88E5;
}

/* ── Global Reset ──────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0F1419 0%, #131b26 50%, #0d1117 100%) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text) !important;
}

.block-container, [data-testid="stMainBlockContainer"] {
    padding-top: 1.5rem !important;
    padding-bottom: 1.5rem !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161c28 100%) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

[data-testid="stSidebarHeader"] {
    padding: 0.8rem 1rem 0.4rem 1rem !important;
}

/* ── Universal Button Overrides ───────────────── */
.stButton button,
div[data-testid="stButton"] button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"],
button[kind="secondary"],
button[kind="primary"] {
    background: linear-gradient(135deg, rgba(26, 31, 46, 0.95) 0%, rgba(35, 42, 59, 0.95) 100%) !important;
    color: #00D9FF !important;
    border: 1px solid rgba(0, 217, 255, 0.4) !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.02em !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    padding: 0.5rem 1.2rem !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25) !important;
}

.stButton button:hover,
div[data-testid="stButton"] button:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-primary"]:hover,
button[kind="secondary"]:hover,
button[kind="primary"]:hover {
    background: linear-gradient(135deg, #00D9FF 0%, #00FF88 100%) !important;
    color: #0F1419 !important;
    border-color: transparent !important;
    font-weight: 700 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 22px rgba(0, 217, 255, 0.45) !important;
}

.stButton button:active,
div[data-testid="stButton"] button:active {
    transform: translateY(0px) !important;
    box-shadow: 0 2px 8px rgba(0, 217, 255, 0.3) !important;
}

/* Sidebar action buttons (e.g. Clear Cache, Refresh Data) */
[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, rgba(26, 31, 46, 0.95) 0%, rgba(35, 42, 59, 0.95) 100%) !important;
    border: 1px solid rgba(0, 217, 255, 0.4) !important;
    color: #00D9FF !important;
    border-radius: 10px !important;
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    width: 100% !important;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.25) !important;
}

[data-testid="stSidebar"] .stButton button:hover,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover,
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg, #00D9FF 0%, #00FF88 100%) !important;
    color: #0F1419 !important;
    border-color: transparent !important;
    font-weight: 700 !important;
    box-shadow: 0 6px 18px rgba(0, 217, 255, 0.4) !important;
    transform: translateY(-2px) !important;
}

/* Selectbox / dropdown */
.stSelectbox div[data-baseweb="select"] > div {
    background: var(--surface) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}
.stMultiSelect div[data-baseweb="select"] > div {
    background: var(--surface) !important;
    border-color: var(--border) !important;
    border-radius: 8px !important;
}

/* Pills / Visual Segmented Control */
[data-testid="stPills"] {
    gap: 6px !important;
}
[data-testid="stPills"] button {
    background: rgba(26,31,46,0.9) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-muted) !important;
    border-radius: 8px !important;
    padding: 0.35rem 0.75rem !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
[data-testid="stPills"] button:hover {
    border-color: var(--cyan) !important;
    color: var(--text) !important;
}
[data-testid="stPills"] button[aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,217,255,0.2), rgba(0,255,136,0.1)) !important;
    border: 1px solid var(--cyan) !important;
    color: var(--cyan) !important;
    font-weight: 700 !important;
}

/* ── Universal Slider Custom Theme ─────────────────────── */
.stSlider,
[data-testid="stSlider"],
div[data-baseweb="slider"] {
    padding-top: 0.2rem !important;
    padding-bottom: 0.5rem !important;
}

/* Slider Track Fill (Cyan to Mint Green Gradient) */
div[data-baseweb="slider"] > div > div,
[data-testid="stSlider"] div[data-baseweb="slider"] > div > div {
    background: linear-gradient(90deg, #00D9FF 0%, #00FF88 100%) !important;
}

/* Slider Track Base */
div[data-baseweb="slider"] > div,
[data-testid="stSlider"] div[data-baseweb="slider"] > div {
    background: var(--surface-light) !important;
    border-radius: 6px !important;
    height: 6px !important;
}

/* Slider Thumb Handle */
div[role="slider"],
[data-testid="stSlider"] div[role="slider"] {
    background-color: #00D9FF !important;
    border: 2px solid #0F1419 !important;
    box-shadow: 0 0 12px rgba(0, 217, 255, 0.8) !important;
}

/* Slider Floating Value Tooltip Badge */
[data-testid="stThumbValue"],
.stSlider [data-testid="stThumbValue"],
[data-testid="stSlider"] [data-testid="stThumbValue"] {
    background: linear-gradient(135deg, rgba(26, 31, 46, 0.95), rgba(35, 42, 59, 0.95)) !important;
    color: #00D9FF !important;
    border: 1px solid rgba(0, 217, 255, 0.4) !important;
    border-radius: 8px !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 0.82rem !important;
    padding: 3px 8px !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4) !important;
}

/* Metrics */
[data-testid="stMetric"] {
    background: rgba(26,31,46,0.8) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
    backdrop-filter: blur(10px) !important;
}
[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 0.8rem !important; }
[data-testid="stMetricValue"] { color: var(--cyan) !important; font-family: 'Space Mono', monospace !important; }
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* DataFrame / Tables */
.stDataFrame { border-radius: 10px !important; overflow: hidden !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #00D9FF22, #00D9FF11) !important;
    color: var(--cyan) !important;
    border-bottom: 2px solid var(--cyan) !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
}

/* Input fields */
.stTextInput input, .stNumberInput input {
    background: var(--surface) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}

/* Radio buttons */
.stRadio label { color: var(--text) !important; }

/* Checkboxes */
.stCheckbox label { color: var(--text) !important; }

/* Progress bar */
.stProgress > div > div { background: var(--cyan) !important; }

/* Divider */
hr { border-color: var(--border) !important; }

/* ── Custom Components ──────────────────────────── */
.pharma-header {
    background: linear-gradient(135deg, rgba(0,217,255,0.08) 0%, rgba(255,107,53,0.05) 100%);
    border: 1px solid rgba(0,217,255,0.2);
    border-radius: 12px;
    padding: 0.8rem 1.4rem;
    margin-bottom: 0.8rem;
    position: relative;
    overflow: hidden;
}
.pharma-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #00D9FF, #FF6B35, #00FF88);
}
.pharma-header h1 {
    font-size: 1.55rem;
    font-weight: 800;
    background: linear-gradient(135deg, #00D9FF, #00FF88);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1.2;
}
.pharma-header .subtitle {
    color: var(--text-muted);
    font-size: 0.82rem;
    margin-top: 0.2rem;
}
.pharma-header .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,255,136,0.12);
    border: 1px solid rgba(0,255,136,0.3);
    color: #00FF88;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-top: 0.6rem;
}
.pharma-header .status-badge.offline {
    background: rgba(255,68,68,0.12);
    border-color: rgba(255,68,68,0.3);
    color: #FF4444;
}

.kpi-card {
    background: linear-gradient(135deg, rgba(26,31,46,0.9) 0%, rgba(35,42,59,0.9) 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.kpi-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    border-color: rgba(0,217,255,0.3);
}
.kpi-card .kpi-icon { font-size: 1.8rem; margin-bottom: 0.5rem; }
.kpi-card .kpi-label { color: var(--text-muted); font-size: 0.78rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.08em; }
.kpi-card .kpi-value { color: var(--text); font-family: 'Space Mono', monospace; font-size: 2rem; font-weight: 700; line-height: 1.1; }
.kpi-card .kpi-delta { font-size: 0.78rem; margin-top: 0.3rem; }
.kpi-card .kpi-accent { position: absolute; top: 0; left: 0; width: 4px; height: 100%; border-radius: 14px 0 0 14px; }

.cat-card {
    background: linear-gradient(135deg, rgba(26,31,46,0.95) 0%, rgba(35,42,59,0.95) 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.8rem;
    transition: all 0.25s ease;
    cursor: pointer;
    position: relative;
    overflow: hidden;
}
.cat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.35);
    border-color: rgba(0,217,255,0.25);
}
.cat-card .cat-code { font-size: 1.1rem; font-weight: 700; color: var(--cyan); font-family: 'Space Mono', monospace; }
.cat-card .cat-model { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; }

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.badge-high   { background: rgba(255,68,68,0.18);  color: #FF4444; border: 1px solid rgba(255,68,68,0.4); }
.badge-medium { background: rgba(255,215,0,0.18);  color: #FFD700; border: 1px solid rgba(255,215,0,0.4); }
.badge-low    { background: rgba(0,255,136,0.15);  color: #00FF88; border: 1px solid rgba(0,255,136,0.4); }
.badge-cyan   { background: rgba(0,217,255,0.15);  color: #00D9FF; border: 1px solid rgba(0,217,255,0.4); }

.rec-card {
    background: rgba(26,31,46,0.9);
    border-radius: 14px;
    padding: 1.3rem 1.5rem;
    margin-bottom: 1rem;
    border-left: 4px solid var(--cyan);
    border-top: 1px solid var(--border);
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    transition: all 0.25s ease;
}
.rec-card:hover { transform: translateX(4px); }
.rec-card.high { border-left-color: #FF4444; }
.rec-card.medium { border-left-color: #FFD700; }
.rec-card.low { border-left-color: #00FF88; }
.rec-card .rec-signal { font-size: 1rem; font-weight: 700; margin-bottom: 0.4rem; }
.rec-card .rec-text { color: var(--text-muted); font-size: 0.88rem; line-height: 1.5; }
.rec-card .rec-rationale { color: var(--text-muted); font-size: 0.78rem; font-style: italic; margin-top: 0.5rem; }

.alert-card {
    background: rgba(26,31,46,0.85);
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    border: 1px solid var(--border);
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
}
.alert-card .alert-icon { font-size: 1.3rem; }
.alert-card .alert-body {}
.alert-card .alert-title { font-weight: 600; font-size: 0.88rem; }
.alert-card .alert-text  { color: var(--text-muted); font-size: 0.78rem; margin-top: 2px; }

.section-header {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text);
    margin: 0.8rem 0 0.5rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.section-header::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

.offline-banner {
    background: rgba(255,68,68,0.12);
    border: 1px solid rgba(255,68,68,0.3);
    border-radius: 10px;
    padding: 0.8rem 1.2rem;
    color: #FF6B6B;
    font-size: 0.88rem;
    font-weight: 500;
    margin-bottom: 1rem;
}

.metric-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--surface-light);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 4px 12px;
    font-family: 'Space Mono', monospace;
    font-size: 0.82rem;
    color: var(--text);
}

.impact-positive { color: #00FF88; font-weight: 700; }
.impact-negative { color: #FF4444; font-weight: 700; }
.impact-neutral  { color: var(--text-muted); }

/* Scrollbar styling */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--surface); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--cyan); }
</style>
"""


def inject_css():
    st.markdown(DARK_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", connected: bool = True):
    html = f"""
    <div class="pharma-header">
        <h1>{title}</h1>
        <div class="subtitle">{subtitle}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def section_title(icon: str, title: str):
    st.markdown(f'<div class="section-header">{icon} {title}</div>', unsafe_allow_html=True)


def kpi_card(icon: str, label: str, value: str, delta: str = "", accent: str = "#00D9FF"):
    html = f"""
    <div class="kpi-card">
        <div class="kpi-accent" style="background:{accent};"></div>
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {"<div class='kpi-delta'>" + delta + "</div>" if delta else ""}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def badge(text: str, level: str = "cyan") -> str:
    return f'<span class="badge badge-{level.lower()}">{text}</span>'


def rec_card(signal: str, priority: str, text: str, rationale: str, icon: str = "📊"):
    lvl = priority.lower()
    col = {"high": "#FF4444", "medium": "#FFD700", "low": "#00FF88"}.get(lvl, "#00D9FF")
    html = f"""
    <div class="rec-card {lvl}">
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:0.5rem;">
            <span style="font-size:1.3rem;">{icon}</span>
            <span class="rec-signal">{signal}</span>
            <span class="badge badge-{lvl}" style="margin-left:auto;">{priority}</span>
        </div>
        <div class="rec-text">{text}</div>
        <div class="rec-rationale">📌 {rationale}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def offline_banner():
    st.markdown(
        '<div class="offline-banner">⚠️  Backend offline — Showing cached data only. '
        'Start the API with: <code>uvicorn main:app --reload</code></div>',
        unsafe_allow_html=True,
    )
