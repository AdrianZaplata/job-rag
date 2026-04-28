"""Re-extraction service for prompt_version drift correction.

Per D-13: lives here (not in services/ingestion.py) -- keeps the ingest path
focused on net-new content. Reuses extract_posting() from
extraction/extractor.py directly (D-15: embeddings preserved -- raw_text,
job_postings.embedding, job_chunks.* are NOT touched).

Per Pattern 3 in 02-RESEARCH.md: fresh AsyncSession per posting iteration
(Pitfall 5 -- B1ms 5-conn pool would saturate during 1-3s LLM round-trips
if one outer session held the conn for the whole loop).
"""
import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import delete, select

from job_rag.db.engine import AsyncSessionLocal
from job_rag.db.models import JobPostingDB, JobRequirementDB
from job_rag.extraction.extractor import extract_posting
from job_rag.extraction.prompt import PROMPT_VERSION
from job_rag.logging import get_logger
from job_rag.models import derive_skill_category

log = get_logger(__name__)


@dataclass
class ReextractReport:
    """Summary of a reextract_stale run.

    - selected: rows that matched the WHERE clause (also: count for --dry-run)
    - succeeded: per-posting commits that succeeded
    - failed: per-posting failures (extraction error, validation error, etc.)
    - skipped: only meaningful for --dry-run (== selected when dry_run=True)
    - total_cost_usd: sum of usage_info["cost_usd"] across successful runs
    - failures: list of (posting_id, error_message) for surfacing in CLI output
    """

    selected: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_cost_usd: float = 0.0
    failures: list[tuple[UUID, str]] = field(default_factory=list)


async def reextract_stale(
    *,
    all: bool = False,
    posting_id: UUID | None = None,
    dry_run: bool = False,
    yes: bool = False,
) -> ReextractReport:
    """Re-extract postings whose prompt_version is stale (D-12, D-14, D-16).

    Default selection: WHERE prompt_version != PROMPT_VERSION (idempotent --
    re-running picks up only the still-stale rows after a partial failure).

    Override flags:
    - all=True:        re-extract every row regardless of prompt_version.
                       Requires yes=True (T-CLI-01 mitigation) -- the CLI
                       subcommand calls typer.confirm before passing yes=True.
    - posting_id=...:  single-posting debug; selects exactly that one row.
    - dry_run=True:    count what would be re-extracted, no UPDATE.

    Per-posting commit (D-16): one fresh AsyncSession per row so partial
    failures don't roll back earlier successes. Each session is short-lived
    (~1-3s for the LLM call + ~10ms for the UPDATE/DELETE), respecting the
    B1ms 3+2 pool budget.
    """
    if all and not yes:
        raise RuntimeError(
            "--all requires explicit confirmation: call with yes=True "
            "or use `job-rag reextract --all` which prompts."
        )

    report = ReextractReport()

    # Phase 1: SELECT target IDs in a fresh session, then close. Holding open
    # one session for the whole loop is rejected (Pitfall 5).
    async with AsyncSessionLocal() as session:
        if posting_id is not None:
            stmt = select(JobPostingDB.id).where(JobPostingDB.id == posting_id)
        elif all:
            stmt = select(JobPostingDB.id)
        else:
            stmt = select(JobPostingDB.id).where(
                JobPostingDB.prompt_version != PROMPT_VERSION,
            )
        result = await session.execute(stmt)
        target_ids = [row[0] for row in result.all()]

    report.selected = len(target_ids)
    log.info(
        "reextract_started",
        selected=report.selected,
        all=all,
        posting_id=str(posting_id) if posting_id else None,
        dry_run=dry_run,
        prompt_version=PROMPT_VERSION,
    )

    if dry_run:
        report.skipped = len(target_ids)
        log.info("reextract_dry_run_complete", would_reextract=report.skipped)
        return report

    # Phase 2: Per-posting loop. Each iteration: fresh session, load row,
    # extract, write, commit. On exception: session rolls back via
    # `async with` exit; loop continues (D-16).
    for pid in target_ids:
        try:
            await _reextract_one(pid, report)
        except Exception as e:
            # Defensive belt-and-suspenders -- _reextract_one catches its own
            # exceptions. This catches anything that escapes (e.g., session
            # creation errors).
            report.failed += 1
            report.failures.append((pid, str(e)))
            log.error("reextract_failed", posting_id=str(pid), error=str(e))

    log.info(
        "reextract_complete",
        selected=report.selected,
        succeeded=report.succeeded,
        failed=report.failed,
        total_cost_usd=report.total_cost_usd,
    )
    return report


