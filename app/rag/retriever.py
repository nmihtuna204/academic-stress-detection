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
    # Stable identifier assigned at ingest ("<file>::<index>"). Chroma returns it
    # alongside the documents, so it costs nothing to carry. It is what the
    # retrieval evaluation scores against and what the generator cites, neither
    # of which can rely on (source, heading) staying unique once a long section
    # is split across chunks.
    chunk_id: str = ""


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
        ids = result.get("ids") or [[]]
        docs: list[RetrievedDoc] = []
        for i, (text, meta, dist) in enumerate(
            zip(result["documents"][0], result["metadatas"][0], result["distances"][0])
        ):
            docs.append(
                RetrievedDoc(
                    text=text,
                    source=str(meta.get("source", "")),
                    heading=str(meta.get("heading", "")),
                    distance=float(dist),
                    chunk_id=str(ids[0][i]) if i < len(ids[0]) else "",
                )
            )
        return docs
    except Exception as exc:
        logger.error("RAG retrieval failed: %s", exc)
        return []
