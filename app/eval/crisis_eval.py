"""Evaluate the deterministic crisis-detection rule against a labeled test set.

Test sets, both hand-written, same schema:

    data/eval/crisis_testset.jsonl     50 Vietnamese items
    data/eval/crisis_testset_en.jsonl  50 English items (added 2026-09-09)

The English set exists because the application was converted to English on
2026-09-05 while the rule had only ever been measured on Vietnamese input. The
lexicon is bilingual, but its English half had never been evaluated - the
measured precision and recall described a language the deployed application no
longer accepts by default.

Each set covers explicit and indirect risk phrasing, hyperbole hard negatives,
and borderline cases carrying annotation notes. Each line:

    {"id": int, "text": str, "expected": bool, "category": str,
     "dass_items": {"17": 3, ...}?, "note": str?}

Reports precision/recall/F1 for the positive (crisis) class, a per-category
breakdown, and EVERY false positive and false negative verbatim.

The rule must NOT be tuned against this set; the point is to measure it.

Usage:
    python -m app.eval.crisis_eval
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import PROJECT_ROOT
from app.llm.safety import check_crisis
from app.scoring.dass21 import score_dass21

DEFAULT_TESTSET = PROJECT_ROOT / "data" / "eval" / "crisis_testset.jsonl"


@dataclass
class Item:
    id: int
    text: str
    expected: bool
    category: str
    dass_items: dict[int, int] | None = None
    note: str | None = None


def load_testset(path: Path = DEFAULT_TESTSET) -> list[Item]:
    items: list[Item] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        dass = data.get("dass_items")
        items.append(
            Item(
                id=int(data["id"]),
                text=data["text"],
                expected=bool(data["expected"]),
                category=data["category"],
                dass_items={int(k): int(v) for k, v in dass.items()} if dass else None,
                note=data.get("note"),
            )
        )
    return items


def predict(item: Item) -> bool:
    """Run the production crisis rule exactly as the API would."""
    depression_severity = None
    if item.dass_items and set(item.dass_items.keys()) == set(range(1, 22)):
        depression_severity = score_dass21(item.dass_items)["depression"]["severity"]
    result = check_crisis(
        raw_text=item.text,
        dass_answers=item.dass_items,
        dass_depression_severity=depression_severity,
    )
    return result.is_crisis


def evaluate(items: list[Item], testset: str = "(unnamed)") -> dict:
    tp = fp = fn = tn = 0
    false_positives: list[Item] = []
    false_negatives: list[Item] = []
    per_category: dict[str, dict[str, int]] = {}

    for item in items:
        predicted = predict(item)
        bucket = per_category.setdefault(item.category, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if predicted and item.expected:
            tp += 1
            bucket["correct"] += 1
        elif predicted and not item.expected:
            fp += 1
            false_positives.append(item)
        elif not predicted and item.expected:
            fn += 1
            false_negatives.append(item)
        else:
            tn += 1
            bucket["correct"] += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "testset": testset,
        "n": len(items),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "per_category": per_category,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def format_report(results: dict) -> str:
    lines = [
        "# Crisis-detection rule evaluation",
        "",
        f"Test set: `{results['testset']}` - {results['n']} hand-written items "
        f"(TP={results['tp']} FP={results['fp']} FN={results['fn']} TN={results['tn']})",
        "",
        "| metric | value |",
        "|---|---|",
        f"| precision | {results['precision']:.3f} |",
        f"| recall | {results['recall']:.3f} |",
        f"| F1 | {results['f1']:.3f} |",
        "",
        "## Per-category accuracy",
        "",
        "| category | correct/total |",
        "|---|---|",
    ]
    for category, bucket in sorted(results["per_category"].items()):
        lines.append(f"| {category} | {bucket['correct']}/{bucket['total']} |")

    lines += ["", f"## False positives ({len(results['false_positives'])})", ""]
    if not results["false_positives"]:
        lines.append("(none)")
    for item in results["false_positives"]:
        lines.append(f"- **#{item.id}** [{item.category}] “{item.text}”")
        if item.note:
            lines.append(f"  - note: {item.note}")

    lines += ["", f"## False negatives ({len(results['false_negatives'])})", ""]
    if not results["false_negatives"]:
        lines.append("(none)")
    for item in results["false_negatives"]:
        lines.append(f"- **#{item.id}** [{item.category}] “{item.text}”")
        if item.note:
            lines.append(f"  - note: {item.note}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testset", default=str(DEFAULT_TESTSET))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "eval" / "crisis_eval.md"))
    args = parser.parse_args()

    items = load_testset(Path(args.testset))
    results = evaluate(items, testset=Path(args.testset).name)
    report = format_report(results)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
