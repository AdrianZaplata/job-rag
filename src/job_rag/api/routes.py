"""FastAPI route handlers for the Job RAG API.

Phase 1 Plan 06 wires the typed SSE route handler with:
- 60s ``asyncio.timeout`` wrap around ``stream_agent`` (D-25 / BACK-06)
- typed heartbeat via sse-starlette ``ping_message_factory`` (D-15 / BACK-05)
- cooperative shutdown drain via ``app.state.shutdown_event`` + ``active_streams`` (D-17)
- sanitized error events (no stack traces, ≤200 chars, no newlines) (D-19 / T-06-01)
- ``X-Accel-Buffering: no`` + ``Content-Encoding: identity`` defensive headers (D-18)
- OpenAPI ``responses=`` exposes the ``AgentEvent`` union via inline JSON schema (BACK-02)

``/match``, ``/gaps``, and ``/ingest`` receive ``user_id`` via ``Depends(get_current_user_id)``
and pass it to ``load_profile(user_id=...)`` (BACK-08 / D-10). ``/ingest`` calls
``ingest_from_source`` directly (D-24) — the previous sync ``ingest_file`` path
would have raised ``RuntimeError`` because ``asyncio.run`` cannot run inside an
already-running event loop.
"""

import asyncio
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.event import ServerSentEvent
from sse_starlette.sse import EventSourceResponse

from job_rag.agent.graph import run_agent
from job_rag.agent.stream import stream_agent
from job_rag.api.auth import (
    agent_limit,
    get_current_user_id,
    ingest_limit,
    require_api_key,
    standard_limit,
)
from job_rag.api.deps import get_session
from job_rag.api.sse import (
    AgentEvent,
    ErrorEvent,
    HeartbeatEvent,
    to_sse,
)
from job_rag.config import settings
from job_rag.db.models import JobPostingDB
from job_rag.services.ingestion import (
    MarkdownFileSource,
    ingest_from_source,
)
from job_rag.services.matching import aggregate_gaps, load_profile, match_posting
from job_rag.services.retrieval import rag_query, search_postings

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]


# ----------------------------------------------------------------------
# SSE helpers — module-level so the route handler stays focused.
# ----------------------------------------------------------------------


def _heartbeat_factory() -> ServerSentEvent:
    """Custom ping factory: emits a typed ``event: heartbeat`` with ISO-8601 ts.

    Sse-starlette would otherwise emit a comment-only ``: ping`` keep-alive
    that EventSource clients silently consume. Plan 06 (D-15) wants the
    heartbeat to be a real, observable event in the discriminated AgentEvent
    union so the frontend (Phase 6) can choose to render it as a liveness
    indicator.
    """
    ev = HeartbeatEvent(type="heartbeat", ts=datetime.now(UTC).isoformat())
    return ServerSentEvent(event="heartbeat", data=ev.model_dump_json())


