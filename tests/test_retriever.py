"""Thorough tests for RAG retrieval (ChromaDB collection mocked, no network).

Covers the branches app/rag/retriever.retrieve never exercised outside the
network-marked ingestion tests: empty collection, blank query, k-capping,
field mapping, and the best-effort exception swallow.
"""

from __future__ import annotations

import pytest

from app.rag.retriever import RetrievedDoc, retrieve


class FakeCollection:
    """Minimal stand-in for a Chroma collection."""

    def __init__(self, docs: list[tuple[str, str, str, float]], raise_on_query: bool = False,
                 stamp: str | None = "test-model"):
        # docs: list of (text, source, heading, distance)
        self._docs = docs
        self._raise = raise_on_query
        self._stamp = stamp
        self.last_n_results: int | None = None

    def count(self) -> int:
        return len(self._docs)

    def query(self, query_texts, n_results):
        if self._raise:
            raise RuntimeError("boom")
        self.last_n_results = n_results
        chosen = self._docs[:n_results]
        return {
            "documents": [[d[0] for d in chosen]],
            "metadatas": [[
                {"source": d[1], "heading": d[2]}
                | ({"embedding_model": self._stamp} if self._stamp else {})
                for d in chosen
            ]],
            "distances": [[d[3] for d in chosen]],
        }


@pytest.fixture(autouse=True)
def _query_model(monkeypatch):
    """Queries in these tests are 'embedded' by test-model; no real model loads."""
    monkeypatch.setattr("app.rag.retriever.embedding_model_name", lambda: "test-model")


@pytest.fixture()
def patch_collection(monkeypatch):
    def _install(collection):
        monkeypatch.setattr("app.rag.retriever.get_collection", lambda: collection)
        return collection

    return _install


SAMPLE_DOCS = [
    ("Enough sleep helps reduce stress.", "04_sleep.md", "Sleep", 0.11),
    ("Break assignments into smaller pieces.", "02_coping.md", "Time management", 0.22),
    ("Find your university counselling office.", "03_support.md", "Support", 0.33),
    ("Family pressure.", "06_family.md", "Family", 0.44),
    ("The DASS scale.", "05_scales.md", "DASS", 0.55),
]


class TestRetrieveHappyPath:
    def test_returns_retrieved_docs_with_all_fields(self, patch_collection):
        patch_collection(FakeCollection(SAMPLE_DOCS))
        docs = retrieve("insomnia because of exams", k=3)
        assert len(docs) == 3
        assert all(isinstance(d, RetrievedDoc) for d in docs)
        first = docs[0]
        assert first.text == "Enough sleep helps reduce stress."
        assert first.source == "04_sleep.md"
        assert first.heading == "Sleep"
        assert first.distance == pytest.approx(0.11)

    def test_k_is_capped_at_collection_count(self, patch_collection):
        collection = patch_collection(FakeCollection(SAMPLE_DOCS[:2]))
        docs = retrieve("stress", k=4)
        assert len(docs) == 2
        # retrieve() must not ask for more than the collection holds.
        assert collection.last_n_results == 2

    def test_default_k_is_four(self, patch_collection):
        patch_collection(FakeCollection(SAMPLE_DOCS))
        assert len(retrieve("stress")) == 4


class TestRetrieveEdgeCases:
    def test_empty_collection_returns_empty(self, patch_collection):
        patch_collection(FakeCollection([]))
        assert retrieve("any query at all") == []

    @pytest.mark.parametrize("query", ["", "   ", "\n\t", None])
    def test_blank_or_none_query_returns_empty_without_touching_store(self, query, monkeypatch):
        # get_collection must not even be called for a blank query.
        def _boom():
            raise AssertionError("get_collection should not be called for blank query")

        monkeypatch.setattr("app.rag.retriever.get_collection", _boom)
        assert retrieve(query) == []

    def test_query_exception_is_swallowed(self, patch_collection):
        # RAG is a best-effort enhancement; a store failure must degrade to [].
        patch_collection(FakeCollection(SAMPLE_DOCS, raise_on_query=True))
        assert retrieve("stress") == []

    def test_get_collection_exception_is_swallowed(self, monkeypatch):
        def _boom():
            raise RuntimeError("chroma unavailable")

        monkeypatch.setattr("app.rag.retriever.get_collection", _boom)
        assert retrieve("stress") == []


class TestEmbeddingModelMismatch:
    """Both candidate models emit 384-d vectors, so a mismatch fails silently.

    Retrieval must refuse instead: an empty result makes the service withhold
    advice, where a wrong one would ground advice in unrelated passages.
    """

    def test_chunks_from_another_model_are_refused(self, patch_collection):
        patch_collection(FakeCollection(SAMPLE_DOCS, stamp="chroma-default-all-MiniLM-L6-v2"))
        assert retrieve("stress") == []

    def test_chunks_from_the_same_model_are_returned(self, patch_collection):
        patch_collection(FakeCollection(SAMPLE_DOCS, stamp="test-model"))
        assert len(retrieve("stress")) == 4

    def test_unstamped_legacy_chunks_are_still_served(self, patch_collection):
        patch_collection(FakeCollection(SAMPLE_DOCS, stamp=None))
        assert len(retrieve("stress")) == 4
