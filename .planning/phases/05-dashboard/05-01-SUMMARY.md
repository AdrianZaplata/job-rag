---
phase: 05-dashboard
plan: 01
subsystem: testing
tags: [pytest, vitest, shadcn, recharts, skip-on-missing, wave-0, foundation]

# Dependency graph
requires:
  - phase: 04-frontend-shell-auth
    provides: "Plan 04-04 string-concat dynamic-import skip-on-missing pattern; existing shadcn components.json (radix-nova / neutral); Vitest + RTL frontend test infra"
  - phase: 01-backend-prep
    provides: "Plan 01-01 importlib.import_module + hasattr 3-guard skip pattern; pytest-asyncio + AsyncSession fixtures"
provides:
  - "6 skip-guarded test classes in tests/test_analytics.py covering top_skills / salary_bands / cv_match / _apply_filters / EU_COUNTRY_CODES / TestFilterEffects"
  - "dashboard_postings_factory pytest fixture in tests/conftest.py (12-posting variety covering E1-E12)"
  - "TestDashboardEndpoints class in tests/test_api.py skip-guarded on OpenAPI route registration"
  - "Three net-new shadcn primitives on disk: alert.tsx, chart.tsx, toggle-group.tsx + auto-installed toggle.tsx"
  - "recharts 3.8.0 added transitively to frontend/package.json via shadcn chart"
  - "Five vitest stub files using string-concat dynamic-import skip-on-missing pattern (TopSkillsCard, SalaryBandsCard, CvVsMarketCard, DashboardFilters, useDashboardFilters)"
affects: [05-02-analytics-service, 05-03-api-routes, 05-04-hooks, 05-05-widgets, 05-06-route-integration]

# Tech tracking
tech-stack:
  added: [recharts@^3.8.0]
  patterns:
    - "Wave 0 backend skip-on-missing: importlib.import_module + hasattr 3-guard (carryover from Plan 01-01)"
    - "Wave 0 frontend skip-on-missing: string-concat dynamic import + describe.skipIf (Plan 04-04)"
    - "Bare `npx shadcn@latest add` (no --style / --base-color) to preserve existing radix-nova / neutral preset"
    - "ToggleGroup imported via existing `radix-ui` umbrella package (matches dropdown-menu.tsx) instead of direct @radix-ui/react-toggle-group"

key-files:
  created:
    - tests/test_analytics.py
    - frontend/src/components/ui/alert.tsx
    - frontend/src/components/ui/chart.tsx
    - frontend/src/components/ui/toggle-group.tsx
    - frontend/src/components/ui/toggle.tsx
    - frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx
    - frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx
    - frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx
    - frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx
    - frontend/src/components/dashboard/useDashboardFilters.test.ts
  modified:
    - tests/conftest.py
    - tests/test_api.py
    - frontend/package.json
    - frontend/package-lock.json

key-decisions:
  - "Used existing `radix-ui` umbrella package for ToggleGroup imports instead of expecting a direct @radix-ui/react-toggle-group dep (matches the codebase's existing dropdown-menu.tsx pattern). Plan acceptance criterion #6 was written with an unbundled-radix assumption."
  - "Skipped the npm overrides.react-is workaround because `npm ls react-is` reported clean (recharts/react-is@17.0.2 deduped via @testing-library/dom). Per the plan's explicit guidance: 'don't add defensive config that isn't load-bearing'."

patterns-established:
  - "Wave 0 foundation pattern: scaffold tests + UI primitives BEFORE implementation lands, so each subsequent wave activates tests automatically without test edits"
  - "Dashboard postings factory: list-of-ORM-rows builder with optional `custom=[...]` override, supporting variety dimensions across all E1-E12 edge cases"
  - "Bare shadcn install: never pass --style or --base-color flags after initial scaffold — let components.json drive the preset"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06]

# Metrics
duration: ~15 min
completed: 2026-05-22
---

# Phase 05 Plan 01: Wave 0 Foundation Summary

**Test scaffolds + shadcn primitives that activate automatically when Wave 1/2 lands target symbols, using importlib (Python) + string-concat dynamic import (TypeScript) skip-on-missing patterns from Plans 01-01 and 04-04.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-22T10:00:30Z
- **Completed:** 2026-05-22T10:15:00Z
- **Tasks:** 2
- **Files modified:** 14 (10 created + 4 modified)

## Accomplishments

