"""The four systems compared in the thesis evaluation.

| id            | system                                                        |
|---------------|---------------------------------------------------------------|
| tfidf_lr      | TF-IDF + Logistic Regression (ported from research/baseline)  |
| phobert_ft    | fine-tuned local PhoBERT stress classifier (3-class)          |
| llm_zeroshot  | GPT-4o-mini, raw text only                                    |
| llm_full      | proposed system: text + emotion + questionnaires + RAG        |

All systems are evaluated on the same held-out test split in the same 4-class
label space (Low/Moderate/High/Severe).

PhoBERT 3-class -> 4-class mapping: identity on {Low, Moderate, High}. The
fine-tuned model has no "Severe" class, so it can never predict Severe; its
"High" prediction covers the High+Severe region. This is reported as-is (its
recall on Severe is 0 by construction) rather than remapped, because any
score-free remapping would be arbitrary.

LLM responses are cached on disk keyed by a hash of the full input, so
re-running a comparison performs zero API calls and is deterministic.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.config import PROJECT_ROOT, get_settings
from app.eval.datasets import (
    dass_answers_from_row,
    has_questionnaire_items,
    pss_answers_from_row,
)

logger = logging.getLogger(__name__)

STRESS_LEVELS = ["Low", "Moderate", "High", "Severe"]

DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "eval" / "llm_cache"

# Concurrent in-flight LLM requests. Overridden by Settings.llm_concurrency so a
# rate-limited free tier can be throttled without editing code; this constant is
# the fallback when settings are unavailable.
LLM_CONCURRENCY = 4


# Above this share of unparseable replies, the "predictions" are mostly the
# fallback label and the metrics describe that constant, not the system. Chosen
# after a real incident: a daily quota ran out mid-run, four ablation
# configurations returned 30/30 failures, and the harness reported them as
# accuracy 0.333 - numerically identical to the majority-class baseline and
# indistinguishable from a genuine result to anyone reading the table.
MAX_TOLERABLE_FAILURE_RATE = 0.2


@dataclass
class SystemResult:
    system: str
    y_true: list[str]
    y_pred: list[str]
    notes: dict = field(default_factory=dict)

    def unreportable_reason(self) -> str | None:
        """Why this result must not be published as a number, or None if it may be.

        Returning a reason rather than raising lets the caller record the system
        as "not run", which is the honest artifact, instead of either crashing or
        printing a fabricated score.
        """
        parse_failures = self.notes.get("parse_failures") or 0
        rate_limited = self.notes.get("rate_limited") or 0
        call_failures = self.notes.get("call_failures") or 0
        # A system predating the split counts reports only parse_failures.
        failures = self.notes.get("unusable") or (parse_failures + rate_limited + call_failures)
        n = len(self.y_pred)
        if not failures or not n:
            return None
        rate = failures / n
        if rate <= MAX_TOLERABLE_FAILURE_RATE:
            return None

        # Name the dominant cause. "Unparseable" is a claim about the model;
        # a 429 is a claim about the account, and conflating them has already
        # put a wrong sentence in the report.
        if rate_limited >= max(parse_failures, call_failures):
            cause = (
                f"{rate_limited} of them were provider rate-limit refusals (HTTP 429), so those "
                "requests never reached the model and nothing about its behaviour was measured"
            )
        elif parse_failures >= call_failures:
            cause = f"{parse_failures} of them were replies the parser rejected as malformed"
        else:
            cause = f"{call_failures} of them were other call failures"
        return (
            f"{failures}/{n} replies ({rate:.0%}) produced no usable prediction and fell back "
            f"to a fixed label, above the {MAX_TOLERABLE_FAILURE_RATE:.0%} threshold; the "
            f"metrics would describe the fallback, not the system. {cause}."
        )


# ---------------------------------------------------------------------------
# tfidf_lr
# ---------------------------------------------------------------------------


def run_tfidf_lr(df: pd.DataFrame, seed: int = 42) -> SystemResult:
    """Word-level TF-IDF + Logistic Regression, fitted on the train split.

    Hyperparameters ported unchanged from research/baseline.py.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=2000, C=5.0, class_weight="balanced", random_state=seed)),
        ]
    )
    pipeline.fit(train["text"], train["label"])
    y_pred = pipeline.predict(test["text"]).tolist()
    return SystemResult(
        system="tfidf_lr",
        y_true=test["label"].tolist(),
        y_pred=y_pred,
        notes={"train_size": len(train), "test_size": len(test)},
    )


# ---------------------------------------------------------------------------
# majority
# ---------------------------------------------------------------------------


