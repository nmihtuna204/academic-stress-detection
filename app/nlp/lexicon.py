"""Vietnamese stress-keyword lexicon and matching utilities.

The lexicon groups ~90 Vietnamese terms/phrases commonly used by students to
describe academic stress. Matching is diacritic-aware, case-insensitive, and
phrase-based (longest match wins), on lightly normalized text.
"""

from __future__ import annotations

import re
import unicodedata

# Grouped for readability; matching uses the flattened set.
STRESS_LEXICON: dict[str, list[str]] = {
    "pressure_workload": [
        "áp lực", "áp lực học tập", "áp lực thi cử", "áp lực điểm số",
        "deadline", "chạy deadline", "trễ deadline", "ngập trong bài tập",
        "quá tải", "học không kịp", "không kịp tiến độ", "dồn dập",
        "nước đến chân", "học ngày học đêm", "thi liên tục", "lịch học dày đặc",
        "khối lượng bài vở", "bài tập chồng chất", "ôn thi",
    ],
    "anxiety_worry": [
        "lo lắng", "lo âu", "bất an", "hồi hộp", "căng thẳng", "stress",
        "áp lực đồng trang lứa", "sợ thi", "sợ rớt môn", "sợ trượt",
        "sợ thất bại", "hoang mang", "bồn chồn", "đứng ngồi không yên",
        "tim đập nhanh", "toát mồ hôi", "run tay", "hoảng loạn", "hoảng sợ",
        "suy nghĩ nhiều", "nghĩ ngợi", "mất bình tĩnh",
    ],
    "exhaustion": [
        "kiệt sức", "mệt mỏi", "mệt rã rời", "đuối", "đuối sức", "burnout",
        "cạn năng lượng", "không còn sức", "uể oải", "rã rời", "quá mệt",
        "không gượng nổi", "sức cùng lực kiệt",
    ],
    "sleep": [
        "mất ngủ", "thiếu ngủ", "khó ngủ", "trằn trọc", "thức khuya",
        "thức trắng", "ngủ không ngon", "ngủ không đủ giấc", "ác mộng",
    ],
    "mood_low": [
        "chán nản", "buồn bã", "buồn chán", "tủi thân", "thất vọng",
        "chán học", "mất động lực", "mất hứng thú", "trống rỗng",
        "cô đơn", "lạc lõng", "tự ti", "vô dụng", "thua kém",
        "khóc", "muốn khóc", "tuyệt vọng", "u uất", "nặng nề",
    ],
    "overwhelm_stuck": [
        "bế tắc", "ngột ngạt", "không lối thoát", "đường cùng", "mắc kẹt",
        "không biết phải làm sao", "mông lung", "rối bời", "khủng hoảng",
        "sụp đổ", "chịu không nổi", "quá sức chịu đựng", "gục ngã",
        "muốn bỏ học", "muốn bỏ cuộc", "buông xuôi",
    ],
    "external_pressure": [
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
CRISIS_KEYWORDS: list[str] = [
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
    phrase are suppressed (e.g. "áp lực học tập" suppresses "áp lực" for the
    same span).
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
    """Return crisis phrases present in `text` (empty list = no crisis signal)."""
    normalized = normalize(text)
    return [kw for kw in CRISIS_KEYWORDS if kw in normalized]
