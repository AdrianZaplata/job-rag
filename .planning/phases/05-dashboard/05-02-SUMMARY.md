---
phase: 05-dashboard
plan: 02
subsystem: api
tags: [sqlalchemy, pgvector, percentile_cont, pydantic, async, fastapi, analytics]

# Dependency graph
requires:
  - phase: 05-dashboard
    provides: "Plan 05-01 skip-guarded test scaffolds in tests/test_analytics.py + dashboard_postings_factory fixture in tests/conftest.py"
  - phase: 02-corpus-cleanup
    provides: "JobPostingDB.location_country / location_region / salary_period / skill_category columns the analytics module aggregates over"
  - phase: 01-backend-prep
    provides: "user_id-aware load_profile + match_posting signature reused by cv_match"
provides:
  - "src/job_rag/services/analytics.py with 3 async public functions (top_skills, salary_bands, cv_match), 1 private _apply_filters helper, EU_COUNTRY_CODES frozenset (27 ISO-3166 alpha-2 codes)"
  - "src/job_rag/api/dashboard.py with 5 Pydantic BaseModel response classes (TopSkillItem, DashboardTopSkillsResponse, DashboardSalaryBandsResponse, MissingSkillItem, DashboardCvMatchResponse) + 2 StrEnums (CountryFilter, RemoteFilter)"
  - "27 tests in tests/test_analytics.py activated (Plan 05-01 skip-guards flipped from SKIPPED to PASSED)"
affects: [05-03-api-routes, 05-04-hooks, 05-05-widgets, 05-06-route-integration]

# Tech tracking
tech-stack:
  added: []  # No new dependencies — pure code addition on existing SQLAlchemy 2.x + Pydantic stack
  patterns:
    - "Service module with shared _apply_filters helper that mutates a SQLAlchemy select with country/seniority/remote WHERE clauses (D-07/08/09)"
    - "Hybrid SQL pre-filter + Python fold pattern for cv_match: SQL narrows postings via _apply_filters, Python folds match_posting() to preserve the alias-aware fuzzy matching"
    - "Pydantic response models in api/<feature>.py drive OpenAPI named schemas for downstream openapi-typescript codegen"
    - "Test strategy for SQL-heavy async functions: MagicMock AsyncSession + AsyncMock on session.execute with side_effect ordered to match the implementation's execute() call sequence"
    - "SQL stmt assertion via stmt.whereclause.compile(literal_binds=True) instead of full-stmt string match (avoids false-positives on SELECT column lists)"

key-files:
  created:
    - src/job_rag/services/analytics.py
    - src/job_rag/api/dashboard.py
    - .planning/phases/05-dashboard/deferred-items.md
  modified:
    - tests/test_analytics.py
    - tests/conftest.py

key-decisions:
  - "Test strategy: MagicMock+AsyncMock instead of in-memory SQLite. aiosqlite is not a project dependency, SQLite doesn't support PostgreSQL percentile_cont (Pitfall 1), and pgvector's Vector(1536) column would need workarounds to materialize against SQLite. Mocking session.execute mirrors the existing test_lifespan.py pattern."
  - "SQL stmt assertions inspect stmt.whereclause specifically, not the full compiled string. select(JobPostingDB) always includes every JobPostingDB column in the SELECT clause (location_country, remote_policy, etc.), so a substring match on the entire compiled SQL false-positives even when no WHERE clause is present."
  - "Test class TestEuCountrySetMembership uses async test methods (no-op await) to satisfy the module-level pytestmark = pytest.mark.asyncio without warnings. A class-level pytestmark override didn't suppress the warning under pytest-asyncio."
  - "EU_COUNTRY_CODES is declared as frozenset[str] = frozenset({...}) so attempts to call .add() raise AttributeError at runtime (T-5-02-03 immutability). Snapshot date 2026-05-22 is documented in the module docstring."