def run_majority(df: pd.DataFrame) -> SystemResult:
    """Always predict the most frequent training label.

    The floor every other system has to clear. Without it, an accuracy figure has
    no reference point: on a skewed four-class split, a system can look
    respectable while doing nothing a constant predictor could not. Needs no
    model and no API call, so there is no reason for it to be missing.
    """
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    majority = train["label"].value_counts().idxmax()

    return SystemResult(
        system="majority",
        y_true=test["label"].tolist(),
        y_pred=[majority] * len(test),
        notes={
            "majority_label": majority,
            "train_size": len(train),
            "test_size": len(test),
        },
    )


# ---------------------------------------------------------------------------
# tfidf_svm
# ---------------------------------------------------------------------------


def run_tfidf_svm(df: pd.DataFrame, seed: int = 42) -> SystemResult:
    """TF-IDF with a linear support-vector classifier.

    The second classical comparator. Same features as `tfidf_lr`, different
    decision rule, so a gap between the two is attributable to the classifier
    rather than to the representation. Also offline.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC

    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("clf", LinearSVC(C=1.0, class_weight="balanced", random_state=seed)),
        ]
    )
    pipeline.fit(train["text"], train["label"])
    return SystemResult(
        system="tfidf_svm",
        y_true=test["label"].tolist(),
        y_pred=pipeline.predict(test["text"]).tolist(),
        notes={"train_size": len(train), "test_size": len(test)},
    )


# ---------------------------------------------------------------------------
# phobert_ft
# ---------------------------------------------------------------------------


def run_phobert_ft(df: pd.DataFrame) -> SystemResult:
    """Local fine-tuned PhoBERT classifier; identity 3->4 class mapping."""
    from app.nlp.emotion import _load_stress_classifier, _map_phobert_label

    clf = _load_stress_classifier()
    if clf is None:
        raise RuntimeError(
            "models/phobert-stress is not available; cannot run the phobert_ft baseline"
        )

    test = df[df["split"] == "test"]
    y_pred: list[str] = []
    for text in test["text"]:
        predictions = clf(text)[0]
        scores = {_map_phobert_label(p["label"]): float(p["score"]) for p in predictions}
        y_pred.append(max(scores, key=scores.get))

    return SystemResult(
        system="phobert_ft",
        y_true=test["label"].tolist(),
        y_pred=y_pred,
        notes={
            "class_mapping": "identity on {Low, Moderate, High}; model cannot predict Severe",
            "test_size": len(test),
        },
    )


# ---------------------------------------------------------------------------
# LLM cache
# ---------------------------------------------------------------------------


# Evaluation runs at temperature 0, unlike the deployed app which uses the
# configured value. Two reasons, both discovered by measurement: a thesis result
# has to be reproducible, and the first run at temperature 0.2 produced 7 badly
# formed JSON replies out of 70 (a real one: `"confidence": 0. nine`) against 0
# at temperature 0. Each failure becomes a fallback label, so sampling noise was
# depressing the score of the system under test.
EVAL_TEMPERATURE = 0.0


@lru_cache(maxsize=1)
def _eval_llm():
    """Temperature-0 client shared by every llm_full evaluation call."""
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=EVAL_TEMPERATURE,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        max_retries=settings.llm_max_retries,
    )


def _cache_key(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_get(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def cache_put(cache_dir: Path, key: str, value: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _classify_failure(exc: Exception) -> str:
    """Separate "the model wrote bad JSON" from "the request never landed".

    Both end in the same fallback label, but they mean opposite things about the
    system: one is a model-behaviour result worth reporting, the other says the
    provider refused and nothing was measured. The 2026-09-08 run recorded 32
    failures of which 31 were HTTP 429 and exactly one was malformed JSON, so
    calling the whole set "unparseable" - as the earlier run's notes did, and as
    the report still says - misstates what happened.
    """
    from langchain_core.exceptions import OutputParserException

    if isinstance(exc, OutputParserException):
        return "parse_error"
    name = type(exc).__name__
    if "RateLimit" in name or "429" in str(exc)[:200]:
        # The body of a 429 is the only place the provider states the DAILY
        # token allowance - no response header carries it. Capture it here so
        # the next pre-flight can report real headroom instead of inferring it
        # from a probe small enough to fit through any remaining gap.
        from app.eval.quota import record_from_error

        record_from_error(exc)
        return "rate_limited"
    return "call_error"


def _record_parse_failure(cache_dir: Path, key: str, system: str, exc: Exception) -> None:
    """Persist one unparseable reply so the failure can be diagnosed later.

    Written beside the cache rather than into it, so a failure is never served
    back as though it were a result. Same privacy footing as the cache itself:
    on `--dataset synthetic` the content is generated text, and on
    `--dataset real` it is subject to the same handling as the cached
    reasoning strings that already live in this directory.
    """
    failure_dir = cache_dir / "_parse_failures"
    try:
        failure_dir.mkdir(parents=True, exist_ok=True)
        (failure_dir / f"{key}.json").write_text(
            json.dumps(
                {"system": system, "error_type": type(exc).__name__, "error": str(exc)[:4000]},
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
    except OSError as write_exc:  # diagnostics must never break a run
        logger.warning("could not record parse failure: %s", write_exc)


def _parse_label_json(raw: str) -> tuple[str | None, float | None]:
    """Extract {'label': ..., 'confidence': ...} from a possibly fenced reply."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None, None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None, None
    label = data.get("label")
    if label not in STRESS_LEVELS:
        return None, None
    confidence = data.get("confidence")
    return label, float(confidence) if isinstance(confidence, (int, float)) else None


