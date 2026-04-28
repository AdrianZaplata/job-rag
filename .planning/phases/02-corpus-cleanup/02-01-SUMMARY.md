---
phase: 02-corpus-cleanup
plan: 01
subsystem: database
tags: [pydantic, sqlalchemy, strenum, schema-evolution, location, skill-taxonomy]

requires:
  - phase: 01-backend-prep
    provides: SQLAlchemy 2.x Mapped[] ORM, JobPostingDB/JobRequirementDB baseline, alembic infrastructure
provides:
  - SkillType (renamed 8-value enum) + new SkillCategory(hard/soft/domain) in models.py
  - derive_skill_category(skill_type) deterministic 8→3 mapping helper
  - Location Pydantic submodel (country alpha-2, city, region — all nullable)
  - JobRequirement carrying both skill_type (LLM) + skill_category (derived)
  - JobPostingDB.location_country/city/region flat columns + ix_job_postings_location_country
  - JobRequirementDB.skill_type/skill_category columns + matching indexes
  - Updated test_models.py + sample_posting fixture mirroring new schema
affects: [02-02 (prompt rewrite), 02-03 (migration 0004), 02-04 (reextract service + corpus run), 03 (infrastructure references schema)]

tech-stack:
  added: []
  patterns:
    - "Two-axis skill taxonomy: LLM extracts kind (SkillType, 8 values), code derives category (SkillCategory, 3 values) via pure-function helper in models.py"
    - "Pydantic submodel ↔ flat DB columns (Location ↔ location_country/city/region) — avoids PostgreSQL composite type complexity per D-11"
    - "Identity comparisons (`is`) for StrEnum singletons in pure-function helpers"

key-files:
  created: []
  modified:
    - src/job_rag/models.py
    - src/job_rag/db/models.py
    - tests/test_models.py
    - tests/conftest.py

key-decisions:
  - "Used `is` (identity) not `==` for StrEnum comparisons in derive_skill_category — StrEnum members are singletons and `is` is faster + clearer"
  - "Description on Location.country reads 'ISO-3166 alpha-2 code (DE, PL, US, GB, ...)' — propagates to LLM via Instructor JSON Schema (Pitfall 3 mitigation)"
  - "Added test_string_location_rejected and test_old_category_field_rejected as rename gates — catch any accidental partial-revert"

patterns-established:
  - "Pure-function helper colocated with its enums in models.py (D-03 / CONTEXT.md convention)"
  - "Sample-posting fixture wraps every JobRequirement with derive_skill_category(SkillType.X) call to keep skill_category in lockstep with skill_type"

requirements-completed: [CORP-02, CORP-03]

duration: 4m
completed: 2026-04-28
---

# Phase 2 Plan 01: Schema Evolution Summary

**SkillType/SkillCategory two-axis taxonomy + Location Pydantic submodel landed across Pydantic models, SQLAlchemy ORM, and test fixtures — Phase 2's source-of-truth schema is now in place.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-28T07:24:08Z
- **Completed:** 2026-04-28T07:28:05Z
- **Tasks:** 3 (all auto, all TDD where applicable)
- **Files modified:** 4

## Accomplishments

- `models.py`: Renamed existing `SkillCategory(8 values)` → `SkillType`; added new 3-value `SkillCategory(HARD/SOFT/DOMAIN)`; added `derive_skill_category()` deterministic mapper (D-03); added `Location(country/city/region)` BaseModel with all-nullable fields (D-09).
- `db/models.py`: Renamed `JobRequirementDB.category` → `skill_type`; added `skill_category` column; dropped `JobPostingDB.location` and added flat `location_country/city/region` columns (D-11); swapped indexes; added `ix_job_postings_location_country` (Phase 5 dashboard heavy filter).
- `tests/test_models.py`: Added `TestSkillType`, `TestSkillCategoryDerivation` (parametrized 8→3), `TestLocation` (parametrized 5 cases inc. all-null), `TestJobRequirementBothFields`; rewrote existing `TestJobRequirement` / `TestJobPosting` to new schema; added rename-gate tests.
- `tests/conftest.py`: Updated `sample_posting` fixture to use `Location(country="DE", city="Berlin", region=None)` and 8 `JobRequirement(...)` constructors with `skill_type=` + `skill_category=derive_skill_category(...)`.

## Task Commits

1. **Task 1: Rewrite models.py — SkillType/SkillCategory split + Location** — `a0876fc` (feat)
2. **Task 2: Update db/models.py — skill_type/skill_category + flat location_* columns** — `dc773af` (feat)
3. **Task 3: Extend tests + update conftest fixture** — `959cbf1` (test)

_Note: TDD steps for Tasks 1-2 verified via inline `python -c "..."` import-fail-then-pass smoke; the comprehensive test classes landed in Task 3 per the plan's structure (test classes are heavier and benefit from co-landing with the fixture rewrite)._

