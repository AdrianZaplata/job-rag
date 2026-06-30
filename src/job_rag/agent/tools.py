"""LangChain tool wrappers around the existing job-rag services.

These reuse the same async implementations the MCP server uses, so
behavior is consistent across the agent, MCP, and HTTP entry points.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from job_rag.mcp_server import tools as job_tools
from job_rag.models import Seniority


def _dump(payload: Any) -> str:
    return json.dumps(payload, default=str, ensure_ascii=False)


@tool
async def search_jobs(
    query: str,
    remote_only: bool = False,
    seniority: Seniority | None = None,
    location: str | None = None,
    limit: int = 5,
) -> str:
    """Semantic search over the AI Engineer job posting corpus.

    Use this to find postings matching a topic, skill, or constraint
    (e.g. "roles using LangGraph", "remote senior positions"). Pass
    `remote_only=True` for fully-remote roles, `seniority` (one of junior,
    mid, senior, staff, lead, unknown) to filter by level, and `location`
    (a city or country like "Berlin" or "DE") to scope by place. Omit any
    filter you don't need — do NOT pass empty strings or "null".
    Returns a JSON list of postings with id, company, title, skills, and
    rerank score. Always pass the posting `id` to other tools.
    """
    result = await job_tools.search_postings(
        query=query,
        remote_only=remote_only,
        seniority=seniority,
        location=location,
        limit=limit,
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
    seniority: Seniority | None = None,
    remote_only: bool = False,
    location: str | None = None,
) -> str:
    """Aggregate the user's missing skills across all (or filtered) postings.

    Ranks the top must-have and nice-to-have skill gaps by how often they
    appear in the corpus — use it for "what should I learn?" and
    "what's the top skill in <city>?" questions.

    Pass `seniority` (one of junior, mid, senior, staff, lead, unknown) to
    scope by level, `remote_only=True` to count only fully-remote roles, and
    `location` (a city or country like "Berlin" or "DE") to scope by place.
    Omit any filter you don't need — do NOT pass empty strings or "null".
    With no arguments it aggregates over the entire corpus.

    Returns JSON with `total_postings_analyzed` and the ranked gap lists.
    """
    return _dump(
        await job_tools.skill_gaps(
            seniority=seniority, remote_only=remote_only, location=location
        )
    )


AGENT_TOOLS = [search_jobs, match_profile, analyze_gaps]
