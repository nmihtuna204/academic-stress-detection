"""Smoke tests for the SQLAlchemy models and session plumbing."""

from app.db import (
    Prediction,
    QuestionnaireResponse,
    StressContext,
    TextEntry,
    User,
    get_session,
)


def test_create_user_and_related_rows(tmp_db):
    session = next(get_session())
    try:
        user = User(age=21, gender="Female", year_of_study=3, major="IT", university="UEH")
        session.add(user)
        session.commit()
        assert user.student_id  # UUID auto-generated
        assert user.created_at is not None

        entry = TextEntry(
            student_id=user.student_id,
            raw_text="I have been under a lot of deadline pressure this week.",
            text_length=55,
            language="en",
            emotion_label="negative",
            emotion_scores={"negative": 0.9},
            sentiment_polarity="negative",
            stress_keywords=["pressure", "deadline"],
        )
        response = QuestionnaireResponse(
            student_id=user.student_id,
            dass_q1=1, depression_score=10, depression_level="Mild",
            pss_total_score=20, pss_stress_category="Moderate",
        )
        context = StressContext(
            student_id=user.student_id,
            study_hours_per_week=30.0,
            is_exam_period=True,
            assignment_workload=4,
            academic_pressure_source=["Exams", "Family expectations"],
            coping_strategies=["Exercise/play sport"],
        )
        prediction = Prediction(
            student_id=user.student_id,
            ground_truth_label="Moderate",
            llm_predicted_label="Moderate",
            llm_confidence=0.8,
            rag_retrieved_context=["doc1"],
            llm_explanation="...",
        )
        session.add_all([entry, response, context, prediction])
        session.commit()

        fetched = session.get(User, user.student_id)
        assert fetched is not None
        assert len(fetched.text_entries) == 1
        assert fetched.text_entries[0].stress_keywords == ["pressure", "deadline"]
        assert fetched.predictions[0].llm_confidence == 0.8
    finally:
        session.close()
