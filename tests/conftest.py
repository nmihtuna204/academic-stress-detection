"""Shared pytest fixtures: temp SQLite DB and repo-root import path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable regardless of how pytest is invoked.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
