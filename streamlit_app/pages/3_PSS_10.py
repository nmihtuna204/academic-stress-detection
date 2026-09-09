"""PSS-10 questionnaire (10 items, 0-4 scale).

Same presentation approach as the DASS-21 page: no `st.form`, so the progress
counter tracks the student live. Scale and validation are unchanged.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.scoring.pss10 import ANSWER_CHOICES, PSS10_QUESTIONS  # noqa: E402

from ui.components import (  # noqa: E402
    app_footer,
    callout,
    page_header,
    progress_bar,
    question_card,
    spacer,
)
from ui.nav import render_sidebar  # noqa: E402
from ui.theme import configure_page  # noqa: E402
from utils import require_consent  # noqa: E402

configure_page("PSS-10", "📊")
require_consent()
render_sidebar("pss")

TOTAL = len(PSS10_QUESTIONS)
OPTIONS = [f"{value} — {label}" for value, label in ANSWER_CHOICES.items()]

page_header(
    "PSS-10 questionnaire",
    subtitle="For each question, choose how often it applied to you **over the past month**.",
    icon_name="chart-bar",
    eyebrow="Step 3",
)

for question in PSS10_QUESTIONS:
    key = f"pss_{question['id']}"
    if key not in st.session_state:
        previous = st.session_state.pss_answers.get(question["id"])
        st.session_state[key] = OPTIONS[previous] if previous is not None else None

answered = sum(1 for q in PSS10_QUESTIONS if st.session_state.get(f"pss_{q['id']}") is not None)
progress_bar(answered, TOTAL)

for question in PSS10_QUESTIONS:
    qid = question["id"]
    with question_card(qid, question["text"]):
        st.radio(
            f"Question {qid}",
            OPTIONS,
            key=f"pss_{qid}",
            label_visibility="collapsed",
        )

st.session_state.pss_answers = {
    q["id"]: OPTIONS.index(st.session_state[f"pss_{q['id']}"])
    for q in PSS10_QUESTIONS
    if st.session_state.get(f"pss_{q['id']}") is not None
}

spacer(12)
if answered < TOTAL:
    callout("info", f"You still have **{TOTAL - answered} items** to answer.")
else:
    callout("success", "PSS-10 done. Now tell us a little about your academic context.")
    st.page_link(
        "pages/4_Context.py",
        label="Continue: Academic context",
        icon=":material/arrow_forward:",
    )

app_footer()
