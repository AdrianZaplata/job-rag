"""LangChain tool wrappers around the existing job-rag services.

These reuse the same async implementations the MCP server uses, so
behavior is consistent across the agent, MCP, and HTTP entry points.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from job_rag.mcp_server import tools as job_tools


def _dump(payload: Any) -> str:
    return json.dumps(payload, default=str, ensure_ascii=False)


@tool
async def search_jobs(
    query: str,
    remote_only: bool = False,
    seniority: str | None = None,
    limit: int = 5,
) -> str:
    """Semantic search over the AI Engineer job posting corpus.

    Use this to find postings matching a topic, skill, or constraint
    (e.g. "roles using LangGraph", "remote senior positions").
    Returns a JSON list of postings with id, company, title, skills, and
    rerank score. Always pass the posting `id` to other tools.
    """
    result = await job_tools.search_postings(
        query=query, remote_only=remote_only, seniority=seniority, limit=limit
    )
    return _dump(result)


@tool
async def match_profile(posting_id: str) -> str:
    """Score how well the user's profile matches a specific posting.

    Pass a posting `id` from `search_jobs`. Returns a JSON match report
    with the score, matched and missed skills, and bonus signals.
    """
    return _dump(await job_tools.match_skills(posting_id))


@tool
async def analyze_gaps(
    seniority: str | None = None,
    remote: str | None = None,
) -> str:
    """Aggregate the user's missing skills across all (or filtered) postings.

    Returns the top must-have and nice-to-have gaps ranked by frequency.
    Use this to recommend which skills to learn for maximum coverage.
    """
    return _dump(await job_tools.skill_gaps(seniority=seniority, remote=remote))


AGENT_TOOLS = [search_jobs, match_profile, analyze_gaps]
