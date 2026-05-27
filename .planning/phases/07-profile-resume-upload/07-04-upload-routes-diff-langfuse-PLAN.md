---
phase: 07-profile-resume-upload
plan: 04
type: execute
wave: 2
depends_on: [02, 03]
files_modified:
  - src/job_rag/api/middleware.py
  - src/job_rag/api/app.py
  - src/job_rag/api/routes.py
  - src/job_rag/services/profile.py
  - src/job_rag/observability.py
  - tests/test_api.py
  - tests/test_profile.py
  - tests/test_observability.py
  - frontend/openapi.snapshot.json
  - frontend/src/api/types.ts
autonomous: true
requirements: [PROF-02, PROF-04, PROF-06]
requirements_addressed: [PROF-02, PROF-04, PROF-06]

must_haves:
  truths:
    - "POST /profile/upload accepts multipart/form-data (PDF or DOCX), returns ResumeUploadResponse with skills_diff"
    - "Oversized uploads (Content-Length > 2 MB) get 413 BEFORE the body is fully read (ASGI middleware)"
    - "Chunked-encoding (no Content-Length) uploads cap at 2 MB via mid-stream read loop, return 413"
    - ".txt and other unsupported types return 415 unsupported_file_type"
    - "Encrypted PDFs return 422 pdf_encrypted; under-100 char extractions return 422 text_extraction_failed"
    - "PATCH /profile replaces skills_json fully; None fields preserve existing values"
    - "GET /profile returns 200 + UserSkillProfile shape for the authenticated user"
    - "Langfuse trace per upload spans text_extract then llm_extract then diff_compute (plus profile_save on PATCH with matching extraction_id)"
    - "Langfuse traces do NOT capture raw resume text (PII redaction per D-33)"
    - "Langfuse fail-open: missing keys leave upload+save functional, just untraced"
    - "OpenAPI snapshot + frontend/src/api/types.ts regenerated post-backend land, including the GET /profile endpoint"
  artifacts:
    - path: "src/job_rag/api/middleware.py"
      provides: "ResumeUploadSizeGuard ASGI middleware (pre-body 413)"
      contains: "ResumeUploadSizeGuard"
    - path: "src/job_rag/api/routes.py"
      provides: "POST /profile/upload, PATCH /profile, and GET /profile handlers"
      contains: "/profile/upload"
    - path: "src/job_rag/services/profile.py"
      provides: "compute_skills_diff + SkillDiffItem + ResumeUploadResponse + UserProfileUpdate"
      contains: "def compute_skills_diff"
    - path: "src/job_rag/observability.py"
      provides: "get_langfuse_client helper (fail-open)"
      contains: "def get_langfuse_client"
    - path: "tests/test_profile.py"
      provides: "Backend tests covering upload, diff, PATCH paths"
      contains: "test_upload_pdf_happy_path"
    - path: "tests/test_api.py"
      provides: "GET /profile integration test"
      contains: "test_get_profile_returns_loaded_profile"
    - path: "frontend/openapi.snapshot.json"
      provides: "OpenAPI snapshot including ResumeUploadResponse + UserProfileUpdate + UserSkillProfile schemas"
  key_links:
    - from: "src/job_rag/api/app.py"
      to: "ResumeUploadSizeGuard middleware"
      via: "app.add_middleware(ResumeUploadSizeGuard)"
      pattern: "add_middleware.*ResumeUploadSizeGuard"
    - from: "POST /profile/upload handler"
      to: "asyncio.to_thread(extract_resume, text)"
      via: "Phase 1 D-05 async-from-sync wrap pattern"
      pattern: "asyncio.to_thread.*extract_resume"
    - from: "POST /profile/upload + PATCH /profile"
      to: "Langfuse trace correlation via extraction_id"
      via: "lf.trace(name='resume_upload', id=str(extraction_id))"
      pattern: "extraction_id"
    - from: "GET /profile"
      to: "load_profile(session, user_id=...)"
      via: "Phase 7 D-01/D-02 DB-backed read path"
      pattern: "await load_profile"
---

<objective>
Wire the resume upload + PATCH save endpoints, the GET /profile read endpoint, the pre-body size guard middleware, the skill-diff service, the Langfuse trace correlation across both endpoints, and the backend tests that prove every gate (PROF-02 / PROF-04 / PROF-06). After this plan lands, the backend is feature-complete for Phase 7 and the OpenAPI snapshot is regenerated so Plan 05's frontend can codegen against the new schemas.

Purpose: This is the integration plan. It composes the foundation (Plan 01: deps, settings, fixtures), the data layer (Plan 02: load_profile DB flip + seed), and the extraction primitive (Plan 03: extract_resume + ResumeExtraction model) into the three HTTP endpoints and the diff service that closes the loop. The Langfuse work is here because the spans straddle the route boundary (text_extract + llm_extract + diff_compute fire in /profile/upload; profile_save fires in PATCH /profile when the same extraction_id is supplied). GET /profile is also added here so the OpenAPI snapshot regen at the end of this plan ships a complete profile route surface (POST upload + PATCH save + GET read) that Plan 05 codegens against.
Output: 1 new middleware + 1 new service + 1 observability helper + 3 new routes (POST upload, PATCH save, GET read) + backend tests + 3 observability tests + 1 GET /profile test in tests/test_api.py + OpenAPI snapshot regen.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/07-profile-resume-upload/07-CONTEXT.md
@.planning/phases/07-profile-resume-upload/07-RESEARCH.md
@.planning/phases/07-profile-resume-upload/07-PATTERNS.md
@.planning/phases/07-profile-resume-upload/07-VALIDATION.md
@src/job_rag/api/app.py
@src/job_rag/api/routes.py
@src/job_rag/api/auth.py
@src/job_rag/api/deps.py
@src/job_rag/observability.py
@src/job_rag/services/matching.py
@src/job_rag/db/models.py
@src/job_rag/models.py
@src/job_rag/config.py

<interfaces>
From Plan 02:

    async def load_profile(session: AsyncSession, *, user_id: UUID | None = None) -> UserSkillProfile

From Plan 03:

    def extract_resume(text: str) -> tuple[ResumeExtraction, dict]   # @retry(stop_after_attempt(3))
    class ResumeExtraction(BaseModel)                                # uses min_salary_eur (not min_salary)

From Plan 01:

    settings.max_resume_size_bytes  # default 2_000_000

