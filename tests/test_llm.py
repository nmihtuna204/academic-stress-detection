"""Tests for the safety rules and the LangChain chain (LLM mocked)."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.llm.chain import (
    assess,
    build_chain,
    format_context,
    format_emotion,
    format_questionnaires,
    format_retrieved_docs,
)
from app.llm.safety import check_crisis
from app.rag.retriever import RetrievedDoc
from app.schemas.enums import Language, SentimentPolarity, StressLevel
from app.schemas.models import EmotionResult, StressContextIn


def make_dass_answers(value: int = 0, overrides: dict[int, int] | None = None) -> dict[int, int]:
    answers = {qid: value for qid in range(1, 22)}
    if overrides:
        answers.update(overrides)
    return answers


class TestCrisisDetection:
    def test_self_harm_text_triggers(self):
        result = check_crisis(raw_text="em thấy không muốn sống nữa")
        assert result.is_crisis
        assert "self_harm_language_in_text" in result.reasons
        assert result.message_vi and "115" in result.message_vi

    def test_maximal_risk_items_trigger(self):
        answers = make_dass_answers(0, {17: 3, 21: 3})
        result = check_crisis(dass_answers=answers)
        assert result.is_crisis
        assert "dass_risk_items_maximal" in result.reasons

    def test_extremely_severe_depression_with_risk_item_triggers(self):
        answers = make_dass_answers(0, {17: 2})
        result = check_crisis(
            dass_answers=answers, dass_depression_severity="Extremely Severe"
        )
        assert result.is_crisis

    def test_ordinary_stress_does_not_trigger(self):
        result = check_crisis(
            raw_text="em rất áp lực vì deadline và mất ngủ",
            dass_answers=make_dass_answers(1),
            dass_depression_severity="Mild",
        )
        assert not result.is_crisis
        assert result.message_vi is None

    def test_no_input_no_crisis(self):
        assert not check_crisis().is_crisis


VALID_LLM_JSON = json.dumps(
    {
        "predicted_level": "High",
        "confidence": 0.78,
        "reasoning_vi": "Bạn đang có nhiều dấu hiệu căng thẳng: điểm DASS-21 ở mức cao, thiếu ngủ và nhiều deadline.",
        "suggestions_vi": [
            "Chia nhỏ bài tập thành các phần 30 phút và làm phần dễ trước.",
            "Cố định giờ ngủ, tránh màn hình 30 phút trước khi ngủ.",
            "Chia sẻ với một người bạn tin tưởng hoặc phòng tham vấn của trường.",
        ],
        "risk_flags": ["sleep_deprivation"],
    },
    ensure_ascii=False,
)


def make_fake_llm(content: str = VALID_LLM_JSON):
    return FakeMessagesListChatModel(responses=[AIMessage(content=content)])


class TestChain:
    @pytest.mark.asyncio
    async def test_assess_returns_structured_output(self):
        emotion = EmotionResult(
            emotion_label="stress_high",
            emotion_scores={"stress_high": 0.8},
            sentiment_polarity=SentimentPolarity.NEGATIVE,
            stress_keywords=["áp lực", "mất ngủ"],
            language=Language.VI,
            model_stress_level=StressLevel.HIGH,
        )
        docs = [RetrievedDoc(text="Ngủ đủ giấc giúp giảm stress.", source="04.md", heading="Ngủ", distance=0.2)]
        result = await assess(
            raw_text="Em rất áp lực vì deadline, đêm nào cũng mất ngủ.",
            emotion=emotion,
            dass_result={
                "depression": {"score": 10, "severity": "Mild"},
                "anxiety": {"score": 8, "severity": "Mild"},
                "stress": {"score": 28, "severity": "Severe"},
                "overall_severity": "Severe",
            },
            pss_result={"total_score": 30, "category": "High"},
            stress_context=StressContextIn(sleep_hours_avg=4.5, is_exam_period=True),
            retrieved_docs=docs,
            llm=make_fake_llm(),
        )
        assert result.predicted_level == StressLevel.HIGH
        assert result.confidence == pytest.approx(0.78)
        assert len(result.suggestions_vi) == 3
        assert "sleep_deprivation" in result.risk_flags

    @pytest.mark.asyncio
    async def test_invalid_llm_output_raises(self):
        with pytest.raises(Exception):
            await assess(
                raw_text="test",
                emotion=None,
                dass_result=None,
                pss_result=None,
                stress_context=None,
                retrieved_docs=[],
                llm=make_fake_llm("this is not json"),
            )

    def test_build_chain_with_fake_llm(self):
        chain = build_chain(llm=make_fake_llm())
        result = chain.invoke(
            {
                "raw_text": "x",
                "emotion_summary": "y",
                "questionnaire_summary": "z",
                "context_summary": "c",
                "retrieved_docs": "d",
            }
        )
        assert result.predicted_level == StressLevel.HIGH


class TestPromptFormatting:
    def test_format_emotion_none(self):
        assert "không có" in format_emotion(None)

    def test_format_emotion_full(self):
        emotion = EmotionResult(
            emotion_label="negative",
            emotion_scores={"sentiment_neg": 0.9},
            sentiment_polarity=SentimentPolarity.NEGATIVE,
            stress_keywords=["bế tắc"],
        )
        text = format_emotion(emotion)
        assert "bế tắc" in text
        assert "negative" in text

    def test_format_questionnaires_both(self):
        text = format_questionnaires(
            {
                "depression": {"score": 10, "severity": "Mild"},
                "anxiety": {"score": 8, "severity": "Mild"},
                "stress": {"score": 20, "severity": "Moderate"},
                "overall_severity": "Moderate",
            },
            {"total_score": 22, "category": "Moderate"},
        )
        assert "DASS-21" in text and "PSS-10" in text
        assert "22/40" in text

    def test_format_context_selected_fields(self):
        text = format_context(StressContextIn(sleep_hours_avg=5, financial_stress=4))
        assert "5" in text and "4" in text

    def test_format_retrieved_docs(self):
        docs = [RetrievedDoc(text="Nội dung.", source="01.md", heading="H", distance=0.1)]
        assert "Tài liệu 1" in format_retrieved_docs(docs)
        assert "không có tài liệu" in format_retrieved_docs([])
