---
phase: 05-dashboard
plan: 04
subsystem: ui
tags: [react, typescript, openapi-typescript, react-router, vitest, testing-library, codegen, tanstack-query]

# Dependency graph
requires:
  - phase: 05-dashboard
    provides: "Plan 05-03 frontend/openapi.snapshot.json with /dashboard/* paths + named schemas (DashboardTopSkillsResponse, DashboardSalaryBandsResponse, DashboardCvMatchResponse, TopSkillItem, MissingSkillItem, CountryFilter, RemoteFilter, Seniority)"
  - phase: 05-dashboard
    provides: "Plan 05-01 skip-on-missing stub useDashboardFilters.test.ts (6 placeholder vitest tests gated on dynamic import of the hook)"
  - phase: 04-frontend-shell-auth
    provides: "Plan 04-02/04-03 authedFetch wrapper attaching MSAL Bearer + propagating AbortSignal; react-router 7.x useSearchParams"
provides:
  - "frontend/src/api/types.ts regenerated via npm run codegen:snapshot — surfaces 7 new named TS interfaces (DashboardTopSkillsResponse, DashboardSalaryBandsResponse, DashboardCvMatchResponse, TopSkillItem, MissingSkillItem, CountryFilter, RemoteFilter) plus Seniority union"
  - "frontend/src/api/jobs.ts: 3 typed analytics fetchers (topSkills, salaryBands, cvVsMarket) wrapping authedFetch + a buildFilterQuery helper applying default elision on the wire-side"
  - "frontend/src/components/dashboard/useDashboardFilters.ts: typed URL-state hook exporting Country / Remote / Seniority / DashboardFilters with isCountry / isRemote / isSeniority defensive type guards, updater-form setParams, replace: false history push"
  - "frontend/src/components/dashboard/useDashboardFilters.test.tsx: 10 active vitest tests (Plan 05-01's 6 stubs filled + 4 additional defensive-coercion tests) — all PASSING with MemoryRouter + renderHook"
affects: [05-05-widgets, 05-06-route-integration]

# Tech tracking
tech-stack:
  added: []  # No new deps — uses existing openapi-typescript / react-router / @testing-library/react
  patterns:
    - "openapi-typescript named-schema codegen: response_model annotations in Plan 05-03 -> $ref schemas -> components['schemas']['XxxResponse'] in types.ts (Plan 05-04 consumes via type aliases)"
    - "Typed-fetcher module shape: 3 async functions (topSkills/salaryBands/cvVsMarket) all (filters: DashboardFilters, signal?: AbortSignal) -> Promise<XxxResponse>; wrap authedFetch + throw on non-2xx; return res.json() as Promise<T> cast"
    - "URL-state hook with type guards: isCountry / isRemote / isSeniority narrow string | null to typed union; invalid strings -> safe defaults (defensive coercion)"
    - "Default-elision pattern (wire + URL parity): jobs.ts buildFilterQuery omits country=WW / seniority=undefined / remote=any from the request URL; useDashboardFilters setFilters omits the same from the history URL. /dashboard (no params) is canonical for all-defaults state"
    - "Vitest test file extension policy: tests using JSX (MemoryRouter wrapper, etc.) MUST be .test.tsx not .test.ts — esbuild does NOT auto-detect JSX in .ts files even with verbatimModuleSyntax"

key-files:
  created:
    - frontend/src/components/dashboard/useDashboardFilters.ts
  modified:
    - frontend/src/api/types.ts
    - frontend/src/api/jobs.ts
    - frontend/src/components/dashboard/useDashboardFilters.test.tsx  (renamed from .test.ts + active assertions)

