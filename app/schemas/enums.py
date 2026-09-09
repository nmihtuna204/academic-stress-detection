"""Shared enums used by both Pydantic schemas and SQLAlchemy models."""

from __future__ import annotations

from enum import Enum


class Gender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"


class Language(str, Enum):
    VI = "vi"
    EN = "en"
    MIXED = "mixed"


class SentimentPolarity(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class DassSeverity(str, Enum):
    """DASS-21 severity levels (per subscale), official Lovibond labels."""

    NORMAL = "Normal"
    MILD = "Mild"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    EXTREMELY_SEVERE = "Extremely Severe"


class PssCategory(str, Enum):
    """PSS-10 perceived-stress categories (0-13 / 14-26 / 27-40)."""

    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"


class StressLevel(str, Enum):
    """Unified 4-class stress label used for ground truth and LLM prediction."""

    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    SEVERE = "Severe"
