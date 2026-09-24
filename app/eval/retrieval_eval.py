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


def run_production_queries(queries: list[Query], max_k: int) -> list[QueryOutcome]:
    """The natural queries as the deployed service actually sends them.

    `run_queries` scores the set as written: raw sentences, plus the `keywords`
    queries, which reproduce a shape production retired on 2026-09-06. Neither is
    what `build_rag_query()` sends. Until 2026-09-24 the report led with that
    mixed figure (MRR 0.787) as though it described the deployed system; the
    production form scored 0.843. This is the number the report now leads with.
    """
    outcomes: list[QueryOutcome] = []
    for query in queries:
        if query.style != "natural":
            continue
        docs = retrieve(as_production_query(query.query), k=max_k)
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
    production_outcomes = run_production_queries(queries, max_k=max(ks))
    # The sweep skips k=4, so the deployed depth is added for this aggregate.
    production = (
        aggregate(production_outcomes, tuple(sorted(set(ks) | {PRODUCTION_K})))
        if production_outcomes
        else None
    )

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
        "production": production,
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

    lines = ["# Retrieval quality evaluation", ""]
    production = results.get("production")
    if production:
        lines += [
            f"**Deployed query form: MRR = {production['mrr']:.3f}, "
            f"Recall@{PRODUCTION_K} = {production['recall_at'][PRODUCTION_K]:.3f}, "
            f"{len(production['misses_at_production_k'])} of {production['n_queries']} queries "
            f"with no relevant chunk in the top {PRODUCTION_K}.**",
            "",
            f"That is the {production['n_queries']} natural queries passed through "
            "`build_rag_query()`, as the deployed service sends them, at the deployed "
            f"depth k = {PRODUCTION_K}. It is the figure that describes the system.",
            "",
        ]
    lines += [
        f"## Query set as written ({overall['n_queries']} queries, MRR = {overall['mrr']:.3f})",
        "",
        "Raw sentences, plus the `keywords` queries, which reproduce the query shape "
        "production retired on 2026-09-06 and are kept as a regression guard. "
        "**This is not a measure of the deployed system** — no production query takes "
        "either form — and the headline above should be quoted instead.",
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

    def _miss_lines(miss_list: list[QueryOutcome]) -> list[str]:
        out: list[str] = []
        if not miss_list:
            out.append("(none)")
        for outcome in miss_list:
            q = outcome.query
            out.append(f"- **#{q.id}** [{q.style}/{q.lang}] “{q.query}”")
            out.append(f"  - expected: {', '.join(sorted(q.relevant))}")
            out.append(
                "  - got: "
                + (", ".join(outcome.retrieved[:PRODUCTION_K]) if outcome.retrieved else "(nothing)")
            )
            if q.note:
                out.append(f"  - note: {q.note}")
        return out

    if production:
        prod_misses = production["misses_at_production_k"]
        lines += [
            f"## Deployed form: queries with no relevant chunk in the top {PRODUCTION_K} "
            f"({len(prod_misses)})",
            "",
        ]
        lines += _miss_lines(prod_misses)
        lines.append("")

    misses = overall["misses_at_production_k"]
    lines += [
        f"## As written: queries with no relevant chunk in the top {PRODUCTION_K} ({len(misses)})",
        "",
    ]
    lines += _miss_lines(misses)

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


# Passages a suggestion can be grounded in: the four coping groups and the
# sleep-hygiene tips. The others describe stress or the scales, which explains
# a result but gives rule 4 nothing to recommend.
ACTIONABLE_CHUNKS = frozenset({
    "02_coping_strategies.md::0",
    "02_coping_strategies.md::1",
    "02_coping_strategies.md::2",
    "02_coping_strategies.md::3",
    "04_sleep_and_study.md::2",
})
# The coping group that answers each elevated DASS subscale.
SUBSCALE_CHUNK = {
    "stress": "02_coping_strategies.md::0",
    "anxiety": "02_coping_strategies.md::2",
    "depression": "02_coping_strategies.md::3",
}


def questionnaire_branch_eval() -> dict:
    """Old vs current query for submissions with no free text.

    The query set above is all text-derived, so this branch needs its own
    measure. Every combination of the three DASS subscales at Normal, Moderate
    and Severe (27 profiles) is sent through both constructions. Two questions:
    how much of the top k can ground a suggestion at all, and does the coping
    group matching each elevated subscale reach the top k. The relevance sets are
    defined by section headings, so this checks topical routing, not quality.
    """
    import itertools

    from app.api.services import questionnaire_query
    from app.schemas.models import Dass21Scores, QuestionnaireResult
    from app.scoring import derive_ground_truth

    arms: dict[str, dict] = {
        "old": {"actionable": [], "matched": [], "sets": set()},
        "current": {"actionable": [], "matched": [], "sets": set()},
    }
    levels = ("Normal", "Moderate", "Severe")
    for dep, anx, st in itertools.product(levels, repeat=3):
        label = derive_ground_truth(dass_stress_severity=st)
        q = QuestionnaireResult(
            dass21=Dass21Scores(
                depression_score=0, anxiety_score=0, stress_score=0,
                depression_level=dep, anxiety_level=anx, stress_level_dass=st, overall_severity=st,
            ),
            ground_truth_label=label,
        )
        elevated = [name for name, lvl in (("depression", dep), ("anxiety", anx), ("stress", st)) if lvl != "Normal"]
        for arm, query in (("old", f"student with {label} stress"), ("current", questionnaire_query(q))):
            ids = [d.chunk_id for d in retrieve(query, k=PRODUCTION_K)]
            arms[arm]["actionable"].append(sum(i in ACTIONABLE_CHUNKS for i in ids) / PRODUCTION_K)
            arms[arm]["matched"] += [SUBSCALE_CHUNK[name] in ids for name in elevated]
            arms[arm]["sets"].add(frozenset(ids))
    return {
        arm: {
            "profiles": 27,
            "actionable_share": _mean(v["actionable"]),
            "matched_rate": _mean([float(m) for m in v["matched"]]),
            "n_elevated": len(v["matched"]),
            "distinct_sets": len(v["sets"]),
        }
        for arm, v in arms.items()
    }


def format_questionnaire_branch(result: dict) -> str:
    old, cur = result["old"], result["current"]
    return "\n".join([
        "## Questionnaire-only submissions (no free text)",
        "",
        "27 DASS profiles (each subscale Normal / Moderate / Severe), top "
        f"{PRODUCTION_K}. *Actionable* = a coping-group or sleep-hygiene passage, the only "
        "kind rule 4 can turn into a suggestion. *Matched* = the coping group for an elevated "
        "subscale is retrieved (stress → time management, anxiety → regulating emotions, "
        "depression → social support).",
        "",
        "| query construction | actionable share of top 4 | matched subscale reached | distinct top-4 sets |",
        "|---|---:|---:|---:|",
        f"| old: `student with <label> stress` | {old['actionable_share']:.0%} | "
        f"{old['matched_rate']:.0%} of {old['n_elevated']} | {old['distinct_sets']} |",
        f"| current: `questionnaire_query()` | {cur['actionable_share']:.0%} | "
        f"{cur['matched_rate']:.0%} of {cur['n_elevated']} | {cur['distinct_sets']} |",
        "",
        "Relevance here is defined by section headings rather than by independent labels, so "
        "this measures whether the query reaches the right section, not how good the advice is.",
        "",
    ])


THRESHOLD_GRID = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)


