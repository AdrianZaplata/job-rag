---
phase: 07-profile-resume-upload
verified: 2026-05-30T16:27:30Z
status: human_needed
score: 5/5 must-haves verified at code level
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "G-07-UAT-01: Langfuse SDK 3.x → 4.x migration (PROF-06 trace contract) — closed by Plan 07-06: 5 v3 call sites in routes.py rewritten to v4 start_as_current_observation; 2 new helpers (derive_langfuse_trace_id, redact_current_generation_input) in observability.py; tests/_langfuse_fake.py contract-faithful FakeLangfuseClient with v3-name AttributeError guard; 4 new TestResumeUploadV4Tracing tests assert exact span order + cross-request trace_id correlation + PII-redaction at BOTH generation AND trace levels"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Replay Live UAT Test 1 — upload a 1.5 MB PDF resume via the deployed UI with LANGFUSE_PUBLIC_KEY/SECRET_KEY set; inspect Langfuse dashboard for single trace per upload with 4 spans (text_extract, langfuse.openai auto-GENERATION, diff_compute, profile_save) correlated by derive_langfuse_trace_id(extraction_id); the raw resume text MUST NOT be visible in any span/trace input or metadata — expected '[REDACTED — char_count=N]' watermark instead"
    expected: "Single trace with parent resume_upload span + 3 explicit child spans + 1 auto-captured GENERATION; PATCH /profile attaches profile_save to the SAME trace via re-derived trace_id; trace root input AND generation input both show '[REDACTED — char_count=N]' (no name/email/phone/LinkedIn/GitHub/address leak)"
    why_human: "Closes G-07-UAT-01 — the original failure was discovered ONLY in the live Langfuse dashboard. Code-level FakeLangfuseClient tests prove the call shape against the v4 contract but cannot prove the deployed Langfuse Cloud renders the trace as expected. Reference: 07-HUMAN-UAT.md Test 1."
  - test: "Save a profile via the UI after upload, then refresh the Dashboard CV-vs-market widget"
    expected: "Dashboard widget reflects the new skill list within one re-render (TanStack cache invalidation propagates from save → dashboard)"
    why_human: "End-to-end UI flow requires running backend + frontend + DB; automated tests verify the invalidateQueries call but not the visible widget refresh"
  - test: "Upload a >2 MB file via the browser and observe DevTools Network panel"
    expected: "413 response returned BEFORE the full body is uploaded (Content-Length-based reject); body bytes transmitted < 2 MB cap"
    why_human: "Browser-side streaming behaviour cannot be observed reliably from automated tests — the middleware test asserts the 413 outcome but not the pre-body-streaming property"
  - test: "Upload a PDF that triggers an LLM cold-start, observe stepped status copy"
    expected: "Copy transitions 0-2s 'Reading…' → 2-10s 'Asking the agent…' → 10s+ 'Still working…' per D-31"
    why_human: "Requires real cold-start latency (set ACA min-replicas=0 + idle 5 min); fake-timer tests verify transitions in isolation but not the user-perceived experience"
  - test: "Inline-edit on an added chip (rename), save, refresh /profile"
    expected: "Renamed skill appears in ProfileView Badge list after refresh — proves the edited name persists through PATCH"
    why_human: "End-to-end persistence verification requires a running DB; component test asserts onRename callback but not the round-trip"
