"""PSS-10 (Perceived Stress Scale, 10 items) scoring engine.

Implements Cohen's official PSS-10 scoring: items are rated 0-4, items
4, 5, 7 and 8 are reverse-scored (4 - value), and the total (0-40) maps to
Low (0-13), Moderate (14-26), High (27-40) perceived stress.

Pure functions only - deterministic ground-truth source.
"""

from __future__ import annotations

# Items whose score is reversed (positively worded items).
REVERSE_SCORED_ITEMS: frozenset[int] = frozenset({4, 5, 7, 8})

# Category cutoffs (inclusive lower bound) on the 0-40 total.
_CATEGORY_THRESHOLDS: list[tuple[int, str]] = [
    (0, "Low"),
    (14, "Moderate"),
    (27, "High"),
]

PSS10_QUESTIONS: list[dict[str, object]] = [
    {"id": 1, "reverse": False, "text": "How often have you been upset because of something that happened unexpectedly?"},
    {"id": 2, "reverse": False, "text": "How often have you felt that you were unable to control the important things in your life?"},
    {"id": 3, "reverse": False, "text": "How often have you felt nervous and stressed?"},
    {"id": 4, "reverse": True, "text": "How often have you felt confident about your ability to handle your personal problems?"},
    {"id": 5, "reverse": True, "text": "How often have you felt that things were going your way?"},
    {"id": 6, "reverse": False, "text": "How often have you found that you could not cope with all the things that you had to do?"},
    {"id": 7, "reverse": True, "text": "How often have you been able to control irritations in your life?"},
    {"id": 8, "reverse": True, "text": "How often have you felt that you were on top of things?"},
    {"id": 9, "reverse": False, "text": "How often have you been angered because of things that were outside of your control?"},
    {"id": 10, "reverse": False, "text": "How often have you felt difficulties were piling up so high that you could not overcome them?"},
]

# Official PSS-10 response anchors (past month).
ANSWER_CHOICES: dict[int, str] = {
    0: "Never",
    1: "Almost never",
    2: "Sometimes",
    3: "Fairly often",
    4: "Very often",
}


def _validate_answers(answers: dict[int, int]) -> None:
    """Raise ValueError unless `answers` maps exactly ids 1-10 to ints in 0-4."""
    expected_ids = set(range(1, 11))
    if set(answers.keys()) != expected_ids:
        raise ValueError(
            f"answers must contain exactly keys 1-10, got {sorted(answers.keys())}"
        )
    for question_id, value in answers.items():
        if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1, 2, 3, 4):
            raise ValueError(
                f"answer for question {question_id} must be an int in 0-4, got {value!r}"
            )


def classify_pss(total_score: int) -> str:
    """Classify a 0-40 PSS-10 total into Low / Moderate / High."""
    if not 0 <= total_score <= 40:
        raise ValueError(f"total_score must be in 0-40, got {total_score}")
    category = _CATEGORY_THRESHOLDS[0][1]
    for lower_bound, label in _CATEGORY_THRESHOLDS:
        if total_score >= lower_bound:
            category = label
        else:
            break
    return category


def score_pss10(answers: dict[int, int]) -> dict:
    """Score a completed PSS-10 questionnaire.

    Args:
        answers: mapping of question id (1-10) to answer value (0-4).

    Returns:
        {
            "total_score": int,       # 0-40, after reverse-scoring items 4,5,7,8
            "category": str,          # Low / Moderate / High
            "item_scores": dict[int, int],  # per-item scores after reversal
        }

    Raises:
        ValueError: if `answers` doesn't have exactly 10 entries with
            keys 1-10 and values 0-4.
    """
    _validate_answers(answers)

    item_scores = {
        qid: (4 - value if qid in REVERSE_SCORED_ITEMS else value)
        for qid, value in answers.items()
    }
    total_score = sum(item_scores.values())

    return {
        "total_score": total_score,
        "category": classify_pss(total_score),
        "item_scores": item_scores,
    }