# ---------------------------------------------------------------------------
# llm_zeroshot
# ---------------------------------------------------------------------------

ZEROSHOT_SYSTEM = """\
You are a classifier for academic stress levels in university students.
Based only on the passage provided, classify the stress level into exactly one
of four levels: Low, Moderate, High, Severe.
Return ONLY a single valid JSON object of the form: {"label": "<Low|Moderate|High|Severe>", "confidence": <0..1>}
Do not add any other text."""


async def _zeroshot_one(llm, semaphore: asyncio.Semaphore, text: str, cache_dir: Path) -> tuple[str, bool]:
    """Classify one text; returns (label, parse_ok). Cache-first."""
    settings = get_settings()
    key = _cache_key(
        {
            "system": "llm_zeroshot",
            "model": settings.openai_model,
            "endpoint": settings.openai_base_url,
            "text": text,
        }
    )
    cached = cache_get(cache_dir, key)
    if cached is not None:
        return cached["label"], cached.get("parse_ok", True)

    from langchain_core.messages import HumanMessage, SystemMessage

    async with semaphore:
        reply = await llm.ainvoke([SystemMessage(content=ZEROSHOT_SYSTEM), HumanMessage(content=text)])
    label, _confidence = _parse_label_json(reply.content)
    parse_ok = label is not None
    if label is None:
        # Deterministic fallback for unparseable replies; counted and reported.
        label = "Moderate"
    cache_put(cache_dir, key, {"label": label, "parse_ok": parse_ok, "raw": reply.content})
    return label, parse_ok


async def run_llm_zeroshot(df: pd.DataFrame, cache_dir: Path = DEFAULT_CACHE_DIR) -> SystemResult:
    """GPT-4o-mini on raw text only - no RAG, no questionnaire, no emotion."""
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.0,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        max_retries=settings.llm_max_retries,
    )
    test = df[df["split"] == "test"]
    semaphore = asyncio.Semaphore(settings.llm_concurrency)
    outcomes = await asyncio.gather(
        *[_zeroshot_one(llm, semaphore, text, cache_dir) for text in test["text"]]
    )
    y_pred = [label for label, _ in outcomes]
    parse_failures = sum(1 for _, ok in outcomes if not ok)
    return SystemResult(
        system="llm_zeroshot",
        y_true=test["label"].tolist(),
        y_pred=y_pred,
        notes={"parse_failures": parse_failures, "test_size": len(test), "temperature": 0.0},
    )


# ---------------------------------------------------------------------------
# llm_full (the proposed system)
# ---------------------------------------------------------------------------


