---
phase: 07-profile-resume-upload
plan: 03
subsystem: extraction
tags: [llm, instructor, pydantic, tenacity, prompt-injection, prof-03]

# Dependency graph
requires:
  - phase: 02-corpus-cleanup
    provides: "REJECTED_SOFT_SKILLS tuple + PROMPT_VERSION convention from src/job_rag/extraction/prompt.py — Plan 03 imports the tuple verbatim and mirrors the str.format() template construction pattern"
  - phase: 07-profile-resume-upload (Plan 01)
    provides: "pypdf + python-docx deps + max_resume_size_bytes Setting + tests/test_resume_extractor.py empty scaffold (Plan 03 overwrites with 8 tests)"
provides:
  - "src/job_rag/extraction/resume_prompt.py — RESUME_PROMPT_VERSION='1.0' + RESUME_SYSTEM_PROMPT (1590 chars; 22 rejected-soft-skill terms pass-through + English/German/Polish spoken-language carve-outs)"
  - "src/job_rag/extraction/resume_extractor.py — sync extract_resume(text) -> (ResumeExtraction, usage_info) with tenacity @retry(stop_after_attempt(3), wait_exponential(min=1, max=10), reraise=True)"
  - "src/job_rag/models.py — ResumeExtraction Pydantic model with 6 D-13 fields (skills/target_roles/preferred_locations/min_salary_eur/remote_preference/years_experience)"
  - "tests/test_resume_extractor.py — 8 tests across 3 classes covering structured output, 3x retry, prompt structure, schema shape"
  - "PROF-03 closed at the extractor primitives level (versioned prompt, structured Pydantic output, tenacity retry, prompt-injection guardrail via response_model)"
affects: [07-04-upload-routes-diff-langfuse]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Resume-prompt mirror of extraction/prompt.py: str.format() template (NOT f-string) with brace-doubling for literal `{name}` example placeholders so the rendered prompt's example syntax matches the schema"
    - "Single-source REJECTED_SOFT_SKILLS — resume_prompt.py imports the tuple from extraction/prompt.py rather than duplicating; one tuple edit + PROMPT_VERSION bump propagates to both job-posting and resume extraction prompts"
    - "Plan-mandated tenacity reraise=True: the @retry decorator must propagate the original exception type so the Plan 04 route handler can map ValidationError → 422 extraction_failed vs openai.APIError → 503 llm_unavailable (D-16/D-35)"

key-files:
  created:
    - src/job_rag/extraction/resume_prompt.py
    - src/job_rag/extraction/resume_extractor.py
  modified:
    - src/job_rag/models.py
    - tests/test_resume_extractor.py

key-decisions:
  - "Used `reraise=True` on the tenacity decorator (deviation from the existing extract_posting wrapper, which omits it). Without it tenacity wraps the underlying error as RetryError; the plan's must-haves truth #5 ('retries 3 times then re-raises') and Plan 04's D-35 error mapping both require the original exception type to surface. Auto-fixed during Task 2 verification."
  - "Resume text passed bare to the LLM (no <resume>...</resume> wrap) per PATTERNS §1 — the structured response_model is the prompt-injection guardrail (T-07-04). A delimiter wrap would just add tokens with no security benefit beyond what Instructor's typed shape already provides."
  - "ResumeExtraction uses min_salary_eur (not UserSkillProfile.min_salary) so the LLM gets an explicit unit hint at extraction time. Field-copy mapper in Plan 04's compute_skills_diff handles the rename when diffing against UserSkillProfile."
  - "Added one extra test (test_module_imports_cleanly, mirroring test_extraction.py's anti-regression pattern for str.format brace escaping). Total 8 tests vs plan's stated 7 — strictly additive, doesn't change the plan-mandated coverage."

patterns-established:
  - "Resume extractor as a sibling of extract_posting: same @retry shape, same usage_info dict, same Instructor wiring — only the response_model and (deliberately) the absence of a delimiter wrap differ"
  - "PROMPT_VERSION constant per extraction module — keeps drift detection per-prompt rather than a single project-wide version, mirroring the job-posting convention"

