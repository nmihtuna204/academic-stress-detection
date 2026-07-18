"""DASS-21 (Depression, Anxiety and Stress Scale - 21 items) scoring engine.

Implements the official DASS-21 item-to-subscale mapping and the
scoring/severity classification rules defined by Lovibond & Lovibond (1995).
Pure functions only - this module is the ground-truth source and must stay
deterministic.

Vietnamese item wording follows the validated Vietnamese adaptation of the
DASS-21 (Tran et al., 2013, BMC Psychiatry) with minor smoothing for a
student audience.
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

# The 21 official DASS-21 items with English reference text, Vietnamese
# wording for the UI, and their subscale assignment.
DASS21_QUESTIONS: list[dict[str, object]] = [
    {"id": 1, "subscale": "stress", "text": "I found it hard to wind down", "text_vi": "Tôi thấy khó mà thoải mái, thư giãn được"},
    {"id": 2, "subscale": "anxiety", "text": "I was aware of dryness of my mouth", "text_vi": "Tôi bị khô miệng"},
    {"id": 3, "subscale": "depression", "text": "I couldn't seem to experience any positive feeling at all", "text_vi": "Tôi dường như chẳng có chút cảm xúc tích cực nào"},
    {"id": 4, "subscale": "anxiety", "text": "I experienced breathing difficulty", "text_vi": "Tôi bị rối loạn nhịp thở (thở gấp, khó thở dù chẳng làm việc gì nặng)"},
    {"id": 5, "subscale": "depression", "text": "I found it difficult to work up the initiative to do things", "text_vi": "Tôi thấy khó bắt tay vào công việc, thiếu động lực để bắt đầu"},
    {"id": 6, "subscale": "stress", "text": "I tended to over-react to situations", "text_vi": "Tôi có xu hướng phản ứng thái quá với mọi tình huống"},
    {"id": 7, "subscale": "anxiety", "text": "I experienced trembling (e.g. in the hands)", "text_vi": "Tôi bị run (ví dụ run tay)"},
    {"id": 8, "subscale": "stress", "text": "I felt that I was using a lot of nervous energy", "text_vi": "Tôi thấy mình đang suy nghĩ, lo lắng quá nhiều, đầu óc căng như dây đàn"},
    {"id": 9, "subscale": "anxiety", "text": "I was worried about situations in which I might panic and make a fool of myself", "text_vi": "Tôi lo lắng về những tình huống có thể khiến tôi hoảng sợ hoặc tự làm mình xấu hổ"},
    {"id": 10, "subscale": "depression", "text": "I felt that I had nothing to look forward to", "text_vi": "Tôi thấy mình chẳng có gì để mong đợi ở tương lai"},
    {"id": 11, "subscale": "stress", "text": "I found myself getting agitated", "text_vi": "Tôi thấy bản thân dễ bị kích động, bồn chồn"},
    {"id": 12, "subscale": "stress", "text": "I found it difficult to relax", "text_vi": "Tôi thấy khó thư giãn được"},
    {"id": 13, "subscale": "depression", "text": "I felt down-hearted and blue", "text_vi": "Tôi cảm thấy chán nản, buồn rầu"},
    {"id": 14, "subscale": "stress", "text": "I was intolerant of anything that kept me from getting on with what I was doing", "text_vi": "Tôi không chấp nhận được việc có điều gì đó xen vào cản trở việc tôi đang làm"},
    {"id": 15, "subscale": "anxiety", "text": "I felt I was close to panic", "text_vi": "Tôi thấy mình gần như hoảng loạn"},
    {"id": 16, "subscale": "depression", "text": "I was unable to become enthusiastic about anything", "text_vi": "Tôi không thấy hăng hái, hứng thú với bất kỳ việc gì"},
    {"id": 17, "subscale": "depression", "text": "I felt I wasn't worth much as a person", "text_vi": "Tôi cảm thấy mình chẳng đáng giá gì, không xứng đáng là một con người"},
    {"id": 18, "subscale": "stress", "text": "I felt that I was rather touchy", "text_vi": "Tôi thấy mình khá dễ tự ái, dễ phật ý"},
    {"id": 19, "subscale": "anxiety", "text": "I was aware of the action of my heart in the absence of physical exertion", "text_vi": "Tôi cảm nhận rõ nhịp tim của mình dù không hề vận động (tim đập nhanh, hẫng nhịp)"},
    {"id": 20, "subscale": "anxiety", "text": "I felt scared without any good reason", "text_vi": "Tôi thấy sợ hãi vô cớ"},
    {"id": 21, "subscale": "depression", "text": "I felt that life was meaningless", "text_vi": "Tôi cảm thấy cuộc sống thật vô nghĩa"},
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

ANSWER_CHOICES_VI: dict[int, str] = {
    0: "Không đúng với tôi chút nào",
    1: "Đúng với tôi phần nào, hoặc thỉnh thoảng mới đúng",
    2: "Đúng với tôi phần nhiều, hoặc phần lớn thời gian là đúng",
    3: "Hoàn toàn đúng với tôi, hoặc hầu hết thời gian là đúng",
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
