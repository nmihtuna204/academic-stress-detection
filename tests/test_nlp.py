"""Tests for the lexicon and emotion module (models mocked/optional)."""

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
        text = "Dạo này mình rất áp lực vì deadline dồn dập, đêm nào cũng mất ngủ."
        found = find_stress_keywords(text)
        assert "áp lực" in found
        assert "deadline" in found
        assert "mất ngủ" in found
        assert "dồn dập" in found

    def test_longest_phrase_wins(self):
        found = find_stress_keywords("Em chịu nhiều áp lực học tập.")
        assert "áp lực học tập" in found
        assert "áp lực" not in found

    def test_case_insensitive(self):
        assert "stress" in find_stress_keywords("MÌNH RẤT STRESS")

    def test_clean_text_no_matches(self):
        assert find_stress_keywords("Hôm nay trời đẹp, mình đi chơi với bạn.") == []


class TestCrisisKeywords:
    def test_detects_self_harm_language(self):
        assert find_crisis_keywords("nhiều lúc em muốn chết cho xong") == ["muốn chết"]
        assert find_crisis_keywords("em từng nghĩ đến tự tử") == ["tự tử"]

    def test_normal_stress_text_is_not_crisis(self):
        assert find_crisis_keywords("em rất áp lực và mệt mỏi vì thi cử") == []


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
    """analyze() must work with no ML models available (lexicon-only mode)."""

    @pytest.fixture(autouse=True)
    def no_models(self, monkeypatch):
        from app.nlp import emotion as emotion_module

        monkeypatch.setattr(emotion_module, "_load_stress_classifier", lambda: None)
        monkeypatch.setattr(emotion_module, "_load_sentiment_model", lambda: None)

    def test_stressful_text(self):
        result = analyze("Em quá tải và kiệt sức, đêm nào cũng mất ngủ vì lo lắng chuyện thi cử.")
        assert result.sentiment_polarity == SentimentPolarity.NEGATIVE
        assert "kiệt sức" in result.stress_keywords
        assert result.language == Language.VI
        assert result.model_stress_level is None

    def test_neutral_text(self):
        result = analyze("Hôm nay mình học nhóm với bạn ở thư viện.")
        assert result.sentiment_polarity == SentimentPolarity.NEUTRAL
        assert result.stress_keywords == []

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError):
            analyze("   ")

    def test_too_long_text_rejected(self):
        with pytest.raises(ValueError):
            analyze("a" * 4001)


class TestAnalyzeWithMockedModels:
    def test_stress_classifier_output_used(self, monkeypatch):
        from app.nlp import emotion as emotion_module

        def fake_stress_clf(text):
            return [[
                {"label": "LABEL_0", "score": 0.1},
                {"label": "LABEL_1", "score": 0.2},
                {"label": "LABEL_2", "score": 0.7},
            ]]

        def fake_sentiment_clf(text):
            return [[
                {"label": "NEG", "score": 0.8},
                {"label": "NEU", "score": 0.15},
                {"label": "POS", "score": 0.05},
            ]]

        monkeypatch.setattr(emotion_module, "_load_stress_classifier", lambda: fake_stress_clf)
        monkeypatch.setattr(emotion_module, "_load_sentiment_model", lambda: fake_sentiment_clf)

        result = analyze("Em áp lực lắm.")
        assert result.model_stress_level == "High"
        assert result.emotion_label == "stress_high"
        assert result.sentiment_polarity == SentimentPolarity.NEGATIVE
        assert result.emotion_scores["stress_high"] == 0.7
        assert result.emotion_scores["sentiment_neg"] == 0.8
