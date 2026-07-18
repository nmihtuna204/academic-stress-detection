"""Emotion and stress detection module built on HuggingFace transformers.

Uses a pre-trained text-classification model to derive per-emotion scores
from free-text input, then combines them into a single stress score suitable
for surfacing alongside structured screening tools like DASS-21.

Note: the default model ("j-hartmann/emotion-english-distilroberta-base") is
English-only. If Vietnamese (or other non-English) text input is needed
later, swap MODEL_NAME to "cardiffnlp/twitter-xlm-roberta-base-sentiment".
That model only outputs 3 labels (positive/neutral/negative) instead of 7
emotions, so the stress_score formula in analyze_text() would need to be
reworked to use those labels instead of fear/sadness/anger/joy/disgust.
"""

from __future__ import annotations

from functools import lru_cache

from transformers import Pipeline, pipeline

MODEL_NAME = "j-hartmann/emotion-english-distilroberta-base"
MAX_TEXT_LENGTH = 2000


@lru_cache(maxsize=1)
def load_emotion_model() -> Pipeline:
    """Load (and cache) the emotion-classification pipeline.

    The model is only loaded from disk/network on the first call; subsequent
    calls return the cached pipeline instance, since loading it is slow and
    it should not be reloaded on every request.

    Returns:
        A HuggingFace `Pipeline` configured for multi-label text
        classification, returning scores for all emotion labels.
    """
    return pipeline(task="text-classification", model=MODEL_NAME, top_k=None)


def _validate_text(text: str) -> None:
    """Validate free-text input for emotion analysis.

    Raises:
        ValueError: if `text` is empty, whitespace-only, or longer than
            `MAX_TEXT_LENGTH` characters.
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty or whitespace-only")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(
            f"text must not exceed {MAX_TEXT_LENGTH} characters, got {len(text)}"
        )


def _compute_stress_score(emotions: dict[str, float]) -> float:
    """Compute a 0.0-1.0 stress score from raw per-emotion probabilities.

    Fear, sadness, and anger contribute positively to stress; disgust
    contributes lightly positively; joy contributes negatively; neutral
    and surprise are treated as stress-irrelevant (zero weight).

    Args:
        emotions: mapping of emotion label to probability (0.0-1.0).

    Returns:
        The weighted stress score, clipped to [0.0, 1.0].
    """
    raw_score = (
        0.4 * emotions.get("fear", 0.0)
        + 0.35 * emotions.get("sadness", 0.0)
        + 0.25 * emotions.get("anger", 0.0)
        + 0.1 * emotions.get("disgust", 0.0)
        - 0.3 * emotions.get("joy", 0.0)
    )
    return max(0.0, min(1.0, raw_score))


def analyze_text(text: str) -> dict:
    """Analyze free-text input for emotional content and derived stress level.

    Args:
        text: free-text input, e.g. a student's self-description of how
            they feel.

    Returns:
        A dict of the form:
        {
            "raw_emotions": {"fear": float, "sadness": float, "anger": float,
                              "joy": float, "neutral": float, "disgust": float,
                              "surprise": float},
            "stress_score": float,  # 0.0-1.0
            "dominant_emotion": str,
        }

    Raises:
        ValueError: if `text` is empty, whitespace-only, or too long.
    """
    _validate_text(text)

    model = load_emotion_model()
    predictions = model(text)[0]

    raw_emotions: dict[str, float] = {
        prediction["label"]: prediction["score"] for prediction in predictions
    }
    dominant_emotion = max(raw_emotions, key=raw_emotions.get)
    stress_score = _compute_stress_score(raw_emotions)

    return {
        "raw_emotions": raw_emotions,
        "stress_score": stress_score,
        "dominant_emotion": dominant_emotion,
    }


if __name__ == "__main__":
    sample_texts = [
        "I can't keep up with my exams, I feel like I'm drowning",
        "I went to class today and had lunch with friends",
        "I just finished my project and I feel great!",
    ]

    for sample_text in sample_texts:
        result = analyze_text(sample_text)
        print(f"Text: {sample_text!r}")
        print(f"  Dominant emotion: {result['dominant_emotion']}")
        print(f"  Stress score: {result['stress_score']:.3f}")
        print("  Raw emotions:")
        for label, score in sorted(
            result["raw_emotions"].items(), key=lambda item: item[1], reverse=True
        ):
            print(f"    {label:<10} {score:.3f}")
        print()
