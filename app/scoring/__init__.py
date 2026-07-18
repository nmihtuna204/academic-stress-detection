"""Deterministic scoring engines - the ground-truth source for stress labels."""

from __future__ import annotations

from app.scoring.dass21 import DASS21_QUESTIONS, SEVERITY_LEVELS, score_dass21
from app.scoring.pss10 import PSS10_QUESTIONS, score_pss10

# Order matters: index encodes increasing severity.
_STRESS_LEVELS: list[str] = ["Low", "Moderate", "High", "Severe"]

# DASS-21 stress-subscale severity -> unified 4-class label.
_DASS_TO_UNIFIED: dict[str, str] = {
    "Normal": "Low",
    "Mild": "Moderate",
    "Moderate": "Moderate",
    "Severe": "High",
    "Extremely Severe": "Severe",
}

# PSS-10 category -> unified 4-class label.
_PSS_TO_UNIFIED: dict[str, str] = {
    "Low": "Low",
    "Moderate": "Moderate",
    "High": "High",
}


def derive_ground_truth(
    dass_stress_severity: str | None = None,
    pss_category: str | None = None,
) -> str:
    """Derive the unified ground-truth stress label (Low/Moderate/High/Severe).

    Combines the DASS-21 *stress subscale* severity and the PSS-10 category by
    taking the more severe of the two mappings. At least one input is required.

    Raises:
        ValueError: if both inputs are None or a label is unrecognized.
    """
    candidates: list[str] = []
    if dass_stress_severity is not None:
        if dass_stress_severity not in _DASS_TO_UNIFIED:
            raise ValueError(f"unknown DASS severity: {dass_stress_severity!r}")
        candidates.append(_DASS_TO_UNIFIED[dass_stress_severity])
    if pss_category is not None:
        if pss_category not in _PSS_TO_UNIFIED:
            raise ValueError(f"unknown PSS category: {pss_category!r}")
        candidates.append(_PSS_TO_UNIFIED[pss_category])
    if not candidates:
        raise ValueError("at least one of dass_stress_severity / pss_category is required")
    return max(candidates, key=_STRESS_LEVELS.index)


__all__ = [
    "DASS21_QUESTIONS",
    "PSS10_QUESTIONS",
    "SEVERITY_LEVELS",
    "score_dass21",
    "score_pss10",
    "derive_ground_truth",
]
