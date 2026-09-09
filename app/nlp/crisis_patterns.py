"""Crisis-detection patterns, organised by clinical construct.

The rule this replaces matched a flat list of fixed phrases. That works for
explicit statements and fails almost completely on indirect and passive
ideation, which is expressed compositionally rather than as set phrases:
measured on a held-out bilingual set, the phrase list caught 0 of 14 indirect
items. Adding more fixed phrases would have fitted the specific sentences in
the test sets rather than the way the risk is actually voiced.

The patterns below are therefore grouped by construct, and the constructs come
from standard suicide-risk assessment rather than from any error list in this
repository:

    EXPLICIT        stated intent, plan or act of self-harm or suicide
    PASSIVE_WISH    wish not to wake, wish to be dead, wish never born
    EXISTENCE       wish to stop existing / not be here
    BURDEN          perceived burdensomeness - others better off without me
                    (Joiner's interpersonal theory names this and thwarted
                    belonging as the two ideation-forming states)
    PREPARATION     goodbye notes, giving possessions away, stockpiling pills
    ESCAPE          indifference to dying, hoping for harm as a way out

DESIGN POSITION ON THE TRADE-OFF. This is a screening aid. A false positive
shows helplines to a student who is not in crisis; a false negative shows
nothing to a student who is. Those costs are not symmetric, so these patterns
are deliberately tuned toward recall, and the precision cost is measured and
reported rather than avoided.

IDIOM GUARDS. English and Vietnamese both use lethal vocabulary for ordinary
complaint - "this deadline is killing me", "laptop died", "cười muốn chết".
Guards suppress a match only when the guard overlaps the SAME span, so a text
containing both an idiom and a genuine disclosure still fires on the
disclosure. Guards are a small, named list of idiom classes, not a catch-all.

HONEST LIMITATION. The author of these patterns also wrote the evaluation sets,
so this is not a blind construction. The discipline actually applied was
procedural: the held-out set was written and frozen (with its SHA-256 recorded)
before these patterns existed, the patterns were written from the construct list
above rather than from failing items, and the first measurement was reported
without iterating on it.
"""

from __future__ import annotations

import re

# --- Patterns, by construct --------------------------------------------------
# Each entry is (construct, regex). Matching is case-insensitive over normalised
# text. Vietnamese and English patterns live together because a single student
# may write either, and the deployed application accepts both.

