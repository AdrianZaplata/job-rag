import asyncio
import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from job_rag.config import settings
from job_rag.db.engine import AsyncSessionLocal
from job_rag.db.models import JobPostingDB, JobRequirementDB
from job_rag.extraction.extractor import extract_linkedin_id, extract_posting
from job_rag.extraction.prompt import PROMPT_VERSION
from job_rag.logging import get_logger
from job_rag.models import JobPosting

log = get_logger(__name__)


# ====================================================================
# IngestionSource Protocol + data types — Phase 1 BACK-10
# ====================================================================
#
# Threat model (see .planning/phases/01-backend-prep/01-03-PLAN.md):
# - T-03-01 (path-traversal tampering): MarkdownFileSource receives its Path
#   from the CLI (Typer arg) — Adrian-controlled trust boundary. Future
#   IngestionSource implementations that accept user-supplied paths MUST
#   validate at the consumer (e.g., HTTP-uploaded paths).
# - T-03-02 (info-disclosure): IngestResult.error_details captures str(e)
#   tuples. The service layer keeps them structured; Plan 06's /ingest
#   route handler is responsible for sanitization before client surface.
# - T-03-03 (DoS via large file): no file-size cap on the Path read —
#   Adrian-curated single-user corpus accepts this risk for v1.


@dataclass(frozen=True, slots=True)
class RawPosting:
    """A raw posting emitted by an IngestionSource.

    The Protocol intentionally carries NO extraction / DB / hash concerns —
    content_hash is computed by ingest_from_source (D-22), extraction happens
    downstream. Fields are exactly the four locked by D-21.
    """

    raw_text: str
    source_url: str
    source_id: str | None  # e.g. linkedin_job_id, None for bare markdown
    fetched_at: datetime


@runtime_checkable
class IngestionSource(Protocol):
    """Async-iterable source of RawPosting objects. [D-20]

    Implementations are typically async generators. `isinstance(..., IngestionSource)`
    performs attribute-only shape check (Pitfall F, RESEARCH.md §"runtime_checkable
    Protocol's isinstance() only checks attribute presence") — it asserts the
    `__aiter__` attribute exists, NOT that yields are correctly shaped. For real
    contract enforcement, rely on pyright's static check.

    The Protocol declares `def __aiter__(self) -> AsyncIterator[RawPosting]` (sync
    method returning an AsyncIterator) per the standard async-iterator protocol.
    Concrete implementations may use `async def __aiter__` (async generator) — both
    forms produce an AsyncIterator at runtime and pyright basic-mode accepts both
    (Assumption A2).
    """

    def __aiter__(self) -> AsyncIterator[RawPosting]:
        ...


