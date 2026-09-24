"""Faithfulness of generated suggestions to the retrieved reference material.

`retrieval_eval` scores whether the right passages were *retrieved*. This scores
whether the advice the generator wrote is actually *supported* by them - the
property prompt rule 4 demands and the property that matters to a student.

Method (LLM-as-judge, RAGAS-style claim support):

1. For each test item in the ablation subsample, read the suggestions the
   classification run already produced from the LLM cache. Nothing is
   regenerated, so the judged text is exactly what was evaluated.
2. Re-run retrieval with the production query (`build_rag_query`) to recover the
   four passages the generator saw. Retrieval is deterministic and the knowledge
   base has not changed since those runs.
3. A judge model from a different family than the generator labels each
   suggestion `supported`, `partial` or `unsupported` against those passages.

The `no_rag` configuration is the CONTROL. Its suggestions were written without
any reference material and are judged against the same passages. If they score
nearly as "supported" as the full pipeline's, the knowledge base merely overlaps
with generic advice and the grounding claim is not demonstrated. The gap between
the two arms is the result; the absolute rate alone is not.

What this does NOT establish:
- **Judge validity.** An LLM judge is an instrument that itself needs checking.
  `--export-rating 30` writes a blind sheet (suggestion + passages, no judge
  verdict) and a separate key; fill `human_verdict` and run `--agreement` for
  judge-human Cohen's kappa. Until then the rates are the judge's opinion, and
  should be quoted as such.
- **Usefulness or safety.** A suggestion can be fully supported and still be a
  poor fit for the student. That is the human-rating study's question.

Usage:
    python -m app.eval.faithfulness_eval --limit 40
    python -m app.eval.faithfulness_eval --export-rating 30   # blind sheet for a human
    python -m app.eval.faithfulness_eval --agreement          # after rating it
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)

OUT_DIR = PROJECT_ROOT / "data" / "eval"
# A different model family from the generator (openai/gpt-oss-120b), so the
# judge is not grading its own phrasing. On Groq it also draws on a separate
# per-model quota.
DEFAULT_JUDGE_MODEL = "qwen/qwen3.8-27b"
VERDICTS = ("supported", "partial", "unsupported")
# Same threshold the classification harness uses: above it, the rates describe
# the failures rather than the system.
MAX_TOLERABLE_FAILURE_RATE = 0.2
# A verdict list for five suggestions is ~350 tokens. The cap matters on Groq,
# whose free tier limits qwen3.8-27b to 1,000 output tokens per MINUTE and
# rejects outright any request whose default reservation (~1,400) exceeds it.
JUDGE_MAX_TOKENS = 500

# id -> (use_rag, use_questionnaire, use_emotion), matching app.eval.ablation.
ARMS: dict[str, tuple[bool, bool, bool]] = {
    "full": (True, True, True),
    "no_rag": (False, True, True),
}

JUDGE_SYSTEM = """\
You check whether advice is supported by reference passages. You are strict and literal.

For EACH numbered suggestion, decide:
- "supported": the action it recommends, and every specific detail it gives \
(technique, number, service, phone number, time), is stated in or directly implied \
by at least one passage. Rephrasing and addressing the reader personally are fine.
- "partial": the core action appears in a passage, but the suggestion adds at least \
one specific detail that no passage contains.
- "unsupported": the core action does not appear in any passage.

Judge only against the passages. Do not use your own knowledge of what is good advice.