key-decisions:
  - "Hook shipped in Task 1 commit (feat) rather than as Task 2 GREEN. Cause: Task 1's verify includes npm run typecheck, and jobs.ts imports `type { DashboardFilters }` from the hook module. Without the hook file existing, typecheck fails and Task 1 cannot pass. Applied Rule 3 (auto-fix blocking issue): bundled the hook into Task 1's feat commit so the verify cleanly passes; Task 2 commit becomes the test-only activation. Documented as deviation #1."
  - "Test file extension forced to .test.tsx (renamed from .test.ts). The stub from Plan 05-01 was .test.ts because it didn't use JSX. The active tests use a MemoryRouter wrapper that requires JSX. Esbuild's .ts loader refuses JSX even with verbatimModuleSyntax. Renamed via git mv to preserve history. The plan body anticipated this only implicitly (the example code uses JSX); plan deliverables.frontmatter.files_modified still lists .test.ts — actual artifact is .test.tsx."
  - "Added 4 extra tests beyond the 6 from Plan 05-01's stub: invalid-country / invalid-remote / invalid-seniority coercion + updater-form setParams param preservation. Plan body says 'at least 6 tests pass' (success_criteria #4) and explicitly anticipates additions ('the original 6 from the stub plus 4 additional defensive-coercion tests Plan 05-04 adds for completeness'). 10/10 active tests pass."
  - "isSeniority type guard added (plan's verbatim UI-SPEC snippet did NOT have one — it used `as Seniority` cast instead). Plan body's Task 2 action section DOES include isSeniority + SENIORITIES tuple. The plan body wins over the UI-SPEC excerpt; the type-guard approach is stricter (rejects 'xyz' instead of letting it propagate as a runtime-typed Seniority)."

patterns-established:
  - "Plan-level Task 1 commit can bundle implementation needed for verify to pass even when a downstream Task is marked tdd='true' — Rule 3 deviation. Future executors: if Task N verify depends on a Task N+1 artifact, bundle the dependency forward and document. Don't split tasks across commits in ways that make individual verifies infeasible."
  - "buildFilterQuery() helper in jobs.ts is the canonical wire-side default-elision implementation. Any future analytics endpoint MUST route through it (or share the same WW/undefined/any contract) so the network URL and history URL stay in lockstep."
  - "Hook + tests + fetcher trio for new URL-driven page surfaces: ~100-line hook with type guards + ~90-line vitest covering deep-link / elision / coercion + ~30-line fetcher module is the established shape. Plan 05-06 (chat) MAY adopt the same pattern if the chat surface gets URL-state in v2."

requirements-completed: [DASH-04, DASH-06, SHEL-03]

# Metrics
duration: ~4 min
completed: 2026-05-22
---

# Phase 05 Plan 04: Dashboard Frontend Data Layer Summary

**Typed openapi-typescript codegen + 3 analytics fetchers + URL-state hook with defensive coercion — Plan 05-05 widgets can now wire useQuery against `topSkills(filters, signal)` and read filter state via `useDashboardFilters()` without further integration work.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-22T08:38:39Z
- **Completed:** 2026-05-22T08:42:55Z
- **Tasks:** 2 (Task 1 single feat commit; Task 2 split into rename commit + content commit)
- **Files modified:** 3 source + 1 generated (types.ts) + 1 renamed (.test.ts -> .test.tsx)
- **Commits:** 3 (1 feat + 2 test)

## Accomplishments

