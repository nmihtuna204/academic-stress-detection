"""Bilingual stress-keyword lexicon and matching utilities.

The lexicon groups terms/phrases commonly used by students to describe academic
stress. Matching is diacritic-aware, case-insensitive, and phrase-based (longest
match wins), on lightly normalized text.

Both English and Vietnamese entries are kept on purpose. The UI is English, so
English input must be matched; the Vietnamese entries are retained because the
crisis rule's reported precision/recall was measured on a Vietnamese testset and
dropping them would both invalidate those numbers and silently stop detecting
Vietnamese crisis language, which students may still use in free text. Matching
is plain substring containment, so the two sets do not interfere.

English entries are deliberately multi-word or unambiguous: single short words
(e.g. "down", "die") are avoided because they match inside unrelated words.
"""

from __future__ import annotations

import re
import unicodedata

# Grouped for readability; matching uses the flattened set.
STRESS_LEXICON: dict[str, list[str]] = {
    "pressure_workload": [
        # English
        "pressure", "academic pressure", "exam pressure", "grade pressure",
        "deadline", "behind on deadlines", "drowning in assignments",
        "overloaded", "overwhelmed", "can't keep up", "cant keep up",
        "falling behind", "piling up", "packed schedule", "heavy workload",
        "back to back exams", "cramming", "studying day and night",
        # Vietnamese
        "áp lực", "áp lực học tập", "áp lực thi cử", "áp lực điểm số",
        "chạy deadline", "trễ deadline", "ngập trong bài tập",
        "quá tải", "học không kịp", "không kịp tiến độ", "dồn dập",
        "nước đến chân", "học ngày học đêm", "thi liên tục", "lịch học dày đặc",
        "khối lượng bài vở", "bài tập chồng chất", "ôn thi",
    ],
    "anxiety_worry": [
        # English
        "worried", "anxious", "anxiety", "uneasy", "nervous", "on edge",
        "stress", "stressed", "peer pressure", "scared of exams",
        "afraid of failing", "fear of failure", "panicking", "panic attack",
        "restless", "heart racing", "shaking hands", "overthinking",
        "can't calm down", "cant calm down",
        # Vietnamese
        "lo lắng", "lo âu", "bất an", "hồi hộp", "căng thẳng",
        "áp lực đồng trang lứa", "sợ thi", "sợ rớt môn", "sợ trượt",
        "sợ thất bại", "hoang mang", "bồn chồn", "đứng ngồi không yên",
        "tim đập nhanh", "toát mồ hôi", "run tay", "hoảng loạn", "hoảng sợ",
        "suy nghĩ nhiều", "nghĩ ngợi", "mất bình tĩnh",
    ],
    "exhaustion": [
        # English
        "exhausted", "drained", "worn out", "no energy", "running on empty",
        "so tired", "burnout", "burned out", "burnt out", "sluggish",
        # Vietnamese
        "kiệt sức", "mệt mỏi", "mệt rã rời", "đuối", "đuối sức",
        "cạn năng lượng", "không còn sức", "uể oải", "rã rời", "quá mệt",
        "không gượng nổi", "sức cùng lực kiệt",
    ],
    "sleep": [
        # English
        "insomnia", "can't sleep", "cant sleep", "sleep deprived",
        "trouble sleeping", "staying up late", "all-nighter", "all nighter",
        "not sleeping well", "nightmares", "tossing and turning",
        # Vietnamese
        "mất ngủ", "thiếu ngủ", "khó ngủ", "trằn trọc", "thức khuya",
        "thức trắng", "ngủ không ngon", "ngủ không đủ giấc", "ác mộng",
    ],
    "mood_low": [
        # English
        "depressed", "feeling sad", "miserable", "disappointed",
        "lost motivation", "no motivation", "lost interest", "empty inside",
        "lonely", "isolated", "worthless", "useless", "not good enough",
        "crying", "want to cry", "hopeless",
        # Vietnamese
        "chán nản", "buồn bã", "buồn chán", "tủi thân", "thất vọng",
        "chán học", "mất động lực", "mất hứng thú", "trống rỗng",
        "cô đơn", "lạc lõng", "tự ti", "vô dụng", "thua kém",
        "khóc", "muốn khóc", "tuyệt vọng", "u uất", "nặng nề",
    ],
    "overwhelm_stuck": [
        # English
        "stuck", "trapped", "suffocating", "no way out", "dead end",
        "don't know what to do", "dont know what to do", "falling apart",
        "breaking down", "can't take it anymore", "cant take it anymore",
        "want to give up", "want to drop out", "giving up",
        # Vietnamese
        "bế tắc", "ngột ngạt", "không lối thoát", "đường cùng", "mắc kẹt",
        "không biết phải làm sao", "mông lung", "rối bời", "khủng hoảng",
        "sụp đổ", "chịu không nổi", "quá sức chịu đựng", "gục ngã",
        "muốn bỏ học", "muốn bỏ cuộc", "buông xuôi",
    ],
    "external_pressure": [
        # English
        "family expectations", "parents expect", "a burden", "failed a course",
        "tuition", "financial pressure", "being compared", "compared to others",
        "retaking", "failing grades", "low gpa", "bad grades",
        # Vietnamese
        "kỳ vọng của gia đình", "bố mẹ kỳ vọng", "gánh nặng", "nợ môn",
        "học phí", "tiền trọ", "áp lực tài chính", "so sánh", "bị so sánh",
        "học lại", "thi lại", "rớt môn", "điểm kém", "gpa thấp",
    ],
}