Return ONLY one JSON object, no other text:
{"verdicts": [{"i": <suggestion number>, "verdict": "supported|partial|unsupported", \
"evidence": ["<passage id>", ...], "reason": "<one short sentence>"}]}"""


# A refusal written into the suggestions field ("No specific coping suggestions
# are available from the reference material") is rule 4 working, not advice. The
# no_rag run produced three of these; judging them as "unsupported" would count
# a correct refusal as a grounding failure.
_REFUSAL_RE = re.compile(
    r"\bno (specific |further |grounded )?(coping )?(suggestions?|advice|recommendations?)\b"
    r"|\bcannot (be )?(provide|offer|give)\b",
    re.IGNORECASE,
)


def is_refusal(suggestion: str) -> bool:
    return bool(_REFUSAL_RE.search(suggestion))


# A suggestion that points the student to professional or institutional help.
_REFERRAL_RE = re.compile(
    r"counsel|professional|helpline|hotline|therap|psycholog|psychiatr|doctor|clinic|"
    r"health service|mental[- ]health service",
    re.IGNORECASE,
)


def is_referral(suggestion: str) -> bool:
    return bool(_REFERRAL_RE.search(suggestion))


def order_sensitive(text: str, emotion, canonical_ids: list[str], trials: int = 8) -> bool:
    """Would a different ordering of equal-length keywords retrieve other passages?

    Before 2026-09-19 the keyword order depended on the interpreter's hash seed
    (see app.nlp.lexicon.ALL_KEYWORDS), so the passages the generator saw for an
    item may differ from the canonical ones judged here. This finds the items
    where that is possible, so results can be reported without them.
    """
    import random

    from app.api.services import build_rag_query
    from app.rag.retriever import retrieve

    if emotion is None or len(emotion.stress_keywords) < 2:
        return False
    groups: dict[int, list[str]] = {}
    for kw in emotion.stress_keywords:
        groups.setdefault(len(kw), []).append(kw)
    if all(len(g) < 2 for g in groups.values()):
        return False
    rng = random.Random(42)
    for _ in range(trials):
        shuffled: list[str] = []
        for length in sorted(groups, reverse=True):
            g = groups[length][:]
            rng.shuffle(g)
            shuffled.extend(g)
        variant = emotion.model_copy(update={"stress_keywords": shuffled})
        ids = [d.chunk_id for d in retrieve(build_rag_query(text, variant, None), k=4)]
        if set(ids) != set(canonical_ids):
            return True
    return False


@dataclass
class Judgment:
    item: int
    arm: str
    index: int
    suggestion: str
    verdict: str
    evidence: list[str]
    reason: str
    order_sensitive: bool = False


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def format_passages(docs) -> str:
    return "\n\n".join(f"[{d.chunk_id}] {d.heading}\n{d.text}" for d in docs)


def judge_prompt(docs, suggestions: list[str]) -> str:
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(suggestions, start=1))
    return f"PASSAGES:\n\n{format_passages(docs)}\n\nSUGGESTIONS:\n{numbered}"


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_verdicts(raw: str, n_suggestions: int) -> list[dict] | None:
    """Return one verdict dict per suggestion, in order, or None if unusable.

    Strict on coverage: a reply that skips a suggestion or invents a verdict
    label is rejected whole, because silently treating a gap as any particular
    verdict would bias the rate in that direction.
    """
    text = _THINK_RE.sub("", raw).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    by_index: dict[int, dict] = {}
    for entry in data.get("verdicts", []):
        try:
            i = int(entry.get("i"))
        except (TypeError, ValueError):
            return None
        verdict = str(entry.get("verdict", "")).strip().lower()
        if verdict not in VERDICTS:
            return None
        evidence = entry.get("evidence") or []
        by_index[i] = {
            "verdict": verdict,
            "evidence": [str(e) for e in evidence] if isinstance(evidence, list) else [],
            "reason": str(entry.get("reason", "")),
        }
    if sorted(by_index) != list(range(1, n_suggestions + 1)):
        return None
    return [by_index[i] for i in range(1, n_suggestions + 1)]


def _judge_llm(model: str):
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    return ChatOpenAI(
        model=model,
        temperature=0.0,
        max_tokens=JUDGE_MAX_TOKENS,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        max_retries=settings.llm_max_retries,
    )


def judge_cache_key(docs, suggestions: list[str], model: str) -> str:
    """Cache key for one judge call.

    Shared by judge_one, which stores under it, and recover_judged_passages,
    which looks up under it, so the two cannot drift apart. It hashes the
    passages together with the suggestions, which is what makes recovery exact.
    """
    from app.eval.baselines import _cache_key

    return _cache_key(
        {
            "system": "faithfulness_judge:v1",
            "model": model,
            "endpoint": get_settings().openai_base_url,
            "passages": [[d.chunk_id, d.text] for d in docs],
            "suggestions": suggestions,
        }
    )


async def judge_one(
    llm, semaphore: asyncio.Semaphore, docs, suggestions: list[str], model: str, cache_dir: Path
) -> list[dict] | None:
    """Judge one item's suggestions. Cache-first; None on an unusable reply."""
    from app.eval.baselines import cache_get, cache_put

    key = judge_cache_key(docs, suggestions, model)
    cached = cache_get(cache_dir, key)
    if cached is not None:
        return cached["verdicts"]

    from langchain_core.messages import HumanMessage, SystemMessage

    async with semaphore:
        try:
            reply = await llm.ainvoke(
                [SystemMessage(content=JUDGE_SYSTEM), HumanMessage(content=judge_prompt(docs, suggestions))]
            )
        except Exception as exc:  # noqa: BLE001 - one failed call must not end the run
            logger.warning("judge call failed: %s", exc)
            return None
    verdicts = parse_verdicts(str(reply.content), len(suggestions))
    if verdicts is None:
        logger.warning("judge reply unusable: %.300s", reply.content)
        return None
    cache_put(cache_dir, key, {"verdicts": verdicts, "raw": reply.content})
    return verdicts


