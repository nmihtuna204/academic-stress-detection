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

# Concurrent in-flight LLM requests.
LLM_CONCURRENCY = 4


@dataclass
class SystemResult:
    system: str
    y_true: list[str]
    y_pred: list[str]
    notes: dict = field(default_factory=dict)


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

ZEROSHOT_SYSTEM_VI = """\
Bạn là công cụ phân loại mức độ căng thẳng học đường của sinh viên Việt Nam.
Chỉ dựa vào đoạn chia sẻ được đưa, hãy phân loại mức độ căng thẳng vào đúng một
trong bốn mức: Low, Moderate, High, Severe.
Trả về DUY NHẤT một JSON hợp lệ dạng: {"label": "<Low|Moderate|High|Severe>", "confidence": <0..1>}
Không thêm bất kỳ văn bản nào khác."""


async def _zeroshot_one(llm, semaphore: asyncio.Semaphore, text: str, cache_dir: Path) -> tuple[str, bool]:
    """Classify one text; returns (label, parse_ok). Cache-first."""
    settings = get_settings()
    key = _cache_key({"system": "llm_zeroshot", "model": settings.openai_model, "text": text})
    cached = cache_get(cache_dir, key)
    if cached is not None:
        return cached["label"], cached.get("parse_ok", True)

    from langchain_core.messages import HumanMessage, SystemMessage

    async with semaphore:
        reply = await llm.ainvoke([SystemMessage(content=ZEROSHOT_SYSTEM_VI), HumanMessage(content=text)])
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
    )
    test = df[df["split"] == "test"]
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
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
        return cached["label"], True

    emotion = analyze(text) if use_emotion else None
    docs = []
    if use_rag:
        query_parts = [text[:300]]
        if emotion and emotion.stress_keywords:
            query_parts.insert(0, " ".join(emotion.stress_keywords))
        docs = retrieve(" ".join(query_parts), k=4)

    async with semaphore:
        assessment = await assess(
            raw_text=text,
            emotion=emotion,
            dass_result=dass_result,
            pss_result=pss_result,
            stress_context=None,
            retrieved_docs=docs,
        )
    label = assessment.predicted_level.value
    cache_put(
        cache_dir,
        key,
        {
            "label": label,
            "confidence": assessment.confidence,
            "reasoning_vi": assessment.reasoning_vi,
            "suggestions_vi": assessment.suggestions_vi,
            "risk_flags": assessment.risk_flags,
        },
    )
    return label, True


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
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
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
    return SystemResult(
        system=system_id,
        y_true=test["label"].tolist(),
        y_pred=[label for label, _ in outcomes],
        notes={
            "test_size": len(test),
            "use_rag": use_rag,
            "use_questionnaire": use_questionnaire,
            "use_emotion": use_emotion,
            "ground_truth_leakage": use_questionnaire,
        },
    )