Existing helpers used by this plan:

    from job_rag.api.auth import get_current_user_id, require_api_key, standard_limit
    from job_rag.api.deps import get_session, Session  # Annotated[AsyncSession, Depends(get_session)]
    from job_rag.observability import is_enabled, _ensure_env, get_openai_client
    from job_rag.services.matching import _normalize_skill, load_profile

D-13 ResumeUploadResponse target shape (RESEARCH D-17 lines 116-127):

    class SkillDiffItem(BaseModel):
        name: str
        source: Literal["added", "removed", "unchanged"]
        editable: bool

    class ResumeUploadResponse(BaseModel):
        extracted: ResumeExtraction
        skills_diff: list[SkillDiffItem]
        prompt_version: str
        extraction_id: UUID

D-21 UserProfileUpdate target shape:

    class UserProfileUpdate(BaseModel):
        skills: list[UserSkill]                            # REQUIRED — replaces fully
        target_roles: list[str] | None = None              # None = no change
        preferred_locations: list[str] | None = None
        min_salary_eur: int | None = None
        remote_preference: RemotePolicy | None = None
        extraction_id: UUID | None = None                  # for Langfuse correlation

D-35 error taxonomy:

| Status | reason | trigger |
|--------|--------|---------|
| 413 | file_too_large       | Content-Length > 2_000_000 (pre-body) OR chunked > 2 MB |
| 415 | unsupported_file_type| extension not in {.pdf, .docx} OR Content-Type mismatch |
| 422 | pdf_encrypted        | pypdf.errors.PdfReadError raised                        |
| 422 | text_extraction_failed | extracted text < 100 non-whitespace chars             |
| 422 | extraction_failed    | tenacity exhausted 3 retries (ValidationError)          |
| 422 | empty_skills         | extraction returned 0 skills                            |
| 503 | llm_unavailable      | openai.APIError family                                  |
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → API → upload handler | Untrusted file bytes arrive over the wire; size + type must be gated BEFORE arbitrary code runs against the bytes |
| extracted text → LLM → Langfuse trace | LLM input/output flows through observability; raw resume text must not enter trace storage (PII) |
| PATCH body → DB update | Untrusted skill-name list reaches UPDATE user_profile; safe via parameter binding |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-02 | Denial of Service | POST /profile/upload | mitigate | ResumeUploadSizeGuard middleware reads Content-Length BEFORE the body is materialized; rejects > 2 MB with 413. Fallback: chunked-encoded uploads cap at 2 MB via read_with_cap loop, abort mid-stream. Validated by test_upload_413_oversized_content_length (07-04-01) and test_upload_413_chunked_streaming (07-04-02). |
| T-07-05 | Spoofing (content-type bypass) | POST /profile/upload | mitigate | Whitelist = `Path(filename).suffix.lower() in {".pdf", ".docx"}` AND `Content-Type in {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}`; rejects with 415. No magic-byte sniff (libmagic native dep overkill for two file types). Validated by test_upload_415_txt_file_rejected (07-04-03). |
| T-07-06 | Tampering (PATCH scope) | PATCH /profile | mitigate | Pydantic enforces `skills` is REQUIRED; other fields default to None and use `if v is not None: updates[col] = v` to preserve existing DB values. Validated by test_patch_replaces_skills_json (07-04-12) and test_patch_none_fields_preserve_existing (07-04-13). |
| T-07-07 | Information disclosure (PII in traces) | Langfuse observability | mitigate | text_extract span metadata holds only {char_count, page_count, file_type} — NEVER text itself. llm_extract auto-captured input is post-processed via `lf.update_current_observation(input={"text": f"[REDACTED — char_count={n}]"})` per RESEARCH §6 lines 324-329. Skill names + salary remain traced (operational signal, not PII). Validated by test_resume_trace_does_not_capture_text (07-04-16). |
| T-07-08 | Availability (Langfuse outage) | observability fail-open | mitigate | get_langfuse_client returns None when keys missing; every call site guards with `if lf:` so trace failures NEVER break the upload/save flow. Mirrors get_openai_client pattern. Validated by test_langfuse_fail_open_when_keys_missing (07-04-17). |
</threat_model>

<tasks>

<task type="auto" id="07-04-01" tdd="true">
  <name>Task 1: middleware + profile service (compute_skills_diff + Pydantic schemas) + Langfuse helper</name>
  <files>src/job_rag/api/middleware.py, src/job_rag/api/app.py, src/job_rag/services/profile.py, src/job_rag/observability.py, tests/test_profile.py</files>
  <read_first>
    - src/job_rag/api/app.py (existing CORSMiddleware wiring — middleware ordering)
    - src/job_rag/api/auth.py (lines 101-131 — RateLimiter callable-class shape, conceptually closest to middleware)
    - src/job_rag/services/matching.py (lines 38-40 — `_normalize_skill` to import)
    - src/job_rag/observability.py (lines 24-54 — `is_enabled`, `_ensure_env`, `get_openai_client` factory pattern)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §2 lines 56-108 (middleware shape + fallback)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §6 lines 272-329 (Langfuse client + PII redaction)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §8 lines 364-403 (compute_skills_diff)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §3 lines 145-181 (compute_skills_diff canonical)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §4 lines 185-233 (middleware canonical)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §10 lines 477-528 (get_langfuse_client canonical)
  </read_first>
  <behavior>
    - compute_skills_diff classifies skills as added/removed/unchanged via _normalize_skill equality
    - Diff output ordered: added (alphabetical) then removed (alphabetical) then unchanged (alphabetical) per D-19
    - "Python" vs "python" treated as unchanged via _normalize_skill case-folding
    - ResumeUploadSizeGuard returns 413 JSON before call_next when Content-Length > max_resume_size_bytes for POST /profile/upload
    - Other paths and non-POST requests pass through to call_next untouched
    - get_langfuse_client returns None when langfuse keys missing; returns Langfuse instance when set
  </behavior>
  <action>
