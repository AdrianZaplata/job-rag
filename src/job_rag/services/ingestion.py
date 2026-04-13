import hashlib
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from job_rag.config import settings
from job_rag.db.models import JobPostingDB, JobRequirementDB
from job_rag.extraction.extractor import extract_linkedin_id, extract_posting
from job_rag.extraction.prompt import PROMPT_VERSION
from job_rag.logging import get_logger
from job_rag.models import JobPosting

log = get_logger(__name__)


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
                total_cost += cost
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