patterns-established:
  - "Service-layer analytics module: src/job_rag/services/analytics.py exports async functions that accept an AsyncSession + filter kwargs, return plain dicts. Routes layer (Plan 05-03) wraps these with Pydantic response models from api/dashboard.py."
  - "Filter mutation helper: _apply_filters(stmt, *, country, seniority, remote) is the canonical shape for filter composition; routes pass user-supplied query params verbatim."
  - "EU country resolution: union branch OR(location_country IN EU_COUNTRY_CODES, location_region == 'EU') catches both ISO-coded EU postings AND D-09 NULL-country 'Remote (EU)' rows."
  - "Salary normalization: month → year via CASE WHEN salary_period = 'month' THEN salary_min * 12 ELSE salary_min END in the percentile_cont sort expression. Hourly excluded."
  - "Zero-state SQL handling for cv_match: early return {mean_score: None, postings_compared: 0, top_missing_must_have: []} BEFORE invoking load_profile() / match_posting() to avoid wasted work and 404-vs-200 ambiguity."

requirements-completed: [DASH-01, DASH-02, DASH-03]

# Metrics
duration: ~8 min
completed: 2026-05-22
---

# Phase 05 Plan 02: Analytics Service Module Summary

**Backend analytics service with top_skills SQL GROUP BY, salary_bands percentile_cont, and cv_match hybrid SQL+Python fold — backed by 27 passing tests covering all 6 test classes (DASH-01/02/03).**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-22T08:13:37Z
- **Completed:** 2026-05-22T08:21:24Z
- **Tasks:** 2
- **Files modified:** 5 (3 created + 2 modified)

## Accomplishments

- **DASH-01 ships:** `top_skills(session, *, country, seniority, remote, include_soft, limit)` server-side SQL GROUP BY aggregation with must/nice split via `case((cond,1),else_=0) + func.sum()`. Soft skills hidden by default via `WHERE skill_category != 'soft'` (D-13); `include_soft=True` flips the toggle.
- **DASH-02 ships:** `salary_bands(session, *, country, seniority, remote)` server-side PostgreSQL `percentile_cont(p25/p50/p75)` ordered-set aggregate via the mandatory `func.percentile_cont(0.X).within_group(<expr>.asc())` chain (RESEARCH Pitfall 1). Salary-period normalization: month rows treated as `salary_min * 12`; `hour` rows excluded entirely.
- **DASH-03 ships:** `cv_match(session, user_id, *, country, seniority, remote)` hybrid SQL pre-filter + Python fold. Uses `selectinload(JobPostingDB.requirements)` to avoid N+1 (Pitfall 14); reuses `match_posting()` formula verbatim (D-10); caps top missing must-haves at 3 via `Counter.most_common(3)` (D-11); D-12 zero-postings case returns `{mean_score: None, postings_compared: 0, top_missing_must_have: []}` without raising.
- **Plan 05-01 skip-guards activate:** all 27 tests in `tests/test_analytics.py` (across `TestTopSkills` × 4, `TestSalaryBands` × 5, `TestCvMatch` × 4, `TestApplyFilters` × 7, `TestEuCountrySetMembership` × 6, `TestFilterEffects` × 1) flipped from SKIPPED to PASSED with no test edits to the skip-guards themselves.
- **API contract Pydantic models in place:** 5 BaseModel response classes + 2 StrEnum filter types drive OpenAPI named-schema emission so Plan 05-04's `openapi-typescript` codegen produces named TS interfaces. `p25/p50/p75` declared `int | None` (Pitfall 2); `mean_score` declared `float | None` (D-12).
- **EU_COUNTRY_CODES committed:** immutable `frozenset[str]` of exactly 27 ISO-3166 alpha-2 codes (snapshot 2026-05-22), sorted: `['AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK']`. ISO `GR` for Greece (not EU protocol `EL`); `GB`/`UK` excluded (Brexit 2020-01-31).

## Task Commits

Each task was committed atomically (Task 1 was TDD with RED then GREEN commits):

1. **Task 1 RED: test bodies for analytics service** — `86e0aa8` (test)
2. **Task 1 GREEN: implement analytics service module** — `8f0038c` (feat)
3. **Task 2: dashboard Pydantic response models + filter enums** — `58556c3` (feat)

## Files Created/Modified

