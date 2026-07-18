"""Vietnamese emotion/sentiment analysis for free-text stress input.

Model strategy (each layer degrades gracefully if unavailable):
1. Local fine-tuned PhoBERT stress classifier (`models/phobert-stress`,
   3-class Low/Moderate/High) - the primary stress signal.
2. `wonrax/phobert-base-vietnamese-sentiment` for sentiment polarity
   (POS/NEG/NEU), downloaded from the HuggingFace hub.
3. Lexicon-only analysis (always available, offline).

Models are loaded lazily and cached, so the first request pays the load cost
once per process.
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
    # No diacritics, no clear English signal: likely unaccented Vietnamese.
    return Language.VI


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


@lru_cache(maxsize=1)
def _load_sentiment_model():
    """Load the Vietnamese sentiment model from the HF hub, or None."""
    settings = get_settings()
    try:
        from transformers import pipeline

        clf = pipeline(
            task="text-classification",
            model=settings.hf_sentiment_model,
            top_k=None,
            truncation=True,
            max_length=256,
        )
        logger.info("Loaded sentiment model %s", settings.hf_sentiment_model)
        return clf
    except Exception as exc:  # offline, model renamed, ...
        logger.warning("Sentiment model %s unavailable: %s", settings.hf_sentiment_model, exc)
        return None


def _map_phobert_label(raw_label: str) -> str:
    """Map a raw classifier label (possibly LABEL_i) to a stress-level name."""
    if raw_label.upper().startswith("LABEL_"):
        try:
            return _PHOBERT_STRESS_LABELS[int(raw_label.split("_")[1])]
        except (IndexError, ValueError):
            return raw_label
    return raw_label


_SENTIMENT_MAP = {
    "POS": SentimentPolarity.POSITIVE,
    "NEG": SentimentPolarity.NEGATIVE,
    "NEU": SentimentPolarity.NEUTRAL,
    "POSITIVE": SentimentPolarity.POSITIVE,
    "NEGATIVE": SentimentPolarity.NEGATIVE,
    "NEUTRAL": SentimentPolarity.NEUTRAL,
}


def _lexicon_fallback_polarity(keyword_count: int) -> SentimentPolarity:
    if keyword_count >= 2:
        return SentimentPolarity.NEGATIVE
    if keyword_count == 1:
        return SentimentPolarity.NEUTRAL
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
    sentiment = None

    stress_clf = _load_stress_classifier()
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

    sentiment_clf = _load_sentiment_model()
    if sentiment_clf is not None:
        try:
            predictions = sentiment_clf(text)[0]
            for p in predictions:
                emotion_scores[f"sentiment_{p['label'].lower()}"] = round(float(p["score"]), 4)
            top_label = max(predictions, key=lambda p: p["score"])["label"]
            sentiment = _SENTIMENT_MAP.get(top_label.upper())
        except Exception as exc:
            logger.warning("Sentiment inference failed: %s", exc)

    if sentiment is None:
        sentiment = _lexicon_fallback_polarity(len(keywords))

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
    return {
        "phobert_stress": _load_stress_classifier() is not None,
        "sentiment": _load_sentiment_model() is not None,
    }
