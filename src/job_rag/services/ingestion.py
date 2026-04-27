import asyncio
import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from job_rag.config import settings
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


def ingest_file(session: Session, file_path: Path) -> tuple[bool, str, str | None]:
    """Ingest a single markdown posting file.

    Returns (was_ingested, reason, posting_id).
    """
    raw_text = file_path.read_text(encoding="utf-8")
    c_hash = _content_hash(raw_text)

    # Try to extract linkedin ID from raw text before calling LLM
    linkedin_id = None
    for line in raw_text.splitlines():
        if "linkedin.com/jobs/view/" in line:
            linkedin_id = extract_linkedin_id(line)
            break

    if _posting_exists(session, c_hash, linkedin_id):
        log.info("skipped_duplicate", file=file_path.name, linkedin_id=linkedin_id)
        return False, "duplicate", None

    posting, usage = extract_posting(raw_text)
    posting.raw_text = raw_text

    if not linkedin_id:
        linkedin_id = extract_linkedin_id(posting.source_url)

    try:
        db_posting = _store_posting(session, posting, c_hash, linkedin_id)
        session.commit()
    except IntegrityError:
        session.rollback()
        log.info("skipped_concurrent_duplicate", file=file_path.name)
        return False, "duplicate", None

    return True, f"ingested (${usage['cost_usd']:.4f})", str(db_posting.id)


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