follow_ups:
  - id: WR-01
    severity: warning
    source: 07-06-REVIEW.md
    summary: "Fail-open path on start_as_current_observation failure re-runs the ENTIRE upload pipeline — can double-bill OpenAI extraction if failure originates in context manager __exit__ rather than __enter__. HTTPException is correctly excluded. Edge-case (only fires on a real trace-teardown exception); does not block PROF-06 contract."
    location: src/job_rag/api/routes.py:870-895
    recommendation: "Split trace-setup guard from pipeline-execution guard so only __enter__ failures fall through to the un-traced pipeline. Defer to Phase 8 housekeeping or 07.1 follow-up."
  - id: WR-02
    severity: warning
    source: 07-06-REVIEW.md
    summary: "tags=['resume','phase-7'] buried inside metadata kwarg instead of passed as the top-level tags= keyword the v4 SDK supports — Langfuse UI tag filter will not index the values. Behavioral regression vs the v3 lf.trace(tags=...) call. Trace correlation + PII redaction still work; this is a discoverability nit."
    location: src/job_rag/api/routes.py:875-880
    recommendation: "Pass tags=['resume','phase-7'] as a top-level kwarg to start_as_current_observation (or call lf.update_current_span(tags=[...]) immediately inside the context body)."
  - id: WR-03
    severity: warning
    source: 07-06-REVIEW.md
    summary: "derive_langfuse_trace_id fallback uses hashlib.blake2b(seed, 16) while Langfuse v4 SDK likely uses SHA-256 — the BLAKE2b 'parity' claim in the docstring is unverified. Invisible within a single process (lru_cache forces all callers to take the same branch), but a latent landmine if anything ever crosses process boundaries or if the test fallback diverges from prod."
    location: src/job_rag/observability.py:110-130
    recommendation: "Verify against installed langfuse 4.1.0 which hash the SDK uses; either match the algorithm exactly OR drop the parity claim from the docstring and document the fallback as in-process-only."
deprecation_warnings:
  - api: "Langfuse.set_current_trace_io(input=...)"
    location: src/job_rag/observability.py:156
    note: "Emits DeprecationWarning in langfuse 4.1.0 — Langfuse plans to replace with propagate_attributes(). KNOWINGLY retained because it's the only v4 way to override the TRACE-LEVEL input that langfuse.openai writes (the layer where the captured trace-c744bb2d...json export showed PII). Documented in plan 07-06 SUMMARY and 07-06-REVIEW.md. Migrate when Langfuse ships a non-deprecated trace-input setter."
---

# Phase 7: Profile & Resume Upload — Verification Report (Re-verification after gap closure)

**Phase Goal:** Phase 7 ships the personal-data loop when Adrian can upload a PDF or DOCX resume, see an Instructor-extracted skill diff vs his current profile in a reviewable panel, and tick/edit/save confirmed skills back to `user_profile` — with the full extract→review→save trace visible in Langfuse.

**Verified:** 2026-05-30T16:27:30Z
**Status:** human_needed
**Re-verification:** Yes — after Plan 07-06 (Langfuse SDK v4 migration) closed G-07-UAT-01

## Re-verification Summary

The 2026-05-28/29 verification surfaced **G-07-UAT-01**: live UAT proved truth #5 (Langfuse trace contract) was silently no-op'd in production because the code targeted Langfuse SDK 3.x while the installed library was 4.1.0. The 5 v3 call sites raised `AttributeError` which the T-07-08 fail-open `try/except` guards swallowed — so uploads succeeded but tracing AND PII redaction silently never happened. The captured `trace-c744bb2d0683a35da965946940e70bab.json` export showed a standalone OpenAI-generation trace with Adrian's full resume PII in `trace.input` (name, email, phone, LinkedIn, GitHub, address).

Plan 07-06 (commits `ad31379`, `3ffc244`, `82bb8d5`) closed G-07-UAT-01 by:

1. **5 v3 call sites in `routes.py` rewritten** to v4 `start_as_current_observation(name=..., as_type=..., trace_context={"trace_id": ...}, metadata=...)` context managers. The 4 spans (`resume_upload`, `text_extract`, `diff_compute`, `profile_save`) are now correlated across requests via `derive_langfuse_trace_id(extraction_id)` — a deterministic 32-hex hash that POST and PATCH both compute from the same seed.

2. **Two-layer PII redaction** via new `redact_current_generation_input(client, char_count)` helper in `observability.py`: `client.update_current_generation(input=REDACTED)` + `client.set_current_trace_io(input=REDACTED)`. The trace-level setter fixes the root cause captured in the live UAT export (PII was leaking at trace.input, not just at the generation-child level).