async def _full_one(
    semaphore: asyncio.Semaphore,
    row: pd.Series,
    cache_dir: Path,
    use_rag: bool = True,
    use_questionnaire: bool = True,
    use_emotion: bool = True,
    cache_tag: str = "llm_full",
) -> tuple[str, bool]:
    """Run the proposed pipeline for one row (ablation-configurable)."""
    from app.api.services import build_rag_query
    from app.llm.chain import assess
    from app.nlp.emotion import analyze
    from app.rag.retriever import retrieve
    from app.scoring import score_dass21, score_pss10

    settings = get_settings()
    text = str(row["text"])

    dass_result = pss_result = None
    if use_questionnaire:
        dass_result = score_dass21(dass_answers_from_row(row))
        pss_result = score_pss10(pss_answers_from_row(row))

    key = _cache_key(
        {
            "system": cache_tag,
            "model": settings.openai_model,
            "endpoint": settings.openai_base_url,
            "temperature": EVAL_TEMPERATURE,
            # The key hashes inputs, not the retrieved passages, so a change to
            # the query construction is invisible to it. Bump this whenever the
            # retrieval path changes or the cache serves pre-change answers.
            "query_shape": "v2-build_rag_query",
            "text": text,
            "use_rag": use_rag,
            "use_questionnaire": use_questionnaire,
            "use_emotion": use_emotion,
            "dass": dass_result,
            "pss": pss_result,
        }
    )
    cached = cache_get(cache_dir, key)
    if cached is not None:
        return cached["label"], "ok"

    emotion = analyze(text) if use_emotion else None
    docs = []
    if use_rag:
        # Must be the *production* query, not a local approximation of it. This
        # path previously hand-rolled the query with the keywords prepended,
        # which is the reverse of the shape build_rag_query() was measured into
        # (RESULTS.md 4b) and produced a different top-4 chunk set on 53 % of
        # dataset items - so the number reported for the proposed system came
        # from a retrieval path the deployed system never runs.
        docs = retrieve(build_rag_query(text, emotion, None), k=4)

    async with semaphore:
        try:
            assessment = await assess(
                raw_text=text,
                emotion=emotion,
                dass_result=dass_result,
                pss_result=pss_result,
                stress_context=None,
                retrieved_docs=docs,
                llm=_eval_llm(),
            )
        except Exception as exc:  # noqa: BLE001 - one bad reply must not end the run
            # Weaker models occasionally emit malformed JSON (a real example:
            # `"confidence": 0. nine`). Treat it the same way the zero-shot path
            # does: fall back to a deterministic label, count it, and carry on.
            # Aborting would discard 69 good predictions because of one bad one.
            #
            # Record it. The 2026-09-08 run reported 7/70 parse failures and
            # then discarded the evidence, because this branch returned without
            # writing anything - leaving no way to tell a malformed number from
            # a wrapper the parser could have been taught to strip. The reply
            # text travels inside the exception, so persisting the exception is
            # enough to make the next run's failures diagnosable.
            _record_parse_failure(cache_dir, key, cache_tag, exc)
            kind = _classify_failure(exc)
            logger.warning("llm_full %s, using fallback label: %s", kind, exc)
            return "Moderate", kind

    label = assessment.predicted_level.value
    cache_put(
        cache_dir,
        key,
        {
            "label": label,
            "confidence": assessment.confidence,
            "reasoning": assessment.reasoning,
            "suggestions": assessment.suggestions,
            "risk_flags": assessment.risk_flags,
        },
    )
    return label, "ok"


async def run_llm_full(
    df: pd.DataFrame,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    use_rag: bool = True,
    use_questionnaire: bool = True,
    use_emotion: bool = True,
    system_id: str = "llm_full",
) -> SystemResult:
    """The proposed system (also the configurable engine for the ablation study).

    NOTE (reported wherever results appear): with `use_questionnaire=True` the
    prompt contains the DASS/PSS scores from which the ground-truth label is
    derived, so high agreement is partly by construction. The ablation
    configuration `no_questionnaire` quantifies performance without that signal.
    """
    if use_questionnaire and not has_questionnaire_items(df):
        raise RuntimeError("dataset lacks per-item DASS/PSS answers required by llm_full")

    test = df[df["split"] == "test"]
    semaphore = asyncio.Semaphore(get_settings().llm_concurrency)
    cache_tag = f"llm_full:{int(use_rag)}{int(use_questionnaire)}{int(use_emotion)}"
    outcomes = await asyncio.gather(
        *[
            _full_one(
                semaphore,
                row,
                cache_dir,
                use_rag=use_rag,
                use_questionnaire=use_questionnaire,
                use_emotion=use_emotion,
                cache_tag=cache_tag,
            )
            for _, row in test.iterrows()
        ]
    )
    # Reported, not hidden: each failure contributed a fallback "Moderate" rather
    # than a prediction, so a large count makes the metrics meaningless and the
    # reader has to be able to see that.
    kinds = [kind for _, kind in outcomes]
    parse_failures = sum(1 for k in kinds if k == "parse_error")
    rate_limited = sum(1 for k in kinds if k == "rate_limited")
    call_failures = sum(1 for k in kinds if k == "call_error")
    unusable = parse_failures + rate_limited + call_failures
    if unusable:
        logger.warning(
            "%s: %d/%d responses unusable and fell back to 'Moderate' "
            "(%d malformed JSON, %d rate-limited, %d other call errors)",
            system_id, unusable, len(test), parse_failures, rate_limited, call_failures,
        )

    return SystemResult(
        system=system_id,
        y_true=test["label"].tolist(),
        y_pred=[label for label, _ in outcomes],
        notes={
            "test_size": len(test),
            "parse_failures": parse_failures,
            "rate_limited": rate_limited,
            "call_failures": call_failures,
            "unusable": unusable,
            "use_rag": use_rag,
            "use_questionnaire": use_questionnaire,
            "use_emotion": use_emotion,
            "ground_truth_leakage": use_questionnaire,
        },
    )