**Created:**
- `src/job_rag/services/analytics.py` (~240 lines) — 3 async public functions + 1 private filter helper + EU_COUNTRY_CODES frozenset
- `src/job_rag/api/dashboard.py` (~125 lines) — 5 Pydantic BaseModels + 2 StrEnum filter types
- `.planning/phases/05-dashboard/deferred-items.md` — log of pre-existing alembic env-var test failures (out of scope per executor scope boundary)

**Modified:**
- `tests/test_analytics.py` — replaced 27 `pytest.skip()` placeholder bodies with real assertions using MagicMock+AsyncMock; converted 6 sync tests in TestEuCountrySetMembership to async to suppress pytest-asyncio warnings
- `tests/conftest.py` — removed `user_id` kwarg from `dashboard_postings_factory._build_posting` (Plan 05-01 fixture bug fix; see Deviations below)

## Decisions Made

**Test strategy:** MagicMock + AsyncMock instead of in-memory SQLite or real Postgres. Reasoning:

1. `aiosqlite` is not a current dependency, so adding it would expand the dep surface for tests only.
2. PostgreSQL `percentile_cont` does not run on SQLite — the salary_bands tests cannot use SQLite without a separate workaround.
3. `pgvector.Vector(1536)` mapped column on JobPostingDB would not materialize against SQLite without a type override.
4. The codebase already uses MagicMock + AsyncMock for AsyncSession in `tests/test_lifespan.py` and `tests/test_mcp_server.py`; the pattern is idiomatic.
5. Verification of SQL correctness shifts to `stmt.compile(literal_binds=True)` inspection — the implementation produces a SQLAlchemy Select object regardless of backend, and the structure (WHERE clauses, IN lists, JOIN targets) is what the tests assert.

**SQL stmt assertion technique:** When a test needs to assert the absence of a clause (e.g., "country=WW adds no WHERE"), inspect `stmt.whereclause` (None when nothing applied) rather than substring-matching the full compiled SQL string. The full SQL includes the SELECT column list which always names every column on JobPostingDB; substring matches on column names false-positive even when no WHERE clause is present.

**TDD execution shape:** Plan 05-01 had already scaffolded skip-guarded test classes with `pytest.skip("...")` body placeholders. Task 1 was executed as TDD with two commits: (1) RED — fill in real assertion bodies that still skip because analytics.py doesn't exist, (2) GREEN — ship analytics.py so the skip-guards flip to active and tests pass. The plan's `tdd="true"` marker maps to this two-commit shape.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed user_id kwarg from dashboard_postings_factory**
- **Found during:** Task 1 (TestCvMatch::test_returns_mean_score_postings_compared_top_missing)
- **Issue:** `tests/conftest.py::dashboard_postings_factory._build_posting` passed `user_id=uuid.uuid4()` to `JobPostingDB(...)`, but `JobPostingDB` has no `user_id` column. SQLAlchemy's declarative constructor raised `TypeError: 'user_id' is an invalid keyword argument for JobPostingDB`. The plan's `<interfaces>` block listed `user_id: Mapped[uuid.UUID]` on JobPostingDB, but the actual code (src/job_rag/db/models.py:11-59) does not have it — v1 corpus is global, keyed by `career_id='ai_engineer'`. Per-user data lives on `UserProfileDB` only.
- **Fix:** Removed the `user_id=user_id` line from the `JobPostingDB(...)` instantiation in `_build_posting`. Added a comment documenting that JobPostingDB has no user_id column.
- **Files modified:** `tests/conftest.py`
- **Verification:** `dashboard_postings_factory()` now produces 12 JobPostingDB rows without raising; all 4 TestCvMatch tests pass.
- **Committed in:** `8f0038c` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed TestApplyFilters tests asserting full compiled SQL instead of WHERE clause**
- **Found during:** Task 1 (TestApplyFilters::test_country_ww_no_filter)
- **Issue:** Tests asserted `"location_country" not in compiled_sql` to verify the WW branch adds no filter. But `select(JobPostingDB)` always includes `location_country` in the SELECT column list (along with every other column). The substring match false-positived even when no WHERE clause was added.
- **Fix:** Changed assertions to inspect `stmt.whereclause` directly: `assert stmt.whereclause is None` for no-filter cases, `str(stmt.whereclause.compile(literal_binds=True))` for filter-applied cases. Applied this pattern to all 7 TestApplyFilters tests for consistency.
- **Files modified:** `tests/test_analytics.py`
- **Verification:** All 7 TestApplyFilters tests pass; the assertion mode now distinguishes WHERE clauses from SELECT column lists.
- **Committed in:** `8f0038c` (Task 1 GREEN commit)

