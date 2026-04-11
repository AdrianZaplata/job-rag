from unittest.mock import patch

from job_rag import observability


def _clear_caches() -> None:
    observability.get_openai_client.cache_clear()
    observability._langfuse_handler.cache_clear()


class TestIsEnabled:
    def test_disabled_when_keys_missing(self):
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                assert observability.is_enabled() is False

    def test_enabled_when_both_keys_set(self):
        with patch.object(observability.settings, "langfuse_public_key", "pk-test"):
            with patch.object(observability.settings, "langfuse_secret_key", "sk-test"):
                assert observability.is_enabled() is True

    def test_disabled_when_only_one_key_set(self):
        with patch.object(observability.settings, "langfuse_public_key", "pk-test"):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                assert observability.is_enabled() is False


class TestGetOpenAIClient:
    def test_returns_plain_openai_when_disabled(self):
        _clear_caches()
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                client = observability.get_openai_client()
                # Plain openai client has 'chat' attribute but isn't from langfuse
                assert client.__class__.__module__.startswith("openai")
        _clear_caches()


class TestGetLangchainCallbacks:
    def test_empty_when_disabled(self):
        _clear_caches()
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                assert observability.get_langchain_callbacks() == []
        _clear_caches()


class TestFlush:
    def test_flush_noop_when_disabled(self):
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                # Should not raise
                observability.flush()
