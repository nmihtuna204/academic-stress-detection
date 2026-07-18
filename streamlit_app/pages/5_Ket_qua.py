"""Results page: gauge, subscale bars, LLM explanation and suggestions."""

import plotly.graph_objects as go
import streamlit as st

from utils import (
    DASS_SEVERITY_VI,
    LEVEL_COLORS,
    LEVEL_LABELS_VI,
    PSS_CATEGORY_VI,
    api_post,
    require_consent,
    show_crisis,
    show_disclaimer,
)

st.set_page_config(page_title="Kết quả", page_icon="📊", layout="wide")
require_consent()

st.title("📊 Kết quả đánh giá")

LEVEL_ORDER = ["Low", "Moderate", "High", "Severe"]

# DASS severity -> status color (paired with its text label everywhere).
DASS_SEVERITY_COLORS = {
    "Normal": "#0ca30c",
    "Mild": "#fab219",
    "Moderate": "#fab219",
    "Severe": "#ec835a",
    "Extremely Severe": "#d03b3b",
}


def build_payload() -> dict | None:
    """Assemble the /assess/full payload from everything saved in the session."""
    has_text = bool(st.session_state.raw_text)
    has_dass = len(st.session_state.dass_answers) == 21
    has_pss = len(st.session_state.pss_answers) == 10
    if not (has_text or has_dass or has_pss):
        return None
    payload: dict = {"student_id": st.session_state.student_id}
    profile = {k: v for k, v in st.session_state.profile.items() if v is not None}
    if profile:
        payload["user"] = profile
    if has_text:
        payload["raw_text"] = st.session_state.raw_text
    if has_dass:
        payload["dass21"] = {"answers": {str(k): v for k, v in st.session_state.dass_answers.items()}}
    if has_pss:
        payload["pss10"] = {"answers": {str(k): v for k, v in st.session_state.pss_answers.items()}}
    if st.session_state.stress_context:
        payload["stress_context"] = {
            k: v for k, v in st.session_state.stress_context.items() if v is not None
        }
    return payload


def gauge_chart(level: str, confidence: float | None) -> go.Figure:
    """Meter for the unified stress level; label carries meaning, color reinforces."""
    value = LEVEL_ORDER.index(level) + 0.5
    fig = go.Figure(
        go.Indicator(
            mode="gauge",
            value=value,
            gauge={
                "axis": {
                    "range": [0, 4],
                    "tickvals": [0.5, 1.5, 2.5, 3.5],
                    "ticktext": [LEVEL_LABELS_VI[lv] for lv in LEVEL_ORDER],
                    "tickfont": {"size": 14},
                },
                "bar": {"color": "rgba(0,0,0,0)"},
                "steps": [
                    {"range": [i, i + 1], "color": LEVEL_COLORS[lv] + "55"}
                    for i, lv in enumerate(LEVEL_ORDER)
                ],
                "threshold": {
                    "line": {"color": LEVEL_COLORS[level], "width": 6},
                    "thickness": 0.9,
                    "value": value,
                },
            },
        )
    )
    subtitle = f"Độ tin cậy: {confidence:.0%}" if confidence is not None else ""
    fig.update_layout(
        height=280,
        margin=dict(t=30, b=10, l=30, r=30),
        annotations=[
            dict(
                text=f"<b>{LEVEL_LABELS_VI[level]}</b><br><span style='font-size:13px'>{subtitle}</span>",
                x=0.5, y=0.08, showarrow=False, font=dict(size=26, color=LEVEL_COLORS[level]),
            )
        ],
    )
    return fig


