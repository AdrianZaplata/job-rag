"""FastAPI app factory.

Wires the application lifespan (Plan 05 / D-17, D-26, D-27):
- startup preloads the cross-encoder reranker (eliminates 2-3s cold start on
  the first /agent/stream request — BACK-03)
- startup creates ``app.state.shutdown_event`` (anyio.Event) and
  ``app.state.active_streams`` (set) so Plan 06's route handler can register
  in-flight stream tasks for cooperative drain on SIGTERM
- shutdown signals the event, gathers active streams with a 30s budget, then
  disposes the async DB engine

Adds CORS middleware with an env-var-driven origin allow-list — NEVER ``*``
(D-26 / T-05-01). No GZipMiddleware is registered anywhere — sse-starlette
raises NotImplementedError on compression and EventSource clients receive
buffered garbage instead of a stream (Pitfall 6 / D-18).

Customizes ``app.openapi()`` so the inline ``AgentEvent`` ``$defs`` from the
``/agent/stream`` route's ``responses=`` schema are promoted into the global
``components.schemas`` (BACK-02). FastAPI does not walk inline content
schemas by default, so without this hop ``openapi-typescript`` would have to
chase ``$defs`` per-route. Promotion gives Phase 6 a single canonical
location for the discriminated union types.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy import text

from job_rag.api.routes import router
from job_rag.config import settings
from job_rag.db.engine import AsyncSessionLocal, async_engine
from job_rag.extraction.prompt import PROMPT_VERSION
from job_rag.logging import get_logger
from job_rag.services.retrieval import _get_reranker

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App lifespan: preload reranker, init drain primitives, dispose DB."""
    log.info("lifespan_startup_begin")

    # 1. Preload the cross-encoder model (~80MB, blocks ~2-3s) [D-27, BACK-03]
    _get_reranker()
    log.info("reranker_preloaded")

    # 2. Drift check (Phase 2 D-17 / Pattern 4). One-shot SELECT; if any rows
    #    returned, emit a structured warning. Does NOT block startup on
    #    error (best-effort observability).
    try:
        async with AsyncSessionLocal() as session:
            stmt = text(
                "SELECT prompt_version, COUNT(*) AS n "
                "FROM job_postings "
                "WHERE prompt_version != :current "
                "GROUP BY prompt_version"
            )
            result = await session.execute(stmt, {"current": PROMPT_VERSION})
            stale_rows = result.all()
            if stale_rows:
                stale_summary = {
                    row.prompt_version: row.n for row in stale_rows
                }
                stale_count = sum(stale_summary.values())
                log.warning(
                    "prompt_version_drift",
                    stale_count=stale_count,
                    stale_by_version=stale_summary,
                    current=PROMPT_VERSION,
                    remediation="run `job-rag reextract` to re-extract stale rows",
                )
            else:
                log.info("prompt_version_check_clean", current=PROMPT_VERSION)
    except Exception as e:
        # Best-effort: DB might be slow on cold start; do NOT block ASGI from
        # accepting connections.
        log.warning("prompt_version_check_failed", error=str(e))

    # 3. Create app-wide shutdown event for SSE handlers to observe [D-17]
    #    sse-starlette's shutdown_event kwarg expects an anyio.Event (NOT
    #    asyncio.Event) — the library wraps both backends through anyio for
    #    asyncio/trio portability. Plan 06 wires this into EventSourceResponse.
    app.state.shutdown_event = anyio.Event()

    # 3. Track all in-flight SSE handler tasks for cooperative drain [D-17]
    app.state.active_streams = set()

    log.info("lifespan_startup_complete")
    yield

    # --- shutdown [D-17] ---
    log.info(
        "lifespan_shutdown_begin",
        active_streams=len(app.state.active_streams),
    )

    # 1. Signal every in-flight stream to wrap up
    app.state.shutdown_event.set()

    # 2. Wait up to 30s for them to drain (D-17 budget; Phase 3 layers
    #    terminationGracePeriodSeconds=120 as belt-and-suspenders)
    if app.state.active_streams:
        try:
            await asyncio.wait_for(
                asyncio.gather(*app.state.active_streams, return_exceptions=True),
                timeout=30.0,
            )
        except TimeoutError:
            # Python 3.11+: asyncio.TimeoutError is an alias for builtin
            # TimeoutError (ruff UP041 enforces the canonical spelling).
            log.warning(
                "shutdown_drain_timeout",
                remaining=len(app.state.active_streams),
            )

    # 3. Tear down DB engine
    await async_engine.dispose()
    log.info("lifespan_shutdown_complete")


app = FastAPI(
    title="Job RAG API",
    description="RAG system for AI Engineer job postings — search, matching, and gap analysis",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS middleware [D-26, BACK-01, T-05-01]
# allow_origins comes from settings.allowed_origins (env-var driven, NEVER "*").
# allow_credentials=True is incompatible with wildcard origins per CORS spec —
# CORSMiddleware would refuse to combine the two. allow_methods includes
# OPTIONS for browser preflight; allow_headers allows the Bearer token + JSON
# Content-Type the SPA will send.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# CRITICAL: do NOT add GZipMiddleware [D-18, Pitfall 6].
# sse-starlette raises NotImplementedError on compressed transfer-encoding,
# and EventSource clients receive a buffered binary blob instead of streamed
# events. The CI grep guard in tests/ (Plan 01-01) ensures this never regresses.

app.include_router(router)


def _promote_inline_defs(schema: dict[str, Any]) -> dict[str, Any]:
    """Promote inline ``$defs`` from route-level content schemas into ``components.schemas``.

    FastAPI inlines Pydantic JSON schemas for ``responses[X].content[Y].schema``
    rather than referencing ``components.schemas``. The discriminated
    ``AgentEvent`` union on ``/agent/stream`` carries a ``$defs`` dict
    containing the six event models; without this hop, ``openapi-typescript``
    cannot find ``TokenEvent`` / ``ToolStartEvent`` / etc. at the canonical
    ``#/components/schemas/<name>`` location.

    BACK-02 expects at least one of the six event models to appear in
    ``components.schemas``. Promotion is non-destructive (skips names that
    already exist) and idempotent (calling twice produces the same result).
    """
    components = schema.setdefault("components", {})
    components_schemas = components.setdefault("schemas", {})

    paths = schema.get("paths", {})
    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for op in path_item.values():
            if not isinstance(op, dict):
                continue
            responses = op.get("responses", {})
            if not isinstance(responses, dict):
                continue
            for resp in responses.values():
                if not isinstance(resp, dict):
                    continue
                content = resp.get("content", {})
                if not isinstance(content, dict):
                    continue
                for media in content.values():
                    if not isinstance(media, dict):
                        continue
                    media_schema = media.get("schema", {})
                    if not isinstance(media_schema, dict):
                        continue
                    defs = media_schema.pop("$defs", None)
                    if isinstance(defs, dict):
                        for name, definition in defs.items():
                            components_schemas.setdefault(name, definition)
    return schema


def custom_openapi() -> dict[str, Any]:
    """Cached OpenAPI generator that promotes inline ``$defs`` (BACK-02)."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema = _promote_inline_defs(schema)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
