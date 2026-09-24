"""Results: the most important screen in the app.

Design rule for this page: never lead with a number. A student arriving here may
already be anxious, so the first thing they read is a plain-language sentence
about what the result means and what it does not mean. The level badge, gauge
and subscale scores sit underneath as supporting detail.

The payload and the /assess/full call are unchanged.
"""

import streamlit as st
from ui.charts import dass_bar_chart, gauge_chart, radar_chart, trend_chart
from ui.components import (
    app_footer,
    callout,
    card,
    factor_list,
    page_header,
    recommendation_grid,
    result_hero,
    section_title,
    spacer,
    stat_card,
)
from ui.nav import render_sidebar
from ui.theme import configure_page
from utils import (
    DASS_SEVERITY_LABELS,
    LEVEL_LABELS,
    PSS_CATEGORY_LABELS,
    api_get,
    api_post,
    headline_level,
    require_consent,
    show_crisis,
)

configure_page("Results", "✨")
require_consent()
render_sidebar("result")

# --- Copy -----------------------------------------------------------------
# One reassuring headline + body per level. Written to inform without alarming:
# even the highest level opens with recognition rather than a verdict.
HEADLINES = {
    "Low": (
        "Overall you seem to be holding a good balance",
        "Your results suggest your stress is at a mild level. This is a good moment to "
        "keep up the habits that are working for you — resting enough, and staying "
        "connected with friends and family.",
    ),
    "Moderate": (
        "It looks like you are carrying some academic pressure",
        "Your stress sits at a moderate level — quite common for students during busy "
        "periods. This is **not a medical diagnosis**, but it may be a nudge to give "
        "yourself a little more care.",
    ),
    "High": (
        "You have been under a fair amount of pressure lately",
        "Your results show stress above the usual range. This **does not mean you have "
        "a mental-health condition** — but your body and mind may genuinely need rest. "
        "Consider talking to someone you trust.",
    ),
    "Severe": (
        "It looks like you are holding a great deal right now",
        "Your results show a high level of stress. This is **not a medical diagnosis**, "
        "but it is a clear sign that you deserve support. Reaching out to your university "
        "counselling service or a professional is a strong choice, not a sign of weakness.",
    ),
}

RISK_FLAG_LABELS = {
    "self_harm_risk": "Signs of self-harm",
    "severe_sleep_deprivation": "Severe sleep deprivation",
    "sleep_deprivation": "Sleep deprivation",
    "academic_overload": "Academic overload",
    "social_isolation": "Low social connection",
    "financial_stress": "Financial pressure",
    "burnout": "Signs of burnout",
    "anxiety": "Signs of anxiety",
    "depression": "Signs of low mood",
}

REC_ICONS = ["leaf", "wind", "calendar-check", "users", "book-open"]


def humanize_flag(flag: str) -> str:
    return RISK_FLAG_LABELS.get(flag, flag.replace("_", " ").capitalize())


def protective_factors(ctx: dict) -> list[str]:
    """Strengths derived from what the student told us on the Context page.

    Not from the model — these are simply their own answers reflected back, so
    the page has something affirming to show alongside the risk flags.
    """
    out: list[str] = []
    if (ctx.get("sleep_hours_avg") or 0) >= 7:
        out.append("Getting enough sleep")
    if (ctx.get("sleep_quality") or 0) >= 4:
        out.append("Good sleep quality")
    if (ctx.get("social_support_level") or 0) >= 4:
        out.append("Supportive family/friends")
    if (ctx.get("extracurricular_hours") or 0) >= 2:
        out.append("Physical/extracurricular activity")
    if len(ctx.get("coping_strategies") or []) >= 2:
        out.append("Several familiar coping strategies")
    if ctx.get("support_resource_awareness"):
        out.append("Knows where to find support")
    if (ctx.get("financial_stress") or 5) <= 2:
        out.append("Little financial pressure")
    return out


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
        payload["dass21"] = {
            "answers": {str(k): v for k, v in st.session_state.dass_answers.items()}
        }
    if has_pss:
        payload["pss10"] = {
            "answers": {str(k): v for k, v in st.session_state.pss_answers.items()}
        }
    if st.session_state.stress_context:
        payload["stress_context"] = {
            k: v for k, v in st.session_state.stress_context.items() if v is not None
        }
    return payload


# --- Entry ---------------------------------------------------------------
page_header(
    "Your results",
    subtitle="Pulled together from everything you shared. Read it as a prompt for "
    "understanding yourself better, not as a verdict.",
    icon_name="sparkles",
    eyebrow="Step 5",
)

payload = build_payload()

if payload is None:
    callout(
        "warning",
        "There is nothing to analyse yet. Please **share how you feel** or complete at "
        "least one questionnaire (DASS-21 / PSS-10) first.",
    )
    col1, col2 = st.columns(2)
    with col1:
        st.page_link("pages/1_Share_Feelings.py", label="Share how you feel",
                     icon=":material/edit_note:")
    with col2:
        st.page_link("pages/2_DASS_21.py", label="DASS-21 questionnaire",
                     icon=":material/checklist:")
    app_footer()
    st.stop()

