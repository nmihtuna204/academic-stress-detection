"""Stress context: academic stressors, lifestyle, coping resources.

Fields and the saved payload are unchanged — presentation only.
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

configure_page("Academic context", "🎓")
require_consent()
render_sidebar("context")

page_header(
    "Your academic context & resources",
    subtitle="This information helps the system tailor its suggestions to your situation. "
    "Everything here is **optional** — feel free to skip any part.",
    icon_name="graduation-cap",
    eyebrow="Step 4",
)

ctx = st.session_state.stress_context

_WORKLOAD = {1: "Very light", 2: "Light", 3: "Moderate", 4: "Heavy", 5: "Very heavy"}
_QUALITY = {1: "Very poor", 2: "Poor", 3: "Average", 4: "Good", 5: "Very good"}
_FINANCIAL = {1: "Negligible", 2: "Slight", 3: "Moderate", 4: "High", 5: "Very high"}
_SUPPORT = {1: "Very little", 2: "Little", 3: "Moderate", 4: "A lot", 5: "A great deal"}

with st.form("context_form"):
    section_title("Study", "book-open")
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        study_hours = st.slider(
            "Study hours per week (classes and self-study combined)",
            0, 80, ctx.get("study_hours_per_week", 25),
        )
        workload = st.select_slider(
            "Current assignment / project workload",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("assignment_workload", 3),
            format_func=lambda x: f"{x} — {_WORKLOAD[x]}",
        )
        exam_period = st.toggle(
            "Currently in exam season / peak week", value=ctx.get("is_exam_period", False)
        )
    with col2:
        gpa_known = st.toggle("Report my GPA", value=ctx.get("gpa") is not None)
        gpa = st.number_input(
            "Current GPA (4-point scale)", 0.0, 4.0, ctx.get("gpa") or 3.0, 0.1,
            disabled=not gpa_known,
        )
        pressure_sources = st.multiselect(
            "Main sources of academic pressure",
            ["Exams", "Grades/GPA", "Projects/assignments", "Family expectations",
             "Comparison with peers", "English/graduation requirements", "Career direction",
             "Failed or retaken courses"],
            default=ctx.get("academic_pressure_source", []),
        )

    section_title("Lifestyle", "moon")
    col3, col4 = st.columns(2, gap="medium")
    with col3:
        sleep_hours = st.slider(
            "Average hours of sleep per night", 3.0, 12.0, ctx.get("sleep_hours_avg", 7.0), 0.5
        )
        sleep_quality = st.select_slider(
            "Sleep quality",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("sleep_quality", 3),
            format_func=lambda x: f"{x} — {_QUALITY[x]}",
        )
    with col4:
        part_time = st.toggle("Working a part-time job", value=ctx.get("part_time_job", False))
        financial = st.select_slider(
            "Level of financial pressure",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("financial_stress", 2),
            format_func=lambda x: f"{x} — {_FINANCIAL[x]}",
        )

    section_title("Coping resources", "users")
    col5, col6 = st.columns(2, gap="medium")
    with col5:
        social_support = st.select_slider(
            "Support from family/friends when you are struggling",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("social_support_level", 3),
            format_func=lambda x: f"{x} — {_SUPPORT[x]}",
        )
        extracurricular = st.slider(
            "Hours of extracurricular activity/sport per week",
            0.0, 30.0, ctx.get("extracurricular_hours", 3.0), 0.5,
        )
    with col6:
        coping = st.multiselect(
            "What do you usually do when you are stressed?",
            ["Exercise/play sport", "Listen to music/watch films", "Talk to friends",
             "Talk to family", "Play games", "Sleep", "Journalling",
             "Meditate/relax", "Go out/travel", "Eat"],
            default=ctx.get("coping_strategies", []),
        )
        sought_help = st.toggle(
            "I have sought professional psychological support before",
            value=ctx.get("has_sought_help", False),
        )
        aware = st.toggle(
            "I know about my university's counselling service",
            value=ctx.get("support_resource_awareness", False),
        )

    spacer(10)
    submitted = st.form_submit_button("Save context", type="primary")

if submitted:
    st.session_state.stress_context = {
        "study_hours_per_week": float(study_hours),
        "is_exam_period": exam_period,
        "assignment_workload": workload,
        "gpa": float(gpa) if gpa_known else None,
        "academic_pressure_source": pressure_sources,
        "part_time_job": part_time,
        "financial_stress": financial,
        "sleep_hours_avg": float(sleep_hours),
        "sleep_quality": sleep_quality,
        "social_support_level": social_support,
        "extracurricular_hours": float(extracurricular),
        "coping_strategies": coping,
        "has_sought_help": sought_help,
        "support_resource_awareness": aware,
    }
    callout("success", "Saved. You are ready to see your results.")

if st.session_state.stress_context:
    spacer(8)
    st.page_link(
        "pages/5_Results.py", label="Continue: See your results", icon=":material/arrow_forward:"
    )

app_footer()
