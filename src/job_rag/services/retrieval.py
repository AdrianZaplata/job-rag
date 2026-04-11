from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sentence_transformers import CrossEncoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_rag.config import settings
from job_rag.db.models import JobChunkDB, JobPostingDB
from job_rag.logging import get_logger
from job_rag.observability import get_langchain_callbacks, get_openai_client

log = get_logger(__name__)

_reranker: CrossEncoder | None = None

RAG_SYSTEM_PROMPT = """\
You are a job search assistant for AI Engineer roles. Given relevant job posting \
excerpts and a user question, provide a helpful, concise answer. Reference specific \
companies and roles when relevant. If the retrieved context doesn't contain enough \
information to answer, say so honestly."""


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(settings.reranker_model)
    return _reranker


def _embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    client = get_openai_client()
    response = client.embeddings.create(model=settings.embedding_model, input=[query])
    return response.data[0].embedding


async def search_postings(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 20,
    seniority: str | None = None,
    remote: str | None = None,
    min_salary: int | None = None,
) -> list[dict[str, Any]]:
    """Semantic search over postings using pgvector cosine distance.

    Returns top_k postings sorted by similarity.
    """
    query_embedding = _embed_query(query)

    stmt = (
        select(
            JobPostingDB,
            JobPostingDB.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .filter(JobPostingDB.embedding.isnot(None))
        .options(selectinload(JobPostingDB.requirements))
        .order_by("distance")
        .limit(top_k)
    )

    if seniority:
        stmt = stmt.filter(JobPostingDB.seniority == seniority)
    if remote:
        stmt = stmt.filter(JobPostingDB.remote_policy == remote)
    if min_salary is not None:
        stmt = stmt.filter(
            (JobPostingDB.salary_max >= min_salary) | (JobPostingDB.salary_max.is_(None))
        )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "posting": row.JobPostingDB,
            "distance": float(row.distance),
            "similarity": 1 - float(row.distance),
        }
        for row in rows
    ]


async def search_chunks(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """Semantic search over chunks for granular retrieval."""
    query_embedding = _embed_query(query)

    stmt = (
        select(
            JobChunkDB,
            JobChunkDB.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .filter(JobChunkDB.embedding.isnot(None))
        .order_by("distance")
        .limit(top_k)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "chunk": row.JobChunkDB,
            "distance": float(row.distance),
            "similarity": 1 - float(row.distance),
        }
        for row in rows
    ]


def rerank(
    query: str,
    results: list[dict[str, Any]],
    *,
    top_k: int = 5,
    text_key: str = "posting",
) -> list[dict[str, Any]]:
    """Rerank search results using a cross-encoder model.

    Returns top_k results sorted by relevance score.
    """
    if not results:
        return []

    reranker = _get_reranker()

    pairs: list[tuple[str, str]] = []
    for r in results:
        if text_key == "posting":
            posting: JobPostingDB = r["posting"]
            must_have = [req.skill for req in posting.requirements if req.required]
            text = (
                f"{posting.title} at {posting.company}. "
                f"Skills: {', '.join(must_have)}. "
                f"Responsibilities: {posting.responsibilities[:300]}"
            )
        else:
            text = r["chunk"].content
        pairs.append((query, text))

    scores = reranker.predict(pairs)

    for i, r in enumerate(results):
        r["rerank_score"] = float(scores[i])

    results.sort(key=lambda x: x["rerank_score"], reverse=True)
    return results[:top_k]


async def rag_query(
    session: AsyncSession,
    query: str,
    *,
    seniority: str | None = None,
    remote: str | None = None,
    min_salary: int | None = None,
    top_k_retrieve: int = 20,
    top_k_rerank: int = 5,
) -> dict[str, Any]:
    """Full RAG pipeline: search -> rerank -> generate.

    Returns answer text and source postings.
    """
    # 1. Retrieve
    results = await search_postings(
        session,
        query,
        top_k=top_k_retrieve,
        seniority=seniority,
        remote=remote,
        min_salary=min_salary,
    )

    if not results:
        return {"answer": "No matching job postings found.", "sources": []}

    # 2. Rerank
    reranked = rerank(query, results, top_k=top_k_rerank)

    # 3. Build context
    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []
    for r in reranked:
        posting: JobPostingDB = r["posting"]
        must_have = [req.skill for req in posting.requirements if req.required]
        nice_to_have = [req.skill for req in posting.requirements if not req.required]

        context_parts.append(
            f"**{posting.title}** at **{posting.company}** "
            f"({posting.location}, {posting.remote_policy})\n"
            f"Seniority: {posting.seniority}\n"
            f"Must-have: {', '.join(must_have)}\n"
            f"Nice-to-have: {', '.join(nice_to_have)}\n"
            f"Responsibilities: {posting.responsibilities}\n"
        )
        sources.append({
            "id": str(posting.id),
            "title": posting.title,
            "company": posting.company,
            "similarity": r["similarity"],
            "rerank_score": r["rerank_score"],
        })

    context = "\n---\n".join(context_parts)

    # 4. Generate answer with LangChain
    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_SYSTEM_PROMPT),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ])

    llm = ChatOpenAI(
        model=settings.rag_model,
        api_key=settings.openai_api_key,  # type: ignore[arg-type]
        temperature=0.3,
    )

    chain = prompt | llm | StrOutputParser()
    callbacks = get_langchain_callbacks()
    answer = await chain.ainvoke(
        {"context": context, "question": query},
        config={"callbacks": callbacks} if callbacks else None,
    )

    log.info(
        "rag_query_complete",
        query=query,
        retrieved=len(results),
        reranked=len(reranked),
    )

    return {"answer": answer, "sources": sources}