**Step A — Create `src/job_rag/api/middleware.py`** per RESEARCH §2 and PATTERNS §4. The module exports `ResumeUploadSizeGuard(BaseHTTPMiddleware)`. The `dispatch` method MUST:
- Match `request.url.path == "/profile/upload"` AND `request.method == "POST"`
- Read `request.headers.get("content-length")`; if present and `int(cl) > settings.max_resume_size_bytes`, return `JSONResponse(status_code=413, content={"detail": {"reason": "file_too_large", "message": "Resume must be <=2 MB."}})`
- Wrap `int(cl)` in `try/except ValueError` (defensive — bogus header → treat as 0 → flow through to handler)
- Emit `log.warning("resume_upload_rejected_oversized", content_length=cl_int, cap=settings.max_resume_size_bytes)` on the reject path
- For all other paths/methods: `return await call_next(request)` unchanged

Imports needed:
- `from starlette.middleware.base import BaseHTTPMiddleware`
- `from starlette.responses import JSONResponse`
- `from starlette.requests import Request`
- `from job_rag.config import settings`
- `from job_rag.logging import get_logger`

**Step B — Wire middleware in `src/job_rag/api/app.py`:**

Add `from job_rag.api.middleware import ResumeUploadSizeGuard` near the existing CORS import. Add `app.add_middleware(ResumeUploadSizeGuard)` ABOVE the existing CORSMiddleware registration (per PATTERNS §4 line 233 — order matters; CORS preflight OPTIONS must still flow through CORS handling, but the size guard only fires on POST /profile/upload, so OPTIONS bypasses cleanly).

**Step C — Create `src/job_rag/services/profile.py`** per PATTERNS §3. Module shape:

    """Profile diff service (Phase 7 D-17..D-20)."""

    from typing import Literal
    from uuid import UUID

    from pydantic import BaseModel, Field

    from job_rag.models import RemotePolicy, ResumeExtraction, UserSkill, UserSkillProfile
    from job_rag.services.matching import _normalize_skill


    class SkillDiffItem(BaseModel):
        name: str
        source: Literal["added", "removed", "unchanged"]
        editable: bool


    class ResumeUploadResponse(BaseModel):
        extracted: ResumeExtraction
        skills_diff: list[SkillDiffItem]
        prompt_version: str
        extraction_id: UUID


    class UserProfileUpdate(BaseModel):
        skills: list[UserSkill]
        target_roles: list[str] | None = None
        preferred_locations: list[str] | None = None
        min_salary_eur: int | None = None
        remote_preference: RemotePolicy | None = None
        extraction_id: UUID | None = Field(default=None, description="Langfuse correlation token (D-21)")


    def compute_skills_diff(
        current: UserSkillProfile, extracted_skills: list[UserSkill]
    ) -> list[SkillDiffItem]:
        """Diff extracted skills against current profile (D-17..D-20).

        Two skills are 'the same' iff _normalize_skill(a) == _normalize_skill(b).
        Output ordering: added (alphabetical) then removed (alphabetical) then unchanged (alphabetical).
        Casing: extracted for added/unchanged, current for removed.
        """
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

**Step D — Add `get_langfuse_client` to `src/job_rag/observability.py`** per PATTERNS §10. Append AFTER existing `get_openai_client`:

    @lru_cache(maxsize=1)
    def get_langfuse_client() -> Any | None:
        """Return a raw Langfuse client for manual span/trace creation (Phase 7 D-32).

        Fail-open: returns None when keys are missing — all callers MUST guard
        with `if lf:` before usage (mirrors get_langchain_callbacks fail-open).
        """
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

Add to `__all__` if present.

**Step E — Unit tests for compute_skills_diff (APPEND to `tests/test_profile.py`, NOT overwriting Plan 01 scaffold):**

    """Tests for the Phase 7 profile feature (PROF-01..06)."""

    from job_rag.models import RemotePolicy, UserSkill, UserSkillProfile
    from job_rag.services.profile import SkillDiffItem, compute_skills_diff


    def _profile(skill_names: list[str]) -> UserSkillProfile:
        return UserSkillProfile(skills=[UserSkill(name=n) for n in skill_names])


    def test_compute_skills_diff_classifies_correctly():
        current = _profile(["Python", "FastAPI", "Docker"])
        extracted = [UserSkill(name=n) for n in ["Python", "Rust", "FastAPI"]]
        diff = compute_skills_diff(current, extracted)
        sources = {item.name: item.source for item in diff}
        assert sources == {
            "Rust": "added",
            "Docker": "removed",
            "Python": "unchanged",
            "FastAPI": "unchanged",
        }


    def test_compute_skills_diff_orders_added_first():
        current = _profile(["B-old", "C-old"])
        extracted = [UserSkill(name=n) for n in ["A-new", "Z-new", "B-old"]]
        diff = compute_skills_diff(current, extracted)
        added_names = [d.name for d in diff if d.source == "added"]
        removed_names = [d.name for d in diff if d.source == "removed"]
        unchanged_names = [d.name for d in diff if d.source == "unchanged"]
        assert added_names == ["A-new", "Z-new"]
        assert removed_names == ["C-old"]
        assert unchanged_names == ["B-old"]
        sources_in_order = [item.source for item in diff]
        first_added = next(i for i, s in enumerate(sources_in_order) if s == "added")
        first_removed = next(i for i, s in enumerate(sources_in_order) if s == "removed")
        first_unchanged = next(i for i, s in enumerate(sources_in_order) if s == "unchanged")
        assert first_added < first_removed < first_unchanged


    def test_compute_skills_diff_normalizes_via_normalize_skill():
        current = _profile(["Python", "FastAPI"])
        extracted = [UserSkill(name="python"), UserSkill(name="fast api")]
        diff = compute_skills_diff(current, extracted)
        sources = {item.name: item.source for item in diff}
        assert all(s == "unchanged" for s in sources.values()), sources

