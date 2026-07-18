"""Application configuration via pydantic-settings.

All secrets and environment-specific values come from environment variables
or a local `.env` file (see `.env.example`). Never hardcode keys.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenAI / LLM ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60.0

    # --- Database ---
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'stress_app.db'}"

    # --- RAG / ChromaDB ---
    chroma_persist_dir: str = str(PROJECT_ROOT / "data" / "chroma")
    chroma_collection_name: str = "stress_knowledge"
    knowledge_dir: str = str(PROJECT_ROOT / "data" / "knowledge")

    # --- NLP models ---
    # Local fine-tuned PhoBERT stress classifier (preferred if present).
    phobert_stress_model_dir: str = str(PROJECT_ROOT / "models" / "phobert-stress")

    # --- API ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # --- Streamlit ---
    # Base URL the Streamlit frontend uses to reach the FastAPI backend.
    api_base_url: str = "http://127.0.0.1:8000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
