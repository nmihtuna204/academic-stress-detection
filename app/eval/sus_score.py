"""SUS (System Usability Scale) scoring from a filled response CSV.

Input CSV columns: `respondent_id, q1..q10`, each answer in 1-5.
Standard scoring (Brooke, 1996): odd items contribute (answer - 1), even items
contribute (5 - answer); SUS = sum * 2.5, range 0-100.

Usage:
    python -m app.eval.sus_score --csv data/eval/sus_responses.csv
"""

from __future__ import annotations

import argparse

import pandas as pd

QUESTION_COLS = [f"q{i}" for i in range(1, 11)]

# Grade bands per Bangor et al. (2008) / Sauro & Lewis curved grading.
GRADE_BANDS = [
    (84.1, "A (Excellent)"),
    (72.6, "B (Good)"),
    (62.7, "C (Fair)"),
    (51.7, "D (Poor)"),
    (0.0, "F (Very poor)"),
]


def sus_score(answers: dict[str, int] | pd.Series) -> float:
    """Score one respondent's 10 answers (1-5 each) on the 0-100 SUS scale."""
    total = 0
    for i in range(1, 11):
        value = int(answers[f"q{i}"])
        if not 1 <= value <= 5:
            raise ValueError(f"q{i} must be in 1-5, got {value}")
        total += (value - 1) if i % 2 == 1 else (5 - value)
    return total * 2.5


def grade(score: float) -> str:
    for threshold, label in GRADE_BANDS:
        if score >= threshold:
            return label
    return GRADE_BANDS[-1][1]


def score_file(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in QUESTION_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing columns: {missing}")
    df = df.dropna(subset=QUESTION_COLS)
    df["sus"] = df[QUESTION_COLS].apply(sus_score, axis=1)
    df["grade"] = df["sus"].apply(grade)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()

    df = score_file(args.csv)
    print(df[["respondent_id", "sus", "grade"]].to_string(index=False))
    mean = df["sus"].mean()
    print(f"\nn = {len(df)}   mean SUS = {mean:.1f}   ({grade(mean)})")
    print("Reference: 68 is the population average; >= 72.6 reads as 'good'.")


if __name__ == "__main__":
    main()
