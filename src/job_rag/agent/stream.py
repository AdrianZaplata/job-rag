"""Streaming helpers for the LangGraph agent.

Yields structured events the API layer can forward as Server-Sent Events:

    {"type": "token", "content": "..."}            # incremental LLM output
    {"type": "tool_start", "name": "...", "args": {...}}
    {"type": "tool_end", "name": "...", "output": "..."}
    {"type": "final", "content": "..."}            # complete answer
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage

from job_rag.agent.graph import build_agent
from job_rag.observability import get_langchain_callbacks


async def stream_agent(query: str) -> AsyncIterator[dict[str, Any]]:
    """Stream agent execution as a sequence of structured events."""
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
                yield {"type": "token", "content": content}

        elif kind == "on_tool_start":
            yield {
                "type": "tool_start",
                "name": event.get("name"),
                "args": data.get("input"),
            }

        elif kind == "on_tool_end":
            output = data.get("output")
            output_str = (
                getattr(output, "content", str(output)) if output is not None else ""
            )
            yield {
                "type": "tool_end",
                "name": event.get("name"),
                "output": output_str,
            }

    yield {"type": "final", "content": "".join(final_text_parts)}
