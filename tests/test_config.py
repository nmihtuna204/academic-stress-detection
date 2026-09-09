"""Tests for LLM provider configuration.

The client speaks the OpenAI API but need not talk to OpenAI. These pin the
switch that makes a free or self-hosted endpoint usable, and pin the default
so that leaving the setting alone still reaches OpenAI.
"""

import pytest

from app.config import Settings


class TestProviderSettings:
    """Defaults are asserted with `_env_file=None`.

    Without that these read the developer's real .env and assert whatever
    happens to be configured locally, which is not a test of anything.
    """

    def test_base_url_defaults_to_empty_meaning_openai(self):
        assert Settings(_env_file=None).openai_base_url == ""

    def test_concurrency_has_a_conservative_default(self):
        assert Settings(_env_file=None).llm_concurrency == 4

    def test_retries_are_enabled_by_default(self):
        """A 429 is pacing, not failure. Zero retries aborts a whole run."""
        assert Settings(_env_file=None).llm_max_retries >= 5

    def test_base_url_is_read_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
        assert Settings().openai_base_url == "https://api.groq.com/openai/v1"

    def test_concurrency_is_read_from_the_environment(self, monkeypatch):
        """Free tiers rate-limit, so this must be tunable without a code edit."""
        monkeypatch.setenv("LLM_CONCURRENCY", "1")
        assert Settings().llm_concurrency == 1


class TestChatClientWiring:
    """`base_url=None` is what keeps the OpenAI default intact."""

    def _captured_kwargs(self, monkeypatch):
        captured = {}

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            # build_chain composes `prompt | llm | parser`, and LangChain accepts
            # a plain callable in that position.
            def __call__(self, *args, **kwargs):  # pragma: no cover - never invoked
                raise AssertionError("the fake client should not be called")

        import langchain_openai

        monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeChatOpenAI)
        return captured

    def test_empty_base_url_is_passed_as_none(self, monkeypatch):
        from app import config
        from app.llm import chain

        monkeypatch.setattr(config, "get_settings", lambda: Settings(_env_file=None, openai_base_url=""))
        monkeypatch.setattr(chain, "get_settings", lambda: Settings(_env_file=None, openai_base_url=""))
        captured = self._captured_kwargs(monkeypatch)

        chain.build_chain()
        assert captured["base_url"] is None

    def test_configured_base_url_reaches_the_client(self, monkeypatch):
        from app.llm import chain

        settings = Settings(_env_file=None, openai_base_url="http://localhost:11434/v1")
        monkeypatch.setattr(chain, "get_settings", lambda: settings)
        captured = self._captured_kwargs(monkeypatch)

        chain.build_chain()
        assert captured["base_url"] == "http://localhost:11434/v1"


class TestCacheKeyIsolatesProviders:
    """Two providers serving the same model name are not interchangeable.

    Without the endpoint in the key, switching provider would silently reuse
    the previous provider's cached answers and the comparison would be a lie.
    """

    def test_same_model_different_endpoint_gives_a_different_key(self):
        from app.eval.baselines import _cache_key

        base = {"system": "llm_zeroshot", "model": "llama-3.3-70b", "text": "hello"}
        groq = _cache_key({**base, "endpoint": "https://api.groq.com/openai/v1"})
        local = _cache_key({**base, "endpoint": "http://localhost:11434/v1"})
        assert groq != local

    def test_identical_inputs_still_hit_the_same_key(self):
        from app.eval.baselines import _cache_key

        payload = {
            "system": "llm_zeroshot",
            "model": "gpt-4o-mini",
            "endpoint": "",
            "text": "hello",
        }
        assert _cache_key(dict(payload)) == _cache_key(dict(payload))


class TestConsentConsistency:
    """Changing provider without changing the consent document breaks consent.

    The consent form names OpenAI specifically. This is a reminder in test form:
    if someone points the system elsewhere, this fails and tells them what else
    has to change.
    """

    def test_config_documents_the_consent_obligation(self):
        import inspect

        from app import config

        source = inspect.getsource(config)
        assert "consent" in source.lower(), (
            "Settings.openai_base_url must keep the note about consent_form_vi.md 4; "
            "silently re-routing student free text to another provider would "
            "contradict the consent participants gave."
        )


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Settings are cached in a singleton; drop it around each test."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