def dass_bar_chart(dass: dict) -> go.Figure:
    """Horizontal bars for the three DASS-21 subscales (0-42), direct-labeled."""
    rows = [
        ("Căng thẳng", dass["stress_score"], dass["stress_level_dass"]),
        ("Lo âu", dass["anxiety_score"], dass["anxiety_level"]),
        ("Trầm cảm", dass["depression_score"], dass["depression_level"]),
    ]
    fig = go.Figure(
        go.Bar(
            y=[r[0] for r in rows],
            x=[r[1] for r in rows],
            orientation="h",
            marker=dict(color=[DASS_SEVERITY_COLORS[r[2]] for r in rows], cornerradius=4),
            width=0.45,
            text=[f" {r[1]} — {DASS_SEVERITY_VI[r[2]]}" for r in rows],
            textposition="outside",
            textfont=dict(size=14),
            hovertemplate="%{y}: %{x} điểm<extra></extra>",
        )
    )
    fig.update_layout(
        height=230,
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis=dict(range=[0, 55], title="Điểm (0–42)", showgrid=True, gridcolor="rgba(128,128,128,0.15)"),
        yaxis=dict(showgrid=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


payload = build_payload()

if payload is None:
    st.warning(
        "Chưa có dữ liệu để phân tích. Hãy **nhập cảm nghĩ** hoặc hoàn thành ít nhất "
        "một bảng hỏi (DASS-21 / PSS-10) trước."
    )
    st.page_link("pages/1_Nhap_cam_nghi.py", label="Nhập cảm nghĩ", icon="📝")
    st.page_link("pages/2_DASS_21.py", label="Bảng hỏi DASS-21", icon="📋")
    st.stop()

col_run, col_info = st.columns([1, 3])
with col_run:
    run = st.button("🔍 Phân tích ngay", type="primary", use_container_width=True)
with col_info:
    parts = []
    if st.session_state.raw_text:
        parts.append("cảm nghĩ")
    if len(st.session_state.dass_answers) == 21:
        parts.append("DASS-21")
    if len(st.session_state.pss_answers) == 10:
        parts.append("PSS-10")
    if st.session_state.stress_context:
        parts.append("bối cảnh")
    st.caption("Dữ liệu sẽ phân tích: " + ", ".join(parts))

if run:
    with st.spinner("Đang phân tích... (lần đầu có thể mất tới 1 phút để nạp mô hình)"):
        result = api_post("/assess/full", payload, timeout=300.0)
    if result is not None:
        st.session_state.last_result = result
        st.session_state.student_id = result.get("student_id")

result = st.session_state.last_result
if result is None:
    st.stop()

# --- Crisis path: helplines only, nothing else. ---
if result.get("crisis_detected"):
    show_crisis(result["crisis_message_vi"])
    st.info(
        "Vì sự an toàn của bạn, hệ thống tạm không hiển thị kết quả phân tích chi tiết. "
        "Điều quan trọng nhất lúc này là bạn được hỗ trợ trực tiếp. 💙"
    )
    st.stop()

st.divider()

assessment = result.get("assessment")
questionnaire = result.get("questionnaire")
emotion = result.get("emotion")

# --- Row 1: gauge + DASS bars ---
col1, col2 = st.columns([2, 3])
with col1:
    st.subheader("Mức độ căng thẳng ước lượng")
    if assessment:
        st.plotly_chart(gauge_chart(assessment["predicted_level"], assessment.get("confidence")), use_container_width=True)
        st.caption("Ước lượng của mô hình AI dựa trên toàn bộ dữ liệu bạn cung cấp.")
    elif questionnaire:
        st.plotly_chart(gauge_chart(questionnaire["ground_truth_label"], None), use_container_width=True)
        st.caption("Tính từ điểm bảng hỏi (mô hình AI hiện không khả dụng).")

with col2:
    if questionnaire and questionnaire.get("dass21"):
        st.subheader("Điểm DASS-21 theo tiểu thang")
        st.plotly_chart(dass_bar_chart(questionnaire["dass21"]), use_container_width=True)
    if questionnaire and questionnaire.get("pss10"):
        pss = questionnaire["pss10"]
        category_vi = PSS_CATEGORY_VI[pss["pss_stress_category"]]
        st.metric(
            "PSS-10 — cảm nhận stress (0–40)",
            f"{pss['pss_total_score']} điểm",
            delta=f"Mức {category_vi}",
            delta_color="off",
        )

# --- Row 2: emotion analysis of the text ---
if emotion:
    with st.expander("🔬 Phân tích văn bản của bạn (mô hình PhoBERT)", expanded=False):
        col3, col4 = st.columns(2)
        with col3:
            st.markdown(f"- **Chiều hướng cảm xúc:** {emotion['sentiment_polarity']}")
            if emotion.get("model_stress_level"):
                st.markdown(
                    f"- **Mức stress theo mô hình:** {LEVEL_LABELS_VI.get(emotion['model_stress_level'], emotion['model_stress_level'])}"
                )
        with col4:
            if emotion.get("stress_keywords"):
                st.markdown("**Từ khóa căng thẳng phát hiện được:**")
                st.markdown(" ".join(f"`{kw}`" for kw in emotion["stress_keywords"]))

# --- Row 3: LLM explanation + suggestions ---
if assessment:
    st.subheader("💬 Giải thích")
    st.markdown(assessment["reasoning_vi"])

    st.subheader("🌱 Gợi ý dành cho bạn")
    for i, suggestion in enumerate(assessment["suggestions_vi"], start=1):
        st.markdown(f"**{i}.** {suggestion}")

    if assessment.get("risk_flags"):
        st.warning(
            "Hệ thống ghi nhận một số dấu hiệu cần lưu ý: "
            + ", ".join(f"`{flag}`" for flag in assessment["risk_flags"])
            + ". Nếu các dấu hiệu này kéo dài, bạn nên tìm đến phòng tham vấn tâm lý của trường."
        )

    if result.get("rag_sources"):
        st.caption("Nguồn tài liệu tham khảo: " + " · ".join(result["rag_sources"]))

st.divider()
show_disclaimer()
st.page_link("pages/6_Lich_su.py", label="Xem lịch sử các lần đánh giá", icon="🕘")
