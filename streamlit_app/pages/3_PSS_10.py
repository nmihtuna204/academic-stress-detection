"""PSS-10 questionnaire page (10 items, 0-4 scale, Vietnamese wording)."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.scoring.pss10 import ANSWER_CHOICES_VI, PSS10_QUESTIONS  # noqa: E402

from utils import require_consent, show_disclaimer  # noqa: E402

st.set_page_config(page_title="PSS-10", page_icon="📋", layout="wide")
require_consent()

st.title("📋 Bảng hỏi PSS-10")
st.markdown(
    "Với mỗi câu, hãy chọn tần suất phù hợp với bạn **trong 1 tháng vừa qua**."
)

OPTIONS = [f"{value} — {label}" for value, label in ANSWER_CHOICES_VI.items()]

with st.form("pss10_form"):
    answers: dict[int, int] = {}
    for question in PSS10_QUESTIONS:
        qid = question["id"]
        previous = st.session_state.pss_answers.get(qid)
        choice = st.radio(
            f"**Câu {qid}.** {question['text_vi']}",
            OPTIONS,
            index=previous if previous is not None else None,
            key=f"pss_{qid}",
        )
        if choice is not None:
            answers[qid] = OPTIONS.index(choice)
        st.divider()

    submitted = st.form_submit_button("Lưu PSS-10 💾", type="primary")

if submitted:
    if len(answers) < 10:
        st.error(f"Bạn còn {10 - len(answers)} câu chưa trả lời. Vui lòng trả lời đủ 10 câu.")
    else:
        st.session_state.pss_answers = answers
        st.success("Đã lưu PSS-10! Hãy điền thêm bối cảnh học tập của bạn.")

if len(st.session_state.pss_answers) == 10:
    st.page_link("pages/4_Boi_canh.py", label="👉 Tiếp tục: Bối cảnh & nguồn lực", icon="🎒")

show_disclaimer()
