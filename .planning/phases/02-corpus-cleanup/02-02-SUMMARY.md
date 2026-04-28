---
phase: 02-corpus-cleanup
plan: 02
subsystem: extraction
tags: [prompt-engineering, str-format, rejection-rules, location-extraction, prompt-versioning]

requires:
  - phase: 02-corpus-cleanup
    plan: 01
    provides: "SkillType / SkillCategory enums + Location submodel referenced by prompt's REJECTION RULES + LOCATION EXTRACTION + skill_category-derived note"
provides:
  - "PROMPT_VERSION = '2.0' (bumped from 1.1) — drift signal for downstream observability"
  - "REJECTED_SOFT_SKILLS tuple: 22 universal LinkedIn fluff terms (single source of truth)"
  - "_SYSTEM_PROMPT_TEMPLATE + str.format()-built SYSTEM_PROMPT (Pattern 2 / Pitfall 4)"
  - "REJECTION RULES + LOCATION EXTRACTION + borderline + spoken-language carve-outs"
  - "TestPromptStructure / TestRejectionRulesUnit / TestRejectionRulesLive coverage"
  - "integration pytest marker registered in pyproject.toml"
affects: [02-03 (migration referencing PROMPT_VERSION), 02-04 (reextract service consumes new prompt + schema)]

tech-stack:
  added: []
  patterns:
    - "str.format() with single named placeholder ({rejected_terms}) — bypasses f-string brace-doubling for embedded JSON-array literals (Pattern 2)"
    - "Brace-doubling ({{ }}) limited to 4 LOCATION EXTRACTION example lines — small reviewable surface"
    - "Module-level template + .format() invocation at import time → import-error gate for prompt syntax bugs"
    - "@pytest.mark.integration marker for live-LLM round-trips excluded from default CI"

key-files:
  created: []
  modified:
    - src/job_rag/extraction/prompt.py
    - tests/test_extraction.py
    - pyproject.toml

key-decisions:
  - "Used str.format() with single {rejected_terms} placeholder over f-string — 8 existing decomposition examples contain literal JSON-array brackets that would require brace-doubling under f-string. str.format() ignores all braces except the named placeholder, so existing examples ride through unmodified. Brace-doubling required only on 4 LOCATION EXTRACTION example lines."
  - "Test file uses Pydantic JobPosting/Location/SkillType constructors (Plan 02-01 schema) directly — confirms cross-plan integration works in same wave."
  - "Existing TestExtractPosting test updated to use Location submodel rather than free-text location — proves Plan 01's Pydantic rewrite + Plan 02's prompt rewrite compose cleanly."
  - "Added 'integration' marker as a list-extension to existing pyproject.toml markers — preserves the 'eval' marker untouched."

patterns-established:
  - "Single-source-of-truth tuple for prompt-time taxonomy: REJECTED_SOFT_SKILLS lives in prompt.py and is interpolated via str.format() into the SYSTEM_PROMPT — no two-list drift risk"
  - "Module-load-time template build (SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(...)) acts as an import-time syntax gate; test_module_imports_cleanly is the canonical anti-regression for Pitfall 4"

requirements-completed: [CORP-01]

duration: ~6m
completed: 2026-04-28
---

# Phase 2 Plan 02: Prompt Tightening Summary

**Tightened the extraction prompt with PROMPT_VERSION 2.0, a 22-term REJECTED_SOFT_SKILLS tuple, str.format()-built SYSTEM_PROMPT preserving 8 decomposition examples verbatim, and 4 new LOCATION EXTRACTION examples — all under one named placeholder so brace-doubling stays surgical (4 lines, not the whole template).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-28
- **Completed:** 2026-04-28
- **Tasks:** 2 (Task 1: prompt rewrite; Task 2: test extension + marker registration)
- **Files modified:** 3

## Accomplishments

