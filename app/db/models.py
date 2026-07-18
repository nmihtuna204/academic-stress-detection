"""SQLAlchemy ORM models implementing the project data schema.

Tables: users, text_entries, questionnaire_responses, stress_context,
predictions. SQLite via SQLAlchemy 2.0 style (Mapped / mapped_column).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    student_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)  # Nam/Nữ/Khác
    year_of_study: Mapped[int | None] = mapped_column(Integer, nullable=True)
    major: Mapped[str | None] = mapped_column(String(120), nullable=True)
    university: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    text_entries: Mapped[list["TextEntry"]] = relationship(back_populates="user")
    questionnaire_responses: Mapped[list["QuestionnaireResponse"]] = relationship(back_populates="user")
    stress_contexts: Mapped[list["StressContext"]] = relationship(back_populates="user")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="user")


class TextEntry(Base):
    __tablename__ = "text_entries"

    entry_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.student_id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    text_length: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(8), default="vi")  # vi/en/mixed
    emotion_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    emotion_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sentiment_polarity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    stress_keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="text_entries")


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    response_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.student_id"), index=True)

    # DASS-21 raw items (0-3); nullable so a PSS-only response is valid.
    dass_q1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q4: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q6: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q7: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q8: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q9: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q10: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q11: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q12: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q13: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q14: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q15: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q16: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q17: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q18: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q19: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q20: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dass_q21: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # DASS-21 derived scores (doubled sums) and severity labels.
    depression_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anxiety_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depression_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    anxiety_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stress_level_dass: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # PSS-10 raw items (0-4); nullable so a DASS-only response is valid.
    pss_q1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q4: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q5: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q6: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q7: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q8: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q9: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_q10: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pss_total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pss_stress_category: Mapped[str | None] = mapped_column(String(12), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="questionnaire_responses")


class StressContext(Base):
    __tablename__ = "stress_context"

    context_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.student_id"), index=True)

    # Academic stressors
    study_hours_per_week: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_exam_period: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    assignment_workload: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    gpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    academic_pressure_source: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Lifestyle stressors
    part_time_job: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    financial_stress: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    sleep_hours_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5

    # Coping resources
    social_support_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    extracurricular_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    coping_strategies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    has_sought_help: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    support_resource_awareness: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="stress_contexts")


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.student_id"), index=True)
    ground_truth_label: Mapped[str | None] = mapped_column(String(12), nullable=True)
    llm_predicted_label: Mapped[str | None] = mapped_column(String(12), nullable=True)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rag_retrieved_context: Mapped[list | None] = mapped_column(JSON, nullable=True)
    llm_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="predictions")
