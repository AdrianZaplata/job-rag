---
phase: 07-profile-resume-upload
verified: 2026-05-28T11:44:42Z
status: gaps_found
status_history:
  - 2026-05-28T11:44:42Z: human_needed (initial verifier output, code-level all green)
  - 2026-05-29T00:00:00Z: gaps_found (live UAT Test 1 failed — Langfuse SDK 3.x→4.x mismatch surfaced; see HUMAN-UAT G-07-UAT-01)
score: 4/5 must-haves verified (truth #5 demoted to FAILED after live UAT)
overrides_applied: 0
gaps:
  - id: G-07-UAT-01
    title: "Langfuse SDK 3.x → 4.x migration (PROF-06 trace contract broken)"
    severity: blocking
    source: live UAT Test 1 (HUMAN-UAT.md)
    affected_truth: 5
    affected_requirements: [PROF-06]
    evidence_file: "trace-c744bb2d0683a35da965946940e70bab.json (Langfuse export from Adrian's first real upload)"
    summary: |
      Phase 7 backend calls `lf.trace()`, `trace.span().end()`, and
      `lf.update_current_observation()` — Langfuse Python SDK 3.x methods that
      do not exist on the installed 4.1.0 client (OTel-based rewrite). All
      calls raise AttributeError, are swallowed by T-07-08 fail-open
      try/except wrappers, and silently no-op. The manual spans (text_extract,
      diff_compute, profile_save) and PII redaction at `routes.py:805` never
      run in production. Only `langfuse.openai` auto-instrumentation survives.
      Result: standalone GENERATION trace with full unredacted resume PII
      (name, email, phone, LinkedIn URL, GitHub URL, address) in trace.input.
    affected_files:
      - src/job_rag/api/routes.py:687
      - src/job_rag/api/routes.py:756
      - src/job_rag/api/routes.py:804
      - src/job_rag/api/routes.py:817
      - src/job_rag/api/routes.py:897
      - src/job_rag/observability.py
      - tests/test_observability.py
    why_unit_tests_passed: |
      tests/test_observability.py mocks get_langfuse_client(); the mock
      accepts any method call (.trace, .span, .update_current_observation)
      without raising. Tests verified call shape ("intent"), not real SDK
      compatibility. Live UAT was first contact with a real 4.x client.
human_verification:
  - test: "Upload a 1.5 MB PDF resume via the running UI and confirm Langfuse dashboard shows a single trace with 4 spans (text_extract, llm_extract auto, diff_compute, profile_save) correlated by extraction_id"
    expected: "Single Langfuse trace per upload spanning extraction → Instructor → diff → PATCH; raw resume text NOT visible in any span input/metadata"
    why_human: "Requires live Langfuse account + LANGFUSE_PUBLIC_KEY/SECRET_KEY in env + visual inspection of Langfuse UI; the code-level wiring is verified but the trace-rendering contract is external"
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
---

# Phase 7: Profile & Resume Upload — Verification Report

**Phase Goal:** Phase 7 ships the personal-data loop when Adrian can upload a PDF or DOCX resume, see an Instructor-extracted skill diff vs his current profile in a reviewable panel, and tick/edit/save confirmed skills back to `user_profile` — with the full extract→review→save trace visible in Langfuse.

**Verified:** 2026-05-28T11:44:42Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `data/profile.json` is no longer the read path; `load_profile(session, user_id)` hits the `user_profile` table (PROF-01) | VERIFIED | `src/job_rag/services/matching.py:16-54` shows async DB-backed `load_profile`; `grep -rn 'profile.json' src/` returns 0 matches; alembic 0006 seeds the row via `ON CONFLICT (user_id) DO NOTHING`; 3 load_profile tests + 3 alembic seed tests green |
| 2 | 1.5 MB PDF upload succeeds; >2 MB rejected with 413 BEFORE body fully read; DOCX accepted (PROF-02) | VERIFIED | `ResumeUploadSizeGuard` middleware in `src/job_rag/api/middleware.py` reads Content-Length pre-body; in-handler chunked fallback at `routes.py:660-680`; 8 upload tests green (PDF happy path + DOCX happy path + 413 oversized Content-Length + 413 chunked + 415 .txt + 422 encrypted + 422 empty-text + 422 extraction_failed) |
| 3 | Upload response shows reviewable diff split into added/removed/unchanged; UI renders as tick/untick chips with inline edit (PROF-03, PROF-04, PROF-05) | VERIFIED | `compute_skills_diff` in `src/job_rag/services/profile.py:84` returns ordered `SkillDiffItem[]`; `ResumeUploadResponse` returns `skills_diff` field; `SkillDiffChip.tsx` renders D-24 status pills + Pencil edit on added items; `ReviewPanel.tsx` shows sticky footer with `Save profile (N skills)` label; 25 frontend tests across 5 component spec files green |
| 4 | Save PATCHes user_profile; next CV-vs-market dashboard load reflects new skills (PROF-06) | VERIFIED (code-level) | `PATCH /profile` handler in `routes.py:848-908` writes `skills_json` and preserves None fields; `useResumeUpload.ts:52-53` calls `setQueryData(['profile'], profile)` AND `invalidateQueries({queryKey: ['dashboard']})`; 3 PATCH tests green. End-to-end widget refresh flagged for human verification |
| 5 | Langfuse trace shows a single trace per upload spanning extraction → Instructor → diff → (on save) PATCH (PROF-06) | VERIFIED (code-level) | 3 explicit `trace.span(name=…)` calls in `routes.py` (text_extract, diff_compute, profile_save) all correlated by `extraction_id = uuid.uuid4()`; the LLM call goes through `langfuse.openai.OpenAI` wrapper in `observability.py:47-50`, auto-capturing the 4th `llm_extract` span; PII redaction at `routes.py:805` writes `[REDACTED — char_count=N]` to the LLM span input; 3 Langfuse tests green (4-span shape, no-PII, fail-open). Live Langfuse dashboard rendering flagged for human verification |

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
| `src/job_rag/api/routes.py` POST /profile/upload | resume upload endpoint | VERIFIED | 245 lines; handles all 7 error reasons; trace.span calls for text_extract + diff_compute |
| `src/job_rag/api/routes.py` PATCH /profile | profile save endpoint | VERIFIED | 61 lines; None-as-no-change semantics; profile_save span on matching extraction_id |
| `src/job_rag/api/routes.py` GET /profile | profile read endpoint | VERIFIED | 10 lines; delegates to async load_profile |
| `frontend/src/api/profile.ts` | typed service module | VERIFIED | getProfile + uploadResume + saveProfile all exported (71 lines) |
| `frontend/src/components/profile/types.ts` | DiffItemState + ReviewState | VERIFIED | discriminated union ReviewState + DiffItemState present |
| `frontend/src/components/profile/useResumeUpload.ts` | TanStack mutation hook | VERIFIED | idle→reviewing→saved state machine; invalidates ['profile'] AND ['dashboard'] on save |
| `frontend/src/components/profile/ProfileView.tsx` | read-only current skills surface | VERIFIED | Card + Badge chips with count, alphabetical sort, 4 surface states |
| `frontend/src/components/profile/ResumeUploader.tsx` | file input + drop-zone + stepped copy | VERIFIED | 268 lines; native input + drag-drop; client pre-check size+ext; D-31 stepped copy; D-35 COPY map |
| `frontend/src/components/profile/SkillDiffChip.tsx` | chip atom with inline edit | VERIFIED | 156 lines; D-24 verbatim status pill classes; inline edit restricted to added |
| `frontend/src/components/profile/ReviewPanel.tsx` | sticky footer review UI | VERIFIED | 144 lines; sticky CardFooter; live count label; disabled-when-empty save |
| `frontend/src/routes/Profile.tsx` | page composition | VERIFIED | PhasePlaceholder removed; idle/reviewing/saved composition |
| `frontend/openapi.snapshot.json` | schemas + paths | VERIFIED | ResumeUploadResponse, SkillDiffItem, UserProfileUpdate all present at lines 1112, 1156, 1218; /profile and /profile/upload paths registered |
| `frontend/src/api/types.ts` | codegen types | VERIFIED | All 3 schemas codegen'd at lines 540, 565, 612 |
| `tests/fixtures/sample-resume.pdf` + .docx + encrypted + empty-text | 4 synthetic fixtures | VERIFIED | All 4 present with documented sizes (1006/36911/826/431 bytes) |
| `pyproject.toml` | pypdf + python-docx pins | VERIFIED | `pypdf>=6,<7` at line 31; `python-docx>=1,<2` at line 32 |
| `src/job_rag/config.py` | max_resume_size_bytes Setting | VERIFIED | line 61: `Field(default=2_000_000, ge=1)` |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `app.py` | `ResumeUploadSizeGuard` | `app.add_middleware` | WIRED | `app.py:145` calls `add_middleware(ResumeUploadSizeGuard)` ABOVE CORS |
| POST /profile/upload | `asyncio.to_thread(extract_resume, text)` | async-from-sync wrap | WIRED | `routes.py:782` (verified by inspection); offloads sync extractor |
| POST /profile/upload + PATCH /profile | Langfuse trace correlation | `extraction_id` UUID | WIRED | POST generates `extraction_id = uuid.uuid4()` at `routes.py:632`, returns in `ResumeUploadResponse.extraction_id`; PATCH echoes via `payload.extraction_id` and `lf.trace(id=str(...))` at `routes.py:896` |
| GET /profile | `load_profile(session, user_id=...)` | DB-backed read | WIRED | `routes.py:926`: `return await load_profile(session, user_id=user_id)` |
| `useResumeUpload` save mutation | dashboard cache invalidation | `queryClient.invalidateQueries` | WIRED | `useResumeUpload.ts:53` invalidates `['dashboard']` query key family |
| `frontend/src/api/profile.ts` | `authedFetch` | GET/POST FormData/PATCH JSON | WIRED | All 3 service functions call `authedFetch` with correct method + body shape |
| `Profile.tsx` | `useResumeUpload` | import + invoke + conditional render | WIRED | line 18 destructures `state, upload, save, reset`; lines 21-50 conditionally render based on phase |
| `load_profile` callers (5 sites) | async DB query | `await load_profile(session, ...)` | WIRED | All 5 sites flipped (routes.py /match + /gaps, analytics.py, mcp_server tools.py x2) per Plan 02 SUMMARY |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| ProfileView.tsx | `data` (UserSkillProfile) | `useQuery({queryKey: ['profile'], queryFn: getProfile})` → GET /profile → `load_profile` → user_profile DB row | Yes (DB-backed; seeded by 0006 migration with 62 skills) | FLOWING |
| ResumeUploader.tsx | `error` (Error) | `uploadResume` reject path parses `{detail: {reason}}` from backend HTTP error | Yes (backend returns D-35 error tokens with real `reason` field) | FLOWING |
| ReviewPanel.tsx | `localDiff` (DiffItemState[]) | `useResumeUpload.upload.onSuccess` populates from `ResumeUploadResponse.skills_diff` returned by POST /profile/upload | Yes (`compute_skills_diff` returns real DB current profile diffed against LLM extraction) | FLOWING |
| Profile.tsx | `state` (ReviewState) | `useResumeUpload` hook owns the state machine; populated by real TanStack mutation results | Yes (no hardcoded empties; state transitions driven by mutation lifecycle) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| All key Python modules importable | `uv run python -c "from job_rag.api.middleware import ResumeUploadSizeGuard; from job_rag.services.profile import compute_skills_diff, ResumeUploadResponse, UserProfileUpdate, SkillDiffItem; from job_rag.observability import get_langfuse_client; ..."` | OK | PASS |
| `RESUME_PROMPT_VERSION == '1.0'` + carve-outs present | inline assertion via `python -c` | All assertions pass | PASS |
| `ResumeExtraction` schema shape | `model_json_schema()` includes all 6 D-13 fields | All required fields present | PASS |
| `load_profile` is async | `inspect.iscoroutinefunction(load_profile)` | True | PASS |
| Backend resume-extractor + profile tests | `uv run pytest tests/test_resume_extractor.py tests/test_profile.py -x` | 22 passed | PASS |
| Profile-related observability + matching + api tests (subset) | `uv run pytest ... -k 'profile or load_profile or get_profile or resume_upload or resume_trace or langfuse_fail_open'` | 4 passed, 3 skipped (PG-gated when DB not running), 47 deselected | PASS |
| Backend pyright | `uv run pyright src/` | 0 errors, 0 warnings, 0 informations | PASS |
| Frontend test suite | `npm test -- --run` | 113 passed across 22 test files | PASS |
| Frontend typecheck | `npm run typecheck` | exits 0 | PASS |
| No PhasePlaceholder in Profile.tsx | `grep PhasePlaceholder frontend/src/routes/Profile.tsx` | exit 1 (not found) | PASS |
| `grep -rn 'profile.json' src/` | grep | 0 matches | PASS |
| OpenAPI snapshot contains new schemas | `grep ResumeUploadResponse frontend/openapi.snapshot.json` | 3 hits at lines 703, 1112, 1141 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| PROF-01 | Plans 01, 02, 04 | UserProfile DB model + seed + data/profile.json removed from canonical read path | SATISFIED | UserProfileDB schema unchanged (already existed from Phase 1); 0006 seed migration commits Adrian's 62-skill profile via embedded dict literal; `load_profile()` body flipped to async DB query; `grep 'profile.json' src/` returns 0 matches |
| PROF-02 | Plans 01, 03, 04 | PDF/DOCX upload (multipart, 2 MB cap, pypdf 6.x, python-docx 1.x) | SATISFIED | pyproject.toml pins `pypdf>=6,<7` (resolved 6.12.2) + `python-docx>=1,<2` (resolved 1.2.0); ResumeUploadSizeGuard enforces pre-body 413; in-handler chunked fallback at `routes.py:660-680`; type whitelist (ext + Content-Type) at `routes.py:638` returns 415 |
| PROF-03 | Plan 03 | Resume text → Instructor + GPT-4o-mini + pinned prompt → structured shape | SATISFIED | `extract_resume()` calls `instructor.from_openai(get_openai_client()).chat.completions.create_with_completion(model=settings.openai_model, response_model=ResumeExtraction, ...)`; `RESUME_PROMPT_VERSION = "1.0"` pinned and propagated through usage_info |
| PROF-04 | Plan 04 | Diff response (added / removed / unchanged) for UI side-by-side | SATISFIED | `compute_skills_diff()` classifies via `_normalize_skill` equality; output ordered added → removed → unchanged (alphabetical within bucket); 3 diff tests green |
| PROF-05 | Plan 05 | Frontend review panel — tick/untick chips + inline edit | SATISFIED | `SkillDiffChip.tsx` shows status pills + native checkbox + Pencil-icon inline edit (restricted to added); `ReviewPanel.tsx` lists chips + sticky footer with live count; 14 component tests green |
| PROF-06 | Plans 04, 05 | PATCH persist + full Langfuse trace across the pipeline | SATISFIED (code-level) | PATCH /profile writes skills_json via SQL UPDATE; useResumeUpload save mutation invalidates ['profile'] AND ['dashboard']; 3 explicit Langfuse spans + 1 auto-captured (LLM) all correlated by `extraction_id`; PII redaction in place. Live Langfuse-dashboard verification flagged for human |

All 6 PROF requirements satisfied at code/test level. No orphaned requirements detected (REQUIREMENTS.md lists exactly PROF-01..06 against Phase 7 and all are claimed in plan frontmatter).

### Anti-Patterns Found

No blocker anti-patterns. Spot-checks against `src/job_rag/api/routes.py`, `src/job_rag/services/profile.py`, `src/job_rag/api/middleware.py`, `src/job_rag/extraction/resume_extractor.py`, and all 6 new frontend source files found:

- No `TODO`/`FIXME`/`PLACEHOLDER` markers in production code.
- No `return null` / `return []` / `return {}` placeholder bodies; every return path is meaningful.
- Hardcoded `[]` / `{}` / `null` patterns appear only in legitimate defaults: Pydantic `Field(default_factory=list)`, React `useState({phase: 'idle'})`, and Langfuse fail-open `trace = None` guards.
- Empty-handler stubs: none. All `onClick`/`onSubmit` handlers route to real mutations or state changes.
- Fetch + response-handling pairs all verified (no dangling `fetch` without `await` / `.then`).
- Langfuse failure paths use `except Exception: pass` deliberately (fail-open per T-07-08); these are documented in code comments and verified by `test_langfuse_fail_open_when_keys_missing`.

### Human Verification Required

5 items requiring human testing (see frontmatter `human_verification` block for structured form):

1. **Langfuse trace rendering (M-marker 3).** Upload a 1.5 MB resume via the running UI with `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` set; inspect the Langfuse dashboard. Expected: single trace per upload with 4 spans (text_extract, llm_extract auto, diff_compute, profile_save) correlated by extraction_id; raw resume text NOT visible in any span input or metadata. Why human: requires live Langfuse account + visual inspection of an external service UI.

2. **Dashboard cache propagation (M-marker 4).** Upload a resume, save the diff with at least one new skill, then navigate to the Dashboard. Expected: CV-vs-market widget reflects the new skill list within one re-render. Why human: end-to-end UI flow requires running backend + frontend + DB; automated tests verify the `invalidateQueries` call but not the visible widget refresh.

3. **Pre-body 413 streaming behaviour (M-marker 2).** Attempt to upload a 5 MB file via the browser; open DevTools Network panel and observe the request. Expected: 413 response returned with bytes transmitted << 5 MB (Content-Length-based pre-body reject). Why human: browser-side streaming behaviour cannot be observed reliably from automated tests; the middleware test asserts the 413 outcome but not the pre-body-streaming property.

4. **Cold-start stepped copy (M-marker 6).** Force a cold start (set ACA min-replicas=0 + idle 5 min), upload a resume, observe the status copy transitions. Expected: 0-2s "Reading…" → 2-10s "Asking the agent…" → 10s+ "Still working…" per D-31. Why human: requires real cold-start latency; fake-timer tests verify transitions in isolation but not the user-perceived experience.

5. **Inline-edit round-trip (M-marker 5).** Upload a resume, inline-edit an added chip's name, save, refresh `/profile`. Expected: the renamed skill appears in the ProfileView Badge list after refresh — proves the edited name persists through PATCH. Why human: end-to-end persistence verification requires a running DB; component test asserts `onRename` callback but not the round-trip.

### Gaps Summary

No gaps found at the code/test level. All 5 ROADMAP Success Criteria are satisfied by code that exists, is wired, and is exercised by green automated tests (22 backend tests across `test_resume_extractor.py` + `test_profile.py`; 113 frontend tests; 0 regressions in the full backend suite when DATABASE_URL is set; pyright + typecheck clean; the pre-existing Phase 04.1 `test_0005_upgrade_populates_oid_when_env_set` failure documented in `deferred-items.md` is OUT OF SCOPE per the SCOPE BOUNDARY rule).

The 3 truths that include "(code-level)" qualifiers (#4 dashboard-refresh, #5 Langfuse-dashboard, and the pre-body-413 streaming claim under #2) are mechanically verified through tests but their user-perceived behaviour cannot be confirmed without running services (live Langfuse, running ACA backend with cold-start, browser DevTools). These are listed under `human_verification` rather than as gaps — the code contracts are correct; only the live behaviour needs eyeball confirmation.

---

_Verified: 2026-05-28T11:44:42Z_
_Verifier: Claude (gsd-verifier)_
