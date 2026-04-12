import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from job_rag.agent.graph import run_agent
from job_rag.agent.stream import stream_agent
from job_rag.api.auth import agent_limit, ingest_limit, require_api_key, standard_limit
from job_rag.api.deps import get_session
from job_rag.db.models import JobPostingDB
from job_rag.services.matching import aggregate_gaps, load_profile, match_posting
from job_rag.services.retrieval import rag_query, search_postings

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_session)]


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
async def match(session: Session, posting_id: str) -> dict[str, Any]:
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

    profile = load_profile()
    return match_posting(profile, posting)


@router.get("/gaps", dependencies=[Depends(require_api_key), Depends(standard_limit)])
async def gaps(
    session: Session,
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

    profile = load_profile()
    return aggregate_gaps(profile, postings)


class AgentQuery(BaseModel):
    query: str


@router.post("/agent", dependencies=[Depends(require_api_key), Depends(agent_limit)])
async def agent_query(payload: AgentQuery) -> dict[str, Any]:
    """Run the LangGraph agent to completion on a single query."""
    return await run_agent(payload.query)


@router.get("/agent/stream", dependencies=[Depends(require_api_key), Depends(agent_limit)])
async def agent_stream(q: str) -> EventSourceResponse:
    """Stream the agent's tool calls and tokens via Server-Sent Events.

    Each SSE message has an `event` field (token, tool_start, tool_end,
    final) and a JSON `data` payload.
    """

    async def event_source():
        async for event in stream_agent(q):
            yield {
                "event": event["type"],
                "data": json.dumps(event, default=str, ensure_ascii=False),
            }

    return EventSourceResponse(event_source())


@router.post("/ingest", dependencies=[Depends(require_api_key), Depends(ingest_limit)])
async def ingest(file: UploadFile) -> dict[str, Any]:
    """Ingest a single job posting markdown file.

    Uses sync session for compatibility with existing ingestion pipeline.
    """
    import tempfile
    from pathlib import Path

    from job_rag.db.engine import SessionLocal
    from job_rag.services.embedding import embed_and_store_posting
    from job_rag.services.ingestion import ingest_file

    MAX_UPLOAD_BYTES = 1_000_000  # 1 MB
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 1 MB)")
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".md", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    session = SessionLocal()
    try:
        was_ingested, reason, posting_id = ingest_file(session, tmp_path)
        if not was_ingested:
            return {"ingested": False, "reason": reason}

        # Auto-embed the newly ingested posting by its ID
        if posting_id:
            posting = (
                session.query(JobPostingDB)
                .filter(JobPostingDB.id == posting_id)
                .first()
            )
            if posting:
                embed_and_store_posting(session, posting)
                session.commit()

        return {"ingested": True, "reason": reason}
    finally:
        session.close()
        tmp_path.unlink(missing_ok=True)
