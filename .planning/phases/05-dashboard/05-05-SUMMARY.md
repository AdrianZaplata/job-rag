---
phase: 05-dashboard
plan: 05
subsystem: ui
tags: [react, typescript, tanstack-query, recharts, shadcn, vitest, testing-library, msw-not-used, dashboard-widgets]

# Dependency graph
requires:
  - phase: 05-dashboard
    provides: "Plan 05-04 typed fetchers (topSkills/salaryBands/cvVsMarket) + useDashboardFilters URL-state hook + 7 codegen response types"
  - phase: 05-dashboard
    provides: "Plan 05-01 shadcn primitives (Alert, ChartContainer, ToggleGroup) + 4 widget test stubs using string-concat dynamic-import skip-on-missing pattern"
  - phase: 04-frontend-shell-auth
    provides: "Plan 04-XX EmptyState primitive + QueryClient + AppShell lazy-import contract"
provides:
  - "frontend/src/components/dashboard/DashboardFilters.tsx: filter bar (country DropdownMenuRadioGroup 4 items + seniority DropdownMenuRadioGroup 6 items + remote ToggleGroup 3 items) reading/writing via useDashboardFilters"
  - "frontend/src/components/dashboard/TopSkillsCard.tsx: 4-state widget (Skeleton/Alert/EmptyState/SkillsBarList) with double-stacked Tailwind bars + Show more button when skills.length > 10"
  - "frontend/src/components/dashboard/TopSkillsDialog.tsx: modal with 50-row scrollable table (sticky header, role=region aria-label='Skill list')"
  - "frontend/src/components/dashboard/SalaryBandsCard.tsx: 4-state widget with Recharts BarChart (p25/p50/p75) inside ChartContainer with accessibilityLayer + LabelList '€{value}/yr' + DASH-02 sample-size footer"
  - "frontend/src/components/dashboard/CvVsMarketCard.tsx: 4-state widget with text-5xl .toFixed(2) hero number + Badge variant=secondary chips for top-3 missing must-haves + footer 'Score across N postings'"
  - "frontend/src/components/dashboard/errors.ts: describeError(err) shared helper returning err.message or fallback 'Unexpected error. Reload the page or try again later.'"
  - "frontend/src/routes/Dashboard.tsx: composition replacing the Phase 4 placeholder with the full 3-up grid (mx-auto max-w-6xl p-6 space-y-6 outer / grid grid-cols-1 md:grid-cols-3 gap-4 inner)"
  - "4 active widget test files: 5 + 7 + 6 + 6 = 24 passing tests across DashboardFilters / TopSkillsCard / SalaryBandsCard / CvVsMarketCard"
affects: [05-06-route-integration, future-chat-surface, future-analytics-widgets]

# Tech tracking
tech-stack:
  added: []  # No new deps — uses Plan 05-01's recharts + shadcn primitives + Plan 05-04's openapi types
  patterns:
    - "Per-widget useQuery: queryKey: ['dashboard', NAME, filters] + queryFn: ({signal}) => fetcher(filters, signal) + staleTime: 5 * 60_000 (D-22 override of Phase 4's 30s default). Filters object is structurally-shared so adjacent identical objects produce no refetch."
    - "Hermetic widget tests: vi.mock('@/api/jobs') with all 3 fetchers mocked + QueryClientProvider with retry:false + MemoryRouter wrapper. Mock implementation per test (mockResolvedValue / mockRejectedValue / never-resolving promise for isPending)."
    - "4-state widget render contract: isPending → Skeleton (role=status aria-label=Loading X); isError → Alert variant=destructive + describeError(error); data && empty → EmptyState; data && non-empty → main view. Footer rendered iff data && !isError (renders during loading transition out)."
    - "Recharts wiring: BarChart with accessibilityLayer, var(--chart-1) fill via ChartContainer config theme-aware variable, LabelList position='top' with custom formatter. ChartContainer aria-label provides a screen-reader summary of all 3 percentile values."
    - "Verbatim UI-SPEC §16 copy strings: each widget hardcodes the exact title/empty-state/error/footer text from the spec. grep-asserted in acceptance criteria so test refactors can't silently drift the wording."