- **DASH-04 typed filter shapes shipped:** `Country`, `Remote`, `Seniority`, `DashboardFilters` exports from `useDashboardFilters.ts` give the rest of Phase 5 strict TypeScript safety on every filter-bearing surface. Country / Remote come from hand-typed unions (the UI subset that matches CountryFilter / RemoteFilter codegen unions); Seniority comes from the codegen output directly.
- **DASH-06 URL-state contract live:** `?country=&seniority=&remote=` round-trips through `useSearchParams` with default elision on write and defensive coercion on read. `/dashboard` (no params) is canonical for all-defaults; `/dashboard?country=DE&seniority=senior` deep-links exactly as the UI-SPEC section 10 table specifies.
- **SHEL-03 fetcher trio ready:** `topSkills` / `salaryBands` / `cvVsMarket` all return openapi-typescript-codegened response types — `(filters, signal) => Promise<DashboardTopSkillsResponse>` etc. Plan 05-05 widgets wrap these in `useQuery({ queryFn: ({ signal }) => topSkills(filters, signal) })` with zero hand-typed interfaces.
- **types.ts regenerated:** 7 new named TS interfaces emit cleanly from the Plan 05-03 OpenAPI snapshot. `DashboardTopSkillsResponse`, `DashboardSalaryBandsResponse`, `DashboardCvMatchResponse`, `TopSkillItem`, `MissingSkillItem`, `CountryFilter`, `RemoteFilter` — plus `Seniority` as a string-union enum.
- **10/10 hook tests pass:** `useDashboardFilters.test.tsx` covers deep-link read (2 tests), default elision on write (3 tests), no-params default state (1 test), invalid-value coercion (3 tests), and updater-form param preservation (1 test). All pass with MemoryRouter + renderHook under vitest 3.2.4 / @testing-library/react 16.3.2.
- **Full frontend suite stays green:** 27 active passing (Phase 4 regression + Plan 05-04's new 10) + 21 skipped (Plan 05-05 widget stubs remain skipped as expected). typecheck + lint + build all clean.

## Task Commits

Each task committed atomically:

1. **Task 1: regenerate types.ts + add jobs.ts fetchers + hook (Rule 3 bundling)** — `ddea92b` (feat)
2. **Task 2a: rename .test.ts -> .test.tsx (JSX support)** — `5711086` (test)
3. **Task 2b: fill test bodies with active assertions** — `94d37f7` (test)

_Note: Task 2 split into two commits because the initial Write was inadvertently lost when git mv ran first (git mv preceded the new-content Write in the working tree, then commit captured only the rename with the OLD stub content). Created a new follow-up commit with the actual new test bodies — per execute-plan protocol "Always create NEW commits rather than amending"._

## Files Created/Modified

- `frontend/src/api/types.ts` — regenerated by `npm run codegen:snapshot` against the Plan 05-03 snapshot. +7 new named schemas; existing 8 schemas (Phase 4) preserved.
- `frontend/src/api/jobs.ts` — replaced the 3-line Phase 4 stub with 67-line typed fetcher module. 3 async functions (topSkills/salaryBands/cvVsMarket) + 1 buildFilterQuery helper + 5 type re-exports from codegen.
- `frontend/src/components/dashboard/useDashboardFilters.ts` — NEW. 100-line hook implementing UI-SPEC section 10 verbatim: typed Country / Remote / Seniority + DashboardFilters; isCountry / isRemote / isSeniority type guards; setFilters with 'key' in patch default-elision branches; replace: false history-push.
- `frontend/src/components/dashboard/useDashboardFilters.test.tsx` — renamed from .test.ts + filled with 10 active assertions. Uses MemoryRouter + renderHook from @testing-library/react.

## Named Schemas Now In types.ts (Plan 05-05 / 05-06 ready)

Verified via grep against `frontend/src/api/types.ts` post-codegen:

| Schema | Count of occurrences | Source |
|--------|---------------------|--------|
| `DashboardTopSkillsResponse` | 4 | api/dashboard.py BaseModel (GET /dashboard/top-skills 200 response) |
| `DashboardSalaryBandsResponse` | 4 | api/dashboard.py BaseModel (GET /dashboard/salary-bands 200 response) |
| `DashboardCvMatchResponse` | 3 | api/dashboard.py BaseModel (GET /dashboard/cv-vs-market 200 response) |
| `TopSkillItem` | 3 | api/dashboard.py BaseModel (one row of top-skills aggregate) |
| `MissingSkillItem` | 3 | api/dashboard.py BaseModel (one row of cv-vs-market top-3 missing must-haves) |
| `CountryFilter` | 5 | api/dashboard.py StrEnum (PL / DE / EU / WW) |
| `RemoteFilter` | 5 | api/dashboard.py StrEnum (any / remote / non_remote) |
| `Seniority` | 5 | models.py StrEnum (junior / mid / senior / staff / lead / unknown) |

## Decisions Made

**Hook bundled into Task 1 commit (Rule 3 deviation).** Plan splits the work into Task 1 (codegen + fetchers) and Task 2 (hook + tests, marked `tdd="true"`). Task 1's verify includes `npm run typecheck`. But `jobs.ts` imports `type { DashboardFilters } from '@/components/dashboard/useDashboardFilters'` — that path doesn't resolve without the hook file. Without the hook, Task 1's verify cannot pass cleanly. Resolved by bundling the hook into Task 1's commit; Task 2 reduces to test-file activation only. The TDD framing in Task 2 was already loose (the test stubs use `describe.skipIf(!useDashboardFilters)` which would simply skip — not fail — if the hook were missing), so this rearrangement doesn't drop test coverage. The plan-level success criteria 1-6 still all hold.

**Test file extension changed: .test.ts -> .test.tsx.** Plan 05-01's stub was `.test.ts` (no JSX). Plan 05-04's active tests use a `MemoryRouter` wrapper component which requires JSX. Esbuild's `.ts` loader does NOT parse JSX (even with `verbatimModuleSyntax: true`). Renamed via `git mv` to preserve git history; the plan body's example code snippets explicitly use JSX syntax so this is expected, but the plan frontmatter still lists `files_modified: useDashboardFilters.test.ts`. The actual artifact is `.tsx`.

**Type-guard approach for Seniority chosen over the UI-SPEC excerpt's cast.** UI-SPEC section 10's snippet had `seniority: (seniorityRaw as Seniority | null) ?? undefined` — a naive cast that accepts any string. The plan body's Task 2 action section provides `isSeniority` + `SENIORITIES` tuple and uses `isSeniority(seniorityRaw) ? seniorityRaw : undefined`. Followed the plan body (stricter; T-INPUT-VALIDATION calls for defensive coercion, and an unguarded cast would let `?seniority=xyz` propagate as a runtime-typed Seniority into the network request).

**Added 4 extra tests beyond Plan 05-01's 6.** Plan body explicitly anticipates this: "the original 6 from the stub plus 4 additional defensive-coercion tests Plan 05-04 adds for completeness." Final count: 10 tests, all passing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Hook bundled into Task 1 commit (typecheck dependency)**
- **Found during:** Task 1 verify (`npm run typecheck` after writing jobs.ts)
- **Issue:** Plan splits Task 1 (jobs.ts fetchers) and Task 2 (hook implementation) into separate tasks, but Task 1's verify includes typecheck, and `jobs.ts` imports `type { DashboardFilters }` from the hook module. With the hook missing, `tsc -b --noEmit` fails: `Cannot find module '@/components/dashboard/useDashboardFilters'`.
- **Fix:** Wrote the full hook (per UI-SPEC section 10) and bundled it into Task 1's `feat` commit. Task 2 reduces to test-file activation only.
- **Files affected:** `frontend/src/components/dashboard/useDashboardFilters.ts` (created in Task 1 commit rather than Task 2 GREEN commit)
- **Verification:** Task 1 typecheck now passes; Task 2 tests pass against the hook from Task 1.
- **Committed in:** `ddea92b` (Task 1 commit bundles the hook)

**2. [Rule 3 - Blocking] Test file extension renamed .test.ts -> .test.tsx (JSX requirement)**
- **Found during:** Task 2 verify (`npm test -- --run useDashboardFilters`)
- **Issue:** Esbuild's `.ts` loader rejects JSX with `Expected ">" but found "initialEntries"`. The Plan 05-01 stub was `.test.ts` because it had no JSX. The active tests need a `<MemoryRouter>` wrapper.
- **Fix:** `git mv` rename to preserve history.
- **Files affected:** `frontend/src/components/dashboard/useDashboardFilters.test.ts` -> `useDashboardFilters.test.tsx`
- **Verification:** vitest now picks the file up via the `.tsx` loader and all 10 tests pass.
- **Committed in:** `5711086` (Task 2a rename) + `94d37f7` (Task 2b content)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - Blocking)
**Impact on plan:** Both fixes were forced by the plan's own constraints (Task 1 typecheck + Plan 05-01 stub extension). No scope creep; the resulting artifacts match the plan's `files_modified` list with the single extension delta (.test.ts -> .test.tsx) documented in Decisions Made.