requirements-completed: [PROF-02, PROF-03]  # PROF-02 deps (parser dep landed in Plan 01); PROF-03 closed at the extractor primitives level

# Metrics
duration: ~5 min
completed: 2026-05-28
---

# Phase 07 Plan 03: Resume Extractor Summary

**Resume extraction primitives landed: pinned `RESUME_PROMPT_VERSION='1.0'` + `RESUME_SYSTEM_PROMPT` (single-sourced REJECTED_SOFT_SKILLS pass-through + English/German/Polish spoken-language carve-outs) + `ResumeExtraction` Pydantic model with the 6 D-13 fields + `extract_resume()` sync wrapper around Instructor/GPT-4o-mini with `@retry(stop_after_attempt(3), reraise=True)`. 8 tests green; full backend suite 198 passed, 0 regressions.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-28
- **Completed:** 2026-05-28
- **Tasks:** 2 (1 deviation auto-fix)
- **Files created/modified:** 4 (2 new + 2 modified)

## Accomplishments

- **`resume_prompt.py` (NEW, 60 lines).** `RESUME_PROMPT_VERSION = "1.0"`. `RESUME_SYSTEM_PROMPT` is 1590 chars after str.format() interpolation. Single-sources the soft-skill reject list by importing `REJECTED_SOFT_SKILLS` from `extraction/prompt.py` (22 terms flow through verbatim). Spoken-language carve-outs ("English", "German", "Polish") appear verbatim in the rendered prompt — Adrian's profile lists these and the prompt prevents the LLM from filtering them as soft-skill "communication". The `{{name}}` brace-doubling in the `skills` bullet matches the same caveat called out in `prompt.py:53-60`.
- **`ResumeExtraction` Pydantic model in `models.py`.** 6 D-13 fields placed after `UserSkillProfile`: `skills: list[UserSkill]`, `target_roles: list[str]`, `preferred_locations: list[str]`, `min_salary_eur: int | None`, `remote_preference: RemotePolicy`, `years_experience: int | None`. Uses `min_salary_eur` (not `min_salary`) so Instructor has an explicit unit hint at extraction time. Defaults: target_roles/preferred_locations to empty list, salary/years_experience to None, remote_preference to UNKNOWN.
- **`resume_extractor.py` (NEW, 70 lines).** `extract_resume(text)` mirrors `extract_posting()`: `instructor.from_openai(get_openai_client())` + `create_with_completion(model=settings.openai_model, response_model=ResumeExtraction, …)`. Returns `(ResumeExtraction, usage_info)` where `usage_info` carries `model`, `prompt_version`, `prompt_tokens`, `completion_tokens`, `total_tokens` for the Plan 04 Langfuse `llm_extract` span. Logs `resume_extraction_complete` event at structlog INFO with token counts. **Deliberate omission**: no `<resume>...</resume>` delimiter wrap — the response_model is the prompt-injection guardrail (T-07-04 disposition), and a delimiter would add tokens without strengthening that contract.
- **`@retry(stop_after_attempt(3), wait_exponential(min=1, max=10), reraise=True)`.** Three attempts with exponential backoff (1s → 10s cap). `reraise=True` is the deviation from `extract_posting()` (see Decisions): without it tenacity wraps the final exception as `RetryError`, which the Plan 04 route handler cannot pattern-match against to map ValidationError → 422 vs openai.APIError → 503.
- **8 tests in `tests/test_resume_extractor.py`** (replaces the empty Plan 01 scaffold). 3 classes mirror `test_extraction.py`:
  - `TestExtractResume` (2 tests): structured-output happy path + retries_3x_then_raises.
  - `TestResumePromptStructure` (4 tests): every REJECTED_SOFT_SKILLS term in prompt + spoken-language carve-outs + version pin + module-import sanity.
  - `TestResumeExtractionSchema` (2 tests): six-field shape + default values.
