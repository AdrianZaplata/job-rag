"""Tool implementations for the job-rag MCP server.

These are plain async functions wrapping existing services so they can be
unit-tested directly without going through FastMCP's tool dispatcher.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from job_rag.config import settings
from job_rag.db.engine import AsyncSessionLocal, SessionLocal
from job_rag.db.models import JobPostingDB
from job_rag.logging import get_logger
from job_rag.services.matching import aggregate_gaps, load_profile, match_posting
from job_rag.services.retrieval import rerank
from job_rag.services.retrieval import search_postings as _search_postings

log = get_logger(__name__)


def _serialize_posting(posting: JobPostingDB) -> dict[str, Any]:
    """Convert a JobPostingDB row into a JSON-serializable summary.

    Phase 2: location is now a nested object {country/city/region}; each
    requirement carries skill_type AND skill_category (D-02, D-03).
    """
    must_have = [
        {"skill": r.skill, "skill_type": r.skill_type, "skill_category": r.skill_category}
        for r in posting.requirements if r.required
    ]
    nice_to_have = [
        {"skill": r.skill, "skill_type": r.skill_type, "skill_category": r.skill_category}
        for r in posting.requirements if not r.required
    ]
    return {
        "id": str(posting.id),
        "title": posting.title,
        "company": posting.company,
        "location": {
            "country": posting.location_country,
            "city": posting.location_city,
            "region": posting.location_region,
        },
        "remote_policy": posting.remote_policy,
        "seniority": posting.seniority,
        "salary_min": posting.salary_min,
        "salary_max": posting.salary_max,
        "salary_raw": posting.salary_raw,
        "must_have": must_have,
        "nice_to_have": nice_to_have,
        "source_url": posting.source_url,
    }


async def search_postings(
    query: str,
    remote_only: bool = False,
    seniority: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Semantic search over job postings with optional filters.

    Returns ranked posting summaries — no LLM generation, since the MCP
    client (Claude) can synthesize answers from the structured results.
    """
    async with AsyncSessionLocal() as session:
        results = await _search_postings(
            session,
            query,
            top_k=max(limit * 4, 20),
            seniority=seniority,
            remote="remote" if remote_only else None,
        )

        if not results:
            return {"query": query, "count": 0, "results": []}

        # Rerank — push CPU-bound forward pass off the event loop [D-28,
        # BACK-04, T-05-03] so other MCP tool calls in flight (and
        # asyncio.to_thread-based ingestion below) keep ticking.
        reranked = await asyncio.to_thread(rerank, query, results, top_k=limit)

        return {
            "query": query,
            "count": len(reranked),
            "results": [
                {
                    **_serialize_posting(r["posting"]),
                    "similarity": round(r["similarity"], 4),
                    "rerank_score": round(r["rerank_score"], 4),
                }
                for r in reranked
            ],
        }


async def match_skills(posting_id: str) -> dict[str, Any]:
    """Match a specific job posting against the user profile."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(JobPostingDB)
            .filter(JobPostingDB.id == posting_id)
            .options(selectinload(JobPostingDB.requirements))
        )
        result = await session.execute(stmt)
        posting = result.scalar_one_or_none()

        if not posting:
            return {"error": "posting_not_found", "posting_id": posting_id}

        # MCP tools run outside the HTTP request cycle so there is no Entra
        # JWT to read — pass settings.seeded_user_id explicitly per D-08
        # so the v1 single-user assumption is surfaced at the call site
        # rather than relying on the load_profile fallback.
        profile = load_profile(user_id=settings.seeded_user_id)
        return match_posting(profile, posting)


async def skill_gaps(
    seniority: str | None = None,
    remote: str | None = None,
) -> dict[str, Any]:
    """Aggregate skill gaps across all (or filtered) postings."""
    async with AsyncSessionLocal() as session:
        stmt = select(JobPostingDB).options(selectinload(JobPostingDB.requirements))
        if seniority:
            stmt = stmt.filter(JobPostingDB.seniority == seniority)
        if remote:
            stmt = stmt.filter(JobPostingDB.remote_policy == remote)

        result = await session.execute(stmt)
        postings = list(result.scalars().all())

        if not postings:
            return {
                "error": "no_postings_found",
                "filters": {"seniority": seniority, "remote": remote},
            }

        # See match_skills above — MCP tools pass user_id explicitly per D-08.
        profile = load_profile(user_id=settings.seeded_user_id)
        return aggregate_gaps(profile, postings)


def _allowed_path(path: Path) -> bool:
    """Check that a path resolves inside the configured data directory."""
    allowed = Path(settings.data_dir).resolve()
    return path.resolve().is_relative_to(allowed)


def _ingest_path_sync(path: Path) -> dict[str, Any]:
    """Sync helper that runs the existing ingestion + embedding pipeline."""
    from job_rag.services.embedding import embed_and_store_posting
    from job_rag.services.ingestion import ingest_file

    session = SessionLocal()
    try:
        was_ingested, reason, posting_id = ingest_file(session, path)
        if not was_ingested:
            return {"ingested": False, "reason": reason}

        # Embed the specific posting by ID to avoid race conditions
        embedded = False
        if posting_id:
            posting = (
                session.query(JobPostingDB)
                .filter(JobPostingDB.id == posting_id)
                .first()
            )
            if posting:
                embed_and_store_posting(session, posting)
                session.commit()
                embedded = True

        return {
            "ingested": True,
            "embedded": embedded,
            "reason": reason,
        }
    finally:
        session.close()


async def ingest_posting(
    file_path: str | None = None,
    content: str | None = None,
) -> dict[str, Any]:
    """Ingest a single job posting markdown file.

    Pass either a `file_path` to a markdown file on disk, or `content` with
    the raw markdown text. The latter is useful when the MCP client doesn't
    share a filesystem with the server.
    """
    if not file_path and not content:
        return {"error": "must_provide_file_path_or_content"}

    if file_path:
        path = Path(file_path)
        if not path.exists():
            return {"error": "file_not_found"}
        if not _allowed_path(path):
            return {"error": "path_not_allowed"}
        return await asyncio.to_thread(_ingest_path_sync, path)

    if content is None:
        return {"error": "content_required_when_file_path_not_provided"}
    MAX_CONTENT_BYTES = 1_000_000  # 1 MB
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        return {"error": "content_too_large", "max_bytes": MAX_CONTENT_BYTES}
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        return await asyncio.to_thread(_ingest_path_sync, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