## Issues Encountered

**Test commit 5711086 captured the rename without the new content.** Order of operations was: (1) `Write` to the working tree with new test body, (2) `git mv` to rename, (3) `git commit`. Git's rename detection treated the file as 100% similar because `git mv` itself does NOT capture the working-tree changes — the renamed file in the index was the OLD stub content; the working tree had the NEW content but it wasn't staged. The commit looked successful but contained no diff. Resolved by a follow-up `git add` + new commit (`94d37f7`). The correct ordering would have been `git mv` then `Write` then `git add` — or just `Write` to the new path then `git rm` the old path. Documented as a process-side learning.

## Threat Model Coverage

| Threat ID | Mitigation Applied | Verification |
|-----------|--------------------|--------------|
| T-INPUT-VALIDATION | `isCountry` / `isRemote` / `isSeniority` type guards in `useDashboardFilters.ts` reject invalid URL values (`?country=ZZ` -> WW; `?remote=foo` -> any; `?seniority=xyz` -> undefined). 3 dedicated tests in `useDashboardFilters.test.tsx` exercise the defensive coercion. Backend Plan 05-03 provides defense-in-depth (Pydantic 422 if invalid value somehow bypasses the hook). | `cd frontend && npx vitest run useDashboardFilters` → 10/10 PASSED |
| T-5-04-01 (Tampering, jobs.ts query string) | `URLSearchParams.set` in `buildFilterQuery` escapes values; no raw string concatenation. The 3 fetchers route through `authedFetch` (Phase 4 D-11/D-13), so Bearer + 401-retry-after-refresh machinery is uniform. | `grep "URLSearchParams" frontend/src/api/jobs.ts` returns 1 ✓ |
| T-5-04-02 (Info Disclosure, URL surface) | **Accepted.** The URL exposes filter selection (e.g. `/dashboard?country=DE`), but it's intentional per DASH-06 deep-linking. No PII / IDs / secrets — only enum filter values. | n/a (accept disposition) |
| T-AUTH-06 (carry from Phase 4) | All 3 fetchers (`topSkills` / `salaryBands` / `cvVsMarket`) call `authedFetch`; no bare `fetch` paths bypass the Bearer. | `grep -c "authedFetch" frontend/src/api/jobs.ts` returns 4 (1 import + 3 calls) ✓ |

