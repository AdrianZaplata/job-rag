"""FastMCP server exposing job-rag tools over stdio.

Run with `job-rag mcp` (or `python -m job_rag.mcp_server.server`). Wire it
into Claude Code by adding an entry like:

    {
      "mcpServers": {
        "job-rag": {
          "command": "uv",
          "args": ["run", "--directory", "/abs/path/to/job-rag", "job-rag", "mcp"]
        }
      }
    }
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from job_rag.mcp_server import tools

mcp = FastMCP("job-rag")


@mcp.tool()
async def search_postings(
    query: str,
    remote_only: bool = False,
    seniority: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Semantic search over the AI Engineer job posting corpus.

    Args:
        query: Natural-language search query (e.g. "roles using LangGraph").
        remote_only: If true, restrict to fully remote postings.
        seniority: Optional filter — junior, mid, senior, staff, lead.
        limit: Max postings to return after reranking (default 5).
    """
    return await tools.search_postings(
        query=query,
        remote_only=remote_only,
        seniority=seniority,
        limit=limit,
    )


@mcp.tool()
async def match_skills(posting_id: str) -> dict[str, Any]:
    """Score how well the user's profile matches a specific posting.

    Args:
        posting_id: UUID of the posting (from `search_postings` results).

    Returns the match score, matched/missed must-have and nice-to-have
    skills, and bonus signals (remote/salary fit).
    """
    return await tools.match_skills(posting_id)


@mcp.tool()
async def skill_gaps(
    seniority: str | None = None,
    remote: str | None = None,
) -> dict[str, Any]:
    """Aggregate the user's missing skills across all (or filtered) postings.

    Args:
        seniority: Optional filter — junior, mid, senior, staff, lead.
        remote: Optional filter — remote, hybrid, onsite.

    Returns top must-have and nice-to-have gaps ranked by frequency.
    """
    return await tools.skill_gaps(seniority=seniority, remote=remote)


@mcp.tool()
async def ingest_posting(
    file_path: str | None = None,
    content: str | None = None,
) -> dict[str, Any]:
    """Ingest a new job posting and generate its embeddings.

    Args:
        file_path: Absolute path to a markdown file on the server's filesystem.
        content: Raw markdown text (alternative to file_path).

    Exactly one of `file_path` or `content` should be provided.
    """
    return await tools.ingest_posting(file_path=file_path, content=content)


def run() -> None:
    """Start the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    run()
