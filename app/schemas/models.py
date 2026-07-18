"""Pydantic v2 request/response schemas mirroring the data model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import (
    DassSeverity,
    Gender,
    Language,
    PssCategory,
    SentimentPolarity,
    StressLevel,
)


class UserCreate(BaseModel):
    age: int | None = Field(None, ge=15, le=80)
    gender: Gender | None = None
    year_of_study: int | None = Field(None, ge=1, le=8)
    major: str | None = Field(None, max_length=120)
    university: str | None = Field(None, max_length=200)


class UserOut(UserCreate):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    created_at: datetime


# --- NLP ---


class EmotionResult(BaseModel):
    """Output of the NLP emotion/sentiment analysis of one text."""

    emotion_label: str
    emotion_scores: dict[str, float]
    sentiment_polarity: SentimentPolarity
    stress_keywords: list[str] = Field(default_factory=list)
    language: Language = Language.VI
    model_stress_level: StressLevel | None = None  # from local PhoBERT classifier, if loaded


class TextEntryIn(BaseModel):
    student_id: str | None = None
    raw_text: str = Field(..., min_length=1, max_length=4000)

    @field_validator("raw_text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_text must not be blank")
        return v


class TextEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: str
    student_id: str
    raw_text: str
    text_length: int
    language: Language
    emotion_label: str | None
    emotion_scores: dict | None
    sentiment_polarity: SentimentPolarity | None
    stress_keywords: list | None
    timestamp: datetime


# --- Questionnaires ---


class Dass21Answers(BaseModel):
    """Raw DASS-21 answers, q1..q21 each 0-3."""

    answers: dict[int, int] = Field(..., description="question id (1-21) -> answer 0-3")

    @field_validator("answers")
    @classmethod
    def _validate(cls, v: dict[int, int]) -> dict[int, int]:
        if set(v.keys()) != set(range(1, 22)):
            raise ValueError("answers must contain exactly question ids 1-21")
        if any(not (0 <= a <= 3) for a in v.values()):
            raise ValueError("each DASS-21 answer must be in 0-3")
        return v


class Pss10Answers(BaseModel):
    """Raw PSS-10 answers, q1..q10 each 0-4."""

    answers: dict[int, int] = Field(..., description="question id (1-10) -> answer 0-4")

    @field_validator("answers")
    @classmethod
    def _validate(cls, v: dict[int, int]) -> dict[int, int]:
        if set(v.keys()) != set(range(1, 11)):
            raise ValueError("answers must contain exactly question ids 1-10")
        if any(not (0 <= a <= 4) for a in v.values()):
            raise ValueError("each PSS-10 answer must be in 0-4")
        return v


class Dass21Scores(BaseModel):
    depression_score: int
    anxiety_score: int
    stress_score: int
    depression_level: DassSeverity
    anxiety_level: DassSeverity
    stress_level_dass: DassSeverity
    overall_severity: DassSeverity


class Pss10Scores(BaseModel):
    pss_total_score: int = Field(..., ge=0, le=40)
    pss_stress_category: PssCategory


class QuestionnaireRequest(BaseModel):
    student_id: str | None = None
    dass21: Dass21Answers | None = None
    pss10: Pss10Answers | None = None

    @field_validator("pss10")
    @classmethod
    def _at_least_one(cls, v, info):
        if v is None and info.data.get("dass21") is None:
            raise ValueError("at least one of dass21 / pss10 is required")
        return v


class QuestionnaireResult(BaseModel):
    response_id: str | None = None
    student_id: str | None = None
    dass21: Dass21Scores | None = None
    pss10: Pss10Scores | None = None
    ground_truth_label: StressLevel


# --- Stress context ---


class StressContextIn(BaseModel):
    student_id: str | None = None

    # Academic stressors
    study_hours_per_week: float | None = Field(None, ge=0, le=112)
    is_exam_period: bool | None = None
    assignment_workload: int | None = Field(None, ge=1, le=5)
    gpa: float | None = Field(None, ge=0, le=4.0)
    academic_pressure_source: list[str] | None = None

    # Lifestyle stressors
    part_time_job: bool | None = None
    financial_stress: int | None = Field(None, ge=1, le=5)
    sleep_hours_avg: float | None = Field(None, ge=0, le=24)
    sleep_quality: int | None = Field(None, ge=1, le=5)

    # Coping resources
    social_support_level: int | None = Field(None, ge=1, le=5)
    extracurricular_hours: float | None = Field(None, ge=0, le=112)
    coping_strategies: list[str] | None = None
    has_sought_help: bool | None = None
    support_resource_awareness: bool | None = None


# --- LLM assessment ---


class LlmAssessment(BaseModel):
    """Structured output contract for the LangChain assessment chain."""

    predicted_level: StressLevel = Field(..., description="Low/Moderate/High/Severe")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning_vi: str = Field(..., description="Explanation in Vietnamese, empathetic, non-diagnostic")
    suggestions_vi: list[str] = Field(..., min_length=3, max_length=5, description="Actionable coping suggestions in Vietnamese")
    risk_flags: list[str] = Field(default_factory=list, description="e.g. self_harm_risk, severe_sleep_deprivation")


class FullAssessmentRequest(BaseModel):
    student_id: str | None = None
    user: UserCreate | None = None
    raw_text: str | None = Field(None, max_length=4000)
    dass21: Dass21Answers | None = None
    pss10: Pss10Answers | None = None
    stress_context: StressContextIn | None = None


class AssessmentResponse(BaseModel):
    prediction_id: str | None = None
    student_id: str | None = None
    crisis_detected: bool = False
    crisis_message_vi: str | None = None
    emotion: EmotionResult | None = None
    questionnaire: QuestionnaireResult | None = None
    assessment: LlmAssessment | None = None
    rag_sources: list[str] = Field(default_factory=list)
    disclaimer_vi: str = (
        "⚠️ Đây là công cụ sàng lọc và tự nhìn nhận, KHÔNG phải công cụ chẩn đoán y khoa. "
        "Kết quả chỉ mang tính tham khảo. Nếu bạn cảm thấy quá tải, hãy tìm đến chuyên gia "
        "tâm lý hoặc cơ sở y tế."
    )