## Verification Results

**Hook tests (Plan 05-04 deliverable):**
```
$ cd frontend && npx vitest run useDashboardFilters
 ✓ src/components/dashboard/useDashboardFilters.test.tsx (10 tests) 13ms

 Test Files  1 passed (1)
      Tests  10 passed (10)
```

**Full frontend test suite (regression sweep):**
```
$ cd frontend && npm test -- --run
 Test Files  9 passed | 4 skipped (13)
      Tests  27 passed | 21 skipped (48)
```
- The 21 skipped tests are the 4 Plan 05-05 widget stub files (TopSkillsCard / SalaryBandsCard / CvVsMarketCard / DashboardFilters) which Plan 05-05 will activate. All Phase 4 / Plan 05-01 active tests still pass.

**Typecheck:**
```
$ cd frontend && npm run typecheck
> tsc -b --noEmit
(exits 0, no output)
```

**Lint:**
```
$ cd frontend && npm run lint
> eslint .
(exits 0, no output)
```

**Build:**
```
$ cd frontend && npm run build
✓ built in 192ms
(chunk-size warning for the existing main bundle — pre-existing, not Plan 05-04 regression)
```

**Codegen integrity:**
```
$ cd frontend && grep -c "DashboardTopSkillsResponse" src/api/types.ts
4
$ grep -c "MissingSkillItem" src/api/types.ts
3
$ grep -c "CountryFilter" src/api/types.ts
5
```

**jobs.ts surface:**
```
$ grep -E "export async function (topSkills|salaryBands|cvVsMarket)" frontend/src/api/jobs.ts
export async function topSkills(
export async function salaryBands(
export async function cvVsMarket(
```
3 lines — exactly the 3 expected fetchers.

## User Setup Required

None — pure frontend codegen + module addition. No new env vars, no migrations, no MSAL config changes.

## Next Phase Readiness

Plan 05-05 (Wave 2b widgets) can immediately:
- `import { topSkills, salaryBands, cvVsMarket } from '@/api/jobs'` and wrap each in `useQuery({ queryKey: ['dashboard', '<feature>', filters], queryFn: ({ signal }) => topSkills(filters, signal), staleTime: 5 * 60_000 })`
- `import { useDashboardFilters } from '@/components/dashboard/useDashboardFilters'` in both the filter-bar component (`DashboardFilters.tsx`) and in each widget for its `useQuery` key + fetcher arg
- `import type { DashboardFilters, Country, Remote, Seniority } from '@/components/dashboard/useDashboardFilters'` and `import type { TopSkillsResponse, TopSkillItem, ... } from '@/api/jobs'` for type-safe widget props
- Activate the 4 currently-skipped widget test stubs (TopSkillsCard / SalaryBandsCard / CvVsMarketCard / DashboardFilters) — the import paths they probe are now all live

No blockers.

## TDD Gate Compliance

