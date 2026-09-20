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
    stress_keywords=["pressure", "deadline"],
    language=Language.VI,
    model_stress_level=StressLevel.HIGH,
)

FAKE_DOC = RetrievedDoc(
    text="A document.", source="01.md", heading="H", distance=0.1, chunk_id="01.md::0"
)


def make_assessment(citations: list[str] | None = None) -> LlmAssessment:
    return LlmAssessment(
        predicted_level=StressLevel.HIGH,
        confidence=0.8,
        reasoning="You are showing several signs of stress.",
        suggestions=["Get enough sleep.", "Break assignments down.", "Talk to a friend."],
        risk_flags=[],
        citations=list(citations) if citations is not None else ["01.md::0"],
    )


FAKE_ASSESSMENT = make_assessment()


@pytest.fixture()
def client(tmp_db, monkeypatch):
    from app.api import main, services

    async def fake_llm_assess(**kwargs):
        return FAKE_ASSESSMENT

    monkeypatch.setattr(main, "analyze", lambda text: FAKE_EMOTION)
    monkeypatch.setattr(services, "analyze", lambda text: FAKE_EMOTION)
    monkeypatch.setattr(services, "retrieve", lambda query, k=4: [FAKE_DOC])
    monkeypatch.setattr(services, "fetch_chunks", lambda ids: [])
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
        response = client.post("/assess/text", json={"raw_text": "I am under a lot of pressure because of deadlines."})
        assert response.status_code == 200
        body = response.json()
        assert body["student_id"]
        assert body["emotion"]["emotion_label"] == "stress_high"
        assert body["crisis_detected"] is False
        assert "diagnostic" in body["disclaimer"]

    def test_blank_text_rejected(self, client):
        assert client.post("/assess/text", json={"raw_text": "   "}).status_code == 422

    def test_crisis_text_bypasses_normal_flow(self, client):
        response = client.post("/assess/text", json={"raw_text": "I want to kill myself"})
        assert response.status_code == 200
        body = response.json()
        assert body["crisis_detected"] is True
        assert "115" in body["crisis_message"]


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
            "raw_text": "I am under a lot of pressure from deadlines and I cannot sleep.",
            "dass21": full_dass(1),
            "pss10": full_pss(3),
            "stress_context": {"sleep_hours_avg": 4.5, "is_exam_period": True},
        }
        response = client.post("/assess/full", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["prediction_id"]
        assert body["assessment"]["predicted_level"] == "High"
        assert len(body["assessment"]["suggestions"]) == 3
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
        created = client.post("/assess/full", json={"raw_text": "So much pressure.", "pss10": full_pss(3)})
        student_id = created.json()["student_id"]

        response = client.get(f"/history/{student_id}")
        assert response.status_code == 200
        body = response.json()
        assert len(body["text_entries"]) == 1
        assert len(body["questionnaire_responses"]) == 1
        assert len(body["predictions"]) == 1

    def test_unknown_student_404(self, client):
        assert client.get("/history/nonexistent-id").status_code == 404


class TestAdviceFailureIsExplained:
    """A missing advice section must say why it is missing.

    Retrieval returning nothing already set `advice_unavailable_reason`, but a
    failing generation call did not: the page rendered an empty advice block
    with no explanation, which reads as a broken screen rather than a degraded
    one and leaves the student guessing whether the silence means something
    about their results.
    """

    def test_generation_failure_sets_a_reason(self, client, monkeypatch):
        import app.api.services as services

        async def boom(**kwargs):
            raise RuntimeError("Error code: 429 - rate_limit_exceeded")

        monkeypatch.setattr(services, "llm_assess", boom)
        response = client.post(
            "/assess/full",
            json={
                "raw_text": "I am behind on every subject and I sleep badly.",
                "dass21": {"answers": {str(i): 1 for i in range(1, 22)}},
                "pss10": {"answers": {str(i): 2 for i in range(1, 11)}},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["assessment"] is None
        assert body["advice_unavailable_reason"], "a silent empty advice section is the bug"
        # The deterministic half must still be complete.
        assert body["questionnaire"] is not None
        assert body["questionnaire"]["ground_truth_label"]


class TestGrounding:
    """Advice must be traceable to retrieved material, or not given at all."""

    def test_no_retrieval_means_no_generated_advice(self, client, monkeypatch):
        """With nothing retrieved there is nothing to ground advice in.

        Generating anyway is the exact failure the retrieval layer exists to
        prevent, so the pipeline refuses rather than falling back on the model's
        own knowledge.
        """
        from app.api import services

        called = False

        async def must_not_be_called(**kwargs):
            nonlocal called
            called = True
            return FAKE_ASSESSMENT

        monkeypatch.setattr(services, "retrieve", lambda query, k=4: [])
        monkeypatch.setattr(services, "llm_assess", must_not_be_called)

        response = client.post("/assess/full", json={"dass21": full_dass(1)})
        body = response.json()

        assert called is False, "the generator must not run without retrieved context"
        assert body["assessment"] is None
        assert body["advice_unavailable_reason"]
        # Deterministic scoring is unaffected by the refusal.
        assert body["questionnaire"]["dass21"]["depression_score"] == 14

    def test_declining_to_advise_is_explained_to_the_student(self, client, monkeypatch):
        """Retrieved material that covers nothing yields an empty list, said aloud.

        Rule 4 lets the model return no suggestions rather than invent some. The
        page must then say advice was withheld, not render an empty section.
        """
        from app.api import services

        declined = FAKE_ASSESSMENT.model_copy(update={"suggestions": [], "citations": []})

        async def declines(**kwargs):
            return declined

        monkeypatch.setattr(services, "llm_assess", declines)
        body = client.post("/assess/full", json={"dass21": full_dass(1)}).json()

        assert body["assessment"]["suggestions"] == []
        assert body["assessment"]["predicted_level"] == "High"
        assert body["advice_unavailable_reason"]

    def test_valid_citations_are_resolved_to_readable_sources(self, client):
        response = client.post("/assess/full", json={"dass21": full_dass(1)})
        body = response.json()
        assert body["assessment"]["citations"] == ["01.md::0"]
        assert body["cited_sources"] == ["01.md — H"]

    def test_citations_not_in_retrieved_context_are_discarded(self, client, monkeypatch):
        """A citation the model invented is a fabricated provenance claim."""
        from app.api import services

        async def fabricating_llm(**kwargs):
            return make_assessment(citations=["01.md::0", "99_invented.md::7"])

        monkeypatch.setattr(services, "llm_assess", fabricating_llm)

        body = client.post("/assess/full", json={"dass21": full_dass(1)}).json()
        assert body["assessment"]["citations"] == ["01.md::0"]
        assert body["cited_sources"] == ["01.md — H"]

    def test_uncited_advice_is_reported_as_uncited(self, client, monkeypatch):
        from app.api import services

        async def uncited_llm(**kwargs):
            return make_assessment(citations=[])

        monkeypatch.setattr(services, "llm_assess", uncited_llm)

        body = client.post("/assess/full", json={"dass21": full_dass(1)}).json()
        assert body["assessment"] is not None
        assert body["cited_sources"] == []

    def test_retrieved_and_cited_are_reported_separately(self, client, monkeypatch):
        """`rag_sources` is what was searched; it is not evidence of use."""
        from app.api import services

        async def partly_cited(**kwargs):
            return make_assessment(citations=[])

        monkeypatch.setattr(services, "llm_assess", partly_cited)

        body = client.post("/assess/full", json={"dass21": full_dass(1)}).json()
        assert body["rag_sources"] == ["01.md — H"]
        assert body["cited_sources"] == []


class TestCrisisDisclosuresAreNotRetained:
    """The crisis rule must clear before anything the student disclosed is stored.

    Persisting a self-harm disclosure and only then deciding it was a crisis is
    the worst-case ordering: the most sensitive text in the system would be the
    text most certainly written to disk.
    """

    def test_crisis_text_is_not_stored(self, client):
        response = client.post("/assess/text", json={"raw_text": "I want to kill myself"})
        student_id = response.json()["student_id"]

        history = client.get(f"/history/{student_id}").json()
        assert history["text_entries"] == []

    def test_crisis_questionnaire_is_not_stored(self, client):
        answers = {str(i): 0 for i in range(1, 22)}
        answers["17"] = 3
        answers["21"] = 3
        response = client.post("/assess/questionnaire", json={"dass21": {"answers": answers}})
        assert response.json()["crisis_detected"] is True
        student_id = response.json()["student_id"]

        history = client.get(f"/history/{student_id}").json()
        assert history["questionnaire_responses"] == []

    def test_full_pipeline_stores_nothing_on_crisis(self, client):
        payload = {
            "raw_text": "I want to kill myself",
            "dass21": full_dass(2),
            "pss10": full_pss(3),
            "stress_context": {"sleep_hours_avg": 4.0},
        }
        response = client.post("/assess/full", json=payload)
        body = response.json()
        assert body["crisis_detected"] is True

        history = client.get(f"/history/{body['student_id']}").json()
        assert history["text_entries"] == []
        assert history["questionnaire_responses"] == []
        assert history["predictions"] == []

    def test_non_crisis_input_is_still_stored(self, client):
        """The guard must not silently stop ordinary submissions being recorded."""
        response = client.post("/assess/full", json={"raw_text": "So much pressure.", "pss10": full_pss(3)})
        history = client.get(f"/history/{response.json()['student_id']}").json()
        assert len(history["text_entries"]) == 1
        assert len(history["questionnaire_responses"]) == 1


class TestDeleteSession:
    """The consent document promises a right to withdraw; this is it."""

    def test_delete_removes_every_trace(self, client):
        created = client.post(
            "/assess/full",
            json={
                "raw_text": "So much pressure.",
                "dass21": full_dass(1),
                "pss10": full_pss(3),
                "stress_context": {"sleep_hours_avg": 6.0},
            },
        )
        student_id = created.json()["student_id"]
        assert client.get(f"/history/{student_id}").status_code == 200

        response = client.delete(f"/session/{student_id}")
        assert response.status_code == 200
        deleted = response.json()["deleted"]
        assert deleted["text_entries"] == 1
        assert deleted["questionnaire_responses"] == 1
        assert deleted["stress_contexts"] == 1
        assert deleted["predictions"] == 1
        assert deleted["users"] == 1

        # The id itself is gone, so history can no longer resolve it.
        assert client.get(f"/history/{student_id}").status_code == 404

    def test_delete_unknown_student_404(self, client):
        assert client.delete("/session/nonexistent-id").status_code == 404

    def test_delete_is_not_repeatable(self, client):
        created = client.post("/assess/text", json={"raw_text": "So much pressure."})
        student_id = created.json()["student_id"]
        assert client.delete(f"/session/{student_id}").status_code == 200
        assert client.delete(f"/session/{student_id}").status_code == 404


class TestSupportMaterialPinning:
    """Students screened High/Severe must have help-seeking material in context.

    Rule 4 forbids advice absent from the passages, and the ranked top 4 held no
    support-resource passage for any of 70 test items, so a referral to
    professional help could never be grounded without this.
    """

    PINNED = [
        RetrievedDoc(text="When to seek help.", source="01.md", heading="Seek help",
                     distance=float("nan"), chunk_id="01_academic_stress.md::3", pinned=True),
        RetrievedDoc(text="Counselling offices.", source="03.md", heading="Counselling",
                     distance=float("nan"), chunk_id="03_support_resources_vietnam.md::1", pinned=True),
    ]

    @pytest.fixture()
    def seen(self, client, monkeypatch):
        from app.api import services

        captured: dict = {"fetched": None, "docs": None}

        def fake_fetch(ids):
            captured["fetched"] = list(ids)
            return [d for d in self.PINNED if d.chunk_id in ids]

        async def capture(**kwargs):
            captured["docs"] = kwargs["retrieved_docs"]
            return FAKE_ASSESSMENT

        monkeypatch.setattr(services, "fetch_chunks", fake_fetch)
        monkeypatch.setattr(services, "llm_assess", capture)
        return captured

    @staticmethod
    def severe_stress_dass() -> dict:
        """Stress subscale maximal, every other item 0: Severe label, no crisis items."""
        stress_items = {1, 6, 8, 11, 12, 14, 18}
        return {"answers": {str(i): 3 if i in stress_items else 0 for i in range(1, 22)}}

    def test_high_screening_puts_support_passages_in_context(self, client, seen):
        body = client.post("/assess/full", json={"dass21": self.severe_stress_dass()}).json()
        assert body["questionnaire"]["ground_truth_label"] == "Severe"
        ids = [d.chunk_id for d in seen["docs"]]
        assert ids[0] == "01.md::0", "ranked results come first and are unchanged"
        assert "01_academic_stress.md::3" in ids
        assert "03_support_resources_vietnam.md::1" in ids

    def test_low_screening_is_left_alone(self, client, seen):
        client.post("/assess/full", json={"dass21": full_dass(0), "pss10": full_pss(0)})
        assert seen["fetched"] is None
        assert [d.chunk_id for d in seen["docs"]] == ["01.md::0"]

    def test_a_support_passage_already_ranked_is_not_duplicated(self, client, seen, monkeypatch):
        from app.api import services

        ranked = [self.PINNED[0]]
        monkeypatch.setattr(services, "retrieve", lambda query, k=4: ranked)
        client.post("/assess/full", json={"dass21": self.severe_stress_dass()})
        assert seen["fetched"] == ["03_support_resources_vietnam.md::1"]

    @pytest.mark.parametrize(
        ("dass_depression", "dass_anxiety", "dass_stress", "pss", "expected"),
        [
            ("Normal", "Normal", "Normal", "Low", False),
            ("Severe", "Normal", "Normal", "Low", True),  # severe depression alone
            ("Normal", "Extremely Severe", "Normal", "Low", True),  # severe anxiety alone
            ("Normal", "Normal", "Severe", "Low", True),  # stress maps to High
            ("Moderate", "Moderate", "Mild", "Moderate", False),
        ],
    )
    def test_trigger_rule(self, dass_depression, dass_anxiety, dass_stress, pss, expected):
        from app.api.services import needs_support_material

        dass = {
            "depression": {"severity": dass_depression},
            "anxiety": {"severity": dass_anxiety},
            "stress": {"severity": dass_stress},
        }
        assert needs_support_material(dass, {"category": pss}) is expected

    def test_pinned_ids_exist_in_the_knowledge_base(self):
        """Chunk ids derive from file names; a rename would silently unpin them."""
        from app.api.services import SUPPORT_CHUNK_IDS
        from app.rag.ingest import load_knowledge_chunks

        ids = {c.chunk_id for c in load_knowledge_chunks()}
        assert set(SUPPORT_CHUNK_IDS) <= ids