_PATTERNS: list[tuple[str, str]] = [
    # ---------------- EXPLICIT ----------------
    ("explicit", r"\bkill(?:ing)?\s+(?:myself|my\s?self)\b"),
    ("explicit", r"\bsuicid(?:e|al)\b"),
    ("explicit", r"\b(?:end|ending)\s+my\s+life\b"),
    ("explicit", r"\btake\s+my\s+own\s+life\b"),
    ("explicit", r"\b(?:end|ending)\s+it\s+all\b"),
    ("explicit", r"\b(?:want|wanna|going)\s+to\s+(?:die|be\s+dead)\b"),
    ("explicit", r"\b(?:don'?t|do\s+not)\s+want\s+to\s+live\b"),
    ("explicit", r"\bno\s+(?:reason|point)\s+(?:for\s+me\s+)?to\s+live\b"),
    ("explicit", r"\bnothing\s+to\s+live\s+for\b"),
    ("explicit", r"\b(?:hurt|harm|cut|cutting|harming|hurting)\s+(?:myself|my\s?self)\b"),
    ("explicit", r"\bself[\s-]?harm(?:ing)?\b"),
    ("explicit", r"\battempt(?:ed)?\s+suicide\b|\bsuicide\s+attempt\b"),
    ("explicit", r"\bblade\b.{0,40}\b(?:desk|drawer|bag)\b"),
    ("explicit", r"\btự\s+(?:tử|sát|hại|làm\s+đau|làm\s+hại)\b"),
    ("explicit", r"\bmuốn\s+chết\b"),
    ("explicit", r"\bkhông\s+muốn\s+sống\b"),
    ("explicit", r"\bkết\s+thúc\s+(?:cuộc\s+đời|đời\s+mình|cuộc\s+sống)\b"),
    ("explicit", r"\brạch\s+tay\b"),
    ("explicit", r"\bkhông\s+(?:còn\s+)?lý\s+do\s+(?:gì\s+)?để\s+sống\b"),
    ("explicit", r"\bkhông\s+thiết\s+sống\b"),
    ("explicit", r"\bchết\s+đi\s+cho\s+(?:xong|rồi)\b"),
    ("explicit", r"\blưỡi\s+lam\b"),
    # Both were carried by the superseded phrase list and were lost in this
    # rewrite; the Vietnamese development set caught the regression.
    ("explicit", r"\bsống\s+không\s+còn\s+ý\s+nghĩa\b"),
    ("explicit", r"\bkết\s+thúc\s+tất\s+cả"),

    # ---------------- PASSIVE_WISH ----------------
    ("passive_wish", r"\b(?:not|never|don'?t|do\s+not|won'?t)\s+(?:want\s+to\s+)?wake\s+up\b"),
    ("passive_wish", r"\bwake\s+up\b.{0,20}\b(?:never|again)\b"),
    ("passive_wish", r"\bhop(?:e|ing)\b.{0,25}\bnot\s+wake\b"),
    ("passive_wish", r"\bwish(?:ed)?\s+(?:i|I)\s+(?:was|were)\s+dead\b"),
    ("passive_wish", r"\bwish\b.{0,15}\bnever\s+(?:been\s+)?born\b"),
    ("passive_wish", r"\bwant\s+to\s+be\s+dead\b"),
    ("passive_wish", r"\b(?:đừng|không)\s+tỉnh\s+(?:dậy|lại)\b"),
    ("passive_wish", r"\btỉnh\s+(?:dậy|lại)\b.{0,15}\b(?:nữa|không\s+bao\s+giờ)\b"),
    ("passive_wish", r"\bước\b.{0,25}\bchưa\s+từng\s+(?:được\s+)?sinh\s+ra\b"),
    ("passive_wish", r"\bước\s+(?:gì\s+)?mình\s+chết\b"),

    # ---------------- EXISTENCE ----------------
    ("existence", r"\b(?:stop|quit|cease)\s+(?:to\s+)?exist(?:ing)?\b"),
    ("existence", r"\b(?:don'?t|do\s+not|no\s+longer)\s+want\s+to\s+exist\b"),
    ("existence", r"\bnot\s+(?:be|being)\s+here\s+any\s?more\b"),
    ("existence", r"\bdisappear\b.{0,15}\b(?:forever|permanently|for\s+good)\b"),
    ("existence", r"\bngừng\s+tồn\s+tại\b"),
    ("existence", r"\bkhông\s+muốn\s+tồn\s+tại\b"),
    ("existence", r"\bbiến\s+mất\b.{0,20}\b(?:mãi\s+mãi|vĩnh\s+viễn|khỏi\s+thế\s+giới)\b"),

    # ---------------- BURDEN ----------------
    ("burden", r"\bbetter\s+off\s+without\s+me\b"),
    ("burden", r"\b(?:a\s+)?burden\s+to\s+(?:everyone|everybody|them|my\s+\w+)\b"),
    ("burden", r"\bno\s+point\s+in\s+me\s+being\s+here\b"),
    ("burden", r"\b(?:easier|better)\b.{0,25}\bif\s+i\s+(?:were|was)\s+(?:not|n'?t)\s+(?:around|here|alive)\b"),
    ("burden", r"\bnobody\s+would\s+(?:really\s+)?(?:lose|miss|notice|care)\b"),
    ("burden", r"\bwould\s+be\s+relieved\s+if\s+i\s+(?:were|was)\s+gone\b"),
    ("burden", r"\bnot\s+worth\s+(?:existing|living|being\s+here)\b"),
    ("burden", r"\bgánh\s+nặng\b"),
    ("burden", r"\b(?:tốt|nhẹ\s+nhõm|nhẹ)\s+hơn\b.{0,25}\bkhông\s+có\s+(?:em|mình|tôi)\b"),
    ("burden", r"\bkhông\s+có\s+(?:em|mình|tôi)\s+(?:trên\s+đời|thì)\b"),
    ("burden", r"\bchẳng\s+ai\s+mất\s+mát\s+gì\b"),
    ("burden", r"\bkhông\s+đáng\s+(?:để\s+)?(?:tồn\s+tại|sống)\b"),

    # ---------------- PREPARATION ----------------
    ("preparation", r"\b(?:goodbye|farewell)\s+(?:letter|note|message)s?\b"),
    ("preparation", r"\bwrote\s+letters?\s+for\s+my\b"),
    ("preparation", r"\bgiv(?:e|ing|en)\s+away\s+(?:my|the)\s+(?:things|stuff|belongings|possessions)\b"),
    ("preparation", r"\b(?:count(?:ing)?|sav(?:ed|ing)\s+up)\b.{0,25}\bpills?\b"),
    ("preparation", r"\bsav(?:ed|ing)\s+up\s+(?:my\s+)?medication\b"),
    ("preparation", r"\bthư\s+(?:tạm\s+biệt|từ\s+biệt)\b"),
    ("preparation", r"\b(?:đem|cho)\s+(?:cho\s+)?hết\s+(?:những\s+)?(?:thứ|đồ)\b"),
    ("preparation", r"\b(?:đếm|gom|để\s+dành)\b.{0,25}\bviên\s+thuốc\b"),
    ("preparation", r"\bthuốc\s+ngủ\b.{0,25}\b(?:thật\s+nhiều|uống)\b|\buống\s+thật\s+nhiều\s+thuốc\b"),

    # ---------------- ESCAPE ----------------
    ("escape", r"\btired\s+of\s+(?:being\s+alive|living)\b"),
    ("escape", r"\bhop(?:e|ing)\s+something\s+happens\s+to\s+me\b"),
    ("escape", r"\bif\s+i\s+(?:got|get|was|were)\s+hit\s+by\b"),
    ("escape", r"\bif\s+i\s+did\s+not\s+(?:come\s+back|wake)\b"),
    ("escape", r"\bmệt\s+vì\s+(?:phải\s+)?sống\b"),
    ("escape", r"\bmong\s+(?:có\s+)?chuyện\s+gì\s+đó\s+xảy\s+ra\b"),
    ("escape", r"\bnếu\s+.{0,30}\bkhông\s+về\b.{0,30}\bchẳng\s+ai\b"),
    ("escape", r"\bgặp\s+tai\s+nạn\b.{0,20}\bcũng\s+không\s+sao\b"),
    ("escape", r"\bsống\s+(?:thế\s+này\s+)?thì\s+sống\s+làm\s+gì\b"),
    ("escape", r"\bnghĩ\s+(?:đến|về)\s+(?:chuyện\s+dại\s+dột|cái\s+chết\s+của\s+(?:chính\s+)?mình)\b"),
]