**3. [Rule 1 - Bug] Converted sync tests in TestEuCountrySetMembership to async**
- **Found during:** Task 1 (final test run cleanup)
- **Issue:** The module-level `pytestmark = pytest.mark.asyncio` applied to all tests in the module, but `TestEuCountrySetMembership` contained 6 sync test methods (pure constant inspection). Pytest-asyncio emitted 6 warnings: "marked with @pytest.mark.asyncio but it is not an async function". A class-level `pytestmark: list = []` override did not suppress the warning under the current pytest-asyncio version.
- **Fix:** Converted all 6 TestEuCountrySetMembership methods to `async def` (trivially awaitable, no actual await needed). Tests still pass; warnings disappear.
- **Files modified:** `tests/test_analytics.py`
- **Verification:** `uv run pytest tests/test_analytics.py` reports 27 passed, 0 warnings.
- **Committed in:** `8f0038c` (Task 1 GREEN commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs; 1 in conftest from Plan 05-01, 2 in my own test code during this plan)
**Impact on plan:** All auto-fixes are correctness fixes (conftest fixture was unusable; assertion modes were false-positiving). No scope creep. Plan's substantive contracts (3 async service functions, 5 Pydantic models, 2 StrEnums, EU_COUNTRY_CODES frozenset, all 27 tests passing) are intact.

## Issues Encountered

- **Pre-existing test_alembic.py failures:** Two tests (`test_0004_upgrade_smoke`, `test_0004_downgrade_smoke`) fail with `KeyError: 'DATABASE_URL'`. Reproduced on `git stash` of all Plan 05-02 changes — these failures pre-date this plan. Logged to `deferred-items.md` per executor scope-boundary rule (not caused by current task).

## Threat Model Coverage

| Threat ID | Mitigation Applied | Verification |
|-----------|--------------------|--------------|
| T-5-02-01 (Tampering, SQL clauses) | All filter values reach `_apply_filters` through Pydantic-validated enum types (Plan 05-03 boundary); the function uses parameterized SQLAlchemy expressions (`stmt.where(JobPostingDB.location_country == "PL")`); no raw string concatenation | TestApplyFilters tests inspect compiled SQL — all values are bound via SQLAlchemy parameter binding |
| T-5-02-02 (Information Disclosure) | Pydantic response models declare ONLY the dashboard surface fields (skill, count, percentage). No `posting_id`, no `user_id`, no PII | `grep -E "user_id\|posting_id" src/job_rag/api/dashboard.py` returns 0 hits |
| T-5-02-03 (Tampering, EU_COUNTRY_CODES) | Declared as `frozenset[str]` (immutable); .add() raises AttributeError. Snapshot date 2026-05-22 in module docstring with Wikipedia source citation | `EU_COUNTRY_CODES.add('XX')` raises AttributeError; `isinstance(EU_COUNTRY_CODES, frozenset)` is True (verified by TestEuCountrySetMembership::test_is_frozenset) |
| T-5-02-04 (DoS, percentile_cont at scale) | Accepted for v1 (~108 postings; percentile_cont is index-served by salary_min + salary_period filter) | n/a — accept disposition, revisit at corpus >1000 |
| T-INPUT-VALIDATION | CountryFilter / RemoteFilter StrEnums + existing Seniority enum reject bad strings at FastAPI Query() boundary (Plan 05-03 will wire) | `DashboardSalaryBandsResponse(p25="NaN")` raises ValidationError; verified via Pydantic schema inspection |
| T-AUTH-06 (carry) | Plan 05-03 wires `Depends(get_current_user_id)` on the new routes. This plan is service-layer only; `cv_match` accepts `user_id` as a typed parameter | Service module accepts but does not validate user_id; Plan 05-03 provides the validator |

