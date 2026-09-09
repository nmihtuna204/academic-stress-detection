"""Evaluate retrieval quality against a labelled query set.

Query set: `data/eval/retrieval_queries.jsonl` - hand-written queries, each
labelled with the chunk ids that genuinely answer it. Each line:

    {"id": int, "style": "natural"|"keywords", "lang": "en"|"vi",
     "query": str, "relevant": [chunk_id, ...], "note": str?}

Reports Recall@k, Precision@k, MRR and nDCG@k over a sweep of k, broken down by
query style and language, and lists EVERY query for which no relevant chunk was
retrieved. Binary relevance (a chunk either answers the query or it does not),
so every gain is 1 and IDCG is the ideal ordering of the labelled set.

Two things this measurement does NOT establish, stated here so they are not
inferred from the numbers:

- **Faithfulness.** This scores whether the right passages were *retrieved*, not
  whether the generator actually *used* them. That needs an LLM-as-judge pass
  and a live API key.
- **Annotator independence.** The corpus, the queries and the relevance labels
  were all produced within this project, with a single annotator and therefore
  no inter-annotator agreement. Treat the absolute values as a sanity check on
  the retrieval configuration, not as a benchmark result.

The `keywords` queries reproduce the shape `build_rag_query()` emitted *before*
the 2026-09-06 rewrite: lexicon keywords replacing the student's sentence, plus a
questionnaire label. They are retained because the paired comparison at the end
of the report uses them to show what that construction cost, and to guard against
it being reintroduced. Production now retrieves on the sentence itself with the
keywords appended, which that comparison measured as the better arm.

Usage:
    python -m app.eval.retrieval_eval
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from app.config import PROJECT_ROOT
from app.rag.retriever import retrieve

DEFAULT_QUERYSET = PROJECT_ROOT / "data" / "eval" / "retrieval_queries.jsonl"
K_SWEEP = (1, 3, 5, 8)
# k used by the production pipeline (see services.run_full_assessment).
PRODUCTION_K = 4


@dataclass
class Query:
    id: int
    query: str
    relevant: set[str]
    style: str
    lang: str
    note: str | None = None


@dataclass
class QueryOutcome:
    query: Query
    retrieved: list[str] = field(default_factory=list)

    def first_relevant_rank(self) -> int | None:
        """1-based rank of the first relevant chunk, or None if never retrieved."""
        for rank, chunk_id in enumerate(self.retrieved, start=1):
            if chunk_id in self.query.relevant:
                return rank
        return None

    def recall_at(self, k: int) -> float:
        if not self.query.relevant:
            return 0.0
        hits = len(set(self.retrieved[:k]) & self.query.relevant)
        return hits / len(self.query.relevant)

    def precision_at(self, k: int) -> float:
        if k == 0:
            return 0.0
        hits = len(set(self.retrieved[:k]) & self.query.relevant)
        return hits / k

    def ndcg_at(self, k: int) -> float:
        """Binary-gain nDCG: DCG over the returned order against the ideal order."""
        dcg = sum(
            1.0 / math.log2(rank + 1)
            for rank, chunk_id in enumerate(self.retrieved[:k], start=1)
            if chunk_id in self.query.relevant
        )
        ideal_hits = min(len(self.query.relevant), k)
        idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        return dcg / idcg if idcg else 0.0


def load_queryset(path: Path = DEFAULT_QUERYSET) -> list[Query]:
    queries: list[Query] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        queries.append(
            Query(
                id=int(data["id"]),
                query=data["query"],
                relevant=set(data["relevant"]),
                style=data.get("style", "natural"),
                lang=data.get("lang", "en"),
                note=data.get("note"),
            )
        )
    return queries


def run_queries(queries: list[Query], max_k: int) -> list[QueryOutcome]:
    """Retrieve once per query at the deepest k, then slice for the sweep.

    Retrieval is rank-stable, so the top-k for any smaller k is a prefix of the
    top-max_k list. Running the embedder once per query rather than once per k
    keeps the evaluation cheap and removes any chance of the sweep points
    disagreeing with each other.
    """
    outcomes: list[QueryOutcome] = []
    for query in queries:
        docs = retrieve(query.query, k=max_k)
        outcomes.append(QueryOutcome(query=query, retrieved=[d.chunk_id for d in docs]))
    return outcomes


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(outcomes: list[QueryOutcome], ks: tuple[int, ...] = K_SWEEP) -> dict:
    """Mean metrics over a set of outcomes, plus the complete miss list."""
    ranks = [o.first_relevant_rank() for o in outcomes]
    mrr = _mean([1.0 / r for r in ranks if r is not None] + [0.0 for r in ranks if r is None])

    return {
        "n_queries": len(outcomes),
        "mrr": round(mrr, 4),
        "recall_at": {k: round(_mean([o.recall_at(k) for o in outcomes]), 4) for k in ks},
        "precision_at": {k: round(_mean([o.precision_at(k) for o in outcomes]), 4) for k in ks},
        "ndcg_at": {k: round(_mean([o.ndcg_at(k) for o in outcomes]), 4) for k in ks},
        "misses_at_production_k": [
            o for o in outcomes if o.recall_at(PRODUCTION_K) == 0.0
        ],
    }


def evaluate(queries: list[Query], ks: tuple[int, ...] = K_SWEEP) -> dict:
    outcomes = run_queries(queries, max_k=max(ks))
    overall = aggregate(outcomes, ks)

    by_style: dict[str, dict] = {}
    for style in sorted({o.query.style for o in outcomes}):
        by_style[style] = aggregate([o for o in outcomes if o.query.style == style], ks)

    by_lang: dict[str, dict] = {}
    for lang in sorted({o.query.lang for o in outcomes}):
        by_lang[lang] = aggregate([o for o in outcomes if o.query.lang == lang], ks)

    # Chunks that no query ever surfaced in the top-k: dead corpus regions.
    surfaced: set[str] = set()
    for o in outcomes:
        surfaced.update(o.retrieved[:PRODUCTION_K])
    labelled: set[str] = set()
    for q in queries:
        labelled.update(q.relevant)

    return {
        "overall": overall,
        "by_style": by_style,
        "by_lang": by_lang,
        "outcomes": outcomes,
        "ks": ks,
        "never_surfaced": sorted(labelled - surfaced),
    }


def _metric_table(stats: dict, ks: tuple[int, ...]) -> list[str]:
    lines = ["| k | Recall@k | Precision@k | nDCG@k |", "|---:|---:|---:|---:|"]
    for k in ks:
        lines.append(
            f"| {k} | {stats['recall_at'][k]:.3f} | "
            f"{stats['precision_at'][k]:.3f} | {stats['ndcg_at'][k]:.3f} |"
        )
    return lines


def format_report(results: dict) -> str:
    ks = results["ks"]
    overall = results["overall"]

    lines = [
        "# Retrieval quality evaluation",
        "",
        f"Query set: {overall['n_queries']} hand-labelled queries over the "
        "knowledge corpus, scored against the production `retrieve()` path.",
        "",
        f"**MRR = {overall['mrr']:.3f}**  ·  production k = {PRODUCTION_K}",
        "",
        "## Overall",
        "",
    ]
    lines += _metric_table(overall, ks)

    lines += ["", "## By query style", ""]
    for style, stats in results["by_style"].items():
        lines += [
            f"### {style} (n = {stats['n_queries']}, MRR = {stats['mrr']:.3f})",
            "",
        ]
        lines += _metric_table(stats, ks)
        lines.append("")

    lines += ["## By query language", ""]
    for lang, stats in results["by_lang"].items():
        lines += [f"### {lang} (n = {stats['n_queries']}, MRR = {stats['mrr']:.3f})", ""]
        lines += _metric_table(stats, ks)
        lines.append("")

    misses = overall["misses_at_production_k"]
    lines += [f"## Queries with no relevant chunk in the top {PRODUCTION_K} ({len(misses)})", ""]
    if not misses:
        lines.append("(none)")
    for outcome in misses:
        q = outcome.query
        lines.append(f"- **#{q.id}** [{q.style}/{q.lang}] “{q.query}”")
        lines.append(f"  - expected: {', '.join(sorted(q.relevant))}")
        lines.append(
            "  - got: "
            + (", ".join(outcome.retrieved[:PRODUCTION_K]) if outcome.retrieved else "(nothing)")
        )
        if q.note:
            lines.append(f"  - note: {q.note}")

    lines += ["", "## Labelled chunks never surfaced by any query", ""]
    if results["never_surfaced"]:
        for chunk_id in results["never_surfaced"]:
            lines.append(f"- {chunk_id}")
    else:
        lines.append("(none - every labelled chunk was retrieved for at least one query)")

    lines += [
        "",
        "## Scope of this measurement",
        "",
        "- Retrieval only. Whether the generator *used* the retrieved passages is a "
        "faithfulness question and is not measured here; it needs an LLM-as-judge pass "
        "and a live API key.",
        "- Corpus, queries and relevance labels all originate within this project, with a "
        "single annotator and therefore no inter-annotator agreement.",
        "- Binary relevance, so nDCG rewards ordering but not degrees of usefulness.",
        "",
    ]
    return "\n".join(lines) + "\n"


def as_legacy_query(query: str) -> str:
    """Reproduce the query construction used before the 2026-09-06 rewrite.

    The old path did not retrieve on the student's sentence: it ran the lexicon
    over the text and retrieved on the matched keywords instead, falling back to
    the raw text only when nothing matched. Kept so the harness can show the
    before/after rather than asserting the improvement.
    """
    from app.nlp.lexicon import find_stress_keywords

    keywords = find_stress_keywords(query)
    return " ".join(keywords) if keywords else query[:300]


def as_production_query(query: str) -> str:
    """What the current `build_rag_query()` sends for this student text.

    Calls the production helper rather than restating it, so the comparison
    cannot drift away from the deployed behaviour.
    """
    from app.api.services import build_rag_query
    from app.nlp.lexicon import find_stress_keywords
    from app.schemas.models import EmotionResult

    emotion = EmotionResult(
        emotion_label="eval",
        emotion_scores={},
        sentiment_polarity="neutral",
        stress_keywords=find_stress_keywords(query),
    )
    return build_rag_query(query, emotion, None)


def compare_query_construction(queries: list[Query], ks: tuple[int, ...] = K_SWEEP) -> dict:
    """Paired comparison of the old and current query construction.

    Same queries, same relevance labels, same retriever - only the query string
    differs. This isolates the effect of the transformation itself, which a
    between-groups comparison of differently-written queries cannot do.
    """
    natural = [q for q in queries if q.style == "natural"]
    transformed = [
        Query(
            id=q.id,
            query=as_legacy_query(q.query),
            relevant=q.relevant,
            style=q.style,
            lang=q.lang,
        )
        for q in natural
    ]
    current = [
        Query(
            id=q.id,
            query=as_production_query(q.query),
            relevant=q.relevant,
            style=q.style,
            lang=q.lang,
        )
        for q in natural
    ]
    # Queries that matched no lexicon keyword pass through unchanged, so averaging
    # over all of them dilutes the effect. The affected subset is where the
    # transformation actually does something, and is the honest estimate of its
    # cost when it fires.
    affected_idx = [
        i for i, (q, t) in enumerate(zip(natural, transformed)) if t.query != q.query[:300]
    ]

    result = {
        "n_paired": len(natural),
        "n_reduced_to_keywords": len(affected_idx),
        "as_written": aggregate(run_queries(natural, max_k=max(ks)), ks),
        "as_legacy": aggregate(run_queries(transformed, max_k=max(ks)), ks),
        "as_current": aggregate(run_queries(current, max_k=max(ks)), ks),
        "ks": ks,
    }
    if affected_idx:
        result["affected_as_written"] = aggregate(
            run_queries([natural[i] for i in affected_idx], max_k=max(ks)), ks
        )
        result["affected_as_legacy"] = aggregate(
            run_queries([transformed[i] for i in affected_idx], max_k=max(ks)), ks
        )
        result["affected_as_current"] = aggregate(
            run_queries([current[i] for i in affected_idx], max_k=max(ks)), ks
        )
    return result


def _comparison_table(ks: tuple[int, ...], written: dict, legacy: dict, current: dict) -> list[str]:
    lines = [
        "| Metric | Student's sentence | Old construction | Current construction | Δ vs old |",
        "|---|---:|---:|---:|---:|",
        f"| MRR | {written['mrr']:.3f} | {legacy['mrr']:.3f} | {current['mrr']:.3f} | "
        f"{current['mrr'] - legacy['mrr']:+.3f} |",
    ]
    for metric, label in (("recall_at", "Recall"), ("ndcg_at", "nDCG")):
        for k in ks:
            base, old_v, new_v = written[metric][k], legacy[metric][k], current[metric][k]
            lines.append(
                f"| {label}@{k} | {base:.3f} | {old_v:.3f} | {new_v:.3f} | {new_v - old_v:+.3f} |"
            )
    return lines


def format_comparison(comparison: dict) -> str:
    ks = comparison["ks"]
    lines = [
        "## Paired comparison: query construction, before and after",
        "",
        f"Same {comparison['n_paired']} queries and the same relevance labels, retrieved under "
        "three query constructions. Only the query string differs, so the effect is attributable "
        "to the transformation rather than to how the queries were written.",
        "",
        "- **Student's sentence** — the query exactly as written, an upper reference point.",
        "- **Old construction** — replaced the sentence with matched lexicon keywords and "
        "appended a questionnaire label.",
        "- **Current construction** — keeps the sentence, appends the keywords, drops the label. "
        "Chosen by this measurement.",
        "",
        f"{comparison['n_reduced_to_keywords']} of {comparison['n_paired']} queries matched a "
        "lexicon keyword; the rest pass through unchanged under every arm and dilute the mean.",
        "",
    ]
    lines += _comparison_table(
        ks, comparison["as_written"], comparison["as_legacy"], comparison["as_current"]
    )
    lines.append("")

    if "affected_as_written" in comparison:
        lines += [
            f"### Restricted to the {comparison['n_reduced_to_keywords']} queries the "
            "construction actually changes",
            "",
            "This is the effect where it actually fires.",
            "",
        ]
        lines += _comparison_table(
            ks,
            comparison["affected_as_written"],
            comparison["affected_as_legacy"],
            comparison["affected_as_current"],
        )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queryset", default=str(DEFAULT_QUERYSET))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "eval" / "retrieval_eval.md"))
    args = parser.parse_args()

    queries = load_queryset(Path(args.queryset))
    results = evaluate(queries)
    report = format_report(results)
    report += "\n" + format_comparison(compare_query_construction(queries))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
