"""Apply the author's review of the implicit-distress queries to the frozen file.

The ten queries in data/eval/retrieval_queries_implicit.jsonl were labelled by a
model and frozen (SHA-256 below) before anything was run on them. Their labels
count only once the author has reviewed them, in the checklist in
docs/REVIEW_implicit_retrieval_queries.md. This reads that checklist and:

- refuses unless the jsonl is still the frozen file (or an earlier review of it),
  so a review is always applied to what was pre-registered;
- checks every chunk id against the knowledge base, so a typo cannot become a
  label;
- prints every change against the frozen labels, so the review is on record;
- writes the reviewed labels, marking each row `author-reviewed`.

Usage:
    python scripts/apply_query_review.py --check   # show what would change, write nothing
    python scripts/apply_query_review.py           # apply it
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

JSONL = REPO / "data" / "eval" / "retrieval_queries_implicit.jsonl"
REVIEW = REPO / "docs" / "REVIEW_implicit_retrieval_queries.md"
FROZEN_SHA256 = "3d23dbf131067655348ce998d471069d67385b84614b69a842122d62688a68f3"
PREFIX = {
    "01": "01_academic_stress.md",
    "02": "02_coping_strategies.md",
    "03": "03_support_resources_vietnam.md",
    "04": "04_sleep_and_study.md",
    "05": "05_dass_pss_scales.md",
    "06": "06_family_financial_pressure.md",
}
SHORT_ID = re.compile(r"\b(\d{2})::(\d+)\b")


def _full(prefix: str, n: str) -> str:
    if prefix not in PREFIX:
        raise ValueError(f"unknown chunk prefix {prefix}::{n}")
    return f"{PREFIX[prefix]}::{n}"


def parse_review(markdown: str) -> tuple[dict[int, set[str]], str]:
    """Reviewed labels per query id, and the support-reach definition chosen.

    A ticked box keeps its label, an unticked one drops it, and ids after `Add:`
    are added. Exactly one of the two definitions must be ticked.
    """
    decision = markdown.split("## One decision before the run", 1)[-1].split("\n## ", 1)[0]
    keep = re.search(r"^- \[([ xX])\] Keep the pre-registered definition", decision, re.M)
    extend = re.search(r"^- \[([ xX])\] Also count", decision, re.M)
    if not keep or not extend:
        raise ValueError("the support-definition decision is missing from the review")
    ticked = [name for name, m in (("preregistered", keep), ("extended", extend)) if m.group(1) in "xX"]
    if len(ticked) != 1:
        raise ValueError(f"tick exactly one support definition, found {len(ticked)}")

    labels: dict[int, set[str]] = {}
    sections = re.split(r"^### Query (\d+)[^\n]*$", markdown, flags=re.M)
    for qid, body in zip(sections[1::2], sections[2::2], strict=True):
        body = body.split("\n## ", 1)[0]
        chosen: set[str] = set()
        for mark, prefix, n in re.findall(r"^- \[([ xX])\] `(\d{2})::(\d+)`", body, re.M):
            if mark in "xX":
                chosen.add(_full(prefix, n))
        for line in re.findall(r"^Add:(.*)$", body, re.M):
            chosen |= {_full(p, n) for p, n in SHORT_ID.findall(line)}
        if not chosen:
            raise ValueError(f"query {qid} has no relevant chunk left; a query needs at least one")
        labels[int(qid)] = chosen
    if not labels:
        raise ValueError("no '### Query N' sections found in the review")
    return labels, ticked[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Print the changes; write nothing.")
    args = parser.parse_args()

    raw = JSONL.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    frozen = hashlib.sha256(raw).hexdigest() == FROZEN_SHA256
    if not frozen and not all(r.get("labels") == "author-reviewed" for r in rows):
        raise SystemExit("The jsonl is neither the frozen pre-registered file nor a reviewed one. Refusing.")

    labels, definition = parse_review(REVIEW.read_text(encoding="utf-8"))
    ids = {r["id"] for r in rows}
    if set(labels) != ids:
        raise SystemExit(f"review covers queries {sorted(labels)}, the file has {sorted(ids)}")

    from app.rag.ingest import load_knowledge_chunks

    known = {c.chunk_id for c in load_knowledge_chunks()}
    unknown = sorted(set().union(*labels.values()) - known)
    if unknown:
        raise SystemExit(f"not chunks in the knowledge base: {unknown}")

    print(f"Applying to the {'frozen' if frozen else 'previously reviewed'} file. "
          f"Support-reach definition: {definition}.\n")
    changed = 0
    for row in rows:
        before, after = set(row["relevant"]), labels[row["id"]]
        dropped, added = sorted(before - after), sorted(after - before)
        if dropped or added:
            changed += 1
            print(f"  #{row['id']}: " + "; ".join(
                ([f"dropped {', '.join(dropped)}"] if dropped else []) +
                ([f"added {', '.join(added)}"] if added else [])))
        row["relevant"] = sorted(after)
        row["labels"] = "author-reviewed"
    print(f"\n{changed} of {len(rows)} queries changed; the rest were accepted as proposed.")

    if args.check:
        print("--check: nothing written.")
        return 0
    stamp = dt.date.today().isoformat()
    for row in rows:
        row["reviewed_on"] = stamp
    JSONL.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"Wrote {JSONL.relative_to(REPO)}; commit it with the review so the change is on record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
