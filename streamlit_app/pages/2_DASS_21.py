"""DASS-21 questionnaire (21 items, 0-3 scale).

Questions, scale and validation are unchanged — this file only governs how they
are presented. The page deliberately does NOT use `st.form`: a form defers every
rerun until submit, which would freeze the progress counter at 0/21 while the
student works. Answers auto-save to session_state on each interaction instead.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.scoring.dass21 import ANSWER_CHOICES, DASS21_QUESTIONS  # noqa: E402

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

configure_page("DASS-21", "📋")
require_consent()
render_sidebar("dass")

TOTAL = len(DASS21_QUESTIONS)
OPTIONS = [f"{value} — {label}" for value, label in ANSWER_CHOICES.items()]

page_header(
    "DASS-21 questionnaire",
    subtitle="For each statement, choose how much it applied to you **over the past "
    "week**. There are no right or wrong answers — just answer as you truly felt.",
    icon_name="clipboard-list",
    eyebrow="Step 2",
)

# Seed widget state from any previously saved answers so navigating away and
# back does not wipe the student's progress.
for question in DASS21_QUESTIONS:
    key = f"dass_{question['id']}"
    if key not in st.session_state:
        previous = st.session_state.dass_answers.get(question["id"])
        st.session_state[key] = OPTIONS[previous] if previous is not None else None

answered = sum(1 for q in DASS21_QUESTIONS if st.session_state.get(f"dass_{q['id']}") is not None)
progress_bar(answered, TOTAL)

for question in DASS21_QUESTIONS:
    qid = question["id"]
    with question_card(qid, question["text"]):
        st.radio(
            f"Question {qid}",
            OPTIONS,
            key=f"dass_{qid}",
            label_visibility="collapsed",
        )

# Auto-save: mirror widget state into the canonical answers dict every run.
st.session_state.dass_answers = {
    q["id"]: OPTIONS.index(st.session_state[f"dass_{q['id']}"])
    for q in DASS21_QUESTIONS
    if st.session_state.get(f"dass_{q['id']}") is not None
}

spacer(12)
if answered < TOTAL:
    callout("info", f"You still have **{TOTAL - answered} items** to answer. Take your time.")
else:
    callout("success", "You have completed the DASS-21. Next up is the PSS-10.")
    st.page_link(
        "pages/3_PSS_10.py",
        label="Continue: PSS-10 questionnaire",
        icon=":material/arrow_forward:",
    )

app_footer()