## Files Created/Modified

- `src/job_rag/models.py` — `SkillType` enum (8 vals), `SkillCategory` enum (3 vals), `derive_skill_category()` helper, `Location` submodel, `JobRequirement` (skill_type + skill_category), `JobPosting.location: Location`. Other classes unchanged.
- `src/job_rag/db/models.py` — `JobRequirementDB`: `category` → `skill_type` + new `skill_category`; indexes swapped. `JobPostingDB`: `location` removed, three `location_*` nullable columns added, new `ix_job_postings_location_country`. `UserDB`/`UserProfileDB`/`JobChunkDB` untouched (D-12 invariant preserved).
- `tests/test_models.py` — 4 new test classes (`TestSkillType`, `TestSkillCategoryDerivation`, `TestLocation`, `TestJobRequirementBothFields`) + rewritten `TestJobRequirement` / `TestJobPosting` for new schema. 31 tests pass.
- `tests/conftest.py` — `sample_posting` fixture rebuilt against new schema; import block adds `Location`, `SkillType`, `derive_skill_category`; removed unused `SkillCategory`.

## Decisions Made

- **`is` vs `==` in `derive_skill_category`**: chose identity comparison since StrEnum members are singletons. Faster and clearer intent.
- **Test rename-gate**: added `test_old_category_field_rejected` and `test_string_location_rejected`. These act as tripwires for any future accidental schema drift back to the old shape.
- **Wrapped LangChain not affected**: schema rewrite stays inside Pydantic / SQLAlchemy layer; downstream service / api / mcp call sites NOT touched in this plan (they belong to subsequent Phase 2 plans per the plan's `<verification>` note about expected full-suite reds).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Three ruff E501 + F401 errors after initial implementation**
- **Found during:** Task 3 verification (running `ruff check` after writing tests)
- **Issue:** Two `E501 Line too long (>100)` violations on the new `skill_type: SkillType = Field(description=...)` line in `models.py` and the new `# skill_category derived...` comment in `db/models.py`; one `F401 SkillCategory imported but unused` in `tests/conftest.py` (kept import block clean — derive_skill_category() returns the SkillCategory but the fixture never references it directly).
- **Fix:** (a) Split the long Field description into a parenthesized two-string concat; (b) shortened the comment by removing "time"; (c) removed `SkillCategory` from conftest.py imports.
- **Files modified:** `src/job_rag/models.py`, `src/job_rag/db/models.py`, `tests/conftest.py`
- **Verification:** `uv run ruff check` → all checks passed; `uv run pyright` → 0 errors; `uv run pytest tests/test_models.py` → 31 passed.
- **Committed in:** `959cbf1` (Task 3 commit — folded into the test+fixture commit since the fixes were inline with that task's writes).

---

**Total deviations:** 1 auto-fixed (3 lint sub-fixes, all in Rule 1 scope as my own newly-written code violating in-tree style)
**Impact on plan:** Pure style polish. No semantic change. No scope creep.

## Issues Encountered

None — verification commands ran cleanly and all 31 tests pass on the first GREEN attempt after the lint polish.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 02-02 (prompt rewrite) ready**: `models.py` exports `SkillType` (the LLM-extracted enum the prompt references) and `Location` (which the LLM must produce structured output for). `PROMPT_VERSION` bump to "2.0" is Plan 02-02's job.
- **Plan 02-03 (migration 0004) ready**: ORM column shapes in `db/models.py` are the contract the migration must mirror exactly (`alembic check` no-drift gate). String lengths: country `String(2)`, city `String(255)`, region `String(100)`, skill_type/skill_category `String(20)`.
- **Plan 02-04 (reextract service + corpus run) ready**: `derive_skill_category()` is the helper the reextract service will call at write time. `JobRequirement` shape matches what `extract_posting()` returns into.
- **Expected full-suite reds (acknowledged in the plan)**: `services/ingestion.py`, `services/matching.py`, `services/retrieval.py`, `mcp_server/tools.py`, `cli.py`, `api/app.py` still reference the old field names. Plan 02-02 fixes prompt + extraction; Plan 02-04 sweeps service + DB call sites. NOT in scope for 02-01.

## Self-Check: PASSED

- [x] `src/job_rag/models.py` exists and contains `class SkillType(StrEnum):` (verified via Read).
- [x] `src/job_rag/db/models.py` exists and contains `skill_type` (verified via Edit context).
- [x] `tests/test_models.py` exists and contains `class TestSkillCategoryDerivation` (verified via Write).
- [x] `tests/conftest.py` exists and contains `Location(country=` (verified via Edit).
- [x] Commit `a0876fc` exists in `git log` (Task 1).
- [x] Commit `dc773af` exists in `git log` (Task 2).
- [x] Commit `959cbf1` exists in `git log` (Task 3).

---
*Phase: 02-corpus-cleanup*
*Completed: 2026-04-28*
