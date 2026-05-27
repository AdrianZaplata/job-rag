# Phase 7: Profile & Resume Upload — Research

**Researched:** 2026-05-27
**Status:** Ready for planning
**Source:** Synthesised from CONTEXT.md (37 locked decisions D-01..D-37) + UI-SPEC.md + codebase reads. CONTEXT.md is the canonical spec — this file converts those decisions into implementation-ready notes, including the Nyquist Validation Architecture.

## Overview

Phase 7 is heavily decision-locked. CONTEXT.md (60 KB) already specifies every implementation detail across 37 D-XX bullets; UI-SPEC.md (120 KB) specifies every visual contract. The remaining research is mechanical synthesis: confirm library APIs, document `load_profile()` call-site impact, lock down the Alembic seed-migration shape, and produce the Validation Architecture seed for the Nyquist gate.

The phase reuses every existing backend pattern (Instructor + tenacity, Langfuse fail-open, `Depends(get_current_user_id)`, `standard_limit`) and every existing frontend primitive (Card, Badge, Button, Input, Skeleton, Alert, sonner) — NO new shadcn primitives, NO infra changes. The only net-new dependencies are `pypdf>=6,<7` and `python-docx>=1,<2`.

## 1. PDF/DOCX text extraction

### pypdf 6.x (D-09)

```python
from io import BytesIO
import pypdf

def extract_pdf_text(raw: bytes) -> str:
    reader = pypdf.PdfReader(BytesIO(raw))
    if reader.is_encrypted:
        raise pypdf.errors.PdfReadError("encrypted")
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)
```

- `PdfReader.is_encrypted` is a property — check BEFORE accessing pages (accessing pages on an encrypted reader raises `PdfReadError`).
- `page.extract_text()` returns `""` for image-only pages (no OCR). D-10's `len(text.strip()) < 100` post-condition catches this.
- Memory: a 2 MB PDF parsed in-memory peaks around ~6–8 MB transient (pypdf builds intermediate objects). Acceptable for ACA's 0.5 vCPU / 1 GB free-tier.
- Catch `pypdf.errors.PdfReadError` for malformed/corrupt PDFs → 422 `pdf_encrypted` (the most common cause; lump together for v1 per D-35).

### python-docx 1.x (D-09)

```python
from io import BytesIO
import docx

def extract_docx_text(raw: bytes) -> str:
    doc = docx.Document(BytesIO(raw))
    parts: list[str] = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            parts.append("\t".join(cell.text for cell in row.cells))
    return "\n".join(parts)
```

- `doc.paragraphs` walks the body — does NOT include text inside tables. Tables must be iterated separately.
- `doc.sections[*].header` and `.footer` are NOT traversed (D-09 explicit). Headers/footers in resumes are typically name/contact and rarely contain skills.
- Memory: similar to pypdf — well under 100 MB for a 2 MB DOCX.
- DOCX is a zip; corrupt or non-DOCX bytes raise `docx.opc.exceptions.PackageNotFoundError` → 422 (treat as `text_extraction_failed`).

## 2. FastAPI pre-body 413 enforcement (D-07 literal)

REQ-PROF-02 explicit wording: "rejected with a 413 before the body is fully read". Two layers:

### Primary: ASGI middleware reading `content-length` header