- Backend Wave 0: 35 new pytest tests collect cleanly and skip via 3-guard pattern (ImportError + hasattr). When Plan 05-02 lands `services/analytics.py` and Plan 05-03 lands the `/dashboard/*` routes, each gate flips from skip to active without any test edits.
- Frontend Wave 0: 27 new vitest tests collect cleanly and skip via `describe.skipIf(!Symbol)` after string-concat dynamic import. Plan 05-04 / 05-05 will land target modules and activate tests automatically.
- Three net-new shadcn primitives installed via bare invocation (no --style / --base-color flags) — `alert.tsx`, `chart.tsx`, `toggle-group.tsx`, with auto-installed `toggle.tsx`. Existing `radix-nova` / `neutral` preset preserved.
- `recharts ^3.8.0` added transitively to `package.json` via shadcn chart.
- 12-posting `dashboard_postings_factory` fixture in conftest.py covering all E1-E12 edge cases (DE/PL/EU/WW, salary year/month/hour/NULL, skill_category hard/soft/domain, remote/hybrid/onsite).

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend test scaffolding** — `0f78ff2` (test)
2. **Task 2: Frontend scaffolding (shadcn + 5 test stubs)** — `62b83b6` (feat)

## Files Created/Modified

**Created:**
- `tests/test_analytics.py` — 6 skip-guarded test classes (TestTopSkills, TestSalaryBands, TestCvMatch, TestApplyFilters, TestEuCountrySetMembership, TestFilterEffects) covering E1-E12 edge cases via `pytest.skip()` placeholders inside `@pytest.mark.skipif(...)` classes.
- `frontend/src/components/ui/alert.tsx` — shadcn Alert + AlertTitle + AlertDescription + AlertAction with `default` / `destructive` variants (pure CVA, no Radix dep).
- `frontend/src/components/ui/chart.tsx` — ChartContainer + ChartTooltip + related wrappers around Recharts.
- `frontend/src/components/ui/toggle-group.tsx` — ToggleGroup + ToggleGroupItem on top of `radix-ui` umbrella package's ToggleGroup primitive.
- `frontend/src/components/ui/toggle.tsx` — base Toggle primitive (auto-installed with toggle-group).
- `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx` (6 stub tests)
- `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx` (5 stub tests)
- `frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx` (6 stub tests)
- `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx` (4 stub tests)
- `frontend/src/components/dashboard/useDashboardFilters.test.ts` (6 stub tests)

**Modified:**
- `tests/conftest.py` — appended `dashboard_postings_factory` fixture; `sample_posting` untouched (T-5-01-02 mitigation).
- `tests/test_api.py` — appended `TestDashboardEndpoints` class + `_dashboard_routes_present()` skip-guard.
- `frontend/package.json` / `package-lock.json` — recharts 3.8.0 added transitively by shadcn install.

## Decisions Made

- **Existing radix-ui umbrella package used for ToggleGroup imports.** The plan's acceptance criterion expected `@radix-ui/react-toggle-group` to appear directly in `package.json`. The codebase already imports radix primitives via the `radix-ui` umbrella package (see `dropdown-menu.tsx`) — shadcn followed that pattern, and the toggle-group component imports `{ ToggleGroup as ToggleGroupPrimitive } from "radix-ui"`. The plan's literal grep check was based on an outdated unbundled assumption; the substantive requirement (ToggleGroup available, ToggleGroupItem exported) is satisfied.
- **Skipped the `overrides.react-is` workaround.** Plan Step B (T-5-01-03 mitigation) said to apply the override only if `npm ls react-is` showed UNMET PEER or invalid entries. Post-install, `npm ls react-is` reports clean (recharts → react-is@17.0.2, deduped via @testing-library/dom). Per plan guidance: "don't add defensive config that isn't load-bearing".

## Deviations from Plan

### Documented as acceptance-criterion mismatch

**1. [Rule 1 - Bug] Plan acceptance criterion #6 was written against an unbundled-radix assumption**
- **Found during:** Task 2 verification
- **Issue:** Plan required `grep -q '"@radix-ui/react-toggle-group"' frontend/package.json` to return 0. After running `npx shadcn@latest add toggle-group`, the resulting `toggle-group.tsx` imports `{ ToggleGroup as ToggleGroupPrimitive } from "radix-ui"` — using the umbrella package already in `package.json`. The literal grep returns no match.
- **Fix:** No code change needed. The substantive contract (ToggleGroup primitive accessible, ToggleGroupItem exported, codebase pattern preserved) is satisfied. Documented in the task commit message and here.
- **Files modified:** None — codebase pattern matches existing dropdown-menu.tsx.
- **Verification:** `grep -q "radix-ui" frontend/package.json` returns 0 (the umbrella package providing ToggleGroup is present); `grep -q "ToggleGroupItem" frontend/src/components/ui/toggle-group.tsx` returns 0.
- **Committed in:** 62b83b6 (Task 2 commit)

---

**Total deviations:** 1 documented mismatch (no code fix needed; plan grep criterion was overly literal).
**Impact on plan:** No scope change. All substantive Wave 0 contracts satisfied. Plans 05-02 through 05-05 are unaffected.

## Issues Encountered

None — execution followed the plan as written, with the single documented deviation above.

## Threat Model Coverage