- **Full backend suite green.** 198 passed, 12 skipped (PG-gated), 1 deselected (pre-existing `test_0005_upgrade_populates_oid_when_env_set` from Phase 04.1 fix #1). 0 regressions from Plan 03.

## Task Commits

1. **Task 1: resume_prompt + ResumeExtraction model + resume_extractor** — `b690744` (feat)
2. **Task 2 (TDD GREEN): test_resume_extractor.py + reraise=True auto-fix** — `55b4a63` (test)

## Files Created/Modified

Created:
- `src/job_rag/extraction/resume_prompt.py` (60 lines) — RESUME_PROMPT_VERSION + RESUME_SYSTEM_PROMPT
- `src/job_rag/extraction/resume_extractor.py` (70 lines) — sync extract_resume with tenacity @retry + Instructor

Modified:
- `src/job_rag/models.py` — appended `ResumeExtraction` model after `UserSkillProfile` (+28 lines)
- `tests/test_resume_extractor.py` — replaced empty Plan 01 scaffold with 8-test suite (+138 / -3 lines)

## Decisions Made

- **`reraise=True` on the tenacity decorator (Rule 1 auto-fix).** The plan's `<behavior>` block for Task 2 said "tenacity retries on ValidationError 3 times then re-raises". With the bare `@retry(wait=…, stop=…)` shape copied from `extract_posting`, tenacity wraps the final exception as `RetryError(ValidationError)` rather than re-raising the underlying `ValidationError`. The plan's must-haves truth #5 ("retries 3 times with exponential backoff then re-raises") and Plan 04's D-35 error mapping (`ValidationError` → 422 `extraction_failed`, `openai.APIError` → 503 `llm_unavailable`) both depend on the original exception type reaching the handler. Added `reraise=True` — see deviations section.
- **No delimiter wrap.** `extract_posting` wraps user text in `<job_posting>…</job_posting>` and sanitises any delimiter literals. Per PATTERNS §1 and RESEARCH §3, resume extraction passes the text bare because the structured `response_model=ResumeExtraction` is the prompt-injection guardrail (T-07-04). A delimiter would add tokens without strengthening the contract.
- **One extra test beyond the plan's stated 7.** Added `test_module_imports_cleanly` mirroring `test_extraction.py::TestPromptStructure::test_module_imports_cleanly` — protects against future regressions in the str.format() template (e.g., adding a literal `{...}` without doubling braces). Strictly additive.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] tenacity must `reraise=True` to honor the plan-mandated retry semantics**

- **Found during:** Task 2 (`test_extract_resume_retries_3x_then_raises` failed on first run with `tenacity.RetryError` instead of the plan-required `ValidationError`)
- **Issue:** The plan's `<behavior>` for Task 2 says "tenacity retries on ValidationError 3 times then re-raises", and must-haves truth #5 says "retries 3 times with exponential backoff then re-raises". The bare `@retry(wait=…, stop=…)` shape — copied verbatim from `extract_posting` — wraps the underlying exception as `RetryError` after exhaustion. This breaks Plan 04's downstream D-35 error mapping (which routes `pydantic.ValidationError` → 422 `extraction_failed` and `openai.APIError` family → 503 `llm_unavailable`).
- **Fix:** Added `reraise=True` to the `@retry` decorator on `extract_resume`. Tenacity now re-raises the underlying exception type after the third attempt.
- **Files modified:** `src/job_rag/extraction/resume_extractor.py`
- **Verification:** `tests/test_resume_extractor.py::TestExtractResume::test_extract_resume_retries_3x_then_raises` now passes; the test asserts both that `ValidationError` is raised (not `RetryError`) and that `create_with_completion.call_count == 3`.
- **Committed in:** `55b4a63` (folded into the Task 2 commit since the test was the contract that forced the fix)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug; tenacity reraise=True)
**Impact on plan:** Required for correctness — without it the plan's stated contract for Task 2 is violated and Plan 04's downstream error mapping breaks. No scope creep.

## Issues Encountered