parts = []
if st.session_state.raw_text:
    parts.append("what you wrote")
if len(st.session_state.dass_answers) == 21:
    parts.append("DASS-21")
if len(st.session_state.pss_answers) == 10:
    parts.append("PSS-10")
if st.session_state.stress_context:
    parts.append("your context")

col_run, col_info = st.columns([1, 2])
with col_run:
    run = st.button("Analyse now", type="primary", use_container_width=True)
with col_info:
    st.caption("Will analyse: " + ", ".join(parts))

if run:
    with st.spinner(
        "Reading and analysing... (the first run may take up to a minute to load the model)"
    ):
        result = api_post("/assess/full", payload, timeout=300.0)
    if result is not None:
        st.session_state.last_result = result
        st.session_state.student_id = result.get("student_id")

result = st.session_state.last_result
if result is None:
    app_footer()
    st.stop()

# --- Crisis path: helplines only, nothing else. ---
if result.get("crisis_detected"):
    show_crisis(result["crisis_message"])
    callout(
        "info",
        "For your safety, the detailed analysis is not being shown right now. What "
        "matters most at this moment is that you get support directly.",
    )
    app_footer()
    st.stop()

assessment = result.get("assessment")
questionnaire = result.get("questionnaire")
emotion = result.get("emotion")

# --- Fusion rule ----------------------------------------------------------
# The validated instrument is authoritative for the headline level whenever the
# student completed one. The language model is unvalidated for this construct,
# so it contributes explanation and suggestions but never overrules a DASS-21 /
# PSS-10 score. It supplies the headline only when there is no questionnaire to
# defer to. Where the two disagree, the disagreement is shown rather than hidden.
level = None
confidence = None
level_source = None
model_level = assessment["predicted_level"] if assessment else None

if questionnaire:
    level = questionnaire["ground_truth_label"]
    level_source = "questionnaire"
elif assessment:
    level = model_level
    confidence = assessment.get("confidence")
    level_source = "model"

disagreement = (
    level_source == "questionnaire" and model_level is not None and model_level != level
)

# --- Hero summary ---------------------------------------------------------
if level:
    headline, body = HEADLINES[level]
    result_hero(level, LEVEL_LABELS[level], headline, body)
    if level_source == "questionnaire":
        st.caption(
            "This level comes from your DASS-21 / PSS-10 scores, which are validated "
            "questionnaires. The AI below explains and suggests, but does not decide it."
        )
    if disagreement:
        callout(
            "info",
            f"The AI model read your writing as **{LEVEL_LABELS[model_level]}**, which "
            f"differs from your questionnaire result of **{LEVEL_LABELS[level]}**. The "
            "questionnaire is what the headline reflects. A difference like this is "
            "normal and often just means a few lines of writing capture less than "
            "31 questions do.",
        )
    if not assessment:
        callout(
            "info",
            "The AI explanation is unavailable right now, so only your questionnaire "
            "result is shown.",
        )

# --- Gauge + subscales ----------------------------------------------------
section_title("Overview", "activity")
col1, col2 = st.columns([2, 3], gap="medium")
with col1:
    with card("gauge"):
        if level:
            st.plotly_chart(
                gauge_chart(level, confidence, LEVEL_LABELS),
                use_container_width=True,
                config={"displayModeBar": False},
            )
with col2:
    if questionnaire and questionnaire.get("dass21"):
        with card("dassbars"):
            st.markdown("**DASS-21 scores by subscale**")
            st.plotly_chart(
                dass_bar_chart(questionnaire["dass21"], DASS_SEVERITY_LABELS),
                use_container_width=True,
                config={"displayModeBar": False},
            )
    if questionnaire and questionnaire.get("pss10"):
        pss = questionnaire["pss10"]
        stat_card(
            "PSS-10 — perceived stress (0–40)",
            f"{pss['pss_total_score']} points",
            delta=f"{PSS_CATEGORY_LABELS[pss['pss_stress_category']]} level",
            tone="accent",
        )

# --- Radar profile --------------------------------------------------------
axes: list[tuple[str, float]] = []
if questionnaire and questionnaire.get("dass21"):
    d = questionnaire["dass21"]
    axes += [
        ("Stress", 100 * d["stress_score"] / 42),
        ("Anxiety", 100 * d["anxiety_score"] / 42),
        ("Depression", 100 * d["depression_score"] / 42),
    ]
if questionnaire and questionnaire.get("pss10"):
    axes.append(("Perceived stress", 100 * questionnaire["pss10"]["pss_total_score"] / 40))