# --- Idiom guards ------------------------------------------------------------
# Suppress a match only where the guard covers the SAME span. Each entry names
# an idiom class observed in student writing, not an individual test sentence.

_GUARDS: list[str] = [
    # exercise intensity: "killing myself at the gym"
    r"kill(?:ing)?\s+myself\s+(?:at|in|on)\s+the\s+\w+",
    # scope clarification: "end it all - this group chat, I mean"
    r"end(?:ing)?\s+it\s+all\s*[—–,\-]{1,2}\s*(?:this|the|my)\b",
    # device or object failure: "my laptop died"
    r"(?:laptop|computer|phone|battery|wifi|printer)\s+(?:died|is\s+dead)",
    # humour: "died laughing", "cười muốn chết"
    r"(?:died|dying|nearly\s+died)\s+laughing",
    r"cười\s+(?:muốn|đến|sặc)\s+chết",
    # willingness idiom: "I would kill for a coffee"
    r"(?:would|'d|could)\s+kill\s+(?:to|for)\b",
    # commitment idiom: "the hill I will die on"
    r"hill\s+(?:i\s+)?(?:will|would|'ll)\s+die\s+on",
    # Vietnamese intensifier: a stative adjective followed by "muốn chết" is
    # the exact counterpart of English "X is killing me". The construction that
    # carries intent puts a PRONOUN before it ("em muốn chết"), so guarding the
    # adjective slot leaves the real phrasing live. This idiom class defeated the
    # superseded rule too - it accounts for all three of its false positives on
    # the Vietnamese development set.
    # Vietnamese adjectives are frequently disyllabic ("buồn ngủ", "mệt mỏi"),
    # so the compounds are listed explicitly rather than allowing a wildcard
    # token before "muốn chết" - a wildcard would swallow real disclosures
    # such as "em buồn quá muốn chết".
    r"\b(?:buồn\s+ngủ|mệt\s+mỏi|đau\s+đầu|nhức\s+đầu|chán\s+nản|đói\s+bụng|khát\s+nước|nóng\s+nực|lạnh\s+cóng)\s+(?:muốn|đến)\s+chết\b",
    r"\b(?:khó|mệt|đói|no|buồn|chán|nóng|lạnh|đau|sợ|vui|cười|thèm|lười|bận|nhức|ngán|tức|áp\s+lực)\s+(?:muốn|đến)\s+chết\b",
    # reported speech or joking about someone else
    r"(?:đùa|giỡn)\b.{0,40}\bmuốn\s+chết\b",
    r"\bnó\s+muốn\s+chết\s+vì\b",
    # scope clarification, Vietnamese counterpart of "end it all - this chat"
    r"kết\s+thúc\s+tất\s+cả\s*[—–,\-]{1,2}\s*(?:cái|nhóm|con)\b",
]

CRISIS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (construct, re.compile(pattern, re.IGNORECASE)) for construct, pattern in _PATTERNS
]
IDIOM_GUARDS: list[re.Pattern[str]] = [re.compile(g, re.IGNORECASE) for g in _GUARDS]


def find_crisis_matches(normalized_text: str) -> list[tuple[str, str]]:
    """Return (construct, matched_text) for every crisis pattern that fires.

    A match is dropped when an idiom guard covers an overlapping span, so a
    message carrying both an idiom and a genuine disclosure still fires on the
    disclosure rather than being silenced by the idiom.
    """
    if not normalized_text:
        return []

    guard_spans = [m.span() for guard in IDIOM_GUARDS for m in guard.finditer(normalized_text)]

    def is_guarded(span: tuple[int, int]) -> bool:
        return any(gs[0] < span[1] and span[0] < gs[1] for gs in guard_spans)

    hits: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for construct, pattern in CRISIS_PATTERNS:
        for match in pattern.finditer(normalized_text):
            if is_guarded(match.span()):
                continue
            key = (construct, match.group(0))
            if key not in seen:
                seen.add(key)
                hits.append(key)
    return hits
