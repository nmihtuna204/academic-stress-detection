"""Synthetic evaluation-data generator.

Creates N synthetic students whose DASS-21/PSS-10 answers are driven by a
latent stress level theta in [0, 1], so ground-truth labels are internally
consistent. A simulated "LLM prediction" is written alongside: it agrees with
the ground truth with probability `agreement`, otherwise errs to an adjacent
class - mimicking a decent-but-imperfect model so the evaluation pipeline can
be exercised without real participants or API calls.

Usage:
    python -m app.eval.synthetic --rows 200 --seed 42 [--agreement 0.72]
"""

from __future__ import annotations

import argparse
import random

from app.db.database import get_session, init_db
from app.db.models import Prediction, QuestionnaireResponse, User
from app.scoring import derive_ground_truth, score_dass21, score_pss10

STRESS_LEVELS = ["Low", "Moderate", "High", "Severe"]

MAJORS = ["Công nghệ thông tin", "Kinh tế", "Y khoa", "Kỹ thuật", "Ngôn ngữ Anh", "Sư phạm", "Luật"]
UNIVERSITIES = ["ĐH Bách Khoa", "ĐH Kinh tế Quốc dân", "ĐH Quốc gia", "ĐH Sư phạm", "ĐH Y Dược"]


def _likert(rng: random.Random, theta: float, max_value: int) -> int:
    """Sample one questionnaire item consistent with latent stress theta."""
    center = theta * max_value
    value = rng.gauss(center, 0.9)
    return max(0, min(max_value, round(value)))


def generate_student(rng: random.Random) -> dict:
    """Generate one synthetic student record (answers + scores + prediction)."""
    theta = rng.betavariate(2.0, 2.2)  # skews slightly toward lower stress

    dass_answers = {qid: _likert(rng, theta, 3) for qid in range(1, 22)}
    # PSS positive items (4,5,7,8) anti-correlate with stress pre-reversal.
    pss_answers = {
        qid: (_likert(rng, 1 - theta, 4) if qid in {4, 5, 7, 8} else _likert(rng, theta, 4))
        for qid in range(1, 11)
    }

    dass_result = score_dass21(dass_answers)
    pss_result = score_pss10(pss_answers)
    ground_truth = derive_ground_truth(
        dass_stress_severity=dass_result["stress"]["severity"],
        pss_category=pss_result["category"],
    )
    return {
        "theta": theta,
        "dass_answers": dass_answers,
        "pss_answers": pss_answers,
        "dass_result": dass_result,
        "pss_result": pss_result,
        "ground_truth": ground_truth,
    }


def simulate_llm_prediction(rng: random.Random, ground_truth: str, agreement: float) -> tuple[str, float]:
    """Simulated LLM label: correct with p=agreement, else an adjacent class."""
    index = STRESS_LEVELS.index(ground_truth)
    if rng.random() < agreement:
        label = ground_truth
        confidence = rng.uniform(0.65, 0.95)
    else:
        neighbors = [i for i in (index - 1, index + 1) if 0 <= i < len(STRESS_LEVELS)]
        label = STRESS_LEVELS[rng.choice(neighbors)]
        confidence = rng.uniform(0.4, 0.75)
    return label, round(confidence, 3)


def seed_database(rows: int = 200, seed: int = 42, agreement: float = 0.72) -> int:
    """Insert `rows` synthetic students (+ responses + predictions) into the DB."""
    rng = random.Random(seed)
    init_db()
    session = next(get_session())
    try:
        for _ in range(rows):
            record = generate_student(rng)
            user = User(
                age=rng.randint(18, 25),
                gender=rng.choices(["Nữ", "Nam", "Khác"], weights=[52, 45, 3])[0],
                year_of_study=rng.randint(1, 5),
                major=rng.choice(MAJORS),
                university=rng.choice(UNIVERSITIES),
            )
            session.add(user)
            session.flush()

            response = QuestionnaireResponse(student_id=user.student_id)
            for qid, value in record["dass_answers"].items():
                setattr(response, f"dass_q{qid}", value)
            for qid, value in record["pss_answers"].items():
                setattr(response, f"pss_q{qid}", value)
            dass = record["dass_result"]
            response.depression_score = dass["depression"]["score"]
            response.anxiety_score = dass["anxiety"]["score"]
            response.stress_score = dass["stress"]["score"]
            response.depression_level = dass["depression"]["severity"]
            response.anxiety_level = dass["anxiety"]["severity"]
            response.stress_level_dass = dass["stress"]["severity"]
            response.pss_total_score = record["pss_result"]["total_score"]
            response.pss_stress_category = record["pss_result"]["category"]
            session.add(response)

            label, confidence = simulate_llm_prediction(rng, record["ground_truth"], agreement)
            session.add(
                Prediction(
                    student_id=user.student_id,
                    ground_truth_label=record["ground_truth"],
                    llm_predicted_label=label,
                    llm_confidence=confidence,
                    rag_retrieved_context=[],
                    llm_explanation="(synthetic)",
                )
            )
        session.commit()
    finally:
        session.close()
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--agreement", type=float, default=0.72)
    args = parser.parse_args()
    count = seed_database(rows=args.rows, seed=args.seed, agreement=args.agreement)
    print(f"Seeded {count} synthetic students into the database.")