Run: `uv run pytest tests/test_profile.py -k compute_skills_diff -x`. Expected: 3 green.
  </action>
  <verify>
    <automated>uv run python -c "from job_rag.api.middleware import ResumeUploadSizeGuard; from job_rag.services.profile import compute_skills_diff, SkillDiffItem, ResumeUploadResponse, UserProfileUpdate; from job_rag.observability import get_langfuse_client; print('OK')" &amp;&amp; uv run pytest tests/test_profile.py -k compute_skills_diff -x &amp;&amp; uv run pyright src/job_rag/api/middleware.py src/job_rag/services/profile.py src/job_rag/observability.py</automated>
  </verify>
  <acceptance_criteria>
    - `from job_rag.api.middleware import ResumeUploadSizeGuard` imports cleanly
    - `from job_rag.services.profile import compute_skills_diff, SkillDiffItem, ResumeUploadResponse, UserProfileUpdate` imports cleanly (VALIDATION 07-04-09 schema gates)
    - `get_langfuse_client()` returns None when langfuse keys are NOT in env; returns Langfuse instance when set
    - `uv run pytest tests/test_profile.py -k compute_skills_diff_classifies` passes (VALIDATION 07-04-09)
    - `uv run pytest tests/test_profile.py -k compute_skills_diff_orders` passes (VALIDATION 07-04-10)
    - `uv run pytest tests/test_profile.py -k compute_skills_diff_normalizes` passes (VALIDATION 07-04-11)
    - `pyright src/` exits 0
    - `grep -E "ResumeUploadSizeGuard" src/job_rag/api/app.py` confirms middleware wired
  </acceptance_criteria>
  <done>
    - 4 modified/new source files committed
    - 3 diff tests green
  </done>
</task>

<task type="auto" id="07-04-02" tdd="true">
  <name>Task 2: POST /profile/upload route handler + ResumeUploadSizeGuard validation + upload tests</name>
  <files>src/job_rag/api/routes.py, tests/test_profile.py</files>
  <read_first>
    - src/job_rag/api/routes.py (existing /match handler lines 171-200 for Depends pattern; existing /ingest handler lines 477-528 for UploadFile pattern)
    - src/job_rag/api/auth.py (get_current_user_id, require_api_key, standard_limit — line refs in PATTERNS §"Shared Patterns")
    - src/job_rag/services/profile.py (just created in Task 1 — imports `compute_skills_diff`, `ResumeUploadResponse`, `SkillDiffItem`)
    - src/job_rag/services/matching.py (post-Plan-02 `load_profile`)
    - src/job_rag/extraction/resume_extractor.py (from Plan 03)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §2 lines 85-99 (chunked fallback `read_with_cap`)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §6 lines 286-329 (Langfuse trace wiring + PII redaction)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §7 lines 342-412 (route patterns)
    - tests/fixtures/sample-resume.pdf, sample-resume.docx, encrypted-sample.pdf, empty-text-sample.pdf (Plan 01 fixtures)
  </read_first>
  <behavior>
    - POST /profile/upload accepts UploadFile, returns 200 + ResumeUploadResponse for valid PDF/DOCX
    - 413 file_too_large fires PRE-BODY for Content-Length > 2 MB (middleware-level); fires MID-STREAM for chunked > 2 MB (handler-level read loop)
    - 415 unsupported_file_type for non-{pdf,docx} extension or wrong Content-Type
    - 422 pdf_encrypted on pypdf.errors.PdfReadError
    - 422 text_extraction_failed when extracted text < 100 non-whitespace chars
    - 422 extraction_failed when tenacity exhausts 3 retries (ValidationError)
    - 422 empty_skills when extraction returns 0 skills
    - 503 llm_unavailable on openai.APIError family
    - Langfuse trace per upload: 3 spans (text_extract, llm_extract auto-captured, diff_compute); raw resume text never appears in trace metadata; missing keys = fail-open no-op
  </behavior>
  <action>
**Step A — Implement POST /profile/upload in `src/job_rag/api/routes.py`** (insert below the existing `/agent/stream` block per CONTEXT D-Discretion line 299):

    @router.post(
        "/profile/upload",
        dependencies=[Depends(require_api_key), Depends(standard_limit)],
        response_model=ResumeUploadResponse,
    )
    async def upload_resume(
        file: UploadFile,
        session: Session,
        user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    ) -> ResumeUploadResponse:
        """POST /profile/upload — PDF/DOCX -> Instructor extraction -> skill diff (PROF-02..04)."""
        extraction_id = uuid.uuid4()

        # Type whitelist (D-08, T-07-05)
        filename = file.filename or ""
        suffix = Path(filename).suffix.lower()
        ctype = file.content_type or ""
        ALLOWED = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        if suffix not in ALLOWED or ctype != ALLOWED[suffix]:
            log.warning("resume_upload_failed", reason="unsupported_file_type",
                        filename=filename, content_type=ctype)
            raise HTTPException(status_code=415, detail={
                "reason": "unsupported_file_type",
                "message": "Upload a PDF or DOCX.",
            })

        # Chunked-encoding fallback for D-07 (no Content-Length header case)
        cap = settings.max_resume_size_bytes
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                log.warning("resume_upload_failed", reason="file_too_large",
                            bytes_read=total, cap=cap)
                raise HTTPException(status_code=413, detail={
                    "reason": "file_too_large",
                    "message": "Resume must be <=2 MB.",
                })
            chunks.append(chunk)
        raw = b"".join(chunks)

        lf = get_langfuse_client()
        trace = None
        if lf:
            trace = lf.trace(
                name="resume_upload",
                id=str(extraction_id),
                user_id=str(user_id),
                tags=["resume", "phase-7"],
            )

        # text_extract span (D-32 #1)
        text_extract_start = time.perf_counter()
        try:
            if suffix == ".pdf":
                text = await asyncio.to_thread(_extract_pdf_text, raw)
                file_type = "pdf"
                page_count = _pdf_page_count(raw)
            else:  # .docx
                text = await asyncio.to_thread(_extract_docx_text, raw)
                file_type = "docx"
                page_count = None
        except pypdf.errors.PdfReadError:
            log.warning("resume_upload_failed", reason="pdf_encrypted")
            raise HTTPException(status_code=422, detail={
                "reason": "pdf_encrypted",
                "message": "Remove the password and try again.",
            })
        except Exception:
            log.exception("resume_upload_failed", reason="text_extraction_failed")
            raise HTTPException(status_code=422, detail={
                "reason": "text_extraction_failed",
                "message": "Could not read the file.",
            })
        text_extract_ms = int((time.perf_counter() - text_extract_start) * 1000)

        if len(text.strip()) < 100:
            log.warning("resume_upload_failed", reason="text_extraction_failed",
                        char_count=len(text.strip()))
            raise HTTPException(status_code=422, detail={
                "reason": "text_extraction_failed",
                "message": "The file appears to be a scanned image. v1 doesn't support OCR.",
            })

        # D-11: cap text at 50 KB pre-LLM
        if len(text) > 50_000:
            log.warning("resume_text_truncated", original_chars=len(text), truncated_chars=50_000)
            text = text[:50_000]

        if trace:
            # T-07-07: metadata only — NO raw text
            trace.span(name="text_extract").end(metadata={
                "file_type": file_type,
                "char_count": len(text),
                "page_count": page_count,
                "latency_ms": text_extract_ms,
            })

        # llm_extract span auto-captured by langfuse.openai wrapper; we redact post-call (T-07-07)
        try:
            extraction, usage_info = await asyncio.to_thread(extract_resume, text)
        except ValidationError:
            log.exception("resume_extraction_failed", attempts=3)
            raise HTTPException(status_code=422, detail={
                "reason": "extraction_failed",
                "message": "The agent could not parse the resume. Try again or simplify the formatting.",
            })
        except openai.APIError:
            log.exception("resume_upload_failed", reason="llm_unavailable")
            raise HTTPException(status_code=503, detail={
                "reason": "llm_unavailable",
                "message": "The LLM is down. Try again later.",
            })

        if not extraction.skills:
            raise HTTPException(status_code=422, detail={
                "reason": "empty_skills",
                "message": "No skills found. Is this a resume?",
            })

        # Redact LLM span input (PII) — D-33
        if lf:
            try:
                lf.update_current_observation(input={"text": f"[REDACTED — char_count={len(text)}]"})
            except Exception:
                pass  # fail-open

        # diff_compute span (D-32 #3)
        diff_start = time.perf_counter()
        current = await load_profile(session, user_id=user_id)
        skills_diff = compute_skills_diff(current, extraction.skills)
        diff_ms = int((time.perf_counter() - diff_start) * 1000)
        if trace:
            trace.span(name="diff_compute").end(metadata={
                "added_count": sum(1 for d in skills_diff if d.source == "added"),
                "removed_count": sum(1 for d in skills_diff if d.source == "removed"),
                "unchanged_count": sum(1 for d in skills_diff if d.source == "unchanged"),
                "latency_ms": diff_ms,
            })

        log.info("resume_skills_extracted", skills_count=len(extraction.skills),
                 added=sum(1 for d in skills_diff if d.source == "added"))

        return ResumeUploadResponse(
            extracted=extraction,
            skills_diff=skills_diff,
            prompt_version=RESUME_PROMPT_VERSION,
            extraction_id=extraction_id,
        )

