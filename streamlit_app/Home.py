"""Home page: welcome, what the app does, and informed consent.

Consent is required before any data entry — the rule is unchanged; only its
presentation is. Nothing here calls the API.
"""

import sys
from pathlib import Path

import streamlit as st

# Streamlit puts `streamlit_app/` on sys.path, not the project root, so the
# `app` package is unreachable without this. Same pattern as the questionnaire
# pages, which already import from `app.scoring`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ui.components import (  # noqa: E402
    app_footer,
    callout,
    feature_grid,
    hero,
    section_title,
    spacer,
)
from ui.icons import icon  # noqa: E402
from ui.nav import render_sidebar  # noqa: E402
from ui.theme import configure_page  # noqa: E402
from utils import init_state  # noqa: E402

from app.config import llm_provider_identity  # noqa: E402

configure_page("Home", "🌿")
init_state()
render_sidebar("home")

# --- Welcome -------------------------------------------------------------
hero(
    "Hello",
    "Welcome to a calm space of your own",
    "This is somewhere you can pause for a moment, look back on the past week and "
    "better understand your academic stress — with the help of AI and standardized "
    "questionnaires. No grading, no judgment.",
)

feature_grid(
    [
        ("brain", "AI-powered analysis",
         "A language model reads what you write and explains the result in plain words.",
         "primary"),
        ("clipboard-list", "Standardized questionnaires",
         "DASS-21 and PSS-10 — two scales widely used in psychological research.",
         "secondary"),
        ("lock", "Completely anonymous",
         "No name, no student ID. Each session is tied only to a random code.",
         "success"),
    ],
    min_width=250,
)

# --- How it works --------------------------------------------------------
section_title("Four steps, about 10 minutes", "leaf", hint="You can stop at any time")

feature_grid(
    [
        ("pen-line", "Share how you feel",
         "Write freely for a few lines about your past week.", "accent"),
        ("clipboard-list", "Take two questionnaires",
         "DASS-21 (21 items) and PSS-10 (10 items).", "accent"),
        ("graduation-cap", "Add your context",
         "Study schedule, sleep, sources of support.", "accent"),
        ("sparkles", "Get your results",
         "Your stress level, an explanation and 3 suggestions.", "accent"),
    ],
    min_width=200,
)

spacer(28)
callout(
    "info",
    "This is a **screening and self-reflection tool**, not a medical diagnosis. "
    "If you are going through a really hard time, please reach out to a mental-health "
    "professional or your university counselling office.",
)

# --- Consent -------------------------------------------------------------
section_title("Consent to take part", "shield-check")

# These points must not promise less than docs/consent_form_vi.md does. In
# particular §4 (third-party processing), §5 (retention) and §6 (withdrawal)
# have to be visible here, because this screen is the only thing a participant
# actually reads before disclosing anything.
# Resolved from the ACTUAL configured provider, not hardcoded - this stayed
# wrong for weeks the last time it was hardcoded and the provider changed.
_LLM_PROVIDER, _LLM_JURISDICTION = llm_provider_identity()

_CONSENT_POINTS = [
    "I am 18 or older and a university or college student.",
    "I understand this is a screening tool, not a medical diagnosis.",
    "I understand that what I write is sent, without any identifying information, "
    f"to a language-model service ({_LLM_PROVIDER}, based in {_LLM_JURISDICTION}) "
    "to be analysed.",
    "I understand my data is stored under a random anonymous code, kept for at most "
    "12 months after the project is defended, and then permanently deleted.",
    "I understand I can stop at any time, and can erase everything I have submitted "
    "from the History page using my anonymous code.",
    "I take part voluntarily and agree to anonymous data being stored for research.",
]

with st.form("consent_form"):
    st.markdown(
        '<ul class="pt-consent-list">'
        + "".join(f"<li>{icon('check', 17)}<span>{p}</span></li>" for p in _CONSENT_POINTS)
        + "</ul>",
        unsafe_allow_html=True,
    )

    agreed = st.checkbox("I have read and **agree** to the points above.")

    st.markdown(
        '<p style="font-size:.85rem;color:var(--muted);margin:1.2rem 0 .4rem;'
        'font-weight:550">Background information — optional, for statistics only</p>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        age = st.number_input("Age", min_value=15, max_value=80, value=20)
        gender = st.selectbox(
            "Gender", ["Male", "Female", "Other"], index=None, placeholder="Select..."
        )
    with col2:
        year = st.selectbox("Year of study", [1, 2, 3, 4, 5, 6], index=None, placeholder="Select...")
        major = st.text_input("Major", placeholder="e.g. Information Technology")
    with col3:
        university = st.text_input("University", placeholder="e.g. Bach Khoa University")

    spacer(8)
    submitted = st.form_submit_button("Start the journey", type="primary")

if submitted:
    if not agreed:
        callout("warning", "Please tick the consent box to continue.")
    else:
        st.session_state.consented = True
        st.session_state.profile = {
            "age": int(age),
            "gender": gender,
            "year_of_study": int(year) if year else None,
            "major": major or None,
            "university": university or None,
        }
        callout("success", "Thank you! Move on to **Share how you feel** to begin.")

if st.session_state.consented:
    st.page_link(
        "pages/1_Share_Feelings.py",
        label="Continue: Share how you feel",
        icon=":material/arrow_forward:",
    )

app_footer()
