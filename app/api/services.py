"""Assessment orchestration shared by the API routes.

Pulls together: crisis check -> NLP -> scoring -> RAG -> LLM -> persistence.
Each step degrades gracefully; the deterministic scoring path never depends
on the LLM being reachable.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import Prediction, QuestionnaireResponse, StressContext, TextEntry, User
from app.llm.chain import assess as llm_assess
from app.llm.safety import check_crisis
from app.nlp.emotion import analyze
from app.rag.retriever import RetrievedDoc, retrieve
from app.schemas.enums import StressLevel
from app.schemas.models import (
    AssessmentResponse,
    Dass21Answers,
    Dass21Scores,
    EmotionResult,
    FullAssessmentRequest,
    LlmAssessment,
    Pss10Answers,
    Pss10Scores,
    QuestionnaireResult,
    StressContextIn,
    UserCreate,
)
from app.scoring import derive_ground_truth, score_dass21, score_pss10

logger = logging.getLogger(__name__)


def get_or_create_user(session: Session, student_id: str | None, user_in: UserCreate | None) -> User:
    """Fetch the user by anonymized id, or create one (optionally from metadata)."""
    if student_id:
        user = session.get(User, student_id)
        if user is not None:
            return user
    data = user_in.model_dump(exclude_none=True) if user_in else {}
    if "gender" in data:
        data["gender"] = data["gender"].value if hasattr(data["gender"], "value") else data["gender"]
    user = User(**data)
    if student_id:
        user.student_id = student_id
    session.add(user)
    session.commit()
    return user


def save_text_entry(session: Session, student_id: str, raw_text: str, emotion: EmotionResult) -> TextEntry:
    entry = TextEntry(
        student_id=student_id,
        raw_text=raw_text,
        text_length=len(raw_text),
        language=emotion.language.value,
        emotion_label=emotion.emotion_label,
        emotion_scores=emotion.emotion_scores,
        sentiment_polarity=emotion.sentiment_polarity.value,
        stress_keywords=emotion.stress_keywords,
    )
    session.add(entry)
    session.commit()
    return entry


def score_questionnaires(
    dass21: Dass21Answers | None, pss10: Pss10Answers | None
) -> tuple[dict | None, dict | None, QuestionnaireResult | None]:
    """Run the deterministic scorers; returns (dass_result, pss_result, api_result)."""
    if dass21 is None and pss10 is None:
        return None, None, None
    dass_result = score_dass21(dass21.answers) if dass21 else None
    pss_result = score_pss10(pss10.answers) if pss10 else None
    ground_truth = derive_ground_truth(
        dass_stress_severity=dass_result["stress"]["severity"] if dass_result else None,
        pss_category=pss_result["category"] if pss_result else None,
    )
    api_result = QuestionnaireResult(
        dass21=Dass21Scores(
            depression_score=dass_result["depression"]["score"],
            anxiety_score=dass_result["anxiety"]["score"],
            stress_score=dass_result["stress"]["score"],
            depression_level=dass_result["depression"]["severity"],
            anxiety_level=dass_result["anxiety"]["severity"],
            stress_level_dass=dass_result["stress"]["severity"],
            overall_severity=dass_result["overall_severity"],
        )
        if dass_result
        else None,
        pss10=Pss10Scores(
            pss_total_score=pss_result["total_score"],
            pss_stress_category=pss_result["category"],
        )
        if pss_result
        else None,
        ground_truth_label=StressLevel(ground_truth),
    )
    return dass_result, pss_result, api_result


def save_questionnaire(
    session: Session,
    student_id: str,
    dass21: Dass21Answers | None,
    pss10: Pss10Answers | None,
    dass_result: dict | None,
    pss_result: dict | None,
) -> QuestionnaireResponse:
    row = QuestionnaireResponse(student_id=student_id)
    if dass21 and dass_result:
        for qid, value in dass21.answers.items():
            setattr(row, f"dass_q{qid}", value)
        row.depression_score = dass_result["depression"]["score"]
        row.anxiety_score = dass_result["anxiety"]["score"]
        row.stress_score = dass_result["stress"]["score"]
        row.depression_level = dass_result["depression"]["severity"]
        row.anxiety_level = dass_result["anxiety"]["severity"]
        row.stress_level_dass = dass_result["stress"]["severity"]
    if pss10 and pss_result:
        for qid, value in pss10.answers.items():
            setattr(row, f"pss_q{qid}", value)
        row.pss_total_score = pss_result["total_score"]
        row.pss_stress_category = pss_result["category"]
    session.add(row)
    session.commit()
    return row


def delete_student_data(session: Session, student_id: str) -> dict[str, int] | None:
    """Erase every row belonging to one anonymized id. Returns per-table counts.

    Backs the participant's right to withdraw, which the consent document
    promises. Returns None when the id is unknown, so the caller can 404.

    Children are deleted before the user row because the foreign keys are not
    declared ON DELETE CASCADE; deleting the parent first would strand them.
    """
    user = session.get(User, student_id)
    if user is None:
        return None

    deleted: dict[str, int] = {}
    for label, model in (
        ("predictions", Prediction),
        ("stress_contexts", StressContext),
        ("questionnaire_responses", QuestionnaireResponse),
        ("text_entries", TextEntry),
    ):
        deleted[label] = (
            session.query(model).filter(model.student_id == student_id).delete(
                synchronize_session=False
            )
        )
    session.delete(user)
    session.commit()
    deleted["users"] = 1
    logger.info("Erased all data for student_id=%s: %s", student_id, deleted)
    return deleted


def save_stress_context(session: Session, student_id: str, context: StressContextIn) -> StressContext:
    data = context.model_dump(exclude_none=True, exclude={"student_id"})
    row = StressContext(student_id=student_id, **data)
    session.add(row)
    session.commit()
    return row


def build_rag_query(
    raw_text: str | None, emotion: EmotionResult | None, questionnaire: QuestionnaireResult | None
) -> str:
    """Compose a retrieval query from the strongest available signals.

    Shape chosen by measurement, not intuition. On the 16 labelled queries the
    old construction actually altered (`app.eval.retrieval_eval`, paired design,
    same relevance labels):

        keywords replacing the text (old)   MRR 0.509   Recall@1 0.344
        raw text only                       MRR 0.778   Recall@1 0.656
        raw text + keywords (this)          MRR 0.839   Recall@1 0.719

    Two lessons are encoded here. The student's sentence carries topical signal
    that a bag of matched lexicon keywords throws away, so the sentence leads and
    the keywords sharpen it rather than replacing it. And appending the
    questionnaire label ("student with High stress") *hurt* every variant tested,
    costing the best arm 0.15 MRR: it is semantic noise that pulls a dense
    embedding away from the topic, so it is no longer appended to a text query.

    The no-free-text branch is unchanged, because the query set is all
    text-derived and provides no evidence about it.
    """
    text = raw_text.strip()[:300] if raw_text and raw_text.strip() else ""
    if text:
        keywords = " ".join(emotion.stress_keywords) if emotion and emotion.stress_keywords else ""
        return f"{text} {keywords}".strip()

    if questionnaire:
        return f"student with {questionnaire.ground_truth_label.value} stress"
    return "coping strategies for academic stress in university students"


async def run_full_assessment(
    session: Session, request: FullAssessmentRequest, llm=None
) -> AssessmentResponse:
    """Full pipeline for POST /assess/full (and the building blocks reused elsewhere).

    Ordering is safety-driven: everything up to and including the crisis rule is
    computed in memory, and NOTHING the student disclosed is written to the
    database until the rule has cleared. A student disclosing self-harm is routed
    to helplines and their disclosure is not retained.
    """
    user = get_or_create_user(session, request.student_id, request.user)

    # 1. Analysis only - pure computation, no persistence yet.
    emotion: EmotionResult | None = None
    if request.raw_text and request.raw_text.strip():
        emotion = analyze(request.raw_text)

    dass_result, pss_result, questionnaire = score_questionnaires(request.dass21, request.pss10)

    # 2. Crisis rule - runs BEFORE any persistence and before the LLM.
    crisis = check_crisis(
        raw_text=request.raw_text,
        dass_answers=request.dass21.answers if request.dass21 else None,
        dass_depression_severity=dass_result["depression"]["severity"] if dass_result else None,
    )
    if crisis.is_crisis:
        # Reasons only - never the text that triggered them.
        logger.warning("Crisis rule triggered: %s", crisis.reasons)
        return AssessmentResponse(
            student_id=user.student_id,
            crisis_detected=True,
            crisis_message=crisis.message,
            emotion=emotion,
            questionnaire=questionnaire,
        )

    # 3. Cleared by the crisis rule - now it is safe to persist.
    if emotion is not None:
        save_text_entry(session, user.student_id, request.raw_text, emotion)

    if questionnaire is not None:
        row = save_questionnaire(
            session, user.student_id, request.dass21, request.pss10, dass_result, pss_result
        )
        questionnaire.response_id = row.response_id
        questionnaire.student_id = user.student_id

    if request.stress_context is not None:
        save_stress_context(session, user.student_id, request.stress_context)

    # 5. RAG retrieval.
    docs: list[RetrievedDoc] = retrieve(build_rag_query(request.raw_text, emotion, questionnaire), k=4)

    # 6. LLM assessment (skipped gracefully if unavailable/misconfigured).
    #
    # Refusal on empty retrieval: with nothing retrieved there is nothing to
    # ground advice in, and an ungrounded mental-health suggestion is precisely
    # the failure mode the retrieval layer exists to prevent. Deterministic
    # scoring is unaffected and still returned.
    assessment: LlmAssessment | None = None
    advice_unavailable_reason: str | None = None

    if not docs:
        advice_unavailable_reason = (
            "No reference material could be retrieved, so no grounded suggestions were "
            "generated. Your questionnaire results below are unaffected."
        )
        logger.warning("Retrieval returned no documents; skipping generation to avoid ungrounded advice")
    else:
        try:
            assessment = await llm_assess(
                raw_text=request.raw_text,
                emotion=emotion,
                dass_result=dass_result,
                pss_result=pss_result,
                stress_context=request.stress_context,
                retrieved_docs=docs,
                llm=llm,
            )
        except Exception as exc:
            logger.error("LLM assessment failed, returning deterministic results only: %s", exc)
            # Say so on the page. Without this the advice section renders empty
            # with no explanation, which reads as a broken screen rather than a
            # degraded one - and leaves the student unsure whether the missing
            # advice means something about their results. The deterministic
            # scoring below is unaffected either way.
            advice_unavailable_reason = (
                "Personalised suggestions could not be generated just now (the language "
                "service was unavailable). Your questionnaire results below are complete "
                "and unaffected."
            )

    # Citations are only trustworthy once checked against what was actually
    # retrieved: an id the model invented is a fabricated provenance claim, which
    # is worse than no citation at all.
    cited_sources: list[str] = []
    if assessment is not None:
        by_id = {d.chunk_id: d for d in docs if d.chunk_id}
        kept, dropped = [], []
        for citation in assessment.citations:
            (kept if citation in by_id else dropped).append(citation)
        if dropped:
            logger.warning("Discarded citations not present in retrieved context: %s", dropped)
        assessment.citations = kept
        cited_sources = [f"{by_id[c].source} — {by_id[c].heading}" for c in kept]

    # 7. Persist the prediction row (evaluation data).
    prediction = Prediction(
        student_id=user.student_id,
        ground_truth_label=questionnaire.ground_truth_label.value if questionnaire else None,
        llm_predicted_label=assessment.predicted_level.value if assessment else None,
        llm_confidence=assessment.confidence if assessment else None,
        rag_retrieved_context=[f"{d.source}::{d.heading}" for d in docs],
        llm_explanation=assessment.reasoning if assessment else None,
    )
    session.add(prediction)
    session.commit()

    return AssessmentResponse(
        prediction_id=prediction.prediction_id,
        student_id=user.student_id,
        emotion=emotion,
        questionnaire=questionnaire,
        assessment=assessment,
        rag_sources=[f"{d.source} — {d.heading}" for d in docs],
        cited_sources=cited_sources,
        advice_unavailable_reason=advice_unavailable_reason,
    )
