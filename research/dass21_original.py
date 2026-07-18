"""DASS-21 (Depression, Anxiety and Stress Scale - 21 items) scoring module.

Implements the official DASS-21 questionnaire, its item-to-subscale mapping,
and the scoring/severity classification rules defined by Lovibond & Lovibond.
"""

from __future__ import annotations

import random

# Severity levels in ascending order of severity, shared by all subscales.
SEVERITY_LEVELS: list[str] = [
    "Normal",
    "Mild",
    "Moderate",
    "Severe",
    "Extremely Severe",
]

# Official DASS-21 severity cutoffs (inclusive lower bound) per subscale.
# Scores are the doubled subscale sums (see score_dass21).
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

# The 21 official DASS-21 questions, each tagged with its id and subscale.
DASS21_QUESTIONS: list[dict[str, object]] = [
    {"id": 1, "text": "I found it hard to wind down", "subscale": "stress"},
    {"id": 2, "text": "I was aware of dryness of my mouth", "subscale": "anxiety"},
    {"id": 3, "text": "I couldn't seem to experience any positive feeling at all", "subscale": "depression"},
    {"id": 4, "text": "I experienced breathing difficulty (e.g. excessively rapid breathing, breathlessness in the absence of physical exertion)", "subscale": "anxiety"},
    {"id": 5, "text": "I found it difficult to work up the initiative to do things", "subscale": "depression"},
    {"id": 6, "text": "I tended to over-react to situations", "subscale": "stress"},
    {"id": 7, "text": "I experienced trembling (e.g. in the hands)", "subscale": "anxiety"},
    {"id": 8, "text": "I felt that I was using a lot of nervous energy", "subscale": "stress"},
    {"id": 9, "text": "I was worried about situations in which I might panic and make a fool of myself", "subscale": "anxiety"},
    {"id": 10, "text": "I felt that I had nothing to look forward to", "subscale": "depression"},
    {"id": 11, "text": "I found myself getting agitated", "subscale": "stress"},
    {"id": 12, "text": "I found it difficult to relax", "subscale": "stress"},
    {"id": 13, "text": "I felt down-hearted and blue", "subscale": "depression"},
    {"id": 14, "text": "I was intolerant of anything that kept me from getting on with what I was doing", "subscale": "stress"},
    {"id": 15, "text": "I felt I was close to panic", "subscale": "anxiety"},
    {"id": 16, "text": "I was unable to become enthusiastic about anything", "subscale": "depression"},
    {"id": 17, "text": "I felt I wasn't worth much as a person", "subscale": "depression"},
    {"id": 18, "text": "I felt that I was rather touchy", "subscale": "stress"},
    {"id": 19, "text": "I was aware of the action of my heart in the absence of physical exertion (e.g. sense of heart rate increase, heart missing a beat)", "subscale": "anxiety"},
    {"id": 20, "text": "I felt scared without any good reason", "subscale": "anxiety"},
    {"id": 21, "text": "I felt that life was meaningless", "subscale": "depression"},
]

# Valid answer scale, per the DASS-21 response format.
ANSWER_CHOICES: dict[int, str] = {
    0: "Did not apply to me at all",
    1: "Applied to me to some degree, or some of the time",
    2: "Applied to me to a considerable degree, or a good part of time",
    3: "Applied to me very much, or most of the time",
}


def _validate_answers(answers: dict[int, int]) -> None:
    """Validate that `answers` has exactly the 21 expected question ids and valid scores.

    Raises:
        ValueError: if the keys aren't exactly {1, ..., 21} or any value
            isn't an integer in [0, 3].
    """
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


def _classify_severity(subscale: str, score: int) -> str:
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
        A dict of the form:
        {
            "depression": {"score": int, "severity": str},
            "anxiety": {"score": int, "severity": str},
            "stress": {"score": int, "severity": str},
            "overall_severity": str,
        }
        where each subscale "score" is the raw item sum multiplied by 2
        (per official DASS-21 scoring rules), and "overall_severity" is
        the most severe of the three subscale classifications.

    Raises:
        ValueError: if `answers` doesn't have exactly 21 entries with
            keys 1-21 and values 0-3.
    """
    _validate_answers(answers)

    raw_sums = {"depression": 0, "anxiety": 0, "stress": 0}
    for question in DASS21_QUESTIONS:
        question_id = question["id"]
        subscale = question["subscale"]
        raw_sums[subscale] += answers[question_id]

    result: dict = {}
    worst_severity_index = 0
    for subscale, raw_sum in raw_sums.items():
        score = raw_sum * 2
        severity = _classify_severity(subscale, score)
        result[subscale] = {"score": score, "severity": severity}
        worst_severity_index = max(worst_severity_index, SEVERITY_LEVELS.index(severity))

    result["overall_severity"] = SEVERITY_LEVELS[worst_severity_index]
    return result


if __name__ == "__main__":
    sample_answers: dict[int, int] = {
        question["id"]: random.randint(0, 3) for question in DASS21_QUESTIONS
    }

    print("Sample answers:")
    for question in DASS21_QUESTIONS:
        qid = question["id"]
        print(f"  Q{qid:>2} [{question['subscale']:<10}] = {sample_answers[qid]}: {question['text']}")

    result = score_dass21(sample_answers)

    print("\nScoring result:")
    for subscale in ("depression", "anxiety", "stress"):
        print(f"  {subscale.capitalize():<11} score={result[subscale]['score']:>2}  severity={result[subscale]['severity']}")
    print(f"  Overall severity: {result['overall_severity']}")
