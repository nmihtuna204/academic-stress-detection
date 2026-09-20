"""Retrieval interface over the ChromaDB knowledge collection."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.rag.store import embedding_model_name, get_collection

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
    # True when the passage was added by policy rather than ranked by the query
    # (see app.api.services.retrieve_for_assessment); its distance is then NaN.
    pinned: bool = False


def fetch_chunks(chunk_ids: list[str]) -> list[RetrievedDoc]:
    """Fetch specific chunks by id, in the order given; missing ids are skipped.

    No embedding is involved, so this is unaffected by the query model. Returns
    an empty list on any store failure, like `retrieve`.
    """
    if not chunk_ids:
        return []
    try:
        result = get_collection().get(ids=list(chunk_ids), include=["documents", "metadatas"])
        by_id = {
            cid: (text, meta)
            for cid, text, meta in zip(result["ids"], result["documents"], result["metadatas"], strict=True)
        }
        missing = [cid for cid in chunk_ids if cid not in by_id]
        if missing:
            logger.error("Pinned knowledge chunks missing from the store: %s", missing)
        return [
            RetrievedDoc(
                text=by_id[cid][0],
                source=str(by_id[cid][1].get("source", "")),
                heading=str(by_id[cid][1].get("heading", "")),
                distance=float("nan"),
                chunk_id=cid,
                pinned=True,
            )
            for cid in chunk_ids
            if cid in by_id
        ]
    except Exception as exc:
        logger.error("Fetching pinned chunks failed: %s", exc)
        return []


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
        # Fail closed on an embedding mismatch. The query was embedded by this
        # process's model; if the chunks were embedded by another, the ranking
        # is meaningless, and an empty result makes the service withhold advice
        # rather than ground it in unrelated passages. Chunks ingested before
        # the stamp existed carry none and are accepted with a warning.
        current = embedding_model_name()
        stamps = {m.get("embedding_model") for m in result["metadatas"][0]} - {None}
        if stamps and stamps != {current}:
            logger.error(
                "Knowledge chunks were embedded with %s but queries use %s; refusing to "
                "retrieve. Re-run `python -m app.rag.ingest` after deleting data/chroma.",
                sorted(stamps), current,
            )
            return []
        if not stamps:
            logger.warning("Knowledge chunks carry no embedding-model stamp; re-run ingest")
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
