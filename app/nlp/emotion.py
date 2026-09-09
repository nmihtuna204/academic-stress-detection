"""Emotion analysis for free-text stress input.

Model strategy (each layer degrades gracefully if unavailable):
1. Local fine-tuned PhoBERT stress classifier (`models/phobert-stress`,
   3-class Low/Moderate/High) - the primary signal. Fully offline.
2. Lexicon-only analysis (always available, offline).

LANGUAGE CAVEAT: PhoBERT is a Vietnamese-only encoder fine-tuned on Vietnamese
student text, so its stress prediction is only meaningful for Vietnamese input.
English input still works, but it falls through to the bilingual lexicon path
(`model_stress_level=None`), which `_derive_polarity` and `analyze` already
handle. Making the model layer work in English would require fine-tuning an
English encoder on labelled English data - a modelling task, not a translation.

Sentiment polarity is DERIVED from the stress prediction and the keyword
lexicon rather than a separate sentiment model: a dedicated hub-downloaded
sentiment model added no signal the stress classifier doesn't already carry,
plus a network dependency (see DECISIONS.md, defense-strengthening Phase 6).

The model is loaded lazily and cached, so the first request pays the load
cost once per process.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from app.config import get_settings
from app.nlp.lexicon import find_stress_keywords, normalize
from app.schemas.enums import Language, SentimentPolarity, StressLevel
from app.schemas.models import EmotionResult

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 4000

# Label order used when the local PhoBERT stress classifier was fine-tuned.
_PHOBERT_STRESS_LABELS = ["Low", "Moderate", "High"]

_VI_CHARS = re.compile(r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]")
_EN_HINT_WORDS = frozenset(
    "the a an and or but i you we they he she it is are was were not this that "
    "my your of to in on for with at have has do does feel felt so very really".split()
)


def detect_language(text: str) -> Language:
    """Heuristic vi/en/mixed detection via diacritics and English stopwords."""
    normalized = normalize(text)
    words = re.findall(r"[a-zA-Zăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ']+", normalized)
    if not words:
        return Language.VI
    has_diacritics = bool(_VI_CHARS.search(normalized))
    english_ratio = sum(1 for w in words if w in _EN_HINT_WORDS) / len(words)
    if has_diacritics and english_ratio > 0.15:
        return Language.MIXED
    if has_diacritics:
        return Language.VI
    if english_ratio > 0.2:
        return Language.EN
    # No diacritics and no clear English signal. The UI is English, so English is
    # the better default here; unaccented Vietnamese is still caught by the
    # diacritics branch above whenever the student types accents.
    return Language.EN


@lru_cache(maxsize=1)
def _load_stress_classifier():
    """Load the local fine-tuned PhoBERT stress classifier, or None."""
    settings = get_settings()
    try:
        from transformers import pipeline

        clf = pipeline(
            task="text-classification",
            model=settings.phobert_stress_model_dir,
            top_k=None,
            truncation=True,
            max_length=256,
        )
        logger.info("Loaded local PhoBERT stress classifier from %s", settings.phobert_stress_model_dir)
        return clf
    except Exception as exc:  # model dir missing, torch issues, ...
        logger.warning("Local PhoBERT stress classifier unavailable: %s", exc)
        return None


def _map_phobert_label(raw_label: str) -> str:
    """Map a raw classifier label (possibly LABEL_i) to a stress-level name."""
    if raw_label.upper().startswith("LABEL_"):
        try:
            return _PHOBERT_STRESS_LABELS[int(raw_label.split("_")[1])]
        except (IndexError, ValueError):
            return raw_label
    return raw_label


def _derive_polarity(
    model_stress_level: StressLevel | None, keyword_count: int
) -> SentimentPolarity:
    """Polarity from the stress prediction and lexicon (no sentiment model).

    High stress reads as negative; Moderate is negative only when the lexicon
    corroborates; everything else is neutral (the pipeline has no positive
    signal to detect, and neutral is the honest default).
    """
    if model_stress_level == StressLevel.HIGH:
        return SentimentPolarity.NEGATIVE
    if model_stress_level == StressLevel.MODERATE and keyword_count >= 1:
        return SentimentPolarity.NEGATIVE
    if model_stress_level is None and keyword_count >= 2:
        return SentimentPolarity.NEGATIVE
    return SentimentPolarity.NEUTRAL


def analyze(text: str) -> EmotionResult:
    """Analyze one free-text entry: emotion label, scores, polarity, keywords.

    Never raises because a model is missing - degrades to lexicon-only.

    Raises:
        ValueError: if `text` is empty/blank or exceeds MAX_TEXT_LENGTH.
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty or whitespace-only")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"text must not exceed {MAX_TEXT_LENGTH} characters, got {len(text)}")

    language = detect_language(text)
    keywords = find_stress_keywords(text)

    emotion_scores: dict[str, float] = {}
    model_stress_level: StressLevel | None = None

    # PhoBERT is a Vietnamese-only encoder fine-tuned on Vietnamese student text.
    # Run it only on input it can actually read: given English it still returns a
    # confident-looking label, and surfacing that to a student as "stress level per
    # the model" would be presenting noise as signal. Skipping it here drops through
    # to the lexicon-only path handled below, which is the honest answer.
    stress_clf = _load_stress_classifier() if language in (Language.VI, Language.MIXED) else None
    if stress_clf is not None:
        try:
            predictions = stress_clf(text)[0]
            stress_scores = {
                _map_phobert_label(p["label"]): round(float(p["score"]), 4) for p in predictions
            }
            emotion_scores.update({f"stress_{k.lower()}": v for k, v in stress_scores.items()})
            top = max(stress_scores, key=stress_scores.get)
            if top in StressLevel.__members__.values() or top in ("Low", "Moderate", "High"):
                model_stress_level = StressLevel(top)
        except Exception as exc:
            logger.warning("PhoBERT stress inference failed: %s", exc)

    sentiment = _derive_polarity(model_stress_level, len(keywords))

    if model_stress_level is not None:
        emotion_label = f"stress_{model_stress_level.value.lower()}"
    elif sentiment == SentimentPolarity.NEGATIVE:
        emotion_label = "negative"
    elif sentiment == SentimentPolarity.POSITIVE:
        emotion_label = "positive"
    else:
        emotion_label = "neutral"

    return EmotionResult(
        emotion_label=emotion_label,
        emotion_scores=emotion_scores,
        sentiment_polarity=sentiment,
        stress_keywords=keywords,
        language=language,
        model_stress_level=model_stress_level,
    )


def warmup() -> dict[str, bool]:
    """Eagerly load models (called at API startup); report availability."""
    return {"phobert_stress": _load_stress_classifier() is not None}
