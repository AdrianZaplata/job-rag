# Phase 7: Profile & Resume Upload — Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 28 new/modified files
**Analogs found:** 27 / 28 (1 file — `api/middleware.py` — has no direct prior analog; researched skeleton in RESEARCH.md §2)

This file maps every Phase 7 file (new or modified) to the closest existing analog in the codebase, with concrete code excerpts and line references the planner can paste into plan actions verbatim.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/job_rag/extraction/resume_extractor.py` | service (extraction) | request-response (sync, retry) | `src/job_rag/extraction/extractor.py` | exact |
| `src/job_rag/extraction/resume_prompt.py` | config (prompt constant) | static | `src/job_rag/extraction/prompt.py` | exact |
| `src/job_rag/services/profile.py` | service (pure compute) | transform | `src/job_rag/services/matching.py` (_normalize_skill helpers) | role-match |
| `src/job_rag/api/middleware.py` | middleware (ASGI) | request-response | *(no analog — single ASGI middleware not yet in repo; new file)* | none |
| `alembic/versions/0006_seed_user_profile.py` | migration (data seed) | one-shot | `alembic/versions/0005_adopt_entra_oid.py` | role-match (data vs schema, but idempotency helpers + revision chain identical) |
| `src/job_rag/services/matching.py` (modify `load_profile`) | service (DB read) | request-response (async DB) | self (current body) + Phase 5 D-06 dashboard async session pattern in `services/analytics.py` | exact (signature pre-built by Phase 1 D-07) |
| `src/job_rag/api/routes.py` (+POST /profile/upload, +PATCH /profile) | controller (HTTP) | file-I/O + CRUD | `src/job_rag/api/routes.py::ingest` (UploadFile) + `routes.py::match` (Depends pattern) | exact |
| `src/job_rag/models.py` (+ResumeExtraction) | model (Pydantic) | static schema | `models.py::UserSkillProfile` | exact |
| `src/job_rag/config.py` (+max_resume_size_bytes) | config | static | `config.py::agent_timeout_seconds` Field with ge=1 | exact |
| `src/job_rag/observability.py` (+get_langfuse_client) | utility (observability) | event-driven | `observability.py::get_openai_client` (lru_cache + fail-open) | exact |
| `pyproject.toml` (+pypdf, +python-docx) | config | static | existing `[project] dependencies` block | exact |
| `tests/test_profile.py` | test | unit + integration | `tests/test_matching.py` shape + `tests/test_extraction.py` mocking | exact |
| `tests/test_resume_extractor.py` | test | unit (mocked LLM) | `tests/test_extraction.py::TestExtractPosting` | exact |
| `tests/test_alembic.py` | test | migration | *(may be new; append-to-existing if present)* | partial |
| `tests/test_mcp_server.py` (modify mocks) | test | unit | existing patches at `:126, :164` | self-edit |
| `tests/test_analytics.py` (modify mocks) | test | unit | existing monkeypatch at `:357, :378, :403, :417` | self-edit |
| `tests/conftest.py` (+ fixtures) | test fixture | static | `conftest.py::sample_raw_text` (file-read fixture) | exact |
| `tests/test_observability.py` (+ trace tests) | test | unit | existing observability tests | partial |
| `frontend/src/components/profile/ProfileView.tsx` | component (presentation) | request-response (read) | `frontend/src/components/dashboard/TopSkillsCard.tsx` (Card + Skeleton + EmptyState + Alert pattern) | exact |
| `frontend/src/components/profile/ResumeUploader.tsx` | component (input) | file-I/O | `frontend/src/components/chat/ChatComposer.tsx` (sticky input + Button) | role-match |
| `frontend/src/components/profile/ReviewPanel.tsx` | component (composite) | request-response | `frontend/src/components/dashboard/TopSkillsCard.tsx` (Card+Footer) + Phase 6 `ChatTranscript.tsx` (list rendering) | exact |
| `frontend/src/components/profile/SkillDiffChip.tsx` | component (atom) | local state | shadcn Badge + Input usage in dashboard/chat | partial |
| `frontend/src/components/profile/useResumeUpload.ts` | hook (state machine) | request-response (mutation) | `frontend/src/components/chat/useChatStream.ts` (state owner, AbortController) | role-match (mutation vs stream) |
| `frontend/src/components/profile/types.ts` | type module | static | `frontend/src/components/chat/types.ts`, `frontend/src/components/dashboard/useDashboardFilters.ts` | exact |
| `frontend/src/components/profile/*.test.tsx` | test | vitest+RTL | `frontend/src/components/dashboard/__tests__/*` + `useDashboardFilters.test.tsx` | exact |
| `frontend/src/routes/Profile.tsx` (replace placeholder) | route (page) | composition | `frontend/src/routes/Dashboard.tsx` + `Chat.tsx` (route uses feature folder) | exact |
| `frontend/src/api/profile.ts` (fill stub) | api client | request-response | `frontend/src/api/jobs.ts` (typed service module) | exact |
| `frontend/src/api/types.ts`, `frontend/openapi.snapshot.json` | codegen output | static | regenerated via `npm run codegen:snapshot && npm run codegen` (Phase 4 D-14) | exact |
| `data/README.md` | docs | static | *(new tiny doc; ~10 lines)* | n/a |

---

## Pattern Assignments

### 1. `src/job_rag/extraction/resume_extractor.py` (NEW, service-extraction, request-response)

**Analog:** `src/job_rag/extraction/extractor.py` (lines 1-83, full file)
**Match:** EXACT — Instructor + tenacity + structured-output + usage_info return tuple

**Imports pattern** (lines 1-12):
```python
import re

import instructor
from tenacity import retry, stop_after_attempt, wait_exponential

from job_rag.config import settings
from job_rag.extraction.prompt import PROMPT_VERSION, SYSTEM_PROMPT
from job_rag.logging import get_logger
from job_rag.models import JobPosting
from job_rag.observability import get_openai_client

log = get_logger(__name__)
```

**Core pattern — @retry decorator + Instructor call** (lines 36-83):
```python
@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def extract_posting(raw_text: str) -> tuple[JobPosting, dict]:
    """Extract structured data from a job posting using Instructor.

    Returns a tuple of (JobPosting, usage_info) where usage_info contains
    token counts and cost.
    """
    client = instructor.from_openai(get_openai_client())

    posting, completion = client.chat.completions.create_with_completion(
        model=settings.openai_model,
        response_model=JobPosting,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                "<job_posting>\n"
                f"{_sanitize_delimiters(raw_text)}\n"
                "</job_posting>"
            )},
        ],
    )

    usage = completion.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    cost = _compute_cost(settings.openai_model, prompt_tokens, completion_tokens)

    usage_info = {
        "model": settings.openai_model,
        "prompt_version": PROMPT_VERSION,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": cost,
    }
    log.info("extraction_complete", company=posting.company, ..., **usage_info)
    return posting, usage_info
```

**Phase 7 application:** Copy verbatim. Replace `extract_posting` → `extract_resume`, `JobPosting` → `ResumeExtraction`, `SYSTEM_PROMPT` → `RESUME_SYSTEM_PROMPT`, `PROMPT_VERSION` → `RESUME_PROMPT_VERSION`. Drop the `<job_posting>` delimiter (resume text has no injection-prone tag; D-15 doesn't mention sanitisation). Keep the `tuple[ResumeExtraction, dict]` return — usage_info feeds the Langfuse `llm_extract` span metadata.

**RESEARCH skeleton:** lines 113-147 of `07-RESEARCH.md` shows the exact target shape — use that as the literal scaffold.

---

### 2. `src/job_rag/extraction/resume_prompt.py` (NEW, config-constant)

**Analog:** `src/job_rag/extraction/prompt.py` (lines 1-142, full file)
**Match:** EXACT — `PROMPT_VERSION` + reject list import + str.format() template

**Versioning pattern** (lines 22-27, 137-141):
```python
PROMPT_VERSION = "2.0"

# D-18: conservative ~22-term reject list. Lowercase canonical forms; LLM is
# instructed to compare case-insensitively in the prompt below.
REJECTED_SOFT_SKILLS: tuple[str, ...] = (
    "communication",
    "teamwork",
    ...
)

# ... template definition ...

SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(
    rejected_terms=", ".join(REJECTED_SOFT_SKILLS),
)
```

**Phase 7 application:** Add `RESUME_PROMPT_VERSION = "1.0"` (D-12). REUSE `REJECTED_SOFT_SKILLS` via import (D-14: `from job_rag.extraction.prompt import REJECTED_SOFT_SKILLS`). New template focuses on resume-specific carve-outs: spoken languages (English/German/Polish per D-14), structured-output schema mapping to `ResumeExtraction` fields. Build final `RESUME_SYSTEM_PROMPT` via the same `_TEMPLATE.format(rejected_terms=", ".join(REJECTED_SOFT_SKILLS))` pattern (no f-string — same brace-doubling caveat applies if any literal `{...}` examples are added; see Phase 2 D-19 / Pitfall 4 callout in `prompt.py:53-60`).

---

### 3. `src/job_rag/services/profile.py` (NEW, service-pure-compute)

**Analog:** `src/job_rag/services/matching.py` (lines 38-40, `_normalize_skill`)
**Match:** ROLE-MATCH — both are pure-Python skill-comparison helpers in services/

**Normalization helper** (matching.py:38-40):
```python
def _normalize_skill(name: str) -> str:
    """Normalize skill name for fuzzy matching."""
    return name.lower().strip().replace("-", " ").replace("_", " ")
```

**Phase 7 application:** Import `_normalize_skill` from `job_rag.services.matching` (D-20). `compute_skills_diff` is the new pure helper — see RESEARCH.md §8 lines 366-403 for the canonical implementation. Pydantic `SkillDiffItem` model co-located in this module (D-17). Module shape mirrors `matching.py`: top-level helpers + pure synchronous diff function (no I/O, no DB access). Logger import via `get_logger(__name__)` matching matching.py:11.

**Canonical implementation** (from 07-RESEARCH.md lines 366-398):
```python
class SkillDiffItem(BaseModel):
    name: str
    source: Literal["added", "removed", "unchanged"]
    editable: bool


def compute_skills_diff(
    current: UserSkillProfile, extracted_skills: list[UserSkill]
) -> list[SkillDiffItem]:
    current_map = {_normalize_skill(s.name): s.name for s in current.skills}
    extracted_map = {_normalize_skill(s.name): s.name for s in extracted_skills}
    cur_keys = set(current_map); ext_keys = set(extracted_map)
    added = sorted(extracted_map[k] for k in (ext_keys - cur_keys))
    removed = sorted(current_map[k] for k in (cur_keys - ext_keys))
    unchanged = sorted(extracted_map[k] for k in (ext_keys & cur_keys))
    return [
        *(SkillDiffItem(name=n, source="added", editable=True) for n in added),
        *(SkillDiffItem(name=n, source="removed", editable=False) for n in removed),
        *(SkillDiffItem(name=n, source="unchanged", editable=False) for n in unchanged),
    ]
```

---

### 4. `src/job_rag/api/middleware.py` (NEW, ASGI middleware)

**Analog:** NONE in repo — the project currently has no Starlette `BaseHTTPMiddleware` subclass. CORS is wired via `CORSMiddleware` directly in `api/app.py` (factory pattern). The closest reference is the `RateLimiter` class in `api/auth.py:101-131` (callable-style dep, not BaseHTTPMiddleware, but conceptually similar request-inspection pre-handler).

**RateLimiter reference for callable-class pattern** (auth.py:101-123):
```python
class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, calls: int, period: int) -> None:
        self.calls = calls
        self.period = period
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = [t for t in self._requests[client_ip] if now - t < self.period]
        if len(window) >= self.calls:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        window.append(now)
        self._requests[client_ip] = window
```

**Phase 7 application:** Per RESEARCH.md §2 lines 62-77, the new middleware mounts on the app (in `api/app.py`) BEFORE the router. It MUST be a `BaseHTTPMiddleware` subclass (not a dep) so the 413 fires before any UploadFile body materialization — Phase 4 dep-style guards run AFTER FastAPI has already streamed the body into memory, which would violate REQ-PROF-02 "before the body is fully read".

**Canonical implementation** (RESEARCH.md §2):
```python
# src/job_rag/api/middleware.py (NEW)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from job_rag.config import settings


class ResumeUploadSizeGuard(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/profile/upload" and request.method == "POST":
            cl = request.headers.get("content-length")
            if cl is not None and int(cl) > settings.max_resume_size_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": {"reason": "file_too_large",
                                        "message": "Resume must be ≤2 MB."}},
                )
        return await call_next(request)
```

Wire in `api/app.py` next to existing `CORSMiddleware`: `app.add_middleware(ResumeUploadSizeGuard)`. Order matters — add ABOVE CORS so OPTIONS preflight from the browser still flows through CORS even for the upload route.

---

### 5. `alembic/versions/0006_seed_user_profile.py` (NEW, data migration)

**Analog:** `alembic/versions/0005_adopt_entra_oid.py` (lines 1-110, full file)
**Match:** ROLE-MATCH — 0005 is schema, 0006 is data; revision chain + idempotency helpers + downgrade symmetry pattern identical

**Revision header pattern** (0005, lines 31-48):
```python
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Phase 1 D-08 invariant: this canonical UUID MUST match config.py
# settings.seeded_user_id ...
# Migrations do NOT import from job_rag.config — keep as a literal constant here.
SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"
```

**Idempotency helpers pattern** (0005, lines 51-71):
```python
def _has_column(conn: sa.engine.Connection, table: str, column: str) -> bool:
    """Idempotency helper — check information_schema for column presence."""
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ).bindparams(t=table, c=column)
        ).first()
    )
```

**Upgrade/downgrade symmetry** (0005, lines 74-109):
```python
def upgrade() -> None:
    """Upgrade schema to Phase 4 shape."""
    conn = op.get_bind()
    if not _has_column(conn, "users", "entra_oid"):
        op.add_column("users", sa.Column("entra_oid", sa.String(255), nullable=True))
    # ... more idempotent steps ...


def downgrade() -> None:
    """Reverse — drop the partial unique index."""
    conn = op.get_bind()
    if _has_index(conn, "ix_users_entra_oid_unique"):
        op.drop_index("ix_users_entra_oid_unique", table_name="users")
```

**Phase 7 application:** Use `revision = "0006"`, `down_revision = "0005"`. For data idempotency, the analog is `ON CONFLICT (user_id) DO NOTHING` rather than a helper function (PG-supported on both PG16 prod and PG17 dev). Embed `data/profile.json` as Python dict literal per D-03 (the file IS gitignored at container layer — runtime file-read would crash on fresh ACA boot per RESEARCH.md §5 "Why embed the dict literal vs read data/profile.json"). Canonical skeleton in RESEARCH.md lines 210-261.

---

### 6. `src/job_rag/services/matching.py` — modify `load_profile()` (signature + body)

**Analog:** SELF (current body lines 14-35) + `services/analytics.py::_compute_cv_vs_market` pattern (referenced in RESEARCH.md §4 table)
**Match:** EXACT — Phase 1 D-07 pre-built the kwarg-only signature as the forward hook

**Current body** (matching.py:14-35):
```python
def load_profile(
    *, user_id: UUID | None = None, path: str | None = None,
) -> UserSkillProfile:
    """Load user skill profile.

    Phase 1 (v1): reads ``data/profile.json`` regardless of ``user_id`` —
    the parameter is accepted for forward compatibility with Phase 7
    (PROF-01), which will flip the source to the ``user_profile`` DB table
    keyed by ``user_id``. [D-07]
    """
    if user_id is None:
        user_id = settings.seeded_user_id
    profile_path = Path(path or settings.profile_path)
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    return UserSkillProfile(**data)
```

**Phase 7 application:** Body-flip per RESEARCH.md §4 lines 172-201. New signature: `async def load_profile(session: AsyncSession, *, user_id: UUID | None = None) -> UserSkillProfile`. Drop `path` kwarg (Phase 1 D-07 hook, no production caller). Updates 5 call sites:

| File | Line | Caller context |
|------|------|----------------|
| `src/job_rag/api/routes.py` | 192 | `/match/{posting_id}` (already async, has `session: Session` dep) |
| `src/job_rag/api/routes.py` | 216 | `/gaps` (already async, has `session: Session` dep) |
| `src/job_rag/mcp_server/tools.py` | 121 | `match_skills` (already opens `async with AsyncSessionLocal() as session:`) |
| `src/job_rag/mcp_server/tools.py` | 147 | `skill_gaps` (same) |
| `src/job_rag/services/analytics.py` | 295 | `_compute_cv_vs_market` (already async, takes session param) |

All 5 use `await load_profile(session, user_id=...)` — no signature break since all callers already have a session in scope. Pattern from routes.py:192 (current sync call):
```python
profile = load_profile(user_id=user_id)
```
becomes:
```python
profile = await load_profile(session, user_id=user_id)
```

---

### 7. `src/job_rag/api/routes.py` (modify) — POST /profile/upload + PATCH /profile

**Analog:** `src/job_rag/api/routes.py::ingest` (lines 477-528) for UploadFile + dep stack; `routes.py::match` (lines 171-193) for the Depends pattern with `get_current_user_id`
**Match:** EXACT — same router, same dep stack pattern

**Upload route Depends pattern** (routes.py:477-503, `/ingest`):
```python
@router.post("/ingest", dependencies=[Depends(require_api_key), Depends(ingest_limit)])
async def ingest(
    file: UploadFile,
    session: Session,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
) -> dict[str, Any]:
    """Ingest a single job posting markdown file via the async pipeline."""
    _ = user_id  # reserved for Phase 7 — accepted via Depends so multi-tenancy wiring is in place
    MAX_UPLOAD_BYTES = 1_000_000  # 1 MB
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 1 MB)")
```

**GET-style profile read pattern** (routes.py:171-193, `/match`):
```python
@router.get(
    "/match/{posting_id}",
    dependencies=[Depends(require_api_key), Depends(standard_limit)],
)
async def match(
    session: Session,
    posting_id: str,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
) -> dict[str, Any]:
    """Match a specific posting against the user profile."""
    stmt = (select(JobPostingDB).filter(JobPostingDB.id == posting_id)...)
    result = await session.execute(stmt)
    posting = result.scalar_one_or_none()
    if not posting:
        raise HTTPException(status_code=404, detail="Posting not found")
    profile = load_profile(user_id=user_id)  # post-Phase-7: await load_profile(session, user_id=...)
    return match_posting(profile, posting)
```

**Error-detail dict pattern** (routes.py:444-453, `_sanitize` + ErrorEvent — D-19 sanitization rule applies to backend error messages exposed via SSE; Phase 7 D-35 uses HTTPException detail dict instead of SSE error envelope):
```python
except Exception as e:
    yield to_sse(ErrorEvent(type="error", reason="internal", message=_sanitize(e)))
```

**Phase 7 application — POST /profile/upload** (uses `standard_limit` per D-06; structured `detail={reason, message}` per D-35; UploadFile + size-cap fallback for chunked encoding per RESEARCH.md §2 lines 87-99; calls `asyncio.to_thread(extract_resume, text)` per D-15; structured logging per D-35 `log.warning("resume_upload_failed", reason=..., ...)`).

**Phase 7 application — PATCH /profile** (per RESEARCH.md §7 lines 334-357):
```python
@router.patch("/profile", dependencies=[Depends(require_api_key), Depends(standard_limit)])
async def update_profile(
    session: Session,
    payload: UserProfileUpdate,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
) -> UserSkillProfile:
    updates: dict[str, Any] = {
        "skills_json": json.dumps([s.model_dump() for s in payload.skills]),
        "updated_at": func.now(),
    }
    if payload.target_roles is not None:
        updates["target_roles_json"] = json.dumps(payload.target_roles)
    # ... other optional fields ...
    stmt = update(UserProfileDB).where(UserProfileDB.user_id == user_id).values(**updates)
    await session.execute(stmt)
    await session.commit()
    return await load_profile(session, user_id=user_id)
```

---

### 8. `src/job_rag/models.py` (modify, +ResumeExtraction)

**Analog:** `src/job_rag/models.py::UserSkillProfile` (lines 147-158)
**Match:** EXACT — sibling Pydantic model in the same file

**UserSkillProfile shape** (models.py:147-158):
```python
class UserSkillProfile(BaseModel):
    """User's skill profile for matching against job postings."""

    skills: list[UserSkill] = Field(description="User skills")
    target_roles: list[str] = Field(default_factory=list, description="Target job titles")
    preferred_locations: list[str] = Field(default_factory=list, description="Preferred locations")
    min_salary: int | None = Field(
        default=None, description="Minimum acceptable salary in EUR/year"
    )
    remote_preference: RemotePolicy = Field(
        default=RemotePolicy.UNKNOWN, description="Preferred remote policy"
    )
```

**Phase 7 application** (D-13):
```python
class ResumeExtraction(BaseModel):
    """LLM-extracted resume contents (Phase 7 D-13). Sibling of UserSkillProfile
    that adds `years_experience` and is decoupled from the canonical user-state shape."""

    skills: list[UserSkill] = Field(description="Extracted user skills")
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    min_salary_eur: int | None = Field(default=None)
    remote_preference: RemotePolicy = Field(default=RemotePolicy.UNKNOWN)
    years_experience: int | None = Field(default=None)
```

Note: D-13 uses `min_salary_eur` (not `min_salary` like `UserSkillProfile`); the field-copy mapper called by the upload handler renames to match `UserSkillProfile` when diffing.

---

### 9. `src/job_rag/config.py` (modify, +max_resume_size_bytes)

**Analog:** `src/job_rag/config.py::agent_timeout_seconds` (lines 51-53)
**Match:** EXACT — same `Field(default=..., ge=N)` pattern with explanatory comment

**Existing pattern** (config.py:51-53):
```python
# ge=1 guards against env-misconfig (0 or negative) that would silently break
# asyncio.wait_for and sse-starlette's ping kwarg downstream (D-15, D-25).
agent_timeout_seconds: int = Field(default=60, ge=1)
heartbeat_interval_seconds: int = Field(default=15, ge=1)
```

**Phase 7 application** (D-07):
```python
# Phase 7 D-07: 2 MB cap on resume uploads. Enforced by the ASGI middleware
# in api/middleware.py BEFORE the body is materialized into memory (REQ-PROF-02
# literal "rejected with 413 before the body is fully read").
max_resume_size_bytes: int = Field(default=2_000_000, ge=1)
```

---

### 10. `src/job_rag/observability.py` (modify, +get_langfuse_client helper)

**Analog:** `src/job_rag/observability.py::get_openai_client` (lines 39-54)
**Match:** EXACT — same `@lru_cache(maxsize=1)` + fail-open + `_ensure_env()` pattern

**Existing pattern** (observability.py:24-54):
```python
def is_enabled() -> bool:
    """Langfuse is on iff both keys are set."""
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def _ensure_env() -> None:
    """Langfuse SDK reads from os.environ — mirror settings into it once."""
    if settings.langfuse_public_key:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    ...


@lru_cache(maxsize=1)
def get_openai_client() -> Any:
    """Return an OpenAI client, langfuse-wrapped when observability is enabled."""
    if is_enabled():
        _ensure_env()
        from langfuse.openai import OpenAI as LangfuseOpenAI
        log.info("openai_client_wrapped", provider="langfuse")
        return LangfuseOpenAI(api_key=settings.openai_api_key)
    import openai
    return openai.OpenAI(api_key=settings.openai_api_key)
```

**Phase 7 application** (RESEARCH.md §6 lines 274-285):
```python
@lru_cache(maxsize=1)
def get_langfuse_client() -> Any | None:
    """Return a raw Langfuse client for manual span/trace creation (Phase 7 D-32).

    Fail-open: returns None when keys are missing — all callers MUST guard with
    `if lf:` before usage (matches the existing pattern in get_langchain_callbacks)."""
    if not is_enabled():
        return None
    _ensure_env()
    from langfuse import Langfuse
    log.info("langfuse_client_initialized")
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
```

**PII redaction** (D-33) — additional guidance: post-process the auto-captured `llm_extract` span via `lf.update_current_observation(input=...)` to redact resume body. See RESEARCH.md §6 lines 324-329 for the canonical approach.

---

### 11. `pyproject.toml` (modify)

**Analog:** existing `[project] dependencies` block (current pinned-range style: `instructor`, `langgraph`, `pydantic`, etc.)
**Match:** EXACT — same pin style

**Phase 7 application** (D-09, REQ-PROF-02 literals):
```toml
"pypdf>=6,<7",
"python-docx>=1,<2",
```

After edit: `uv lock` to bump `uv.lock`. Done.

---

### 12. `tests/test_resume_extractor.py` (NEW)

**Analog:** `tests/test_extraction.py::TestExtractPosting` (lines 39-85) + `TestPromptStructure` (lines 87-136) + `TestRejectionRulesUnit` (lines 138-189)
**Match:** EXACT — same mock-Instructor pattern + prompt-content assertions + reject-list pass-through assertions

**Mock-Instructor pattern** (test_extraction.py:65-71):
```python
with patch("job_rag.extraction.extractor.instructor") as mock_instructor:
    mock_client = MagicMock()
    mock_instructor.from_openai.return_value = mock_client
    mock_client.chat.completions.create_with_completion.return_value = (
        mock_posting,
        mock_completion,
    )
    posting, usage_info = extract_posting(sample_raw_text)
    assert posting.company == "TestCorp"
    ...
    assert usage_info["prompt_version"] == PROMPT_VERSION
```

**Prompt-content assertions** (test_extraction.py:104-112, 114-121):
```python
def test_rejected_terms_in_system_prompt(self):
    for term in REJECTED_SOFT_SKILLS:
        assert term in SYSTEM_PROMPT, f"missing rejection term: {term!r}"

def test_borderline_and_spoken_language_carveouts(self):
    assert "leadership" in SYSTEM_PROMPT
    assert "English" in SYSTEM_PROMPT
    assert "German" in SYSTEM_PROMPT
```

**Phase 7 application:** Mirror exact class structure. `TestExtractResume::test_extract_returns_resume_extraction_and_usage` (with mocked Instructor returning `ResumeExtraction`). `TestResumePromptStructure::test_rejected_terms_in_system_prompt` (asserts REJECTED_SOFT_SKILLS terms appear in `RESUME_SYSTEM_PROMPT`) + `test_spoken_language_carveouts` (English/German/Polish appear). `TestExtractResume::test_retries_3x_then_raises` (mock `ValidationError` on every call — tenacity retries 3x then re-raises).

---

### 13. `tests/test_profile.py` (NEW)

**Analog:** `tests/test_matching.py` (shape) + `tests/test_extraction.py` (mocking) + multipart upload tests in `tests/test_api.py` (if present) for the 413/415/422 paths
**Match:** EXACT (mirror shape per D-36 + CONTEXT line 300 "test_profile.py mirrors tests/test_matching.py shape")

**Phase 7 application** — 7 test cases per D-36:
1. `test_upload_pdf_happy_path` — fixture PDF → 200 + non-empty `skills_diff`
2. `test_upload_docx_happy_path` — fixture DOCX → 200 + non-empty `skills_diff`
3. `test_upload_413_oversized_content_length` — set `Content-Length: 3_000_000` header + 1 KB body, assert 413 + handler NEVER invoked (use a sentinel; closes the D-36 gap flagged in RESEARCH.md §"Gap not covered by D-36")
4. `test_upload_415_txt_file` — `.txt` upload → 415 `{reason: "unsupported_file_type"}`
5. `test_upload_422_encrypted_pdf` — fixture `tests/fixtures/encrypted-sample.pdf` → 422 `pdf_encrypted`
6. `test_upload_422_empty_text_pdf` — image-only fixture → 422 `text_extraction_failed`
7. `test_upload_422_extraction_failed_after_retries` — `monkeypatch.setattr("...extract_resume", lambda *a, **kw: raise ValidationError)` → 422 `extraction_failed`

Plus diff-helper tests:
- `test_compute_skills_diff_classifies_correctly`
- `test_compute_skills_diff_orders_added_first` (added → removed → unchanged, alphabetical)
- `test_compute_skills_diff_normalizes_via_normalize_skill` (Python vs python → unchanged)

Plus PATCH tests:
- `test_patch_replaces_skills_json`
- `test_patch_none_fields_preserve_existing`
- `test_patch_returns_loaded_profile`

Plus PROF-01 / D-05 tests (matching.py::load_profile):
- `test_load_profile_returns_seeded_row` (assert returned `UserSkillProfile` matches seed dict)
- `test_load_profile_fails_when_row_missing` (assert `RuntimeError`)
- `test_load_profile_independent_of_filesystem` (patch `settings.profile_path` to nonexistent path; load still works — D-05 criterion 2)

These live in `tests/test_matching.py` OR `tests/test_profile.py` per planner discretion (CONTEXT D-Discretion line 300 says profile tests file).

---

### 14. `tests/conftest.py` (modify, +fixtures)

**Analog:** `tests/conftest.py::sample_raw_text` (lines 20-24)
**Match:** EXACT — file-read fixture from `tests/fixtures/`

**Existing pattern** (conftest.py:20-24):
```python
@pytest.fixture
def sample_raw_text() -> str:
    path = "tests/fixtures/sample_posting.md"
    with open(path, encoding="utf-8") as f:
        return f.read()
```

**Phase 7 application:**
```python
@pytest.fixture
def sample_resume_pdf() -> bytes:
    with open("tests/fixtures/sample-resume.pdf", "rb") as f:
        return f.read()

@pytest.fixture
def sample_resume_docx() -> bytes:
    with open("tests/fixtures/sample-resume.docx", "rb") as f:
        return f.read()

@pytest.fixture
def encrypted_resume_pdf() -> bytes:
    with open("tests/fixtures/encrypted-sample.pdf", "rb") as f:
        return f.read()

@pytest.fixture
def empty_text_resume_pdf() -> bytes:
    with open("tests/fixtures/empty-text-sample.pdf", "rb") as f:
        return f.read()
```

Mirror the byte-return style (not str) since upload tests POST `multipart/form-data` with raw bytes.

---

### 15. `tests/test_mcp_server.py` + `tests/test_analytics.py` (modify mocks)

**Analog:** existing patches at `test_mcp_server.py:126,164` and `test_analytics.py:357,378,403,417`
**Match:** SELF-EDIT — replace sync mock with async mock

**Existing pattern (sync mock)** (RESEARCH.md §4 lines 165-168):
```python
# test_mcp_server.py:126, :164
patch("job_rag.mcp_server.tools.load_profile")  # → MagicMock returning UserSkillProfile

# test_analytics.py:357, :378, :403, :417
monkeypatch.setattr(analytics, "load_profile", lambda *, user_id: UserSkillProfile(...))
```

**Phase 7 application** (per RESEARCH.md §4):
```python
# test_mcp_server.py
from unittest.mock import AsyncMock
patch("job_rag.mcp_server.tools.load_profile", AsyncMock(return_value=UserSkillProfile(...)))

# test_analytics.py
async def fake_load_profile(session, *, user_id):
    return UserSkillProfile(...)
monkeypatch.setattr(analytics, "load_profile", fake_load_profile)
```

---

### 16. `tests/test_observability.py` (modify, +trace tests)

**Analog:** existing observability tests (if any)
**Match:** PARTIAL — add three new test cases per RESEARCH.md validation table:
- `test_resume_upload_trace_has_four_spans` (mock `get_langfuse_client()`; assert `text_extract`, `llm_extract`, `diff_compute` emitted on upload; `profile_save` emitted on PATCH with matching `extraction_id`)
- `test_resume_trace_does_not_capture_text` (assert no span metadata contains raw resume text — D-33 PII redaction)
- `test_langfuse_fail_open_when_keys_missing` (patch settings to clear keys; upload still works without traces — mirrors `get_openai_client` fail-open pattern)

---

### 17. `frontend/src/components/profile/ProfileView.tsx` (NEW)

**Analog:** `frontend/src/components/dashboard/TopSkillsCard.tsx` (lines 1-138, full file)
**Match:** EXACT — Card + Skeleton + Alert + EmptyState pattern, with TanStack `useQuery`

**Card + useQuery pattern** (TopSkillsCard.tsx:83-138):
```tsx
export function TopSkillsCard() {
  const { filters } = useDashboardFilters()
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['dashboard', 'top-skills', filters],
    queryFn: ({ signal }) => topSkills(filters, signal),
    staleTime: 5 * 60_000,
  })

  return (
    <Card className="flex flex-col" data-testid="top-skills-card">
      <CardHeader>
        <CardTitle className="text-sm font-medium">Top skills</CardTitle>
      </CardHeader>
      <CardContent className="flex-1">
        {isPending && <TopSkillsSkeleton />}
        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Couldn't load top skills</AlertTitle>
            <AlertDescription>{describeError(error)}</AlertDescription>
          </Alert>
        )}
        {!isPending && !isError && data && data.skills.length === 0 && (
          <EmptyState icon={BarChart3} heading="No skills" body="..." />
        )}
        {!isPending && !isError && data && data.skills.length > 0 && (
          <SkillsBarList skills={data.skills.slice(0, VISIBLE_ROWS)} />
        )}
      </CardContent>
    </Card>
  )
}
```

**Phase 7 application:** `<ProfileView>` reads current profile via `useQuery({queryKey: ['profile'], queryFn: getProfile})`. Renders skills as read-only shadcn `<Badge>` chips grouped alphabetically; header shows count "Current skills (47)". Same layered loading/empty/error pattern (D-19 cited as SHEL-06 in CONTEXT canonical_refs).

---

### 18. `frontend/src/components/profile/ResumeUploader.tsx` (NEW)

**Analog:** `frontend/src/components/chat/ChatComposer.tsx` (lines 73-113) for sticky-input + Button pattern; `<input type="file">` is native (no analog in repo today)
**Match:** ROLE-MATCH — interactive input component with submit button

**Sticky input + Button pattern** (ChatComposer.tsx:73-113):
```tsx
return (
  <div className="sticky bottom-0 border-t bg-background px-4 py-3">
    <div className="flex items-end gap-2">
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask the agent something…"
        aria-label="Ask the agent"
        rows={1}
        className="min-h-[44px] max-h-[200px] resize-none flex-1"
        disabled={isStreaming || disabled}
      />
      {isStreaming ? (
        <Button variant="destructive" onClick={onStop} aria-label="Stop streaming response">
          <Square className="h-4 w-4 mr-1" aria-hidden="true" />Stop
        </Button>
      ) : (
        <Button onClick={onSubmit} disabled={disabled || value.trim() === ''}>
          <Send className="h-4 w-4 mr-1" aria-hidden="true" />Send
        </Button>
      )}
    </div>
  </div>
)
```

**Phase 7 application** (D-30, D-31): drop-zone wrapper div with `onDragOver` / `onDrop` listeners; native `<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document">` styled as a dashed border; client-side pre-checks (size ≤ 2 MB, extension in `{.pdf, .docx}`) before POST; shows file name + size + Remove (`X` lucide icon) before user clicks Upload; stepped status copy during upload (Reading… / Asking the agent… / Still working…) with `setTimeout` for 2s/10s thresholds (cold-start awareness pattern mirror of Phase 6 D-19 — see `useChatStream.ts` lines 24, 174-177 for the setTimeout COLD_START_DELAY_MS pattern).

---

### 19. `frontend/src/components/profile/ReviewPanel.tsx` (NEW)

**Analog:** `TopSkillsCard.tsx` for Card+Footer; chip list = simple `<ul>` of `<SkillDiffChip>` items
**Match:** EXACT — composition of existing primitives

**Phase 7 application** (D-27 — verbatim layout from CONTEXT):
```tsx
<Card>
  <CardHeader>
    <CardTitle>Review extracted skills</CardTitle>
    <CardDescription>{n_extracted} skills found · {n_added} new · {n_removed} removed · {n_unchanged} unchanged</CardDescription>
  </CardHeader>
  <CardContent className="max-h-[60vh] overflow-y-auto">
    <ul>
      {diff.map(item => <SkillDiffChip key={item.name} {...item} />)}
    </ul>
  </CardContent>
  <CardFooter className="sticky bottom-0 bg-background border-t">
    <Button variant="outline" onClick={cancel}>Discard</Button>
    <Button onClick={save} disabled={isSaving}>Save profile ({n} skills)</Button>
  </CardFooter>
</Card>
```

Live summary label "Save (3 new · 2 keep removed · 47 unchanged)" updates on each chip toggle.

---

### 20. `frontend/src/components/profile/SkillDiffChip.tsx` (NEW)

**Analog:** shadcn Badge usage in TopSkillsCard + Input usage from RESEARCH.md §10 inline-edit pattern
**Match:** PARTIAL — composes existing primitives in a new shape

**Inline-edit pattern** (RESEARCH.md §10 lines 435-457):
```tsx
const [editing, setEditing] = useState(false);
const [draft, setDraft] = useState(name);
return editing ? (
  <Input
    value={draft}
    autoFocus
    onChange={(e) => setDraft(e.target.value)}
    onBlur={() => { setName(draft); setEditing(false); }}
    onKeyDown={(e) => {
      if (e.key === "Enter") { setName(draft); setEditing(false); }
      if (e.key === "Escape") { setDraft(name); setEditing(false); }
    }}
  />
) : (<span>{name}</span>);
{item.editable && (
  <Button variant="ghost" size="icon" onClick={() => setEditing(true)}>
    <Pencil className="h-3 w-3" />
  </Button>
)}
```

**Status pill colors** (D-24):
- Added → `bg-green-500/10 text-green-700 dark:text-green-400`
- Removed → `bg-red-500/10 text-red-700 dark:text-red-400`
- Unchanged → `bg-muted text-muted-foreground`

Apply via `<Badge className={pillColor}>`. Tick affordance: native `<input type="checkbox">` wrapped in `<label>` for accessibility (RESEARCH.md §10 Option A recommendation).

---

### 21. `frontend/src/components/profile/useResumeUpload.ts` (NEW)

**Analog:** `frontend/src/components/chat/useChatStream.ts` (lines 127-280) for state-owner hook pattern; TanStack `useMutation` pattern (no direct analog — chat uses streaming, not mutations)
**Match:** ROLE-MATCH — both are state-owning hooks with one lifecycle owner

**State-owner hook pattern** (useChatStream.ts:127-280, condensed):
```typescript
export function useChatStream(): UseChatStreamReturn {
  const [items, dispatch] = useReducer(transcriptReducer, [])
  const [isStreaming, setIsStreaming] = useState(false)
  const [coldStart, setColdStart] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      if (coldStartTimerRef.current) {
        clearTimeout(coldStartTimerRef.current)
      }
    }
  }, [])

  const submit = useCallback(async (query: string) => {
    // ... mutation logic + cold-start timer + abort controller ...
  }, [clearColdStartTimer])

  return { items, isStreaming, coldStart, networkError, submit, stop, ... }
}
```

**Phase 7 application** (RESEARCH.md §11 lines 470-505):
```typescript
type ReviewState =
  | { phase: 'idle' }
  | { phase: 'reviewing'; diff: DiffItemState[]; extractionId: string }
  | { phase: 'saved' };

export function useResumeUpload() {
  const queryClient = useQueryClient();
  const [state, setState] = useState<ReviewState>({ phase: 'idle' });

  const upload = useMutation({
    mutationFn: (file: File) => uploadResume(file),
    onSuccess: (resp) => setState({
      phase: 'reviewing',
      diff: resp.skills_diff.map(d => ({ ...d, checked: d.source !== 'removed', editedName: d.name })),
      extractionId: resp.extraction_id,
    }),
  });

  const save = useMutation({
    mutationFn: (payload: UserProfileUpdate) => saveProfile(payload),
    onSuccess: (profile) => {
      queryClient.setQueryData(['profile'], profile);
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setState({ phase: 'saved' });
    },
  });

  return { state, upload, save, reset: () => setState({ phase: 'idle' }) };
}
```

---

### 22. `frontend/src/components/profile/types.ts` (NEW)

**Analog:** `frontend/src/components/chat/types.ts` + `frontend/src/components/dashboard/useDashboardFilters.ts` (lines 13-26 for re-export pattern)
**Match:** EXACT — module-local types that extend codegen types

**Re-export pattern** (useDashboardFilters.ts:13-26):
```typescript
import type { components } from '@/api/types'

export type Seniority = components['schemas']['Seniority']

export type Country = 'PL' | 'DE' | 'EU' | 'WW'
export type Remote = 'any' | 'remote' | 'non_remote'

export type DashboardFilters = {
  country: Country
  seniority: Seniority | undefined
  remote: Remote
}
```

**Phase 7 application:**
```typescript
import type { components } from '@/api/types'

export type SkillDiffItem = components['schemas']['SkillDiffItem']
export type ResumeUploadResponse = components['schemas']['ResumeUploadResponse']
export type UserProfileUpdate = components['schemas']['UserProfileUpdate']

export type DiffItemState = SkillDiffItem & {
  checked: boolean
  editedName: string
}
```

---

### 23. `frontend/src/components/profile/*.test.tsx` (NEW)

**Analog:** `frontend/src/components/dashboard/__tests__/*.test.tsx` (if present) + `useDashboardFilters.test.tsx`
**Match:** EXACT — same Vitest + RTL pattern; assertions via `screen.getByRole`/`screen.getByText`

**Phase 7 application:** 5 test files per CONTEXT integration_points: `ProfileView.test.tsx`, `ResumeUploader.test.tsx`, `ReviewPanel.test.tsx`, `SkillDiffChip.test.tsx`, `useResumeUpload.test.tsx`. Coverage per RESEARCH.md Validation Architecture (PROF-05 table lines 569-573) — see PROF-05 gate criteria for the exact assertions each test must hit.

---

### 24. `frontend/src/routes/Profile.tsx` (modify — replace PhasePlaceholder)

**Current state** (Profile.tsx, full file):
```tsx
import { PhasePlaceholder } from '@/components/PhasePlaceholder'

export function ProfilePage() {
  return <PhasePlaceholder phase={7} feature="Profile" />
}
```

**Analog for replacement:** `frontend/src/routes/Dashboard.tsx` + `Chat.tsx` (route composes feature-folder components)
**Match:** EXACT

**Phase 7 application** (D-28 — two-state via React state):
```tsx
export function ProfilePage() {
  const { state, upload, save, reset } = useResumeUpload();

  if (state.phase === 'idle') {
    return (
      <>
        <ProfileView />
        <ResumeUploader onUpload={upload.mutate} isPending={upload.isPending} />
      </>
    );
  }
  return (
    <ReviewPanel
      diff={state.diff}
      extractionId={state.extractionId}
      onSave={save.mutate}
      onCancel={reset}
      isSaving={save.isPending}
    />
  );
}
```

---

### 25. `frontend/src/api/profile.ts` (modify — fill stub)

**Analog:** `frontend/src/api/jobs.ts` (lines 1-67, full file — typed dashboard service module)
**Match:** EXACT

**Service module pattern** (jobs.ts:40-46):
```typescript
export async function topSkills(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<TopSkillsResponse> {
  const res = await authedFetch(`/dashboard/top-skills${buildFilterQuery(filters)}`, { signal })
  if (!res.ok) throw new Error(`top-skills: HTTP ${res.status}`)
  return res.json() as Promise<TopSkillsResponse>
}
```

**Phase 7 application** (D-29):
```typescript
import { authedFetch } from '@/api/authedFetch'
import type { components } from '@/api/types'

export type ResumeUploadResponse = components['schemas']['ResumeUploadResponse']
export type UserProfileUpdate = components['schemas']['UserProfileUpdate']
export type UserSkillProfile = components['schemas']['UserSkillProfile']

export async function getProfile(signal?: AbortSignal): Promise<UserSkillProfile> {
  const res = await authedFetch('/profile', { signal })
  if (!res.ok) throw new Error(`profile: HTTP ${res.status}`)
  return res.json() as Promise<UserSkillProfile>
}

export async function uploadResume(file: File, signal?: AbortSignal): Promise<ResumeUploadResponse> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await authedFetch('/profile/upload', { method: 'POST', body: fd, signal })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.reason ?? `upload: HTTP ${res.status}`)
  }
  return res.json() as Promise<ResumeUploadResponse>
}

export async function saveProfile(payload: UserProfileUpdate, signal?: AbortSignal): Promise<UserSkillProfile> {
  const res = await authedFetch('/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) throw new Error(`profile-save: HTTP ${res.status}`)
  return res.json() as Promise<UserSkillProfile>
}
```

Note: `authedFetch` already handles `FormData` bodies (does not set Content-Type — browser auto-sets `multipart/form-data; boundary=...`). The `Content-Length` header is browser-computed; the backend's middleware D-07 reads it pre-body.

---

### 26. `frontend/src/api/types.ts` + `frontend/openapi.snapshot.json` (regenerate)

**Analog:** Phase 4 D-14 codegen workflow
**Match:** EXACT

**Phase 7 application** (RESEARCH.md §9):
```bash
cd frontend
npm run codegen:snapshot   # writes openapi.snapshot.json from running backend
npm run codegen            # regenerates frontend/src/api/types.ts
git add openapi.snapshot.json src/api/types.ts
```

Sequencing: backend lands first → regen + commit → frontend builds against new types.ts. CI drift guard (Phase 4 D-14) enforces snapshot-vs-running diff = 0.

---

### 27. `data/README.md` (NEW)

**Phase 7 application** (D-04, ~10 lines): document `data/profile.json` as a reference snapshot, not a runtime read path (see PROF-01). Suggested content:
```markdown
# data/

Local-only reference data. NOT a runtime read path.

- `profile.json` — reference snapshot of Adrian's seed `user_profile` row. The canonical runtime
  source is the `user_profile` DB row, seeded by `alembic/versions/0006_seed_user_profile.py` from
  an embedded dict literal (PROF-01 / Phase 7 D-03, D-04). Update flow when seed contents change:
  edit `profile.json` + regenerate the dict literal in the migration in lockstep.
- `postings/` — markdown ingestion corpus; consumed by `job-rag ingest` (development only).
```

---

## Shared Patterns

### Authentication + Rate Limiting (applies to all POST/PATCH/GET routes)

**Source:** `src/job_rag/api/routes.py:171-178` (existing `/match`) + `src/job_rag/api/auth.py:135-168`

```python
from job_rag.api.auth import get_current_user_id, require_api_key, standard_limit

@router.post(
    "/profile/upload",
    dependencies=[Depends(require_api_key), Depends(standard_limit)],
)
async def upload_resume(
    file: UploadFile,
    session: Session,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
) -> ResumeUploadResponse:
    ...
```

**Apply to:** `POST /profile/upload`, `PATCH /profile` (D-06, D-21).

`standard_limit` (30/min) is the chosen tier per D-06 — `agent_limit` (10/min) is reserved for Phase 6 chat. The `get_current_user_id` dep enforces AUTH-06 single-user guard (rejects any oid ≠ `settings.seeded_user_entra_oid` with 403). Phase 7 inherits this guard automatically — no per-route auth changes.

---

### Error Handling (HTTPException with structured detail)

**Source:** `src/job_rag/api/routes.py:189-190` (HTTPException pattern); D-35 introduces the structured `detail={reason, message}` shape

```python
raise HTTPException(
    status_code=413,
    detail={"reason": "file_too_large", "message": "Resume must be ≤2 MB."},
)
```

**Apply to:** every error-emitting branch in `POST /profile/upload` (7 reasons per D-35 table). Backend `log.warning("resume_upload_failed", reason=..., file_type=..., file_size_bytes=...)` accompanies every raise.

Frontend maps `reason` → user-facing copy via the literal `COPY` object in `useResumeUpload.ts` (D-35 mapping table).

---

### Structured Logging

**Source:** `src/job_rag/logging.py::get_logger` + `extraction/extractor.py:75-81` (event-name + kwargs pattern)

```python
log = get_logger(__name__)

log.info(
    "extraction_complete",
    company=posting.company,
    title=posting.title,
    requirements_count=len(posting.requirements),
    **usage_info,
)
```

**Apply to:** all Phase 7 backend code. New event names: `resume_upload_started`, `resume_text_extracted`, `resume_skills_extracted`, `resume_upload_failed`, `profile_saved`, `resume_text_truncated`, `resume_extraction_failed` (D-11, D-16, D-35).

---

### Async-from-sync via `asyncio.to_thread` (Phase 1 D-05 reranker pattern)

**Source:** Phase 1 D-05 (reranker preload wrap) — referenced in CONTEXT canonical_refs

```python
# Sync function:
def extract_resume(text: str) -> tuple[ResumeExtraction, dict]: ...

# Called from async route:
extraction, usage_info = await asyncio.to_thread(extract_resume, text)
```

**Apply to:** `POST /profile/upload` calling `extract_resume()` (D-15). The sync OpenAI client inside `extract_resume` would block the event loop if called directly; `asyncio.to_thread` offloads to the default executor.

---

### Langfuse fail-open

**Source:** `src/job_rag/observability.py:24-26, 39-54, 74-83` (`is_enabled()` guard + lru_cache factory + best-effort flush)

```python
def is_enabled() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)

# All callers guard:
lf = get_langfuse_client()
if lf:
    with lf.trace(...) as t: ...
```

**Apply to:** every Langfuse touch in `POST /profile/upload` + `PATCH /profile` (D-32, D-33). Always behind an `if lf:` guard. No-op when keys missing (Phase 1 observability convention).

---

### Frontend TanStack Query keying + cache invalidation

**Source:** Phase 5 D-15 cache keys + `frontend/src/components/dashboard/TopSkillsCard.tsx:87-91`

```typescript
const { data, isPending, isError } = useQuery({
  queryKey: ['dashboard', 'top-skills', filters],
  queryFn: ({ signal }) => topSkills(filters, signal),
  staleTime: 5 * 60_000,
})
```

**Apply to:**
- `<ProfileView>` reads via `useQuery({ queryKey: ['profile'], queryFn: getProfile })`
- `useResumeUpload` save mutation calls `queryClient.setQueryData(['profile'], profile)` on success + `queryClient.invalidateQueries({ queryKey: ['dashboard'] })` so Phase 5 CV-vs-market widget re-fetches on next render (D-22, D-Discretion `TanStack Query keys`).

---

### Frontend layered loading/empty/error pattern (SHEL-06)

**Source:** Phase 4 D-19 + `TopSkillsCard.tsx:98-113`

```tsx
{isPending && <Skeleton />}
{isError && <Alert variant="destructive">...</Alert>}
{!isPending && !isError && data && data.skills.length === 0 && <EmptyState ... />}
{!isPending && !isError && data && data.skills.length > 0 && <ContentRenderer .../>}
```

**Apply to:** `<ProfileView>` (skill list with possible-empty state), `<ResumeUploader>` (idle / uploading / cold-start states per D-31), `<ReviewPanel>` (saving state).

---

### Feature-folder component organization

**Source:** Phase 5 D-15 (`frontend/src/components/dashboard/`) + Phase 6 D-27 (`frontend/src/components/chat/`)

```
frontend/src/components/{feature}/
  {Feature}View.tsx           — top-level read-state surface
  {Feature}{Verb}.tsx         — action surfaces (Composer, Uploader, ...)
  {atom}.tsx                  — leaf components (Chip, Tool, ...)
  use{Feature}{Verb}.ts       — state-owning custom hook
  types.ts                    — module-local types extending codegen
  __tests__/ OR *.test.tsx    — co-located vitest+RTL tests
```

**Apply to:** `frontend/src/components/profile/` per D-29 — 6 files total (ProfileView, ResumeUploader, ReviewPanel, SkillDiffChip, useResumeUpload, types).

---

## No Analog Found

| File | Role | Data Flow | Reason | Fallback |
|------|------|-----------|--------|----------|
| `src/job_rag/api/middleware.py` | ASGI middleware | request-response | No existing `BaseHTTPMiddleware` subclass in repo; the closest pattern is `RateLimiter` callable-dep in `auth.py:101-131`, but middleware MUST be class-based for pre-body inspection | Use RESEARCH.md §2 lines 62-77 skeleton verbatim |
| `data/README.md` | docs | static | New tiny doc; no analog | D-04 literal: "reference snapshot, NOT a runtime read path — see PROF-01" |

---

## Pattern Reuse Summary

| Pattern | Source File | Reused By |
|---------|-------------|-----------|
| Instructor `@retry` extraction | `extraction/extractor.py:36-83` | `extraction/resume_extractor.py` |
| `PROMPT_VERSION` + `REJECTED_SOFT_SKILLS` | `extraction/prompt.py:22-50, 137-141` | `extraction/resume_prompt.py` |
| `_normalize_skill` helper | `services/matching.py:38-40` | `services/profile.py::compute_skills_diff` |
| Idempotent migration with revision chain | `alembic/versions/0005_adopt_entra_oid.py:38-48, 74-109` | `alembic/versions/0006_seed_user_profile.py` |
| `Depends(require_api_key) + Depends(standard_limit) + Depends(get_current_user_id)` | `api/routes.py:171-178, 477-481` + `api/auth.py:135-168` | `POST /profile/upload`, `PATCH /profile` |
| `UploadFile` + size-cap | `api/routes.py:504-507` (1 MB) | `POST /profile/upload` (2 MB, plus pre-body middleware) |
| Pydantic sibling model | `models.py::UserSkillProfile:147-158` | `models.py::ResumeExtraction` |
| `Field(default=..., ge=1)` Setting | `config.py:51-53` | `config.py::max_resume_size_bytes` |
| `@lru_cache(maxsize=1)` + fail-open client factory | `observability.py:39-54` | `observability.py::get_langfuse_client` |
| Mock-Instructor unit test | `tests/test_extraction.py:65-71` | `tests/test_resume_extractor.py` |
| File-bytes pytest fixture | `tests/conftest.py:20-24` | `conftest.py::sample_resume_pdf/docx/...` |
| Card + useQuery + Skeleton/Alert/EmptyState | `frontend/src/components/dashboard/TopSkillsCard.tsx:83-138` | `ProfileView.tsx`, `ReviewPanel.tsx` |
| Sticky-bottom Card footer | `frontend/src/components/chat/ChatComposer.tsx:73-113` | `ReviewPanel.tsx` CardFooter |
| State-owner hook (cleanup on unmount + AbortController) | `frontend/src/components/chat/useChatStream.ts:127-280` | `useResumeUpload.ts` |
| Typed service module via `components['schemas']` | `frontend/src/api/jobs.ts:12-22, 40-46` | `frontend/src/api/profile.ts` |
| Cold-start setTimeout copy pattern | `frontend/src/components/chat/useChatStream.ts:24, 174-177` | `ResumeUploader.tsx` (D-31 stepped copy) |
| TanStack mutation + setQueryData + invalidateQueries | (NEW — first mutation in repo; pattern documented in RESEARCH.md §11) | `useResumeUpload.ts` |

---

## Metadata

**Analog search scope:**
- `src/job_rag/api/`
- `src/job_rag/services/`
- `src/job_rag/extraction/`
- `src/job_rag/db/`
- `src/job_rag/observability.py`, `config.py`, `models.py`, `logging.py`
- `alembic/versions/`
- `tests/` (top-level)
- `frontend/src/components/{dashboard,chat}/`
- `frontend/src/api/`
- `frontend/src/routes/`

**Files scanned:** 16 backend + 9 frontend + 5 alembic = 30 read operations
**Pattern extraction date:** 2026-05-27

## PATTERN MAPPING COMPLETE
