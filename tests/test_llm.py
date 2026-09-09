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
        result = check_crisis(raw_text="I dont want to live anymore")
        assert result.is_crisis
        assert "self_harm_language_in_text" in result.reasons
        assert result.message and "115" in result.message

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
            raw_text="I am under a lot of pressure from deadlines and cannot sleep",
            dass_answers=make_dass_answers(1),
            dass_depression_severity="Mild",
        )
        assert not result.is_crisis
        assert result.message is None

    def test_no_input_no_crisis(self):
        assert not check_crisis().is_crisis


VALID_LLM_JSON = json.dumps(
    {
        "predicted_level": "High",
        "confidence": 0.78,
        "reasoning": "You are showing several signs of stress: high DASS-21 scores, too little sleep and many deadlines.",
        "suggestions": [
            "Split assignments into 30-minute chunks and start with the easiest part.",
            "Keep a fixed bedtime and avoid screens 30 minutes before sleep.",
            "Talk to a friend you trust or your university counselling office.",
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
            stress_keywords=["pressure", "insomnia"],
            language=Language.VI,
            model_stress_level=StressLevel.HIGH,
        )
        docs = [RetrievedDoc(text="Enough sleep helps reduce stress.", source="04.md", heading="Sleep", distance=0.2)]
        result = await assess(
            raw_text="I am under so much deadline pressure that I cannot sleep at night.",
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
        assert len(result.suggestions) == 3
        assert "sleep_deprivation" in result.risk_flags

    @pytest.mark.asyncio
    async def test_wrapped_json_still_parses(self):
        """Fences, preamble and <think> blocks must not cost a whole assessment.

        The 2026-09-08 run lost 7/70 full-pipeline responses and 9/30 ablation
        responses to a strict parser, each falling back to a fixed "Moderate"
        label, while the zero-shot baseline - which cleaned its replies - lost
        none against the same model. Each wrapper below is a form that run saw.
        """
        wrappers = {
            "fenced": "```json\n" + VALID_LLM_JSON + "\n```",
            "bare_fence": "```\n" + VALID_LLM_JSON + "\n```",
            "preamble": "Here is my assessment:\n" + VALID_LLM_JSON,
            "trailing": VALID_LLM_JSON + "\n\nLet me know if you need more.",
            "think_block": "<think>weighing the evidence</think>\n" + VALID_LLM_JSON,
        }
        for name, content in wrappers.items():
            result = await assess(
                raw_text="test",
                emotion=None,
                dass_result=None,
                pss_result=None,
                stress_context=None,
                retrieved_docs=[],
                llm=make_fake_llm(content),
            )
            assert result.predicted_level == StressLevel.HIGH, name

    @pytest.mark.asyncio
    async def test_grounded_reply_with_one_suggestion_is_accepted(self):
        """Rule 4 outranks the count of 3, so the schema floor must allow it."""
        import json as _json

        payload = _json.loads(VALID_LLM_JSON)
        payload["suggestions"] = ["Keep a fixed bedtime, per the sleep material."]
        result = await assess(
            raw_text="test",
            emotion=None,
            dass_result=None,
            pss_result=None,
            stress_context=None,
            retrieved_docs=[],
            llm=make_fake_llm(_json.dumps(payload, ensure_ascii=False)),
        )
        assert len(result.suggestions) == 1

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
        assert "no free-text data" in format_emotion(None)

    def test_format_emotion_full(self):
        emotion = EmotionResult(
            emotion_label="negative",
            emotion_scores={"sentiment_neg": 0.9},
            sentiment_polarity=SentimentPolarity.NEGATIVE,
            stress_keywords=["stuck"],
        )
        text = format_emotion(emotion)
        assert "stuck" in text
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

    def test_format_retrieved_docs_labels_each_block_with_its_citable_id(self):
        """The chunk id is the citation handle the prompt tells the model to use.

        If it stops appearing, the model cannot cite anything the service is able
        to verify, and citation validation silently discards everything.
        """
        docs = [
            RetrievedDoc(
                text="Content.", source="01.md", heading="H", distance=0.1, chunk_id="01.md::0"
            )
        ]
        rendered = format_retrieved_docs(docs)
        assert "01.md::0" in rendered
        assert "Content." in rendered
        assert "H" in rendered

    def test_format_retrieved_docs_empty_states_the_refusal_rule(self):
        rendered = format_retrieved_docs([])
        assert "no reference material" in rendered
        # The model is told not to fill the gap from its own knowledge.
        assert "do not" in rendered.lower()
