"""Shared helpers for the Streamlit frontend: API client, state, styling."""

from __future__ import annotations

import os

import httpx
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

DISCLAIMER_VI = (
    "⚠️ **Lưu ý quan trọng:** Đây là công cụ sàng lọc và tự nhìn nhận, **không phải công cụ "
    "chẩn đoán y khoa**. Kết quả chỉ mang tính tham khảo. Nếu bạn cảm thấy quá tải hoặc các "
    "dấu hiệu kéo dài, hãy tìm đến chuyên gia tâm lý hoặc cơ sở y tế."
)

# Status colors (validated palette): level is always shown WITH its text label,
# never by color alone.
LEVEL_COLORS = {
    "Low": "#0ca30c",
    "Moderate": "#fab219",
    "High": "#ec835a",
    "Severe": "#d03b3b",
}

LEVEL_LABELS_VI = {
    "Low": "Thấp",
    "Moderate": "Trung bình",
    "High": "Cao",
    "Severe": "Rất cao",
}

DASS_SEVERITY_VI = {
    "Normal": "Bình thường",
    "Mild": "Nhẹ",
    "Moderate": "Vừa",
    "Severe": "Nặng",
    "Extremely Severe": "Rất nặng",
}

PSS_CATEGORY_VI = {"Low": "Thấp", "Moderate": "Trung bình", "High": "Cao"}


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
    """Stop rendering the page unless the user has consented on the home page."""
    init_state()
    if not st.session_state.consented:
        st.warning("Vui lòng đọc và đồng ý tham gia ở trang **Trang chủ** trước khi tiếp tục.")
        st.page_link("Trang_Chu.py", label="👉 Về Trang chủ", icon="🏠")
        st.stop()


def api_post(path: str, payload: dict, timeout: float = 120.0) -> dict | None:
    """POST to the FastAPI backend; render a friendly error and return None on failure."""
    try:
        response = httpx.post(f"{API_BASE_URL}{path}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error(
            "Không kết nối được máy chủ phân tích. Hãy chắc chắn backend FastAPI đang chạy "
            f"tại `{API_BASE_URL}` (lệnh: `uvicorn app.api.main:app`)."
        )
    except httpx.HTTPStatusError as exc:
        st.error(f"Máy chủ trả về lỗi {exc.response.status_code}: {exc.response.text[:300]}")
    except httpx.HTTPError as exc:
        st.error(f"Lỗi khi gọi máy chủ: {exc}")
    return None


def api_get(path: str, timeout: float = 30.0) -> dict | None:
    try:
        response = httpx.get(f"{API_BASE_URL}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error(
            "Không kết nối được máy chủ phân tích. Hãy chắc chắn backend FastAPI đang chạy "
            f"tại `{API_BASE_URL}`."
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        st.error(f"Máy chủ trả về lỗi {exc.response.status_code}.")
    except httpx.HTTPError as exc:
        st.error(f"Lỗi khi gọi máy chủ: {exc}")
    return None


def show_disclaimer() -> None:
    st.info(DISCLAIMER_VI)


def show_crisis(message_vi: str) -> None:
    """Render the crisis helpline block prominently."""
    st.error(message_vi)
