"""Crisis-detection rule and helpline content (safety-critical, deterministic).

The rule runs BEFORE any LLM call. If it fires, the normal assessment flow is
bypassed and the crisis message is returned instead. The helplines stay
Vietnamese services because the deployment audience is students in Vietnam;
only the surrounding wording is English.

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

CRISIS_MESSAGE = """\
🆘 **Your safety genuinely matters to us.**

From what you shared, it sounds like you are going through something very hard \
right now. You are not alone, and these feelings can be worked through with the \
right support.

**Please reach out to one of these right now:**

- 📞 **Ngay Mai helpline: 096 306 1414** — free psychological support for young people
- 📞 **Hotline 111** — national support line, free, available 24/7
- 🚑 **Emergency 115** — if you are in immediate danger
- 🏥 Go to the nearest medical facility or your university counselling office

**Right now:** please don't stay on your own. Call or message someone you trust \
(a close friend, a sibling, a parent, a teacher) and tell them you need someone \
with you.

Asking for help is an act of courage. You deserve support. 💙\
"""


@dataclass
class CrisisCheckResult:
    is_crisis: bool
    reasons: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    message: str | None = None


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
            message=CRISIS_MESSAGE,
        )
    return CrisisCheckResult(is_crisis=False)