def _sanitize(exc: BaseException) -> str:
    """Bound + newline-strip exception text for SSE error event payloads.

    D-19 / T-06-01: never include exception class names, stack traces, or
    module paths in the wire-format error message. The 200-char bound prevents
    accidental information leak from large exception messages and keeps the
    frame within an EventSource line buffer. Always returns a non-empty
    string (falls back to ``"internal error"`` if the exception's repr is
    empty after stripping).
    """
    return str(exc).strip().replace("\n", " ").replace("\r", " ")[:200] or "internal error"


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/health")
async def health(session: Session) -> dict[str, str]:
    """Check API and database connectivity."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/search", dependencies=[Depends(require_api_key), Depends(standard_limit)])
async def search(
    session: Session,
    q: str,
    seniority: str | None = None,
    remote: str | None = None,
    min_salary: int | None = None,
    generate: bool = True,
) -> dict[str, Any]:
    """Semantic search over job postings with optional RAG generation.

    When generate=True (default), returns an LLM-generated answer with sources.
    When generate=False, returns just the ranked search results.
    """
    if generate:
        result = await rag_query(
            session,
            q,
            seniority=seniority,
            remote=remote,
            min_salary=min_salary,
        )
        return result

    results = await search_postings(
        session,
        q,
        seniority=seniority,
        remote=remote,
        min_salary=min_salary,
    )
    return {
        "results": [
            {
                "id": str(r["posting"].id),
                "title": r["posting"].title,
                "company": r["posting"].company,
                "location": r["posting"].location,
                "remote_policy": r["posting"].remote_policy,
                "seniority": r["posting"].seniority,
                "similarity": round(r["similarity"], 4),
            }
            for r in results
        ]
    }


@router.get(
    "/match/{posting_id}",
    dependencies=[Depends(require_api_key), Depends(standard_limit)],
)
async def match(
    session: Session,
    posting_id: str,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
) -> dict[str, Any]:
    """Match a specific posting against the user profile."""
    stmt = (
        select(JobPostingDB)
        .filter(JobPostingDB.id == posting_id)
        .options(selectinload(JobPostingDB.requirements))
    )
    result = await session.execute(stmt)
    posting = result.scalar_one_or_none()

    if not posting:
        raise HTTPException(status_code=404, detail="Posting not found")

    profile = load_profile(user_id=user_id)
    return match_posting(profile, posting)


@router.get("/gaps", dependencies=[Depends(require_api_key), Depends(standard_limit)])
async def gaps(
    session: Session,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    seniority: str | None = None,
    remote: str | None = None,
) -> dict[str, Any]:
    """Aggregate skill gaps across all (or filtered) postings."""
    stmt = select(JobPostingDB).options(selectinload(JobPostingDB.requirements))
    if seniority:
        stmt = stmt.filter(JobPostingDB.seniority == seniority)
    if remote:
        stmt = stmt.filter(JobPostingDB.remote_policy == remote)

    result = await session.execute(stmt)
    postings = list(result.scalars().all())

    if not postings:
        raise HTTPException(status_code=404, detail="No postings found with given filters")

    profile = load_profile(user_id=user_id)
    return aggregate_gaps(profile, postings)


class AgentQuery(BaseModel):
    query: str


@router.post("/agent", dependencies=[Depends(require_api_key), Depends(agent_limit)])
async def agent_query(payload: AgentQuery) -> dict[str, Any]:
    """Run the LangGraph agent to completion on a single query."""
    return await run_agent(payload.query)


# Inline OpenAPI JSON schema for AgentEvent so /docs exposes the union and
# openapi-typescript (Phase 6) can codegen a frontend discriminated union.
# Computed at import time so the schema is embedded in the route's OpenAPI
# operation object — falls back to an empty dict if Pydantic refuses to
# materialize the schema (no in-tree path produces this fallback today; the
# fallback exists as a defensive guard so route registration never raises).
try:
    _AGENT_EVENT_JSON_SCHEMA: dict[str, Any] = TypeAdapter(AgentEvent).json_schema(  # type: ignore[arg-type]
        ref_template="#/components/schemas/{model}",
    )
except Exception:  # pragma: no cover - defensive fallback
    _AGENT_EVENT_JSON_SCHEMA = {}


@router.get(
    "/agent/stream",
    dependencies=[Depends(require_api_key), Depends(agent_limit)],
    responses={
        # OpenAPI exposure of the AgentEvent union — consumed by openapi-typescript
        # in Phase 6 so the frontend gets a discriminated-union type for free.
        200: {
            "content": {
                "text/event-stream": {
                    "schema": _AGENT_EVENT_JSON_SCHEMA,
                }
            },
            "description": (
                "Stream of AgentEvent variants (token, tool_start, tool_end, "
                "heartbeat, error, final)"
            ),
        }
    },
)
async def agent_stream(request: Request, q: str) -> EventSourceResponse:
    """Stream agent execution as SSE: typed events + heartbeat + 60s timeout + drain.

    The handler wraps the Plan 04 ``stream_agent`` async iterator in
    ``asyncio.timeout(settings.agent_timeout_seconds)`` (D-25) so a runaway
    LangGraph reasoning loop cannot block forever. Three exception branches
    each emit a typed ``ErrorEvent`` (D-19) before closing:

    - ``TimeoutError`` → ``reason="agent_timeout"``
    - ``CancelledError`` → ``reason="shutdown"`` (then re-raises so sse-starlette
      can complete the cancellation handshake)
    - any other ``Exception`` → ``reason="internal"`` with sanitized message

    The current task is registered in ``app.state.active_streams`` on entry
    and discarded in ``finally`` — Plan 05's lifespan shutdown drains this set
    via ``asyncio.gather(*active_streams)`` with a 30s grace period (D-17).

    sse-starlette's ``ping_message_factory`` is overridden so the keep-alive
    is a real ``event: heartbeat`` rather than a comment-only ``:ping`` (D-15).
    Defensive headers (``X-Accel-Buffering: no`` + ``Content-Encoding: identity``)
    prevent reverse-proxy/CDN buffering and accidental compression that would
    break EventSource parsing (D-18 / Pitfall 6).
    """
    app = request.app

    async def typed_event_generator():
        # stream_agent yields AgentEvent instances (Plan 04); to_sse converts to
        # the {"event": ..., "data": ...} dict sse-starlette consumes.
        current_task = asyncio.current_task()
        if current_task is not None:
            app.state.active_streams.add(current_task)
        try:
            try:
                async with asyncio.timeout(settings.agent_timeout_seconds):
                    async for event in stream_agent(q):
                        yield to_sse(event)
            except TimeoutError:
                # Python 3.11+: asyncio.TimeoutError aliased to builtin TimeoutError
                # (ruff UP041). D-16: emit a typed agent_timeout error frame.
                yield to_sse(
                    ErrorEvent(
                        type="error",
                        reason="agent_timeout",
                        message=(
                            f"Agent exceeded {settings.agent_timeout_seconds}s timeout"
                        ),
                    )
                )
            except asyncio.CancelledError:
                # D-17: lifespan shutdown sets app.state.shutdown_event;
                # sse-starlette propagates as CancelledError after the grace
                # period. Emit a sanitized shutdown error then re-raise so
                # the cancellation handshake completes cleanly.
                yield to_sse(
                    ErrorEvent(
                        type="error",
                        reason="shutdown",
                        message="Server is shutting down — please retry shortly",
                    )
                )
                raise
            except Exception as e:
                # D-19 / T-06-01: never leak stack traces. _sanitize bounds the
                # message to 200 chars and strips newlines/CRs.
                yield to_sse(
                    ErrorEvent(
                        type="error",
                        reason="internal",
                        message=_sanitize(e),
                    )
                )
        finally:
            if current_task is not None:
                app.state.active_streams.discard(current_task)

    return EventSourceResponse(
        typed_event_generator(),
        ping=settings.heartbeat_interval_seconds,
        ping_message_factory=_heartbeat_factory,
        # D-17: cooperative drain — sse-starlette watches this anyio.Event
        # and stops new pings once it fires; the 30s grace lets in-flight
        # generators finish their current frame.
        shutdown_event=app.state.shutdown_event,
        shutdown_grace_period=30.0,
        # D-18: defense-in-depth headers. sse-starlette sets some of these by
        # default; declaring them at the response level guarantees they reach
        # the client even if a future middleware tries to override.
        headers={
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )


@router.post("/ingest", dependencies=[Depends(require_api_key), Depends(ingest_limit)])
async def ingest(
    file: UploadFile,
    session: Session,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
) -> dict[str, Any]:
    """Ingest a single job posting markdown file via the async pipeline.

    Pre-Plan-06, this route called ``ingest_file(SessionLocal(), tmp_path)`` —
    Plan 03's rewrap of ``ingest_file`` uses ``asyncio.run`` internally, which
    raises ``RuntimeError`` when called from an already-running event loop
    (i.e. inside any ``async def`` route). Plan 06 closes the latent crash by
    calling the async ``ingest_from_source`` directly with the request's
    AsyncSession dependency (D-24).

    Error strings in ``error_details`` are sanitized via ``_sanitize`` (T-06-06)
    so per-source extraction failures cannot leak stack traces to the API
    boundary — same helper used by the ``/agent/stream`` error event path.

    The ``user_id`` dep is wired so future plans (Phase 7 PROF-01 onward) can
    scope ingestion writes to a user without a signature change. Today the
    value is the single seeded user; the dep itself is the multi-tenancy hook.
    """
    # Note: user_id is reserved for Phase 7 — accepted via Depends so the
    # multi-tenancy wiring is in place without a signature change later.
    _ = user_id

    MAX_UPLOAD_BYTES = 1_000_000  # 1 MB
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 1 MB)")

    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td) / (file.filename or "posting.md")
        with tmp_path.open("wb") as dst:
            dst.write(content)
        result = await ingest_from_source(session, MarkdownFileSource(tmp_path))

    return {
        "total": result.total,
        "ingested": result.ingested,
        "skipped": result.skipped,
        "errors": result.errors,
        "total_cost_usd": result.total_cost_usd,
        "posting_ids": result.posting_ids,
        "error_details": [
            # T-06-06: sanitize per-source error strings at the API boundary
            # (same helper used by /agent/stream's internal error branch).
            {"source_url": u, "error": _sanitize(Exception(e))}
            for u, e in result.error_details
        ],
    }

