---
phase: 05-dashboard
verified: 2026-05-23T02:15:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
requirements_satisfied: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, SHEL-03, SHEL-06]
re_verification: null
---

# Phase 5: Dashboard Verification Report

**Phase Goal:** Phase 5 ships the first shareable surface when the Dashboard page renders three analytical widgets (top skills, salary bands, CV-vs-market score) under a shared filter bar, with state round-tripping through URL search params.

**Verified:** 2026-05-23T02:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria — canonical contract)

| #   | Truth                                                                                                                                                                                                | Status      | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --- | -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------| ----------- | -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1   | SC1: Deep-link pre-populates filters; changing any filter updates URL in place (DASH-04, DASH-06)                                                                                                    | VERIFIED    | `useDashboardFilters.ts` (lines 54-99): `useSearchParams` + `setParams` updater form + `replace: false` history-push; defensive `isCountry`/`isRemote`/`isSeniority` type guards; default elision via `next.delete(...)`. 10/10 hook tests pass (deep-link read, default elision, defensive coercion). M3 UAT screenshot `m3-refresh-state-preserved.png` confirms `/dashboard?country=DE&seniority=senior&remote=remote` round-trips. |
| 2   | SC2: Top-skills widget shows top 8-10 hard skills with must-have/nice-to-have split; "show more" drill-down (DASH-01, DASH-05)                                                                       | VERIFIED    | `TopSkillsCard.tsx` line 96 (`<CardTitle>Top skills</CardTitle>`) + line 120 (`Show more` button) + line 124 (`<TopSkillsDialog>`); soft skills hidden via `skill_category != 'soft'` in `analytics.py:129`; `TopSkillsDialog.tsx:26` `<DialogTitle>All top skills</DialogTitle>` with `max-h-[70vh] overflow-y-auto` (line 31). 7/7 widget tests pass. M4 UAT confirmed scrollable 15+ row table.                                |
| 3   | SC3: Salary-bands widget shows p25/p50/p75 via `percentile_cont`, with "N of M postings had salary data" footnote (DASH-02)                                                                          | VERIFIED    | `analytics.py:214-216` uses `func.percentile_cont(0.25/0.50/0.75).within_group(normalized_salary.asc())`; month rows normalized x12 via `case`; hour rows excluded (`salary_period.in_(["year", "month"])`). `SalaryBandsCard.tsx:105` renders `{data.postings_with_salary} of {data.total_postings}`. M1 + M2 UAT confirmed footnote rendered ("26 of 88 postings had salary data" WW; "1 of 5" DE+Senior+Remote).             |
| 4   | SC4: CV-vs-market widget shows aggregate mean score + top 3 missing must-haves; updates with filters (DASH-03)                                                                                       | VERIFIED    | `analytics.py:cv_match` uses `selectinload(JobPostingDB.requirements)` (line 280) + Counter.most_common(3) for top 3 missing. `CvVsMarketCard.tsx:77` renders `data.mean_score.toFixed(2)` hero number; `:86` renders `<Badge variant="secondary">` chips. D-12 zero-postings returns `{mean_score: null, postings_compared: 0, top_missing_must_have: []}`. M2 UAT: PL=0.29, DE=0.28, EU/WW=0.28 with distinct missing-skill chips. |
| 5   | SC5: Country flip PL/DE/EU/WW produces different numbers across all 3 widgets (canary proves SQL flow) (DASH-01..04)                                                                                 | VERIFIED    | M2 UAT live evidence (PL: Python=40, p50=€793,440, missing Azure/AWS/SQL; DE: Python=29, p50=€67,500, missing TensorFlow/LLMs/ML; EU≡WW because corpus is EU-only). Backend `_apply_filters` (analytics.py:45-91) implements 4-value country branch including EU-27 union OR `location_region='EU'` per D-07. Pytest `TestFilterEffects::test_country_filter_changes_results` passes.                                          |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/job_rag/services/analytics.py` | top_skills + salary_bands + cv_match + _apply_filters + EU_COUNTRY_CODES | VERIFIED | 296 lines; 3 async functions, 1 private helper, frozenset[str] with exactly 27 ISO codes (DE/PL/GR in; GB/EL out). |
| `src/job_rag/api/dashboard.py` | 5 Pydantic models + 2 StrEnums | VERIFIED | 125 lines; CountryFilter / RemoteFilter / TopSkillItem / DashboardTopSkillsResponse / DashboardSalaryBandsResponse / MissingSkillItem / DashboardCvMatchResponse; nullable p25/p50/p75; nullable mean_score. |
| `src/job_rag/api/routes.py` | 3 @router.get handlers under /dashboard/* | VERIFIED | Lines 244-336 contain 3 handlers (top-skills, salary-bands, cv-vs-market) tagged `["dashboard"]`, each with `response_model=DashboardXxxResponse`, `Depends(require_api_key)`, `Depends(dashboard_limit)` (post-hotfix 120/min), `Depends(get_current_user_id)`. |
| `tests/test_analytics.py` | All 6 test classes flip to active | VERIFIED | 27/27 tests pass (TestTopSkills 4, TestSalaryBands 5, TestCvMatch 4, TestApplyFilters 7, TestEuCountrySetMembership 6, TestFilterEffects 1). |
| `tests/test_api.py::TestDashboardEndpoints` | 8 active tests | VERIFIED | 8/8 tests pass: shape (3), unauthed→401 (1), invalid country→422 (1), 4-value country (1), named-schema (1), D-12 zero-state (1). |
| `frontend/openapi.snapshot.json` | Regenerated with 3 paths + 7 named schemas | VERIFIED | Contains `/dashboard/{top-skills,salary-bands,cv-vs-market}` and `CountryFilter`, `DashboardCvMatchResponse`, `DashboardSalaryBandsResponse`, `DashboardTopSkillsResponse`, `MissingSkillItem`, `RemoteFilter`, `TopSkillItem`. |
| `frontend/src/api/types.ts` | Codegen output with 7 new named schemas | VERIFIED | All 7 schemas present; Seniority enum union present. |
| `frontend/src/api/jobs.ts` | 3 typed fetchers + buildFilterQuery | VERIFIED | `topSkills`, `salaryBands`, `cvVsMarket` wrap authedFetch; `buildFilterQuery` applies default elision matching the URL-side. |
| `frontend/src/components/dashboard/useDashboardFilters.ts` | URL state hook with default elision | VERIFIED | useSearchParams + setParams updater form + replace:false; isCountry/isRemote/isSeniority type guards. |
| `frontend/src/components/dashboard/useDashboardFilters.test.tsx` | At least 6 active vitest tests | VERIFIED | 10/10 tests pass; renamed from `.test.ts` to `.test.tsx` (intentional — esbuild requires .tsx for JSX MemoryRouter wrapper; documented in 05-04-SUMMARY.md Deviation #1). |
| `frontend/src/components/dashboard/DashboardFilters.tsx` | Country dropdown + seniority + remote toggle | VERIFIED | DropdownMenuRadioGroup for country (4 items) + seniority (6 items) + ToggleGroup for remote (3 items). |
| `frontend/src/components/dashboard/TopSkillsCard.tsx` | TanStack Query useQuery + 4 states + Show more | VERIFIED | useQuery with `staleTime: 5*60_000`; 4-state branch (Skeleton/Alert/EmptyState/data); Show more button when skills.length > 10. |
| `frontend/src/components/dashboard/TopSkillsDialog.tsx` | Scrollable modal with full ranked list | VERIFIED | DialogTitle "All top skills"; max-h-[70vh] overflow-y-auto; sticky-top thead; 5 columns (#, Skill, Must, Nice, Total). |
| `frontend/src/components/dashboard/SalaryBandsCard.tsx` | Recharts BarChart with p25/p50/p75 | VERIFIED | `<BarChart>` inside `<ChartContainer>` with accessibilityLayer; LabelList; "N of M postings had salary data" footer. |
| `frontend/src/components/dashboard/CvVsMarketCard.tsx` | Hero score + Badge chips | VERIFIED | text-5xl `data.mean_score.toFixed(2)`; aria-label `Match score X.YZ`; up-to-3 Badge variant=secondary chips. |
| `frontend/src/components/dashboard/errors.ts` | describeError helper | VERIFIED | Shared error message helper imported by all 3 widget Alert branches. |
| `frontend/src/routes/Dashboard.tsx` | 3-up grid replacing PhasePlaceholder | VERIFIED | `grid grid-cols-1 md:grid-cols-3 gap-4` composing DashboardFilters + TopSkillsCard + SalaryBandsCard + CvVsMarketCard; named export DashboardPage preserved. |
| `.planning/phases/05-dashboard/05-UAT.md` | 6 M-marker evidence + 9 screenshots | VERIFIED | 296-line UAT document with all 6 M-markers (M1-M5 PASS, M6 DOCUMENTED), 9 screenshots in `uat-screenshots/`, hotfix-commit chronology, 4 explicit deviation triage. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `routes.py` /dashboard/* handlers | `analytics.py` (top_skills/salary_bands/cv_match) | `from job_rag.services.analytics import ... as analytics_*` | WIRED | Lines 56-67 of routes.py import the 3 functions; each handler calls `await analytics_*(session, ...)` with `.value` conversions on enum params. |
| `routes.py` /dashboard/* handlers | `api/dashboard.py` (response models + filter enums) | `from job_rag.api.dashboard import ...` | WIRED | Lines 41-49 import CountryFilter, RemoteFilter, plus 3 response models; each handler annotates `response_model=Dashboard*Response`. |
| `analytics.py` cv_match | `services/matching.py` (load_profile + match_posting) | `from job_rag.services.matching import load_profile, match_posting` | WIRED | Line 28 imports both; cv_match folds match_posting over selectinload'd postings (line 280). |
| `analytics.py` salary_bands | PostgreSQL `percentile_cont` via SQLAlchemy `func.percentile_cont(...).within_group(...)` | Mandatory `.within_group(<expr>.asc())` chain (Pitfall 1) | WIRED | Lines 214-216 use the canonical SQLAlchemy ordered-set aggregate form. |
| `frontend/src/api/jobs.ts` | `frontend/src/api/authedFetch.ts` | `import { authedFetch }` + 3 fetcher calls | WIRED | Line 12 imports; each fetcher calls `authedFetch('/dashboard/...')` with optional AbortSignal. |
| `frontend/src/api/authedFetch.ts` | MSAL Bearer token | `headers.set('Authorization', \`Bearer ${token}\`)` | WIRED | Line 60 attaches Bearer header from acquireTokenSilent; line 73 attaches on 401-retry path. |
| 3 widget cards | `frontend/src/api/jobs.ts` fetchers | `useQuery({ queryFn: ({signal}) => topSkills/salaryBands/cvVsMarket(filters, signal) })` | WIRED | TopSkillsCard line 89, SalaryBandsCard line 48, CvVsMarketCard line 43 — all 3 widgets wire useQuery to their fetcher with filters as queryKey + AbortSignal propagation. |
| `DashboardFilters` + 3 widgets | `useDashboardFilters` hook | `const { filters, setFilters } = useDashboardFilters()` | WIRED | DashboardFilters.tsx line 31 (reads + writes); each widget reads via `const { filters } = useDashboardFilters()`. |
| `routes/Dashboard.tsx` | 4 dashboard components | JSX composition under grid layout | WIRED | Lines 13-18 compose DashboardFilters + grid 3-up of TopSkillsCard / SalaryBandsCard / CvVsMarketCard. |
| `frontend/openapi.snapshot.json` | `app.openapi()` deterministic capture | In-process Python script (Plan 04-01 pattern) | WIRED | Snapshot contains 3 /dashboard/* paths and 7 named schemas; back-to-back captures diff-clean. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| TopSkillsCard | `data` (useQuery result) | `topSkills(filters, signal)` → authedFetch → `/dashboard/top-skills` → `analytics_top_skills` → SQLAlchemy SELECT against JobRequirementDB JOIN JobPostingDB | YES | M1 UAT live; M2 PL=Python(40), DE=Python(29). |
| SalaryBandsCard | `data` (useQuery result) | `salaryBands(filters, signal)` → authedFetch → `/dashboard/salary-bands` → `analytics_salary_bands` → `percentile_cont` against JobPostingDB | YES | M1 + M2 UAT live; M2 DE p50=€67,500 with footnote "26 of 88 postings had salary data". |
| CvVsMarketCard | `data` (useQuery result) | `cvVsMarket(filters, signal)` → authedFetch → `/dashboard/cv-vs-market` → `analytics_cv_match` → selectinload + Counter.most_common(3) | YES | M2 UAT: PL=0.29, DE=0.28; distinct top-3 missing-must-have skill chips per country. |
| DashboardFilters | filters (from hook) | `useSearchParams()` round-trip; setFilters writes via `setParams` updater | YES | M3 UAT: deep-link URL → filter UI state preserved on refresh. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Backend analytics module functions importable + EU_COUNTRY_CODES contract | `uv run python -c "from job_rag.services.analytics import EU_COUNTRY_CODES; assert len(EU_COUNTRY_CODES) == 27 and 'DE' in EU_COUNTRY_CODES and 'GR' in EU_COUNTRY_CODES and 'GB' not in EU_COUNTRY_CODES and 'EL' not in EU_COUNTRY_CODES and isinstance(EU_COUNTRY_CODES, frozenset)"` | Exit 0 — len=27, DE/PL/GR in, GB/EL out, is frozenset | PASS |
| Backend test suite (analytics + dashboard endpoints) | `uv run pytest tests/test_analytics.py tests/test_api.py::TestDashboardEndpoints -v` | 35/35 PASSED in 3.02s (27 analytics + 8 dashboard endpoint tests) | PASS |
| OpenAPI surface integrity | `uv run python -c "from job_rag.api.app import app; s = app.openapi(); ..."` checks 3 paths + 7 named schemas + tags=['dashboard'] | All assertions pass — "OpenAPI integrity: OK" | PASS |
| Frontend test suite | `cd frontend && npm test -- --run` | 51/51 PASSED across 13 test files; 0 skipped, 0 failed | PASS |
| OpenAPI snapshot contains dashboard surface | Python JSON check on `frontend/openapi.snapshot.json` | 3 paths + 7 schemas confirmed | PASS |
| Live M2 country canary (SC5) | Manual UAT against deployed SWA | PL/DE/EU/WW: distinct Top-1 skill, p50, mean_score, missing chips | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| DASH-01 | 05-01, 05-02, 05-03, 05-05 | Analytical endpoint returns top-N skills with must-have/nice-to-have split, server-side SQL aggregation | SATISFIED | `analytics.py::top_skills` uses `func.sum(case((required.is_(True), 1), else_=0))` SQL aggregation; route `/dashboard/top-skills`; TopSkillsCard renders bars. 4/4 TestTopSkills pass. |
| DASH-02 | 05-01, 05-02, 05-03, 05-05 | Salary bands p25/p50/p75 via PostgreSQL percentile_cont; N of M footnote | SATISFIED | `analytics.py::salary_bands` uses `percentile_cont.within_group`; month normalized x12; hour excluded. SalaryBandsCard.tsx line 105 renders "N of M postings had salary data". M2 UAT verified footnote. |
| DASH-03 | 05-01, 05-02, 05-03, 05-05 | CV-vs-market aggregate match score + top 3 missing must-haves | SATISFIED | `analytics.py::cv_match` reuses match_posting() formula unchanged (D-10); Counter.most_common(3); D-12 zero-state returns 200 not 404. CvVsMarketCard renders hero + Badge chips. M2 UAT verified per-country variation. |
| DASH-04 | 05-01, 05-03, 05-04, 05-05 | Dashboard React page with shared filter bar (country/seniority/remote) | SATISFIED | DashboardFilters.tsx wires DropdownMenuRadioGroup (4 country items: Worldwide/EU/Germany/Poland) + 6 seniority items + ToggleGroup (3 remote items). All 3 widgets share same filters via hook. |
| DASH-05 | 05-01, 05-05 | Top-skills "show more" drill-down with full ranked list | SATISFIED | TopSkillsCard.tsx line 120 "Show more" button opens TopSkillsDialog with `max-h-[70vh] overflow-y-auto` 5-column table. M4 UAT confirmed scrolling. |
| DASH-06 | 05-01, 05-04, 05-05 | Dashboard filter state syncs to URL search params (deep-link + refresh safe) | SATISFIED | useDashboardFilters.ts uses useSearchParams + setParams updater + replace:false. Default elision via next.delete. 10/10 hook tests pass. M3 UAT verified URL round-trip survives refresh. |
| SHEL-03 (carry-forward) | 05-04, 05-05 | TanStack Query for server state (no ad-hoc useEffect fetching) | SATISFIED | All 3 widgets use useQuery with staleTime: 5*60_000 + queryKey: ['dashboard', NAME, filters] + queryFn signal propagation. |
| SHEL-06 (carry-forward) | 05-05 | Per-page loading/empty/error states + error boundary | SATISFIED | Each widget implements 4-state branch (Skeleton/Alert/EmptyState/data); describeError shared helper. |

**All 6 phase requirements (DASH-01..06) and 2 carry-forwards (SHEL-03, SHEL-06) satisfied.**

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | TODO/FIXME/placeholder/coming soon | — | No anti-patterns detected in dashboard source files (analytics.py, dashboard.py, routes.py dashboard handlers, all 5 widget components, hook, jobs.ts, errors.ts). The single `return null` in `TopSkillsCard.tsx` is an inner guard for an empty array within a fully-rendered SkillsBarList component (not a stub at the top level). |

### Out-of-Scope Findings (documented in UAT, deferred to v2/Phase 8)

These are explicit acceptances, NOT verification failures:

1. **PLN currency normalization (M2 PL p50 €793,440/yr)** — deferred to v2 per existing PROJECT.md §Constraints decision ("salary values treated as EUR; FX-aware conversion is a v2 platform feature"). Visible inflated number is a tolerable signal to the v1 user (Adrian).
2. **EU ≡ WW corpus scope** — Phase 8 polish candidate. Country filter is correctly implemented; identical EU/WW numbers are a corpus-distribution artifact, not a SQL bug.
3. **N=1 salary-bands rendering** — Phase 8 polish candidate. Visual artifact when filter narrows to 1 salary-bearing posting; numbers are correct, chart shape is degenerate.
4. **`--chart-1` saturation** — Phase 8 polish candidate. Recharts neutral-gray accent is correct per radix-nova Linear-dense ethos but visually subtle on theme toggle.

### Pre-existing Test Failures (not Phase 5 regressions)

`tests/test_alembic.py::test_0004_upgrade_smoke` and `test_0004_downgrade_smoke` fail with `KeyError: 'DATABASE_URL'`. Logged in `.planning/phases/05-dashboard/deferred-items.md`. Reproduced on `git stash` of all Plan 05-02 changes — these failures pre-date Phase 5 and are unrelated to dashboard work.

### Human Verification Required

None. Live UAT (Plan 05-06) already exercised:
- Initial render with real Entra-authenticated traffic (M1)
- Country-flip canary against real corpus (M2)
- Refresh-state preservation (M3)
- Show More dialog scrolling (M4)
- Theme toggle on /dashboard (M5)
- Cold-start documentation (M6)

All 6 M-markers have human-confirmed outcomes with 9 screenshots in `.planning/phases/05-dashboard/uat-screenshots/`. UAT overall verdict: PASS WITH DOCUMENTED FINDINGS.

### Gaps Summary

None. All 5 ROADMAP success criteria met. All 8 requirement IDs (DASH-01..06 + SHEL-03/06) satisfied. All artifacts present, substantive, wired, and producing real data (Level 4 trace confirmed via live UAT M2 canary). 35/35 backend tests + 51/51 frontend tests pass.

The phase exposed a latent Phase 4 auth bug (`_expected_issuer()` subdomain mismatch) during UAT; root cause was fixed in `ab9437d` and verified by a successful M1 dashboard render against deployed prod. The hotfix commits (`fbf82c6` rate-limit bump 30→120/min, `8c8037a` React Query skip-4xx-retry, `ab9437d` iss-subdomain fix) all landed before UAT close.

Phase goal — "ship the first shareable surface when the Dashboard page renders three analytical widgets under a shared filter bar with URL state round-trip" — is achieved. Ready to mark Phase 5 verified.

---

_Verified: 2026-05-23T02:15:00Z_
_Verifier: Claude (gsd-verifier)_
