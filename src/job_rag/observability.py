"""Langfuse observability — optional, no-op when keys aren't configured.

Usage:
    from job_rag.observability import get_openai_client, get_langchain_callbacks

    client = get_openai_client()                # langfuse-wrapped if enabled
    callbacks = get_langchain_callbacks()       # [LangfuseHandler] or []

The wrappers are imported lazily so the rest of the codebase doesn't pay
the import cost when observability is disabled.
"""
from __future__ import annotations

import hashlib
import os
import uuid as _uuid
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


@lru_cache(maxsize=1)
def get_langfuse_client() -> Any | None:
    """Return a raw Langfuse client for manual span/trace creation (Phase 7 D-32).

    Fail-open: returns ``None`` when keys are missing — all callers MUST
    guard with ``if lf:`` before usage (mirrors :func:`get_langchain_callbacks`
    fail-open semantics). Cached so the same client is reused across the
    resume upload + PATCH save paths within a process.
    """
    if not is_enabled():
        return None
    _ensure_env()
    from langfuse import Langfuse  # type: ignore[import-untyped]

    log.info("langfuse_client_initialized")
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def derive_langfuse_trace_id(seed: _uuid.UUID | str) -> str:
    """Derive a deterministic 32-char hex Langfuse trace_id from an extraction_id.

    Phase 7 G-07-UAT-01: Langfuse 4.x replaces the v3 trace-by-id
    correlation API with a ``create_trace_id(seed=...)`` helper that hashes
    the seed into a 16-byte OTel-compatible trace_id. Both ``POST
    /profile/upload`` and ``PATCH /profile`` derive the same trace_id from
    the same ``extraction_id`` so spans land on the same trace.

    Fail-open: returns the (deterministic) ID even when Langfuse is disabled —
    callers should check ``get_langfuse_client()`` before consuming the ID
    for actual tracing. This avoids a None-check at every call site. When
    the client is absent we replicate the BLAKE2b(seed, 16)[:16].hex()
    derivation Langfuse uses internally so tests that patch out the client
    still get a stable, deterministic ID.
    """
    lf = get_langfuse_client()
    seed_str = str(seed)
    if lf is None:
        return hashlib.blake2b(seed_str.encode("utf-8"), digest_size=16).hexdigest()
    return lf.create_trace_id(seed=seed_str)


def redact_current_generation_input(client: Any, *, char_count: int) -> None:
    """Overwrite resume PII on the auto-captured GENERATION + trace input (D-33).

    The ``langfuse.openai`` wrapper auto-captures the LLM call as a child
    GENERATION observation AND writes the raw input to the trace root.
    This helper performs BOTH redactions in v4-compatible style:

    1. ``client.update_current_generation(input=REDACTED)`` — overrides the
       CHILD generation's input field.
    2. ``client.set_current_trace_io(input=REDACTED)`` — overrides the
       TRACE-LEVEL input (which is what showed PII in the
       ``trace-c744bb2d...json`` export captured during live UAT).

    Both calls are wrapped in ``try/except Exception: pass`` per T-07-08
    fail-open semantics. If step 1 raises, step 2 is still attempted —
    defense in depth for PII redaction.
    """
    redacted = {"text": f"[REDACTED — char_count={char_count}]"}
    try:
        client.update_current_generation(input=redacted)
    except Exception:  # pragma: no cover - fail-open per T-07-08
        log.warning("langfuse_redact_generation_failed", char_count=char_count)
    try:
        client.set_current_trace_io(input=redacted)
    except Exception:  # pragma: no cover - fail-open per T-07-08
        log.warning("langfuse_redact_trace_failed", char_count=char_count)
