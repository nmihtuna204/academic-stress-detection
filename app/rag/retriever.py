"""Retrieval interface over the ChromaDB knowledge collection."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.rag.store import get_collection

logger = logging.getLogger(__name__)


@dataclass
class RetrievedDoc:
    text: str
    source: str
    heading: str
    distance: float


def retrieve(query: str, k: int = 4) -> list[RetrievedDoc]:
    """Return the top-k knowledge chunks most relevant to `query`.

    Returns an empty list when the collection is empty or the query is blank,
    never raises on retrieval failure (RAG is a best-effort enhancement).
    """
    if not query or not query.strip():
        return []
    try:
        collection = get_collection()
        if collection.count() == 0:
            logger.warning("Knowledge collection is empty - run `python -m app.rag.ingest`")
            return []
        result = collection.query(query_texts=[query], n_results=min(k, collection.count()))
        docs: list[RetrievedDoc] = []
        for text, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            docs.append(
                RetrievedDoc(
                    text=text,
                    source=str(meta.get("source", "")),
                    heading=str(meta.get("heading", "")),
                    distance=float(dist),
                )
            )
        return docs
    except Exception as exc:
        logger.error("RAG retrieval failed: %s", exc)
        return []