# Flattened, longest-first so longer phrases match before their substrings.
ALL_KEYWORDS: list[str] = sorted(
    {kw for group in STRESS_LEXICON.values() for kw in group},
    key=len,
    reverse=True,
)

# High-risk phrases that trigger the crisis rule regardless of model output.
# Deliberately conservative: explicit self-harm / suicide language only.
#
# The English entries are NOT optional: the UI invites students to write in
# English, and a crisis rule that only understands Vietnamese would silently
# miss "I want to kill myself". Every entry is a multi-word phrase or an
# unambiguous term, so the false-positive surface stays small.
CRISIS_KEYWORDS: list[str] = [
    # English
    "kill myself", "killing myself", "suicide", "suicidal",
    "want to die", "wanna die", "end my life", "ending my life",
    "take my own life", "don't want to live", "dont want to live",
    "no reason to live", "better off dead", "hurt myself", "harm myself",
    "self-harm", "self harm", "cut myself", "cutting myself",
    "end it all", "disappear from this world", "life is meaningless",
    # Vietnamese
    "tự tử", "tự sát", "muốn chết", "không muốn sống", "kết thúc cuộc đời",
    "kết thúc tất cả", "tự làm đau", "tự làm hại", "rạch tay", "tự hại",
    "không thiết sống", "chết đi cho xong", "biến mất khỏi thế giới",
    "sống không còn ý nghĩa",
]


def normalize(text: str) -> str:
    """Lowercase, NFC-normalize, and collapse whitespace."""
    text = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def find_stress_keywords(text: str) -> list[str]:
    """Return lexicon phrases present in `text` (deduplicated, longest-first).

    Substring matches that are fully covered by an already-matched longer
    phrase are suppressed (e.g. "academic pressure" suppresses "pressure", and
    "áp lực học tập" suppresses "áp lực", for the same span).
    """
    normalized = normalize(text)
    matched: list[str] = []
    covered: list[tuple[int, int]] = []
    for keyword in ALL_KEYWORDS:
        start = normalized.find(keyword)
        while start != -1:
            end = start + len(keyword)
            if not any(cs <= start and end <= ce for cs, ce in covered):
                if keyword not in matched:
                    matched.append(keyword)
                covered.append((start, end))
            start = normalized.find(keyword, end)
    return matched


def find_crisis_keywords(text: str) -> list[str]:
    """Return crisis phrases present in `text` (empty list = no crisis signal).

    Delegates to the construct-organised patterns in `app.nlp.crisis_patterns`.
    The flat `CRISIS_KEYWORDS` list is retained below for provenance - it is the
    rule whose measured 0.800/0.500 appears in earlier drafts - but it is no
    longer what runs: it caught 0 of 14 indirect-ideation items on a held-out
    set, because indirect risk is phrased compositionally rather than as fixed
    phrases.

    The return type stays `list[str]` so callers, the crisis result object and
    the persisted trigger reasons are unaffected.
    """
    from app.nlp.crisis_patterns import find_crisis_matches

    return [matched for _construct, matched in find_crisis_matches(normalize(text))]


def find_crisis_constructs(text: str) -> list[tuple[str, str]]:
    """As `find_crisis_keywords`, but keeps which clinical construct fired.

    Used by the evaluation report; the safety path itself only needs to know
    that something fired.
    """
    from app.nlp.crisis_patterns import find_crisis_matches

    return find_crisis_matches(normalize(text))
