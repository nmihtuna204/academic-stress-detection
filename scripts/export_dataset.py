"""Export the application SQLite DB to one analysis-ready CSV.

Produces `data/real/dataset.csv` in exactly the schema the evaluation scripts
consume (same columns as `data/eval/dataset_synthetic.csv`), so
`python -m app.eval.compare --dataset real` works unchanged.

Privacy: only the anonymized UUID, the free text, questionnaire items/scores,
and derived labels are exported. Demographics (age, gender, major, university)
and any other quasi-identifying fields are deliberately NOT exported.

Per student: the latest text entry and the latest questionnaire response that
has at least one completed instrument. Rows without any questionnaire are
skipped (no ground-truth label can be derived).

Usage:
    python scripts/export_dataset.py                    # export only
    python scripts/export_dataset.py --split            # + stratified train/test
    python scripts/export_dataset.py --drop-incomplete  # drop rows missing text
                                                        #   or either instrument
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlalchemy import select

from app.config import PROJECT_ROOT
from app.db.database import get_session, init_db
from app.db.models import QuestionnaireResponse, TextEntry, User
from app.scoring import derive_ground_truth

DEFAULT_OUT = PROJECT_ROOT / "data" / "real" / "dataset.csv"

EXPORT_SEED = 42
TEST_FRACTION = 0.2


def collect_rows() -> list[dict]:
    """One row per student: latest text + latest scored questionnaire response."""
    init_db()
    session = next(get_session())
    try:
        users = session.scalars(select(User)).all()
        rows: list[dict] = []
        for user in users:
            responses = [
                r
                for r in session.scalars(
                    select(QuestionnaireResponse)
                    .where(QuestionnaireResponse.student_id == user.student_id)
                    .order_by(QuestionnaireResponse.created_at.desc())
                ).all()
                if r.stress_level_dass is not None or r.pss_stress_category is not None
            ]
            if not responses:
                continue  # no ground-truth label derivable
            response = responses[0]

            entry = session.scalars(
                select(TextEntry)
                .where(TextEntry.student_id == user.student_id)
                .order_by(TextEntry.timestamp.desc())
            ).first()

            row: dict = {
                "student_id": user.student_id,
                "text": entry.raw_text if entry else None,
                "label": derive_ground_truth(
                    dass_stress_severity=response.stress_level_dass,
                    pss_category=response.pss_stress_category,
                ),
            }
            for i in range(1, 22):
                row[f"dass21_q{i}"] = getattr(response, f"dass_q{i}")
            for i in range(1, 11):
                row[f"pss_q{i}"] = getattr(response, f"pss_q{i}")
            row["dass21_depression_severity"] = response.depression_level
            row["dass21_stress_severity"] = response.stress_level_dass
            row["pss_total_score"] = response.pss_total_score
            row["pss_stress_category"] = response.pss_stress_category
            rows.append(row)
        return rows
    finally:
        session.close()


def add_split(df: pd.DataFrame, seed: int = EXPORT_SEED) -> pd.DataFrame:
    """Stratified train/test split written into a 'split' column."""
    from sklearn.model_selection import train_test_split

    stratify = df["label"] if df["label"].value_counts().min() >= 2 else None
    if stratify is None:
        print("WARNING: some class has <2 members; split is random, not stratified.")
    train_idx, test_idx = train_test_split(
        df.index, test_size=TEST_FRACTION, random_state=seed, stratify=stratify
    )
    df = df.copy()
    df.loc[train_idx, "split"] = "train"
    df.loc[test_idx, "split"] = "test"
    return df


def summarize(df: pd.DataFrame) -> str:
    lines = [
        f"rows exported:        {len(df)}",
        f"class distribution:   {df['label'].value_counts().to_dict()}",
        f"missing free text:    {int(df['text'].isna().sum() + (df['text'].astype(str).str.strip() == '').sum())}",
        f"missing DASS-21:      {int(df['dass21_q1'].isna().sum())}",
        f"missing PSS-10:       {int(df['pss_q1'].isna().sum())}",
    ]
    if "split" in df.columns:
        lines.append(f"split sizes:          {df['split'].value_counts().to_dict()}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--split", action="store_true", help="add stratified train/test split column")
    parser.add_argument("--seed", type=int, default=EXPORT_SEED)
    parser.add_argument(
        "--drop-incomplete",
        action="store_true",
        help="drop rows missing free text or either instrument (needed for llm_full)",
    )
    args = parser.parse_args()

    rows = collect_rows()
    if not rows:
        raise SystemExit("No exportable rows: the database has no scored questionnaire responses.")

    df = pd.DataFrame(rows)
    if args.drop_incomplete:
        before = len(df)
        complete = (
            df["text"].notna()
            & (df["text"].astype(str).str.strip() != "")
            & df["dass21_q1"].notna()
            & df["pss_q1"].notna()
        )
        df = df[complete].reset_index(drop=True)
        print(f"Dropped {before - len(df)} incomplete rows ({len(df)} remain).")

    if args.split:
        df = add_split(df, seed=args.seed)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {out}")
    print(summarize(df))


if __name__ == "__main__":
    main()