def summarise(judgments: list[Judgment], items: dict[str, dict]) -> pd.DataFrame:
    """One row per arm: counts, rates and Wilson intervals."""
    rows = []
    for arm in ARMS:
        js = [j for j in judgments if j.arm == arm]
        n_items = len({j.item for j in js})
        n = len(js)
        supported = sum(j.verdict == "supported" for j in js)
        partial = sum(j.verdict == "partial" for j in js)
        lo, hi = wilson(supported, n)
        lo2, hi2 = wilson(supported + partial, n)
        stats = items[arm]
        rows.append(
            {
                "arm": arm,
                "items_generated": stats["generated"],
                "items_declined": stats["declined"],
                "refusal_statements": stats["refusals"],
                "declined_by_statement": stats["declined_by_statement"],
                "items_judged": stats["judged"],
                "items_with_suggestions": n_items,
                "judge_failures": stats["judge_failures"],
                "suggestions": n,
                "supported": supported,
                "partial": partial,
                "unsupported": n - supported - partial,
                "supported_rate": round(supported / n, 3) if n else None,
                "supported_ci95": f"[{lo:.2f}, {hi:.2f}]" if n else "",
                "supported_or_partial_rate": round((supported + partial) / n, 3) if n else None,
                "supported_or_partial_ci95": f"[{lo2:.2f}, {hi2:.2f}]" if n else "",
            }
        )
    return pd.DataFrame(rows)


def unreportable(stats: dict) -> str | None:
    attempted = stats["judged"] + stats["judge_failures"]
    if attempted and stats["judge_failures"] / attempted > MAX_TOLERABLE_FAILURE_RATE:
        return (
            f"{stats['judge_failures']}/{attempted} judge calls produced no usable verdicts, "
            f"above the {MAX_TOLERABLE_FAILURE_RATE:.0%} threshold"
        )
    return None