def threshold_analysis(queries: list[Query], thresholds: tuple[float, ...] = THRESHOLD_GRID) -> dict:
    """Would a cosine-distance cut-off on the top-k improve what is retrieved?

    Scored on the natural queries in their production form, at production k.
    A threshold earns its place only if it removes irrelevant passages while
    keeping relevant ones and without emptying results: an emptied result makes
    the service withhold advice, so every emptied query is a student who gets
    none. AUROC summarises how well distance alone separates the two groups
    before any particular cut-off is chosen.
    """
    from sklearn.metrics import roc_auc_score

    hits: list[tuple[int, float, bool]] = []  # (query index, distance, relevant)
    for i, q in enumerate(q for q in queries if q.style == "natural"):
        for doc in retrieve(as_production_query(q.query), k=PRODUCTION_K):
            hits.append((i, doc.distance, doc.chunk_id in q.relevant))
    n_queries = len({i for i, _, _ in hits})
    relevant = [d for _, d, r in hits if r]
    irrelevant = [d for _, d, r in hits if not r]

    def pct(values: list[float], p: float) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, int(p * len(ordered)))] if ordered else float("nan")

    rows = []
    for t in thresholds:
        kept = [(i, d, r) for i, d, r in hits if d <= t]
        kept_queries = {i for i, _, _ in kept}
        had_relevant = {i for i, _, r in hits if r}
        keeps_relevant = {i for i, _, r in kept if r}
        rows.append(
            {
                "threshold": t,
                "irrelevant_removed": 1 - sum(1 for _, _, r in kept if not r) / max(1, len(irrelevant)),
                "relevant_removed": 1 - sum(1 for _, _, r in kept if r) / max(1, len(relevant)),
                "queries_emptied": n_queries - len(kept_queries),
                "queries_losing_all_relevant": len(had_relevant - keeps_relevant),
            }
        )
    labels = [r for _, _, r in hits]
    return {
        "n_queries": n_queries,
        "n_hits": len(hits),
        "relevant": {"n": len(relevant), "p10": pct(relevant, 0.1), "median": pct(relevant, 0.5), "p90": pct(relevant, 0.9)},
        "irrelevant": {"n": len(irrelevant), "p10": pct(irrelevant, 0.1), "median": pct(irrelevant, 0.5), "p90": pct(irrelevant, 0.9)},
        # Lower distance should mean relevant, hence the negation.
        "auroc": roc_auc_score(labels, [-d for _, d, _ in hits]) if 0 < sum(labels) < len(labels) else float("nan"),
        "rows": rows,
    }


