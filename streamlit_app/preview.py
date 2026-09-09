"""Design-system gallery — every component rendered with sample data.

Not part of the app: it lives outside `pages/`, so Streamlit never adds it to
the navigation. Run it on its own port to review the visual language, or to
check components whose real data needs a live LLM key:

    streamlit run streamlit_app/preview.py --server.port 8502

Sample data only. No API calls, no session state, no scoring.
"""

import streamlit as st
from ui.charts import dass_bar_chart, gauge_chart, radar_chart, trend_chart
from ui.components import (
    callout,
    card,
    chips,
    empty_state,
    factor_list,
    feature_grid,
    hero,
    level_badge,
    page_header,
    progress_bar,
    question_card,
    recommendation_grid,
    result_hero,
    section_title,
    spacer,
    stat_grid,
    timeline,
    timeline_item,
)
from ui.theme import configure_page

configure_page("Design system", "🎨")

LEVEL_LABELS = {"Low": "Low", "Moderate": "Moderate", "High": "High", "Severe": "Very high"}
DASS_SEVERITY_LABELS = {
    "Normal": "Normal", "Mild": "Mild", "Moderate": "Moderate",
    "Severe": "Severe", "Extremely Severe": "Extremely severe",
}

page_header(
    "Design system",
    subtitle="Every interface component with sample data — used for visual checks.",
    icon_name="sparkles",
    eyebrow="Preview",
)

# --- Hero -----------------------------------------------------------------
section_title("Hero", "heart")
hero("Hello", "Welcome headline goes here", "A short, warm and readable description.")

# --- Cards ----------------------------------------------------------------
section_title("Feature cards", "book-open")
feature_grid(
    [(ico, f"{tone.capitalize()} card",
      "A short description for this card, just long enough to wrap and check that "
      "the heights stay even.",
      tone)
     for ico, tone in [("brain", "primary"), ("clipboard-list", "secondary"),
                       ("lock", "success"), ("leaf", "accent")]],
    min_width=200,
)

# --- Callouts -------------------------------------------------------------
section_title("Callouts", "info")
for kind in ("info", "success", "warning", "danger"):
    callout(kind, f"This is a **{kind}** callout with a sentence long enough to show the rhythm.")
callout("warning", "⚠️ A string with a leading emoji — the component must strip it, not show 2 icons.")

# --- Stats ----------------------------------------------------------------
section_title("Stat tiles", "chart-bar")
stat_grid([
    ("Assessments taken", "5", "vs. last time", "accent"),
    ("PSS-10 score", "24 points", "vs. last time", "warning"),
    ("Most recent level", "Moderate", None, "success"),
    ("Questionnaires", "3", None, "neutral"),
])

# --- Progress + question --------------------------------------------------
section_title("Progress & question card", "clipboard-list")
progress_bar(13, 21)
with question_card(7, "I found it hard to wind down"):
    st.radio("q", ["0 — Did not apply", "1 — Sometimes", "2 — Often", "3 — Most of the time"],
             key="preview_q", label_visibility="collapsed")

# --- Result heroes (all four levels) --------------------------------------
section_title("Result hero — all four levels", "sparkles")
SAMPLES = {
    "Low": ("Overall you seem to be holding a good balance",
            "Your stress is at a mild level. Keep up the habits that are working for you."),
    "Moderate": ("It looks like you are carrying some academic pressure",
                 "Quite common for students during busy periods. This is **not a medical diagnosis**."),
    "High": ("You have been under a fair amount of pressure lately",
             "Your body and mind may genuinely need rest."),
    "Severe": ("It looks like you are holding a great deal right now",
               "You deserve support. Reaching out to a professional is a strong choice."),
}
for lv, (head, body) in SAMPLES.items():
    result_hero(lv, LEVEL_LABELS[lv], head, body)

# --- Factors --------------------------------------------------------------
section_title("Risk & protective factors", "shield-check")
c = st.columns(2, gap="medium")
with c[0]:
    with card("prev-risk"):
        st.markdown("**Worth watching**")
        factor_list(["Severe sleep deprivation", "Academic overload", "Financial pressure"], "risk")
with c[1]:
    with card("prev-protect"):
        st.markdown("**Your strengths**")
        factor_list(["Getting enough sleep", "Supportive family", "Knows where to find support"],
                    "protect")

# --- Recommendations ------------------------------------------------------
section_title("Recommendation cards", "leaf")
recommendation_grid([
    ("leaf", "Suggestion 1", "Take a full 15-minute break between study sessions, screen-free."),
    ("wind", "Suggestion 2", "Try the 4-7-8 breathing exercise for 2 minutes before bed."),
    ("calendar-check", "Suggestion 3", "Split the project into small milestones with their own deadlines."),
])

# --- Charts ---------------------------------------------------------------
section_title("Charts", "trending-up")
c = st.columns(2, gap="medium")
with c[0]:
    with card("prev-gauge"):
        st.plotly_chart(gauge_chart("High", 0.78, LEVEL_LABELS),
                        use_container_width=True, config={"displayModeBar": False})
with c[1]:
    with card("prev-bars"):
        st.plotly_chart(
            dass_bar_chart(
                {"stress_score": 22, "anxiety_score": 16, "depression_score": 10,
                 "stress_level_dass": "Severe", "anxiety_level": "Moderate",
                 "depression_level": "Mild"},
                DASS_SEVERITY_LABELS,
            ),
            use_container_width=True, config={"displayModeBar": False},
        )

c = st.columns(2, gap="medium")
with c[0]:
    with card("prev-radar"):
        st.plotly_chart(
            radar_chart([("Stress", 72), ("Anxiety", 55), ("Depression", 34),
                         ("Perceived stress", 61)]),
            use_container_width=True, config={"displayModeBar": False},
        )
with c[1]:
    with card("prev-trend"):
        st.plotly_chart(
            trend_chart(
                [("01-06 09:00", "Low"), ("08-06 09:00", "Moderate"),
                 ("15-06 09:00", "High"), ("22-06 09:00", "Moderate")],
                LEVEL_LABELS,
            ),
            use_container_width=True, config={"displayModeBar": False},
        )

# --- Timeline -------------------------------------------------------------
section_title("Timeline", "clock")
with timeline():
    for t, lv in [("22-06 09:00", "Moderate"), ("15-06 09:00", "High"), ("08-06 09:00", "Low")]:
        timeline_item(t, lv, level_badge(lv, LEVEL_LABELS[lv]),
                      f"Per questionnaire: {LEVEL_LABELS[lv]} · Confidence 78%")

# --- Chips & empty --------------------------------------------------------
section_title("Chips & empty state", "info")
chips(["anxious", "pressure", "insomnia", "deadline"])
spacer(16)
empty_state("clock", "No data yet", "A short line explaining why it is empty and what to do next.")
