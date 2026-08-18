"""
⚙️  Settings
=============
Configure backend API URL, check connectivity, view system info,
and clear cached data.
"""
from __future__ import annotations

import streamlit as st
import datetime

from utils.styles import inject_css, page_header, section_title, kpi_card
from utils.api_client import check_health, get_models, get_metrics

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


def render():
    inject_css()
    is_connected = check_health()
    page_header(
        "⚙️ Settings & System Info",
        "Configure dashboard settings and manage data cache",
        connected=is_connected,
    )

    # ── API Configuration ─────────────────────────────────────────────────────
    section_title("🔌", "API Configuration")

    current_url = st.session_state.get("api_base_url", "http://localhost:8000")
    new_url = st.text_input(
        "Backend API URL",
        value=current_url,
        help="The base URL of the FastAPI backend (no trailing slash)",
    )
    if st.button("💾 Save & Reconnect", type="primary"):
        st.session_state["api_base_url"] = new_url
        st.cache_data.clear()
        st.success(f"✅ API URL updated to **{new_url}**. Cache cleared.")
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Cache Management ──────────────────────────────────────────────────────
    section_title("🗄️", "Cache Management")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Clear All Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("✅ All cached data cleared. Next page load will fetch fresh data.")
    with c2:
        st.markdown("""
        <div style="background:rgba(26,31,46,0.8); border:1px solid #2A2F3E; border-radius:10px;
                    padding:1rem; font-size:0.82rem; color:#B0B5C0;">
            📌 Cache TTL: Forecasts = 5 min · Metrics = 30 min · Models = 1 hr
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── System Information ────────────────────────────────────────────────────
    section_title("📋", "System Information")

    if is_connected:
        models_data = get_models()
        metrics     = get_metrics()

        available_models = models_data.get("models", []) if models_data else []
        available_cats   = models_data.get("categories", []) if models_data else []

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("🤖", "Available Models", str(len(available_models)), accent="#00D9FF")
        with c2: kpi_card("📦", "Loaded Categories", str(len(available_cats)), accent="#00FF88")
        with c3: kpi_card("🗂️", "Drug Categories", "8", accent="#FFD700")
        with c4: kpi_card("📅", "Cache Time", datetime.datetime.now().strftime("%H:%M:%S"), accent="#B0B5C0")

        if available_models:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Loaded Models:**  " +
                        "  ".join(f"`{m.upper()}`" for m in available_models))

        if available_cats:
            st.markdown("**Loaded Categories:**  " +
                        "  ".join(f"`{c}`" for c in available_cats))
    else:
        st.warning("⚠️ Backend offline. Start the server with `uvicorn main:app --reload` "
                   "and try again.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Start Server Instructions ─────────────────────────────────────────────
    section_title("🚀", "How to Start the Backend")
    st.code("""
# Navigate to the project root
cd c:\\Users\\agnes\\Desktop\\Remo\\Project\\Sales_Forecasting\\Sales_Analysis_Forecasting

# Start the FastAPI backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
""", language="bash")

    section_title("🖥️", "How to Run This Dashboard")
    st.code("""
# In a separate terminal
streamlit run app.py
""", language="bash")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Category Reference ────────────────────────────────────────────────────
    section_title("📚", "Drug Category Reference")
    import pandas as pd
    cat_df = pd.DataFrame([
        {"Code": k, "Category Name": v} for k, v in CAT_NAMES.items()
    ])
    st.dataframe(cat_df, use_container_width=True, hide_index=True)

    # ── About ─────────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background:rgba(26,31,46,0.8); border:1px solid #2A2F3E; border-radius:12px;
                padding:1.5rem; color:#B0B5C0; font-size:0.85rem; line-height:1.8;">
        <strong style="color:#F5F5F5;">💊 PharmaForecast Analytics v1.0</strong><br>
        Pharmaceutical Sales Forecasting & Analytics Dashboard<br>
        <strong>Models:</strong> Prophet · ARIMA · SARIMA · LightGBM · LSTM<br>
        <strong>Drug Categories:</strong> 8 ATC-coded pharmaceutical categories<br>
        <strong>Features:</strong> Forecasting · Anomaly Detection · What-If Analysis · Recommendations
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    render()
