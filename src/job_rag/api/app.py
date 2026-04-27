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
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_rag.api.routes import router
from job_rag.config import settings
from job_rag.db.engine import async_engine
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

    # 2. Create app-wide shutdown event for SSE handlers to observe [D-17]
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