**Step B — Helper functions INLINE in routes.py (D-CHECKER-FIX-3: helper location is fixed inline; `files_modified` already lists `src/job_rag/api/routes.py` exclusively for these helpers):**

    def _extract_pdf_text(raw: bytes) -> str:
        reader = pypdf.PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise pypdf.errors.PdfReadError("encrypted")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)


    def _pdf_page_count(raw: bytes) -> int:
        try:
            return len(pypdf.PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            return 0


    def _extract_docx_text(raw: bytes) -> str:
        doc = docx.Document(io.BytesIO(raw))
        parts: list[str] = []
        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text)
        for table in doc.tables:
            for row in table.rows:
                parts.append("\t".join(cell.text for cell in row.cells))
        return "\n".join(parts)

Imports to ADD at top of routes.py:

    import asyncio
    import io
    import time
    import uuid
    from typing import Any

    import docx
    import openai
    import pypdf
    from pydantic import ValidationError

    from job_rag.extraction.resume_extractor import extract_resume
    from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION
    from job_rag.observability import get_langfuse_client
    from job_rag.services.matching import load_profile
    from job_rag.services.profile import (
        ResumeUploadResponse,
        SkillDiffItem,
        compute_skills_diff,
    )

(PATCH-only / GET-only imports — `json`, `sqlalchemy.func`/`update`, `UserSkillProfile`, `UserProfileUpdate` — are added in Task 3.)

**Step C — Write the upload tests in `tests/test_profile.py`** (APPEND to existing test file). Use FastAPI's `TestClient` or `httpx.AsyncClient` (whichever existing tests use — match `tests/test_api.py` style). Add 7 tests:

- `test_upload_pdf_happy_path(client, sample_resume_pdf)` — POST multipart with valid PDF bytes; expect 200; response has `skills_diff` list with at least one item; `extraction_id` is a valid UUID
- `test_upload_docx_happy_path(client, sample_resume_docx)` — same for DOCX
- `test_upload_413_oversized_content_length(client)` — send POST with `Content-Length: 3000000` header and a tiny body; expect 413; assert handler NOT invoked (use a request-state counter pattern OR assert via log absence using `caplog`). Use `client.post("/profile/upload", headers={"Content-Length": "3000000"}, content=b"x" * 100)` — note: many test clients overwrite Content-Length; use httpx `Request` directly + `client.send` to bypass auto-Content-Length, OR test the middleware directly via `from starlette.applications import Starlette` mounting an instance and calling it
- `test_upload_413_chunked_streaming(client)` — submit a `Transfer-Encoding: chunked` body > 2 MB (via httpx async stream generator); expect 413 mid-stream. Use `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` with `request = client.build_request("POST", "/profile/upload", headers={"Transfer-Encoding": "chunked"}, content=<async generator yielding > 2 MB>)` then `await client.send(request)`
- `test_upload_415_txt_file_rejected(client)` — POST `text/plain` file with `.txt` extension; expect 415 `{"reason": "unsupported_file_type"}`
- `test_upload_422_encrypted_pdf(client, encrypted_resume_pdf)` — expect 422 `{"reason": "pdf_encrypted"}`
- `test_upload_422_empty_text_pdf(client, empty_text_resume_pdf)` — expect 422 `{"reason": "text_extraction_failed"}`
- `test_upload_422_extraction_failed(client, sample_resume_pdf, monkeypatch)` — monkeypatch `job_rag.api.routes.extract_resume` to raise `ValidationError`; expect 422 `{"reason": "extraction_failed"}`

Use existing test infrastructure patterns from `tests/test_api.py` for `client` fixture + `db_session` fixture.