- `src/job_rag/extraction/prompt.py`: Bumped `PROMPT_VERSION` 1.1 → 2.0 (D-22). Added `REJECTED_SOFT_SKILLS` tuple of 22 universal LinkedIn fluff terms (D-18). Replaced bare `SYSTEM_PROMPT` literal with `_SYSTEM_PROMPT_TEMPLATE` + `str.format()` invocation interpolating one `{rejected_terms}` placeholder (Pattern 2 / Pitfall 4). Added REJECTION RULES, LOCATION EXTRACTION (4 D-09 examples with `{{ }}` doubling), borderline carve-out (leadership/mentoring/stakeholder management/cross-functional collaboration/team leadership → soft_skill per D-20), spoken-language carve-out (English/German/Polish/French → language per D-21 / Pitfall 7), and explicit "skill_category derived deterministically — Do NOT output skill_category" note (D-03). All 8 existing decomposition examples preserved verbatim with their literal JSON-array brackets intact.
- `tests/test_extraction.py`: Updated `test_prompt_version_is_set` assertion 1.1 → 2.0. Updated `TestExtractPosting::test_extract_returns_posting_and_usage` mock to use `Location(country="DE", city="Berlin", region=None)` instead of free-text string (Plan 02-01 schema). Added `TestPromptStructure` with 6 methods: module import gate, rejected-terms-in-prompt, 4 D-09 location example presence, borderline + spoken-language carve-outs, skill_category-code-derived note, decomposition-examples-preserved. Added `TestRejectionRulesUnit::test_extracted_skills_pass_through_verbatim` (LLM-mocked — proves no post-extraction filter; trust surface is the prompt). Added `TestRejectionRulesLive` (`@pytest.mark.integration`, skipped without `OPENAI_API_KEY`) for manual post-Phase-2 LLM round-trip validation.
- `pyproject.toml`: Added `integration: live LLM round-trips, excluded from default CI` to `[tool.pytest.ini_options].markers` list, preserving the existing `eval` marker.

## Task Commits

1. **Task 1: Rewrite prompt.py — PROMPT_VERSION 2.0 + REJECTED_SOFT_SKILLS + str.format() SYSTEM_PROMPT** — `ce82abc` (feat)
2. **Task 2: Extend test_extraction.py with TestPromptStructure / RejectionRulesUnit / RejectionRulesLive + register integration marker** — `b2f2295` (test)

## Files Created/Modified

- `src/job_rag/extraction/prompt.py` — full rewrite (~57 → ~140 lines). Module docstring documents the str.format() decision and Pitfall 4 anti-regression. Other consumers (`extraction/extractor.py`) untouched — `SYSTEM_PROMPT` and `PROMPT_VERSION` exports preserved by name.
- `tests/test_extraction.py` — extended (~74 → ~225 lines). Existing `TestExtractLinkedInId` and `TestExtractPosting` preserved structurally; mock data updated for new schema. 3 new test classes added (8 new test methods total: 6 unit + 1 unit-mocked + 1 integration-skipped).
- `pyproject.toml` — single-line list extension (`markers = [...]`). No other sections touched.

## Decisions Made

- **str.format() over f-string** — 8 existing decomposition examples contain literal JSON-array brackets like `["automotive AI", ...]`. Under f-string, the `{` `}` characters in those examples would need doubling everywhere. str.format() ignores all braces except the named placeholder we declare, so the existing examples ride through unmodified. Brace-doubling is required ONLY on the 4 LOCATION EXTRACTION example lines (small, reviewable surface).
- **Trust surface for rejection** — `TestRejectionRulesUnit` confirms `extract_posting()` does NOT post-process / filter rejected terms. The SYSTEM_PROMPT's REJECTION RULES section IS the only enforcement. If the LLM ignores the rule, the rejected term will surface in the corpus — and `TestRejectionRulesLive` is the manual-run validator. This is documented in the threat register as `T-02-02-02` (accept).
- **Module-load-time template build** — `SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(...)` runs at import. `test_module_imports_cleanly` doubles as the canonical Pitfall 4 anti-regression: any future brace mishap surfaces as ImportError on first test execution rather than silently producing a malformed prompt.
- **Integration marker registration** — added to `pyproject.toml` so `pytest -m integration` runs the live-LLM tests and `pytest -m "not integration"` (default CI filter) skips them. Marker text matches the convention of the existing `eval` marker.