class MarkdownFileSource:
    """v1 IngestionSource: yields one RawPosting per .md file in a directory,
    or a single RawPosting if `path` is a single .md file.

    File reads happen on a thread (asyncio.to_thread) to keep the event loop
    responsive. The linkedin_job_id is best-effort extracted from the raw text
    (first matching `linkedin.com/jobs/view/<id>` URL in the file). [D-23]
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    async def __aiter__(self) -> AsyncIterator[RawPosting]:
        if self.path.is_file():
            files = [self.path]
        else:
            files = sorted(self.path.glob("*.md"))
        for f in files:
            text = await asyncio.to_thread(f.read_text, encoding="utf-8")
            source_id: str | None = None
            for line in text.splitlines():
                if "linkedin.com/jobs/view/" in line:
                    source_id = extract_linkedin_id(line)
                    break
            yield RawPosting(
                raw_text=text,
                source_url=f"file://{f.absolute()}",
                source_id=source_id,
                fetched_at=datetime.now(UTC),
            )


@dataclass
class IngestResult:
    """Summary of an ingest_from_source run.

    posting_ids: ordered list of UUIDs for successfully-ingested postings —
    preserved in the sync ingest_file signature's third tuple slot for CLI
    and /ingest endpoint compatibility (D-24, Assumption A3).
    """

    total: int = 0
    ingested: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: list[tuple[str, str]] = field(default_factory=list)
    total_cost_usd: float = 0.0
    posting_ids: list[str] = field(default_factory=list)


# ====================================================================
# Existing sync helpers — preserved verbatim for backward compat.
# Sync `ingest_file` is rewrapped to delegate to `ingest_from_source`
# (see below); these helpers stay reachable for any other sync caller.
# ====================================================================


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _posting_exists(session: Session, content_hash: str, linkedin_id: str | None) -> bool:
    if linkedin_id:
        existing = (
            session.query(JobPostingDB)
            .filter(
                (JobPostingDB.content_hash == content_hash)
                | (JobPostingDB.linkedin_job_id == linkedin_id)
            )
            .first()
        )
    else:
        existing = (
            session.query(JobPostingDB)
            .filter(JobPostingDB.content_hash == content_hash)
            .first()
        )
    return existing is not None


def _store_posting(
    session: Session,
    posting_data: JobPosting,
    content_hash: str,
    linkedin_id: str | None,
) -> JobPostingDB:

    db_posting = JobPostingDB(
        linkedin_job_id=linkedin_id,
        content_hash=content_hash,
        title=posting_data.title,
        company=posting_data.company,
        location=posting_data.location,
        remote_policy=posting_data.remote_policy.value,
        salary_min=posting_data.salary_min,
        salary_max=posting_data.salary_max,
        salary_raw=posting_data.salary_raw,
        salary_period=posting_data.salary_period.value,
        seniority=posting_data.seniority.value,
        employment_type=posting_data.employment_type,
        responsibilities="\n".join(posting_data.responsibilities),
        benefits="\n".join(posting_data.benefits),
        source_url=posting_data.source_url,
        raw_text=posting_data.raw_text,
        prompt_version=PROMPT_VERSION,
    )
    session.add(db_posting)
    session.flush()

    for req in posting_data.requirements:
        db_req = JobRequirementDB(
            posting_id=db_posting.id,
            skill=req.skill,
            category=req.category.value,
            required=req.required,
        )
        session.add(db_req)

    return db_posting


# ====================================================================
# Async pipeline — primary consumer for Phase 1 onward.
# Sync ingest_file (below) rewraps these for CLI + /ingest backwards compat.
# ====================================================================


async def _posting_exists_async(
    session: AsyncSession,
    content_hash: str,
    linkedin_id: str | None,
) -> bool:
    """Async twin of _posting_exists: dedupe by (content_hash, linkedin_job_id)."""
    stmt = select(JobPostingDB).where(JobPostingDB.content_hash == content_hash)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        return True
    if linkedin_id:
        stmt2 = select(JobPostingDB).where(JobPostingDB.linkedin_job_id == linkedin_id)
        result2 = await session.execute(stmt2)
        if result2.scalar_one_or_none() is not None:
            return True
    return False


async def _store_posting_async(
    session: AsyncSession,
    posting_data: JobPosting,
    content_hash: str,
    linkedin_id: str | None,
) -> JobPostingDB:
    """Async twin of _store_posting. Field mapping mirrors the sync helper exactly
    (T-03-04 mitigation — drift would surface as Pydantic/SQLAlchemy errors).

    Returns the in-flight DB row; caller is responsible for the outer commit
    (ingest_from_source commits per-iteration so partial failures don't roll back
    earlier successes).
    """
    db_posting = JobPostingDB(
        linkedin_job_id=linkedin_id,
        content_hash=content_hash,
        title=posting_data.title,
        company=posting_data.company,
        location=posting_data.location,
        remote_policy=posting_data.remote_policy.value,
        salary_min=posting_data.salary_min,
        salary_max=posting_data.salary_max,
        salary_raw=posting_data.salary_raw,
        salary_period=posting_data.salary_period.value,
        seniority=posting_data.seniority.value,
        employment_type=posting_data.employment_type,
        responsibilities="\n".join(posting_data.responsibilities),
        benefits="\n".join(posting_data.benefits),
        source_url=posting_data.source_url,
        raw_text=posting_data.raw_text,
        prompt_version=PROMPT_VERSION,
    )
    session.add(db_posting)
    await session.flush()  # populate db_posting.id before attaching children

    for req in posting_data.requirements:
        db_req = JobRequirementDB(
            posting_id=db_posting.id,
            skill=req.skill,
            category=req.category.value,
            required=req.required,
        )
        session.add(db_req)

    return db_posting


async def _embed_and_store_async(
    session: AsyncSession,
    db_posting: JobPostingDB,
) -> None:
    """Async twin of embed_and_store_posting — Phase 1 Option A bridge (D-24).

    `embed_and_store_posting` in src/job_rag/services/embedding.py is sync and
    accepts a sync Session. We commit the pending async INSERT so the sync
    session can reload the row, then delegate the embedding work to a thread
    with a fresh SessionLocal. Full async embedding pipeline is explicit
    future work (CONTEXT §Deferred Ideas).

    The JobPostingDB row is committed BEFORE embedding runs — if the embedding
    call fails, the row remains and the error surfaces to ingest_from_source's
    except block (counted under IngestResult.errors). This mirrors the sync
    ingest_file partial-success semantics.
    """
    # Commit the async session's pending INSERT so the sync session reads the row.
    await session.commit()
    posting_id = db_posting.id

    def _sync_embed() -> None:
        # Imports kept inside the thread body to keep _embed_and_store_async
        # free of sync embedding imports at module scope.
        from job_rag.db.engine import SessionLocal
        from job_rag.services.embedding import embed_and_store_posting

        with SessionLocal() as sync_session:
            reloaded = sync_session.get(JobPostingDB, posting_id)
            if reloaded is None:
                raise RuntimeError(
                    f"JobPostingDB {posting_id} not visible in sync session after commit"
                )
            embed_and_store_posting(sync_session, reloaded)
            sync_session.commit()

    await asyncio.to_thread(_sync_embed)


async def ingest_from_source(
    async_session: AsyncSession,
    source: IngestionSource,
) -> IngestResult:
    """Run a source end-to-end: dedupe, extract, embed, store. [D-22, D-24]

    content_hash is computed HERE (D-22) — never inside the source.
    extract_posting (sync + LLM) is pushed to a thread to keep the loop free.
    Each iteration commits independently — a single failure does not roll back
    successfully-ingested prior postings.
    """
    result = IngestResult()

    async for raw in source:
        result.total += 1
        c_hash = hashlib.sha256(raw.raw_text.encode()).hexdigest()

        if await _posting_exists_async(async_session, c_hash, raw.source_id):
            result.skipped += 1
            log.info(
                "skipped_duplicate",
                source_url=raw.source_url,
                source_id=raw.source_id,
            )
            continue

        try:
            # extract_posting is sync + LLM — push to thread for event-loop safety
            posting, usage = await asyncio.to_thread(extract_posting, raw.raw_text)
            posting.raw_text = raw.raw_text

            # Best-effort LinkedIn ID fallback from the extracted source_url
            linkedin_id = raw.source_id
            if not linkedin_id:
                linkedin_id = extract_linkedin_id(posting.source_url)

            db_posting = await _store_posting_async(
                async_session, posting, c_hash, linkedin_id
            )
            await _embed_and_store_async(async_session, db_posting)
            # _embed_and_store_async already committed the posting INSERT;
            # this commit captures any pending state from JobRequirementDB rows
            # added in _store_posting_async (they were flushed but the embed
            # commit only persists the parent INSERT under SA's UoW semantics).
            await async_session.commit()
            result.ingested += 1
            result.total_cost_usd += float(usage.get("cost_usd", 0.0))
            result.posting_ids.append(str(db_posting.id))
        except IntegrityError:
            await async_session.rollback()
            result.skipped += 1
            log.info(
                "skipped_concurrent_duplicate",
                source_url=raw.source_url,
                source_id=raw.source_id,
            )
        except Exception as e:
            await async_session.rollback()
            result.errors += 1
            result.error_details.append((raw.source_url, str(e)))
            log.error("ingest_error", source_url=raw.source_url, error=str(e))

    return result


def ingest_file(
    session: Session,  # noqa: ARG001 - retained for signature parity (D-24)
    file_path: Path,
) -> tuple[bool, str, str | None]:
    """Sync entry point — preserved for CLI and existing /ingest endpoint (D-24).

    Internally constructs a MarkdownFileSource and runs ingest_from_source via
    asyncio.run under a fresh AsyncSession. The sync `session` parameter is
    kept for signature parity (CLI + /ingest pass one) but is NOT used —
    async session is opened internally so the async pipeline works end-to-end.

    Caveat: asyncio.run() raises RuntimeError if called from inside an active
    event loop. This sync wrapper is only safe from sync contexts (Typer CLI).
    The current /ingest FastAPI route is async — Plan 06 will rewrite that
    handler to call `ingest_from_source` directly with the request's
    AsyncSession dependency, removing the asyncio.run hop.

    Returns (was_ingested, reason, posting_id) — the same 3-tuple shape the
    CLI and /ingest route already consume; posting_id (slot 3) is preserved
    via IngestResult.posting_ids[0] on success (Assumption A3).
    """

    async def _run() -> IngestResult:
        async with AsyncSessionLocal() as async_session:
            return await ingest_from_source(
                async_session, MarkdownFileSource(file_path)
            )

    result = asyncio.run(_run())

    if result.ingested:
        posting_id = result.posting_ids[0] if result.posting_ids else None
        return True, f"ingested (${result.total_cost_usd:.4f})", posting_id
    if result.skipped:
        return False, "duplicate", None
    if result.errors:
        msg = result.error_details[0][1] if result.error_details else "unknown"
        return False, f"error: {msg}", None
    return False, "no_content", None


def ingest_directory(session: Session, directory: Path | None = None) -> dict:
    """Ingest all markdown files from a directory.

    Returns summary stats.
    """
    if directory is None:
        directory = Path(settings.data_dir)

    files = sorted(directory.glob("*.md"))
    log.info("ingest_start", directory=str(directory), file_count=len(files))

    ingested = 0
    skipped = 0
    errors = []
    total_cost = 0.0

    for f in files:
        try:
            was_ingested, reason, _posting_id = ingest_file(session, f)
            if was_ingested:
                ingested += 1
                if "$" in reason:
                    cost_str = reason.split("$")[1].rstrip(")")
                    total_cost += float(cost_str)
            else:
                skipped += 1
        except Exception as e:
            log.error("ingest_error", file=f.name, error=str(e))
            errors.append((f.name, str(e)))

    summary = {
        "total_files": len(files),
        "ingested": ingested,
        "skipped": skipped,
        "errors": len(errors),
        "error_details": errors,
        "total_cost_usd": total_cost,
    }
    log.info("ingest_complete", **{k: v for k, v in summary.items() if k != "error_details"})
    return summary
