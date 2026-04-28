# Phase 2: Corpus Cleanup - Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 19 (4 created + 15 modified)
**Analogs found:** 19 / 19 (all files have at least one role-match analog in-tree)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `alembic/versions/0004_corpus_cleanup.py` (NEW) | migration | DDL + backfill (transform) | `alembic/versions/0003_add_career_id.py` (server_default backfill) + `alembic/versions/0001_baseline.py` (table/index DDL) | role-match (no rename precedent in-tree, but same migration framework) |
| `src/job_rag/services/extraction.py` (NEW) | service | batch + per-iteration commit (transform/I-O) | `src/job_rag/services/ingestion.py::ingest_from_source` | role-match (sibling service; loop semantics nearly identical) |
| `src/job_rag/models.py` (MODIFIED) | model | pure compute (Pydantic schema) | self (existing `SkillCategory` / `JobRequirement` / `JobPosting`) | exact (extends own patterns) |
| `src/job_rag/db/models.py` (MODIFIED) | model | ORM column declarations | self (existing `JobPostingDB` / `JobRequirementDB`) + `0002`'s `UserProfileDB` (server_default text columns) | exact |
| `src/job_rag/extraction/prompt.py` (MODIFIED) | config | static template (compute) | self (current `PROMPT_VERSION` + `SYSTEM_PROMPT`) | exact (rewrite-in-place) |
| `src/job_rag/cli.py` (MODIFIED — `reextract` subcommand) | CLI/controller | request-response → async service | `cli.py::ingest`, `cli.py::embed`, `cli.py::agent` (async-via-`asyncio.run`) | exact |
| `src/job_rag/cli.py` (MODIFIED — `list --stats` flag) | CLI/controller | sync DB read → stdout | `cli.py::stats`, `cli.py::list_postings` | exact |
| `src/job_rag/services/ingestion.py` (MODIFIED — `_store_posting*`) | service | LLM-result → ORM write | self (existing `_store_posting` and `_store_posting_async`) | exact |
| `src/job_rag/services/matching.py` (MODIFIED — rename reads) | service | ORM read | self (existing `match_posting` reads `req.required`/`req.skill`) | exact |
| `src/job_rag/services/retrieval.py` (MODIFIED — rename reads + RAG f-string) | service | ORM read → LLM context | self (existing `rag_query` line 206-207 context build) | exact |
| `src/job_rag/mcp_server/tools.py` (MODIFIED — `_serialize_posting`) | controller/glue | ORM → dict | self (existing `_serialize_posting`) | exact |
| `src/job_rag/api/app.py` (MODIFIED — lifespan extension) | controller/glue | request-response (lifespan startup) | self (existing `@asynccontextmanager` lifespan) | exact |
| `tests/test_models.py` (MODIFIED) | test | unit | self (existing `TestJobRequirement`, `TestJobPosting`) | exact |
| `tests/test_extraction.py` (MODIFIED) | test | unit + integration | self (existing `TestExtractPosting`) | exact |
| `tests/test_alembic.py` (MODIFIED — upgrade/downgrade smoke) | test | filesystem scan + Alembic | self (existing `test_no_default_uuid_on_user_id_columns` filesystem scan) — see Pattern Note | partial (existing test is a regex guard, not an upgrade smoke; smoke is a NEW pattern in-tree) |
| `tests/test_reextract.py` (NEW) | test | async + monkeypatch | `tests/test_ingestion.py::TestIngestFromSource` (async monkeypatch + AsyncMock pattern) | exact |
| `tests/test_lifespan.py` (MODIFIED) | test | async lifespan | self (existing `TestLifespanStartup` + `lifespan_manager` fixture) | exact |
| `tests/test_cli.py` (MODIFIED — `TestListStatsPromptVersion`) | test | Typer CLI runner | self (existing `TestInitDbCommand`, `runner.invoke` pattern) | exact |
| `tests/conftest.py` (MODIFIED — sample_posting fixture) | test fixture | static data | self (existing `sample_posting` fixture) | exact |

---

## Pattern Assignments

### `alembic/versions/0004_corpus_cleanup.py` (migration, DDL + backfill)

**Primary analog:** `alembic/versions/0003_add_career_id.py`
**Secondary analog (DDL shape):** `alembic/versions/0001_baseline.py` lines 88-111 (job_requirements table + indexes)
**Secondary analog (idempotent data step):** `alembic/versions/0002_add_user_profile.py` lines 87-96 (`op.execute(sa.text(...))` + `ON CONFLICT DO NOTHING`)

**Header pattern** (copy verbatim from `0003_add_career_id.py:1-22`):
```python
"""add career_id column to job_postings

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27

D-13: every v1 posting is an AI Engineer role; future career expansion
will be explicit. Unlike user_id, a DDL DEFAULT IS intentional here —
backfills all pre-existing rows in one statement.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

For 0004, change `revision = "0004"`, `down_revision = "0003"`, and the docstring should explicitly note "HAND-WRITTEN — autogenerate detects rename as drop+add" (Pitfall 1).

**Add column DDL pattern** (`0003_add_career_id.py:24-34`):
```python
def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "job_postings",
        sa.Column(
            "career_id",
            sa.String(50),
            nullable=False,
            server_default="ai_engineer",  # DDL DEFAULT OK here (D-13)
        ),
    )