key-files:
  created:
    - frontend/src/components/dashboard/DashboardFilters.tsx
    - frontend/src/components/dashboard/TopSkillsCard.tsx
    - frontend/src/components/dashboard/TopSkillsDialog.tsx
    - frontend/src/components/dashboard/SalaryBandsCard.tsx
    - frontend/src/components/dashboard/CvVsMarketCard.tsx
    - frontend/src/components/dashboard/errors.ts
  modified:
    - frontend/src/routes/Dashboard.tsx  # PhasePlaceholder → composition of 4 widgets
    - frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx  # stubs → 5 active tests
    - frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx  # stubs → 7 active tests
    - frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx  # stubs → 6 active tests
    - frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx  # stubs → 6 active tests

key-decisions:
  - "Rule 3 (Blocking) — ship placeholder widget exports in Task 1 commit. routes/Dashboard.tsx imports TopSkillsCard/SalaryBandsCard/CvVsMarketCard, and Task 1's acceptance criterion includes `cd frontend && npm run typecheck` exits 0. Without placeholders, typecheck fails on Cannot find module errors for the 2 widgets Task 1 doesn't ship. Bundled minimal `export function X() { return null }` stubs into Task 1 so typecheck passes; Tasks 2 + 3 replace them with full implementations. Same pattern Plan 05-04 used (Rule 3 hook bundling)."
  - "TopSkillsCard test count: 7 (plan said 'at least 6'). The plan's example test block has 7 explicit `it()` blocks (title, skeleton, error, empty, show-more, plural-footer, singular-plural-edge-case). All 7 ship as-is. Plan acceptance criterion says 'at least 5 PASSED tests each' — we comfortably exceed."
  - "Plan acceptance criterion `grep -q PhasePlaceholder ... | wc -l is 0` was originally satisfied by removing the import, but the verbatim UI-SPEC plan code retained `Phase 4 PhasePlaceholder stub` in a comment. Edited the comment to drop the literal word so the grep returns exactly 0 (no stale references in any form)."

patterns-established:
  - "Placeholder-forward-then-replace task ordering: when later tasks introduce dependencies for earlier tasks' verify steps, ship minimal `return null` placeholders so the gate passes. The replace-in-place Write in the later task commit captures the full implementation cleanly. Same pattern Plan 05-04 used for the hook + jobs.ts typecheck dependency."
  - "Mock-all-three-jobs-functions hermetic test pattern: even when a single widget only calls one fetcher, vi.mock('@/api/jobs') must return all 3 (topSkills/salaryBands/cvVsMarket) because the module exports them all. The unused mocks are vi.fn() no-ops that satisfy the import surface but never get invoked."
  - "ChartContainer aria-label as scaffold for chart accessibility: instead of relying on Recharts' internal accessibilityLayer alone (which announces individual bar values on focus), the wrapper provides a single-line summary `Salary band chart: p25 €X/yr, p50 €Y/yr, p75 €Z/yr`. Screen readers announce this BEFORE the chart interactive surface. Useful for plan 05-06 + any future chart widgets."

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, SHEL-03, SHEL-06]

# Metrics
duration: ~6 min
completed: 2026-05-22
---

# Phase 05 Plan 05: Dashboard Widget Composition Summary

**Wave 2b shipped: 4 widget components + Show More dialog + describeError helper + Dashboard route composition. Visiting `/dashboard` now renders the full Phase 5 surface (filter bar + 3-up grid) against Plan 05-03's live backend endpoints. All 4 Plan 05-01 widget test stubs graduate from skipped to passing — 24 new active tests across the 4 widget files, full frontend suite at 51/51 passing.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-22T08:49:22Z
- **Completed:** 2026-05-22T08:55:16Z
- **Tasks:** 3 (all atomic, one commit per task)
- **Files created:** 6 (DashboardFilters / TopSkillsCard / TopSkillsDialog / SalaryBandsCard / CvVsMarketCard / errors.ts)
- **Files modified:** 5 (routes/Dashboard.tsx + 4 widget test files)
- **Commits:** 3 (3 feat)

## Accomplishments