Run tests after writing:

    uv run pytest tests/test_profile.py -k 'upload_pdf_happy or upload_docx_happy or 413_oversized or 413_chunked or 415_txt or 422_encrypted or 422_empty_text or 422_extraction_failed' -x -v
  </action>
  <verify>
    <automated>uv run pytest tests/test_profile.py -k 'upload_pdf_happy or upload_docx_happy or 413_oversized or 413_chunked or 415_txt or 422_encrypted or 422_empty_text or 422_extraction_failed' -x &amp;&amp; uv run pyright src/job_rag/api/routes.py</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest tests/test_profile.py -k upload_pdf_happy_path -x` passes (VALIDATION 07-04-07)
    - `uv run pytest tests/test_profile.py -k upload_docx_happy_path -x` passes (VALIDATION 07-04-08)
    - `uv run pytest tests/test_profile.py -k 413_oversized_content_length -x` passes (VALIDATION 07-04-01)
    - `uv run pytest tests/test_profile.py -k 413_chunked_streaming -x` passes (VALIDATION 07-04-02)
    - `uv run pytest tests/test_profile.py -k 415_txt_file_rejected -x` passes (VALIDATION 07-04-03)
    - `uv run pytest tests/test_profile.py -k 422_encrypted_pdf -x` passes (VALIDATION 07-04-04)
    - `uv run pytest tests/test_profile.py -k 422_empty_text_pdf -x` passes (VALIDATION 07-04-05)
    - `uv run pytest tests/test_profile.py -k 422_extraction_failed -x` passes (VALIDATION 07-04-06)
    - `grep -E '@router\.post.*"/profile/upload"' src/job_rag/api/routes.py` confirms the POST route declaration
    - `pyright src/job_rag/api/routes.py` exits 0
  </acceptance_criteria>
  <done>
    - 8 backend tests green (2 happy paths + 6 error paths) for the upload endpoint
    - routes.py has POST /profile/upload wired through standard_limit + get_current_user_id + ResumeUploadSizeGuard middleware
    - Inline _extract_pdf_text / _pdf_page_count / _extract_docx_text helpers in routes.py
  </done>
</task>

<task type="auto" id="07-04-03" tdd="true">
  <name>Task 3: PATCH /profile + GET /profile route handlers + PATCH/GET tests</name>
  <files>src/job_rag/api/routes.py, tests/test_profile.py, tests/test_api.py</files>
  <read_first>
    - src/job_rag/api/routes.py (post-Task-2: includes POST /profile/upload + inline text helpers)
    - src/job_rag/services/matching.py (post-Plan-02 `load_profile` signature)
    - src/job_rag/services/profile.py (Task 1: UserProfileUpdate model)
    - src/job_rag/db/models.py (UserProfileDB columns lines 118-147)
    - src/job_rag/models.py (UserSkillProfile shape)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §7 lines 332-362 (PATCH None-as-no-change semantics)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §7 lines 342-412 (route patterns)
    - tests/test_api.py (existing test style — fixture imports, request shape)
  </read_first>
  <behavior>
    - PATCH /profile replaces skills_json entirely; None fields preserve existing values; returns the reloaded UserSkillProfile
    - GET /profile returns 200 + UserSkillProfile shape for the authenticated user (PROF-01 read path via load_profile)
    - Langfuse profile_save span fires on PATCH when extraction_id matches a prior upload (D-32 #4); fail-open if Langfuse keys missing
  </behavior>
  <action>
**Step A — Implement PATCH /profile in `src/job_rag/api/routes.py`** per RESEARCH §7 (insert directly below the POST /profile/upload handler from Task 2):

    @router.patch(
        "/profile",
        dependencies=[Depends(require_api_key), Depends(standard_limit)],
        response_model=UserSkillProfile,
    )
    async def update_profile(
        session: Session,
        payload: UserProfileUpdate,
        user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    ) -> UserSkillProfile:
        """PATCH /profile — replace skills, None means no change (D-21)."""
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

        # profile_save Langfuse span — only if extraction_id provided (D-32 #4)
        lf = get_langfuse_client()
        if lf and payload.extraction_id:
            try:
                trace = lf.trace(id=str(payload.extraction_id))
                trace.span(name="profile_save").end(metadata={
                    "written_skill_count": len(payload.skills),
                })
            except Exception:
                pass  # fail-open

        log.info("profile_saved", user_id=str(user_id), skill_count=len(payload.skills))
        return await load_profile(session, user_id=user_id)

**Step B — Implement GET /profile in `src/job_rag/api/routes.py`** (insert below the PATCH /profile handler). 5-line handler that delegates to the now-DB-backed load_profile from Plan 02:

    @router.get(
        "/profile",
        dependencies=[Depends(require_api_key), Depends(standard_limit)],
        response_model=UserSkillProfile,
    )
    async def get_profile(
        session: Session,
        user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    ) -> UserSkillProfile:
        """GET /profile — return the authenticated user's profile (PROF-01)."""
        return await load_profile(session, user_id=user_id)

**Step C — Add the remaining imports at the top of routes.py** (POST imports already added in Task 2; this task adds the PATCH/GET-specific ones):

    import json

    from sqlalchemy import func, update

    from job_rag.db.models import UserProfileDB
    from job_rag.models import UserSkillProfile
    from job_rag.services.profile import UserProfileUpdate

**Step D — Write the PATCH tests in `tests/test_profile.py`** (APPEND to upload tests from Task 2). 3 tests:

- `test_patch_replaces_skills_json(client, db_session)` — PATCH with `{"skills": [{"name": "NewSkill"}]}`; query DB; assert `skills_json` updated
- `test_patch_none_fields_preserve_existing(client, db_session)` — capture pre-PATCH `target_roles_json`; PATCH without `target_roles`; query DB; assert unchanged
- `test_patch_returns_loaded_profile(client)` — assert response body matches `UserSkillProfile` shape and includes updated skills

**Step E — Write the GET test in `tests/test_api.py`** (APPEND to existing test file — `test_api.py` is the canonical home for route-level happy-path integration tests per the existing convention). 1 test:

- `test_get_profile_returns_loaded_profile(client, db_session)` — seed the user_profile row via the Plan 02 seed migration (already auto-run by `init_db()`); GET /profile; assert 200; assert response JSON has `skills`, `target_roles`, `preferred_locations`, `min_salary` / `min_salary_eur` (whichever the canonical UserSkillProfile field is — verify against `src/job_rag/models.py`), `remote_preference` keys; assert `skills` is a non-empty list containing skill objects with `name` field matching the seed values

Skeleton:

    def test_get_profile_returns_loaded_profile(client):
        resp = client.get("/profile")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "skills" in body
        assert isinstance(body["skills"], list)
        assert len(body["skills"]) > 0
        # Confirm shape matches UserSkillProfile model
        assert "target_roles" in body
        assert "preferred_locations" in body
        assert "remote_preference" in body
        # Confirm first skill has the expected sub-shape
        first = body["skills"][0]
        assert "name" in first

Run tests after writing:

    uv run pytest tests/test_profile.py -k 'patch_replaces or patch_none or patch_returns' -x -v
    uv run pytest tests/test_api.py -k 'get_profile_returns_loaded_profile' -x -v
  </action>
  <verify>
    <automated>uv run pytest tests/test_profile.py -k 'patch_replaces or patch_none or patch_returns' -x &amp;&amp; uv run pytest tests/test_api.py -k 'get_profile_returns_loaded_profile' -x &amp;&amp; uv run pyright src/job_rag/api/routes.py</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest tests/test_profile.py -k patch_replaces_skills_json -x` passes (VALIDATION 07-04-12)
    - `uv run pytest tests/test_profile.py -k patch_none_fields_preserve -x` passes (VALIDATION 07-04-13)
    - `uv run pytest tests/test_profile.py -k patch_returns_loaded_profile -x` passes (VALIDATION 07-04-14)
    - `uv run pytest tests/test_api.py -k get_profile_returns_loaded_profile -x` passes
    - `grep -E '@router\.patch.*"/profile"' src/job_rag/api/routes.py` shows the PATCH route declaration
    - `grep -E '@router\.get.*"/profile"' src/job_rag/api/routes.py` shows the GET route declaration
    - `pyright src/job_rag/api/routes.py` exits 0
  </acceptance_criteria>
  <done>
    - 3 PATCH tests + 1 GET test all green
    - routes.py has PATCH /profile and GET /profile wired through standard_limit + get_current_user_id
    - Both endpoints share the response_model=UserSkillProfile contract
  </done>