Plan 05-04 has Task 2 marked `tdd="true"`. The plan-level RED/GREEN sequence was modified due to the Rule 3 typecheck-dependency deviation:

- **Original spec:** Task 2 RED activates tests (still skip via dynamic-import gate when hook absent) → Task 2 GREEN ships hook → tests transition skip → pass.
- **As executed:** Task 1 ships the hook (Rule 3 bundling so Task 1 typecheck passes) → Task 2 commits activate the tests against the existing hook → 10/10 pass.

Git log gate sequence:
1. `ddea92b` `feat(05-04): regenerate types.ts ... + useDashboardFilters hook` — implementation (would normally be GREEN; bundled with Task 1 here)
2. `5711086` `test(05-04): activate useDashboardFilters tests with MemoryRouter + renderHook` — rename commit (no content change)
3. `94d37f7` `test(05-04): fill useDashboardFilters test bodies with active assertions` — test bodies activated, all pass

The `test(...)` commits land AFTER the `feat(...)` commit. This inverts the strict RED-then-GREEN order. Mitigation: the test commits and feat commits are independent — both individually verifiable — and the test commit `94d37f7` was tested locally against the existing hook before commit. The tests would have FAILED if the hook were missing (10 failures, not 10 skips, because the dynamic-import skipIf guard was removed per plan body instruction). So the test commit DOES exercise real assertions; the strict RED phase is just absent because no broken state was ever committed.

## Self-Check

Verifications below confirm claims above are accurate as of completion time.

### File existence
- `frontend/src/api/types.ts`: FOUND (regenerated)
- `frontend/src/api/jobs.ts`: FOUND (modified, +66 lines)
- `frontend/src/components/dashboard/useDashboardFilters.ts`: FOUND (created, 100 lines)
- `frontend/src/components/dashboard/useDashboardFilters.test.tsx`: FOUND (renamed + content replaced, 94 lines)
- `.planning/phases/05-dashboard/05-04-SUMMARY.md`: FOUND (this file)

### Commits
- `ddea92b` (Task 1 — types.ts + jobs.ts + hook): FOUND
- `5711086` (Task 2a — rename .test.ts -> .test.tsx): FOUND
- `94d37f7` (Task 2b — fill test bodies): FOUND

### Acceptance criteria spot-checks
- `grep -c DashboardTopSkillsResponse frontend/src/api/types.ts` returns 4 ✓
- `grep -c MissingSkillItem frontend/src/api/types.ts` returns 3 ✓
- `grep -c CountryFilter frontend/src/api/types.ts` returns 5 ✓
- `grep -c RemoteFilter frontend/src/api/types.ts` returns 5 ✓
- `grep -q "export async function topSkills" frontend/src/api/jobs.ts` ✓
- `grep -q "export async function salaryBands" frontend/src/api/jobs.ts` ✓
- `grep -q "export async function cvVsMarket" frontend/src/api/jobs.ts` ✓
- `grep -q "filters.country !== 'WW'" frontend/src/api/jobs.ts` ✓
- `grep -q "filters.remote !== 'any'" frontend/src/api/jobs.ts` ✓
- `grep -q "export function useDashboardFilters" frontend/src/components/dashboard/useDashboardFilters.ts` ✓
- `grep -q "isCountry" frontend/src/components/dashboard/useDashboardFilters.ts` ✓
- `grep -q "isSeniority" frontend/src/components/dashboard/useDashboardFilters.ts` ✓
- `grep -q "replace: false" frontend/src/components/dashboard/useDashboardFilters.ts` ✓
- `grep -q "MemoryRouter" frontend/src/components/dashboard/useDashboardFilters.test.tsx` ✓
- `grep -q "renderHook" frontend/src/components/dashboard/useDashboardFilters.test.tsx` ✓
- `grep -c "it(" frontend/src/components/dashboard/useDashboardFilters.test.tsx` returns 10 (≥ 6 required) ✓
- `cd frontend && npm run typecheck` exits 0 ✓
- `cd frontend && npm run lint` exits 0 ✓
- `cd frontend && npm run build` exits 0 ✓
- 10/10 hook tests pass; 27/27 active frontend tests pass; 21 widget stubs SKIP as expected ✓

## Self-Check: PASSED

---
*Phase: 05-dashboard*
*Completed: 2026-05-22*
