"""Data-quality report: flag suspect submissions in the application DB.

Checks per student (latest questionnaire response + latest text entry):

1. straight_line_dass   - all 21 DASS answers identical
2. straight_line_pss    - all 10 PSS answers identical (with items 4/5/7/8
                          reverse-scored, a straight-liner produces internally
                          contradictory content, so this is a strong signal)
3. short_text           - free text under 20 words (or missing entirely)
4. fast_completion      - questionnaire submitted implausibly soon after the
                          account was created (< 120s for 31 items + consent)
5. dass_pss_mismatch    - DASS stress level and PSS category at least two
                          unified levels apart (internally inconsistent report)

Flags are advisory: review flagged rows manually before excluding them, and
document any exclusion in the thesis.

Usage:
    python scripts/data_quality_report.py [--csv data/eval/quality_flags.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from sqlalchemy import select

from app.db.database import get_session, init_db
from app.db.models import QuestionnaireResponse, TextEntry, User

FAST_COMPLETION_SECONDS = 120
MIN_TEXT_WORDS = 20

# Unified severity indices for the mismatch check.
_DASS_INDEX = {"Normal": 0, "Mild": 1, "Moderate": 1, "Severe": 2, "Extremely Severe": 3}
_PSS_INDEX = {"Low": 0, "Moderate": 1, "High": 2}


def check_student(user: User, response: QuestionnaireResponse, entry: TextEntry | None) -> list[str]:
    flags: list[str] = []

    dass = [getattr(response, f"dass_q{i}") for i in range(1, 22)]
    if all(v is not None for v in dass) and len(set(dass)) == 1:
        flags.append("straight_line_dass")

    pss = [getattr(response, f"pss_q{i}") for i in range(1, 11)]
    if all(v is not None for v in pss) and len(set(pss)) == 1:
        flags.append("straight_line_pss")

    words = len(entry.raw_text.split()) if entry and entry.raw_text else 0
    if words < MIN_TEXT_WORDS:
        flags.append(f"short_text({words}w)")

    if response.created_at and user.created_at:
        elapsed = (response.created_at - user.created_at).total_seconds()
        if 0 <= elapsed < FAST_COMPLETION_SECONDS:
            flags.append(f"fast_completion({elapsed:.0f}s)")

    if response.stress_level_dass and response.pss_stress_category:
        gap = abs(
            _DASS_INDEX.get(response.stress_level_dass, 0)
            - _PSS_INDEX.get(response.pss_stress_category, 0)
        )
        if gap >= 2:
            flags.append(
                f"dass_pss_mismatch({response.stress_level_dass}/{response.pss_stress_category})"
            )
    return flags


def run() -> pd.DataFrame:
    init_db()
    session = next(get_session())
    try:
        users = session.scalars(select(User)).all()
        rows = []
        checked = 0
        for user in users:
            response = session.scalars(
                select(QuestionnaireResponse)
                .where(QuestionnaireResponse.student_id == user.student_id)
                .order_by(QuestionnaireResponse.created_at.desc())
            ).first()
            if response is None:
                continue
            entry = session.scalars(
                select(TextEntry)
                .where(TextEntry.student_id == user.student_id)
                .order_by(TextEntry.timestamp.desc())
            ).first()
            checked += 1
            flags = check_student(user, response, entry)
            if flags:
                rows.append(
                    {
                        "student_id": user.student_id,
                        "flags": ";".join(flags),
                        "n_flags": len(flags),
                        "created_at": user.created_at,
                    }
                )
        report = pd.DataFrame(rows)
        print(f"Checked {checked} students with questionnaire data; {len(rows)} flagged.")
        if not report.empty:
            flag_counts: dict[str, int] = {}
            for flags in report["flags"]:
                for flag in flags.split(";"):
                    base = flag.split("(")[0]
                    flag_counts[base] = flag_counts.get(base, 0) + 1
            print("Flag counts:", flag_counts)
            print(report.to_string(index=False, max_colwidth=60))
        return report
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=None, help="also write flagged rows to this CSV")
    args = parser.parse_args()

    report = run()
    if args.csv and not report.empty:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(out, index=False)
        print(f"Flagged rows written to {out}")


if __name__ == "__main__":
    main()