def run(limit: int | None, judge_model: str, out_dir: Path | None = None,
        cache_dir: Path | None = None) -> pd.DataFrame:
    from app.api.services import needs_support_material, retrieve_for_assessment
    from app.eval.ablation import subsample_test_split
    from app.eval.baselines import DEFAULT_CACHE_DIR, cache_get, full_cache_key
    from app.eval.datasets import load_eval_dataset
    from app.nlp.emotion import analyze

    out = out_dir or OUT_DIR
    cache = cache_dir or DEFAULT_CACHE_DIR
    df = load_eval_dataset("synthetic", out_dir=out)
    if limit is not None:
        df = subsample_test_split(df, limit)
    test = df[df["split"] == "test"]

    llm = _judge_llm(judge_model)
    semaphore = asyncio.Semaphore(get_settings().llm_concurrency)

    # Collect the work first, then judge concurrently.
    tasks: list[tuple[int, str, list, list[str]]] = []
    items = {
        arm: {"generated": 0, "declined": 0, "refusals": 0, "declined_by_statement": 0, "judged": 0, "judge_failures": 0}
        for arm in ARMS
    }
    sensitive: set[int] = set()
    passages_by_item: dict[int, str] = {}
    # Items screened as needing support material, and per arm the items whose
    # suggestions point to professional help.
    support_items: set[int] = set()
    referred: dict[str, set[int]] = {arm: set() for arm in ARMS}
    missing: dict[str, int] = {arm: 0 for arm in ARMS}
    for pos, (_, row) in enumerate(test.iterrows()):
        text = str(row["text"])
        emotion = analyze(text)
        # The passages the full pipeline's generator saw, pinned ones included.
        _, dass, pss = full_cache_key(row, True, True, True)
        docs = retrieve_for_assessment(text, emotion, None, dass, pss)
        passages_by_item[pos] = format_passages(docs)
        if needs_support_material(dass, pss):
            support_items.add(pos)
        if order_sensitive(text, emotion, [d.chunk_id for d in docs if not d.pinned]):
            sensitive.add(pos)
        for arm, flags in ARMS.items():
            key, _, _ = full_cache_key(row, *flags)
            cached = cache_get(cache, key)
            if cached is None or "suggestions" not in cached:
                missing[arm] += 1
                continue
            items[arm]["generated"] += 1
            suggestions = [s for s in cached["suggestions"] if str(s).strip()]
            refusals = [s for s in suggestions if is_refusal(s)]
            items[arm]["refusals"] += len(refusals)
            suggestions = [s for s in suggestions if not is_refusal(s)]
            if any(is_referral(s) for s in suggestions):
                referred[arm].add(pos)
            if not suggestions:
                items[arm]["declined"] += 1
                if refusals:
                    items[arm]["declined_by_statement"] += 1
                continue
            tasks.append((pos, arm, docs, suggestions))

    async def _all():
        return await asyncio.gather(
            *[judge_one(llm, semaphore, docs, sugg, judge_model, cache) for _, _, docs, sugg in tasks]
        )

    results = asyncio.run(_all())

    judgments: list[Judgment] = []
    for (pos, arm, _docs, suggestions), verdicts in zip(tasks, results, strict=True):
        if verdicts is None:
            items[arm]["judge_failures"] += 1
            continue
        items[arm]["judged"] += 1
        for i, (s, v) in enumerate(zip(suggestions, verdicts, strict=True), start=1):
            judgments.append(
                Judgment(pos, arm, i, s, v["verdict"], v["evidence"], v["reason"], pos in sensitive)
            )

    table = summarise(judgments, items)
    stable = summarise([j for j in judgments if not j.order_sensitive], items)
    detail = pd.DataFrame([j.__dict__ for j in judgments])
    if not detail.empty:
        detail["evidence"] = detail["evidence"].map(lambda e: ";".join(e))
        detail["passages"] = detail["item"].map(passages_by_item)
    detail.to_csv(out / "faithfulness_judgments.csv", index=False, encoding="utf-8")

    referral = {
        arm: {"support_items": len(support_items), "referred": len(referred[arm] & support_items)}
        for arm in ARMS
    }
    table["support_items"] = [referral[a]["support_items"] for a in table["arm"]]
    table["support_items_referred"] = [referral[a]["referred"] for a in table["arm"]]
    markdown = render(table, judgments, items, missing, len(test), judge_model,
                      stable=stable, n_sensitive=len(sensitive), referral=referral)
    (out / "faithfulness_eval.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return table


def _overlap(a: str, b: str) -> bool:
    lo_a, hi_a = (float(x) for x in a.strip("[]").split(","))
    lo_b, hi_b = (float(x) for x in b.strip("[]").split(","))
    return lo_a <= hi_b and lo_b <= hi_a


def render(table, judgments, items, missing, n_items, judge_model,
           stable=None, n_sensitive: int = 0, referral: dict | None = None) -> str:
    settings = get_settings()
    lines = [
        "# Faithfulness of generated suggestions",
        "",
        "> **Computed on SYNTHETIC data.** Verdicts are an LLM judge's, not yet validated "
        "against a human rater (see `--agreement`).",
        "",
        f"Generator `{settings.openai_model}`; judge `{judge_model}` (different model family). "
        f"{n_items} test items (stratified subsample, seed 42, the ablation's sample). Each "
        "suggestion is judged against the four passages the production query retrieves for "
        "that item, including the support passages pinned for students screened High/Severe "
        "(`app.api.services.retrieve_for_assessment`).",
        "",
    ]
    blocked = {arm: unreportable(items[arm]) for arm in ARMS}
    shown = table[[blocked[a] is None for a in table["arm"]]]
    cols = ["arm", "items_generated", "items_declined", "refusal_statements",
            "items_with_suggestions", "suggestions", "supported_rate", "supported_ci95",
            "supported_or_partial_rate", "supported_or_partial_ci95"]
    if not shown.empty:
        lines += [shown[cols].to_markdown(index=False), ""]
    for arm, reason in blocked.items():
        if reason:
            lines.append(f"**Not reported:** `{arm}` - {reason}.")
    for arm, n in missing.items():
        if n:
            lines.append(f"- `{arm}`: {n}/{n_items} items have no generated output in the cache yet.")
    lines.append("")

    if all(blocked[a] is None for a in ARMS):
        t = table.set_index("arm")
        full, ctrl = t.loc["full"], t.loc["no_rag"]
        lines += ["## Reading", ""]
        lines.append(
            f"Without retrieved material the generator declined to advise on "
            f"{ctrl['items_declined']}/{ctrl['items_generated']} items "
            f"({ctrl['items_declined'] - ctrl['declined_by_statement']} with an empty list, "
            f"{ctrl['declined_by_statement']} by writing a refusal where the advice would go) "
            f"and offered advice on {ctrl['items_with_suggestions']}. With retrieval it advised on "
            f"{full['items_with_suggestions']}/{full['items_generated']}. Prompt rule 4 is what "
            "produces that difference, and it is the clearest evidence here that the advice "
            "is conditioned on the retrieved material."
        )
        if full["suggestions"]:
            lines += [
                "",
                f"Of the full pipeline's {full['suggestions']} suggestions, "
                f"{full['supported_rate']:.0%} {full['supported_ci95']} were fully supported "
                f"and {full['supported_or_partial_rate']:.0%} {full['supported_or_partial_ci95']} "
                "at least partially; 'partial' means the core action is in a passage but a "
                "specific detail was added.",
            ]
        if full["suggestions"] and ctrl["suggestions"]:
            verdict = (
                "overlap, so the difference in support rate is not established at this size"
                if _overlap(full["supported_ci95"], ctrl["supported_ci95"])
                else "do not overlap"
            )
            lines += [
                "",
                f"The control's {ctrl['suggestions']} suggestion(s) scored "
                f"{ctrl['supported_rate']:.0%} {ctrl['supported_ci95']}; the intervals {verdict}. "
                "With so few control suggestions, the refusal counts above carry more weight "
                "than this comparison.",
            ]
        lines.append("")

    if referral and referral["full"]["support_items"]:
        r = referral["full"]
        lo, hi = wilson(r["referred"], r["support_items"])
        lines += [
            "## Referral to professional help",
            "",
            f"{r['support_items']}/{n_items} items were screened High/Severe or with severe DASS "
            "depression/anxiety, and so had the help-seeking passages pinned into context. The full "
            f"pipeline pointed {r['referred']} of them ({r['referred'] / r['support_items']:.0%}, "
            f"95 % CI [{lo:.2f}, {hi:.2f}]) to professional or institutional help. Before pinning, "
            "those passages were never retrieved and 3 of 121 suggestions mentioned such help at all.",
            "",
        ]

    if stable is not None and n_sensitive:
        s_full = stable.set_index("arm").loc["full"]
        lines += [
            "## Sensitivity: keyword-order items excluded",
            "",
            f"{n_sensitive}/{n_items} items retrieve a different top-4 under some ordering of "
            "equal-length keywords. Before the 2026-09-19 fix that ordering depended on the hash "
            "seed, so for these items the generator may have seen different passages from the "
            "ones judged. Excluding them, the full pipeline's supported rate is "
            f"{s_full['supported_rate']:.0%} {s_full['supported_ci95']} over "
            f"{s_full['suggestions']} suggestions "
            f"(supported or partial {s_full['supported_or_partial_rate']:.0%}).",
            "",
        ]

    worst = [j for j in judgments if j.arm == "full" and j.verdict == "unsupported"]
    lines += [f"## Unsupported suggestions from the full pipeline ({len(worst)})", ""]
    lines += [
        f"- item {j.item}, #{j.index}"
        + (" *(keyword-order-sensitive item: the generator may have seen other passages)*"
           if j.order_sensitive else "")
        + f": “{j.suggestion}” — judge: {j.reason}"
        for j in worst
    ] or ["(none)"]
    lines.append("")
    return "\n".join(lines)


RATING_SHEET = OUT_DIR / "faithfulness_rating_sheet.csv"
RATING_KEY = OUT_DIR / "faithfulness_rating_key.csv"


def _item_candidates(limit: int | None) -> dict[int, dict[str, list]]:
    """Per test item, the passage lists a past run could have judged against.

    run() has changed since some judgments were written: support pinning arrived
    later, so an item may have been judged against its ranked passages alone.
    Both lists are offered and the judge cache decides which one it was.
    """
    from app.api.services import retrieve_for_assessment
    from app.eval.ablation import subsample_test_split
    from app.eval.baselines import full_cache_key
    from app.eval.datasets import load_eval_dataset
    from app.nlp.emotion import analyze

    df = load_eval_dataset("synthetic", out_dir=OUT_DIR)
    if limit is not None:
        df = subsample_test_split(df, limit)
    test = df[df["split"] == "test"]
    candidates: dict[int, dict[str, list]] = {}
    for pos, (_, row) in enumerate(test.iterrows()):
        text = str(row["text"])
        _, dass, pss = full_cache_key(row, True, True, True)
        docs = retrieve_for_assessment(text, analyze(text), None, dass, pss)
        ranked = [d for d in docs if not d.pinned]
        # Offer the pinned list only where it differs, so a match labelled
        # "with_pinning" always means pinned passages were in front of the judge.
        candidates[pos] = {"ranked_only": ranked}
        if len(ranked) != len(docs):
            candidates[pos]["with_pinning"] = docs
    return candidates


def recover_judged_passages(
    detail: pd.DataFrame,
    candidates: dict[int, dict[str, list]] | None = None,
    cache_dir: Path | None = None,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    limit: int | None = 40,
) -> tuple[dict[tuple[int, str], str], dict[tuple[int, str], str]]:
    """Recover the exact passages the judge saw, per (item, arm).

    Judgment files written before run() stored a `passages` column cannot feed a
    rating sheet, and rebuilding the passages with today's retrieval would show
    the rater something the judge never saw. The judge cache key hashes the
    passages together with the suggestions, so a candidate list whose key is in
    the cache is byte-identical to the judge's input. Nothing is guessed: any
    (item, arm) that no candidate reproduces raises, naming it.

    Returns the formatted passages and, for each, which candidate matched.
    """
    from app.eval.baselines import DEFAULT_CACHE_DIR, cache_get

    cache = cache_dir or DEFAULT_CACHE_DIR
    if candidates is None:
        candidates = _item_candidates(limit)
    passages: dict[tuple[int, str], str] = {}
    provenance: dict[tuple[int, str], str] = {}
    unrecovered: list[tuple[int, str]] = []
    for (item, arm), rows in detail.groupby(["item", "arm"]):
        k = (int(item), str(arm))
        suggestions = rows.sort_values("index")["suggestion"].astype(str).tolist()
        for name, docs in candidates.get(k[0], {}).items():
            if cache_get(cache, judge_cache_key(docs, suggestions, judge_model)) is not None:
                passages[k] = format_passages(docs)
                provenance[k] = name
                break
        else:
            unrecovered.append(k)
    if unrecovered:
        raise RuntimeError(
            f"Could not reproduce the judge's input for {len(unrecovered)} (item, arm) pairs: "
            f"{unrecovered}. Refusing to build a rating sheet from passages the judge may not have seen."
        )
    return passages, provenance


def export_rating_sheet(n: int = 30, seed: int = 42, judgments_csv: Path | None = None,
                        sheet: Path = RATING_SHEET, key: Path = RATING_KEY,
                        candidates: dict[int, dict[str, list]] | None = None,
                        avoid_key: Path | None = None) -> int:
    """Write a BLIND sheet of n judged suggestions for a human rater, plus a separate key.

    The sheet shows the suggestion and the passages it was judged against, never
    the judge's verdict, so the rater cannot anchor on it. Sampling is stratified
    by the judge's verdict with every verdict represented, because the rare
    verdicts are the ones whose reliability matters most; that makes raw
    agreement on the sheet unrepresentative of the full set, which is why kappa
    is the figure to report.

    A judgments file without a `passages` column (written by an older run())
    has them recovered from the judge cache first; see recover_judged_passages.

    `avoid_key` names an earlier sheet's key whose rows the rater may already
    have seen discussed. Each verdict stratum is filled from unseen rows first
    and falls back to seen ones only when it has too few, so a rare verdict is
    never dropped; any seen row that is used is marked `seen_before` in the key.
    """
    detail = pd.read_csv(judgments_csv or OUT_DIR / "faithfulness_judgments.csv", encoding="utf-8")
    if "passages" not in detail.columns:
        passages, provenance = recover_judged_passages(detail, candidates=candidates)
        pairs = list(zip(detail["item"].astype(int), detail["arm"].astype(str), strict=True))
        detail["passages"] = [passages[p] for p in pairs]
        detail["passage_set"] = [provenance[p] for p in pairs]
    detail["seen_before"] = False
    if avoid_key is not None:
        seen = pd.read_csv(avoid_key, encoding="utf-8")
        seen_ids = set(zip(seen["item"].astype(int), seen["arm"].astype(str), seen["index"].astype(int)))
        detail["seen_before"] = [
            (int(i), str(a), int(x)) in seen_ids
            for i, a, x in zip(detail["item"], detail["arm"], detail["index"], strict=True)
        ]

    def _draw(pool: pd.DataFrame, k: int) -> pd.DataFrame:
        """k rows, unseen first; seen rows only to make up a shortfall."""
        unseen, seen_rows = pool[~pool["seen_before"]], pool[pool["seen_before"]]
        take = unseen.sample(n=min(len(unseen), k), random_state=seed)
        if len(take) < k and not seen_rows.empty:
            take = pd.concat([take, seen_rows.sample(n=min(len(seen_rows), k - len(take)), random_state=seed)])
        return take

    groups = [g for _, g in detail.groupby("verdict")]
    per_group = max(1, n // max(1, len(groups)))
    picked = pd.concat([_draw(g, per_group) for g in groups])
    rest = detail.drop(picked.index)
    if len(picked) < n and not rest.empty:
        picked = pd.concat([picked, _draw(rest, n - len(picked))])
    picked = picked.sample(frac=1, random_state=seed).reset_index(drop=True)
    picked.insert(0, "row_id", range(1, len(picked) + 1))
    blind = picked[["row_id", "suggestion", "passages"]].assign(
        human_verdict="", note="supported | partial | unsupported"
    )
    blind.to_csv(sheet, index=False, encoding="utf-8")
    key_cols = ["row_id", "item", "arm", "index", "verdict", "seen_before"]
    if "passage_set" in picked.columns:
        key_cols.append("passage_set")
    picked[key_cols].to_csv(key, index=False, encoding="utf-8")
    return len(picked)


SECOND_RATER_CSV = OUT_DIR / "faithfulness_second_rater.csv"
SECOND_RATER_KEY = OUT_DIR / "faithfulness_second_rater_key.csv"


def agreement(csv_path: Path, key_path: Path | None = None, column: str = "human_verdict",
              rater: str = "human", resamples: int = 10_000) -> str:
    """Agreement between the judge and a rater, on the rows the rater has rated.

    With `key_path`, `csv_path` is a blind rating sheet and the judge's verdicts
    come from the key; without it, one file carries both columns. `column` names
    the rater's verdicts and `rater` how the result is labelled: the second-model
    check uses its own column precisely so that it can never be read as human.

    Kappa comes with a percentile bootstrap interval, because at n = 30 the
    interval is the honest part of the number.
    """
    import numpy as np
    from sklearn.metrics import cohen_kappa_score

    detail = pd.read_csv(csv_path, encoding="utf-8").fillna("")
    if key_path is not None:
        detail = detail.merge(pd.read_csv(key_path, encoding="utf-8"), on="row_id", how="inner")
    rated = detail[detail[column].astype(str).str.strip().str.lower().isin(VERDICTS)]
    if rated.empty:
        return f"No rows have a {column} yet; fill some in {csv_path.name} first."
    judge = rated["verdict"].to_numpy()
    other = rated[column].astype(str).str.strip().str.lower().to_numpy()
    kappa = cohen_kappa_score(judge, other, labels=list(VERDICTS))
    exact = (judge == other).mean()
    rng = np.random.default_rng(42)
    boot = []
    for _ in range(resamples):
        i = rng.integers(0, len(judge), len(judge))
        if len(set(judge[i]) | set(other[i])) > 1:  # kappa is undefined on one class
            boot.append(cohen_kappa_score(judge[i], other[i], labels=list(VERDICTS)))
    lo, hi = np.percentile(boot, [2.5, 97.5]) if boot else (float("nan"), float("nan"))
    return (
        f"Judge-{rater} agreement on {len(rated)} suggestions: raw {exact:.1%}, "
        f"Cohen's kappa {kappa:.3f} (bootstrap 95% CI [{lo:.2f}, {hi:.2f}])."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=40,
                        help="Test items, stratified, seed 42. Defaults to the ablation's 40.")
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--agreement", action="store_true",
                        help="Report judge-human agreement from the rated sheet instead of judging.")
    parser.add_argument("--agreement-second-rater", action="store_true",
                        help="Report judge agreement with the second MODEL rater (not a human).")
    parser.add_argument("--export-rating", type=int, metavar="N", default=None,
                        help="Write a blind rating sheet of N judged suggestions, and its key.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Sampling seed for --export-rating.")
    parser.add_argument("--avoid-key", type=Path, default=None,
                        help="Key of an earlier sheet whose rows the rater may have seen; "
                             "--export-rating draws unseen rows first.")
    args = parser.parse_args()

    if args.export_rating:
        n = export_rating_sheet(args.export_rating, seed=args.seed, avoid_key=args.avoid_key)
        print(f"Wrote {n} rows to {RATING_SHEET} (blind) and the key to {RATING_KEY}.")
        return
    if args.agreement:
        print(agreement(RATING_SHEET, RATING_KEY))
        return
    if args.agreement_second_rater:
        print(agreement(SECOND_RATER_CSV, SECOND_RATER_KEY, column="second_rater_verdict",
                        rater="second-model"))
        return
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    logging.basicConfig(level=logging.WARNING)
    run(args.limit, args.judge_model)


if __name__ == "__main__":
    main()
