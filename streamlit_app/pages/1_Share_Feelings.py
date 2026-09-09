"""Free-text entry: the student's own words about their week.

The mood chips are writing prompts, not data: picking one can seed an opening
sentence into the box, which the student then edits or deletes. Only the final
text is ever saved or sent — the mood itself is not part of the payload.
"""

import streamlit as st

from ui.components import (
    app_footer,
    callout,
    page_header,
    section_title,
    spacer,
)
from ui.nav import render_sidebar
from ui.theme import configure_page
from utils import require_consent

configure_page("Share how you feel", "💬")
require_consent()
render_sidebar("journal")

page_header(
    "What would you like to share today?",
    subtitle="Write freely for a few lines about **your past week** — study, sleep, "
    "how you felt, what worried you or made you happy. The more honest, the closer "
    "the result will be to you.",
    icon_name="message-circle",
    eyebrow="Step 1",
)

# Mood -> a gentle opener the student can build on.
MOOD_STARTERS = {
    "😊 Pretty good": "This week went pretty well for me. What made me happiest was ",
    "😌 Calm": "This week felt fairly calm. I ",
    "😐 So-so": "This week was fairly ordinary for me. Mostly I ",
    "😔 A bit tired": "This week I felt a bit worn out. What drained me most was ",
    "😣 Overwhelmed": "This week I felt overwhelmed. I have been having to ",
}

if "journal_text" not in st.session_state:
    st.session_state.journal_text = st.session_state.raw_text

section_title("How have you felt overall this week?", "heart", hint="Optional")
mood = st.pills("Mood", list(MOOD_STARTERS), key="mood", label_visibility="collapsed")

if mood:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("Use this opening line", use_container_width=True):
            st.session_state.journal_text = MOOD_STARTERS[mood]
            st.rerun()
    with col_b:
        st.caption(f"Suggestion: *“{MOOD_STARTERS[mood]}...”*")

spacer(8)
st.text_area(
    "How you feel",
    height=240,
    max_chars=4000,
    placeholder="This week I...",
    label_visibility="collapsed",
    key="journal_text",
)

text = st.session_state.journal_text
col1, col2 = st.columns([1, 2])
with col1:
    saved = st.button("Save", type="primary", use_container_width=True)
with col2:
    if text:
        st.caption(f"{len(text)} / 4000 characters")

if saved:
    st.session_state.raw_text = text.strip()
    if st.session_state.raw_text:
        callout("success", "Saved. You can move on to the DASS-21 questionnaire.")
    else:
        callout("info", "You can leave this blank and just take the questionnaires.")

spacer(12)
st.page_link(
    "pages/2_DASS_21.py",
    label="Continue: DASS-21 questionnaire",
    icon=":material/arrow_forward:",
)

app_footer()
