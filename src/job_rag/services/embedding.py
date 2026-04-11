from sqlalchemy.orm import Session

from job_rag.config import settings
from job_rag.db.models import JobChunkDB, JobPostingDB
from job_rag.logging import get_logger
from job_rag.observability import get_openai_client

log = get_logger(__name__)

# Pricing per 1M tokens (USD)
_EMBEDDING_PRICING = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}


def embed_texts(texts: list[str]) -> tuple[list[list[float]], dict]:
    """Embed a batch of texts using OpenAI embeddings API.

    Returns (embeddings, usage_info).
    """
    client = get_openai_client()
    response = client.embeddings.create(model=settings.embedding_model, input=texts)

    embeddings = [item.embedding for item in response.data]
    total_tokens = response.usage.total_tokens
    price_per_m = _EMBEDDING_PRICING.get(settings.embedding_model, 0.02)
    cost = total_tokens * price_per_m / 1_000_000

    usage_info = {
        "model": settings.embedding_model,
        "total_tokens": total_tokens,
        "cost_usd": cost,
    }
    return embeddings, usage_info


def format_posting_for_embedding(posting: JobPostingDB) -> str:
    """Format a posting into a single text block for embedding."""
    must_have = [r.skill for r in posting.requirements if r.required]
    nice_to_have = [r.skill for r in posting.requirements if not r.required]

    parts = [
        f"Title: {posting.title}",
        f"Company: {posting.company}",
        f"Location: {posting.location}",
        f"Remote: {posting.remote_policy}",
        f"Seniority: {posting.seniority}",
    ]
    if must_have:
        parts.append(f"Must-have skills: {', '.join(must_have)}")
    if nice_to_have:
        parts.append(f"Nice-to-have skills: {', '.join(nice_to_have)}")
    if posting.responsibilities:
        parts.append(f"Responsibilities: {posting.responsibilities}")
    return "\n".join(parts)


def chunk_posting(posting: JobPostingDB) -> list[dict[str, str]]:
    """Split a posting into section-based chunks for granular retrieval."""
    chunks: list[dict[str, str]] = []

    must_have = [r.skill for r in posting.requirements if r.required]
    nice_to_have = [r.skill for r in posting.requirements if not r.required]

    header = f"{posting.title} at {posting.company} ({posting.location}, {posting.remote_policy})"

    if posting.responsibilities:
        chunks.append({
            "section": "responsibilities",
            "content": f"{header}\nResponsibilities:\n{posting.responsibilities}",
        })
    if must_have:
        chunks.append({
            "section": "must_have",
            "content": f"{header}\nMust-have requirements: {', '.join(must_have)}",
        })
    if nice_to_have:
        chunks.append({
            "section": "nice_to_have",
            "content": f"{header}\nNice-to-have requirements: {', '.join(nice_to_have)}",
        })
    if posting.benefits:
        chunks.append({
            "section": "benefits",
            "content": f"{header}\nBenefits: {posting.benefits}",
        })

    return chunks


def embed_and_store_posting(session: Session, posting: JobPostingDB) -> dict:
    """Generate posting-level and chunk-level embeddings, store in DB.

    Returns usage_info with total cost.
    """
    texts_to_embed: list[str] = []
    chunk_data: list[dict[str, str]] = []

    # Posting-level embedding
    posting_text = format_posting_for_embedding(posting)
    texts_to_embed.append(posting_text)

    # Chunk-level embeddings
    chunks = chunk_posting(posting)
    for chunk in chunks:
        texts_to_embed.append(chunk["content"])
        chunk_data.append(chunk)

    embeddings, usage_info = embed_texts(texts_to_embed)

    # Store posting-level embedding
    posting.embedding = embeddings[0]

    # Store chunk-level embeddings
    for i, chunk in enumerate(chunk_data):
        db_chunk = JobChunkDB(
            posting_id=posting.id,
            section=chunk["section"],
            content=chunk["content"],
            embedding=embeddings[i + 1],
        )
        session.add(db_chunk)

    log.info(
        "embedding_complete",
        company=posting.company,
        title=posting.title,
        chunks=len(chunk_data),
        tokens=usage_info["total_tokens"],
        cost_usd=f"${usage_info['cost_usd']:.6f}",
    )
    return usage_info


def embed_all_postings(session: Session) -> dict:
    """Embed all postings that don't have embeddings yet.

    Returns summary with total cost.
    """
    postings = (
        session.query(JobPostingDB)
        .filter(JobPostingDB.embedding.is_(None))
        .all()
    )

    if not postings:
        log.info("embed_skip", reason="all postings already embedded")
        return {"total": 0, "embedded": 0, "total_cost_usd": 0.0}

    log.info("embed_start", count=len(postings))

    total_cost = 0.0
    embedded = 0

    for posting in postings:
        usage = embed_and_store_posting(session, posting)
        total_cost += usage["cost_usd"]
        embedded += 1

    session.commit()

    summary = {
        "total": len(postings),
        "embedded": embedded,
        "total_cost_usd": total_cost,
    }
    log.info("embed_complete", **summary)
    return summary