</task>

<task type="auto" id="07-04-04" tdd="true">
  <name>Task 4: Langfuse trace tests + OpenAPI snapshot regen</name>
  <files>tests/test_observability.py, frontend/openapi.snapshot.json, frontend/src/api/types.ts</files>
  <read_first>
    - tests/test_observability.py (existing — APPEND mode per Plan 01)
    - src/job_rag/observability.py (post-Task-1: includes get_langfuse_client)
    - src/job_rag/api/routes.py (post-Task-2 + Task-3: includes upload + PATCH + GET with trace wiring)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §6 lines 286-329 (Langfuse trace structure + PII)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §9 lines 405-419 (codegen workflow)
    - .planning/phases/04-frontend-shell-auth/04-CONTEXT.md §D-14 (OpenAPI codegen workflow)
    - frontend/package.json (verify `codegen` + `codegen:snapshot` npm scripts exist)
  </read_first>
  <behavior>
    - test_resume_upload_trace_has_four_spans: mock get_langfuse_client to return a MagicMock; trigger upload + PATCH with matching extraction_id; assert mock.trace was called with name="resume_upload"; assert spans named text_extract, llm_extract (or auto-captured equivalent), diff_compute on upload + profile_save on PATCH
    - test_resume_trace_does_not_capture_text: spy on every span().end() metadata call; assert NO metadata kwargs contain the raw resume text string ("TEST FIXTURE" substring should NOT appear)
    - test_langfuse_fail_open_when_keys_missing: monkeypatch settings.langfuse_public_key + langfuse_secret_key to empty strings; upload still returns 200; no exceptions raised
    - OpenAPI snapshot includes ResumeUploadResponse, UserProfileUpdate, SkillDiffItem schemas AND surfaces the GET /profile endpoint definition
  </behavior>
  <action>
**Step A — Append Langfuse trace tests to `tests/test_observability.py`:**

    # Phase 7: resume_upload trace tests (D-32, D-33, T-07-07, T-07-08)

    import uuid
    from unittest.mock import MagicMock, patch

    import pytest


    @pytest.mark.asyncio
    async def test_resume_upload_trace_has_four_spans(
        client, sample_resume_pdf, db_session
    ):
        """D-32: trace has text_extract + llm_extract + diff_compute spans;
        PATCH adds profile_save when extraction_id matches."""
        mock_trace = MagicMock()
        mock_lf = MagicMock()
        mock_lf.trace.return_value = mock_trace

        with patch("job_rag.api.routes.get_langfuse_client", return_value=mock_lf):
            resp = client.post(
                "/profile/upload",
                files={"file": ("test.pdf", sample_resume_pdf, "application/pdf")},
            )
            assert resp.status_code == 200
            extraction_id = resp.json()["extraction_id"]

            # PATCH with matching extraction_id
            r2 = client.patch(
                "/profile",
                json={
                    "skills": [{"name": "Python"}],
                    "extraction_id": extraction_id,
                },
            )
            assert r2.status_code == 200

        span_names = [
            call.kwargs.get("name") or (call.args[0] if call.args else None)
            for call in mock_trace.span.call_args_list
        ]
        assert "text_extract" in span_names
        assert "diff_compute" in span_names
        assert "profile_save" in span_names


    @pytest.mark.asyncio
    async def test_resume_trace_does_not_capture_text(
        client, sample_resume_pdf
    ):
        """D-33 / T-07-07: raw resume text never appears in span metadata."""
        captured_metadata = []

        mock_trace = MagicMock()

        def _record_span(name=None, *args, **kwargs):
            span = MagicMock()

            def _end(metadata=None, **kw):
                if metadata:
                    captured_metadata.append(metadata)

            span.end.side_effect = _end
            return span

        mock_trace.span.side_effect = _record_span
        mock_lf = MagicMock()
        mock_lf.trace.return_value = mock_trace

        with patch("job_rag.api.routes.get_langfuse_client", return_value=mock_lf):
            resp = client.post(
                "/profile/upload",
                files={"file": ("test.pdf", sample_resume_pdf, "application/pdf")},
            )
            assert resp.status_code == 200

        # The fixture's text contains "TEST FIXTURE — synthetic data"
        for md in captured_metadata:
            for v in md.values():
                if isinstance(v, str):
                    assert "TEST FIXTURE" not in v, f"raw text leaked into trace: {md}"
                    assert "synthetic data" not in v, f"raw text leaked into trace: {md}"


    @pytest.mark.asyncio
    async def test_langfuse_fail_open_when_keys_missing(
        client, sample_resume_pdf, monkeypatch
    ):
        """T-07-08: upload still works when langfuse keys are missing."""
        monkeypatch.setattr("job_rag.config.settings.langfuse_public_key", "")
        monkeypatch.setattr("job_rag.config.settings.langfuse_secret_key", "")
        # Clear the lru_cache so the next get_langfuse_client call re-checks env
        from job_rag.observability import get_langfuse_client
        get_langfuse_client.cache_clear()

        resp = client.post(
            "/profile/upload",
            files={"file": ("test.pdf", sample_resume_pdf, "application/pdf")},
        )
        assert resp.status_code == 200, resp.text