3. **Mock-based tests replaced by `FakeLangfuseClient`** in `tests/_langfuse_fake.py` — a contract-faithful fake that implements ONLY the v4 surface AND raises `AttributeError("Langfuse v3 API removed in v4: '{name}'")` on every known v3 method name (`trace`, `update_current_observation`, `span`). Closes the why-tests-passed gap: a future PR that accidentally writes a v3 method name will now break CI loudly, not silently no-op at runtime.

The 4 new tests in `TestResumeUploadV4Tracing` assert: exact span order on POST, cross-request trace_id correlation on PATCH, no resume PII in any recorded payload (both generation AND trace-level), v3 method calls would fail loudly. All pass.

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `data/profile.json` is no longer the read path; `load_profile(session, user_id)` hits the `user_profile` table (PROF-01) | VERIFIED | `src/job_rag/services/matching.py:16-54` shows async DB-backed `load_profile`; `grep -rn 'profile.json' src/` returns 0 matches; alembic 0006 seeds Adrian's row via `ON CONFLICT (user_id) DO NOTHING`; 3 load_profile tests + 3 alembic seed tests green |
| 2 | 1.5 MB PDF upload succeeds; >2 MB rejected with 413 BEFORE body fully read; DOCX accepted (PROF-02) | VERIFIED | `ResumeUploadSizeGuard` middleware in `src/job_rag/api/middleware.py` reads Content-Length pre-body; in-handler chunked fallback at `routes.py:660-680`; 8 upload tests green (PDF happy path + DOCX happy path + 413 oversized Content-Length + 413 chunked + 415 .txt + 422 encrypted + 422 empty-text + 422 extraction_failed) |
| 3 | Upload response shows reviewable diff split into added/removed/unchanged; UI renders as tick/untick chips with inline edit (PROF-03, PROF-04, PROF-05) | VERIFIED | `compute_skills_diff` in `src/job_rag/services/profile.py:84` returns ordered `SkillDiffItem[]`; `ResumeUploadResponse` returns `skills_diff`; `SkillDiffChip.tsx` renders D-24 status pills + Pencil edit on added items; `ReviewPanel.tsx` shows sticky footer with `Save profile (N skills)`; 25 frontend tests across 5 component spec files green |
| 4 | Save PATCHes user_profile; next CV-vs-market dashboard load reflects new skills (PROF-06) | VERIFIED (code-level) | `PATCH /profile` handler in `routes.py:898-968` writes `skills_json` and preserves None fields; `useResumeUpload.ts:52-53` calls `setQueryData(['profile'], profile)` AND `invalidateQueries({queryKey: ['dashboard']})`; 3 PATCH tests green. End-to-end widget refresh flagged for human verification |
| 5 | Langfuse trace shows a single trace per upload spanning extraction → Instructor → diff → (on save) PATCH (PROF-06) | VERIFIED (code-level, post-G-07-UAT-01 closure) | 4 v4 `start_as_current_observation(name=…)` calls confirmed at `routes.py:683` (text_extract), `744` (diff_compute), `871` (resume_upload parent), `950` (profile_save). 0 v3 patterns: `grep -rE "lf\.trace\(|trace\.span\(|update_current_observation\(" src/` returns no matches. Cross-request correlation via `derive_langfuse_trace_id(extraction_id)` derived in BOTH POST and PATCH. `redact_current_generation_input(lf, char_count=len(resume_text))` called at `routes.py:735` overrides BOTH GENERATION input AND trace-level input. 5 new `TestResumeUploadV4Tracing` tests + 4 helper-class tests + 2 fake-client tests all green (17/17 in test_observability.py). Live Langfuse dashboard rendering REQUIRES human verification — UAT Test 1 replay |