## Verification Results

**Backend tests:**
```
$ uv run pytest tests/test_analytics.py -v
... 27 passed in 0.20s
```
- All 6 test classes (TestTopSkills, TestSalaryBands, TestCvMatch, TestApplyFilters, TestEuCountrySetMembership, TestFilterEffects) report 27/27 PASSED.
- No skipped tests, no warnings.

**EU_COUNTRY_CODES snapshot:**
```
$ uv run python -c "from job_rag.services.analytics import EU_COUNTRY_CODES as eu; assert len(eu) == 27; print(sorted(eu))"
['AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK']
```
- 27 members. DE/PL/GR included; GB/EL excluded.

**Pydantic response model integrity:**
```
$ uv run python -c "from job_rag.api.dashboard import DashboardSalaryBandsResponse as M; print(M.model_json_schema())"
... "p25": {"anyOf": [{"type": "integer"}, {"type": "null"}], ...
... "currency": {"default": "EUR", "type": "string", ...
```
- p25/p50/p75 emit `anyOf[integer, null]` (Pitfall 2 contract).
- currency defaults to "EUR".

**Style + type checks:**
```
$ uv run ruff check src/job_rag/services/analytics.py src/job_rag/api/dashboard.py
All checks passed!

$ uv run pyright src/job_rag/services/analytics.py src/job_rag/api/dashboard.py
0 errors, 0 warnings, 0 informations
```

**Full backend suite (regression check):**
```
$ uv run pytest
... 226 passed, 19 skipped, 2 failed (pre-existing alembic env-var failures; see deferred-items.md)
```

## User Setup Required

None — pure backend service-layer code addition. No new env vars, no migrations, no external service configuration.

## Next Phase Readiness

Plan 05-03 (API routes) can immediately:
- Import `top_skills`, `salary_bands`, `cv_match` from `job_rag.services.analytics`
- Import `CountryFilter`, `RemoteFilter`, `DashboardTopSkillsResponse`, `DashboardSalaryBandsResponse`, `DashboardCvMatchResponse` from `job_rag.api.dashboard`
- Wire `Depends(get_current_user_id)` on the 3 new routes (T-AUTH-06 follow-through)
- Wire `Depends(standard_limit)` on the 3 new routes (T-RATE-LIMIT)
- The `TestDashboardEndpoints` skip-guard in `tests/test_api.py` will flip to active automatically once routes register

Plan 05-04 (openapi-typescript codegen) can then run after Plan 05-03 emits the OpenAPI surface.

## EU_COUNTRY_CODES Literal (as committed)

```python
EU_COUNTRY_CODES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
})
```

## Test Approach Note (for Plan 05-03)

Plan 05-03 should use the same MagicMock+AsyncMock pattern for its endpoint tests (in `tests/test_api.py::TestDashboardEndpoints`). Do NOT introduce SQLite or aiosqlite; the service-layer tests are mocked, so the route-layer tests should mock `_apply_filters` callees as well or directly mock `analytics.top_skills`/`salary_bands`/`cv_match`.

## Self-Check

Verifications below confirm claims above are accurate as of completion time.

### File existence
- `src/job_rag/services/analytics.py`: FOUND
- `src/job_rag/api/dashboard.py`: FOUND
- `.planning/phases/05-dashboard/deferred-items.md`: FOUND
- `tests/test_analytics.py`: FOUND (modified, 27 tests pass)
- `tests/conftest.py`: FOUND (modified, user_id removed from fixture)

### Commits
- `86e0aa8` (Task 1 RED — test bodies): FOUND
- `8f0038c` (Task 1 GREEN — analytics.py + conftest fix + test cleanups): FOUND
- `58556c3` (Task 2 — dashboard.py Pydantic models): FOUND

## Self-Check: PASSED

---
*Phase: 05-dashboard*
*Completed: 2026-05-22*