def format_threshold_analysis(result: dict) -> str:
    rel, irr = result["relevant"], result["irrelevant"]
    lines = [
        "## Similarity threshold: measured, not adopted",
        "",
        f"{result['n_queries']} natural queries in production form, top {PRODUCTION_K}, "
        f"{result['n_hits']} retrieved passages. Cosine distance of relevant passages: median "
        f"{rel['median']:.3f} (p10 {rel['p10']:.3f}, p90 {rel['p90']:.3f}, n = {rel['n']}); of "
        f"irrelevant ones: median {irr['median']:.3f} (p10 {irr['p10']:.3f}, p90 {irr['p90']:.3f}, "
        f"n = {irr['n']}). **AUROC of distance as a relevance signal: {result['auroc']:.3f}.**",
        "",
        "| cut-off | irrelevant removed | relevant removed | queries emptied | queries losing every relevant hit |",
        "|---:|---:|---:|---:|---:|",
    ]
    for r in result["rows"]:
        lines.append(
            f"| {r['threshold']:.2f} | {r['irrelevant_removed']:.0%} | {r['relevant_removed']:.0%} | "
            f"{r['queries_emptied']} | {r['queries_losing_all_relevant']} |"
        )
    lines += [
        "",
        "An emptied query means the service withholds advice for that student, and a query that "
        "loses every relevant hit keeps only irrelevant ones. A cut-off is worth adopting only if "
        "it removes many irrelevant passages while doing neither; read the table against that "
        "standard. Downstream, the irrelevant passages that stay in the top 4 do not surface as "
        "ungrounded advice: the faithfulness judge found 99 % of generated suggestions supported "
        "at least partially (`faithfulness_eval.md`).",
        "",
    ]
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
    report += "\n" + format_questionnaire_branch(questionnaire_branch_eval())
    report += "\n" + format_threshold_analysis(threshold_analysis(queries))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
