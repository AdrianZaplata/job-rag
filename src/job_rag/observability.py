"""Langfuse observability — optional, no-op when keys aren't configured.

Usage:
    from job_rag.observability import get_openai_client, get_langchain_callbacks

    client = get_openai_client()                # langfuse-wrapped if enabled
    callbacks = get_langchain_callbacks()       # [LangfuseHandler] or []

The wrappers are imported lazily so the rest of the codebase doesn't pay
the import cost when observability is disabled.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from job_rag.config import settings
from job_rag.logging import get_logger

log = get_logger(__name__)


def is_enabled() -> bool:
    """Langfuse is on iff both keys are set."""
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def _ensure_env() -> None:
    """Langfuse SDK reads from os.environ — mirror settings into it once."""
    if settings.langfuse_public_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    if settings.langfuse_secret_key:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    if settings.langfuse_host:
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)


@lru_cache(maxsize=1)
def get_openai_client() -> Any:
    """Return an OpenAI client, langfuse-wrapped when observability is enabled.

    Cached so the wrapped client (which sets up OTEL spans) is reused.
    """
    if is_enabled():
        _ensure_env()
        from langfuse.openai import OpenAI as LangfuseOpenAI  # type: ignore[import-untyped]

        log.info("openai_client_wrapped", provider="langfuse")
        return LangfuseOpenAI(api_key=settings.openai_api_key)

    import openai

    return openai.OpenAI(api_key=settings.openai_api_key)


@lru_cache(maxsize=1)
def _langfuse_handler() -> Any | None:
    if not is_enabled():
        return None
    _ensure_env()
    from langfuse.langchain import CallbackHandler  # type: ignore[import-untyped]

    log.info("langfuse_handler_initialized")
    return CallbackHandler()


def get_langchain_callbacks() -> list[Any]:
    """Return LangChain callbacks list — empty when observability is disabled."""
    handler = _langfuse_handler()
    return [handler] if handler is not None else []


def flush() -> None:
    """Flush pending Langfuse events. Call before process exit."""
    if not is_enabled():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as e:  # pragma: no cover - best effort
        log.warning("langfuse_flush_failed", error=str(e))
