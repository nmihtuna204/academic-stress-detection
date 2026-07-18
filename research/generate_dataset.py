"""Synthetic dataset generator for the Vietnamese student stress-detection project.

Generates a CSV where every record is driven by a single latent stress level
(theta in [0, 1]) so that all feature groups stay mutually consistent:

1. Demographics / metadata          (student_id, age, gender, major, ...)
2. Vietnamese free text             (free_text - main LLM input)
3. Emotion-model features           (7 emotion probabilities + stress score,
                                     same weighting formula as app/emotion.py)
4. DASS-21 items + scores           (scored with app/dass21.py)
5. PSS-10 items + score             (items 4, 5, 7, 8 reverse-scored)
6. Stress sources & coping          (academic / lifestyle / coping, Likert 1-5)
7. Training labels                  (stress_label 3-class + binary)

Usage:
    python app/generate_dataset.py --rows 500 --seed 42 --out data/stress_dataset.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.scoring.dass21 import DASS21_QUESTIONS, score_dass21

# ---------------------------------------------------------------------------
# Group 1: demographics
# ---------------------------------------------------------------------------

GENDERS: list[tuple[str, float]] = [("Nữ", 0.52), ("Nam", 0.45), ("Khác", 0.03)]

MAJORS: list[str] = [
    "Công nghệ thông tin",
    "Kinh tế",
    "Y khoa",
    "Kỹ thuật",
    "Ngôn ngữ Anh",
    "Luật",
    "Sư phạm",
    "Thiết kế đồ họa",
]

LIVING_SITUATIONS: list[str] = ["Sống cùng gia đình", "Ký túc xá", "Ở trọ"]

# ---------------------------------------------------------------------------
# Group 5: PSS-10 (Cohen's Perceived Stress Scale)
# ---------------------------------------------------------------------------

# Items 4, 5, 7, 8 are positively worded and reverse-scored (score = 4 - raw).
PSS_REVERSE_ITEMS: set[int] = {4, 5, 7, 8}

# Standard PSS-10 categories on the 0-40 total.
PSS_CATEGORIES: list[tuple[int, str]] = [(0, "Low"), (14, "Moderate"), (27, "High")]

# ---------------------------------------------------------------------------
# Group 6: stress sources & coping resources (Likert 1-5)
# ---------------------------------------------------------------------------

ACADEMIC_STRESSORS: dict[str, str] = {
    "acad_course_load": "bài tập và deadline dồn dập",
    "acad_exam_pressure": "kỳ thi sắp tới",
    "acad_fear_of_failure": "nỗi sợ rớt môn",
    "acad_time_management": "việc không sắp xếp được thời gian học",
    "acad_english_pressure": "chuẩn đầu ra tiếng Anh",
}

LIFESTYLE_STRESSORS: dict[str, str] = {
    "life_financial_pressure": "chuyện tiền bạc và chi phí sinh hoạt",
    "life_family_expectation": "kỳ vọng của gia đình",
    "life_relationship_stress": "chuyện tình cảm và các mối quan hệ",
    "life_sleep_problems": "tình trạng thiếu ngủ kéo dài",
    "life_health_concerns": "sức khỏe dạo này không tốt",
}

COPING_RESOURCES: dict[str, str] = {
    "cope_family_support": "tâm sự với gia đình",
    "cope_friend_support": "đi cà phê tán gẫu với bạn bè",
    "cope_exercise": "chạy bộ hoặc tập gym",
    "cope_hobbies": "nghe nhạc và xem phim",
    "cope_professional_help": "tìm đến phòng tư vấn tâm lý của trường",
}

# ---------------------------------------------------------------------------
# Group 3: emotion-model simulation
# ---------------------------------------------------------------------------

EMOTION_LABELS: list[str] = [
    "fear", "sadness", "anger", "joy", "neutral", "disgust", "surprise",
]

# Same weighting formula as app/emotion.py::_compute_stress_score. Kept local
# so the generator does not import emotion.py (which pulls in transformers).
EMOTION_STRESS_WEIGHTS: dict[str, float] = {
    "fear": 0.4, "sadness": 0.35, "anger": 0.25, "disgust": 0.1, "joy": -0.3,
}

# ---------------------------------------------------------------------------
# Group 2: Vietnamese free-text fragments, per stress band
# ---------------------------------------------------------------------------

TEXT_FRAGMENTS: dict[str, dict[str, list[str]]] = {
    "low": {
        "opener": [
            "Tuần này mọi thứ khá ổn với mình.",
            "Dạo này mình thấy khá thoải mái.",
            "Nhìn chung việc học đang trong tầm kiểm soát.",
            "Tâm trạng mình dạo này khá tốt.",
            "Học kỳ này mình thấy nhẹ nhàng hơn kỳ trước.",
        ],
        "detail": [
            "Bài vở không quá nhiều nên mình có thời gian nghỉ ngơi.",
            "Mình hoàn thành bài tập đúng hạn và còn thời gian cho bản thân.",
            "Thỉnh thoảng mình hơi lo về {acad} nhưng không đáng kể.",
            "Mình vẫn theo kịp chương trình và điểm số ổn định.",
        ],
        "coping": [
            "Cuối tuần mình thường {cope} để thư giãn.",
            "Mình vẫn duy trì {cope} đều đặn nên tinh thần khá tốt.",
            "Có gì căng thẳng thì mình {cope} là lại ổn.",
        ],
    },
    "moderate": {
        "opener": [
            "Dạo này mình hơi căng thẳng.",
            "Gần đây mình thấy khá mệt mỏi.",
            "Học kỳ này áp lực hơn mình nghĩ.",
            "Mấy tuần nay mình thấy hơi quá tải.",
        ],
        "detail": [
            "Chủ yếu là do {acad}, cộng thêm {life} nữa.",
            "{acad} khiến mình lo lắng, đôi lúc khó tập trung học.",
            "Mình bị áp lực bởi {acad}, và {life} cũng làm mình suy nghĩ nhiều.",
            "Vừa phải lo {acad}, vừa phải nghĩ đến {life} nên đầu óc lúc nào cũng căng.",
        ],
        "symptom": [
            "Đêm mình ngủ không sâu, hay nghĩ ngợi lung tung.",
            "Thỉnh thoảng mình thấy tim đập nhanh khi nghĩ đến deadline.",
            "Mình dễ cáu hơn bình thường và hay quên.",
            "Có hôm mình ngồi vào bàn học mà không làm được gì.",
        ],
        "coping": [
            "Mình cố gắng {cope} để giải tỏa bớt.",
            "May là mình còn {cope} được nên cũng đỡ phần nào.",
            "Mình đang tập {cope} thường xuyên hơn để cân bằng lại.",
        ],
    },
    "high": {
        "opener": [
            "Mình cảm thấy kiệt sức.",
            "Dạo này mình rất tệ, lúc nào cũng căng như dây đàn.",
            "Mình đang quá tải thật sự.",
            "Mấy tuần nay mình gần như không còn chút năng lượng nào.",
        ],
        "detail": [
            "{acad} dồn dập, còn thêm {life} khiến mình muốn buông xuôi.",
            "Mình sợ không qua nổi kỳ này vì {acad}, trong khi {life} cứ đè nặng lên vai.",
            "{acad} làm mình hoảng loạn, mà {life} cũng không buông tha.",
        ],
        "symptom": [
            "Mình mất ngủ triền miên, ăn không ngon và rất dễ cáu gắt.",
            "Nhiều lúc mình hoảng loạn, tim đập nhanh và cảm giác không thở nổi.",
            "Mình thấy mọi thứ vô nghĩa và chỉ muốn trốn khỏi tất cả.",
            "Mình khóc mấy lần trong tuần mà không rõ lý do.",
        ],
        "coping": [
            "Mình đã thử {cope} nhưng không ăn thua.",
            "Mình chưa dám kể với ai, chỉ tự mình chịu đựng.",
            "Bạn mình khuyên nên {cope} nhưng mình chưa đủ can đảm.",
        ],
    },
}


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------

def _weighted_choice(rng: random.Random, options: list[tuple[str, float]]) -> str:
    """Pick one option according to its weight."""
    labels = [label for label, _ in options]
    weights = [weight for _, weight in options]
    return rng.choices(labels, weights=weights, k=1)[0]


def _likert(rng: random.Random, mean: float, sd: float = 0.8,
            low: int = 1, high: int = 5) -> int:
    """Sample an integer Likert response around `mean`, clipped to [low, high]."""
    return max(low, min(high, round(rng.gauss(mean, sd))))


def _sample_theta(rng: random.Random) -> float:
    """Sample the latent stress level from a 3-component mixture."""
    band = rng.choices(["low", "moderate", "high"], weights=[0.35, 0.40, 0.25])[0]
    alpha, beta = {"low": (2.0, 6.0), "moderate": (5.0, 5.0), "high": (6.5, 2.5)}[band]
    return min(1.0, max(0.0, rng.betavariate(alpha, beta)))


def _stress_band(theta: float) -> str:
    """Map latent stress to the text-template band."""
    if theta < 0.35:
        return "low"
    if theta < 0.60:
        return "moderate"
    return "high"


def _softmax(logits: dict[str, float]) -> dict[str, float]:
    peak = max(logits.values())
    exps = {label: math.exp(value - peak) for label, value in logits.items()}
    total = sum(exps.values())
    return {label: value / total for label, value in exps.items()}


# ---------------------------------------------------------------------------
# Per-group generators
# ---------------------------------------------------------------------------

def _generate_demographics(rng: random.Random, index: int, theta: float) -> dict:
    academic_year = rng.choices([1, 2, 3, 4, 5], weights=[0.24, 0.25, 0.25, 0.22, 0.04])[0]
    return {
        "student_id": f"SV{index:04d}",
        "age": 17 + academic_year + rng.choice([0, 0, 1]),
        "gender": _weighted_choice(rng, GENDERS),
        "academic_year": academic_year,
        "major": rng.choice(MAJORS),
        "gpa": round(max(2.0, min(4.0, rng.gauss(3.2 - 0.5 * theta, 0.35))), 2),
        "living_situation": rng.choice(LIVING_SITUATIONS),
        "has_part_time_job": rng.choices([1, 0], weights=[0.45, 0.55])[0],
    }


def _generate_dass21(rng: random.Random, theta: float) -> dict:
    # Per-student subscale tendencies: some students skew anxious vs depressed.
    biases = {sub: rng.gauss(0.0, 0.35) for sub in ("depression", "anxiety", "stress")}

    answers: dict[int, int] = {}
    for question in DASS21_QUESTIONS:
        mean = theta * 3.2 + biases[question["subscale"]]
        answers[question["id"]] = max(0, min(3, round(rng.gauss(mean, 0.7))))

    scored = score_dass21(answers)
    row = {f"dass21_q{qid}": answers[qid] for qid in range(1, 22)}
    for subscale in ("depression", "anxiety", "stress"):
        row[f"dass21_{subscale}_score"] = scored[subscale]["score"]
        row[f"dass21_{subscale}_severity"] = scored[subscale]["severity"]
    row["dass21_overall_severity"] = scored["overall_severity"]
    return row


def _generate_pss10(rng: random.Random, theta: float) -> dict:
    row: dict = {}
    total = 0
    for item in range(1, 11):
        if item in PSS_REVERSE_ITEMS:
            # Positively worded item: raw response is high when stress is low.
            raw = max(0, min(4, round(rng.gauss((1.0 - theta) * 4.0, 0.9))))
            total += 4 - raw
        else:
            raw = max(0, min(4, round(rng.gauss(theta * 4.0, 0.9))))
            total += raw
        row[f"pss_q{item}"] = raw

    category = PSS_CATEGORIES[0][1]
    for lower_bound, label in PSS_CATEGORIES:
        if total >= lower_bound:
            category = label
    row["pss_total_score"] = total
    row["pss_stress_category"] = category
    return row


def _generate_stress_resources(rng: random.Random, theta: float) -> dict:
    row: dict = {}
    for column in ACADEMIC_STRESSORS:
        row[column] = _likert(rng, 1.0 + theta * 4.0)
    for column in LIFESTYLE_STRESSORS:
        row[column] = _likert(rng, 0.8 + theta * 3.8)
    for column in COPING_RESOURCES:
        row[column] = _likert(rng, 1.2 + (1.0 - theta) * 3.6)
    return row


def _generate_emotions(rng: random.Random, theta: float) -> dict:
    logits = {
        "fear": -2.0 + 4.0 * theta + rng.gauss(0, 0.5),
        "sadness": -2.0 + 4.2 * theta + rng.gauss(0, 0.5),
        "anger": -2.5 + 3.0 * theta + rng.gauss(0, 0.5),
        "joy": 1.5 - 4.5 * theta + rng.gauss(0, 0.5),
        "neutral": 0.6 - 1.2 * theta + rng.gauss(0, 0.4),
        "disgust": -3.0 + 1.5 * theta + rng.gauss(0, 0.4),
        "surprise": -2.0 + rng.gauss(0, 0.5),
    }
    probabilities = _softmax(logits)

    stress_score = sum(
        weight * probabilities[label] for label, weight in EMOTION_STRESS_WEIGHTS.items()
    )
    stress_score = max(0.0, min(1.0, stress_score))

    row = {f"emotion_{label}": round(probabilities[label], 4) for label in EMOTION_LABELS}
    row["dominant_emotion"] = max(probabilities, key=probabilities.get)
    row["emotion_stress_score"] = round(stress_score, 4)
    return row


def _top_key(rng: random.Random, row: dict, columns: dict[str, str]) -> str:
    """Return the phrase of the highest-rated column (ties broken at random)."""
    best = max(row[column] for column in columns)
    candidates = [column for column in columns if row[column] == best]
    return columns[rng.choice(candidates)]


def _generate_free_text(rng: random.Random, theta: float, resources: dict) -> str:
    band = _stress_band(theta)
    fragments = TEXT_FRAGMENTS[band]

    acad = _top_key(rng, resources, ACADEMIC_STRESSORS)
    life = _top_key(rng, resources, LIFESTYLE_STRESSORS)
    cope = _top_key(rng, resources, COPING_RESOURCES)

    sentences = [rng.choice(fragments["opener"])]
    sentences.append(rng.choice(fragments["detail"]).format(acad=acad, life=life))
    if "symptom" in fragments and rng.random() < 0.8:
        sentences.append(rng.choice(fragments["symptom"]))
    if rng.random() < 0.85:
        sentences.append(rng.choice(fragments["coping"]).format(cope=cope))
    return " ".join(sentences)


def _derive_labels(dass_row: dict, pss_row: dict) -> dict:
    """Derive the training label from the two validated instruments."""
    dass_level = {
        "Normal": 0, "Mild": 0, "Moderate": 1, "Severe": 2, "Extremely Severe": 2,
    }[dass_row["dass21_stress_severity"]]
    pss_level = {"Low": 0, "Moderate": 1, "High": 2}[pss_row["pss_stress_category"]]

    final_level = int((dass_level + pss_level) / 2 + 0.5)
    label = ["Low", "Moderate", "High"][final_level]
    return {"stress_label": label, "stress_label_binary": int(final_level > 0)}


# ---------------------------------------------------------------------------
# Dataset assembly
# ---------------------------------------------------------------------------

def generate_record(rng: random.Random, index: int) -> dict:
    """Generate one fully consistent synthetic student record."""
    theta = _sample_theta(rng)

    record = _generate_demographics(rng, index, theta)
    dass_row = _generate_dass21(rng, theta)
    pss_row = _generate_pss10(rng, theta)
    resources = _generate_stress_resources(rng, theta)

    record["free_text"] = _generate_free_text(rng, theta, resources)
    record.update(_generate_emotions(rng, theta))
    record.update(dass_row)
    record.update(pss_row)
    record.update(resources)
    record.update(_derive_labels(dass_row, pss_row))
    return record


def column_order() -> list[str]:
    """Column order for the CSV, following the 7 feature groups."""
    columns = [
        # 1. metadata / demographics
        "student_id", "age", "gender", "academic_year", "major", "gpa",
        "living_situation", "has_part_time_job",
        # 2. free text (main LLM input)
        "free_text",
        # 3. emotion-model features
        *[f"emotion_{label}" for label in EMOTION_LABELS],
        "dominant_emotion", "emotion_stress_score",
        # 4. DASS-21
        *[f"dass21_q{i}" for i in range(1, 22)],
        "dass21_depression_score", "dass21_depression_severity",
        "dass21_anxiety_score", "dass21_anxiety_severity",
        "dass21_stress_score", "dass21_stress_severity",
        "dass21_overall_severity",
        # 5. PSS-10
        *[f"pss_q{i}" for i in range(1, 11)],
        "pss_total_score", "pss_stress_category",
        # 6. stress sources & coping resources
        *ACADEMIC_STRESSORS, *LIFESTYLE_STRESSORS, *COPING_RESOURCES,
        # 7. labels
        "stress_label", "stress_label_binary",
    ]
    return columns


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=500, help="number of records")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument(
        "--out", type=Path, default=Path("data/stress_dataset.csv"),
        help="output CSV path",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    records = [generate_record(rng, index + 1) for index in range(args.rows)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel on Windows renders the Vietnamese text correctly.
    with args.out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=column_order())
        writer.writeheader()
        writer.writerows(records)

    label_counts: dict[str, int] = {}
    for record in records:
        label_counts[record["stress_label"]] = label_counts.get(record["stress_label"], 0) + 1

    print(f"Wrote {len(records)} records x {len(column_order())} columns to {args.out}")
    print("stress_label distribution:")
    for label in ("Low", "Moderate", "High"):
        count = label_counts.get(label, 0)
        print(f"  {label:<8} {count:>4} ({count / len(records):.1%})")


if __name__ == "__main__":
    main()
