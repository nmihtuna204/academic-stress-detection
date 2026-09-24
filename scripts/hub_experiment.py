"""Does the document title that ingest prepends to every chunk cause the coping pull?

Retrieval fills 35 % of its top-4 slots from `02_coping_strategies.md`, which is
22 % of the corpus. Ingest writes every chunk as `f"{title}\\n\\n{section}"`, and
that file's title, "Strategies for coping with academic stress", is close to a
paraphrase of the whole query distribution. This tests the idea directly.

    A  chunks embedded exactly as production ingests them (title + section)
    B  the same chunks with the document title removed

Both collections live in an in-memory Chroma client, so `data/chroma` is never
touched. `retrieve()` is pointed at each in turn, so the query path is
production's own. **A must reproduce the production MRR before anything about B
is read**; the script says so explicitly and exits non-zero if it does not.

The ten implicit-distress queries in `retrieval_queries_implicit.jsonl` are not
used: their labels await review, and running them first would compromise it.

Recorded result (2026-09-24), see docs/RESULTS.md §4b: the title is the main
cause of the source-level pull, removing it is not a fix, and it was not adopted.

Usage:
    python scripts/hub_experiment.py
"""

from __future__ import annotations

import collections
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb  # noqa: E402
import numpy as np  # noqa: E402

import app.rag.retriever as retriever  # noqa: E402
from app.eval.retrieval_eval import (  # noqa: E402
    PRODUCTION_K,
    load_queryset,
    questionnaire_branch_eval,
    run_production_queries,
)
from app.rag.ingest import load_knowledge_chunks  # noqa: E402
from app.rag.store import _get_embedding_function, embedding_model_name, get_collection  # noqa: E402

K = PRODUCTION_K
COPING = "02_coping_strategies.md"
ACADEMIC = "01_academic_stress.md"
HUB = "02_coping_strategies.md::4"


def _source(chunk_id: str) -> str:
    return chunk_id.split("::")[0]


def _strip_title(text: str) -> str:
    _title, rest = text.split("\n\n", 1)
    return rest


def _build(client, name: str, chunks, text_fn):
    col = client.create_collection(
        name, metadata={"hnsw:space": "cosine"}, embedding_function=_get_embedding_function()
    )
    col.add(
        ids=[c.chunk_id for c in chunks],
        documents=[text_fn(c.text) for c in chunks],
        metadatas=[{"source": c.source, "heading": c.heading, "embedding_model": embedding_model_name()}
                   for c in chunks],
    )
    return col


def _measure(natural, chunks) -> dict:
    outcomes = run_production_queries(natural, max_k=8)
    rr = np.array([1 / r if (r := o.first_relevant_rank()) else 0.0 for o in outcomes])
    slots = collections.Counter(_source(c) for o in outcomes for c in o.retrieved[:K])
    irrelevant = collections.Counter(
        _source(c) for o in outcomes for c in o.retrieved[:K] if c not in o.query.relevant
    )
    kocc = collections.Counter(c for o in outcomes for c in o.retrieved[:K])
    occ = [kocc.get(c.chunk_id, 0) for c in chunks]
    mean, sd = statistics.mean(occ), statistics.pstdev(occ)
    support = [o for o in outcomes if any(c.startswith("03_") for c in o.query.relevant)]
    branch = questionnaire_branch_eval()["current"]
    return {
        "rr": rr,
        "mrr": rr.mean(),
        "recall4": statistics.mean(o.recall_at(K) for o in outcomes),
        "misses": [o.query.id for o in outcomes if o.recall_at(K) == 0.0],
        "coping_share": slots[COPING] / sum(slots.values()),
        "coping_irrelevant": irrelevant[COPING] / sum(irrelevant.values()),
        "academic_share": slots[ACADEMIC] / sum(slots.values()),
        "hub": kocc[HUB],
        "skew": sum((x - mean) ** 3 for x in occ) / (len(occ) * sd**3),
        "support": f"{sum(any(c.startswith('03_') for c in o.retrieved[:K]) for o in support)}/{len(support)}",
        "actionable": branch["actionable_share"],
        "matched": branch["matched_rate"],
        "top4": {o.query.id: o.retrieved[:K] for o in outcomes},
    }


def main() -> int:
    chunks = load_knowledge_chunks()
    natural = [q for q in load_queryset() if q.style == "natural"]

    # The production number, measured against data/chroma, for the validity check.
    production_mrr = statistics.mean(
        1 / r if (r := o.first_relevant_rank()) else 0.0 for o in run_production_queries(natural, max_k=8)
    )
    labelled = collections.Counter(_source(c) for q in natural for c in q.relevant)
    corpus = collections.Counter(c.source for c in chunks)

    client = chromadb.EphemeralClient()
    variants = {
        "A (title, as deployed)": _build(client, "hub_a", chunks, lambda t: t),
        "B (title removed)": _build(client, "hub_b", chunks, _strip_title),
    }
    results = {}
    try:
        for name, col in variants.items():
            retriever.get_collection = lambda col=col: col
            results[name] = _measure(natural, chunks)
    finally:
        retriever.get_collection = get_collection

    a, b = results.values()
    valid = abs(a["mrr"] - production_mrr) < 1e-9
    print(f"Validity: A reproduces the production MRR ({production_mrr:.6f})? {'YES' if valid else 'NO'}")
    if not valid:
        print("The in-memory build does not match production; nothing below can be trusted.")
        return 1

    print(f"\n{COPING}: {corpus[COPING] / len(chunks):.0%} of the corpus, "
          f"{labelled[COPING] / sum(labelled.values()):.0%} of labelled-relevant chunks\n")
    row = "{:40} {:>24} {:>20}"
    print(row.format("", *results))
    print(row.format("MRR (51 natural, deployed form)", f"{a['mrr']:.4f}", f"{b['mrr']:.4f}"))
    print(row.format(f"Recall@{K}", f"{a['recall4']:.3f}", f"{b['recall4']:.3f}"))
    print(row.format(f"misses in top {K}", str(a["misses"]), str(b["misses"])))
    print(row.format("coping share of top-4 slots", f"{a['coping_share']:.0%}", f"{b['coping_share']:.0%}"))
    print(row.format("coping share of irrelevant slots", f"{a['coping_irrelevant']:.0%}",
                     f"{b['coping_irrelevant']:.0%}"))
    print(row.format("academic_stress share of slots", f"{a['academic_share']:.0%}",
                     f"{b['academic_share']:.0%}"))
    print(row.format(f"{HUB} in top 4 (of 51)", a["hub"], b["hub"]))
    print(row.format("k-occurrence skewness (hubness)", f"{a['skew']:.2f}", f"{b['skew']:.2f}"))
    print(row.format("explicit support queries reached", a["support"], b["support"]))
    print(row.format("questionnaire: actionable share", f"{a['actionable']:.0%}", f"{b['actionable']:.0%}"))
    print(row.format("questionnaire: matched subscale", f"{a['matched']:.0%}", f"{b['matched']:.0%}"))

    diff = b["rr"] - a["rr"]
    rng = np.random.default_rng(42)
    boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(10_000)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    changed = sum(a["top4"][q] != b["top4"][q] for q in a["top4"])
    print(f"\nMRR change B - A: {diff.mean():+.3f}, paired bootstrap 95% CI [{lo:+.3f}, {hi:+.3f}]; "
          f"top 4 changed for {changed}/51 queries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
