"""Shared pytest fixtures: temp SQLite DB and repo-root import path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable regardless of how pytest is invoked.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _real_llm_cache_is_read_only(monkeypatch):
    """No test may write into the real evaluation cache.

    The cache is keyed on inputs only, so a stubbed reply written under a real
    key is later served to a real run as though the model had said it. That
    happened: 85 stub entries (reasoning "x", suggestions ["a"]) written on
    2026-09-09 were served as 24/70 of the published llm_full predictions and
    40/40 of the no_questionnaire ablation. Tests must pass `cache_dir=tmp_path`.
    """
    from app.eval import baselines

    real_dir = baselines.DEFAULT_CACHE_DIR.resolve()
    original = baselines.cache_put

    def guarded(cache_dir, key, value):
        if Path(cache_dir).resolve() == real_dir:
            raise AssertionError(
                "test wrote to the real LLM cache; pass cache_dir=tmp_path"
            )
        original(cache_dir, key, value)

    monkeypatch.setattr(baselines, "cache_put", guarded)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Point the app at a fresh temp SQLite DB for the duration of a test."""
    from app import config
    from app.db import database

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    config.get_settings.cache_clear()
    database.reset_for_tests()
    database.init_db()
    yield
    database.reset_for_tests()
    config.get_settings.cache_clear()
