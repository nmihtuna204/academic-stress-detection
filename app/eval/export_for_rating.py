"""Export a sample of LLM explanations for human rating.

Samples up to N stored LLM explanations from the predictions table and writes
one rating sheet per rater (CSV): item id, the input context, the explanation,
and BLANK columns for accuracy / helpfulness / respectfulness (1-5) plus a
free-text comment. Sheets contain identical items in per-rater shuffled order
(seeded), so raters can't anchor on each other while the analysis script can
join on item_id.

Placeholder explanations from the synthetic seeder ("(synthetic)") are refused:
rating sheets must only ever contain real model output.

Usage:
    python -m app.eval.export_for_rating --n 30 --raters 3
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.config import PROJECT_ROOT
from app.db.database import get_session, init_db
from app.db.models import Prediction

DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "eval" / "rating"

RATING_COLUMNS = ["accuracy_1_5", "helpfulness_1_5", "respectfulness_1_5", "comment"]


def sample_explanations(n: int = 30, seed: int = 42) -> pd.DataFrame:
    """Sample stored real (non-placeholder) LLM explanations."""
    init_db()
    session = next(get_session())
    try:
        predictions = session.scalars(
            select(Prediction).where(
                Prediction.llm_explanation.is_not(None),
                Prediction.llm_explanation != "(synthetic)",
                Prediction.llm_explanation != "",
            )
        ).all()
    finally:
        session.close()

    if not predictions:
        raise SystemExit(
            "No real LLM explanations found in the predictions table. Rating sheets "
            "are only generated from actual model output - run real assessments "
            "first (synthetic placeholder explanations are deliberately excluded)."
        )

    rng = random.Random(seed)
    chosen = rng.sample(predictions, min(n, len(predictions)))
    return pd.DataFrame(
        [
            {
                "item_id": p.prediction_id,
                "predicted_level": p.llm_predicted_label,
                "ground_truth_level": p.ground_truth_label,
                "explanation": p.llm_explanation,
            }
            for p in chosen
        ]
    )


def write_sheets(items: pd.DataFrame, raters: int, out_dir: Path, seed: int = 42) -> list[Path]:
    """Write one CSV per rater: same items, per-rater shuffled order, blank scores."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for rater in range(1, raters + 1):
        sheet = items.sample(frac=1.0, random_state=seed + rater).reset_index(drop=True)
        for column in RATING_COLUMNS:
            sheet[column] = ""
        path = out_dir / f"rating_sheet_rater{rater}.csv"
        sheet.to_csv(path, index=False, encoding="utf-8-sig")  # BOM: opens cleanly in Excel
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--raters", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    items = sample_explanations(n=args.n, seed=args.seed)
    paths = write_sheets(items, raters=args.raters, out_dir=Path(args.out_dir), seed=args.seed)
    print(f"Sampled {len(items)} explanations; wrote {len(paths)} rating sheets:")
    for path in paths:
        print(f"  {path}")
    print(
        "\nInstructions for raters: score each explanation 1-5 on accuracy "
        "(consistent with the shown levels), helpfulness (actionable for the "
        "student), respectfulness (empathetic, non-diagnostic tone); leave a "
        "comment for any score <= 2."
    )


if __name__ == "__main__":
    main()
