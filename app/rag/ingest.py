"""ChromaDB ingestion pipeline for the stress-knowledge base.

Reads Markdown files from `data/knowledge/`, splits them into
heading-delimited chunks, and upserts them into a persistent Chroma
collection. Idempotent: chunk ids are deterministic (file + index), so
re-running refreshes content in place.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.rag.store import embedding_model_name, get_collection

logger = logging.getLogger(__name__)

# Chunks longer than this are further split on paragraph boundaries.
MAX_CHUNK_CHARS = 1500


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source: str
    heading: str


def split_markdown(text: str, source: str) -> list[Chunk]:
    """Split a Markdown document into chunks by ##-level headings.

    The document title (# heading) is prepended to every chunk so each
    chunk stays self-describing for embedding/retrieval.
    """
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else source

    # Split on ## headings, keeping the heading with its section body.
    sections = re.split(r"(?=^##\s)", text, flags=re.MULTILINE)
    chunks: list[Chunk] = []
    for section in sections:
        section = section.strip()
        if not section or section.startswith("# "):  # skip bare title block
            continue
        heading_match = re.match(r"^##\s+(.+)$", section, flags=re.MULTILINE)
        heading = heading_match.group(1).strip() if heading_match else title

        # Secondary split for oversized sections.
        parts: list[str] = []
        if len(section) > MAX_CHUNK_CHARS:
            current = ""
            for paragraph in section.split("\n\n"):
                if current and len(current) + len(paragraph) > MAX_CHUNK_CHARS:
                    parts.append(current)
                    current = paragraph
                else:
                    current = f"{current}\n\n{paragraph}" if current else paragraph
            if current:
                parts.append(current)
        else:
            parts = [section]

        for part in parts:
            chunks.append(
                Chunk(
                    chunk_id=f"{source}::{len(chunks)}",
                    text=f"{title}\n\n{part}",
                    source=source,
                    heading=heading,
                )
            )
    return chunks


def load_knowledge_chunks(knowledge_dir: str | Path | None = None) -> list[Chunk]:
    """Load and chunk every Markdown file in the knowledge directory."""
    directory = Path(knowledge_dir or get_settings().knowledge_dir)
    chunks: list[Chunk] = []
    for md_file in sorted(directory.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks.extend(split_markdown(text, source=md_file.name))
    return chunks


def ingest(knowledge_dir: str | Path | None = None) -> int:
    """Upsert all knowledge chunks into the persistent Chroma collection.

    Returns the number of chunks ingested.
    """
    chunks = load_knowledge_chunks(knowledge_dir)
    if not chunks:
        logger.warning("No knowledge chunks found to ingest")
        return 0

    collection = get_collection()
    model = embedding_model_name()
    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        # The model stamp lets the retriever refuse queries embedded by a
        # different model, which would otherwise fail silently.
        metadatas=[{"source": c.source, "heading": c.heading, "embedding_model": model} for c in chunks],
    )
    logger.info("Ingested %d chunks into collection %r", len(chunks), collection.name)
    return len(chunks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = ingest()
    print(f"Ingested {count} chunks.")
