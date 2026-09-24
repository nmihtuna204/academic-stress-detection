"""History: previous assessments for the current anonymized session id.

Reads GET /history/{student_id} — unchanged. The table dump is replaced by a
trend line plus a timeline, so a student can see movement rather than rows.
"""

import streamlit as st
from ui.charts import trend_chart
from ui.components import (
    app_footer,
    callout,
    card,
    empty_state,
    level_badge,
    page_header,
    section_title,
    spacer,
    stat_grid,
    timeline,
    timeline_item,
)
from ui.nav import render_sidebar
from ui.theme import configure_page
from utils import (
    DASS_SEVERITY_LABELS,
    LEVEL_LABELS,
    PSS_CATEGORY_LABELS,
    api_delete,
    api_get,
    headline_level,
    require_consent,
)

configure_page("History", "📈")
require_consent()
render_sidebar("history")

page_header(
    "Your journey",
    subtitle="The times you paused to check in with yourself. Change over time usually "
    "means more than any single number.",
    icon_name="trending-up",
    eyebrow="Looking back",
)

student_id = st.session_state.student_id
if not student_id:
    empty_state(
        "clock",
        "No assessments yet",
        "Your anonymous code is only created after you run **Analyse** for the first "
        "time on the Results page.",
    )
    spacer(12)
    st.page_link("pages/5_Results.py", label="Go to the Results page",
                 icon=":material/auto_awesome:")
    app_footer()
    st.stop()

history = api_get(f"/history/{student_id}")
if history is None:
    empty_state("clock", "No data found", "There are no records for this anonymous code.")
    app_footer()
    st.stop()

predictions = sorted(history.get("predictions", []), key=lambda p: p["created_at"])
responses = sorted(history.get("questionnaire_responses", []), key=lambda r: r["created_at"])
entries = history.get("text_entries", [])

if not (predictions or responses or entries):
    empty_state("clock", "Nothing saved yet", "Run an analysis on the Results page.")
    app_footer()
    st.stop()

# --- Summary tiles --------------------------------------------------------
latest = predictions[-1] if predictions else None
tiles: list[tuple[str, str, str | None, str]] = [
    ("Assessments taken", str(len(predictions)), None, "accent"),
]
if latest:
    lv_latest = headline_level(latest)
    tiles.append(
        ("Most recent", LEVEL_LABELS.get(lv_latest, "—"),
         latest["created_at"][:10], "accent")
    )
tiles.append(("Questionnaires completed", str(len(responses)), None, "accent"))
stat_grid(tiles)

# --- Trend ----------------------------------------------------------------
points = [
    (p["created_at"][:16].replace("T", " "), headline_level(p))
    for p in predictions
    if headline_level(p)
]
if len(points) >= 2:
    section_title("Change over time", "trending-up")
    with card("trend"):
        st.plotly_chart(
            trend_chart(points, LEVEL_LABELS),
            use_container_width=True,
            config={"displayModeBar": False},
        )
elif points:
    callout("info", "You need at least **2 assessments** to draw a trend chart.")

# --- Timeline -------------------------------------------------------------
if predictions:
    section_title("Your assessments", "clock", hint="Newest first")
    with timeline():
        for p in reversed(predictions):
            lv = headline_level(p)
            badge = level_badge(lv, LEVEL_LABELS.get(lv, "—")) if lv else ""
            model_lv = p.get("llm_predicted_label")
            bits = ["From your questionnaires" if p.get("ground_truth_label") else "From your writing (AI)"]
            # Shown, not hidden, when the model read the writing differently - as on Results.
            if p.get("ground_truth_label") and model_lv and model_lv != p["ground_truth_label"]:
                bits.append(f"AI reading of your writing: {LEVEL_LABELS.get(model_lv, '—')}")
            if p.get("llm_confidence") is not None:
                bits.append(f"AI confidence {p['llm_confidence']:.0%}")
            timeline_item(
                p["created_at"][:16].replace("T", " "),
                lv or "Low",
                badge,
                " · ".join(bits) or "—",
            )

# --- Questionnaire scores -------------------------------------------------
if responses:
    section_title("Questionnaire scores over time", "clipboard-list")
    with st.expander(f"See details ({len(responses)} times)"):
        for r in reversed(responses):
            st.markdown(f"**{r['created_at'][:16].replace('T', ' ')}**")
            cols = st.columns(4)
            fields = [
                ("Depression", r.get("depression_score"), r.get("depression_level")),
                ("Anxiety", r.get("anxiety_score"), r.get("anxiety_level")),
                ("Stress", r.get("stress_score"), r.get("stress_level_dass")),
            ]
            for col, (name, score, sev) in zip(cols, fields):
                with col:
                    value = (
                        f"{score} · {DASS_SEVERITY_LABELS.get(sev, '')}"
                        if score is not None else "—"
                    )
                    st.caption(f"{name}\n\n**{value}**")
            with cols[3]:
                pss = r.get("pss_total_score")
                value = (
                    f"{pss} · {PSS_CATEGORY_LABELS.get(r.get('pss_stress_category'), '')}"
                    if pss is not None else "—"
                )
                st.caption(f"PSS-10\n\n**{value}**")
            st.divider()

# --- Text entries ---------------------------------------------------------
if entries:
    section_title("What you shared", "book-open")
    with st.expander(f"Read back ({len(entries)} entries)"):
        for e in entries:
            st.markdown(f"**{e['timestamp'][:16].replace('T', ' ')}**")
            st.markdown(f"> {e['raw_text']}")
            if e.get("stress_keywords"):
                from ui.components import chips  # local: only needed here

                chips(e["stress_keywords"])
            st.divider()

spacer(10)
st.caption(f"Your anonymous code for this session: `{student_id}`")

# --- Withdrawal -----------------------------------------------------------
# The consent document promises a right to withdraw. This is where it is
# exercised. Two steps on purpose: the action is irreversible.
section_title("Delete my data", "trash-2", hint="This cannot be undone")
with card("erase"):
    st.markdown(
        "You can erase everything stored under your anonymous code: what you wrote, "
        "your questionnaire answers, your context, and your results. This is permanent "
        "and takes effect immediately."
    )
    confirmed = st.checkbox("Yes, I want to permanently delete all of my data.")
    if st.button("Delete my data", type="secondary", disabled=not confirmed):
        result = api_delete(f"/session/{student_id}")
        if result is None:
            callout("info", "There is nothing left to delete for this code.")
        else:
            counts = result.get("deleted", {})
            st.session_state.student_id = None
            st.session_state.last_result = None
            callout(
                "success",
                "Your data has been deleted: "
                + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in counts.items())
                + ".",
            )

app_footer()
