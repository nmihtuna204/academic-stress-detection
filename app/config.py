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
    # Any OpenAI-compatible endpoint. Left empty, the client talks to OpenAI
    # itself. Set it to use Groq, OpenRouter, a local Ollama server or similar,
    # which is what makes a free or self-hosted key usable here.
    #
    # Whatever is set here MUST be recorded in the report and in the consent
    # document: docs/consent_form_vi.md §4 currently names OpenAI specifically,
    # and sending student free text somewhere else silently would break the
    # consent the participant actually gave.
    openai_base_url: str = ""
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60.0
    # Concurrent in-flight LLM requests during evaluation. Free tiers rate-limit
    # aggressively, so this is tunable rather than hardcoded; drop it to 1 or 2
    # if a provider starts returning 429.
    llm_concurrency: int = 4
    # Retries on transient errors, chiefly HTTP 429. A token-per-minute cap is a
    # pacing problem, not a failure: the provider tells you how long to wait and
    # the request succeeds on retry. Without this an evaluation run aborts
    # partway and reports "not run" for a system that was merely going too fast.
    llm_max_retries: int = 8

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


def llm_provider_identity() -> tuple[str, str]:
    """Return (provider_name, jurisdiction) for the CONFIGURED LLM endpoint.

    Consent language and the report must name whoever actually receives
    student text, not whoever the project started with. This was already
    wrong once: the project moved from OpenAI to Groq, and the in-app
    consent screen and the report kept saying "OpenAI" until this was
    added. Deriving the name from `openai_base_url` at read time means a
    future provider change cannot silently invalidate consent again in the
    same way - an unrecognised host still gets a truthful (if generic)
    label instead of a wrong specific one.
    """
    base_url = get_settings().openai_base_url.strip().lower()
    if not base_url or "api.openai.com" in base_url:
        return "OpenAI", "the United States"
    if "groq.com" in base_url:
        return "Groq", "the United States"
    if "openrouter.ai" in base_url:
        return "OpenRouter", "the United States"
    if "generativelanguage.googleapis.com" in base_url:
        return "Google", "the United States"
    if any(local in base_url for local in ("localhost", "127.0.0.1", "0.0.0.0")):
        return "a locally-hosted model", "this machine (no third-party transmission)"
    # Unknown endpoint: name the host rather than guessing a company, so the
    # consent text stays truthful even for a provider not listed above.
    from urllib.parse import urlparse

    host = urlparse(base_url).netloc or base_url
    return f"the configured provider ({host})", "an unverified jurisdiction — confirm before use"