if len(axes) >= 3:
    section_title("Profile across dimensions", "chart-bar",
                  hint="Normalized to a 0–100 scale")
    with card("radar"):
        st.plotly_chart(
            radar_chart(axes), use_container_width=True, config={"displayModeBar": False}
        )

# --- Factors --------------------------------------------------------------
risks = [humanize_flag(f) for f in (assessment.get("risk_flags") if assessment else [])]
protects = protective_factors(st.session_state.stress_context or {})

if risks or protects:
    section_title("Things to watch & your strengths", "shield-check")
    col3, col4 = st.columns(2, gap="medium")
    with col3:
        with card("risks"):
            st.markdown("**Worth watching**")
            if risks:
                factor_list(risks, "risk")
            else:
                st.caption("No concerning signs were recorded.")
    with col4:
        with card("protects"):
            st.markdown("**Your strengths**")
            if protects:
                factor_list(protects, "protect")
                st.caption("Based on the Context section you filled in.")
            else:
                st.caption("Fill in the **Academic context** section to see this.")

# --- LLM explanation ------------------------------------------------------
if assessment:
    section_title(
        "What the AI noticed", "message-circle",
        hint="Explains the model's own reading" if disagreement else None,
    )
    with card("reasoning"):
        st.markdown(assessment["reasoning"])

    # --- Recommendations --------------------------------------------------
    # Empty when the model declined to advise beyond the retrieved material;
    # the reason is shown by the advice_unavailable callout below instead.
    suggestions = assessment["suggestions"][:3]
    if suggestions:
        section_title("Things you could try", "leaf", hint="Pick whichever feels manageable")
        recommendation_grid(
            [
                (REC_ICONS[i % len(REC_ICONS)], f"Suggestion {i + 1}", s)
                for i, s in enumerate(suggestions)
            ]
        )

    if len(assessment["suggestions"]) > 3:
        with st.expander("See more suggestions"):
            for extra in assessment["suggestions"][3:]:
                st.markdown(f"- {extra}")

# Advice deliberately withheld, as opposed to merely missing. The student is
# told which it was.
if result.get("advice_unavailable_reason"):
    callout("info", result["advice_unavailable_reason"])

# --- Text analysis (secondary detail) -------------------------------------
if emotion:
    # The title must not name PhoBERT unless PhoBERT actually contributed. It is
    # a Vietnamese-only classifier and is skipped on English input, in which case
    # everything in this box comes from the bilingual lexicon instead. Labelling
    # a lexicon result as a model result would misstate what the system did.
    _model_ran = bool(emotion.get("model_stress_level"))
    _title = (
        "Analysis of what you wrote (PhoBERT classifier + keyword lexicon)"
        if _model_ran
        else "Analysis of what you wrote (keyword lexicon)"
    )
    with st.expander(_title):
        col5, col6 = st.columns(2)
        with col5:
            st.markdown(f"**Sentiment polarity:** {emotion['sentiment_polarity']}")
            if _model_ran:
                st.markdown(
                    "**Stress level per the model:** "
                    + LEVEL_LABELS.get(
                        emotion["model_stress_level"], emotion["model_stress_level"]
                    )
                )
            else:
                st.caption(
                    "The PhoBERT classifier did not run: it is trained on Vietnamese and "
                    f"this entry was detected as **{emotion.get('language', 'non-Vietnamese')}**. "
                    "Your level below comes from the questionnaires, which are unaffected."
                )
        with col6:
            if emotion.get("stress_keywords"):
                st.markdown("**Stress keywords detected:**")
                from ui.components import chips  # local: only needed here

                chips(emotion["stress_keywords"])

# --- Trend (only once there is more than one assessment) ------------------
student_id = st.session_state.student_id
if student_id:
    history = api_get(f"/history/{student_id}")
    preds = (history or {}).get("predictions", [])
    points = [
        (p["created_at"][:16].replace("T", " "), headline_level(p))
        for p in preds
        if headline_level(p)
    ]
    if len(points) >= 2:
        section_title("Change across assessments", "trending-up")
        with card("trend"):
            st.plotly_chart(
                trend_chart(points, LEVEL_LABELS),
                use_container_width=True,
                config={"displayModeBar": False},
            )

# Attribution. `cited_sources` is what the model said it drew on, after the
# backend discarded any citation that was not actually retrieved. `rag_sources`
# is merely what retrieval returned, so it must not be presented as provenance.
if assessment:
    cited = result.get("cited_sources") or []
    if cited:
        st.caption("Advice drawn from: " + " · ".join(cited))
    else:
        st.caption(
            "The model did not attribute its suggestions to any specific reference "
            "document, so treat them as general guidance."
        )
    if result.get("rag_sources"):
        with st.expander("Documents searched"):
            for source in result["rag_sources"]:
                st.markdown(f"- {source}")

spacer(10)
st.page_link("pages/6_History.py", label="See your assessment history",
             icon=":material/timeline:")

app_footer()
