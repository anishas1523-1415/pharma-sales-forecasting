"""
utils/api_client.py
====================
Centralised HTTP client for the FastAPI backend.
All API calls go through this module with retry logic,
error handling, and session-state caching.
"""

from __future__ import annotations

import time
import requests
import streamlit as st
from typing import Any, Optional

API_BASE_URL = st.session_state.get("api_base_url", "http://localhost:8000")
_MAX_RETRIES = 3
_RETRY_DELAY = 0.5   # seconds, doubles each retry


def _base_url() -> str:
    return st.session_state.get("api_base_url", "http://localhost:8000")


def _get(endpoint: str, params: dict | None = None, timeout: int = 8) -> Optional[Any]:
    url = f"{_base_url()}{endpoint}"
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError:
            return None
        except requests.exceptions.Timeout:
            if attempt == _MAX_RETRIES:
                return None
            time.sleep(_RETRY_DELAY * attempt)
        except requests.exceptions.HTTPError:
            return None
        except Exception:
            return None
    return None


def _post(endpoint: str, payload: dict, timeout: int = 10) -> Optional[Any]:
    url = f"{_base_url()}{endpoint}"
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError:
            return None
        except requests.exceptions.Timeout:
            if attempt == _MAX_RETRIES:
                return None
            time.sleep(_RETRY_DELAY * attempt)
        except requests.exceptions.HTTPError:
            return None
        except Exception:
            return None
    return None


# ── Public API functions ──────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def check_health() -> bool:
    data = _get("/health")
    return data is not None


@st.cache_data(ttl=3600, show_spinner=False)
def get_models() -> Optional[dict]:
    return _get("/models")


@st.cache_data(ttl=1800, show_spinner=False)
def get_metrics() -> Optional[dict]:
    return _get("/metrics")


@st.cache_data(ttl=300, show_spinner=False)
def get_forecast(category: str, model: str, horizon: int) -> Optional[dict]:
    return _post("/forecast", {"category": category, "model": model, "horizon": horizon})


@st.cache_data(ttl=300, show_spinner=False)
def compare_models(category: str) -> Optional[dict]:
    return _post("/compare-models", {"category": category})


@st.cache_data(ttl=300, show_spinner=False)
def detect_anomalies(category: str, model: str) -> Optional[dict]:
    return _post("/api/anomaly/detect", {"category": category, "model": model})


@st.cache_data(ttl=300, show_spinner=False)
def run_what_if(
    category: str,
    model: str,
    change_percent: float,
    disruption_start: str | None = None,
    disruption_end: str | None = None,
) -> Optional[dict]:
    payload: dict = {"category": category, "model": model, "change_percent": change_percent}
    if disruption_start:
        payload["disruption_start"] = disruption_start
    if disruption_end:
        payload["disruption_end"] = disruption_end
    return _post("/api/what-if", payload)


@st.cache_data(ttl=300, show_spinner=False)
def get_recommendations(category: str, model: str) -> Optional[dict]:
    return _post("/api/recommendations", {"category": category, "model": model})
