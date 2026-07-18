"""DASS-21 questionnaire page (21 items, 0-3 scale, Vietnamese wording)."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.scoring.dass21 import ANSWER_CHOICES_VI, DASS21_QUESTIONS  # noqa: E402

from utils import require_consent, show_disclaimer  # noqa: E402

st.set_page_config(page_title="DASS-21", page_icon="📋", layout="wide")
require_consent()

st.title("📋 Bảng hỏi DASS-21")
st.markdown(
    """
Với mỗi câu, hãy chọn mức độ phù hợp với trải nghiệm của bạn **trong 1 tuần vừa qua**.
Không có câu trả lời đúng hay sai — hãy trả lời theo cảm nhận thật của bạn.
"""
)

OPTIONS = [f"{value} — {label}" for value, label in ANSWER_CHOICES_VI.items()]

with st.form("dass21_form"):
    answers: dict[int, int] = {}
    for question in DASS21_QUESTIONS:
        qid = question["id"]
        previous = st.session_state.dass_answers.get(qid)
        choice = st.radio(
            f"**Câu {qid}.** {question['text_vi']}",
            OPTIONS,
            index=previous if previous is not None else None,
            key=f"dass_{qid}",
            horizontal=False,
        )
        if choice is not None:
            answers[qid] = OPTIONS.index(choice)
        st.divider()

    submitted = st.form_submit_button("Lưu DASS-21 💾", type="primary")

if submitted:
    if len(answers) < 21:
        missing = 21 - len(answers)
        st.error(f"Bạn còn {missing} câu chưa trả lời. Vui lòng trả lời đủ 21 câu.")
    else:
        st.session_state.dass_answers = answers
        st.success("Đã lưu DASS-21! Hãy làm tiếp bảng hỏi PSS-10.")

if len(st.session_state.dass_answers) == 21:
    st.page_link("pages/3_PSS_10.py", label="👉 Tiếp tục: Bảng hỏi PSS-10", icon="📋")

show_disclaimer()