```

**Drop column DDL pattern** (same file, line 38):
```python
def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("job_postings", "career_id")
```

**Index creation pattern** (`0001_baseline.py:100-111`):
```python
op.create_index(
    "ix_job_requirements_category",
    "job_requirements",
    ["category"],
    unique=False,
)
op.create_index(
    "ix_job_requirements_skill",
    "job_requirements",
    ["skill"],
    unique=False,
)
```

**Index drop pattern** (`0001_baseline.py:148-149`):
```python
op.drop_index("ix_job_requirements_skill", table_name="job_requirements")
op.drop_index("ix_job_requirements_category", table_name="job_requirements")
```

**Raw SQL execute (for the SQL CASE backfill)** — pattern from `0002_add_user_profile.py:87-96`:
```python
# Seed Adrian's user row — idempotent via ON CONFLICT (T-02-02).
op.execute(
    sa.text(
        "INSERT INTO users (id, email) VALUES (:user_id, :email) "
        "ON CONFLICT (id) DO NOTHING"
    ).bindparams(
        user_id=SEEDED_USER_ID,
        email="adrianzaplata@gmail.com",
    )
)
```

For 0004, plain `op.execute("UPDATE ... SET skill_category = CASE ... END")` (no bindparams needed — the CASE values are literals); the wrapper is the same.

**NEW pattern (no in-tree analog) — `op.alter_column(new_column_name=...)`:**
This is documented in RESEARCH.md §Pattern 1 lines 360-369. No prior migration in this repo renames a column. Plan must explicitly document the hand-written nature (top-of-file docstring) and the 5-step ordering (rename → drop old index → add nullable → backfill → set NOT NULL → create new indexes). See Pitfall 1, 2, 6 in RESEARCH.md.

---

### `src/job_rag/services/extraction.py` (NEW service, batch + per-iteration commit)

**Primary analog:** `src/job_rag/services/ingestion.py::ingest_from_source` (lines 308-370) — closest sibling. Reextract is the same shape: async iteration over a corpus, per-iteration commit on success, log+continue on failure.

**Imports pattern** (`services/ingestion.py:1-22`):
```python
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
```

For `services/extraction.py`: drop `hashlib`, `Path`, `Protocol`, `runtime_checkable`, `IntegrityError`, `Session`, `MarkdownFileSource`-related imports. Add `from sqlalchemy import delete` (for `DELETE FROM job_requirements WHERE posting_id=...`) and `from job_rag.models import derive_skill_category`. Module-level `log = get_logger(__name__)` is mandatory.

**Result dataclass pattern** (`services/ingestion.py:109-124`):
```python
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
```

For `ReextractReport` (RESEARCH.md §Pattern 3 lines 625-634): same `@dataclass` + `field(default_factory=...)` shape, fields are `selected / succeeded / failed / skipped / total_cost_usd / failures`.

**Per-iteration commit + log+continue pattern** (`services/ingestion.py:319-370`):
```python
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
```

**Critical deviation for `reextract_stale`** (RESEARCH.md Pitfall 5 + §Pattern 3): unlike `ingest_from_source` which holds **one** outer `AsyncSession` for the whole loop, `reextract_stale` MUST open a **fresh `AsyncSession` per posting**. Reason: each iteration takes 1-3s of LLM time; B1ms 5-conn pool would saturate. The recipe in RESEARCH.md §Pattern 3 (lines 661-692) uses two sessions: one for `_select_target_ids` (closed before the loop), one fresh per `_reextract_one(posting_id)` call.

**Structlog event naming convention** (used throughout `services/ingestion.py` and `services/embedding.py`):
- `log.info("event_name_underscore_separated", key1=value1, key2=value2)`
- For Phase 2: `reextract_started`, `reextract_dry_run_complete`, `reextract_posting_complete`, `reextract_failed`, `reextract_complete` (RESEARCH.md §Pattern 3).

**LLM call pushed to thread + tenacity inheritance** (`services/ingestion.py:336`):
```python
posting, usage = await asyncio.to_thread(extract_posting, raw.raw_text)
```
`extract_posting` is already retry-decorated (`extraction/extractor.py:36`). Reextract reuses verbatim — RESEARCH.md §Anti-Patterns: "DO NOT change `extract_posting()` signature."

**DELETE-then-INSERT requirements rebuild** — no in-tree analog (existing ingest writes new rows once); follow RESEARCH.md §Pattern 3 lines 759-772:
```python
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
```

---

### `src/job_rag/models.py` (Pydantic models — extend existing patterns)

**Primary analog:** self (the file already has all the patterns Phase 2 needs).

**StrEnum + Field pattern** (`models.py:1-14`, `40-71`):
```python
from enum import StrEnum

from pydantic import BaseModel, Field