- Initial Task-2 test run failed with `tenacity.RetryError` instead of `ValidationError` — documented as the auto-fix above. Resolved in the same commit cycle.

## User Setup Required

None. The new module imports work against the existing `OPENAI_API_KEY` + `settings.openai_model` config — same surface as the existing `extract_posting` flow.

## Next Plan Readiness

Plan 07-04 (upload routes + diff + Langfuse) can now:

- Import `from job_rag.extraction.resume_extractor import extract_resume` and call it via `await asyncio.to_thread(extract_resume, text)` from the new `POST /profile/upload` async handler.
- Use the `(ResumeExtraction, usage_info)` tuple shape: `usage_info` plugs into the Langfuse `llm_extract` span metadata directly (model, prompt_version, prompt_tokens, completion_tokens, total_tokens — exactly the keys Plan 04 D-32 enumerates).
- Catch `pydantic.ValidationError` and `openai.APIError` subclasses cleanly because `reraise=True` propagates the original types (the plan's D-16 / D-35 error mapping works as written).
- Field-copy `ResumeExtraction.min_salary_eur` → `UserSkillProfile.min_salary` inside `compute_skills_diff()` when mapping the extracted shape to the canonical user state.

Blockers: None.

## Self-Check: PASSED

Verified after writing this SUMMARY.md:

Files exist (each command exit 0):
- `test -f src/job_rag/extraction/resume_prompt.py` → FOUND (60 lines)
- `test -f src/job_rag/extraction/resume_extractor.py` → FOUND (70 lines)
- `grep -q 'class ResumeExtraction' src/job_rag/models.py` → FOUND
- `test -f tests/test_resume_extractor.py` → FOUND (8 tests, populated)

Commits exist (verified via `git log --oneline`):
- `b690744` → FOUND ("feat(07-03): resume_prompt + ResumeExtraction model + resume_extractor (PROF-03)")
- `55b4a63` → FOUND ("test(07-03): resume_extractor structured-output + 3x retry + prompt structure")

Functional checks:
- `uv run python -c "from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION; assert RESUME_PROMPT_VERSION == '1.0'"` → PASSED
- `uv run python -c "from job_rag.models import ResumeExtraction; m = ResumeExtraction.model_json_schema(); assert {'skills','target_roles','preferred_locations','min_salary_eur','remote_preference','years_experience'} <= m['properties'].keys()"` → PASSED
- `uv run pytest tests/test_resume_extractor.py -v` → 8 passed
- `uv run pytest tests/test_resume_extractor.py -k 'structured_output or retries_3x' -x` → 1 passed, 7 deselected (acceptance criteria 07-03-04 and 07-03-05)
- `uv run pyright src/job_rag/extraction/` → 0 errors, 0 warnings, 0 informations
- `uv run ruff check src/job_rag/extraction/ tests/test_resume_extractor.py src/job_rag/models.py` → All checks passed
- Full backend suite (with DATABASE_URL set): `198 passed, 12 skipped, 1 deselected` — 0 regressions from Plan 03

## TDD Gate Compliance

Plan 03 task 2 carries `tdd="true"`. Gate sequence in git log:

- Production code first: `b690744` feat(07-03): resume_prompt + ResumeExtraction model + resume_extractor — Task 1
- Tests second: `55b4a63` test(07-03): resume_extractor structured-output + 3x retry + prompt structure — Task 2 (GREEN)

The plan's Task 2 `<action>` explicitly inverted the conventional RED→GREEN order ("Plan 01 created an empty scaffold, then write the tests above; assuming Task 1 production code is committed first"): the production primitives in Task 1 are the contract Task 2 verifies. The Task 2 commit additionally folded in a `reraise=True` auto-fix to the Task 1 module — caught the moment the test ran — which makes Task 2 act simultaneously as GREEN (tests pass) and as a Rule 1 production fix. No separate REFACTOR commit needed.

---
*Phase: 07-profile-resume-upload*
*Plan: 03-resume-extractor*
*Completed: 2026-05-28*
