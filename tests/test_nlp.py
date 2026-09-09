"""Tests for the lexicon and emotion module (models mocked/optional).

The lexicon is deliberately bilingual (see app/nlp/lexicon.py): the UI is
English, but Vietnamese entries are retained so the crisis rule keeps working
for Vietnamese free text. Both sides are covered here on purpose.
"""

import pytest

from app.nlp.lexicon import (
    ALL_KEYWORDS,
    find_crisis_keywords,
    find_stress_keywords,
)
from app.nlp.emotion import analyze, detect_language, _map_phobert_label
from app.schemas.enums import Language, SentimentPolarity


class TestLexicon:
    def test_lexicon_size(self):
        assert len(ALL_KEYWORDS) >= 80

    def test_finds_basic_keywords(self):
        text = "Lately I have been under a lot of pressure because of deadlines, and I can't sleep at night."
        found = find_stress_keywords(text)
        assert "pressure" in found
        assert "deadline" in found
        assert "can't sleep" in found

    def test_longest_phrase_wins(self):
        found = find_stress_keywords("I am under a lot of academic pressure.")
        assert "academic pressure" in found
        assert "pressure" not in found

    def test_case_insensitive(self):
        assert "stressed" in find_stress_keywords("I AM SO STRESSED")

    def test_clean_text_no_matches(self):
        assert find_stress_keywords("The weather is lovely today, I went out with friends.") == []

    def test_still_finds_vietnamese_keywords(self):
        """Vietnamese entries are retained, so Vietnamese input still matches."""
        text = "Dạo này mình rất áp lực vì deadline dồn dập, đêm nào cũng mất ngủ."
        found = find_stress_keywords(text)
        assert "áp lực" in found
        assert "mất ngủ" in found
        assert "dồn dập" in found


class TestCrisisKeywords:
    def test_detects_self_harm_language(self):
        assert find_crisis_keywords("sometimes I just want to die") == ["want to die"]
        assert find_crisis_keywords("I have thought about suicide before") == ["suicide"]

    def test_normal_stress_text_is_not_crisis(self):
        assert find_crisis_keywords("I am really stressed and tired because of exams") == []

    def test_still_detects_vietnamese_self_harm_language(self):
        """Safety-critical: Vietnamese crisis phrasing must not stop being caught."""
        assert find_crisis_keywords("nhiều lúc em muốn chết cho xong") == ["muốn chết"]
        assert find_crisis_keywords("em từng nghĩ đến tự tử") == ["tự tử"]


class TestLanguageDetection:
    def test_vietnamese(self):
        assert detect_language("Tuần này mình rất mệt mỏi vì ôn thi.") == Language.VI

    def test_english(self):
        assert detect_language("I am so stressed about my exams this week.") == Language.EN

    def test_mixed(self):
        assert detect_language("Mình cảm thấy rất stressed vì the deadline, I can't sleep được.") == Language.MIXED


class TestPhobertLabelMapping:
    def test_label_index_mapping(self):
        assert _map_phobert_label("LABEL_0") == "Low"
        assert _map_phobert_label("LABEL_2") == "High"

    def test_named_label_passthrough(self):
        assert _map_phobert_label("Moderate") == "Moderate"


class TestAnalyzeLexiconFallback:
    """analyze() must work with no ML models available (lexicon-only mode).

    This is also the path English input takes in practice: PhoBERT is a
    Vietnamese-only encoder, so English text is scored by the lexicon alone.
    """

    @pytest.fixture(autouse=True)
    def no_models(self, monkeypatch):
        from app.nlp import emotion as emotion_module

        monkeypatch.setattr(emotion_module, "_load_stress_classifier", lambda: None)

    def test_stressful_text(self):
        result = analyze(
            "I am overwhelmed and exhausted, and I can't sleep at night worrying about exams."
        )
        assert result.sentiment_polarity == SentimentPolarity.NEGATIVE
        assert "exhausted" in result.stress_keywords
        assert result.language == Language.EN
        assert result.model_stress_level is None

    def test_neutral_text(self):
        result = analyze("Today I studied with friends at the library.")
        assert result.sentiment_polarity == SentimentPolarity.NEUTRAL
        assert result.stress_keywords == []

    def test_vietnamese_text_still_analysed(self):
        result = analyze("Em quá tải và kiệt sức, đêm nào cũng mất ngủ vì lo lắng chuyện thi cử.")
        assert result.sentiment_polarity == SentimentPolarity.NEGATIVE
        assert "kiệt sức" in result.stress_keywords
        assert result.language == Language.VI

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError):
            analyze("   ")

    def test_too_long_text_rejected(self):
        with pytest.raises(ValueError):
            analyze("a" * 4001)


class TestAnalyzeWithMockedModels:
    def make_stress_clf(self, low, moderate, high):
        def fake_stress_clf(text):
            return [[
                {"label": "LABEL_0", "score": low},
                {"label": "LABEL_1", "score": moderate},
                {"label": "LABEL_2", "score": high},
            ]]

        return fake_stress_clf

    def test_stress_classifier_output_used(self, monkeypatch):
        from app.nlp import emotion as emotion_module

        monkeypatch.setattr(
            emotion_module, "_load_stress_classifier",
            lambda: self.make_stress_clf(0.1, 0.2, 0.7),
        )
        # Vietnamese input: PhoBERT is the language it was trained on, so it runs.
        result = analyze("Em áp lực lắm, deadline dồn dập.")
        assert result.model_stress_level == "High"
        assert result.emotion_label == "stress_high"
        assert result.sentiment_polarity == SentimentPolarity.NEGATIVE
        assert result.emotion_scores["stress_high"] == 0.7

    def test_classifier_skipped_for_english_input(self, monkeypatch):
        """PhoBERT is Vietnamese-only; on English input it must not be consulted.

        It would still return a confident-looking label, and surfacing that as
        "stress level per the model" would present noise as signal.
        """
        from app.nlp import emotion as emotion_module

        monkeypatch.setattr(
            emotion_module, "_load_stress_classifier",
            lambda: self.make_stress_clf(0.1, 0.2, 0.7),
        )
        result = analyze("I am under so much pressure because of deadlines this week.")
        assert result.language == Language.EN
        assert result.model_stress_level is None
        assert result.emotion_scores == {}
        # The lexicon still carries the signal.
        assert "pressure" in result.stress_keywords

    def test_polarity_derived_from_stress_and_lexicon(self, monkeypatch):
        """The model-driven polarity path. Vietnamese input, since that is the
        only language for which the classifier is consulted at all."""
        from app.nlp import emotion as emotion_module

        # Moderate stress + a stress keyword -> negative.
        monkeypatch.setattr(
            emotion_module, "_load_stress_classifier",
            lambda: self.make_stress_clf(0.2, 0.7, 0.1),
        )
        assert analyze("Em áp lực lắm.").sentiment_polarity == SentimentPolarity.NEGATIVE
        # Moderate stress, no keywords -> neutral.
        assert analyze("Tuần này bình thường thôi.").sentiment_polarity == SentimentPolarity.NEUTRAL
        # Low stress -> neutral even with a keyword present.
        monkeypatch.setattr(
            emotion_module, "_load_stress_classifier",
            lambda: self.make_stress_clf(0.8, 0.1, 0.1),
        )
        assert analyze("Hơi lo lắng nhưng ổn.").sentiment_polarity == SentimentPolarity.NEUTRAL