- **DASH-01 (TopSkillsCard) shipped**: Tailwind double-stacked bars (must vs nice), widthPct/mustPct math, top-10 visible in card with Show More opening DASH-05 dialog with 50-row scrollable table. Pluralized footer "{n} posting|postings · {m} unique hard skill|unique hard skills".
- **DASH-02 (SalaryBandsCard) shipped**: Recharts BarChart with 3 bars (p25/p50/p75) inside ChartContainer, accessibilityLayer for keyboard nav, LabelList top position formatted as `€{value}/yr` via toLocaleString. DASH-02 sample-size footer `{postings_with_salary} of {total_postings} posting|postings had salary data`.
- **DASH-03 (CvVsMarketCard) shipped**: text-5xl hero number with `.toFixed(2)` and aria-label `Match score X.YZ`, Badge variant=secondary chips for top-3 missing must-haves with `Math.round(percentage) + '%'`, footer "Score across N posting|postings". Empty state when `mean_score === null` per D-12.
- **DASH-04 (DashboardFilters) shipped**: country DropdownMenuRadioGroup (Worldwide / EU / Germany / Poland), seniority DropdownMenuRadioGroup (Any seniority + Junior / Mid / Senior / Staff / Lead), remote ToggleGroup (Any / Remote / On-site) all wired to useDashboardFilters round-trip.
- **DASH-05 (Show More dialog) shipped**: TopSkillsDialog renders full ranked table inside `max-h-[70vh] overflow-y-auto` region with `role=region aria-label="Skill list"`, sticky-top thead, 5-column layout (#, Skill, Must, Nice, Total).
- **DASH-06 (URL state)**: filter bar reads/writes via Plan 05-04's hook; deep-linking + default elision + defensive coercion all inherited.
- **SHEL-03 (TanStack Query D-22 override)**: each widget passes `staleTime: 5 * 60_000` directly in useQuery options, overriding Phase 4's 30s default per the dashboard freshness contract. Query keys uniform: `['dashboard', NAME, filters]`.
- **SHEL-06 (per-widget loading/empty/error layers)**: all 3 widgets implement the 4-state branch contract uniformly (Skeleton → Alert → EmptyState → data view). Pattern is identical across widgets, making future widgets in Plan 05-06+ trivial to scaffold.
- **routes/Dashboard.tsx replaced**: PhasePlaceholder stub gone; outer container uses literal `mx-auto max-w-6xl p-6 space-y-6` per UI-SPEC §3; grid uses literal `grid grid-cols-1 md:grid-cols-3 gap-4`; named export `DashboardPage` preserved so App.tsx's `lazy(() => import('@/routes/Dashboard').then((m) => ({ default: m.DashboardPage })))` continues to resolve.
- **24 active widget tests pass** across 4 files (5 DashboardFilters + 7 TopSkillsCard + 6 SalaryBandsCard + 6 CvVsMarketCard). Combined with Plan 05-04's 10 hook tests + Phase 4's 17 baseline tests = **51 passing, 0 skipped** across 13 test files.
- **errors.ts shared**: `describeError(err)` lives in one module, imported by all 3 widget Alert branches. Returns `err.message` (already-sanitized by Plan 01-06 backend `_sanitize` + 200-char bound) or the UI-SPEC §9 verbatim fallback.

## Task Commits

Each task committed atomically:

1. **Task 1: DashboardFilters + errors.ts + Dashboard route composition** — `805f449` (feat)
2. **Task 2: TopSkillsCard + TopSkillsDialog + activated TopSkillsCard tests** — `c41bace` (feat)
3. **Task 3: SalaryBandsCard + CvVsMarketCard + activated their tests** — `6efd39a` (feat)

## Files Created/Modified

**Created:**

- `frontend/src/components/dashboard/errors.ts` — 8-line shared helper module exporting `describeError(err: unknown): string`.
- `frontend/src/components/dashboard/DashboardFilters.tsx` — 105-line filter bar; 3 controls; all labels verbatim from UI-SPEC §16.
- `frontend/src/components/dashboard/TopSkillsCard.tsx` — 140-line widget; 4 render branches; double-stacked Tailwind bar formula `(skill.total / leader.total) * 100` width with nested `(must / total) * 100` must-portion.
- `frontend/src/components/dashboard/TopSkillsDialog.tsx` — 65-line dialog; sticky thead, 5-column scrollable table, Close button.
- `frontend/src/components/dashboard/SalaryBandsCard.tsx` — 112-line widget; Recharts BarChart with `accessibilityLayer`, `var(--chart-1)` fill, LabelList `€{value}/yr` formatter via `Intl.NumberFormat`-equivalent `toLocaleString('en-US')`.
- `frontend/src/components/dashboard/CvVsMarketCard.tsx` — 108-line widget; hero number with explicit `data.mean_score !== null && data.mean_score !== undefined` narrowing for TS so `.toFixed(2)` typechecks without `!`.

**Modified:**

- `frontend/src/routes/Dashboard.tsx` — replaced PhasePlaceholder stub with 22-line composition (filter bar + 3-up grid + 3 widgets). Named export `DashboardPage` preserved.
- `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx` — stubs replaced with 5 active vitest tests using MemoryRouter wrapper.
- `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx` — stubs replaced with 7 active tests using QueryClientProvider + MemoryRouter + `vi.mock('@/api/jobs')`.
- `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx` — stubs replaced with 6 active tests.
- `frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx` — stubs replaced with 6 active tests.

## UI-SPEC §16 Verbatim Copy Compliance

First copy-line from each widget (greppable, exact-match):

| File | First copy-line |
|------|------------------|
| `DashboardFilters.tsx` | `aria-label="Dashboard filters"` |
| `TopSkillsCard.tsx` | `<CardTitle className="text-sm font-medium">Top skills</CardTitle>` |
| `TopSkillsDialog.tsx` | `<DialogTitle>All top skills</DialogTitle>` |
| `SalaryBandsCard.tsx` | `<CardTitle className="text-sm font-medium">Salary bands</CardTitle>` |
| `CvVsMarketCard.tsx` | `<CardTitle className="text-sm font-medium">CV vs market</CardTitle>` |

All 5 strings match UI-SPEC §16 verbatim — no paraphrasing.

## Decisions Made

**Placeholder-forward bundling in Task 1 (Rule 3 — Blocking).** Plan splits the work into 3 tasks: Task 1 ships DashboardFilters + errors.ts + routes/Dashboard.tsx; Task 2 ships TopSkillsCard + Dialog; Task 3 ships SalaryBandsCard + CvVsMarketCard. But Task 1's acceptance criterion includes `cd frontend && npm run typecheck` exits 0, and routes/Dashboard.tsx imports all 3 widgets. With Tasks 2 and 3 deferred, typecheck would fail with TS2307 (Cannot find module). Resolved by shipping `export function X() { return null }` placeholder stubs for TopSkillsCard / SalaryBandsCard / CvVsMarketCard in Task 1's commit. Each later task replaces its placeholder with the full implementation. Same Rule 3 pattern Plan 05-04 used for the hook + jobs.ts typecheck dependency.

**TopSkillsCard test count: 7 (plan body example had 7; plan acceptance criterion said 'at least 5').** Plan acceptance criterion #3 says "All 4 widget test files have at least 5 PASSED tests each". The plan body's example test block for TopSkillsCard has 7 explicit `it()` blocks (title, skeleton, error, empty, show-more, plural footer, singular-plural edge case). Shipped all 7 as written. Final: 5 (DashboardFilters) + 7 (TopSkillsCard) + 6 (SalaryBandsCard) + 6 (CvVsMarketCard) = 24 active tests across the 4 widget files. Each comfortably exceeds the floor of 5.

**Dropped `PhasePlaceholder` string from routes/Dashboard.tsx comment.** Plan acceptance criterion stated `grep -q "PhasePlaceholder" frontend/src/routes/Dashboard.tsx | wc -l` is 0 (stub removed). The plan body's example comment text included `// Replaces the Phase 4 PhasePlaceholder stub.` which would leave the literal word in the file. Changed to `// Replaces the Phase 4 placeholder stub.` so `grep -c "PhasePlaceholder" routes/Dashboard.tsx` returns exactly 0 — no stale references in any form, including comments. Pure cosmetic adjustment, no functional impact.

**CvVsMarket TS narrowing.** Plan body's example code has `hasData && (<>{data.mean_score.toFixed(2)}</>)` where `hasData = data != null && data.mean_score != null`. TypeScript's narrowing of `data` from the hasData check doesn't propagate to `data.mean_score` access inside the JSX subtree because hasData is a derived const that TypeScript narrows only to `data != null` — not `data.mean_score != null` (which is what we need for `.toFixed`). Added explicit `data.mean_score !== null && data.mean_score !== undefined` re-check inside the JSX gate so `.toFixed(2)` typechecks cleanly without a non-null assertion. Runtime behavior identical to the plan's spec; just a TS strictness adjustment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 1 placeholder bundling for Tasks 2 + 3 widgets**

- **Found during:** Task 1 verify (`npm run typecheck` after writing routes/Dashboard.tsx)
- **Issue:** `routes/Dashboard.tsx` imports TopSkillsCard, SalaryBandsCard, CvVsMarketCard from `@/components/dashboard/{X}.tsx`. None of these files exist after Task 1's writes. `tsc -b --noEmit` fails with TS2307 (Cannot find module) on all 3 imports.
- **Fix:** Shipped minimal placeholder exports `export function X() { return null }` for each of the 3 widgets in Task 1's commit. Each is a 5-line file with a comment noting that Task 2/3 replaces it.
- **Files affected:** `TopSkillsCard.tsx`, `SalaryBandsCard.tsx`, `CvVsMarketCard.tsx` (placeholders in Task 1; full implementations in Task 2/3)
- **Verification:** Task 1 typecheck passes (`npm run typecheck` exits 0). Task 2 / Task 3 Writes replace the placeholder content cleanly.
- **Committed in:** `805f449` (Task 1; placeholder content), `c41bace` (Task 2 replaces TopSkillsCard placeholder), `6efd39a` (Task 3 replaces SalaryBandsCard + CvVsMarketCard placeholders)

**2. [Rule 1 - Bug] Comment text in routes/Dashboard.tsx contained `PhasePlaceholder`, breaking grep acceptance criterion**

- **Found during:** Task 1 acceptance criteria check (`grep -c "PhasePlaceholder" frontend/src/routes/Dashboard.tsx` returned 1, expected 0)
- **Issue:** Plan body's verbatim example block had `// Replaces the Phase 4 PhasePlaceholder stub.` as a comment line. Plan acceptance criterion `grep -q "PhasePlaceholder" frontend/src/routes/Dashboard.tsx | wc -l is 0 (stub removed)` was interpreted as zero occurrences anywhere in the file, including comments.
- **Fix:** Edited comment to `// Replaces the Phase 4 placeholder stub.` (dropped the literal word).
- **Files affected:** `frontend/src/routes/Dashboard.tsx`
- **Verification:** `grep -c "PhasePlaceholder" frontend/src/routes/Dashboard.tsx` returns 0.
- **Committed in:** `805f449` (Task 1 commit; the edit was applied before commit)

**3. [Rule 1 - Bug] CvVsMarketCard TS narrowing for `.toFixed(2)`**

- **Found during:** Task 3 verify (`npm run typecheck` against the plan body's example code)
- **Issue:** Plan body's example had `hasData && (<>{data.mean_score.toFixed(2)}</>)` where `hasData = data != null && data.mean_score != null`. TypeScript flow analysis doesn't narrow `data.mean_score` from null to number through the derived-const `hasData` check; `.toFixed(2)` errors with "Object is possibly null".
- **Fix:** Added explicit re-check `data.mean_score !== null && data.mean_score !== undefined` directly in the JSX gate. Same runtime semantics; TypeScript narrows correctly inside the gated subtree.
- **Files affected:** `frontend/src/components/dashboard/CvVsMarketCard.tsx`
- **Verification:** `npm run typecheck` exits 0.
- **Committed in:** `6efd39a` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (1 Rule 3 - Blocking, 2 Rule 1 - Bug)
**Impact on plan:** No scope change. All 8 success criteria still met. Each deviation was a TS strictness or grep-literalness adjustment forced by the plan's own acceptance criteria.

## Issues Encountered

None. Tests were predictable, the Recharts wiring worked first-try because Plan 05-01 had already validated the ChartContainer + recharts ^3.8.0 integration, and the openapi-typescript codegen types from Plan 05-04 provided complete type-safety throughout.

## Threat Model Coverage

| Threat ID | Mitigation Applied | Verification |
|-----------|--------------------|--------------|
| T-5-05-01 (Information Disclosure, widget error messages) | `describeError(err)` in `errors.ts` returns either `err.message` (already-sanitized backend error from Plan 01-06 with 200-char + no-newline bound) or the safe fallback "Unexpected error. Reload the page or try again later." No stack traces, no class names, no internal paths. | `grep -q "Unexpected error. Reload the page or try again later." frontend/src/components/dashboard/errors.ts` returns 0 ✓; describeError is the only error rendering path in all 3 widgets (`grep -c "describeError" frontend/src/components/dashboard/*.tsx` returns 3) |
| T-5-05-02 (Tampering, Recharts SVG injection) | **Accepted.** Recharts ^3 renders bar values from JSON-parsed numbers via React props; no `eval`, no `innerHTML`. The aria-label string is constructed from typed `data.p25/p50/p75` (number \| null); React's text-node default escapes the string. | `grep -q "dangerouslySetInnerHTML" frontend/src/components/dashboard/SalaryBandsCard.tsx` returns nothing ✓ |
| T-5-05-03 (Spoofing, theme toggle integrity) | **Accepted.** Phase 4's ThemeToggle (in AppShell) drives the theme via CSS class on documentElement. Recharts `var(--chart-1)` resolves via CSS-var lookup; theme switch is purely visual. No security impact. | n/a (accept disposition) |
| T-AUTH-06 (carry) | All 3 widget fetches route through Plan 05-04's authedFetch wrapper. Bearer attached on every analytics request; backend (Plan 05-03) validates against the seeded oid allowlist. | `grep -c "authedFetch" frontend/src/api/jobs.ts` returns 4 (1 import + 3 calls) — preserved from Plan 05-04 ✓ |
| T-INPUT-VALIDATION (carry) | useDashboardFilters (Plan 05-04) defensively coerces invalid country/seniority/remote BEFORE the widget queryFn runs; Plan 05-03 Pydantic enum types provide defense-in-depth with HTTP 422. | 10/10 hook tests still pass (`npm test -- --run useDashboardFilters`) ✓ |

## Verification Results

**Per-widget tests:**

```
$ cd frontend && npm test -- --run DashboardFilters
 ✓ src/components/dashboard/__tests__/DashboardFilters.test.tsx (5 tests)
 Test Files  1 passed (1)
      Tests  5 passed (5)

$ cd frontend && npm test -- --run TopSkillsCard
 ✓ src/components/dashboard/__tests__/TopSkillsCard.test.tsx (7 tests)
 Test Files  1 passed (1)
      Tests  7 passed (7)

$ cd frontend && npm test -- --run SalaryBandsCard
 ✓ src/components/dashboard/__tests__/SalaryBandsCard.test.tsx (6 tests)
 Test Files  1 passed (1)
      Tests  6 passed (6)

$ cd frontend && npm test -- --run CvVsMarketCard
 ✓ src/components/dashboard/__tests__/CvVsMarketCard.test.tsx (6 tests)
 Test Files  1 passed (1)
      Tests  6 passed (6)
```

**Full frontend suite:**

```
$ cd frontend && npm test -- --run
 Test Files  13 passed (13)
      Tests  51 passed (51)
 Start at 10:55:08
 Duration 1.47s
```

Breakdown:
- Phase 4 baseline (still passing): 17 tests across 8 files (authedFetch, AuthGate, BootErrorFallback, queryClient, ThemeToggle, shellPrimitives, AppShell, readSSEStream)
- Plan 05-04 hook tests (still passing): 10 tests (useDashboardFilters.test.tsx)
- **Plan 05-05 widget tests (newly active):** 24 tests across 4 files (DashboardFilters: 5, TopSkillsCard: 7, SalaryBandsCard: 6, CvVsMarketCard: 6)

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
> tsc -b && vite build
✓ 2655 modules transformed
✓ built in 169ms
dist/assets/Dashboard-B9W_49aA.js     344.80 kB │ gzip: 104.94 kB
```
Dashboard bundle is now ~345kB (vs the empty placeholder it replaced — the addition is mostly recharts ~85kB + radix dropdown-menu ~360kB shared with other routes).

**Phase 4 component intactness:**

```
$ git diff --stat HEAD frontend/src/components/AppShell.tsx frontend/src/components/AuthGate.tsx \
    frontend/src/components/ThemeToggle.tsx frontend/src/components/EmptyState.tsx \
    frontend/components.json frontend/src/app.css
(empty output)
```

No Phase 4 components or config modified per UI-SPEC §17. ✓

## User Setup Required

None — pure frontend module addition. No new env vars, no migrations, no MSAL config changes. The widgets are pre-wired against Plan 05-04's typed fetchers; pointing the frontend at a running backend (Plan 05-02/05-03) is enough to render the surface end-to-end.

## Next Phase Readiness

Plan 05-06 (route integration / final phase plan) can immediately:

- Treat `routes/Dashboard.tsx` as feature-complete. The named export `DashboardPage` is preserved, `App.tsx`'s lazy import unchanged, the 3-up grid composes the 4 widgets correctly.
- Validate the end-to-end smoke when both backend (Plans 05-02/05-03 deployed) and frontend (Plan 05-05 deployed) are live: navigating to `/dashboard?country=DE&seniority=senior&remote=remote` should hit `/dashboard/top-skills?country=DE&seniority=senior&remote=remote`, `/dashboard/salary-bands?...`, `/dashboard/cv-vs-market?...` in 3 concurrent requests and render the 3 widgets.
- Build the chat route (separate concern; not blocked by Plan 05-05).
- Future widgets (e.g., a "Top companies" widget in v1.1) can copy the established widget shape: `useQuery({ queryKey: ['dashboard', NAME, filters], queryFn, staleTime: 5*60_000 })` + 4-state branch render contract + describeError + verbatim UI-SPEC copy.

No blockers.

## TDD Gate Compliance

Plan 05-05 marks all 3 tasks as `tdd="true"`. The plan body's intent: stub tests RED → component GREEN → tests pass. Plan 05-01 had pre-shipped the test stubs with `describe.skipIf(!Symbol)` guards, so the "RED" gate is effectively the skipped tests. Each task's GREEN gate is its feat commit which (a) ships the component and (b) replaces the test stubs with active assertions.

Git log shows the gate sequence:

1. **Task 1 GREEN** — `805f449` `feat(05-05): ship DashboardFilters + errors helper + Dashboard route composition` — DashboardFilters.test.tsx transitions from 4 skipped stub tests to 5 active passing tests in this commit.
2. **Task 2 GREEN** — `c41bace` `feat(05-05): ship TopSkillsCard widget + TopSkillsDialog (DASH-01 + DASH-05)` — TopSkillsCard.test.tsx transitions from 6 skipped stub tests to 7 active passing tests.
3. **Task 3 GREEN** — `6efd39a` `feat(05-05): ship SalaryBandsCard + CvVsMarketCard widgets (DASH-02 + DASH-03)` — both SalaryBandsCard.test.tsx (5→6) and CvVsMarketCard.test.tsx (6→6 with content replacement) become active.

There's no separate `test(...)` commit because each task atomically lands both the implementation AND the activated tests — same pattern Plan 05-04 settled into (the strict RED-then-GREEN order is replaced by "RED via Plan 05-01 stubs that exist as skipped before this plan ran" + GREEN in feat commit). This matches the spirit of TDD (tests written before commit; commit gates on tests passing) while keeping commits atomic at the task level.

Plan-level TDD assertion: at no point did this plan land a feat commit whose tests didn't pass. `npm test -- --run` was the verify gate for each task and passed cleanly each time.

## Self-Check

Verifications below confirm claims above are accurate as of completion time.

### File existence
- `frontend/src/components/dashboard/errors.ts`: FOUND
- `frontend/src/components/dashboard/DashboardFilters.tsx`: FOUND
- `frontend/src/components/dashboard/TopSkillsCard.tsx`: FOUND
- `frontend/src/components/dashboard/TopSkillsDialog.tsx`: FOUND
- `frontend/src/components/dashboard/SalaryBandsCard.tsx`: FOUND
- `frontend/src/components/dashboard/CvVsMarketCard.tsx`: FOUND
- `frontend/src/routes/Dashboard.tsx`: FOUND (modified — PhasePlaceholder stub replaced)
- `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx`: FOUND (5 active tests)
- `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx`: FOUND (7 active tests)
- `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx`: FOUND (6 active tests)
- `frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx`: FOUND (6 active tests)
- `.planning/phases/05-dashboard/05-05-SUMMARY.md`: FOUND (this file)

### Commits
- `805f449` (Task 1 — DashboardFilters + errors.ts + Dashboard route + placeholders): FOUND
- `c41bace` (Task 2 — TopSkillsCard + TopSkillsDialog + tests): FOUND
- `6efd39a` (Task 3 — SalaryBandsCard + CvVsMarketCard + tests): FOUND

### Acceptance criteria spot-checks
- `grep -q "export function describeError" frontend/src/components/dashboard/errors.ts` ✓
- `grep -q "Unexpected error. Reload the page or try again later." frontend/src/components/dashboard/errors.ts` ✓
- `grep -q "aria-label=\"Dashboard filters\"" frontend/src/components/dashboard/DashboardFilters.tsx` ✓
- `grep -q "aria-label=\"Remote policy\"" frontend/src/components/dashboard/DashboardFilters.tsx` ✓
- `grep -q "max-w-6xl" frontend/src/routes/Dashboard.tsx` ✓
- `grep -q "grid-cols-1 md:grid-cols-3" frontend/src/routes/Dashboard.tsx` ✓
- `grep -c "PhasePlaceholder" frontend/src/routes/Dashboard.tsx` returns 0 ✓ (stub fully removed including from comments)
- `grep -q "queryKey: \['dashboard', 'top-skills', filters\]" frontend/src/components/dashboard/TopSkillsCard.tsx` ✓
- `grep -q "queryKey: \['dashboard', 'salary-bands', filters\]" frontend/src/components/dashboard/SalaryBandsCard.tsx` ✓
- `grep -q "queryKey: \['dashboard', 'cv-vs-market', filters\]" frontend/src/components/dashboard/CvVsMarketCard.tsx` ✓
- `grep -q "staleTime: 5 \* 60_000" frontend/src/components/dashboard/TopSkillsCard.tsx` ✓
- `grep -q "staleTime: 5 \* 60_000" frontend/src/components/dashboard/SalaryBandsCard.tsx` ✓
- `grep -q "staleTime: 5 \* 60_000" frontend/src/components/dashboard/CvVsMarketCard.tsx` ✓
- `grep -q "All top skills" frontend/src/components/dashboard/TopSkillsDialog.tsx` ✓
- `grep -q "Top skills" frontend/src/components/dashboard/TopSkillsCard.tsx` ✓
- `grep -q "Salary bands" frontend/src/components/dashboard/SalaryBandsCard.tsx` ✓
- `grep -q "CV vs market" frontend/src/components/dashboard/CvVsMarketCard.tsx` ✓
- `grep -q "BarChart" frontend/src/components/dashboard/SalaryBandsCard.tsx` ✓
- `grep -q "ChartContainer" frontend/src/components/dashboard/SalaryBandsCard.tsx` ✓
- `grep -q "accessibilityLayer" frontend/src/components/dashboard/SalaryBandsCard.tsx` ✓
- `grep -q "var(--chart-1)" frontend/src/components/dashboard/SalaryBandsCard.tsx` ✓
- `grep -q ".toFixed(2)" frontend/src/components/dashboard/CvVsMarketCard.tsx` ✓
- `cd frontend && npm run typecheck` exits 0 ✓
- `cd frontend && npm run lint` exits 0 ✓
- `cd frontend && npm test -- --run` reports 51 passed, 0 skipped ✓
- `cd frontend && npm run build` exits 0 ✓
- Phase 4 file diff stat (AppShell/AuthGate/ThemeToggle/EmptyState/components.json/app.css) returns empty output ✓

## Self-Check: PASSED

---
*Phase: 05-dashboard*
*Completed: 2026-05-22*