class SkillCategory(StrEnum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    CLOUD = "cloud"
    DATABASE = "database"
    CONCEPT = "concept"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    DOMAIN = "domain"
```

For Phase 2: rename this enum to `SkillType` (D-01); add a NEW `SkillCategory(StrEnum)` with `HARD = "hard"` / `SOFT = "soft"` / `DOMAIN = "domain"` (D-02). Same `StrEnum` + UPPERCASE-name + lowercase-value convention.

**Pydantic submodel + nullable field pattern** (`models.py:48-71`):
```python
class JobPosting(BaseModel):
    """Structured representation of an AI Engineer job posting."""

    title: str = Field(description="Job title as written in the posting")
    company: str = Field(description="Company name")
    location: str = Field(description="City/country where the job is based")
    remote_policy: RemotePolicy = Field(description="Remote work policy")
    salary_min: int | None = Field(default=None, description="Minimum salary in EUR/year, or None")
    salary_max: int | None = Field(default=None, description="Maximum salary in EUR/year, or None")
```

For new `Location` submodel (D-06): identical `BaseModel` + `Field(default=None, description=...)` pattern. Three nullable fields; `country` carries `description="ISO-3166 alpha-2 code"` (the description propagates into Instructor's JSON Schema — RESEARCH.md Pitfall 3).

**Pure-function helper pattern** — no in-tree analog in `models.py` (it's currently models-only). The pattern from `services/matching.py:38-40` is the closest:
```python
def _normalize_skill(name: str) -> str:
    """Normalize skill name for fuzzy matching."""
    return name.lower().strip().replace("-", " ").replace("_", " ")
```

For `derive_skill_category(skill_type: SkillType) -> SkillCategory`: module-level def, single-line docstring, type hints required, body is a dict-lookup or `match` statement. Living in `models.py` is the project's convention for enum-adjacent helpers (per CONTEXT.md D-03).

---

### `src/job_rag/db/models.py` (SQLAlchemy ORM — extend existing patterns)

**Primary analog:** self (`JobPostingDB` and `JobRequirementDB` already use the SQLAlchemy 2.x `Mapped[]` syntax Phase 2 extends).

**Mapped column declaration pattern** (`db/models.py:11-53`):
```python
class JobPostingDB(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    linkedin_job_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_policy: Mapped[str] = mapped_column(String(20), nullable=False)
    ...

    __table_args__ = (
        Index("ix_job_postings_company", "company"),
        Index("ix_job_postings_seniority", "seniority"),
        Index("ix_job_postings_remote_policy", "remote_policy"),
    )
```

For Phase 2:
- Drop `location` (D-11) — remove the `Mapped[str]` line entirely.
- Add three new lines following the `Mapped[str | None]` pattern:
  ```python
  location_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
  location_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
  location_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
  ```
- Add `Index("ix_job_postings_location_country", "location_country")` to `__table_args__` (Claude's Discretion in CONTEXT.md, recommended in RESEARCH.md).

**Rename pattern** (`db/models.py:62`):
```python
category: Mapped[str] = mapped_column(String(20), nullable=False)
```
→ rename to `skill_type: Mapped[str] = ...` (same shape). Add a new line `skill_category: Mapped[str] = mapped_column(String(20), nullable=False)`. Update `__table_args__`:
- Replace `Index("ix_job_requirements_category", "category")` → `Index("ix_job_requirements_skill_type", "skill_type")`.
- Add `Index("ix_job_requirements_skill_category", "skill_category")`.

**Idempotency note (alembic check):** `db/models.py:122-126` documents that ORM `server_default` values mirror migration `server_default` values exactly so `alembic check` reports no drift. Same discipline applies here: ORM column types/lengths must match migration 0004 exactly.

---

### `src/job_rag/extraction/prompt.py` (rewrite SYSTEM_PROMPT)

**Primary analog:** self (current file).

**Module-level constant pattern** (`prompt.py:1-3`):
```python
PROMPT_VERSION = "1.1"

SYSTEM_PROMPT = """\
You are a precise data extraction assistant. ...
```

For Phase 2:
- Bump to `PROMPT_VERSION = "2.0"` (D-22).
- Add `REJECTED_SOFT_SKILLS: tuple[str, ...] = (..., ..., ...)` constant (D-18).
- Replace `SYSTEM_PROMPT` with `_SYSTEM_PROMPT_TEMPLATE = """..."""` followed by `SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(rejected_terms=", ".join(REJECTED_SOFT_SKILLS))`.

**Critical: use `str.format()`, NOT f-string** (RESEARCH.md §Pattern 2 + Pitfall 4). The current `SYSTEM_PROMPT` (lines 43-56) contains JSON-array literals like `["automotive AI", "production deployment"]` — the `[` and `]` are fine, but with f-string, every `{` and `}` would need doubling. Using `str.format()` with one named placeholder `{rejected_terms}` keeps the existing decomposition examples clean. Brace-doubling is required ONLY on the four NEW Location example lines (RESEARCH.md §Pattern 2 lines 535-538).

**Existing prompt content to preserve verbatim** (`prompt.py:31-56`): The DECOMPOSITION RULES section + 8 decomposition examples. Phase 2 adds:
- "REJECTION RULES" section (interpolated `{rejected_terms}`).
- Mention of `skill_category` derived deterministically (NOT extracted by LLM).
- "LOCATION EXTRACTION" section with 4 D-09 examples (with `{{...}}` brace-doubling).
- Borderline-policy mention (leadership/mentoring extracted as soft_skill).

---

### `src/job_rag/cli.py` — `reextract` subcommand (NEW Typer command)

**Primary analog:** `cli.py::agent` (lines 205-247) — the only existing async-via-`asyncio.run` Typer command.

**Async-via-asyncio.run + structured output pattern** (`cli.py:205-247`):
```python
@app.command()
def agent(
    query: str = typer.Argument(..., help="Question to ask the agent"),
    stream: bool = typer.Option(False, "--stream", help="Stream tool calls and tokens"),
) -> None:
    """Run the LangGraph agent on a single query."""
    import asyncio

    from job_rag.observability import flush

    async def _run() -> None:
        if stream:
            from job_rag.agent.stream import stream_agent
            ...
        else:
            from job_rag.agent.graph import run_agent
            result = await run_agent(query)
            typer.echo(result["answer"])
            ...

    try:
        asyncio.run(_run())
    finally:
        flush()
```

For `reextract`:
```python
@app.command()
def reextract(
    all: bool = typer.Option(False, "--all", help="Re-extract every row regardless of prompt_version"),
    posting_id: str = typer.Option(None, "--posting-id", help="Re-extract a single posting by UUID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Count what would be re-extracted, no UPDATE"),
) -> None:
    """Re-extract postings whose prompt_version is stale (D-12, D-14, D-16)."""
    import asyncio
    from uuid import UUID

    from job_rag.services.extraction import reextract_stale

    async def _run():
        pid = UUID(posting_id) if posting_id else None
        return await reextract_stale(all=all, posting_id=pid, dry_run=dry_run)

    report = asyncio.run(_run())
    typer.echo(f"\nRe-extraction complete (PROMPT_VERSION={...}):")
    typer.echo(f"  Selected:    {report.selected}")
    typer.echo(f"  Succeeded:   {report.succeeded}")
    typer.echo(f"  Failed:      {report.failed}")
    typer.echo(f"  Skipped:     {report.skipped}")
    typer.echo(f"  Total cost:  ${report.total_cost_usd:.4f}")
    if report.failures:
        typer.echo("\nFailures:")
        for pid, err in report.failures:
            typer.echo(f"  {pid}: {err}")
```

**Output formatting pattern** copied from `cli.py::ingest` (lines 28-39):
```python
typer.echo("\nIngestion complete:")
typer.echo(f"  Total files:  {summary['total_files']}")
typer.echo(f"  Ingested:     {summary['ingested']}")
typer.echo(f"  Skipped:      {summary['skipped']}")
typer.echo(f"  Errors:       {summary['errors']}")
if show_cost:
    typer.echo(f"  Total cost:   ${summary['total_cost_usd']:.4f}")
if summary["error_details"]:
    typer.echo("\nErrors:")
    for filename, error in summary["error_details"]:
        typer.echo(f"  {filename}: {error}")
```

**Local-import-inside-function convention** — every existing `@app.command()` in `cli.py` does its imports inside the function body (e.g., `cli.py:24-26`, `cli.py:48-50`, `cli.py:172-173`). Phase 2 follows this — imports `asyncio`, `UUID`, `reextract_stale` inside `def reextract`.

---

### `src/job_rag/cli.py` — `list --stats` flag (extend existing command)

**Primary analog:** `cli.py::list_postings` (lines 64-89) — extend in place.

**Existing list command** (`cli.py:64-89`):
```python
@app.command(name="list")
def list_postings(
    company: str = typer.Option(None, "--company", "-c", help="Filter by company name"),
) -> None:
    """List all ingested job postings."""
    from job_rag.db.engine import SessionLocal
    from job_rag.db.models import JobPostingDB

    session = SessionLocal()
    try:
        query = session.query(JobPostingDB).order_by(JobPostingDB.company)
        if company:
            query = query.filter(JobPostingDB.company.ilike(f"%{company}%"))
        postings = query.all()

        if not postings:
            typer.echo("No postings found.")
            return

        typer.echo(f"\n{'Company':<25} {'Title':<40} {'Location':<20} {'Remote':<10}")
        typer.echo("-" * 95)
        for p in postings:
            typer.echo(f"{p.company:<25} {p.title:<40} {p.location:<20} {p.remote_policy:<10}")
        typer.echo(f"\nTotal: {len(postings)} postings")
    finally:
        session.close()
```

**Phase 2 changes:**
1. Add `stats: bool = typer.Option(False, "--stats", help="...")` parameter.
2. Add a `Counter` import + branching `if stats:` block (RESEARCH.md §Pattern 5 lines 884-906) before the existing posting-table behavior.
3. Replace `p.location` with `p.location_country or "—"` in the table output (the `location` column is dropped in 0004).

**Counter pattern** copied from `cli.py::stats` (lines 109-117):
```python
from collections import Counter

skill_counts: Counter[str] = Counter()
category_counts: Counter[str] = Counter()
must_have_counts: Counter[str] = Counter()

for req in requirements:
    skill_counts[req.skill] += 1
    category_counts[req.category] += 1
    if req.required:
        must_have_counts[req.skill] += 1
```

For `list --stats`:
```python
counts: Counter[str] = Counter()
for p in session.query(JobPostingDB).all():
    counts[p.prompt_version] += 1
typer.echo(f"\n=== Prompt version distribution (current: {PROMPT_VERSION}) ===")
for ver, count in sorted(counts.items(), reverse=True):
    marker = "" if ver == PROMPT_VERSION else " ⚠️ STALE"
    typer.echo(f"  prompt_version={ver}: {count}{marker}")
```

---

### `src/job_rag/services/ingestion.py` — `_store_posting` + `_store_posting_async` updates

**Primary analog:** self (existing `_store_posting` lines 157-195 and `_store_posting_async` lines 222-266).

**Existing field-mapping pattern** (`services/ingestion.py:164-195`):
```python
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
```

**Phase 2 changes (apply identically to both sync `_store_posting` and async `_store_posting_async`):**
1. Replace `location=posting_data.location` with three lines:
   ```python
   location_country=posting_data.location.country,
   location_city=posting_data.location.city,
   location_region=posting_data.location.region,
   ```
2. In the requirements-loop, rename `category=req.category.value` → `skill_type=req.skill_type.value` and add `skill_category=derive_skill_category(req.skill_type).value`. Need new import: `from job_rag.models import derive_skill_category`.

T-03-04 mitigation note (`services/ingestion.py:228-233`): the comment explicitly says "Field mapping mirrors the sync helper exactly (T-03-04 mitigation — drift would surface as Pydantic/SQLAlchemy errors)." Phase 2 must keep both helpers in lockstep.

---

### `src/job_rag/services/matching.py` (rename `req.category` → `req.skill_type`)

**Primary analog:** self.

**Targeted change** — current code (line 90 in `match_posting`, line 140-145 in `aggregate_gaps`) does NOT actually read `req.category` (it reads `req.skill` and `req.required`). So the matching service may need NO change for Phase 2. **Verify during planning:**

`services/matching.py:78-121` — `match_posting` body reads `r.skill`, `r.required` only:
```python
must_have = [r for r in posting.requirements if r.required]
nice_to_have = [r for r in posting.requirements if not r.required]
matched_must = [r.skill for r in must_have if _skill_matches(user_skills, r.skill)]
```

**Action for the planner:** grep `services/matching.py` for `\.category\b`. If no hits, this file is **untouched** by Phase 2 (CONTEXT.md D-05 over-listed it in the "files to modify" list). If a hit exists, rename to `.skill_type` (one-line edit). Re-validate alias-group matching works against the renamed enum values (no value changes — the rename is attribute-only).

---

### `src/job_rag/services/retrieval.py` (rename reads + RAG f-string)

**Primary analog:** self.

**Current f-string in `rag_query`** (`services/retrieval.py:205-212`):
```python
context_parts.append(
    f"**{posting.title}** at **{posting.company}** "
    f"({posting.location}, {posting.remote_policy})\n"
    f"Seniority: {posting.seniority}\n"
    f"Must-have: {', '.join(must_have)}\n"
    f"Nice-to-have: {', '.join(nice_to_have)}\n"
    f"Responsibilities: {posting.responsibilities}\n"
)
```

**Phase 2 change:** replace `{posting.location}` with a composed location string. Two options:
1. Inline computation: `{', '.join(filter(None, [posting.location_city, posting.location_country, posting.location_region]))}`
2. Helper function on the model. CONTEXT.md gives no preference; RESEARCH.md mentions "the RAG f-string at line 206-207" without prescribing the resolution. Recommend a small helper in retrieval.py (e.g., `_format_location(p) -> str`) to keep the f-string readable.

**Same `req.category` consideration as matching.py** — grep `services/retrieval.py` for `\.category\b`. If no hits, this file's only Phase 2 change is the `posting.location` removal. If hits exist, rename.

---

### `src/job_rag/mcp_server/tools.py` — `_serialize_posting` (emit both fields)

**Primary analog:** self (`tools.py:27-44`).

**Current serialization** (`mcp_server/tools.py:27-44`):
```python
def _serialize_posting(posting: JobPostingDB) -> dict[str, Any]:
    """Convert a JobPostingDB row into a JSON-serializable summary."""
    must_have = [r.skill for r in posting.requirements if r.required]
    nice_to_have = [r.skill for r in posting.requirements if not r.required]
    return {
        "id": str(posting.id),
        "title": posting.title,
        "company": posting.company,
        "location": posting.location,
        "remote_policy": posting.remote_policy,
        "seniority": posting.seniority,
        "salary_min": posting.salary_min,
        "salary_max": posting.salary_max,
        "salary_raw": posting.salary_raw,
        "must_have": must_have,
        "nice_to_have": nice_to_have,
        "source_url": posting.source_url,
    }
```

**Phase 2 changes:**
1. Replace `"location": posting.location` with a structured `"location": {"country": posting.location_country, "city": posting.location_city, "region": posting.location_region}` — matches the new Pydantic submodel shape.
2. The `must_have` / `nice_to_have` lists currently emit `r.skill` only — keep that, but consider whether the dashboard (Phase 5) consumer needs `skill_type` and `skill_category` per requirement. CONTEXT.md "tools.py: emit both skill_type and skill_category" suggests yes — change `must_have = [r.skill ...]` to `must_have = [{"skill": r.skill, "skill_type": r.skill_type, "skill_category": r.skill_category} for r in posting.requirements if r.required]` (or similar). Planner picks the exact JSON shape; downstream MCP consumer is just Adrian via Claude Code in v1 (CONTEXT.md), so no API contract to break.

---

### `src/job_rag/api/app.py` — lifespan extension (drift check)

**Primary analog:** self (existing `lifespan` function, lines 44-92).

**Existing lifespan structure** (`api/app.py:44-92`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """App lifespan: preload reranker, init drain primitives, dispose DB."""
    log.info("lifespan_startup_begin")

    # 1. Preload the cross-encoder model (~80MB, blocks ~2-3s) [D-27, BACK-03]
    _get_reranker()
    log.info("reranker_preloaded")

    # 2. Create app-wide shutdown event for SSE handlers to observe [D-17]
    app.state.shutdown_event = anyio.Event()

    # 3. Track all in-flight SSE handler tasks for cooperative drain [D-17]
    app.state.active_streams = set()

    log.info("lifespan_startup_complete")
    yield

    # --- shutdown [D-17] ---
    ...
```

**Phase 2 insertion** — add a NEW step between "reranker_preloaded" and the drain primitives (RESEARCH.md §Pattern 4 lines 803-844):
```python
# 1. Preload the cross-encoder model (UNCHANGED)
_get_reranker()
log.info("reranker_preloaded")

# 2. Drift check (NEW — Phase 2 D-17). One-shot SELECT; if any rows
#    returned, emit a structured warning. Does NOT block startup on
#    error (best-effort observability).
try:
    async with AsyncSessionLocal() as session:
        stmt = text(
            "SELECT prompt_version, COUNT(*) AS n "
            "FROM job_postings "
            "WHERE prompt_version != :current "
            "GROUP BY prompt_version"
        )
        result = await session.execute(stmt, {"current": PROMPT_VERSION})
        stale_rows = result.all()
        if stale_rows:
            stale_summary = {row.prompt_version: row.n for row in stale_rows}
            log.warning(
                "prompt_version_drift",
                stale_count=sum(stale_summary.values()),
                stale_by_version=stale_summary,
                current=PROMPT_VERSION,
                remediation="run `job-rag reextract` to re-extract stale rows",
            )
        else:
            log.info("prompt_version_check_clean", current=PROMPT_VERSION)
except Exception as e:
    log.warning("prompt_version_check_failed", error=str(e))

# 3. Drain primitives (UNCHANGED — Phase 1 D-17)
app.state.shutdown_event = anyio.Event()
app.state.active_streams = set()
```

**New imports needed** at module top:
- `from sqlalchemy import text`
- `from job_rag.db.engine import AsyncSessionLocal` (already implicit via routes; add explicit import)
- `from job_rag.extraction.prompt import PROMPT_VERSION`

**Best-effort observability convention** — wrap in `try/except` and log the failure as `log.warning(...)`, do NOT re-raise. This matches the "fail-open observability" convention from CLAUDE.md §Error Handling and the existing pattern of `lifespan` startup not crashing on observability hiccups.

---

### `tests/test_models.py` (extend with Location + skill_type + skill_category tests)

**Primary analog:** self (`TestJobRequirement` lines 16-30, `TestJobPosting` lines 33-109).

**Test class pattern** (`tests/test_models.py:16-30`):
```python
class TestJobRequirement:
    def test_valid_requirement(self):
        req = JobRequirement(skill="Python", category=SkillCategory.LANGUAGE, required=True)
        assert req.skill == "Python"
        assert req.category == SkillCategory.LANGUAGE
        assert req.required is True

    def test_nice_to_have(self):
        req = JobRequirement(skill="Kubernetes", category=SkillCategory.TOOL, required=False)
        assert req.required is False

    def test_all_categories(self):
        for cat in SkillCategory:
            req = JobRequirement(skill="test", category=cat, required=True)
            assert req.category == cat
```

For Phase 2, add three new test classes following this template:
1. `TestSkillType` — exercise the renamed enum (8 values, same as existing `TestJobRequirement::test_all_categories`).
2. `TestSkillCategoryDerivation` — exercise `derive_skill_category(skill_type)` against all 8 inputs, asserting 3 outputs.
3. `TestLocation` — round-trip Location with various combinations of nullable fields (the 4 D-09 mapping examples).

**Validation-error pattern** (`tests/test_models.py:81-94`):
```python
def test_missing_required_field_raises(self):
    with pytest.raises(ValidationError):
        JobPosting(
            title="Test",
            # missing company
            ...
        )
```

For Phase 2, add a similar test that creates a `JobRequirement` without `skill_type` and asserts `ValidationError`.

**Existing tests that NEED MIGRATION:**
- `TestJobRequirement::test_valid_requirement` — currently uses `category=SkillCategory.LANGUAGE`; rename to `skill_type=SkillType.LANGUAGE`.
- `TestJobPosting::test_valid_posting` etc. — use `location="Berlin, Germany"` literal; replace with `location=Location(country="DE", city="Berlin", region=None)`.
- `TestJobRequirement::test_all_categories` — iterates over `SkillCategory`; rename to iterate over `SkillType`.

---

### `tests/test_extraction.py` (extend with prompt-structure + rejection tests)

**Primary analog:** self (`TestExtractPosting` lines 28-73).

**Existing prompt_version assertion** (`tests/test_extraction.py:72-73`):
```python
def test_prompt_version_is_set(self):
    assert PROMPT_VERSION == "1.1"
```

For Phase 2, update to `assert PROMPT_VERSION == "2.0"`.

**Mock-based extract test pattern** (`tests/test_extraction.py:29-70`):
```python
def test_extract_returns_posting_and_usage(self, sample_raw_text: str):
    mock_posting = JobPosting(
        title="Senior AI Engineer",
        company="TestCorp",
        location="Berlin, Germany",
        ...
    )

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 500
    mock_usage.completion_tokens = 200

    mock_completion = MagicMock()
    mock_completion.usage = mock_usage

    with patch("job_rag.extraction.extractor.instructor") as mock_instructor:
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client
        mock_client.chat.completions.create_with_completion.return_value = (
            mock_posting,
            mock_completion,
        )

        posting, usage_info = extract_posting(sample_raw_text)
        ...
```

For Phase 2 NEW tests:
- `TestPromptStructure::test_rejected_terms_in_system_prompt` — `assert "communication" in SYSTEM_PROMPT`, `assert "ownership" in SYSTEM_PROMPT`. Verifies `str.format()` interpolation worked.
- `TestPromptStructure::test_location_examples_in_system_prompt` — `assert "DE" in SYSTEM_PROMPT`, `assert "Berlin" in SYSTEM_PROMPT`. Verifies the four D-09 examples landed.
- `TestRejectionRulesUnit` — mock `instructor.from_openai` to return a posting with rejected terms; assert post-extraction shape (the LLM is mocked, so this only verifies our code-level handling, not the LLM's actual rejection — the unit test confirms we don't filter post-hoc).
- `TestRejectionRulesLive` — optional integration test (skipped if `OPENAI_API_KEY` unset) hitting real LLM with a "communication-heavy" posting and asserting `communication` is NOT in extracted skills.

---

### `tests/test_alembic.py` (extend with 0004 upgrade/downgrade smoke)

**Primary analog (in-tree):** `tests/test_alembic.py::test_no_default_uuid_on_user_id_columns` (lines 27-43) — filesystem scan of `alembic/versions/`.

**No precedent in-tree for an actual upgrade/downgrade smoke against a real Postgres.** RESEARCH.md does not provide a direct recipe; the planner needs to:
1. Use a fixture that spins up a Postgres test instance (or relies on docker-compose's postgres service).
2. Run `command.upgrade(cfg, "0003")` to stamp at pre-Phase-2 state.
3. Insert sample rows with the OLD schema (`category` column, `location` column).
4. Run `command.upgrade(cfg, "0004")`.
5. Assert: row count unchanged in `job_requirements`, `skill_type` column exists with old data, `skill_category` column populated by SQL CASE backfill, `location` column dropped, `location_country/city/region` columns exist (NULL).
6. Run `command.downgrade(cfg, "0003")`.
7. Assert: schema reverts.

**Filesystem-scan pattern** (`tests/test_alembic.py:27-43`) — keep this existing test as-is; Phase 2 adds NEW test functions in the same file.

**Pattern from `tests/test_cli.py:18-43`** (skip-on-import-failure for in-progress migrations):
```python
class TestInitDbCommand:
    def test_init_db_invokes_alembic_upgrade(self):
        try:
            from job_rag.cli import app as cli_app
        except ImportError:
            pytest.skip("CLI import failed - confirm job_rag.cli exports Typer app")

        try:
            with patch("job_rag.db.engine.command.upgrade") as mock_upgrade:
                result = runner.invoke(cli_app, ["init-db"])
        except (AttributeError, ModuleNotFoundError):
            pytest.skip("alembic.command not yet imported in db/engine.py (Plan 02)")
        ...
```

For Phase 2's upgrade/downgrade smoke: use `pytest.skip(...)` if no Postgres is reachable, so the test passes locally without docker-compose running.

---

### `tests/test_reextract.py` (NEW — async + monkeypatch)

**Primary analog:** `tests/test_ingestion.py::TestIngestFromSource` (lines 73-237).

**Async + monkeypatch + AsyncMock pattern** (`tests/test_ingestion.py:117-171`):
```python
async def test_ingest_from_source_roundtrip(
    self, tmp_path, ingestion_module, monkeypatch
):
    if not hasattr(ingestion_module, "ingest_from_source"):
        pytest.skip("ingest_from_source not yet added (Plan 03)")

    from unittest.mock import AsyncMock, MagicMock

    # ... setup files ...

    async def _exists(*args, **kwargs):
        return False

    store_calls = {"n": 0}

    async def _store(session, posting, c_hash, linkedin_id):
        store_calls["n"] += 1
        db = MagicMock()
        db.id = f"posting-{store_calls['n']}"
        return db

    async def _embed(session, db_posting):
        return None

    monkeypatch.setattr(ingestion_module, "_posting_exists_async", _exists)
    monkeypatch.setattr(ingestion_module, "_store_posting_async", _store)
    monkeypatch.setattr(ingestion_module, "_embed_and_store_async", _embed)
    monkeypatch.setattr(
        ingestion_module,
        "extract_posting",
        lambda raw: (self._make_posting(), {"cost_usd": 0.001}),
    )

    async_session = MagicMock()
    async_session.commit = AsyncMock()
    async_session.rollback = AsyncMock()

    src = ingestion_module.MarkdownFileSource(tmp_path)
    result = await ingestion_module.ingest_from_source(async_session, src)

    assert result.total == 2
    assert result.ingested == 2
    ...
```

**Test class structure pattern** (`tests/test_ingestion.py:73-82`):
```python
@pytest.mark.asyncio
class TestIngestFromSource:
    """ingest_from_source unit tests — DB layer + LLM mocked."""

    @staticmethod
    def _make_posting():
        """Minimal valid JobPosting for mock extraction returns."""
        from job_rag.models import (
            JobPosting,
            JobRequirement,
            ...
        )
        return JobPosting(...)
```

**For `tests/test_reextract.py`:**
- `@pytest.mark.asyncio` class.
- `_make_posting()` static method using the NEW `Location` submodel + `skill_type`/`skill_category` shape.
- Monkeypatch `extract_posting` (from `services.extraction` import path), `AsyncSessionLocal` (factory), and any DB helpers. The `--dry-run` test asserts `report.skipped == N` and no UPDATE calls.
- Idempotency test: run `reextract_stale` twice, assert second run reports `selected == 0`.
- Partial-failure test: have the mocked `extract_posting` raise on the second posting; assert `report.succeeded == 1`, `report.failed == 1`, loop continued.
- Single-posting test: `reextract_stale(posting_id=UUID(...))` selects exactly 1 row.

---

### `tests/test_lifespan.py` (extend with drift-check test)

**Primary analog:** self (`TestLifespanStartup` lines 28-76, `lifespan_manager` fixture lines 16-25).

**Lazy-import + skip-on-missing fixture pattern** (`tests/test_lifespan.py:16-25`):
```python
@pytest.fixture
def lifespan_manager():
    """Lazy-import asgi-lifespan so this file collects even if the dev dep
    install hasn't happened yet on the runner."""
    try:
        from asgi_lifespan import LifespanManager

        return LifespanManager
    except ImportError as e:
        pytest.skip(f"asgi-lifespan not available: {e}")
```

**Async lifespan test pattern** (`tests/test_lifespan.py:30-55`):
```python
@pytest.mark.asyncio
class TestLifespanStartup:
    async def test_reranker_preloaded(self, lifespan_manager):
        from unittest.mock import patch

        try:
            from job_rag.api.app import app
        except ImportError as e:
            pytest.skip(f"api/app.py not yet wired (Plan 05): {e}")

        try:
            patcher = patch("job_rag.api.app._get_reranker")
            mock_load = patcher.start()
        except AttributeError:
            pytest.skip("_get_reranker not yet exposed in api/app.py (Plan 05)")
        try:
            async with lifespan_manager(app):
                mock_load.assert_called_once()
        finally:
            patcher.stop()
```

**For Phase 2 NEW test (or new file `tests/test_lifespan.py` extension):**
Add a `TestPromptVersionDriftCheck` class following the same pattern:
- Patch `AsyncSessionLocal` (or set up a real test DB) so the `SELECT prompt_version, COUNT(*)` returns a stale row.
- Use `caplog` (pytest fixture) to capture structlog output.
- Assert `prompt_version_drift` event was logged at WARNING level with `stale_count` key.
- Second test: clean state (no stale rows) — assert `prompt_version_check_clean` event was logged at INFO level.

---

### `tests/test_cli.py` (extend with `TestListStatsPromptVersion`)

**Primary analog:** self (`TestInitDbCommand` lines 18-43).

**CliRunner pattern** (`tests/test_cli.py:13-15`):
```python
from typer.testing import CliRunner

runner = CliRunner()
```

**Invoke + result.exit_code pattern** (`tests/test_cli.py:33-43`):
```python
try:
    with patch("job_rag.db.engine.command.upgrade") as mock_upgrade:
        result = runner.invoke(cli_app, ["init-db"])
except (AttributeError, ModuleNotFoundError):
    pytest.skip("alembic.command not yet imported in db/engine.py (Plan 02)")
if mock_upgrade.call_count == 0:
    pytest.skip("init_db not yet swapped to alembic command (Plan 02 provides it)")
assert result.exit_code == 0
mock_upgrade.assert_called_once()
```

**For Phase 2:**
```python
class TestListStatsPromptVersion:
    def test_list_stats_prints_distribution(self, monkeypatch):
        from job_rag.cli import app as cli_app

        # Patch SessionLocal to return a session with two postings
        # at different prompt_versions
        ...
        result = runner.invoke(cli_app, ["list", "--stats"])
        assert result.exit_code == 0
        assert "prompt_version=" in result.stdout
        assert "STALE" in result.stdout  # at least one stale row
```

---

### `tests/conftest.py` (update sample_posting fixture)

**Primary analog:** self (`sample_posting` fixture lines 24-55).

**Existing fixture** (`tests/conftest.py:24-55`):
```python
@pytest.fixture
def sample_posting() -> JobPosting:
    return JobPosting(
        title="Senior AI Engineer",
        company="TestCorp",
        location="Berlin, Germany",
        remote_policy=RemotePolicy.HYBRID,
        salary_min=70000,
        salary_max=90000,
        salary_raw="€70,000-€90,000/year",
        salary_period=SalaryPeriod.YEAR,
        seniority=Seniority.SENIOR,
        employment_type="Full-time",
        requirements=[
            JobRequirement(skill="Python", category=SkillCategory.LANGUAGE, required=True),
            JobRequirement(skill="LLM", category=SkillCategory.CONCEPT, required=True),
            ...
        ],
        ...
    )
```

**Phase 2 changes:**
1. Update import: `from job_rag.models import (JobPosting, JobRequirement, Location, RemotePolicy, SalaryPeriod, Seniority, SkillCategory, SkillType, ...)`.
2. Replace `location="Berlin, Germany"` with `location=Location(country="DE", city="Berlin", region=None)`.
3. Replace each `JobRequirement(..., category=SkillCategory.LANGUAGE, ...)` with `JobRequirement(skill="Python", skill_type=SkillType.LANGUAGE, skill_category=SkillCategory.HARD, required=True)` — or rely on a Pydantic `model_validator` if the planner adds one to auto-derive `skill_category`.

---

## Shared Patterns

### Structlog event-name convention
**Source:** Used throughout the codebase — `services/ingestion.py:327, 359, 365, 368`, `services/embedding.py:113, 138, 153`, `extraction/extractor.py:75`, `api/app.py:47, 51, 62-63, 66-69, 86-87, 92`.
**Apply to:** All new log calls in Phase 2 (extraction service, lifespan drift check, CLI reextract output).

```python
log.info("event_name_underscore_separated", key1=value1, key2=value2)
log.warning("event_name", reason="...", remediation="...")
log.error("event_name", error=str(e), context_key=context_value)
```

### Async-via-asyncio.run for sync entry points (CLI)
**Source:** `cli.py::agent` (lines 211-247).
**Apply to:** New `cli.py::reextract` subcommand. Wrap `await reextract_stale(...)` inside `async def _run()` then call `asyncio.run(_run())`.

### Per-iteration commit on batch async loops
**Source:** `services/ingestion.py::ingest_from_source` (lines 319-370).
**Apply to:** `services/extraction.py::reextract_stale`. Same `try/except + commit + rollback + continue` shape, with the **deviation** that each iteration uses a fresh `AsyncSession` (not the outer one) due to LLM-time-per-iteration concerns (RESEARCH.md Pitfall 5).

### LLM call pushed to thread (preserve event loop)
**Source:** `services/ingestion.py:336` — `posting, usage = await asyncio.to_thread(extract_posting, raw.raw_text)`.
**Apply to:** `services/extraction.py::_reextract_one` body — same call shape; `extract_posting` is the same sync function with `@retry` already applied.

### Module-top imports + `log = get_logger(__name__)` + module-level constants
**Source:** Every service module (`services/ingestion.py:1-22`, `services/retrieval.py:1-17`, `services/embedding.py:1-8`).
**Apply to:** New `services/extraction.py`. Module-top: stdlib imports → third-party imports (sqlalchemy, etc.) → first-party (`job_rag.*`) → blank line → `log = get_logger(__name__)`. No conditional imports inside functions unless the function-local import is for circular-dependency or expensive-import reasons (`observability.py` precedent).

### CLI command body convention (local imports + try/finally with session.close)
**Source:** Every command in `cli.py` does its dependencies via `function-local imports` (e.g., `cli.py:23-25`, `cli.py:48-50`, `cli.py:172-173`).
**Apply to:** New `reextract` command + extended `list --stats` branch.

```python
@app.command()
def some_cmd(...) -> None:
    """Docstring."""
    from job_rag.db.engine import SessionLocal
    from job_rag.db.models import JobPostingDB

    session = SessionLocal()
    try:
        ...  # work
    finally:
        session.close()
```

### Pydantic Field + description (LLM-visible via Instructor)
**Source:** `models.py:43-46, 51-71`.
**Apply to:** New `Location` submodel — every field MUST carry a `description="..."` because Instructor propagates Pydantic descriptions into the JSON Schema, which the LLM uses to ground its output (RESEARCH.md Pitfall 3).

### Type-hints everywhere; `X | None` not `Optional[X]`
**Source:** Repo-wide (CLAUDE.md `[tool.ruff.lint]` `UP` rule).
**Apply to:** All new code in Phase 2. `str | None` not `Optional[str]`. `dict[str, Any]` not `Dict[str, Any]`.

### Skip-on-import-error / hasattr pattern in tests
**Source:** `tests/test_lifespan.py:16-25, 39-50`, `tests/test_ingestion.py:18-23, 31-32, 122-124`, `tests/test_cli.py:23-39`.
**Apply to:** All new test classes in Phase 2 — gate on `try/except ImportError` for the modules under test, so the test suite stays green during incremental plan execution. Removes when Phase 2 fully lands.

```python
try:
    from job_rag.services.extraction import reextract_stale
except ImportError as e:
    pytest.skip(f"services/extraction.py not yet added: {e}")
```

---

## No Analog Found

No NEW pattern in Phase 2 lacks an in-tree analog at the file level. Two specific sub-patterns lack precedent:

| Pattern | File | Reason | Source to use |
|---------|------|--------|---------------|
| `op.alter_column(new_column_name=...)` (column rename) | `0004_corpus_cleanup.py` | No prior migration renames a column (`0001` creates, `0002` adds tables, `0003` adds column) | RESEARCH.md §Pattern 1 lines 360-369 (Alembic op reference) |
| `str.format()` template with single named placeholder | `extraction/prompt.py` | Current prompt is a plain literal — no formatting | RESEARCH.md §Pattern 2 lines 466-589 |
| Real DB upgrade/downgrade smoke against Postgres | `tests/test_alembic.py` | Existing test is a regex-based filesystem scan, not a live-DB smoke | No source — planner composes from `command.upgrade(cfg, "...")` (already used in `db/engine.py:58`) + a Postgres test fixture |
| Fresh-AsyncSession-per-iteration in a service loop | `services/extraction.py` | Existing `ingest_from_source` holds one outer session for the whole loop | RESEARCH.md §Pattern 3 lines 661-792 |

These four sub-patterns are the technical risk concentration of Phase 2 (per RESEARCH.md Summary line 9).

---

## Metadata

**Analog search scope:**
- `src/job_rag/**/*.py` (28 files)
- `alembic/versions/*.py` (3 files)
- `tests/**/*.py` (18 files)

**Files scanned:** 49

**Pattern extraction date:** 2026-04-27

**Files read in full or in part for analog excerpts:**
- `alembic/versions/0001_baseline.py`, `0002_add_user_profile.py`, `0003_add_career_id.py`
- `src/job_rag/models.py`, `db/models.py`, `db/engine.py`, `logging.py`
- `src/job_rag/extraction/prompt.py`, `extractor.py`
- `src/job_rag/services/ingestion.py`, `matching.py`, `retrieval.py`, `embedding.py`
- `src/job_rag/cli.py`, `mcp_server/tools.py`, `api/app.py`
- `tests/conftest.py`, `test_models.py`, `test_alembic.py`, `test_extraction.py`, `test_lifespan.py`, `test_ingestion.py`, `test_cli.py`