Run: `uv run pytest tests/test_observability.py -k 'resume_upload_trace or resume_trace_does_not or langfuse_fail_open' -x`.

**Step B — Regenerate OpenAPI snapshot + frontend types** (now includes GET /profile from Task 3):

    cd frontend
    npm run codegen:snapshot   # writes openapi.snapshot.json from running backend
    npm run codegen            # regenerates frontend/src/api/types.ts from snapshot
    cd ..

Verify the snapshot now includes the new schemas AND the GET endpoint:

    grep -E '"ResumeUploadResponse"|"UserProfileUpdate"|"SkillDiffItem"' frontend/openapi.snapshot.json
    grep -E '"/profile":' frontend/openapi.snapshot.json
    # The /profile path should now have "get", "patch" methods declared

If `codegen:snapshot` requires the backend to be running, start it in a subshell:

    uv run uvicorn job_rag.api.app:app --port 8000 &
    BACKEND_PID=$!
    sleep 3
    cd frontend && npm run codegen:snapshot && npm run codegen && cd ..
    kill $BACKEND_PID

(Phase 4 D-14 — codegen workflow documented there; consult `frontend/package.json` for the actual script.)

Verify CI drift guard would pass: `cd frontend && git diff --exit-code openapi.snapshot.json` after regen returns 0 only if it MATCHES the running backend (which it must, since we just regenerated).

Commit:
- `frontend/openapi.snapshot.json`
- `frontend/src/api/types.ts`
  </action>
  <verify>
    <automated>uv run pytest tests/test_observability.py -k 'resume_upload_trace or resume_trace_does_not or langfuse_fail_open' -x &amp;&amp; grep -E '"ResumeUploadResponse"|"UserProfileUpdate"|"SkillDiffItem"' frontend/openapi.snapshot.json &amp;&amp; cd frontend &amp;&amp; npm run typecheck</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest tests/test_observability.py -k resume_upload_trace_has_four_spans -x` passes (VALIDATION 07-04-15)
    - `uv run pytest tests/test_observability.py -k resume_trace_does_not_capture_text -x` passes (VALIDATION 07-04-16)
    - `uv run pytest tests/test_observability.py -k langfuse_fail_open_when_keys_missing -x` passes (VALIDATION 07-04-17)
    - `frontend/openapi.snapshot.json` contains `ResumeUploadResponse`, `UserProfileUpdate`, `SkillDiffItem` schemas
    - `frontend/openapi.snapshot.json` includes the GET /profile endpoint (paths→/profile→get)
    - `frontend/src/api/types.ts` regenerated; `cd frontend && npm run typecheck` exits 0
    - Backend full suite passes: `uv run pytest tests/ -x`
  </acceptance_criteria>
  <done>
    - 3 Langfuse trace tests green
    - OpenAPI snapshot + types.ts committed; ready for Plan 05 codegen consumers
    - Backend Phase 7 work COMPLETE (POST upload + PATCH save + GET read all shipped + traced)
  </done>
</task>

</tasks>

<verification>
After all four tasks land, run from repo root:

```bash
# Static — modules importable
uv run python -c "from job_rag.api.middleware import ResumeUploadSizeGuard; from job_rag.services.profile import compute_skills_diff, ResumeUploadResponse, UserProfileUpdate, SkillDiffItem; from job_rag.observability import get_langfuse_client; print('OK')"

# Middleware wired in app.py
grep ResumeUploadSizeGuard src/job_rag/api/app.py

# Routes registered (POST, PATCH, GET)
grep -E '@router\.(post|patch|get).*"/profile' src/job_rag/api/routes.py

# Targeted backend tests
uv run pytest tests/test_profile.py -x
uv run pytest tests/test_api.py -k 'get_profile_returns_loaded_profile' -x
uv run pytest tests/test_observability.py -k 'resume_upload_trace or resume_trace_does_not or langfuse_fail_open' -x

# OpenAPI snapshot up-to-date (schemas + GET /profile path)
grep -E '"ResumeUploadResponse"|"UserProfileUpdate"|"SkillDiffItem"' frontend/openapi.snapshot.json

# Frontend typecheck (proves types.ts is valid)
cd frontend && npm run typecheck && cd ..

# Type safety
uv run pyright src/

# Full backend suite
uv run pytest tests/ -x
```

All commands must exit 0.
</verification>

<success_criteria>
- PROF-02, PROF-04, PROF-06 closed at the backend boundary
- PROF-01 GET read-path now reachable via GET /profile (foundation for Plan 05's frontend `getProfile()` consumer)
- All 5 STRIDE threats (T-07-02, T-07-05, T-07-06, T-07-07, T-07-08) mitigated with test coverage
- Frontend types.ts ready for Plan 05 consumption (includes GET /profile)
- 18 backend tests across `tests/test_profile.py` (11 = 3 diff + 8 upload error/happy paths from Task 2 + ... wait, let me recount: Task 1 = 3 diff, Task 2 = 8 upload, Task 3 = 3 PATCH = 14 in test_profile.py + 1 GET in test_api.py + 3 Langfuse in test_observability.py = 18 total) all green
</success_criteria>

<output>
After completion, create `.planning/phases/07-profile-resume-upload/07-04-SUMMARY.md` capturing:
- New route line counts (POST + PATCH + GET) in routes.py
- Confirmation that text-extract helpers were inlined in routes.py (no separate text_extract.py module — fixed per CHECKER-FIX-3)
- OpenAPI snapshot delta (lines added, including the GET /profile endpoint)
- Notable test client tricks needed for the 413 chunked test (httpx ASGITransport workaround or similar)
- Any deviations from VALIDATION's 17 listed gates with reason
- Note: this plan is now 4 tasks (foundation → POST upload → PATCH+GET → Langfuse+OpenAPI) split per CHECKER-FIX-2 to keep task scope sane
</output>
