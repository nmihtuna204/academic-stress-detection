"""DASS-21 (Depression, Anxiety and Stress Scale - 21 items) scoring engine.

Implements the official DASS-21 item-to-subscale mapping and the
scoring/severity classification rules defined by Lovibond & Lovibond (1995).
Pure functions only - this module is the ground-truth source and must stay
deterministic.

Item wording is the original English DASS-21 (Lovibond & Lovibond, 1995). An
earlier revision also carried the validated Vietnamese adaptation (Tran et al.,
2013, BMC Psychiatry); that wording was dropped when the app moved to English.
"""

from __future__ import annotations

SEVERITY_LEVELS: list[str] = [
    "Normal",
    "Mild",
    "Moderate",
    "Severe",
    "Extremely Severe",
]

# Official DASS-21 severity cutoffs (inclusive lower bound) per subscale,
# applied to the doubled subscale sums (see score_dass21).
_SEVERITY_THRESHOLDS: dict[str, list[tuple[int, str]]] = {
    "depression": [
        (0, "Normal"),
        (10, "Mild"),
        (14, "Moderate"),
        (21, "Severe"),
        (28, "Extremely Severe"),
    ],
    "anxiety": [
        (0, "Normal"),
        (8, "Mild"),
        (10, "Moderate"),
        (15, "Severe"),
        (20, "Extremely Severe"),
    ],
    "stress": [
        (0, "Normal"),
        (15, "Mild"),
        (19, "Moderate"),
        (26, "Severe"),
        (34, "Extremely Severe"),
    ],
}

# The 21 official DASS-21 items with their wording and subscale assignment.
DASS21_QUESTIONS: list[dict[str, object]] = [
    {"id": 1, "subscale": "stress", "text": "I found it hard to wind down"},
    {"id": 2, "subscale": "anxiety", "text": "I was aware of dryness of my mouth"},
    {"id": 3, "subscale": "depression", "text": "I couldn't seem to experience any positive feeling at all"},
    {"id": 4, "subscale": "anxiety", "text": "I experienced breathing difficulty"},
    {"id": 5, "subscale": "depression", "text": "I found it difficult to work up the initiative to do things"},
    {"id": 6, "subscale": "stress", "text": "I tended to over-react to situations"},
    {"id": 7, "subscale": "anxiety", "text": "I experienced trembling (e.g. in the hands)"},
    {"id": 8, "subscale": "stress", "text": "I felt that I was using a lot of nervous energy"},
    {"id": 9, "subscale": "anxiety", "text": "I was worried about situations in which I might panic and make a fool of myself"},
    {"id": 10, "subscale": "depression", "text": "I felt that I had nothing to look forward to"},
    {"id": 11, "subscale": "stress", "text": "I found myself getting agitated"},
    {"id": 12, "subscale": "stress", "text": "I found it difficult to relax"},
    {"id": 13, "subscale": "depression", "text": "I felt down-hearted and blue"},
    {"id": 14, "subscale": "stress", "text": "I was intolerant of anything that kept me from getting on with what I was doing"},
    {"id": 15, "subscale": "anxiety", "text": "I felt I was close to panic"},
    {"id": 16, "subscale": "depression", "text": "I was unable to become enthusiastic about anything"},
    {"id": 17, "subscale": "depression", "text": "I felt I wasn't worth much as a person"},
    {"id": 18, "subscale": "stress", "text": "I felt that I was rather touchy"},
    {"id": 19, "subscale": "anxiety", "text": "I was aware of the action of my heart in the absence of physical exertion"},
    {"id": 20, "subscale": "anxiety", "text": "I felt scared without any good reason"},
    {"id": 21, "subscale": "depression", "text": "I felt that life was meaningless"},
]

# Item ids per subscale (derived once; used by tests and the API layer).
SUBSCALE_ITEMS: dict[str, list[int]] = {
    "depression": [q["id"] for q in DASS21_QUESTIONS if q["subscale"] == "depression"],
    "anxiety": [q["id"] for q in DASS21_QUESTIONS if q["subscale"] == "anxiety"],
    "stress": [q["id"] for q in DASS21_QUESTIONS if q["subscale"] == "stress"],
}

# DASS-21 depression items most indicative of self-harm / hopelessness risk,
# used by the crisis-detection rule (see app/llm/safety.py).
RISK_ITEMS: list[int] = [17, 21]

# Official DASS-21 response anchors (past week).
ANSWER_CHOICES: dict[int, str] = {
    0: "Did not apply to me at all",
    1: "Applied to me to some degree, or some of the time",
    2: "Applied to me to a considerable degree, or a good part of the time",
    3: "Applied to me very much, or most of the time",
}


def _validate_answers(answers: dict[int, int]) -> None:
    """Raise ValueError unless `answers` maps exactly ids 1-21 to ints in 0-3."""
    expected_ids = set(range(1, 22))
    if set(answers.keys()) != expected_ids:
        raise ValueError(
            f"answers must contain exactly keys 1-21, got {sorted(answers.keys())}"
        )
    for question_id, value in answers.items():
        if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1, 2, 3):
            raise ValueError(
                f"answer for question {question_id} must be an int in 0-3, got {value!r}"
            )


def classify_severity(subscale: str, score: int) -> str:
    """Classify a doubled subscale score into a DASS-21 severity label."""
    thresholds = _SEVERITY_THRESHOLDS[subscale]
    severity = thresholds[0][1]
    for lower_bound, label in thresholds:
        if score >= lower_bound:
            severity = label
        else:
            break
    return severity


def score_dass21(answers: dict[int, int]) -> dict:
    """Score a completed DASS-21 questionnaire.

    Args:
        answers: mapping of question id (1-21) to answer value (0-3).

    Returns:
        {
            "depression": {"score": int, "severity": str},
            "anxiety": {"score": int, "severity": str},
            "stress": {"score": int, "severity": str},
            "overall_severity": str,
        }
        where each subscale "score" is the raw item sum multiplied by 2
        (per official DASS-21 scoring rules) and "overall_severity" is the
        most severe of the three subscale classifications.

    Raises:
        ValueError: if `answers` doesn't have exactly 21 entries with
            keys 1-21 and values 0-3.
    """
    _validate_answers(answers)

    raw_sums = {"depression": 0, "anxiety": 0, "stress": 0}
    for question in DASS21_QUESTIONS:
        raw_sums[question["subscale"]] += answers[question["id"]]

    result: dict = {}
    worst_severity_index = 0
    for subscale, raw_sum in raw_sums.items():
        score = raw_sum * 2
        severity = classify_severity(subscale, score)
        result[subscale] = {"score": score, "severity": severity}
        worst_severity_index = max(worst_severity_index, SEVERITY_LEVELS.index(severity))

    result["overall_severity"] = SEVERITY_LEVELS[worst_severity_index]
    return result