**Score:** 5/5 truths verified at code level (3 also flagged for human verification for live-service or UX behavior).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/job_rag/api/middleware.py` | ResumeUploadSizeGuard ASGI middleware | VERIFIED | 67 lines; wired in `app.py:145` ABOVE CORSMiddleware so 413 fires pre-body |
| `src/job_rag/services/profile.py` | compute_skills_diff + 3 Pydantic models | VERIFIED | 129 lines; SkillDiffItem, ResumeUploadResponse, UserProfileUpdate, compute_skills_diff all exported |
| `src/job_rag/extraction/resume_prompt.py` | RESUME_PROMPT_VERSION + RESUME_SYSTEM_PROMPT | VERIFIED | `RESUME_PROMPT_VERSION = "1.0"`; English/German/Polish carve-outs present; REJECTED_SOFT_SKILLS imported (not duplicated) |
| `src/job_rag/extraction/resume_extractor.py` | extract_resume(text) with @retry | VERIFIED | tenacity `@retry(stop_after_attempt(3), wait_exponential, reraise=True)`; returns `(ResumeExtraction, usage_info)` |
| `src/job_rag/models.py` | ResumeExtraction Pydantic model | VERIFIED | 6 D-13 fields present (skills, target_roles, preferred_locations, min_salary_eur, remote_preference, years_experience) |
| `alembic/versions/0006_seed_user_profile.py` | idempotent seed migration | VERIFIED | revision=0006, down_revision=0005, ON CONFLICT (user_id) DO NOTHING |
| `src/job_rag/observability.py::get_langfuse_client` | fail-open Langfuse client factory | VERIFIED | `@lru_cache(maxsize=1)` returns `None` when keys missing |
| `src/job_rag/observability.py::derive_langfuse_trace_id` | deterministic 32-hex trace_id from extraction_id (NEW from 07-06) | VERIFIED | Lines 110-130; uses `lf.create_trace_id(seed=str(seed))` when client present, `hashlib.blake2b(seed, 16).hexdigest()` fallback otherwise; 2 helper tests green (deterministic_for_same_seed + different_for_different_seeds). Note: WR-03 advisory on blake2b parity claim — see follow-ups |
| `src/job_rag/observability.py::redact_current_generation_input` | two-layer PII redaction helper (NEW from 07-06) | VERIFIED | Lines 133-158; calls `client.update_current_generation(input=REDACTED)` THEN `client.set_current_trace_io(input=REDACTED)`; each wrapped independently in try/except per T-07-08; 2 helper tests green (calls_both_update_and_set_trace_io + fail_open_when_client_raises) |
| `tests/_langfuse_fake.py::FakeLangfuseClient` | contract-faithful v4 fake with v3 AttributeError guard (NEW from 07-06) | VERIFIED | 231 lines; implements exact v4 surface (start_as_current_observation context manager, update_current_span, update_current_generation, set_current_trace_io, create_trace_id, get_current_trace_id, get_current_observation_id, flush, auth_check, shutdown); `__getattr__` raises `AttributeError("Langfuse v3 API removed in v4: '{name}'. Migrate to start_as_current_observation / update_current_span / update_current_generation.")` on `trace`, `update_current_observation`, `span` |
| `src/job_rag/api/routes.py` POST /profile/upload | resume upload endpoint with v4 Langfuse tracing | VERIFIED | 4 v4 spans + cross-request correlation via derive_langfuse_trace_id. New `_run_resume_upload_pipeline` helper extracted so the fail-open (lf is None) branch reuses the same pipeline body. WR-01 advisory: fail-open path may re-run pipeline on __exit__ failure — edge case, see follow-ups |
| `src/job_rag/api/routes.py` PATCH /profile | profile save endpoint with v4 profile_save span | VERIFIED | `routes.py:947-961` re-derives trace_id from payload.extraction_id and opens `profile_save` span on the SAME trace as the original POST. None-as-no-change semantics preserved. profile_save_then_share_trace_id integration test green |
| `src/job_rag/api/routes.py` GET /profile | profile read endpoint | VERIFIED | 10 lines; delegates to async load_profile |
| `frontend/src/api/profile.ts` | typed service module | VERIFIED | getProfile + uploadResume + saveProfile all exported (71 lines) |
| `frontend/src/components/profile/types.ts` | DiffItemState + ReviewState | VERIFIED | discriminated union ReviewState + DiffItemState present |
| `frontend/src/components/profile/useResumeUpload.ts` | TanStack mutation hook | VERIFIED | idle→reviewing→saved state machine; invalidates ['profile'] AND ['dashboard'] on save |
| `frontend/src/components/profile/ProfileView.tsx` | read-only current skills surface | VERIFIED | Card + Badge chips with count, alphabetical sort, 4 surface states |
| `frontend/src/components/profile/ResumeUploader.tsx` | file input + drop-zone + stepped copy | VERIFIED | 268 lines; native input + drag-drop; client pre-check size+ext; D-31 stepped copy; D-35 COPY map |
| `frontend/src/components/profile/SkillDiffChip.tsx` | chip atom with inline edit | VERIFIED | 156 lines; D-24 verbatim status pill classes; inline edit restricted to added |
| `frontend/src/components/profile/ReviewPanel.tsx` | sticky footer review UI | VERIFIED | 144 lines; sticky CardFooter; live count label; disabled-when-empty save |
| `frontend/src/routes/Profile.tsx` | page composition | VERIFIED | PhasePlaceholder removed; idle/reviewing/saved composition |
| `frontend/openapi.snapshot.json` | schemas + paths | VERIFIED | ResumeUploadResponse, SkillDiffItem, UserProfileUpdate all present; /profile and /profile/upload paths registered |
| `frontend/src/api/types.ts` | codegen types | VERIFIED | All 3 schemas codegen'd |
| `tests/fixtures/sample-resume.pdf` + .docx + encrypted + empty-text | 4 synthetic fixtures | VERIFIED | All 4 present with documented sizes (1006/36911/826/431 bytes) |
| `pyproject.toml` | pypdf + python-docx pins | VERIFIED | `pypdf>=6,<7` (line 31); `python-docx>=1,<2` (line 32); `langfuse>=4.1.0,<5` |
| `src/job_rag/config.py` | max_resume_size_bytes Setting | VERIFIED | `Field(default=2_000_000, ge=1)` |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `app.py` | `ResumeUploadSizeGuard` | `app.add_middleware` | WIRED | `add_middleware(ResumeUploadSizeGuard)` registered ABOVE CORS |
| POST /profile/upload | `asyncio.to_thread(extract_resume, text)` | async-from-sync wrap | WIRED | Offloads sync extractor |
| POST /profile/upload | resume_upload parent span | `lf.start_as_current_observation` | WIRED | `routes.py:871` opens parent span; the entire `_run_resume_upload_pipeline` call runs inside the context manager so text_extract + diff_compute + langfuse.openai auto-GENERATION all inherit the trace_id via OTel context propagation |
| POST /profile/upload + PATCH /profile | Langfuse trace correlation | `derive_langfuse_trace_id(extraction_id)` | WIRED | POST derives trace_id at `routes.py:869`; PATCH re-derives the SAME trace_id at `routes.py:949` from `payload.extraction_id`; `test_post_then_patch_share_trace_id` asserts the equality |
| POST /profile/upload | trace-level PII redaction | `redact_current_generation_input` | WIRED | Called at `routes.py:735` immediately after the Instructor call; writes `[REDACTED — char_count=N]` to BOTH `update_current_generation` AND `set_current_trace_io` |
| GET /profile | `load_profile(session, user_id=...)` | DB-backed read | WIRED | `return await load_profile(session, user_id=user_id)` |
| `useResumeUpload` save mutation | dashboard cache invalidation | `queryClient.invalidateQueries` | WIRED | invalidates `['dashboard']` query key family |
| `frontend/src/api/profile.ts` | `authedFetch` | GET/POST FormData/PATCH JSON | WIRED | All 3 service functions call `authedFetch` with correct method + body shape |
| `Profile.tsx` | `useResumeUpload` | import + invoke + conditional render | WIRED | destructures `state, upload, save, reset`; conditionally renders based on phase |
| `load_profile` callers (5 sites) | async DB query | `await load_profile(session, ...)` | WIRED | All 5 sites flipped (routes.py /match + /gaps, analytics.py, mcp_server tools.py x2) |
| `tests/test_observability.py` | `tests._langfuse_fake.FakeLangfuseClient` | import + patch get_langfuse_client | WIRED | `from tests._langfuse_fake import FakeLangfuseClient`; the v3-name guard means future regressions to lf.trace(...) / update_current_observation(...) fail CI loudly |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| ProfileView.tsx | `data` (UserSkillProfile) | `useQuery({queryKey: ['profile'], queryFn: getProfile})` → GET /profile → `load_profile` → user_profile DB row | Yes (DB-backed; seeded by 0006 migration) | FLOWING |
| ResumeUploader.tsx | `error` (Error) | `uploadResume` reject path parses `{detail: {reason}}` from backend HTTP error | Yes (backend returns D-35 error tokens with real `reason` field) | FLOWING |
| ReviewPanel.tsx | `localDiff` (DiffItemState[]) | `useResumeUpload.upload.onSuccess` populates from `ResumeUploadResponse.skills_diff` returned by POST /profile/upload | Yes (`compute_skills_diff` returns real DB current profile diffed against LLM extraction) | FLOWING |
| Profile.tsx | `state` (ReviewState) | `useResumeUpload` hook owns the state machine; populated by real TanStack mutation results | Yes (no hardcoded empties; state transitions driven by mutation lifecycle) | FLOWING |
| Langfuse trace tree | trace_id + span metadata | `derive_langfuse_trace_id(extraction_id)` deterministically maps the UUID seed to a 32-hex OTel trace_id; metadata flows from the metadata kwarg on each `start_as_current_observation` call | Yes — `extraction_id` is a real `uuid.uuid4()` and `char_count` is `len(resume_text)`. PII is replaced with the watermark `[REDACTED — char_count=N]` at both layers | FLOWING (code-level — live Langfuse dashboard rendering requires UAT replay) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| 0 Langfuse v3 patterns remaining | `grep -rnE "lf\.trace\(|trace\.span\(|update_current_observation\(" src/` | (no matches) | PASS |
| All 4 v4 spans present in routes.py | `grep -nE 'name="(resume_upload\|text_extract\|diff_compute\|profile_save)"' src/job_rag/api/routes.py` | 4 hits (lines 684, 745, 872, 951) | PASS |
| redact helper invoked at routes.py | `grep -nE "redact_current_generation_input\(lf" src/job_rag/api/routes.py` | 1 match (line 735) | PASS |
| derive_langfuse_trace_id called in BOTH POST and PATCH | `grep -nE "derive_langfuse_trace_id" src/job_rag/api/routes.py` | 5 references (import, docstring, POST x1, PATCH x1, docstring back-ref) | PASS |
| Observability suite passes (incl. all 4 TestResumeUploadV4Tracing tests + 2 fake-client tests + 4 helper tests) | `uv run pytest tests/test_observability.py -v` | 17 passed | PASS |
| Profile + resume extractor suites pass | `uv run pytest tests/test_profile.py tests/test_resume_extractor.py` | 22 passed | PASS |
| Full backend suite (excluding 2 documented pre-existing deferred items) | `uv run pytest --ignore=tests/test_alembic.py --deselect tests/test_matching.py::test_load_profile_returns_seeded_row` | 269 passed, 8 skipped (PG-gated), 1 deselected | PASS |
| Backend pyright on the 4 modified files | `uv run pyright src/job_rag/observability.py src/job_rag/api/routes.py tests/_langfuse_fake.py tests/test_observability.py` | 0 errors, 0 warnings, 0 informations | PASS |
| Backend ruff (whole tree) | `uv run ruff check src/ tests/` | All checks passed | PASS |
| Frontend test suite | `npm test -- --run` | 113 passed across 22 test files | PASS |
| Frontend typecheck | `npm run typecheck` | exits 0 | PASS |
| No PhasePlaceholder in Profile.tsx | `grep PhasePlaceholder frontend/src/routes/Profile.tsx` | exit 1 (not found) | PASS |
| `grep -rn 'profile.json' src/` | grep | 0 matches | PASS |
| FakeLangfuseClient raises on v3 method names | embedded in `TestFakeLangfuseClient::test_v3_method_names_raise_attributeerror` | passed: pytest.raises(AttributeError, match="v3 API removed") on .trace / .update_current_observation / .span | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| PROF-01 | Plans 01, 02, 04 | UserProfile DB model + seed + data/profile.json removed from canonical read path | SATISFIED | UserProfileDB schema unchanged (already existed from Phase 1); 0006 seed migration commits Adrian's profile via embedded dict literal; `load_profile()` body flipped to async DB query; `grep 'profile.json' src/` returns 0 matches |
| PROF-02 | Plans 01, 03, 04 | PDF/DOCX upload (multipart, 2 MB cap, pypdf 6.x, python-docx 1.x) | SATISFIED | pyproject.toml pins `pypdf>=6,<7` (resolved 6.12.2) + `python-docx>=1,<2` (resolved 1.2.0); ResumeUploadSizeGuard enforces pre-body 413; in-handler chunked fallback; type whitelist returns 415 |
| PROF-03 | Plan 03 | Resume text → Instructor + GPT-4o-mini + pinned prompt → structured shape | SATISFIED | `extract_resume()` calls Instructor with `response_model=ResumeExtraction`; `RESUME_PROMPT_VERSION = "1.0"` pinned and propagated through usage_info |
| PROF-04 | Plan 04 | Diff response (added / removed / unchanged) for UI side-by-side | SATISFIED | `compute_skills_diff()` classifies via `_normalize_skill` equality; output ordered added → removed → unchanged; 3 diff tests green |
| PROF-05 | Plan 05 | Frontend review panel — tick/untick chips + inline edit | SATISFIED | `SkillDiffChip.tsx` shows status pills + native checkbox + Pencil-icon inline edit (restricted to added); `ReviewPanel.tsx` lists chips + sticky footer; 14 component tests green |
| PROF-06 | Plans 04, 05, 06 | PATCH persist + full Langfuse trace across the pipeline | SATISFIED (code-level, post-07-06 closure) | PATCH /profile writes skills_json; useResumeUpload save mutation invalidates ['profile'] AND ['dashboard']; **G-07-UAT-01 closed** — 4 v4 spans (resume_upload + text_extract + diff_compute + profile_save) correlated via derive_langfuse_trace_id(extraction_id); two-layer PII redaction (generation + trace); 5 TestResumeUploadV4Tracing tests + 4 helper tests assert the contract against FakeLangfuseClient. Live Langfuse-dashboard verification flagged for human (UAT Test 1 replay) |

All 6 PROF requirements satisfied at code/test level. No orphaned requirements detected — REQUIREMENTS.md lists exactly PROF-01..06 against Phase 7, and all are claimed in plan frontmatter across plans 01-06.

### Anti-Patterns Found

No blocker anti-patterns introduced or surviving from the gap-closure delta. Targeted scan of the 4 files touched by Plan 07-06 (`src/job_rag/observability.py`, `src/job_rag/api/routes.py`, `tests/_langfuse_fake.py`, `tests/test_observability.py`):

- No `TODO`/`FIXME`/`PLACEHOLDER` markers in production code.
- No `return null` / `return []` / `return {}` placeholder bodies; every return path is meaningful.
- Hardcoded `[]` / `{}` / `null` patterns appear only in legitimate defaults: Pydantic `Field(default_factory=list)`, React `useState({phase: 'idle'})`, and Langfuse fail-open `if lf is None: ...` guards.
- Empty-handler stubs: none.
- Fetch + response-handling pairs all verified.
- Langfuse failure paths use `except Exception: log.warning(...)` (with structured log) or bare `pass` deliberately (fail-open per T-07-08); the v3-pattern try/except blocks that were swallowing AttributeError have been removed by the migration.

**Three advisory warnings from 07-06-REVIEW.md** (WR-01, WR-02, WR-03) recorded in `follow_ups:` frontmatter. None block the PROF-06 contract:
- WR-01 (fail-open path can re-run pipeline on context-manager exit failure) is an edge case that fires only on a real trace-teardown exception, not on the steady-state path.
- WR-02 (tags buried in metadata) reduces Langfuse-UI filter discoverability but does not affect span structure or PII redaction.
- WR-03 (BLAKE2b vs SHA-256 fallback parity) is invisible within a single process due to `@lru_cache` on `get_langfuse_client`; matters only if the fallback ever crosses process boundaries.

### Human Verification Required

5 items requiring human testing (see frontmatter `human_verification` block for structured form):

1. **G-07-UAT-01 Live Replay (UAT Test 1).** With `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` set in the ACA env, upload a 1.5 MB PDF resume via the running SWA UI. In the Langfuse dashboard, find the most recent trace and confirm:
   - A single parent span named `resume_upload` with `metadata.extraction_id` set, OR (if the deployed v4 SDK chooses a different parent representation) the trace root carries the derived trace_id.
   - 3 explicit child observations (`text_extract`, `diff_compute`, plus the `langfuse.openai` auto-captured GENERATION).
   - The trace root input AND the GENERATION input both show `[REDACTED — char_count=N]` (NOT Adrian's name, email, phone, LinkedIn, GitHub, or address — the exact PII fields that leaked in the original `trace-c744bb2d...json` export).
   - PATCH `/profile` adds a `profile_save` span attached to the SAME trace (re-derived via `derive_langfuse_trace_id(extraction_id)`).
   This test directly closes G-07-UAT-01 — the original failure was only visible at the live Langfuse dashboard, so code-level FakeLangfuseClient tests cannot fully substitute.

2. **Dashboard cache propagation.** Upload a resume, save the diff with at least one new skill, then navigate to the Dashboard. Expected: CV-vs-market widget reflects the new skill list within one re-render. Why human: end-to-end UI flow requires running backend + frontend + DB; automated tests verify the `invalidateQueries` call but not the visible widget refresh.

3. **Pre-body 413 streaming behaviour.** Attempt to upload a 5 MB file via the browser; open DevTools Network panel and observe the request. Expected: 413 response returned with bytes transmitted << 5 MB (Content-Length-based pre-body reject). Why human: browser-side streaming behaviour cannot be observed reliably from automated tests.

4. **Cold-start stepped copy.** Force a cold start (set ACA min-replicas=0 + idle 5 min), upload a resume, observe the status copy transitions. Expected: 0-2s "Reading…" → 2-10s "Asking the agent…" → 10s+ "Still working…" per D-31. Why human: requires real cold-start latency.

5. **Inline-edit round-trip.** Upload a resume, inline-edit an added chip's name, save, refresh `/profile`. Expected: the renamed skill appears in the ProfileView Badge list after refresh. Why human: end-to-end persistence verification requires a running DB.

### Gaps Summary

No code-level gaps remain. G-07-UAT-01 — the blocking gap from the previous verification — is closed at the code level by Plan 07-06: all 5 v3 call sites migrated to the v4 OTel API; cross-request trace correlation via `derive_langfuse_trace_id`; two-layer PII redaction; and a contract-faithful `FakeLangfuseClient` that will fail CI loudly on any future v3 regression.

The remaining `human_verification` items are NOT gaps — they are intentional escalations of contracts that can only be eyeballed live (Langfuse dashboard rendering, browser streaming behaviour, cold-start UX, end-to-end persistence). The Langfuse-trace test (Item 1) is the highest priority because it directly proves G-07-UAT-01 is closed in the same environment where it was originally observed.

Three follow-up advisories from `07-06-REVIEW.md` (WR-01, WR-02, WR-03) are recorded in `follow_ups:` and a DeprecationWarning on `set_current_trace_io` is recorded in `deprecation_warnings:`. None block PROF-06.

Pre-existing test failures (out of scope per `deferred-items.md` SCOPE BOUNDARY rule):
- `tests/test_alembic.py::test_0005_upgrade_populates_oid_when_env_set` (Phase 04.1 env-set UPDATE moved to engine.py)
- `tests/test_matching.py::test_load_profile_returns_seeded_row` (Adrian's live UAT mutated dev DB skills set)
- `tests/test_alembic.py::test_0004_*_smoke` (env-gated; KeyError: 'DATABASE_URL' when local DB offline — 8 skipped not failed)

---

_Verified: 2026-05-30T16:27:30Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification mode: post-gap-closure (Plan 07-06 closes G-07-UAT-01)_
