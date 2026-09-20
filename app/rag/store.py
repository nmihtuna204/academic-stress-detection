"""Persistent ChromaDB client and embedding-function selection.

Embedding preference order:
1. `paraphrase-multilingual-MiniLM-L12-v2` via sentence-transformers -
   local, handles Vietnamese well.
2. Chroma's default ONNX MiniLM (English-leaning, still functional).

Both are cached per-process.

The fallback is only safe for a collection built with it. Both models emit
384-dimensional vectors, so a query embedded by one against chunks embedded by
the other raises nothing and returns plausible-looking nonsense. Ingest
therefore stamps each chunk with `embedding_model_name()`, and the retriever
refuses results stamped with a different model (see `app.rag.retriever`).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

MULTILINGUAL_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
FALLBACK_EMBEDDING_MODEL = "chroma-default-all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_embedding_function():
    """Pick the best available embedding function (None = Chroma default)."""
    try:
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        fn = SentenceTransformerEmbeddingFunction(model_name=MULTILINGUAL_EMBEDDING_MODEL)
        # Force a tiny embed now so failures surface here, not mid-request.
        fn(["health check"])
        logger.info("Using multilingual sentence-transformers embeddings")
        return fn
    except Exception as exc:
        logger.warning(
            "Multilingual embedding model unavailable (%s); falling back to Chroma default", exc
        )
        return None


def embedding_model_name() -> str:
    """Name of the embedding model this process embeds queries and chunks with."""
    if _get_embedding_function() is not None:
        return MULTILINGUAL_EMBEDDING_MODEL
    return FALLBACK_EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_client():
    """Create (once) and return the persistent Chroma client."""
    import chromadb

    persist_dir = get_settings().chroma_persist_dir
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def get_collection():
    """Get or create the knowledge collection with the chosen embeddings."""
    settings = get_settings()
    kwargs = {"name": settings.chroma_collection_name, "metadata": {"hnsw:space": "cosine"}}
    embedding_fn = _get_embedding_function()
    if embedding_fn is not None:
        kwargs["embedding_function"] = embedding_fn
    return get_client().get_or_create_collection(**kwargs)


def reset_for_tests() -> None:
    """Clear cached client/embedding so tests can repoint the persist dir."""
    get_client.cache_clear()
    _get_embedding_function.cache_clear()
