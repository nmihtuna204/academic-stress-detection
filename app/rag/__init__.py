"""RAG package: ChromaDB ingestion and retrieval over the knowledge base."""

from app.rag.ingest import ingest, load_knowledge_chunks
from app.rag.retriever import RetrievedDoc, retrieve

__all__ = ["ingest", "load_knowledge_chunks", "retrieve", "RetrievedDoc"]
