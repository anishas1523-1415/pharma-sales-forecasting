"""
app.py  —  PharmaForecast Analytics Dashboard
===============================================
Main Streamlit entry point using st.navigation.
"""
import sys
import os

# Ensure frontend directory and project root are on the Python path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

PARENT = os.path.dirname(ROOT)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

import streamlit as st

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PharmaForecast Analytics",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "**PharmaForecast Analytics** · Pharmaceutical Sales Intelligence Platform\n\n"
                 "5 ML Models · 8 Drug Categories",
    },
)

# ── Initialise session state defaults ────────────────────────────────────────
if "api_base_url" not in st.session_state:
    st.session_state["api_base_url"] = "http://localhost:8000"

# ── Inject global CSS + sidebar branding ─────────────────────────────────────
from utils.styles import inject_css
inject_css()

# ── Sidebar Branding Logo ────────────────────────────────────────────────────
logo_path = os.path.join(ROOT, "assets", "pharma_logo.svg")
if os.path.exists(logo_path):
    st.logo(logo_path, size="large")
else:
    st.logo("assets/pharma_logo.svg", size="large")

# ── Define Navigation Pages ──────────────────────────────────────────────────
pages = [
    st.Page(os.path.join(ROOT, "pages", "1_🏠_Home.py"), title="Dashboard", icon="🏠", default=True),
    st.Page(os.path.join(ROOT, "pages", "2_📈_Forecast_Explorer.py"), title="Forecast Explorer", icon="📈"),
    st.Page(os.path.join(ROOT, "pages", "3_🚨_Anomaly_Detection.py"), title="Anomaly Detection", icon="🚨"),
    st.Page(os.path.join(ROOT, "pages", "4_🔬_WhatIf_Simulator.py"), title="What-If Simulator", icon="🔬"),
    st.Page(os.path.join(ROOT, "pages", "5_💡_Recommendations.py"), title="Recommendations", icon="💡"),
    st.Page(os.path.join(ROOT, "pages", "6_🤖_Model_Comparison.py"), title="Model Comparison", icon="🤖"),
    st.Page(os.path.join(ROOT, "pages", "7_⚙️_Settings.py"), title="Settings", icon="⚙️"),
]

pg = st.navigation(pages)
pg.run()
