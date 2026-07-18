"""Integration tests for the FastAPI endpoints (NLP/RAG/LLM mocked)."""

import pytest
from fastapi.testclient import TestClient

from app.rag.retriever import RetrievedDoc
from app.schemas.enums import Language, SentimentPolarity, StressLevel
from app.schemas.models import EmotionResult, LlmAssessment


FAKE_EMOTION = EmotionResult(
    emotion_label="stress_high",
    emotion_scores={"stress_high": 0.8},
    sentiment_polarity=SentimentPolarity.NEGATIVE,
    stress_keywords=["áp lực", "deadline"],
    language=Language.VI,
    model_stress_level=StressLevel.HIGH,
)

FAKE_ASSESSMENT = LlmAssessment(
    predicted_level=StressLevel.HIGH,
    confidence=0.8,
    reasoning_vi="Bạn có nhiều dấu hiệu căng thẳng.",
    suggestions_vi=["Ngủ đủ giấc.", "Chia nhỏ bài tập.", "Chia sẻ với bạn bè."],
    risk_flags=[],
)


@pytest.fixture()
def client(tmp_db, monkeypatch):
    from app.api import main, services

    async def fake_llm_assess(**kwargs):
        return FAKE_ASSESSMENT

    monkeypatch.setattr(main, "analyze", lambda text: FAKE_EMOTION)
    monkeypatch.setattr(services, "analyze", lambda text: FAKE_EMOTION)
    monkeypatch.setattr(
        services,
        "retrieve",
        lambda query, k=4: [RetrievedDoc(text="Tài liệu.", source="01.md", heading="H", distance=0.1)],
    )
    monkeypatch.setattr(services, "llm_assess", fake_llm_assess)
    with TestClient(main.app) as test_client:
        yield test_client


def full_dass(value: int = 1) -> dict:
    return {"answers": {str(i): value for i in range(1, 22)}}


def full_pss(value: int = 2) -> dict:
    return {"answers": {str(i): value for i in range(1, 11)}}


class TestHealth:
    def test_health_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAssessText:
    def test_returns_emotion_and_creates_user(self, client):
        response = client.post("/assess/text", json={"raw_text": "Em rất áp lực vì deadline."})
        assert response.status_code == 200
        body = response.json()
        assert body["student_id"]
        assert body["emotion"]["emotion_label"] == "stress_high"
        assert body["crisis_detected"] is False
        assert "chẩn đoán" in body["disclaimer_vi"]

    def test_blank_text_rejected(self, client):
        assert client.post("/assess/text", json={"raw_text": "   "}).status_code == 422

    def test_crisis_text_bypasses_normal_flow(self, client):
        response = client.post("/assess/text", json={"raw_text": "em muốn chết cho xong"})
        assert response.status_code == 200
        body = response.json()
        assert body["crisis_detected"] is True
        assert "115" in body["crisis_message_vi"]


class TestAssessQuestionnaire:
    def test_scores_both_instruments(self, client):
        response = client.post(
            "/assess/questionnaire", json={"dass21": full_dass(1), "pss10": full_pss(2)}
        )
        assert response.status_code == 200
        q = response.json()["questionnaire"]
        assert q["dass21"]["depression_score"] == 14
        assert q["pss10"]["pss_total_score"] == 20
        assert q["ground_truth_label"] in ("Low", "Moderate", "High", "Severe")

    def test_pss_only(self, client):
        response = client.post("/assess/questionnaire", json={"pss10": full_pss(0)})
        assert response.status_code == 200
        q = response.json()["questionnaire"]
        assert q["dass21"] is None
        assert q["pss10"]["pss_total_score"] == 16

    def test_neither_rejected(self, client):
        assert client.post("/assess/questionnaire", json={}).status_code == 422

    def test_out_of_range_answer_rejected(self, client):
        bad = full_dass(1)
        bad["answers"]["5"] = 7
        assert client.post("/assess/questionnaire", json={"dass21": bad}).status_code == 422

    def test_dass_risk_items_trigger_crisis(self, client):
        answers = {str(i): 0 for i in range(1, 22)}
        answers["17"] = 3
        answers["21"] = 3
        response = client.post("/assess/questionnaire", json={"dass21": {"answers": answers}})
        assert response.status_code == 200
        assert response.json()["crisis_detected"] is True


class TestAssessFull:
    def test_full_pipeline(self, client):
        payload = {
            "raw_text": "Em rất áp lực vì deadline và mất ngủ.",
            "dass21": full_dass(1),
            "pss10": full_pss(3),
            "stress_context": {"sleep_hours_avg": 4.5, "is_exam_period": True},
        }
        response = client.post("/assess/full", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["prediction_id"]
        assert body["assessment"]["predicted_level"] == "High"
        assert len(body["assessment"]["suggestions_vi"]) == 3
        assert body["rag_sources"]
        assert body["questionnaire"]["ground_truth_label"]

    def test_empty_payload_rejected(self, client):
        assert client.post("/assess/full", json={}).status_code == 422

    def test_llm_failure_still_returns_deterministic_results(self, client, monkeypatch):
        from app.api import services

        async def broken_llm(**kwargs):
            raise RuntimeError("LLM down")

        monkeypatch.setattr(services, "llm_assess", broken_llm)
        response = client.post("/assess/full", json={"dass21": full_dass(1)})
        assert response.status_code == 200
        body = response.json()
        assert body["crisis_detected"] is False
        assert body["assessment"] is None
        assert body["questionnaire"]["dass21"]["depression_score"] == 14


class TestHistory:
    def test_history_roundtrip(self, client):
        created = client.post("/assess/full", json={"raw_text": "Áp lực quá.", "pss10": full_pss(3)})
        student_id = created.json()["student_id"]

        response = client.get(f"/history/{student_id}")
        assert response.status_code == 200
        body = response.json()
        assert len(body["text_entries"]) == 1
        assert len(body["questionnaire_responses"]) == 1
        assert len(body["predictions"]) == 1

    def test_unknown_student_404(self, client):
        assert client.get("/history/nonexistent-id").status_code == 404