async def _reextract_one(posting_id: UUID, report: ReextractReport) -> None:
    """Re-extract a single posting. Fresh AsyncSession per call.

    Touches structured fields only (D-15): raw_text, job_postings.embedding,
    job_chunks.* are PRESERVED unchanged. Requirements rebuilt via DELETE
    all + INSERT new (cleanest semantics; ondelete=CASCADE handles cleanup
    if the parent were deleted, but parent stays -- explicit DELETE on
    children is clearer).
    """
    async with AsyncSessionLocal() as session:
        try:
            # Load the row.
            stmt = select(JobPostingDB).where(JobPostingDB.id == posting_id)
            result = await session.execute(stmt)
            db_posting = result.scalar_one_or_none()
            if db_posting is None:
                report.failed += 1
                report.failures.append((posting_id, "posting_not_found"))
                return

            raw_text = db_posting.raw_text

            # LLM call -- push to thread (extract_posting is sync, retry is
            # already applied via @retry in extractor.py -- 3 attempts, exp
            # backoff 1-10s).
            posting, usage = await asyncio.to_thread(extract_posting, raw_text)

            # Open Q5 / Pitfall 3 mitigation: GPT-4o-mini sometimes returns
            # "" instead of null for unknown optional fields. Coerce
            # defensively before writing -- keeps the alpha-2 length
            # invariant on country.
            if posting.location.country == "":
                posting.location.country = None
            if posting.location.city == "":
                posting.location.city = None
            if posting.location.region == "":
                posting.location.region = None

            # Update structured fields. Embedding intentionally NOT touched
            # (D-15). raw_text NOT touched (preserved verbatim).
            db_posting.title = posting.title
            db_posting.company = posting.company
            db_posting.location_country = posting.location.country
            db_posting.location_city = posting.location.city
            db_posting.location_region = posting.location.region
            db_posting.remote_policy = posting.remote_policy.value
            db_posting.salary_min = posting.salary_min
            db_posting.salary_max = posting.salary_max
            db_posting.salary_raw = posting.salary_raw
            db_posting.salary_period = posting.salary_period.value
            db_posting.seniority = posting.seniority.value
            db_posting.employment_type = posting.employment_type
            db_posting.responsibilities = "\n".join(posting.responsibilities)
            db_posting.benefits = "\n".join(posting.benefits)
            db_posting.source_url = posting.source_url
            db_posting.prompt_version = PROMPT_VERSION

            # Rebuild requirements: DELETE all old children, INSERT new.
            await session.execute(
                delete(JobRequirementDB).where(
                    JobRequirementDB.posting_id == posting_id,
                ),
            )
            for req in posting.requirements:
                skill_cat = derive_skill_category(req.skill_type)
                session.add(JobRequirementDB(
                    posting_id=posting_id,
                    skill=req.skill,
                    skill_type=req.skill_type.value,
                    skill_category=skill_cat.value,
                    required=req.required,
                ))

            await session.commit()
            report.succeeded += 1
            report.total_cost_usd += float(usage.get("cost_usd", 0.0))
            log.info(
                "reextract_posting_complete",
                posting_id=str(posting_id),
                cost_usd=usage.get("cost_usd", 0.0),
                requirements_count=len(posting.requirements),
            )
        except Exception as e:
            await session.rollback()
            report.failed += 1
            report.failures.append((posting_id, str(e)))
            log.error(
                "reextract_failed",
                posting_id=str(posting_id),
                error=str(e),
            )
