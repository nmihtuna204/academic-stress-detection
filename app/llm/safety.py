"""Crisis-detection rule and helpline content (safety-critical, deterministic).

The rule runs BEFORE any LLM call. If it fires, the normal assessment flow is
bypassed and the crisis message (Vietnamese helplines) is returned instead.

Triggers:
- explicit self-harm/suicide language in the free text (lexicon-based), or
- DASS-21 risk items (17 "not worth much as a person", 21 "life was
  meaningless") both answered at the maximum, or the depression subscale at
  Extremely Severe with either risk item >= 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.nlp.lexicon import find_crisis_keywords
from app.scoring.dass21 import RISK_ITEMS

CRISIS_MESSAGE_VI = """\
🆘 **Chúng mình thực sự quan tâm đến sự an toàn của bạn.**

Từ những gì bạn chia sẻ, có vẻ bạn đang trải qua giai đoạn rất khó khăn. \
Bạn không đơn độc, và những cảm xúc này có thể vượt qua được với sự hỗ trợ đúng cách.

**Hãy liên hệ ngay một trong các kênh sau:**

- 📞 **Đường dây nóng Ngày Mai: 096 306 1414** — hỗ trợ tâm lý miễn phí cho người trẻ
- 📞 **Tổng đài 111** — miễn phí, hoạt động 24/7
- 🚑 **Cấp cứu 115** — nếu bạn đang trong tình huống nguy hiểm
- 🏥 Đến cơ sở y tế gần nhất hoặc phòng tham vấn tâm lý của trường bạn

**Ngay lúc này:** đừng ở một mình — hãy gọi hoặc nhắn tin cho một người bạn tin tưởng \
(bạn thân, anh chị, bố mẹ, thầy cô) và cho họ biết bạn đang cần được ở bên cạnh.

Việc tìm kiếm sự giúp đỡ là dấu hiệu của sự dũng cảm. Bạn xứng đáng được hỗ trợ. 💙\
"""


@dataclass
class CrisisCheckResult:
    is_crisis: bool
    reasons: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    message_vi: str | None = None


def check_crisis(
    raw_text: str | None = None,
    dass_answers: dict[int, int] | None = None,
    dass_depression_severity: str | None = None,
) -> CrisisCheckResult:
    """Run the deterministic crisis-detection rule.

    Args:
        raw_text: the student's free text (optional).
        dass_answers: raw DASS-21 answers keyed 1-21 (optional).
        dass_depression_severity: derived depression severity label (optional).

    Returns:
        CrisisCheckResult with `is_crisis=True` and the helpline message when
        any trigger fires.
    """
    reasons: list[str] = []
    matched: list[str] = []

    if raw_text:
        matched = find_crisis_keywords(raw_text)
        if matched:
            reasons.append("self_harm_language_in_text")

    if dass_answers:
        risk_values = [dass_answers.get(item, 0) for item in RISK_ITEMS]
        if all(v == 3 for v in risk_values):
            reasons.append("dass_risk_items_maximal")
        elif dass_depression_severity == "Extremely Severe" and any(v >= 2 for v in risk_values):
            reasons.append("dass_extremely_severe_depression_with_risk_item")

    if reasons:
        return CrisisCheckResult(
            is_crisis=True,
            reasons=reasons,
            matched_keywords=matched,
            message_vi=CRISIS_MESSAGE_VI,
        )
    return CrisisCheckResult(is_crisis=False)