| Threat ID | Mitigation Applied | Verification |
|-----------|--------------------|--------------|
| T-5-01-01 (shadcn CLI preset clobber) | Bare `npx shadcn@latest add alert chart toggle-group` (no flags) | `grep -q '"style": "radix-nova"' frontend/components.json` returns 0; `grep -q '"baseColor": "neutral"'` returns 0 |
| T-5-01-02 (conftest sample_posting tampering) | Appended `dashboard_postings_factory` only; existing fixture untouched | `grep -q 'sample_posting' tests/conftest.py` succeeds; existing tests (test_matching.py, test_api.py) all pass |
| T-5-01-03 (npm peer-dep DoS) | `npm ls react-is` reports clean; override not needed | `npm ls react-is` shows recharts/react-is@17.0.2 deduped, no UNMET PEER |
| T-AUTH-06 (carry) | Wave 0 ships scaffolds only — no production auth code touched | Plan 05-03 will wire `Depends(get_current_user_id)` on the 3 new endpoints |
| T-INPUT-VALIDATION (planned) | Scaffolded `test_invalid_country_returns_422` in TestDashboardEndpoints | Plan 05-03 fills the test body |
| T-RATE-LIMIT (carry) | Out-of-scope for Wave 0 (test infrastructure only) | Plan 05-03 will wire `Depends(standard_limit)` |

## Verification Results

**Backend:**
```
$ uv run pytest tests/test_analytics.py tests/test_api.py::TestDashboardEndpoints -v
... 35 skipped, 1 warning in 3.72s

$ uv run pytest tests/test_api.py -v --no-header
... 17 passed, 8 skipped, 1 warning in 9.90s
```
- All 35 new Wave 0 tests SKIPPED (no failures, no errors).
- All 17 existing test_api.py tests still pass.
- `uv run ruff check tests/test_analytics.py tests/conftest.py tests/test_api.py` — clean.

**Frontend:**
```
$ cd frontend && npm test -- --run
... 8 passed, 5 skipped (test files); 17 passed, 27 skipped (tests)

$ cd frontend && npm run typecheck
... (zero errors)

$ cd frontend && npm run lint
... clean
```
- All 27 new Wave 0 stub tests SKIP cleanly.
- All 17 existing frontend tests still pass.
- TypeScript: zero new errors (the string-concat import spec sidesteps tsc resolution as designed).

**Config integrity:**
```
$ cat frontend/components.json | grep -E '"style"|"baseColor"'
  "style": "radix-nova",
    "baseColor": "neutral",
```
- Shadcn preset preserved across the bare add.

**Dependency surface:**
- `recharts` 3.8.0 added (transitively via shadcn chart).
- `radix-ui` umbrella unchanged at ^1.4.3 (provides ToggleGroup primitive).
- No new direct dependencies introduced.

## User Setup Required

None — Wave 0 only adds test infrastructure and UI primitives. No external service configuration, no env vars, no migrations.

## Next Phase Readiness

- **Plan 05-02 (analytics service)** can land `src/job_rag/services/analytics.py` with `top_skills`, `salary_bands`, `cv_match`, `_apply_filters`, `EU_COUNTRY_CODES` — the 5 skip-guards activate without test edits.
- **Plan 05-03 (API routes)** can land `/dashboard/top-skills`, `/dashboard/salary-bands`, `/dashboard/cv-vs-market` — the `TestDashboardEndpoints` route-registration guard activates automatically.
- **Plan 05-04 (hook)** can land `useDashboardFilters` — the hook test stub activates automatically.
- **Plan 05-05 (widgets)** can land `TopSkillsCard`, `SalaryBandsCard`, `CvVsMarketCard`, `DashboardFilters` — the 4 component test stubs activate automatically.
- **Plan 05-06 (route integration)** has no Wave 0 dependency; integrates the widgets into `routes/Dashboard.tsx`.

No blockers. Wave 1 (Plans 05-02 + 05-03) and Wave 2 (Plans 05-04 + 05-05) can execute in parallel after Wave 0 commits land.

## Self-Check

Verifications below confirm claims above are accurate as of completion time.

### File existence
- `tests/test_analytics.py`: FOUND
- `tests/conftest.py`: FOUND (modified with new fixture)
- `tests/test_api.py`: FOUND (modified with TestDashboardEndpoints)
- `frontend/src/components/ui/alert.tsx`: FOUND
- `frontend/src/components/ui/chart.tsx`: FOUND
- `frontend/src/components/ui/toggle-group.tsx`: FOUND
- `frontend/src/components/ui/toggle.tsx`: FOUND
- `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx`: FOUND
- `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx`: FOUND
- `frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx`: FOUND
- `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx`: FOUND
- `frontend/src/components/dashboard/useDashboardFilters.test.ts`: FOUND

### Commits
- `0f78ff2` (Task 1 — backend scaffolds): FOUND
- `62b83b6` (Task 2 — frontend scaffolds): FOUND

## Self-Check: PASSED

---
*Phase: 05-dashboard*
*Completed: 2026-05-22*
