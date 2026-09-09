"""Shared helpers for the Streamlit frontend: API client, state, styling."""

from __future__ import annotations

import os

import httpx
import streamlit as st
from ui import tokens as T
from ui.icons import icon

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

DISCLAIMER = (
    "⚠️ **Important:** This is a screening and self-reflection tool, **not a medical "
    "diagnostic instrument**. Results are indicative only. If you feel overwhelmed, or "
    "the signs persist, please reach out to a mental-health professional or a medical "
    "facility."
)

# Status colors: re-exported from the design tokens so charts and DOM share one
# palette. Level is always shown WITH its text label, never by color alone.
LEVEL_COLORS = T.LEVEL_COLORS
LEVEL_INK = T.LEVEL_INK
LEVEL_TINT = T.LEVEL_TINT

# Display labels. Kept as lookup maps (rather than inlined) so charts and pages
# share one wording, and so a future locale only has to change this file.
# "Severe" is shown as "Very high" on purpose: the UI describes stress levels,
# it does not hand out clinical severity verdicts.
LEVEL_LABELS = {
    "Low": "Low",
    "Moderate": "Moderate",
    "High": "High",
    "Severe": "Very high",
}

DASS_SEVERITY_LABELS = {
    "Normal": "Normal",
    "Mild": "Mild",
    "Moderate": "Moderate",
    "Severe": "Severe",
    "Extremely Severe": "Extremely severe",
}

PSS_CATEGORY_LABELS = {"Low": "Low", "Moderate": "Moderate", "High": "High"}


def init_state() -> None:
    """Ensure all session-state keys exist."""
    defaults = {
        "consented": False,
        "student_id": None,
        "profile": {},
        "raw_text": "",
        "dass_answers": {},
        "pss_answers": {},
        "stress_context": {},
        "last_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def require_consent() -> None:
    """Stop rendering the page unless the user has consented on the home page.

    Gate only — the consent rule itself is unchanged; this just presents it as a
    friendly redirect rather than a warning banner.
    """
    init_state()
    if not st.session_state.consented:
        st.markdown(
            '<div class="pt-empty" style="margin-top:2rem">'
            f'<div class="ico">{icon("lock", 26)}</div>'
            "<h4>Let's start from the Home page</h4>"
            "<p>You need to read and agree to take part before moving on to the next "
            "steps. It only takes about 30 seconds.</p></div>",
            unsafe_allow_html=True,
        )
        st.page_link("Home.py", label="Back to Home", icon=":material/home:")
        st.stop()


def api_post(path: str, payload: dict, timeout: float = 120.0) -> dict | None:
    """POST to the FastAPI backend; render a friendly error and return None on failure."""
    try:
        response = httpx.post(f"{API_BASE_URL}{path}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error(
            "Could not reach the analysis server. Make sure the FastAPI backend is "
            f"running at `{API_BASE_URL}` (command: `uvicorn app.api.main:app`)."
        )
    except httpx.HTTPStatusError as exc:
        st.error(f"The server returned error {exc.response.status_code}: {exc.response.text[:300]}")
    except httpx.HTTPError as exc:
        st.error(f"Error calling the server: {exc}")
    return None


def api_get(path: str, timeout: float = 30.0) -> dict | None:
    try:
        response = httpx.get(f"{API_BASE_URL}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error(
            "Could not reach the analysis server. Make sure the FastAPI backend is "
            f"running at `{API_BASE_URL}`."
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        st.error(f"The server returned error {exc.response.status_code}.")
    except httpx.HTTPError as exc:
        st.error(f"Error calling the server: {exc}")
    return None


def api_delete(path: str, timeout: float = 30.0) -> dict | None:
    """DELETE against the backend. Returns None on 404 or any failure."""
    try:
        response = httpx.delete(f"{API_BASE_URL}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error(
            "Could not reach the analysis server. Make sure the FastAPI backend is "
            f"running at `{API_BASE_URL}`."
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        st.error(f"The server returned error {exc.response.status_code}.")
    except httpx.HTTPError as exc:
        st.error(f"Error calling the server: {exc}")
    return None


def show_disclaimer() -> None:
    st.info(DISCLAIMER)


def show_crisis(message: str) -> None:
    """Render the crisis helpline block prominently.

    Deliberately the one place that breaks the calm-pastel language: it needs to
    be unmissable. Still warm rather than alarming — a hand extended, not a
    hazard sign.

    Uses a keyed `st.container` rather than a raw <div>: Streamlit renders each
    st.markdown call into its own DOM block, so a div opened in one call cannot
    wrap the next one — it closes immediately and the helplines fall outside the
    card. The message text comes from the backend and is rendered as Markdown so
    its helpline formatting survives.
    """
    with st.container(border=True, key="ptcrisis"):
        st.markdown(
            '<div class="pt-crisis-head">'
            f'{icon("life-buoy", 22)}<span>You are not alone</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(message)