## Deviations from Plan

None — both tasks executed exactly as planned.

The plan flagged that Task 2's verify command (`pytest tests/test_extraction.py::TestPromptStructure tests/test_extraction.py::TestRejectionRulesUnit -x -q -m "not integration"`) only passes if Plan 02-01's schema is also live (since `TestRejectionRulesUnit` constructs a `JobPosting` with the new Location/SkillType shapes). Plan 02-01 landed first in this same wave (commits `a0876fc..fd5073f`), so the verification ran cleanly: 7/7 new tests pass on the first GREEN.

The unrelated working-tree changes to `src/job_rag/models.py` and `src/job_rag/db/models.py` (post-Plan 02-01 lint-style polish on Field description line breaks and a comment shortening) were left untouched and unstaged — they are out of scope for Plan 02-02 per the SCOPE BOUNDARY rule.

## Issues Encountered

None — all verification commands passed cleanly on first run:

- Task 1 inline smoke (PROMPT_VERSION + len(REJECTED_SOFT_SKILLS) + REJECTION RULES + LOCATION EXTRACTION + 4 D-09 examples + borderline + decomposition substring): exit 0 first try.
- Task 2 pytest filter (`-m "not integration"`): 7/7 new tests pass; 14/14 total `test_extraction.py` tests pass with 1 deselected (the integration one).
- Final ruff: clean. Final pyright on prompt.py: 0 errors.

## User Setup Required

None — no external service configuration required. The `TestRejectionRulesLive` test will skip silently without `OPENAI_API_KEY`; setting it (already in Adrian's `.env`) opts into the ~€0.001 per-run live LLM round-trip when manually requested via `pytest tests/test_extraction.py -m integration`.

## Next Phase Readiness

- **Plan 02-03 (migration 0004) ready**: `PROMPT_VERSION = "2.0"` is the value the migration will need for any prompt_version-aware data steps. The migration itself does not touch `prompt_version` (it's a per-row column populated at re-extraction time, not at migration time).
- **Plan 02-04 (reextract service + corpus run) ready**: `extract_posting()` (unchanged) now produces `JobPosting` objects with `Location` submodel + `skill_type` enum + skill_category derived in code; the prompt enforces 22 rejected terms; the reextract service can iterate stale rows (`WHERE prompt_version != '2.0'`), call `extract_posting()` on `raw_text`, and the prompt does the rejection work. `REJECTED_SOFT_SKILLS` is importable for any future post-extraction validation harness.
- **Drift detection ready**: `PROMPT_VERSION = "2.0"` + the 108 existing postings still carrying `prompt_version = "1.1"` means `job-rag list --stats` (Plan 02-03) will surface the drift after the migration lands; lifespan startup (Plan 02-03) will emit the structured warning.

## Self-Check: PASSED

- [x] `src/job_rag/extraction/prompt.py` exists and contains `PROMPT_VERSION = "2.0"` (verified via Write).
- [x] `src/job_rag/extraction/prompt.py` exports `REJECTED_SOFT_SKILLS` (verified via Task 1 import smoke).
- [x] `tests/test_extraction.py` exists and contains `class TestPromptStructure` (verified via Write).
- [x] `tests/test_extraction.py` contains `class TestRejectionRulesUnit` and `class TestRejectionRulesLive` (verified via Write).
- [x] `pyproject.toml` lists `integration` in `[tool.pytest.ini_options].markers` (verified via Edit).
- [x] Commit `ce82abc` exists in `git log` (Task 1).
- [x] Commit `b2f2295` exists in `git log` (Task 2).

---
*Phase: 02-corpus-cleanup*
*Completed: 2026-04-28*
