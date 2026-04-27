"""Streaming helpers for the LangGraph agent.

Yields typed Pydantic ``AgentEvent`` instances the API layer can forward as
Server-Sent Events:

    TokenEvent(type="token", content="...")              # incremental LLM output
    ToolStartEvent(type="tool_start", name="...", args={...})
    ToolEndEvent(type="tool_end", name="...", output="...")
    FinalEvent(type="final", content="...")              # complete answer

Wire-shape parity (D-14): ``model_dump_json()`` on each event produces JSON
byte-identical (modulo whitespace) to the dict shape this module yielded prior
to Plan 04. The frontend-to-be (Phase 6) consumes the JSON via
``openapi-typescript``; do NOT change field names without a coordinated
frontend update.

This generator does NOT emit ``HeartbeatEvent`` or ``ErrorEvent`` — those are
the route handler's responsibility per D-15/D-16/D-17 and Plan 06. Heartbeats
come from sse-starlette's ``ping_message_factory``; error events come from the
route handler's ``except`` blocks.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage

from job_rag.agent.graph import build_agent
from job_rag.api.sse import (
    AgentEvent,
    FinalEvent,
    TokenEvent,
    ToolEndEvent,
    ToolStartEvent,
)
from job_rag.observability import get_langchain_callbacks


async def stream_agent(query: str) -> AsyncIterator[AgentEvent]:
    """Stream agent execution as a sequence of typed AgentEvent instances."""
    agent = build_agent()
    callbacks = get_langchain_callbacks()
    config: dict[str, Any] = {"callbacks": callbacks} if callbacks else {}

    final_text_parts: list[str] = []

    async for event in agent.astream_events(
        {"messages": [HumanMessage(content=query)]},
        config=config,
        version="v2",
    ):
        kind = event.get("event")
        data = event.get("data", {})

        if kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            content = getattr(chunk, "content", "") if chunk is not None else ""
            if content:
                final_text_parts.append(content)
                yield TokenEvent(type="token", content=content)

        elif kind == "on_tool_start":
            # LangGraph supplies tool input via data["input"]; coerce non-dict
            # shapes (e.g. positional-only invocations) to None to satisfy the
            # ToolStartEvent.args: dict | None contract.
            raw_args = data.get("input")
            args = raw_args if isinstance(raw_args, dict) else None
            yield ToolStartEvent(
                type="tool_start",
                name=event.get("name") or "",
                args=args,
            )

        elif kind == "on_tool_end":
            output = data.get("output")
            output_str = (
                getattr(output, "content", str(output)) if output is not None else ""
            )
            yield ToolEndEvent(
                type="tool_end",
                name=event.get("name") or "",
                output=output_str,
            )

    yield FinalEvent(type="final", content="".join(final_text_parts))