```python
# src/job_rag/api/middleware.py (NEW or appended)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

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

- Mounted on the FastAPI app before the router. Inspected BEFORE any handler runs.
- Returns 413 immediately when Content-Length declares > 2 MB. Body never enters the handler.

### Fallback: chunked-encoding (no Content-Length)

When `Transfer-Encoding: chunked` is used, `Content-Length` is absent. UploadFile read-loop:

```python
async def read_with_cap(upload: UploadFile, cap: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise HTTPException(413, detail={"reason": "file_too_large", "message": "..."})
        chunks.append(chunk)
    return b"".join(chunks)
```

- Aborts mid-stream once `cap` exceeded. Slightly weaker than the header check (the body has partially streamed), but the literal "before the body is fully read" still holds.

### Test strategy

- D-36 test #3: send `Content-Length: 3_000_000` with a 1 KB body → expect 413 + assert handler never invoked (set a counter via `request.state` or a side-channel; alternatively assert via log absence).
- Fallback test: post chunked-encoded body > 2 MB → expect 413 mid-stream (mock httpx client with chunked iterator).

## 3. Instructor + retry mirror (D-15)

Mirror of `src/job_rag/extraction/extractor.py:36-83` (extract_posting):

```python
# src/job_rag/extraction/resume_extractor.py (NEW)
import instructor
from tenacity import retry, stop_after_attempt, wait_exponential

from job_rag.config import settings
from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION, RESUME_SYSTEM_PROMPT
from job_rag.logging import get_logger
from job_rag.models import ResumeExtraction
from job_rag.observability import get_openai_client

log = get_logger(__name__)


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def extract_resume(text: str) -> tuple[ResumeExtraction, dict]:
    client = instructor.from_openai(get_openai_client())
    extraction, completion = client.chat.completions.create_with_completion(
        model=settings.openai_model,
        response_model=ResumeExtraction,
        messages=[
            {"role": "system", "content": RESUME_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    usage = completion.usage
    usage_info = {
        "model": settings.openai_model,
        "prompt_version": RESUME_PROMPT_VERSION,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
    }
    log.info("resume_extraction_complete", skills_count=len(extraction.skills), **usage_info)
    return extraction, usage_info
```

- After 3 retries, tenacity re-raises the underlying exception. Instructor's wrapper raises `pydantic.ValidationError` on persistent schema failures and OpenAI client errors (e.g. `openai.APIError`) for upstream issues. The route handler catches both and maps to:
  - `pydantic.ValidationError` → 422 `extraction_failed` (D-16, D-35)
  - `openai.APIError` family → 503 `llm_unavailable` (D-35)
- Called from the async route via `await asyncio.to_thread(extract_resume, text)` (Phase 1 D-05 reranker pattern; mirrors how the reranker is invoked).

## 4. `load_profile()` async refactor (D-01/D-02)

Verified call sites (`grep -rn "load_profile" src/ tests/`):

| File | Line | Context | After flip |
|------|------|---------|------------|
| `src/job_rag/api/routes.py` | 192 | `/match/{posting_id}` handler | `profile = await load_profile(session, user_id=user_id)` — `session` already injected via `Depends(get_session)` |
| `src/job_rag/api/routes.py` | 216 | `/gaps` handler | `profile = await load_profile(session, user_id=user_id)` — same as above |
| `src/job_rag/mcp_server/tools.py` | 121 | `match_skills()` MCP tool | Already opens `async with AsyncSessionLocal() as session:`; reuse the open session: `profile = await load_profile(session, user_id=settings.seeded_user_id)` |
| `src/job_rag/mcp_server/tools.py` | 147 | `skill_gaps()` MCP tool | Same as above |
| `src/job_rag/services/analytics.py` | 295 | Phase 5 `_compute_cv_vs_market` (called by `/dashboard/cv-vs-market`) | Takes `session: AsyncSession` parameter from caller; `profile = await load_profile(session, user_id=user_id)` |

**Test files that mock `load_profile`** (must update mock signatures + add `session` arg):
- `tests/test_mcp_server.py:126` and `:164` — `patch("job_rag.mcp_server.tools.load_profile")` — replace with async mock returning `UserSkillProfile`
- `tests/test_analytics.py:357, :378, :403, :417` — `monkeypatch.setattr(analytics, "load_profile", lambda *, user_id: ...)` — must become an async callable: `monkeypatch.setattr(analytics, "load_profile", AsyncMock(return_value=...))` or `async def fake(session, *, user_id): ...`

### New body

```python
# src/job_rag/services/matching.py
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_rag.config import settings
from job_rag.db.models import UserProfileDB
from job_rag.models import RemotePolicy, UserSkill, UserSkillProfile


async def load_profile(
    session: AsyncSession, *, user_id: UUID | None = None,
) -> UserSkillProfile:
    """Load user skill profile from the `user_profile` DB row (PROF-01)."""
    uid = user_id or settings.seeded_user_id
    stmt = select(UserProfileDB).where(UserProfileDB.user_id == uid)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        # The seed migration guarantees this row; missing = data-integrity bug.
        raise RuntimeError(f"user_profile row missing for user_id={uid}")
    return UserSkillProfile(
        skills=[UserSkill(**s) for s in json.loads(row.skills_json)],
        target_roles=json.loads(row.target_roles_json),
        preferred_locations=json.loads(row.preferred_locations_json),
        min_salary=row.min_salary_eur,
        remote_preference=RemotePolicy(row.remote_preference),
    )
```

- The `path` kwarg is removed (Phase 1 D-07 forward-compat hook; no production caller passes it).
- Pydantic validates the JSON on read; corrupt rows raise `ValidationError` → 500 (data integrity bug, not user error).

## 5. Alembic data-only seed migration (D-03)

```python
# alembic/versions/0006_seed_user_profile.py
"""seed Adrian's user_profile row (PROF-01 / Phase 7 D-03)"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"

# Embedded snapshot of data/profile.json (CONTEXT D-03: must be a literal dict;
# data/ is gitignored at the container layer so a runtime file read would fail).
_PROFILE = {
    "skills": [
        # ... populated from data/profile.json at migration-author time
    ],
    "target_roles": [...],
    "preferred_locations": [...],
    "min_salary": ...,
    "remote_preference": "remote",
}


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO user_profile "
            "(user_id, skills_json, target_roles_json, preferred_locations_json, "
            " min_salary_eur, remote_preference, updated_at) "
            "VALUES (:uid, :skills, :roles, :locs, :sal, :remote, now()) "
            "ON CONFLICT (user_id) DO NOTHING"
        ).bindparams(
            uid=SEEDED_USER_UUID,
            skills=json.dumps(_PROFILE["skills"]),
            roles=json.dumps(_PROFILE["target_roles"]),
            locs=json.dumps(_PROFILE["preferred_locations"]),
            sal=_PROFILE["min_salary"],
            remote=_PROFILE["remote_preference"],
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM user_profile WHERE user_id = :uid").bindparams(uid=SEEDED_USER_UUID)
    )
```

- ON CONFLICT DO NOTHING is idempotent: re-runs against an existing row are no-ops. PG16 (prod) and PG17 (dev) both support this.
- `down_revision = "0005"` chains after the current head (`0005_adopt_entra_oid`).
- Per Phase 1 D-04: `init_db()` wraps `alembic upgrade head` so the seed runs automatically on container boot. No new wiring.
- **Pgvector caveat**: `alembic/env.py` already registers `pgvector.sqlalchemy.Vector` on `connection.dialect.ischema_names`; this migration is pure SQL so no concern.

### Why embed the dict literal vs read data/profile.json

CONTEXT D-03 is explicit: data/ is gitignored at the container layer. A runtime `Path("data/profile.json").read_text()` inside the migration would crash on first-boot in ACA. Generate the literal once at PR time from `data/profile.json` (e.g., a `scripts/dump_profile_literal.py` helper or a manual paste). Update `data/README.md` (D-04) to record the "reference snapshot, not runtime read path" contract.

## 6. Langfuse trace correlation (D-32)

```python
# src/job_rag/observability.py — additions
from langfuse import Langfuse  # already imported transitively for the openai wrapper

def get_langfuse_client() -> Langfuse | None:
    if not langfuse_enabled():
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
```

Usage in `/profile/upload`:

```python
from uuid import uuid4
extraction_id = uuid4()
lf = get_langfuse_client()
if lf:
    trace = lf.trace(
        name="resume_upload",
        id=str(extraction_id),
        user_id=str(user_id),
        tags=["resume", "phase-7"],
    )
    # Spans (start/end pairs):
    with trace.span(name="text_extract") as s:
        text = ...  # pypdf/python-docx
        s.end(metadata={"file_type": ..., "char_count": len(text), "page_count": ...})
    # llm_extract span is auto-captured by langfuse.openai wrapper (settings.openai already wrapped)
    with trace.span(name="diff_compute") as s:
        diff = compute_skills_diff(current, extracted)
        s.end(metadata={"added_count": ..., "removed_count": ..., "unchanged_count": ...})
```

Usage in `PATCH /profile` (when `extraction_id` is supplied):

```python
lf = get_langfuse_client()
if lf and payload.extraction_id:
    # Attach a new span to the existing trace via the same trace ID
    trace = lf.trace(id=str(payload.extraction_id))  # no-op create / fetch by ID
    with trace.span(name="profile_save") as s:
        await session.execute(update(UserProfileDB).where(...).values(...))
        await session.commit()
        s.end(metadata={"written_skill_count": len(payload.skills)})
```

### PII redaction (D-33)

- The `text_extract` span MUST NOT capture the raw resume text — only metadata (`char_count`, `page_count`, `latency_ms`).
- The `llm_extract` span's `input` field (auto-captured by `langfuse.openai`) WILL contain the resume body unless explicitly suppressed. Use `lf.update_current_observation(input={"text": f"[REDACTED — char_count={n}]"})` immediately after the LLM call, OR — preferred — wrap the LLM call in a no-input span and call `client.chat.completions.create(...)` outside the langfuse-wrapped client for the resume case. The simplest pragmatic solution: keep the wrapper and post-process via `langfuse.update_current_trace(input=None)` before flush.
- Output is the structured `ResumeExtraction` JSON — skill names are operational signal (NOT PII). Safe to trace.
- Fail-open: `get_langfuse_client()` returns None when keys missing; all the `if lf:` blocks no-op cleanly.

## 7. PATCH UPDATE with None-as-no-change (D-21)

```python
# src/job_rag/api/routes.py (Phase 7 addition)
@router.patch("/profile", dependencies=[Depends(require_api_key), Depends(standard_limit)])
async def update_profile(
    session: Session,
    payload: UserProfileUpdate,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
) -> UserSkillProfile:
    # Pydantic enforces `skills` is REQUIRED; other fields default to None.
    updates: dict[str, Any] = {
        "skills_json": json.dumps([s.model_dump() for s in payload.skills]),
        "updated_at": func.now(),
    }
    if payload.target_roles is not None:
        updates["target_roles_json"] = json.dumps(payload.target_roles)
    if payload.preferred_locations is not None:
        updates["preferred_locations_json"] = json.dumps(payload.preferred_locations)
    if payload.min_salary_eur is not None:
        updates["min_salary_eur"] = payload.min_salary_eur
    if payload.remote_preference is not None:
        updates["remote_preference"] = payload.remote_preference.value
    stmt = update(UserProfileDB).where(UserProfileDB.user_id == user_id).values(**updates)
    await session.execute(stmt)
    await session.commit()
    return await load_profile(session, user_id=user_id)
```

- `update().values(**only_provided_fields)` SQL pattern. None values are NEVER passed → DB columns retain their existing value. UPSERT semantics not needed (the seed migration D-03 guarantees the row exists).
- `model_dump(exclude_none=True)` of the Pydantic payload is the idiomatic alternative; either is fine.
- Return the freshly-loaded `UserSkillProfile` so the client's TanStack Query cache can hydrate via `setQueryData(['profile'], data)`.

## 8. `compute_skills_diff()` algorithm (D-17..D-20)

```python
# src/job_rag/services/profile.py (NEW)
from typing import Literal
from pydantic import BaseModel
from job_rag.models import UserSkill, UserSkillProfile
from job_rag.services.matching import _normalize_skill


class SkillDiffItem(BaseModel):
    name: str
    source: Literal["added", "removed", "unchanged"]
    editable: bool


def compute_skills_diff(
    current: UserSkillProfile, extracted_skills: list[UserSkill]
) -> list[SkillDiffItem]:
    """Diff extracted skills against current profile (D-17..D-20)."""
    current_map = {_normalize_skill(s.name): s.name for s in current.skills}
    extracted_map = {_normalize_skill(s.name): s.name for s in extracted_skills}

    cur_keys = set(current_map)
    ext_keys = set(extracted_map)

    added = sorted(extracted_map[k] for k in (ext_keys - cur_keys))
    removed = sorted(current_map[k] for k in (cur_keys - ext_keys))
    unchanged = sorted(extracted_map[k] for k in (ext_keys & cur_keys))

    return [
        *(SkillDiffItem(name=n, source="added", editable=True) for n in added),
        *(SkillDiffItem(name=n, source="removed", editable=False) for n in removed),
        *(SkillDiffItem(name=n, source="unchanged", editable=False) for n in unchanged),
    ]
```

- Casing: uses extracted casing for added/unchanged, current casing for removed (the canonical names the user already chose for removed skills).
- Ordering: added → removed → unchanged, each alphabetical (D-19).
- `_ALIAS_GROUPS` is empty (Phase 1 D-12); diff is normalize-equality only. Future alias support automatically benefits this function once `_ALIAS_INDEX` is populated — no code change required (would need to swap `_normalize_skill` membership for `_skill_matches` semantics; v1 explicitly does NOT do this per D-20).

## 9. OpenAPI codegen workflow

Confirmed from Phase 4 D-14 and frontend tooling:

```bash
# After backend changes land:
cd frontend
npm run codegen:snapshot   # writes openapi.snapshot.json from running backend
npm run codegen            # regenerates frontend/src/api/types.ts from snapshot
git add openapi.snapshot.json src/api/types.ts
git commit -m "chore(07): regen OpenAPI types after profile endpoints"
```

- CI drift guard (Phase 4 D-14): a CI step runs `npm run codegen:snapshot` against the test server, diffs against the committed snapshot, fails on mismatch. Phase 7 backend MUST land + snapshot regen first, then frontend builds against the new types.
- Ordering: 1) backend PLAN merges → 2) snapshot regen + commit → 3) frontend PLAN builds against types.ts.

## 10. Frontend chip UX with shadcn primitives (D-24..D-30)

### Tick affordance — no checkbox install needed

D-25 default tick states: added✓ / removed☐ / unchanged✓. Two implementation choices, both compatible with the existing primitives:

**Option A (Recommended): Native checkbox + label** — semantically correct, accessible by default, no styling tax. Use a `<label>` wrapper so click anywhere on the chip toggles state.

**Option B: Button toggle** — `<Button variant="ghost" size="icon" aria-pressed={checked} onClick={toggle}>` with a Check icon. Slightly more code but matches the Linear-dense aesthetic better.

Recommend Option A for v1 (less code; accessibility wins). If visual polish requires it, swap to Option B in a follow-up.

### Inline edit (D-26)

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
) : (
  <span>{name}</span>
);
{item.editable && (
  <Button variant="ghost" size="icon" onClick={() => setEditing(true)}>
    <Pencil className="h-3 w-3" />
  </Button>
)}
```

### Status pill colors (D-24)

Per the existing shadcn theme (zinc + Geist + new-york):
- Added: `bg-green-500/10 text-green-700 dark:text-green-400`
- Removed: `bg-red-500/10 text-red-700 dark:text-red-400`
- Unchanged: `bg-muted text-muted-foreground`

Apply via `Badge` variant override (`<Badge className={pillColor}>+ ADDED</Badge>`).

## 11. TanStack mutation + state machine (`useResumeUpload`)

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

- Single hook owns upload + post-extract review state + save mutation.
- `setQueryData(['profile'], profile)` hydrates the cache without an extra GET.
- `invalidateQueries({ queryKey: ['dashboard'] })` triggers Phase 5 CV-vs-market widget refetch (it reads profile server-side; the new skills propagate on the next dashboard fetch).
- AbortController: TanStack `useMutation` exposes `mutation.reset()`; deeper cancellation (Phase 6 D-26 pattern) is overkill for a single upload — defer.

## Validation Architecture

This section seeds the Nyquist `VALIDATION.md` — gates per requirement with concrete checkable criteria. Phase 7 has heavy test coverage (D-36 lists 5 backend error paths + happy paths; frontend has 6 components needing Vitest + RTL). This table maps each REQ to its enforcing gates.

### PROF-01 — DB-backed profile read path

| Gate | Coverage criterion | Tooling | Maps to |
|------|--------------------|---------|---------|
| static | `src/job_rag/services/matching.py::load_profile` signature is `async def load_profile(session: AsyncSession, *, user_id: UUID \| None = None) -> UserSkillProfile` | `uv run pyright src/` | D-01, D-02 |
| static | No production code reads `data/profile.json` except `data/README.md` | `grep -rn "profile.json" src/` returns 0 matches | D-05 |
| unit | `tests/test_matching.py::test_load_profile_returns_seeded_row` — assert returned `UserSkillProfile` matches seed dict | `uv run pytest tests/test_matching.py -k load_profile` | D-01..D-03 |
| unit | `tests/test_matching.py::test_load_profile_fails_when_row_missing` — assert `RuntimeError` raised when no row | same | D-02 (defensive) |
| unit | `tests/test_matching.py::test_load_profile_independent_of_filesystem` — patch `settings.profile_path` to nonexistent; assert `load_profile` still works | same | D-05 (criterion 2) |
| integration | `/match/{posting_id}`, `/gaps`, `/dashboard/cv-vs-market` continue to return identical shapes after the flip | `uv run pytest tests/test_api.py tests/test_analytics.py` | D-02 call-site audit |
| migration | `alembic upgrade head` against a fresh DB seeds Adrian's row idempotently | `tests/test_alembic.py` (NEW) or `pytest -k "seed_migration"` | D-03 |

### PROF-02 — Resume upload endpoint

| Gate | Coverage criterion | Tooling | Maps to |
|------|--------------------|---------|---------|
| static | `pypdf>=6,<7` and `python-docx>=1,<2` in `[project] dependencies` | `grep "pypdf\|python-docx" pyproject.toml` | D-09 |
| static | `MAX_RESUME_SIZE_BYTES = 2_000_000` constant in `config.py` | `grep "max_resume_size_bytes" src/job_rag/config.py` | D-07 |
| unit | `test_profile.py::test_upload_pdf_happy_path` — valid PDF → 200 + diff present | `uv run pytest tests/test_profile.py -k upload_pdf_happy` | D-09, D-36 #1 |
| unit | `test_profile.py::test_upload_docx_happy_path` — valid DOCX → 200 + diff present | `uv run pytest tests/test_profile.py -k upload_docx_happy` | D-09, D-36 #2 |
| unit | `test_profile.py::test_upload_413_oversized_content_length` — `Content-Length: 3_000_000` + tiny body → 413 BEFORE handler invoked | `uv run pytest tests/test_profile.py -k 413_oversized` | D-07, D-36 #3 |
| unit | `test_profile.py::test_upload_413_chunked_streaming` — chunked-encoded body > 2 MB → 413 mid-stream | same | D-07 fallback |
| unit | `test_profile.py::test_upload_415_txt_file_rejected` — `.txt` upload → 415 `unsupported_file_type` | same | D-08, D-36 #4 |
| unit | `test_profile.py::test_upload_422_encrypted_pdf` — encrypted PDF fixture → 422 `pdf_encrypted` | `uv run pytest tests/test_profile.py -k 422_encrypted` | D-09, D-35, D-36 #5 |
| unit | `test_profile.py::test_upload_422_empty_text_pdf` — image-only PDF fixture (extracts < 100 chars) → 422 `text_extraction_failed` | same | D-10, D-36 #6 |
| manual UAT | DevTools Network tab shows oversized upload aborts at request-headers stage (no body bytes uploaded) | manual: open `/profile`, upload 5 MB PDF, observe Network | D-07 literal |

### PROF-03 — LLM extraction with versioned prompt

| Gate | Coverage criterion | Tooling | Maps to |
|------|--------------------|---------|---------|
| static | `RESUME_PROMPT_VERSION = "1.0"` in `src/job_rag/extraction/resume_prompt.py` | `grep RESUME_PROMPT_VERSION src/job_rag/extraction/resume_prompt.py` | D-12 |
| static | `RESUME_SYSTEM_PROMPT` references `REJECTED_SOFT_SKILLS` from `extraction/prompt.py` | `grep REJECTED_SOFT_SKILLS src/job_rag/extraction/resume_prompt.py` | D-14 |
| static | `ResumeExtraction` Pydantic model exists in `src/job_rag/models.py` with all 6 fields per D-13 | `grep "class ResumeExtraction" src/job_rag/models.py` | D-13 |
| unit | `test_resume_extractor.py::test_extract_resume_returns_resume_extraction` — Instructor mocked; assert structured output type | `uv run pytest tests/test_resume_extractor.py -k structured_output` | D-15 |
| unit | `test_resume_extractor.py::test_extract_resume_rejects_soft_skills` — mock LLM returns `["communication"]`; assert filtered (or assert prompt instructs LLM to reject) | same | D-14 |
| unit | `test_resume_extractor.py::test_extract_resume_retries_3x_then_raises` — mock `ValidationError` on every call; assert 3 attempts then raises | `uv run pytest tests/test_resume_extractor.py -k retries_3x` | D-15, D-16 |
| unit | `test_profile.py::test_upload_422_extraction_failed_after_retries` — mock `extract_resume` to raise; assert 422 `extraction_failed` | `uv run pytest tests/test_profile.py -k 422_extraction_failed` | D-16, D-35, D-36 #7 |

### PROF-04 — Reviewable diff response

| Gate | Coverage criterion | Tooling | Maps to |
|------|--------------------|---------|---------|
| static | `SkillDiffItem` Pydantic model with `name`, `source: Literal["added","removed","unchanged"]`, `editable: bool` | `grep "class SkillDiffItem" src/job_rag/services/profile.py` | D-17 |
| static | `ResumeUploadResponse` includes `extracted`, `skills_diff`, `prompt_version`, `extraction_id` | `grep "class ResumeUploadResponse" src/job_rag/api/routes.py` or `profile_schemas.py` | D-13 |
| unit | `test_profile.py::test_compute_skills_diff_classifies_correctly` — given known current + extracted, assert added/removed/unchanged buckets | `uv run pytest tests/test_profile.py -k compute_skills_diff` | D-17..D-20 |
| unit | `test_profile.py::test_compute_skills_diff_orders_added_first` — assert output order: added → removed → unchanged, each alphabetical | same | D-19 |
| unit | `test_profile.py::test_compute_skills_diff_normalizes_via_normalize_skill` — assert "Python" and "python" treated as unchanged | same | D-20 |
| integration | `POST /profile/upload` returns response with non-empty `skills_diff` for a fixture | `uv run pytest tests/test_profile.py -k upload_pdf_happy` (asserts shape) | D-17, D-18 |

### PROF-05 — Review panel UI

| Gate | Coverage criterion | Tooling | Maps to |
|------|--------------------|---------|---------|
| static | `frontend/src/components/profile/` directory exists with 6 files per D-29 | `ls frontend/src/components/profile/ \| wc -l` ≥ 6 | D-29 |
| static | `frontend/src/api/profile.ts` exports `uploadResume(file)` + `saveProfile(payload)` | `grep "uploadResume\|saveProfile" frontend/src/api/profile.ts` | D-29 |
| static | `frontend/src/routes/Profile.tsx` no longer renders `<PhasePlaceholder>` | `grep PhasePlaceholder frontend/src/routes/Profile.tsx` returns 0 matches | D-28 |
| static | OpenAPI snapshot regenerated post-backend land | `git diff --exit-code frontend/openapi.snapshot.json` after `npm run codegen:snapshot` returns 0 | §9 |
| vitest unit | `ProfileView.test.tsx` — renders read-only chips when profile is loaded | `cd frontend && npm test -- ProfileView` | D-28, D-29 |
| vitest unit | `ResumeUploader.test.tsx` — file input accepts .pdf/.docx; rejects .txt client-side; rejects > 2 MB client-side | `cd frontend && npm test -- ResumeUploader` | D-30 |
| vitest unit | `SkillDiffChip.test.tsx` — added chip shows green pill + Pencil; removed shows red; unchanged shows muted; Enter saves edit; Esc cancels | `cd frontend && npm test -- SkillDiffChip` | D-24, D-26 |
| vitest unit | `ReviewPanel.test.tsx` — sticky footer; live summary "Save (3 new · 2 keep removed · 47 unchanged)" updates on tick | `cd frontend && npm test -- ReviewPanel` | D-25, D-27 |
| vitest unit | `useResumeUpload.test.tsx` — upload mutation transitions idle→reviewing; save mutation invalidates ['profile'] and ['dashboard'] | `cd frontend && npm test -- useResumeUpload` | §11, D-29 |
| manual UAT | Upload sample resume → see chip list → untick one added → save → dashboard CV-vs-market score updates | screen-record this for the portfolio | PROF-05/06 cross-gate |

### PROF-06 — PATCH save + Langfuse trace

| Gate | Coverage criterion | Tooling | Maps to |
|------|--------------------|---------|---------|
| static | `PATCH /profile` endpoint registered in `src/job_rag/api/routes.py` with `Depends(require_api_key) + Depends(standard_limit) + Depends(get_current_user_id)` | `grep "patch.*profile" src/job_rag/api/routes.py` | D-21 |
| static | `UserProfileUpdate` Pydantic schema requires `skills`, optional others | `grep "class UserProfileUpdate" src/job_rag/api/routes.py` or `profile_schemas.py` | D-21 |
| unit | `test_profile.py::test_patch_replaces_skills_json` — PATCH with new skill list → DB column updated | `uv run pytest tests/test_profile.py -k patch_replaces_skills` | D-21 |
| unit | `test_profile.py::test_patch_none_fields_preserve_existing` — PATCH with `target_roles=None` → DB column unchanged | `uv run pytest tests/test_profile.py -k patch_none_preserves` | D-21 |
| unit | `test_profile.py::test_patch_returns_loaded_profile` — response body matches the post-update `UserSkillProfile` | same | D-22 |
| unit | `test_observability.py::test_resume_upload_trace_has_four_spans` — mock Langfuse client; assert spans `text_extract`, `llm_extract`, `diff_compute` emitted on upload; `profile_save` emitted on PATCH with matching `extraction_id` | `uv run pytest tests/test_observability.py -k resume_upload_trace` | D-32 |
| unit | `test_observability.py::test_resume_trace_does_not_capture_text` — assert no span metadata contains raw resume text | same | D-33 |
| unit | `test_observability.py::test_langfuse_fail_open_when_keys_missing` — patch settings to clear keys; upload still works without traces | same | observability fail-open pattern (Phase 1) |
| manual UAT | Langfuse dashboard shows a single `resume_upload` trace per upload with 4 spans; PATCH attaches `profile_save` span | manual: upload+save against staging with Langfuse keys; open Langfuse UI | D-32, REQ-PROF-06 success-criterion 5 |

### Gap not covered by D-36

- **D-36 #3 (413 oversized)** asserts the 413 status; it does NOT assert that the body was not fully read. **Add an explicit test** that the handler is never invoked when Content-Length declares > 2 MB (use a request-counter middleware or assert via `request.state.handler_invoked` set by a sentinel).
- **Frontend pre-check coverage**: D-36 lists 5 backend error paths but no frontend pre-check tests (client-side > 2 MB rejection, client-side .txt rejection). Add `ResumeUploader.test.tsx` cases for both per the Validation Architecture above.
- **Langfuse trace correlation across two HTTP calls**: not in D-36 (which is backend-route-only). Add `test_observability.py` cases per the table above.

## RESEARCH COMPLETE
