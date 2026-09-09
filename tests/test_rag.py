"""Tests for the RAG pipeline: chunking, ingestion, and retrieval.

Uses a temp Chroma persist dir; ingestion/retrieval tests exercise the real
ChromaDB stack (with whatever embedding function is available locally).
"""

import pytest

from app.rag.ingest import ingest, load_knowledge_chunks, split_markdown


@pytest.fixture()
def tmp_chroma(tmp_path, monkeypatch):
    from app import config
    from app.rag import store

    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("CHROMA_COLLECTION_NAME", "test_knowledge")
    config.get_settings.cache_clear()
    store.get_client.cache_clear()
    yield
    store.get_client.cache_clear()
    config.get_settings.cache_clear()


class TestChunking:
    def test_split_by_headings_prepends_title(self):
        md = "# Title\n\nIntro.\n\n## Section one\n\nBody 1.\n\n## Section two\n\nBody 2.\n"
        chunks = split_markdown(md, source="doc.md")
        assert len(chunks) == 2
        assert all(c.text.startswith("Title") for c in chunks)
        assert chunks[0].heading == "Section one"
        assert chunks[1].heading == "Section two"

    def test_oversized_section_is_split(self):
        body = "\n\n".join(f"Paragraph number {i}. " + "x" * 300 for i in range(10))
        md = f"# T\n\n## Long\n\n{body}"
        chunks = split_markdown(md, source="long.md")
        assert len(chunks) > 1
        assert all(len(c.text) < 2100 for c in chunks)

    def test_real_knowledge_dir_loads(self):
        chunks = load_knowledge_chunks()
        assert len(chunks) >= 15
        sources = {c.source for c in chunks}
        assert "01_academic_stress.md" in sources
        assert "03_support_resources_vietnam.md" in sources


@pytest.mark.requires_network
class TestIngestAndRetrieve:
    """Exercises real ChromaDB + embeddings; downloads a model on cold cache."""

    def test_ingest_then_retrieve(self, tmp_chroma):
        from app.rag.retriever import retrieve

        count = ingest()
        assert count >= 15

        docs = retrieve("cannot sleep before exams, not getting enough rest", k=3)
        assert 1 <= len(docs) <= 3
        assert all(d.text for d in docs)
        assert all(d.source.endswith(".md") for d in docs)
        # The sleep-hygiene document should surface for a sleep query.
        assert any("04_sleep" in d.source or "sleep" in d.text.lower() for d in docs)

    def test_ingest_is_idempotent(self, tmp_chroma):
        from app.rag.store import get_collection

        first = ingest()
        second = ingest()
        assert first == second
        assert get_collection().count() == first

    def test_retrieve_blank_query_returns_empty(self, tmp_chroma):
        from app.rag.retriever import retrieve

        assert retrieve("   ") == []

    def test_retrieve_on_empty_collection_returns_empty(self, tmp_chroma):
        from app.rag.retriever import retrieve

        assert retrieve("stress") == []
