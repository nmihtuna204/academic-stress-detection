"""FastAPI application: async assessment endpoints with auto-generated docs."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.db.database import get_session, init_db
from app.db.models import Prediction, QuestionnaireResponse, TextEntry, User
from app.llm.safety import check_crisis
from app.nlp.emotion import analyze
from app.schemas.models import (
    AssessmentResponse,
    FullAssessmentRequest,
    QuestionnaireRequest,
    TextEntryIn,
)
from app.api import services

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # NLP models load lazily on first request; warm them in the background at
    # startup would block Windows CPU boxes for ~30s, so we accept lazy load.
    yield


app = FastAPI(
    title="Academic Stress Detection API",
    description=(
        "Screening/self-reflection aid for academic stress in university students. "
        "NOT a diagnostic tool."
    ),
    version=__version__,
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    """Liveness probe with model/knowledge availability details."""

    try:
        from app.rag.store import get_collection

        kb_chunks = get_collection().count()
    except Exception:
        kb_chunks = 0
    return {
        "status": "ok",
        "version": __version__,
        "knowledge_chunks": kb_chunks,
    }


@app.post("/assess/text", response_model=AssessmentResponse)
async def assess_text(
    payload: TextEntryIn, session: Session = Depends(get_session)
) -> AssessmentResponse:
    """Analyze free text only: NLP emotion + keywords + crisis check (no LLM).

    The crisis rule runs before the text is written, so a self-harm disclosure
    is routed to helplines rather than retained.
    """
    user = services.get_or_create_user(session, payload.student_id, None)
    emotion = analyze(payload.raw_text)

    crisis = check_crisis(raw_text=payload.raw_text)
    if crisis.is_crisis:
        logger.warning("Crisis rule triggered: %s", crisis.reasons)
        return AssessmentResponse(
            student_id=user.student_id,
            crisis_detected=True,
            crisis_message=crisis.message,
            emotion=emotion,
        )

    services.save_text_entry(session, user.student_id, payload.raw_text, emotion)
    return AssessmentResponse(student_id=user.student_id, emotion=emotion)


@app.post("/assess/questionnaire", response_model=AssessmentResponse)
async def assess_questionnaire(
    payload: QuestionnaireRequest, session: Session = Depends(get_session)
) -> AssessmentResponse:
    """Score DASS-21 and/or PSS-10 deterministically (no LLM)."""
    if payload.dass21 is None and payload.pss10 is None:
        raise HTTPException(status_code=422, detail="at least one of dass21 / pss10 is required")

    user = services.get_or_create_user(session, payload.student_id, None)
    dass_result, pss_result, questionnaire = services.score_questionnaires(
        payload.dass21, payload.pss10
    )

    # Same ordering rule as the other endpoints: clear the crisis check before
    # anything the student disclosed is written down.
    crisis = check_crisis(
        dass_answers=payload.dass21.answers if payload.dass21 else None,
        dass_depression_severity=dass_result["depression"]["severity"] if dass_result else None,
    )
    if crisis.is_crisis:
        logger.warning("Crisis rule triggered: %s", crisis.reasons)
        return AssessmentResponse(
            student_id=user.student_id,
            crisis_detected=True,
            crisis_message=crisis.message,
            questionnaire=questionnaire,
        )

    row = services.save_questionnaire(
        session, user.student_id, payload.dass21, payload.pss10, dass_result, pss_result
    )
    questionnaire.response_id = row.response_id
    questionnaire.student_id = user.student_id
    return AssessmentResponse(student_id=user.student_id, questionnaire=questionnaire)


@app.post("/assess/full", response_model=AssessmentResponse)
async def assess_full(
    payload: FullAssessmentRequest, session: Session = Depends(get_session)
) -> AssessmentResponse:
    """Full pipeline: NLP + scoring + crisis rule + RAG + LLM assessment."""
    if not any([payload.raw_text, payload.dass21, payload.pss10]):
        raise HTTPException(
            status_code=422, detail="provide raw_text and/or questionnaire answers"
        )
    return await services.run_full_assessment(session, payload)


@app.delete("/session/{student_id}")
async def delete_session(student_id: str, session: Session = Depends(get_session)) -> dict:
    """Permanently erase every record for one anonymized id.

    Implements the right to withdraw promised by the consent document. The
    anonymized id is the only handle that exists, so possession of it is what
    authorises the deletion, exactly as it is what authorises reading history.
    """
    deleted = services.delete_student_data(session, student_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="student_id not found")
    return {"student_id": student_id, "deleted": deleted}


@app.get("/history/{student_id}")
async def history(student_id: str, session: Session = Depends(get_session)) -> dict:
    """All stored entries for one anonymized student id."""
    user = session.get(User, student_id)
    if user is None:
        raise HTTPException(status_code=404, detail="student_id not found")

    text_entries = session.scalars(
        select(TextEntry).where(TextEntry.student_id == student_id).order_by(TextEntry.timestamp)
    ).all()
    responses = session.scalars(
        select(QuestionnaireResponse)
        .where(QuestionnaireResponse.student_id == student_id)
        .order_by(QuestionnaireResponse.created_at)
    ).all()
    predictions = session.scalars(
        select(Prediction).where(Prediction.student_id == student_id).order_by(Prediction.created_at)
    ).all()

    return {
        "student_id": student_id,
        "created_at": user.created_at,
        "text_entries": [
            {
                "entry_id": e.entry_id,
                "raw_text": e.raw_text,
                "emotion_label": e.emotion_label,
                "sentiment_polarity": e.sentiment_polarity,
                "stress_keywords": e.stress_keywords,
                "timestamp": e.timestamp,
            }
            for e in text_entries
        ],
        "questionnaire_responses": [
            {
                "response_id": r.response_id,
                "depression_score": r.depression_score,
                "anxiety_score": r.anxiety_score,
                "stress_score": r.stress_score,
                "depression_level": r.depression_level,
                "anxiety_level": r.anxiety_level,
                "stress_level_dass": r.stress_level_dass,
                "pss_total_score": r.pss_total_score,
                "pss_stress_category": r.pss_stress_category,
                "created_at": r.created_at,
            }
            for r in responses
        ],
        "predictions": [
            {
                "prediction_id": p.prediction_id,
                "ground_truth_label": p.ground_truth_label,
                "llm_predicted_label": p.llm_predicted_label,
                "llm_confidence": p.llm_confidence,
                "llm_explanation": p.llm_explanation,
                "created_at": p.created_at,
            }
            for p in predictions
        ],
    }
