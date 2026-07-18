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


def save_stress_context(session: Session, student_id: str, context: StressContextIn) -> StressContext:
    data = context.model_dump(exclude_none=True, exclude={"student_id"})
    row = StressContext(student_id=student_id, **data)
    session.add(row)
    session.commit()
    return row


def build_rag_query(
    raw_text: str | None, emotion: EmotionResult | None, questionnaire: QuestionnaireResult | None
) -> str:
    """Compose a retrieval query from the strongest available signals."""
    parts: list[str] = []
    if emotion and emotion.stress_keywords:
        parts.append(" ".join(emotion.stress_keywords))
    elif raw_text:
        parts.append(raw_text[:300])
    if questionnaire:
        parts.append(f"sinh viên căng thẳng mức {questionnaire.ground_truth_label.value}")
    if not parts:
        parts.append("chiến lược ứng phó stress học tập sinh viên")
    return " ".join(parts)


async def run_full_assessment(
    session: Session, request: FullAssessmentRequest, llm=None
) -> AssessmentResponse:
    """Full pipeline for POST /assess/full (and the building blocks reused elsewhere)."""
    user = get_or_create_user(session, request.student_id, request.user)

    # 1. NLP on free text (if any).
    emotion: EmotionResult | None = None
    if request.raw_text and request.raw_text.strip():
        emotion = analyze(request.raw_text)
        save_text_entry(session, user.student_id, request.raw_text, emotion)

    # 2. Deterministic questionnaire scoring.
    dass_result, pss_result, questionnaire = score_questionnaires(request.dass21, request.pss10)
    if questionnaire is not None:
        row = save_questionnaire(
            session, user.student_id, request.dass21, request.pss10, dass_result, pss_result
        )
        questionnaire.response_id = row.response_id
        questionnaire.student_id = user.student_id

    # 3. Stress context persistence.
    if request.stress_context is not None:
        save_stress_context(session, user.student_id, request.stress_context)

    # 4. Crisis rule - bypasses the LLM entirely when triggered.
    crisis = check_crisis(
        raw_text=request.raw_text,
        dass_answers=request.dass21.answers if request.dass21 else None,
        dass_depression_severity=dass_result["depression"]["severity"] if dass_result else None,
    )
    if crisis.is_crisis:
        logger.warning("Crisis rule triggered: %s", crisis.reasons)
        return AssessmentResponse(
            student_id=user.student_id,
            crisis_detected=True,
            crisis_message_vi=crisis.message_vi,
            emotion=emotion,
            questionnaire=questionnaire,
        )

    # 5. RAG retrieval.
    docs: list[RetrievedDoc] = retrieve(build_rag_query(request.raw_text, emotion, questionnaire), k=4)

    # 6. LLM assessment (skipped gracefully if unavailable/misconfigured).
    assessment: LlmAssessment | None = None
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

    # 7. Persist the prediction row (evaluation data).
    prediction = Prediction(
        student_id=user.student_id,
        ground_truth_label=questionnaire.ground_truth_label.value if questionnaire else None,
        llm_predicted_label=assessment.predicted_level.value if assessment else None,
        llm_confidence=assessment.confidence if assessment else None,
        rag_retrieved_context=[f"{d.source}::{d.heading}" for d in docs],
        llm_explanation=assessment.reasoning_vi if assessment else None,
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
    )
