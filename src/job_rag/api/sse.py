"""SSE event contract for /agent/stream.

Pydantic v2 discriminated union on the ``type`` field per D-14. Six event types:

- ``token``: assistant text chunk (yielded by stream_agent)
- ``tool_start``: tool invocation begun (tool name + args) (yielded by stream_agent)
- ``tool_end``: tool invocation completed (tool name + output) (yielded by stream_agent)
- ``heartbeat``: 15s liveness ping — emitted by sse-starlette ``ping_message_factory``
  in the route handler (Plan 06), NOT by stream_agent.
- ``error``: timeout / shutdown / llm error / internal — emitted by the route handler's
  except blocks (Plan 06), NOT by stream_agent.
- ``final``: stream-complete marker (yielded by stream_agent)

Wire-shape parity (D-14): the JSON these models emit MUST be byte-identical
(modulo whitespace) to the dict shapes the current ``src/job_rag/agent/stream.py``
yields. The frontend-to-be (Phase 6) consumes this shape via ``openapi-typescript``;
changing it is a breaking contract change that requires a frontend update.

Security notes:

- ``ErrorEvent.message`` is documented as "sanitized — NEVER a stack trace" (T-04-01).
  The sanitization helper itself lives in ``api/routes.py`` (Plan 06); this module
  only establishes the field's contract. Pydantic's ``str`` field has no built-in
  length limit — the consumer (route handler) enforces.
- ``ErrorEvent.reason`` is a closed ``Literal`` set (T-04-02). Pydantic rejects any
  other value at parse time. The frontend branches on ``reason`` for retry-vs-fatal;
  adding a new reason requires a coordinated PR + frontend update.
"""
from datetime import datetime  # noqa: F401  # allowed for future ts use
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TokenEvent(BaseModel):
    """Incremental assistant text chunk.

    Wire shape: ``{"type": "token", "content": "<chunk>"}`` — matches the dict
    yielded by ``agent/stream.py`` line 42.
    """

    type: Literal["token"]
    content: str = Field(description="Assistant text chunk")


class ToolStartEvent(BaseModel):
    """Tool invocation has begun.

    Wire shape: ``{"type": "tool_start", "name": "<tool>", "args": {...}|null}`` —
    matches the dict yielded by ``agent/stream.py`` lines 45-49. ``args`` is
    optional because LangGraph may not always supply tool inputs.
    """

    type: Literal["tool_start"]
    name: str = Field(description="Tool function name")
    args: dict | None = Field(default=None, description="Tool arguments (JSON)")


class ToolEndEvent(BaseModel):
    """Tool invocation has completed.

    Wire shape: ``{"type": "tool_end", "name": "<tool>", "output": "<str>"}`` —
    matches the dict yielded by ``agent/stream.py`` lines 56-60. ``output`` is
    stringified at the source; structured outputs lose fidelity through ``str()``
    (T-04-03 accepted tradeoff).
    """

    type: Literal["tool_end"]
    name: str = Field(description="Tool function name")
    output: str = Field(description="Tool return value (stringified)")


class HeartbeatEvent(BaseModel):
    """15s liveness ping (D-15).

    Wire shape: ``{"type": "heartbeat", "ts": "<ISO-8601>"}`` — emitted by the
    route handler's sse-starlette ``ping_message_factory`` (Plan 06), NOT by
    ``stream_agent``. The frontend may surface this as a liveness indicator or
    silently consume it.
    """

    type: Literal["heartbeat"]
    ts: str = Field(description="ISO-8601 timestamp at emit time")


class ErrorEvent(BaseModel):
    """Typed error event (D-16, D-17, D-19).

    Wire shape: ``{"type": "error", "reason": "<literal>", "message": "<str>"}`` —
    emitted by the route handler's except blocks (Plan 06), NOT by ``stream_agent``.
    The ``reason`` field is a closed ``Literal`` set so frontends can branch
    deterministically on retry-vs-fatal classification.

    ``message`` MUST be a sanitized human-readable string — NEVER a stack trace
    (T-04-01). The route handler runs ``_sanitize(exc)`` before constructing this
    event.
    """

    type: Literal["error"]
    reason: Literal["agent_timeout", "shutdown", "llm_error", "internal"] = Field(
        description="Machine-readable error kind (closed Literal set per D-19)"
    )
    message: str = Field(description="Sanitized human-readable message — NEVER a stack trace")


class FinalEvent(BaseModel):
    """Stream-complete marker.

    Wire shape: ``{"type": "final", "content": "<full-message>"}`` — matches the
    dict yielded by ``agent/stream.py`` line 62. ``content`` is the concatenation
    of all token chunks emitted during the stream.
    """

    type: Literal["final"]
    content: str = Field(description="Synthesized final assistant message")


AgentEvent = Annotated[
    TokenEvent | ToolStartEvent | ToolEndEvent | HeartbeatEvent | ErrorEvent | FinalEvent,
    Field(discriminator="type"),
]
"""Pydantic v2 discriminated union for the /agent/stream wire contract.

The ``type`` field discriminates which model to instantiate. ``TypeAdapter(AgentEvent)``
produces an OpenAPI ``discriminator`` attribute that ``openapi-typescript`` consumes
to generate a discriminated union on the frontend.
"""


def to_sse(event: BaseModel) -> dict[str, str]:
    """Convert a Pydantic event into the sse-starlette ServerSentEvent payload dict.

    Returns a ``{"event": <event.type>, "data": <event.model_dump_json()>}`` dict
    that ``EventSourceResponse`` consumes. The ``event`` field becomes the SSE
    ``event:`` line; the ``data`` field becomes the SSE ``data:`` line.
    """
    return {
        "event": event.type,  # type: ignore[attr-defined]
        "data": event.model_dump_json(),
    }
