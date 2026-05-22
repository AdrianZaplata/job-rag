# Phase 5: Dashboard — Research

**Researched:** 2026-05-22
**Domain:** PostgreSQL analytical aggregation via SQLAlchemy 2.x async (`percentile_cont().within_group()`, `case()` + `func.sum()` GROUP BY, `selectinload` fold); FastAPI 0.135 `/dashboard/*` analytical endpoints with explicit Pydantic response models; Vite 8 + React 19.2 dashboard surface using existing TanStack Query 5.100 + React Router v7 + shadcn/ui (radix-nova / neutral) primitives plus net-new `alert`, `chart`, `toggle-group`; Recharts 3.x via shadcn chart block for ONE chart (salary bands).
**Confidence:** HIGH — every recommended library version verified against the live registry on 2026-05-22; SQLAlchemy 2.0 `percentile_cont`/`case()` syntax cited from official docs; CONTEXT.md decisions are pre-locked (23/23 auto-resolved) so Phase 5 research is mostly mechanical gap-filling.

---

## Summary

Phase 5 is a pure additive feature surface — 3 new analytical FastAPI endpoints under `/dashboard/*`, one new backend service module `src/job_rag/services/analytics.py`, and a Dashboard React page composed of three independent widgets under a shared filter bar with URL search-param state. CONTEXT.md auto-resolved all 23 design decisions to the "Recommended" pattern (carried forward from Phase 4's 20/20 lock rate), so the researcher's job is purely to verify libraries, cite the right SQL constructs, surface the EU-27 ISO snapshot, and document the inheritance from Phase 4 patterns (`authedFetch`, `queryClient`, `AppShell`/`AuthGate`, layered SHEL-06).

**Two substantive technical notes for the planner:**

1. **shadcn theme detail correction.** Phase 4 RESEARCH.md documented theme as `style=new-york`/`base-color=zinc`. The actual on-disk `frontend/components.json` was landed with `style=radix-nova`/`baseColor=neutral`/`iconLibrary=lucide`. Phase 5 net-new shadcn installs (`alert`, `chart`, `toggle-group`) inherit whatever the existing `components.json` declares — do NOT override the style flag during install. The Phase 4 deviation is benign; flagging it so the planner doesn't introduce a third theme variant. [VERIFIED: `cat frontend/components.json` 2026-05-22]

2. **CONTEXT.md D-08 / `Seniority.UNKNOWN` filter behaviour.** D-08 says the UI hides the `unknown` value but the backend accepts it defensively. Confirm the planner emits the backend `Seniority` enum literal validation that accepts `unknown` — Pydantic will reject `?seniority=foobar` correctly but a typo like `?seniority=UNKNOWN` (uppercase) will 422. Recommend the planner pin the FastAPI `Query(...)` parameter to the existing `Seniority` enum from `src/job_rag/models.py` so the wire contract is the enum value (lowercase strings). [VERIFIED: `src/job_rag/models.py` lines 76-82]

Everything else is mechanical: SQL gets written against the existing `JobPostingDB`/`JobRequirementDB` schema (all needed indexes already exist per `db/models.py` lines 54-59 and 76-79), routes mirror the `/match` / `/gaps` pattern, the frontend extends `frontend/src/api/jobs.ts` from stub to typed service module, and widgets compose existing shadcn primitives (`Card`, `Skeleton`, `Dialog`, `DropdownMenu`, `Badge`) plus three net-new ones (`alert`, `chart`, `toggle-group`).

**Primary recommendation:** open the planner with **Wave 0** = test scaffolding (`tests/test_analytics.py` skeleton, conftest fixture audit, new test data variants) + shadcn install (`alert`, `chart`, `toggle-group`) + `pyproject.toml` no-op (no new backend deps). **Wave 1** = backend (`analytics.py` service module + Pydantic response models + 3 routes) — entirely server-side, ships first so Wave 2 can codegen against it. **Wave 2** = frontend (codegen refresh + `jobs.ts` typed service + `useDashboardFilters` hook + 3 widgets + filter bar + Dashboard page) in parallel-eligible plans (filter bar + each widget can fan out once `useDashboardFilters` lands). **Wave 3** = phase-close runbook (live verification of the "different numbers per country" success criterion + screenshots for Phase 8 README).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**A. Backend endpoint architecture**
- **D-01:** Three independent analytical endpoints under `/dashboard/*` (top-skills, salary-bands, cv-vs-market). Each widget gets its own React Query key + per-widget error boundary; bundled `/dashboard` rejected.
  - `GET /dashboard/top-skills?country=&seniority=&remote=&include_soft=false&limit=50` → `{ skills: [{skill, must_count, nice_count, total}], total_postings, unique_skills }`
  - `GET /dashboard/salary-bands?country=&seniority=&remote=` → `{ p25, p50, p75, postings_with_salary, total_postings, currency: "EUR" }`
  - `GET /dashboard/cv-vs-market?country=&seniority=&remote=` → `{ mean_score, postings_compared, top_missing_must_have: [{skill, count, percentage}] }`
- **D-02:** New service module `src/job_rag/services/analytics.py` with three async functions (`top_skills`, `salary_bands`, `cv_match`) sharing a private `_apply_filters(stmt, *, country, seniority, remote)` helper. Routes wire `Depends(get_current_user_id)` + `Depends(standard_limit)` (30/min, same as `/search`).
- **D-03:** All endpoints use `Depends(get_current_user_id)` even though v1 data isn't per-user — carries forward Phase 1 D-10 + Phase 4 D-08 pattern.

**B. SQL aggregation strategy**
- **D-04:** SQLAlchemy ORM/Core for top-skills; `func.percentile_cont().within_group()` for salary-bands; hybrid SQL+Python for cv-vs-market. Top-skills uses `case((cond, 1), else_=0)` + `func.sum()` + `GROUP BY skill`; salary-bands filters `WHERE salary_min IS NOT NULL AND salary_period IN ('year','month')` and normalizes month→year via `* 12` in SELECT.
- **D-05:** CV-vs-market uses SQL pre-filter + Python per-posting fold. SQL fetches filtered postings with `selectinload(JobPostingDB.requirements)` (existing `/gaps` pattern). Python loops `match_posting()` per row, `Counter` over `missed_must_have`, cap at 3. O(n) per request where n ≤ 108 in v1; revisit if corpus grows >1000.
- **D-06:** Profile source = continue calling `load_profile()` (reads `data/profile.json` via existing function-body shim). Phase 7 PROF-01 flips the body to DB; Phase 5 doesn't anticipate the change. `load_profile(user_id=...)` signature already accepts user_id keyword-only.

**C. Filter semantics**
- **D-07:** Country filter = canonical 4-value enum (`?country=PL|DE|EU|WW`). `EU` branch = `location_country IN <EU-27 ISO codes>` OR `location_region = 'EU'`. `EU_COUNTRY_CODES: frozenset[str]` hardcoded in `analytics.py` as ISO-3166 alpha-2 codes with snapshot-date comment.
- **D-08:** Seniority filter = single optional value from `Seniority` enum. Omitted = no filter. UI hides `unknown`; backend accepts `?seniority=unknown` defensively.
- **D-09:** Remote filter = 3-state tri-toggle (`?remote=any|remote|non_remote`). `any` (default, omitted) = no filter; `remote` = `remote_policy = 'remote'`; `non_remote` = `remote_policy IN ('hybrid','onsite')`.

**D. CV-vs-market scoring semantics**
- **D-10:** Match score formula = existing `match_posting()` formula UNCHANGED. `score = (matched_must / total_must) * 0.7 + (matched_nice / total_nice) * 0.3`. Aggregate = arithmetic mean.
- **D-11:** Top-3 missing must-have skills = top 3 by frequency in `match_posting(...)["missed_must_have"]` via `collections.Counter`. Returned with `count` and `percentage` (count / total_postings).
- **D-12:** Zero-postings filter = `{ mean_score: null, postings_compared: 0, top_missing_must_have: [] }` HTTP 200. Do NOT 404.

**E. Soft-skill default + filter**
- **D-13:** Soft skills hidden by default; no UI toggle in v1. Backend accepts `?include_soft=true` for future flexibility; Phase 5 does NOT surface UI.

**F. Frontend stack & visualization**
- **D-14:** Single chart library install = `recharts` via `npx shadcn@latest add chart`. Lands `frontend/src/components/ui/chart.tsx` wrapper + adds `recharts ^3` to deps. Salary-bands uses `BarChart`. Top-skills uses Tailwind-native horizontal bars (no chart lib). CV-vs-market uses big-text score + chip list.
- **D-15:** Dashboard component tree under `frontend/src/components/dashboard/`: `DashboardFilters.tsx`, `TopSkillsCard.tsx`, `SalaryBandsCard.tsx`, `CvVsMarketCard.tsx`, `useDashboardFilters.ts`, `api.ts`. Routes folder gets one file (`Dashboard.tsx`).
- **D-16:** API service module shape = extend `frontend/src/api/jobs.ts` (currently stub) — exports `topSkills`, `salaryBands`, `cvVsMarket`. All call `authedFetch` + cast against `openapi-typescript`-generated types.

**G. URL state + filter hook**
- **D-17:** `useDashboardFilters()` typed hook wraps `useSearchParams`. Default elision: omit `country=WW` / `remote=any` from URL. Returns `{ country: 'PL'|'DE'|'EU'|'WW', seniority?: Seniority, remote: 'any'|'remote'|'non_remote', setFilters }`. React Query keys: `['dashboard', 'top-skills', filters]`.

**H. Layout & widget framing**
- **D-18:** 3-up grid on desktop (`grid grid-cols-1 md:grid-cols-3 gap-4`), single column on mobile. Filter bar = horizontal flex on md+, stacked on mobile. Each widget = shadcn `Card` with `CardHeader` (title + sample-size footnote) + `CardContent`. Remote control = `ToggleGroup` (NEW shadcn primitive).

**I. Loading / empty / error states**
- **D-19:** Per-widget skeletons + per-widget empty states + per-widget error fallbacks. Loading: `useQuery().isPending` → shadcn `Skeleton`. Empty (zero postings): `<EmptyState>` (Phase 4 component) with widget-specific copy. Error: per-widget `<Alert variant="destructive">` (NEW shadcn primitive). No whole-page error/empty branch.

**J. Top-skills "show more" UX**
- **D-20:** Click "Show more" → shadcn `Dialog` modal with full ranked list (scrollable `<table>` since shadcn `table` primitive not installed). Backend `?limit=50` default; client renders top-10 in card, modal shows all 50.

**K. Sample size & metadata footnotes**
- **D-21:** Every widget surfaces its `n` in card footer. Top-skills: `"{total_postings} postings · {unique_skills} unique hard skills"`. Salary-bands: `"{postings_with_salary} of {total_postings} postings had salary data"` (literal DASH-02 footnote). CV-vs-market: `"Score across {postings_compared} postings"`.

**L. Caching**
- **D-22:** TanStack Query `staleTime: 5 * 60_000` for all dashboard queries. Override Phase 4 D-Discretion default of 30s. Apply per-query via `staleTime` option, NOT globally.

**M. Linear-dense aesthetic**
- **D-23:** Number-forward over chart-forward. Top-skills: numeric counts beside each bar. Salary-bands: 3 bars labeled `€{value}/yr`. CV-vs-market: big number (2 decimals) + thin baseline indicator. Card titles `text-sm font-medium`, body data `text-2xl`, footnotes `text-xs`.

### Claude's Discretion
- Backend route file placement: extend `src/job_rag/api/routes.py` directly (single routes file pattern).
- OpenAPI tag: all 3 endpoints tagged `"dashboard"` so codegen-typed client groups them.
- Query parameter parsing: native FastAPI `Query(...)` + Pydantic enum validation for `country`/`remote`.
- Salary period normalization: `salary_min * 12` when `salary_period = 'month'`; drop `salary_period = 'hour'`.
- Recharts theme: pull colors from CSS vars (`--chart-1` ... `--chart-5`) that shadcn `chart` block wires up.
- Test placement: backend tests in `tests/test_analytics.py`; frontend tests as `*.test.tsx` colocated.
- Test data: use existing 98 reextracted postings in dev DB (real shape variation).
- Filter bar reuse: `DashboardFilters.tsx` lives under `components/dashboard/`. Refactor up later if reused.
- Match alias-index: `_ALIAS_GROUPS` empty (Phase 1 D-12). Surface as deferred idea if duplicates appear.
- EU-27 list source-of-truth: hardcoded `frozenset` in `analytics.py` + ISO-3166 snapshot date comment.
- Currency assumption: all salary values treated as EUR. Document as known limitation.
- Pagination: not needed (top-skills capped at 50, salary 3 numbers, cv-vs-market 3 missing).
- Layout breakpoints: `md:grid-cols-3` (≥768px); single column below.
- Accessibility: filter dropdowns inherit shadcn a11y; charts add `aria-label`; skeletons use `role="status" aria-live="polite"`.
- Empty filter combos: per-widget empty state handles `country=PL` + `seniority=staff` returning 0.

### Deferred Ideas (OUT OF SCOPE)
- Interactive cross-filtering (v2 DASH2-01).
- Skill co-occurrence view (v2 DASH2-02).
- Time-series trends (v2 DASH2-03).
- Per-posting drill-down pages (v2 DASH2-04).
- "Show soft skills" UI toggle.
- Skill alias matching (`_ALIAS_GROUPS` empty).
- All-countries-in-corpus dynamic dropdown.
- Hourly/contract salary normalization.
- Currency normalization (FX).
- Pagination on top-skills modal.
- Widget order configurability.
- Export to CSV/PNG.
- Always-warm ACA (€8/mo — out of budget).
- Pydantic response models in `models.py` vs `api/dashboard.py` — planner-discretion.
- Replacing `/gaps` with `/dashboard/cv-vs-market` — `/gaps` consumed by Phase 6 agent tool.
- Phase 04.1 in-flight (5 follow-ups parallel-eligible; Phase 5 does NOT depend).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Analytical endpoint returns top-N skills with must-have / nice-to-have split, filterable by country / seniority / remote; server-side SQL aggregation | §SQL Patterns — Top-skills SQL with `case((...,1), else_=0)` + `func.sum()` + `GROUP BY`; §Architectural Responsibility Map — Capability "top-skills"; §Code Examples — `analytics.top_skills()` |
| DASH-02 | Salary bands (p25 / p50 / p75) endpoint via PostgreSQL `percentile_cont` | §SQL Patterns — Salary-bands with `func.percentile_cont(0.5).within_group(...asc())`; period normalization; §Pitfalls — NULL handling, empty result set, hourly rows |
| DASH-03 | CV-vs-market aggregate match score + top 3 missing must-have skills | §Hybrid SQL+Python Fold — `selectinload` + `match_posting` loop + `Counter`; §Code Examples — `analytics.cv_match()` |
| DASH-04 | Dashboard renders 3 widgets under shared filter bar (country: Poland/Germany/EU/Worldwide; seniority; remote toggle) | §Architecture Patterns — 3-up grid + filter bar; §EU-27 ISO Snapshot; §Code Examples — `DashboardFilters.tsx` |
| DASH-05 | Top-skills widget "show more" drill-down with full ranked list | §Code Examples — shadcn `Dialog` with scrollable `<table>`; §Architectural Responsibility Map — Capability "top-skills show more" |
| DASH-06 | Dashboard filter state syncs to URL search params (deep links + refresh safe) | §Code Examples — `useDashboardFilters` hook + default elision; §React Router v7 `useSearchParams` pattern |
| SHEL-03 (carry-forward) | Server state flows through TanStack Query | §Caching strategy — per-query `staleTime: 5 * 60_000` override; §Code Examples — `useQuery` with structured key |
| SHEL-06 (carry-forward) | Error boundary + empty/error/loading states for every page | §Loading / Empty / Error Layered Pattern; §Architecture Patterns — D-19 inheritance from Phase 4 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Backend tech stack frozen**: Python 3.12, FastAPI, LangGraph 1.1.x, PostgreSQL 17 + pgvector, SQLAlchemy 2.x async, Instructor, OpenAI SDK. Phase 5 adds NOTHING to backend deps (no new packages).
- **Frontend stack frozen**: Vite + React 19 + TypeScript, Tailwind v4, shadcn/ui (existing config `style=radix-nova`, `baseColor=neutral`, `iconLibrary=lucide` per `frontend/components.json`). Phase 5 adds `recharts ^3` (transitively via shadcn chart block) + zero net-new top-level deps beyond what `npx shadcn@latest add alert chart toggle-group` pulls.
- **Cloud provider**: Azure only. Phase 5 does NOT touch infrastructure (no Terraform, no Container App env vars, no migrations).
- **Budget**: €0/mo. Phase 5 runtime cost = the existing B1ms Postgres; analytical queries are index-served.
- **IaC**: Terraform only — N/A for Phase 5 (no infra changes).
- **Single user (structurally multi-user)**: every endpoint goes through `Depends(get_current_user_id)`; the `user_id` value is accepted but unused inside analytical queries in v1 (Phase 7 PROF-01 will use it for cv-vs-market once profile is per-user).
- **One cloud, one provider per concern**: N/A for Phase 5 (no new services).
- **Educational goal**: frontend stays UI-only (no SQL, no Python-style aggregations); backend stays data-only (no markdown formatting, no widget framing). Concretely for Phase 5: the backend returns numbers and label strings; the frontend handles all chart rendering, bar drawing, dialog framing.
- **GSD enforcement**: This research run was invoked under GSD; downstream task execution will happen under `/gsd-execute-phase 5`.
- **Code style**: ruff target-version `py312`, line-length 100, rules `E F I UP`. Pyright basic mode. Python 3.12 `X | Y` syntax. `structlog.get_logger(__name__)` per module. `from job_rag.X import Y` absolute imports.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Top-skills SQL aggregation (must/nice split, soft-skill filter) | API / Backend (`analytics.top_skills`) | Database (indexed columns) | Server-side SQL aggregation is DASH-01 wording; index-served by `ix_job_requirements_skill_category` + posting indexes. |
| Salary-bands percentiles (p25/p50/p75) | API / Backend (`analytics.salary_bands`) | Database (`percentile_cont` ordered-set aggregate) | DASH-02 mandates PostgreSQL `percentile_cont` server-side. |
| CV-vs-market score + missing skills | API / Backend (`analytics.cv_match`) hybrid | `matching.match_posting` (existing) | Fuzzy skill match cannot trivially be SQL; SQL pre-filter + Python fold is the right shape for v1 corpus size. |
| Filter parameter validation | API / Backend (FastAPI `Query(...)` + Pydantic enum) | — | Reject bad strings at the boundary; never trust client-supplied filter values inside SQL. |
| Auth gate on dashboard endpoints | API / Backend (`Depends(get_current_user_id)`) | — | AUTH-06 single-user guard fires uniformly. |
| Per-widget caching | Browser / Client (TanStack Query) | — | `staleTime: 5min` per-query override; structural-share-based cache key from filters object. |
| URL search-param state | Browser / Client (React Router v7 `useSearchParams`) | — | DASH-06 deep-linking + refresh-safe. Default elision keeps URLs clean. |
| Filter bar UI (dropdowns + toggle) | Browser / Client (shadcn `DropdownMenu` + `ToggleGroup`) | — | Pure UI state; reads + writes via `useDashboardFilters` hook. |
| Loading skeletons | Browser / Client (shadcn `Skeleton` per-widget) | — | SHEL-06 inheritance from Phase 4 D-19 layered pattern. |
| Empty states (zero filtered postings) | Browser / Client (`<EmptyState>` from Phase 4) | — | Per-widget empty state composes Phase 4 primitive. |
| Error fallbacks per widget | Browser / Client (shadcn `Alert variant="destructive"`) | — | Per-widget error boundary; one widget erroring doesn't kill the page. |
| Salary-bar chart rendering | Browser / Client (Recharts via shadcn `chart` wrapper) | — | Theme-aware via CSS vars `--chart-1..--chart-5`. ONE chart in v1 — earns its weight here. |
| Top-skills bars (no chart lib) | Browser / Client (Tailwind-native horizontal bars) | — | Linear-dense ethos; faster to ship than configuring Recharts for a list view. |
| CV-vs-market hero number | Browser / Client (big-text Tailwind + chip list) | — | Score IS the visualization; no chart needed. |
| Top-skills "show more" modal | Browser / Client (shadcn `Dialog` + scrollable `<table>`) | — | DASH-05 drill-down. `Dialog` primitive landed in Phase 4. |
| OpenAPI tag → typed client | Build-time (`openapi-typescript` codegen) | API / Backend (explicit Pydantic response models) | Re-run `npm run codegen` after backend lands the 3 endpoints; explicit response models produce named TS schemas. |

---

## Standard Stack

### Core (additions for Phase 5)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `recharts` | 3.8.1 | Chart rendering for salary-bands `BarChart` | Pulled transitively by `npx shadcn@latest add chart`. shadcn chart wrapper uses Recharts 3.x under the hood. [VERIFIED: `npm view recharts version` → 3.8.1 on 2026-05-22; CITED: ui.shadcn.com/docs/components/chart] |
| `@radix-ui/react-toggle-group` | 1.1.11 | Underlying primitive for shadcn `ToggleGroup` | Pulled transitively by `npx shadcn@latest add toggle-group`. [VERIFIED: `npm view @radix-ui/react-toggle-group version` → 1.1.11 on 2026-05-22] |
| `@radix-ui/react-alert-dialog` (NOT alert) | n/a | Note: shadcn `alert` is a static a11y primitive (NOT a modal). No Radix dependency for the static variant; the modal version is `alert-dialog`. | Confirm at install time which file shadcn lands — for `alert` (non-modal), no Radix dep is added. [CITED: ui.shadcn.com/docs/components/alert] |

### Backend additions

**None.** Phase 5 uses already-installed `sqlalchemy>=2.x`, `asyncpg`, `pgvector`, `fastapi>=0.135`, `pydantic>=2.x`. No new `uv add` calls.

### shadcn primitives — currently installed (verified on disk 2026-05-22)

`frontend/src/components/ui/`: `badge.tsx`, `button.tsx`, `card.tsx`, `dialog.tsx`, `dropdown-menu.tsx`, `input.tsx`, `skeleton.tsx`, `sonner.tsx`.

### shadcn primitives — net-new for Phase 5

| Primitive | Install Command | What It Emits | What It Depends On |
|-----------|-----------------|---------------|--------------------|
| `alert` | `npx shadcn@latest add alert` | `frontend/src/components/ui/alert.tsx` (Alert + AlertTitle + AlertDescription) | No Radix dep — pure CVA + Tailwind. Variants: `default`, `destructive`. [VERIFIED: shadcn docs 2026-05-22] |
| `chart` | `npx shadcn@latest add chart` | `frontend/src/components/ui/chart.tsx` wrapper exporting `ChartContainer`, `ChartTooltip`, `ChartTooltipContent`, `ChartLegend`, `ChartLegendContent` + `ChartConfig` type. Adds `recharts ^3` to `package.json`. CSS vars `--chart-1` through `--chart-5` in `app.css` (theme-aware). | `recharts ^3.x` — verified Recharts 3 peer-deps `react ^16.8 || ^17 || ^18 || ^19` (compatible with current React 19.2.6). [VERIFIED: `npm view recharts peerDependencies` 2026-05-22; CITED: ui.shadcn.com/docs/components/chart] |
| `toggle-group` | `npx shadcn@latest add toggle-group` | `frontend/src/components/ui/toggle-group.tsx` (ToggleGroup + ToggleGroupItem) + `frontend/src/components/ui/toggle.tsx` (Toggle base primitive — installs together) | `@radix-ui/react-toggle-group ^1.1.11`. [VERIFIED: `npm view @radix-ui/react-toggle-group version`] |

### shadcn theme config (existing — DO NOT override)

The existing `frontend/components.json` declares:
```json
{
  "style": "radix-nova",
  "tailwind": { "css": "src/app.css", "baseColor": "neutral", "cssVariables": true },
  "iconLibrary": "lucide"
}
```

[VERIFIED: `cat frontend/components.json` 2026-05-22]

**Important:** Phase 4 RESEARCH.md and CONTEXT.md D-20 mention `new-york` / `zinc` — that nominal description does NOT match what was actually landed (`radix-nova` / `neutral`). Phase 5 installs MUST inherit the existing config silently. Do NOT pass `--style` or `--base-color` flags during `npx shadcn@latest add` — they'd potentially re-init and clobber. The deviation is benign; flagging so the planner doesn't introduce a third variant.

### React 19 + Recharts 3 peer-dep note

Recharts 3.x officially supports `react ^16.8 || ^17 || ^18 || ^19` and `react-is ^16.8 || ... || ^19` in peer deps. In some ecosystems, `react-is` resolution can produce noisy npm warnings if a transitive dep pins an older `react-is`. Current `frontend/package.json` does NOT include an explicit `react-is` override; let the planner verify that `npm install` after `add chart` doesn't produce peer-dep warnings before committing. If warnings appear, the recommended fix is adding an `overrides.react-is` block matching the installed React version. [CITED: github.com/recharts/recharts discussions/5701; medium.com — Resolving React 19 Dependency Conflicts]

### Version verification log (2026-05-22)

| Package | Source | Verified version |
|---------|--------|------------------|
| `recharts` | npm registry | 3.8.1 |
| `@radix-ui/react-toggle-group` | npm registry | 1.1.11 |
| `@radix-ui/react-alert-dialog` | npm registry (informational — NOT used by `alert`) | 1.1.15 |
| `sqlalchemy` (backend, existing) | already pinned in `pyproject.toml` | 2.x async |
| `fastapi` (backend, existing) | already pinned | 0.135.3 |

---

## Architecture Patterns

### System Architecture Diagram

```
                  ┌────────────────────────────────────────────────────┐
                  │ User on /dashboard?country=DE&seniority=senior     │
                  └─────────────────┬──────────────────────────────────┘
                                    │
                                    ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ Browser (SWA-hosted SPA)                                          │
   │                                                                   │
   │  ┌────────────────────────────────────────────┐                  │
   │  │ routes/Dashboard.tsx                       │                  │
   │  │  └─ useDashboardFilters() ◀─ URL params    │                  │
   │  │       │                                    │                  │
   │  │       ▼                                    │                  │
   │  │   ┌────────────────────────────────┐      │                  │
   │  │   │ <DashboardFilters>             │      │                  │
   │  │   │  country DropdownMenu          │      │                  │
   │  │   │  seniority DropdownMenu        │      │                  │
   │  │   │  remote ToggleGroup            │ ────── writes URL via   │
   │  │   └────────────────────────────────┘      │   setSearchParams│
   │  │       │ filters object                    │   (default elision)
   │  │       ▼                                    │                  │
   │  │   grid grid-cols-1 md:grid-cols-3 gap-4   │                  │
   │  │                                            │                  │
   │  │  ┌─────────────┐ ┌─────────────┐ ┌──────┐ │                  │
   │  │  │TopSkillsCard│ │SalaryBands  │ │CvVs  │ │                  │
   │  │  │             │ │Card         │ │Market│ │                  │
   │  │  │useQuery     │ │useQuery     │ │useQry│ │                  │
   │  │  │['dashboard',│ │['dashboard',│ │['das…│ │                  │
   │  │  │ 'top-skills'│ │ 'salary-…'  │ │ filt]│ │                  │
   │  │  │ filters]    │ │ filters]    │ │      │ │                  │
   │  │  │staleTime=5m │ │staleTime=5m │ │stale…│ │                  │
   │  │  └──────┬──────┘ └──────┬──────┘ └──┬───┘ │                  │
   │  │         │               │            │     │                  │
   │  │         ▼               ▼            ▼     │                  │
   │  │   topSkills()    salaryBands()  cvVsMkt()  │                  │
   │  │   (jobs.ts)      (jobs.ts)      (jobs.ts)  │                  │
   │  │         │               │            │     │                  │
   │  └─────────┴───────────────┴────────────┴─────┘                  │
   │            │   authedFetch (acquireTokenSilent + Bearer)         │
   │            │   3 parallel fetches                                │
   └────────────┼───────────────────────────────────────────────────────
                │
                ▼  HTTP GET /dashboard/{top-skills, salary-bands, cv-vs-market}
                │  with ?country=&seniority=&remote=  + Authorization: Bearer
                ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ ACA Container App (FastAPI)                                       │
   │                                                                   │
   │  Depends(get_current_user_id)  ─ Phase 4 D-08 oid guard           │
   │  Depends(standard_limit)       ─ 30/min                           │
   │       │                                                           │
   │       ▼                                                           │
   │  src/job_rag/api/routes.py  @router.get("/dashboard/...")         │
   │       │                                                           │
   │       ▼                                                           │
   │  src/job_rag/services/analytics.py                                │
   │   ├─ _apply_filters(stmt, country, seniority, remote)             │
   │   │   ├─ country=PL/DE: WHERE location_country = X                │
   │   │   ├─ country=EU: WHERE location_country IN EU_27              │
   │   │   │              OR location_region = 'EU'                    │
   │   │   ├─ country=WW: no filter                                    │
   │   │   ├─ seniority: WHERE seniority = X                           │
   │   │   └─ remote: WHERE remote_policy [=|IN]                       │
   │   │                                                                │
   │   ├─ top_skills():                                                │
   │   │   SELECT skill, SUM(CASE WHEN required THEN 1 ELSE 0) must,   │
   │   │     SUM(CASE WHEN NOT required THEN 1 ELSE 0) nice            │
   │   │   FROM job_requirements                                       │
   │   │   JOIN job_postings p ON ...                                  │
   │   │   WHERE skill_category != 'soft' AND <filters>                │
   │   │   GROUP BY skill ORDER BY COUNT(*) DESC LIMIT 50              │
   │   │                                                                │
   │   ├─ salary_bands():                                              │
   │   │   SELECT percentile_cont(0.25/0.5/0.75) WITHIN GROUP          │
   │   │     (ORDER BY CASE WHEN salary_period='month' THEN salary_min │
   │   │                    * 12 ELSE salary_min END ASC),             │
   │   │     COUNT(*), (filtered total)                                │
   │   │   FROM job_postings                                           │
   │   │   WHERE salary_min IS NOT NULL                                │
   │   │     AND salary_period IN ('year','month')  AND <filters>      │
   │   │                                                                │
   │   └─ cv_match():                                                  │
   │       1. SELECT * FROM job_postings p                             │
   │            JOIN selectinload(requirements) WHERE <filters>        │
   │       2. profile = load_profile(user_id=user_id)                  │
   │       3. for p in postings: score = match_posting(profile, p)     │
   │       4. mean = sum(scores) / len(scores)                         │
   │       5. Counter(missed_must_have).most_common(3)                 │
   │                                                                   │
   │  Returns Pydantic response model (named schema in OpenAPI)        │
   └───────────────────────────────────────────────────────────────────┘
                │
                ▼
   PostgreSQL Flexible Server B1ms — existing indexes:
   - ix_job_postings_location_country  (D-07 country filter)
   - ix_job_postings_seniority         (D-08 seniority filter)
   - ix_job_postings_remote_policy     (D-09 remote filter)
   - ix_job_requirements_skill_category (D-13 soft filter)
   - ix_job_requirements_skill          (top-skills GROUP BY)
```

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `analytics.top_skills(session, *, country, seniority, remote, include_soft, limit)` | `src/job_rag/services/analytics.py` (NEW) | Pure SQL GROUP BY aggregate. Returns dict with `skills`, `total_postings`, `unique_skills`. |
| `analytics.salary_bands(session, *, country, seniority, remote)` | `src/job_rag/services/analytics.py` (NEW) | `percentile_cont` aggregate with month→year normalization. Returns dict with `p25`, `p50`, `p75`, `postings_with_salary`, `total_postings`, `currency`. |
| `analytics.cv_match(session, user_id, *, country, seniority, remote)` | `src/job_rag/services/analytics.py` (NEW) | SQL pre-filter + Python fold over `match_posting`. Returns dict with `mean_score`, `postings_compared`, `top_missing_must_have`. |
| `analytics._apply_filters(stmt, *, country, seniority, remote)` | `src/job_rag/services/analytics.py` (NEW, private) | Shared filter helper that mutates a SQLAlchemy select. |
| `analytics.EU_COUNTRY_CODES: frozenset[str]` | `src/job_rag/services/analytics.py` (NEW, module-level constant) | Snapshot of EU-27 ISO-3166 alpha-2 codes; comment cites snapshot date. |
| 3 Pydantic response models | `src/job_rag/api/dashboard.py` (NEW) OR `src/job_rag/models.py` (extension) — planner discretion | `DashboardTopSkillsResponse`, `DashboardSalaryBandsResponse`, `DashboardCvMatchResponse` + nested item models (`TopSkillItem`, `MissingSkillItem`). Drives OpenAPI named schemas → openapi-typescript named TS schemas. |
| `GET /dashboard/top-skills` route handler | `src/job_rag/api/routes.py` (extension) | `tags=["dashboard"]`, `dependencies=[Depends(require_api_key), Depends(standard_limit)]`, `user_id: Annotated[uuid.UUID, Depends(get_current_user_id)]`, query params via `Query(...)` enum-validated. |
| `GET /dashboard/salary-bands` route handler | `src/job_rag/api/routes.py` (extension) | Same shape; no `user_id` actually needed but accepted for uniformity (D-03). |
| `GET /dashboard/cv-vs-market` route handler | `src/job_rag/api/routes.py` (extension) | Same shape; loads profile via `load_profile(user_id=user_id)`. |
| `Dashboard.tsx` | `frontend/src/routes/Dashboard.tsx` | Replaces existing `PhasePlaceholder` stub. Composes filter bar + 3-up grid + 3 widgets. |
| `DashboardFilters.tsx` | `frontend/src/components/dashboard/DashboardFilters.tsx` (NEW) | Filter bar UI: country `DropdownMenu` + seniority `DropdownMenu` + remote `ToggleGroup`. Reads + writes via `useDashboardFilters`. |
| `useDashboardFilters.ts` | `frontend/src/components/dashboard/useDashboardFilters.ts` (NEW) | Typed wrapper around `useSearchParams`. Default elision for `country=WW` and `remote=any`. |
| `TopSkillsCard.tsx` | `frontend/src/components/dashboard/TopSkillsCard.tsx` (NEW) | Card + Tailwind horizontal bars + "Show more" trigger + Dialog. `useQuery(['dashboard','top-skills',filters], …, { staleTime: 5*60_000 })`. |
| `SalaryBandsCard.tsx` | `frontend/src/components/dashboard/SalaryBandsCard.tsx` (NEW) | Card + Recharts `BarChart` (3 bars). Uses shadcn `chart` wrapper. CSS vars `--chart-1..3`. |
| `CvVsMarketCard.tsx` | `frontend/src/components/dashboard/CvVsMarketCard.tsx` (NEW) | Card + big-text score + chip list of top-3 missing skills. |
| `jobs.ts` (extended) | `frontend/src/api/jobs.ts` (existing stub) | Exports `topSkills(filters, signal)`, `salaryBands(filters, signal)`, `cvVsMarket(filters, signal)` — each calls `authedFetch` + casts against `openapi-typescript` types. |

### Recommended Project Structure (deltas only — Phase 4 baseline assumed)

```
src/job_rag/
├── api/
│   ├── routes.py                 # +3 handlers
│   └── dashboard.py              # NEW — Pydantic response models (or extend models.py)
└── services/
    └── analytics.py              # NEW — 3 async functions + _apply_filters + EU_COUNTRY_CODES

frontend/src/
├── api/
│   └── jobs.ts                   # fill stub: topSkills, salaryBands, cvVsMarket
├── components/
│   ├── ui/                       # NEW: alert.tsx, chart.tsx, toggle-group.tsx, toggle.tsx
│   └── dashboard/                # NEW DIR
│       ├── DashboardFilters.tsx
│       ├── TopSkillsCard.tsx
│       ├── SalaryBandsCard.tsx
│       ├── CvVsMarketCard.tsx
│       └── useDashboardFilters.ts
└── routes/
    └── Dashboard.tsx             # REPLACE PhasePlaceholder stub

tests/
└── test_analytics.py             # NEW
```

### Pattern 1: SQLAlchemy 2.x `percentile_cont().within_group(...)` for salary bands

**What:** Ordered-set aggregate function in PostgreSQL. SQLAlchemy 2.0 exposes it as `func.percentile_cont(fraction).within_group(sort_expr.asc())`. Must use `within_group()`; cannot use plain `func.percentile_cont()`.

**When to use:** server-side percentile computation. Avoids fetching all rows + computing in Python.

**Example:**
```python
# Source: docs.sqlalchemy.org/en/20/core/functions.html — percentile_cont
from sqlalchemy import case, func, select
from job_rag.db.models import JobPostingDB

# salary_period normalization: month → year via *12; drop hour rows
normalized_salary = case(
    (JobPostingDB.salary_period == "month", JobPostingDB.salary_min * 12),
    else_=JobPostingDB.salary_min,
)

stmt = select(
    func.percentile_cont(0.25).within_group(normalized_salary.asc()).label("p25"),
    func.percentile_cont(0.50).within_group(normalized_salary.asc()).label("p50"),
    func.percentile_cont(0.75).within_group(normalized_salary.asc()).label("p75"),
    func.count().label("postings_with_salary"),
).where(
    JobPostingDB.salary_min.isnot(None),
    JobPostingDB.salary_period.in_(["year", "month"]),
)
# apply filters via _apply_filters(stmt, ...)
result = await session.execute(stmt)
row = result.one()
# row.p25 may be None if no rows match — handle in caller per D-12
```

**Confidence:** HIGH — syntax cited from official docs (https://docs.sqlalchemy.org/en/20/core/functions.html#sqlalchemy.sql.functions.percentile_cont).

### Pattern 2: `case((...,1), else_=0)` + `func.sum()` GROUP BY for must/nice split

**What:** Conditional aggregation. The SQLAlchemy 2.0 `case()` import is `from sqlalchemy import case` (or `sqlalchemy.sql.expression.case`). The whens-as-tuples syntax replaces the older keyword-arg form.

**When to use:** count occurrences conditionally inside one `GROUP BY` pass.

**Example:**
```python
# Source: docs.sqlalchemy.org/en/20/core/sqlelement.html — case()
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload  # not needed here; pure aggregate

from job_rag.db.models import JobPostingDB, JobRequirementDB

stmt = (
    select(
        JobRequirementDB.skill.label("skill"),
        func.sum(
            case((JobRequirementDB.required.is_(True), 1), else_=0)
        ).label("must_count"),
        func.sum(
            case((JobRequirementDB.required.is_(False), 1), else_=0)
        ).label("nice_count"),
        func.count().label("total"),
    )
    .join(JobPostingDB, JobRequirementDB.posting_id == JobPostingDB.id)
    .where(JobRequirementDB.skill_category != "soft")  # D-13 default
    .group_by(JobRequirementDB.skill)
    .order_by(func.count().desc())
    .limit(50)
)
# apply filters via _apply_filters(stmt, ...)
result = await session.execute(stmt)
rows = result.all()
# rows: list of named tuples with skill / must_count / nice_count / total

# Sample-size counts (separate query — total_postings, unique_skills):
postings_stmt = select(func.count()).select_from(JobPostingDB)
# apply same filters
postings_count = (await session.execute(postings_stmt)).scalar_one()
```

**Confidence:** HIGH — `case()` syntax cited from https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.case; `func.sum(case(...))` is the canonical conditional aggregation pattern in PostgreSQL. Note: `JobRequirementDB.required` is `Mapped[bool]`; both `JobRequirementDB.required.is_(True)` and the shorter `JobRequirementDB.required` (truthy) work in SQLAlchemy, but `is_(True)`/`is_(False)` is clearer and lint-friendly.

### Pattern 3: Hybrid SQL fold for CV-vs-market

**What:** SQL fetches filtered postings with `selectinload(JobPostingDB.requirements)` (avoids N+1); Python loops `match_posting()` per row.

**When to use:** the aggregation is per-row and cannot be expressed in SQL (fuzzy matching, alias resolution, normalization).

**Example:**
```python
# Source: existing /gaps pattern at src/job_rag/api/routes.py lines 178-199
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from job_rag.db.models import JobPostingDB
from job_rag.services.matching import load_profile, match_posting


async def cv_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    country: str | None,
    seniority: str | None,
    remote: str | None,
) -> dict[str, Any]:
    stmt = select(JobPostingDB).options(selectinload(JobPostingDB.requirements))
    stmt = _apply_filters(stmt, country=country, seniority=seniority, remote=remote)

    result = await session.execute(stmt)
    postings = list(result.scalars().all())

    if not postings:  # D-12: HTTP 200 with empty-state body
        return {
            "mean_score": None,
            "postings_compared": 0,
            "top_missing_must_have": [],
        }

    profile = load_profile(user_id=user_id)
    scores: list[float] = []
    missing: Counter[str] = Counter()
    for p in postings:
        m = match_posting(profile, p)
        scores.append(m["score"])
        for skill in m["missed_must_have"]:
            missing[skill] += 1

    mean_score = round(sum(scores) / len(scores), 3)
    total = len(postings)
    top_3 = [
        {"skill": s, "count": c, "percentage": round(c / total * 100, 1)}
        for s, c in missing.most_common(3)
    ]
    return {
        "mean_score": mean_score,
        "postings_compared": total,
        "top_missing_must_have": top_3,
    }
```

**Confidence:** HIGH — pattern is verbatim the existing `/gaps` handler shape (cited at `src/job_rag/api/routes.py` lines 178-199); `match_posting` signature confirmed at `src/job_rag/services/matching.py` line 78; `aggregate_gaps` returns the same dict shape at line 124.

### Pattern 4: TanStack Query v5 queryKey-as-filter

**What:** Pass the filters object as part of the queryKey. TanStack Query v5 uses **structural sharing** + deep equality on queryKeys to cache identical filter combinations.

**When to use:** every filtered query — `useQuery({ queryKey: ['dashboard', 'top-skills', filters], queryFn, staleTime: 5 * 60_000 })`.

**Example:**
```typescript
// Source: tanstack.com/query/v5/docs/framework/react/guides/query-keys
import { useQuery } from '@tanstack/react-query'

import { topSkills } from '@/api/jobs'
import { useDashboardFilters } from '@/components/dashboard/useDashboardFilters'

export function TopSkillsCard() {
  const { filters } = useDashboardFilters()

  const { data, isPending, isError } = useQuery({
    queryKey: ['dashboard', 'top-skills', filters],
    queryFn: ({ signal }) => topSkills(filters, signal),
    staleTime: 5 * 60_000,  // D-22 override of Phase 4 D-Discretion 30s default
  })

  // render skeleton / empty / error / data
}
```

**Note on the cache key:** TanStack Query v5 hashes queryKeys using `JSON.stringify` with sorted object keys. As long as the filters object has stable keys (the same shape every render), identical filter combos produce identical hash keys → cache hit. If `useDashboardFilters` returns a fresh `filters` object on every render but with identical contents, the hash is still identical (structural sharing). Defensive memoization with `useMemo` is unnecessary for v5 — the key hash handles it. [CITED: tanstack.com/query/v5]

**Per-query override of global staleTime:** The Phase 4 `queryClient.ts` sets `defaultOptions.queries.staleTime: 30_000`. Passing `staleTime: 5 * 60_000` directly in `useQuery({…})` overrides the default for that query only — Phase 6's chat queries continue to use the 30s default. [VERIFIED: `frontend/src/api/queryClient.ts` 2026-05-22]

### Pattern 5: React Router v7 `useSearchParams` with default elision

**What:** Read params via `searchParams.get('key')`; write via the **updater function form** of `setSearchParams` so other params are preserved.

**When to use:** every filter dropdown / toggle. The setter receives the current `URLSearchParams` and returns a new one.

**Example:**
```typescript
// Source: reactrouter.com/api/hooks/useSearchParams
import { useSearchParams } from 'react-router'
import type { Seniority } from '@/api/types'

type Country = 'PL' | 'DE' | 'EU' | 'WW'
type Remote = 'any' | 'remote' | 'non_remote'

const DEFAULT_COUNTRY: Country = 'WW'
const DEFAULT_REMOTE: Remote = 'any'

export type DashboardFilters = {
  country: Country
  seniority: Seniority | undefined
  remote: Remote
}

export function useDashboardFilters() {
  const [params, setParams] = useSearchParams()

  const filters: DashboardFilters = {
    country: ((params.get('country') as Country | null) ?? DEFAULT_COUNTRY),
    seniority: (params.get('seniority') as Seniority | null) ?? undefined,
    remote: ((params.get('remote') as Remote | null) ?? DEFAULT_REMOTE),
  }

  function setFilters(patch: Partial<DashboardFilters>) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      // For each key in patch, either set or delete (default elision)
      if ('country' in patch) {
        if (patch.country && patch.country !== DEFAULT_COUNTRY) {
          next.set('country', patch.country)
        } else {
          next.delete('country')
        }
      }
      if ('seniority' in patch) {
        if (patch.seniority) {
          next.set('seniority', patch.seniority)
        } else {
          next.delete('seniority')
        }
      }
      if ('remote' in patch) {
        if (patch.remote && patch.remote !== DEFAULT_REMOTE) {
          next.set('remote', patch.remote)
        } else {
          next.delete('remote')
        }
      }
      return next
    })
  }

  return { filters, setFilters }
}
```

**Confidence:** HIGH — `useSearchParams` callable signature from https://reactrouter.com/api/hooks/useSearchParams. The updater function form (`setParams((prev) => …)`) is preferred over the value form when you need to preserve unrelated params. The default-elision pattern is hand-rolled (no first-class React Router API for it) but is well-established.

### Anti-Patterns to Avoid

- **Bundling /dashboard into one endpoint.** Couples latencies; one slow widget stalls the others; one widget erroring kills the page. CONTEXT.md D-01 explicitly rejects.
- **Python-side GROUP BY for top-skills.** DASH-01 wording is "no Python-side group-by". The GROUP BY is irreducibly SQL.
- **Python-side `percentile_cont`.** Fetching all `salary_min` values then computing percentiles in Python is wasteful and breaks DASH-02 wording. PostgreSQL does this server-side; use it.
- **Removing the `/gaps` endpoint to replace with `/dashboard/cv-vs-market`.** `/gaps` is consumed by Phase 6's `analyze_gaps` agent tool. Cannot remove until Phase 6 rewires. Deferred to Phase 8 cleanup if relevant.
- **Modifying `match_posting()` formula.** Phase 1 verified the 0.7 must + 0.3 nice formula; tests exist. Phase 5 reuses verbatim.
- **Hardcoding country values in TypeScript without backend matching.** The `Country` literal type in the frontend must match what the backend `Query(..., regex='^(PL|DE|EU|WW)$')` (or enum) accepts. Code-gen handles this once Pydantic uses an enum for the country parameter — recommend the planner define a `CountryFilter(StrEnum)` in the backend so OpenAPI emits a named string enum and openapi-typescript codegens a union literal type.
- **Skipping the per-widget loading skeleton.** SHEL-06 (Phase 4 D-19) layered pattern is the standard; per-widget skeletons are the third layer.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile computation in Python | Fetch all salary_min + numpy.percentile | `func.percentile_cont(...).within_group(...asc())` | Server-side; ~108 rows is small but the pattern scales. NULL-safe in PG. |
| Conditional sum aggregation | Loop in Python summing must/nice per skill | `func.sum(case((cond, 1), else_=0))` + `GROUP BY` | Single SQL pass; uses existing `ix_job_requirements_skill` index. |
| URL state hook | `useState` + `useEffect` + `history.pushState` | React Router v7 `useSearchParams` | Refresh-safe, back-button-safe, deep-link-safe. |
| Query cache for dashboard | localStorage + manual hydration | TanStack Query `staleTime: 5*60_000` | Per-query override of Phase 4 default; structural-share on filter key. |
| Bar chart for salary bands | SVG by hand | shadcn `chart` block (Recharts wrapper) | Theme-aware via CSS vars; tooltip + legend included. |
| Toggle group for remote filter | 3 buttons with manual aria-pressed | shadcn `ToggleGroup` (Radix primitive) | A11y baked in (arrow nav, aria-pressed, single-select semantics). |
| Static alert for error fallback | `<div role="alert">` | shadcn `Alert` | Variants (destructive/default) + consistent typography. |
| OpenAPI → TS types | Hand-write `types.ts` | `openapi-typescript` codegen (already wired Phase 4) | Drift-detection in CI; named schemas for free if Pydantic models are explicit. |
| EU country list | Hit ESCO/REST taxonomy API at runtime | Hardcoded `frozenset[str]` in `analytics.py` with snapshot-date comment | 108-posting corpus + 1 user; runtime lookup is overkill. |
| Skill alias resolution | Add aliases as Phase 5 surfaces them | Inherit empty `_ALIAS_GROUPS`; surface as deferred idea if duplicates seen | Per CONTEXT.md Claude's Discretion; don't expand scope. |

**Key insight:** Phase 5 is mostly about composing existing primitives — Phase 4 shipped the auth/data/UI plumbing, Phase 1-2 shipped the schema. The only net-new code is one Python module (`analytics.py`), three Pydantic response models, three React Query-consuming widgets, one filter hook, and one filter bar.

---

## EU-27 ISO Snapshot (Source-of-Truth for `analytics.py`)

As of **2026-05-22**, the EU has **27 member states**. The ISO-3166 alpha-2 codes are:

```
AT  Austria
BE  Belgium
BG  Bulgaria
HR  Croatia
CY  Cyprus
CZ  Czech Republic
DK  Denmark
EE  Estonia
FI  Finland
FR  France
DE  Germany
GR  Greece
HU  Hungary
IE  Ireland
IT  Italy
LV  Latvia
LT  Lithuania
LU  Luxembourg
MT  Malta
NL  Netherlands
PL  Poland
PT  Portugal
RO  Romania
SK  Slovakia
SI  Slovenia
ES  Spain
SE  Sweden
```

**Recommended literal for `src/job_rag/services/analytics.py`:**

```python
# Source: en.wikipedia.org/wiki/Member_state_of_the_European_Union
# (snapshot 2026-05-22; UK departed 2020-01-31; no membership change since 2023).
# Refresh this constant if EU membership changes (rare; check accession-pending
# countries list).
EU_COUNTRY_CODES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
})
```

**Note on Greece:** ISO-3166 alpha-2 is `GR`. The EU's internal protocol uses `EL` as the abbreviation for Greece, but **the corpus uses ISO-3166 codes** (per Phase 2 CORP-03 — `Location.country` is documented as "ISO-3166 alpha-2 code"). Stay on `GR`. [VERIFIED: `src/job_rag/models.py` line 60]

**EU country filter SQL:**
```python
# country == "EU" branch
stmt = stmt.where(
    or_(
        JobPostingDB.location_country.in_(EU_COUNTRY_CODES),
        JobPostingDB.location_region == "EU",  # catches D-09 NULL-country "Remote (EU)"
    )
)
```

**Confidence:** HIGH for the list (verified via en.wikipedia.org/wiki/Member_state_of_the_European_Union 2026-05-22). HIGH for the SQL pattern (mirrors Phase 2 D-09 NULL-country handling).

---

## Loading / Empty / Error Layered Pattern (D-19 inheritance from Phase 4)

Phase 4 D-19 established four SHEL-06 layers:
1. Root `<ErrorBoundary>` — global error page (catches unhandled render errors).
2. Per-route `<Suspense fallback={<RouteSkeleton/>}/>` — code-split lazy boot.
3. Per-feature loading skeletons (shadcn `Skeleton`) — `useQuery().isPending` branch.
4. Per-feature empty states (`<EmptyState>`) — zero-data branch.

Phase 5 applies layers 3 + 4 + a new per-widget error layer:

| Widget | Loading skeleton shape | Empty-state copy | Error variant |
|--------|------------------------|------------------|---------------|
| Top-skills | 8-10 horizontal bar-shaped Skeletons inside CardContent (`<Skeleton className="h-4 w-full" />` repeated, varying width to simulate sorted bars) | "No skills match these filters" | `<Alert variant="destructive">Couldn't load top skills</Alert>` |
| Salary-bands | 1 wide Skeleton inside CardContent (`<Skeleton className="h-32 w-full" />`) — the future BarChart's bounding box | "No postings with salary data match these filters" | `<Alert variant="destructive">Couldn't load salary data</Alert>` |
| CV-vs-market | 1 small Skeleton (`h-12 w-24`, the hero number) + 3 chip-list Skeletons (`h-6 w-20` each) | "No postings to compare against — try adjusting filters" | `<Alert variant="destructive">Couldn't load match score</Alert>` |

**Filter bar stays interactive in all three states** — error / empty / loading apply only to widget contents, not chrome.

**Order of branches in widget render function (canonical):**
```typescript
if (isError) return <Alert variant="destructive">…</Alert>
if (isPending) return <Skeleton …/>
if (data.total_postings === 0) return <EmptyState …/>
return <ActualContent data={data} />
```

[CITED: `frontend/src/components/EmptyState.tsx` already exists from Phase 4]

---

## Test Data Strategy

`tests/conftest.py` already defines:
- `sample_posting: JobPosting` Pydantic fixture (Berlin, hybrid, €70k-€90k, senior, 5 must-haves + 3 nice-to-haves — mixed `SkillType`). [VERIFIED: `tests/conftest.py` lines 27-97]

**Recommendation for Phase 5 backend tests:**
- **Unit tests for `analytics.py` functions** (in-memory fixture postings, not the dev DB):
  - Define `dashboard_postings_factory` fixture in `tests/conftest.py` that creates a list of `JobPostingDB` ORM instances with **country/seniority/salary variety**: e.g., 5 DE postings (3 with salary, 2 NULL), 3 PL postings, 2 region="EU" / country=NULL, 1 region="Worldwide", varied seniority (junior/mid/senior/staff), varied salary_period (year/month/hour to test normalization). Build via the existing `sample_posting` Pydantic shape mapped to `JobPostingDB` rows.
  - Each test seeds the in-memory async session, calls the analytics function, asserts the dict shape + values.
- **Integration tests for `/dashboard/*` endpoints** (use FastAPI `TestClient`/`AsyncClient` with mocked sessions, mirroring `tests/test_api.py` `TestMatchEndpoint` / `TestGapsEndpoint` shape). Mock the analytics function return value; assert auth gate fires, response shape matches Pydantic model.
- **DO NOT** rely on the 98 dev DB postings for unit tests (non-reproducible — corpus changes break tests). CONTEXT.md Claude's Discretion says "use existing 98 reextracted postings" — interpret as "manual verification only, not unit-test seed."

**Recommendation for Phase 5 frontend tests:**
- **Component tests** (`*.test.tsx` colocated with components): mock `useQuery` return shapes (`isPending`/`isError`/`data`), assert correct branch renders (Skeleton/Alert/EmptyState/data).
- **Hook test for `useDashboardFilters`**: render hook in test with `MemoryRouter`; assert default elision (writing `country: 'WW'` removes the param; writing `country: 'PL'` adds it).
- Use existing Vitest + RTL setup from Phase 4. No new test tooling.

---

## Pydantic Response Models (recommendation)

**File placement:** `src/job_rag/api/dashboard.py` (NEW). Rationale: `src/job_rag/models.py` is the domain models file (JobPosting / JobRequirement / Location / Seniority / RemotePolicy / SalaryPeriod / UserSkillProfile); adding API response models there mixes domain + transport. The `api/` subpackage already contains `routes.py`, `auth.py`, `deps.py`, `sse.py` — adding `api/dashboard.py` keeps API-layer concerns colocated.

**Suggested shape:**

```python
# src/job_rag/api/dashboard.py
from pydantic import BaseModel


class TopSkillItem(BaseModel):
    skill: str
    must_count: int
    nice_count: int
    total: int


class DashboardTopSkillsResponse(BaseModel):
    skills: list[TopSkillItem]
    total_postings: int
    unique_skills: int


class DashboardSalaryBandsResponse(BaseModel):
    p25: int | None
    p50: int | None
    p75: int | None
    postings_with_salary: int
    total_postings: int
    currency: str = "EUR"


class MissingSkillItem(BaseModel):
    skill: str
    count: int
    percentage: float


class DashboardCvMatchResponse(BaseModel):
    mean_score: float | None  # None when postings_compared == 0 (D-12)
    postings_compared: int
    top_missing_must_have: list[MissingSkillItem]
```

**openapi-typescript codegen result:** Each Pydantic class becomes a named TS interface in `frontend/src/api/types.ts`. `paths["/dashboard/top-skills"]["get"]["responses"]["200"]["content"]["application/json"]` resolves to `components["schemas"]["DashboardTopSkillsResponse"]`. The frontend imports these named types from `@/api/types` rather than inlining shapes. [VERIFIED: openapi-ts.dev/introduction]

**Filter parameter validation:**
```python
# src/job_rag/api/dashboard.py — Pydantic-validated query enums

from enum import StrEnum


class CountryFilter(StrEnum):
    PL = "PL"
    DE = "DE"
    EU = "EU"
    WW = "WW"


class RemoteFilter(StrEnum):
    ANY = "any"
    REMOTE = "remote"
    NON_REMOTE = "non_remote"


# Seniority filter uses existing Seniority enum from src/job_rag/models.py
```

Each route handler then takes:
```python
async def top_skills_route(
    session: Session,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    country: CountryFilter = CountryFilter.WW,
    seniority: Seniority | None = None,
    remote: RemoteFilter = RemoteFilter.ANY,
    include_soft: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> DashboardTopSkillsResponse: ...
```

FastAPI's enum-typed Query produces a 422 for invalid values; OpenAPI emits the enum as a named schema with `enum: [...]`; openapi-typescript renders it as a TypeScript union literal type. End-to-end type safety.

---

## Cold-Start ACA Caveat (carry-forward, not a Phase 5 fix)

Per memory `aca-cold-start-profile.md`: ScaledToZero → first byte ≈ **225s** on this image; warm latency ≈ **0.2s**. Dashboard mounts 3 parallel widget fetches; the first user-visit-after-idle hits the cold start once (shared across the 3 fetches), not 3×.

**Phase 5 mitigation:** none — Phase 5 doesn't change infrastructure.
**Phase 5 documentation:** add a one-line callout in the Phase 5 close-out SUMMARY or a README note: "First dashboard load after the container has scaled to zero takes ~3-4 minutes (ACA cold-start); subsequent requests are <1s. This is intentional — `min_replicas=0` keeps the project at €0/mo. Phase 8 portfolio polish may revisit."

**Phase 8 candidate:** flip `min_replicas=1` (~€8/mo) for portfolio-demo reliability. Out of v1 budget; tracked as Deferred Idea.

[CITED: `~/.claude/projects/-Users-adrian-Developer-job-rag/memory/aca-cold-start-profile.md`]

---

## Pitfalls

### Pitfall 1: `func.percentile_cont(...)` without `.within_group(...)`

**Severity:** HIGH. **Mitigation:** ALWAYS chain `.within_group(<sort_expr>.asc())`. Calling `func.percentile_cont(0.5)` alone produces a SQL error at execution (`percentile_cont(double precision) function does not exist` — PostgreSQL requires the ordered-set form). [CITED: docs.sqlalchemy.org/en/20/core/functions.html#sqlalchemy.sql.functions.percentile_cont]

### Pitfall 2: `percentile_cont` over an empty result set

**Severity:** MEDIUM. **What goes wrong:** if `WHERE salary_min IS NOT NULL AND <filters>` matches zero rows, `percentile_cont` returns NULL for each percentile. The Pydantic response model declares `p25/p50/p75: int | None` precisely so this case round-trips cleanly. **Mitigation:** in the analytics function, check `if row.postings_with_salary == 0: return zero-state` dict before returning percentile values; or accept NULLs and let the frontend render the empty state. Recommend the latter — fewer branches.

### Pitfall 3: `salary_period = 'hour'` rows leaking into percentiles

**Severity:** MEDIUM. **What goes wrong:** the corpus has hourly contract postings (e.g., €40/hr). If included unfiltered, they pull p25 far below salaried postings. **Mitigation:** the `WHERE salary_period IN ('year','month')` filter is mandatory; document in code comment that hourly rows are intentionally excluded (deferred idea: normalize via assumption-based hours/week multiplier).

### Pitfall 4: `salary_min * 12` integer overflow

**Severity:** LOW. **What goes wrong:** PostgreSQL `integer` is 32-bit; multiplying a 200k EUR/month value by 12 = 2.4M — fits comfortably. No overflow risk for realistic salaries. Document but don't guard.

### Pitfall 5: `case()` import path confusion

**Severity:** LOW. **What goes wrong:** SQLAlchemy 1.x had `case()` taking a list of whens via the `whens=[(cond, val), ...]` keyword arg. SQLAlchemy 2.x uses positional tuples: `case((cond, val), ..., else_=...)`. Old tutorials and Stack Overflow answers may show the 1.x form. **Mitigation:** import from `sqlalchemy` (not `sqlalchemy.sql`); use the positional tuple form. [CITED: docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.case]

### Pitfall 6: TanStack Query cache key with new filter object reference on every render

**Severity:** LOW. **What goes wrong:** if `useDashboardFilters` returns a fresh `filters` object on every render (which it likely does — it reads from `useSearchParams` which is reactive), TanStack Query still produces an identical hash key because it uses deep JSON-based hashing. **No bug**, but a developer used to other libraries (Apollo, SWR) may add `useMemo` defensively. Recommend the planner explicitly note "no `useMemo` needed — TanStack Query v5 deep-hashes the key" so reviewers don't add it. [CITED: tanstack.com/query/v5/docs/framework/react/guides/query-keys]

### Pitfall 7: Recharts 3 + React 19 peer-dep warnings

**Severity:** LOW. **What goes wrong:** Recharts 3 declares `react-is ^16.8 || ... || ^19` in peer deps. npm install may produce noisy warnings about React 19 / react-is version mismatch (transitive resolution can be off-by-one). **Mitigation:** if warnings appear after `npx shadcn@latest add chart`, add an `overrides` block in `package.json`:
```json
"overrides": {
  "react-is": "$react"
}
```
This pins `react-is` to the same version as `react`. Verify with `npm ls react-is` post-install. [CITED: github.com/recharts/recharts discussions/5701; medium.com/@zachshallbetter — Resolving React 19 Dependency Conflicts]

### Pitfall 8: shadcn `add` with explicit `--style` flag clobbering existing `components.json`

**Severity:** HIGH. **What goes wrong:** Phase 4 RESEARCH.md describes `style=new-york`/`zinc`; actual `components.json` is `style=radix-nova`/`baseColor=neutral`. If the planner adds `--style new-york --base-color zinc` flags to the install command, shadcn may rewrite `components.json` and emit primitives styled inconsistently with already-installed ones. **Mitigation:** install with **bare command** `npx shadcn@latest add alert chart toggle-group` (no style flags); shadcn reads `components.json` and inherits. [VERIFIED: `frontend/components.json` 2026-05-22]

### Pitfall 9: EU=EU returns same numbers as country=WW when corpus is EU-only

**Severity:** MEDIUM (test/UX edge case). **What goes wrong:** if the corpus happens to be 100% EU postings (e.g., Adrian only ingested European listings), country=EU and country=WW will return identical numbers — the "different numbers per country" success criterion fails for that pair. **Mitigation:** verify the dev DB has at least one non-EU posting (e.g., US, UK post-Brexit). Document in the Phase 5 close-out runbook as a manual check. If the corpus is genuinely EU-only, surface to Adrian as "expand the corpus" or "consider hiding the WW option."

### Pitfall 10: Default elision creates filter-toggle UX confusion

**Severity:** LOW. **What goes wrong:** user selects `country=WW`, URL strips the param (default elision), shows `/dashboard`. User then refreshes and the dropdown correctly reads default state. BUT: if user had `country=PL`, then explicitly selects `WW` (the default), the URL drops the `country` param and the dropdown may briefly flicker. **Mitigation:** dropdown defaultValue reads from `filters.country` (always populated); the URL is decoration for share-ability, not state of truth. Filter bar is non-flickering as long as `filters` is the source.

### Pitfall 11: Soft skills leaking into top-skills despite filter

**Severity:** LOW (defense-in-depth). **What goes wrong:** Phase 2's REJECTED_SOFT_SKILLS prompt filter already removes soft skills at extraction time, BUT a few may slip through (e.g., "communication" labeled as `concept` instead of `soft_skill`). The `WHERE skill_category != 'soft'` filter catches the labeled ones; mislabeled ones leak. **Mitigation:** spot-check top-50 result after the first live run; if leak observed, surface to a Phase 2-rev (not Phase 5).

### Pitfall 12: `_ALIAS_GROUPS` empty → "AWS" and "Amazon Web Services" double-counted

**Severity:** LOW (defense-in-depth). **What goes wrong:** if the corpus has both literal strings, top-skills shows them as separate rows. **Mitigation:** per CONTEXT.md Claude's Discretion, treat as a deferred phase if it surfaces. Phase 5 does NOT populate aliases. Document in the close-out runbook.

### Pitfall 13: ACA cold-start UX with 3 parallel widget fetches

**Severity:** LOW (UX, not correctness). **What goes wrong:** first dashboard load after idle takes ~225s, with the 3 widgets all in `isPending` state. Per-widget Skeletons render correctly, but a 3-4 minute wait may look broken. **Mitigation:** Phase 5 close-out documentation, not code change. Phase 8 may revisit cold-start mitigation.

### Pitfall 14: `selectinload(JobPostingDB.requirements)` N+1 trap in `cv_match`

**Severity:** MEDIUM. **What goes wrong:** if the planner forgets `selectinload`, `match_posting(profile, p)` accesses `p.requirements` lazily, triggering a SELECT per posting. With 108 postings, that's 108 queries instead of 2 (one for postings + one for requirements). **Mitigation:** the existing `/gaps` handler uses `selectinload` explicitly (`src/job_rag/api/routes.py` line 186); Phase 5 `cv_match` follows the same pattern. Recommend the planner cite the line number in the task description so the reviewer can compare.

### Pitfall 15: 3 widgets fail to load if backend has 1 endpoint broken

**Severity:** MEDIUM. **What goes wrong:** the React Query keys are independent, so a failure in one endpoint doesn't kill the others — but if all 3 endpoints share a backend bug (e.g., `_apply_filters` raises on `country=EU` due to a typo), all 3 widgets show Alert. **Mitigation:** explicit unit tests on `_apply_filters` (with country=EU exercising both `IN <list>` and `OR region='EU'`); explicit test on the EU country filter against fixtures. Integration test: each of the 3 endpoints, with each of the 4 country values, returns 200 OK with shape-valid Pydantic.

### Pitfall 16: Missing `tags=["dashboard"]` → unnamed OpenAPI operation IDs

**Severity:** LOW. **What goes wrong:** without `tags=["dashboard"]` on each route, FastAPI emits operation IDs like `top_skills_dashboard_top_skills_get`, and openapi-typescript groups everything under a flat `paths` map. **Mitigation:** add `tags=["dashboard"]` on each `@router.get(...)` so the codegen-typed client has clean grouping; also helps the OpenAPI Swagger UI organize the endpoints visually.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ + pytest-asyncio (existing) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_analytics.py -x` |
| Full suite command | `uv run pytest -x` |
| Frontend test | `cd frontend && npm test` (Vitest 3.x, already configured) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | Top-skills SQL aggregation, must/nice split, soft hidden by default, country/seniority/remote filter applied | unit | `pytest tests/test_analytics.py::TestTopSkills -x` | ❌ Wave 0 |
| DASH-01 | OpenAPI exposes `/dashboard/top-skills` with named `DashboardTopSkillsResponse` schema | integration | `pytest tests/test_api.py::TestDashboardEndpoints::test_top_skills_openapi_shape -x` | ❌ Wave 0 |
| DASH-01 | Top-skills widget renders 8-10 hard skills with must/nice bars | unit (frontend) | `cd frontend && npm test -- TopSkillsCard` | ❌ Wave 0 |
| DASH-02 | `percentile_cont` returns p25/p50/p75 with month→year normalization; NULL handling on empty result | unit | `pytest tests/test_analytics.py::TestSalaryBands -x` | ❌ Wave 0 |
| DASH-02 | Salary-bands widget renders Recharts `BarChart` with 3 bars | unit (frontend) | `cd frontend && npm test -- SalaryBandsCard` | ❌ Wave 0 |
| DASH-02 | Sample-size footnote "{n} of {m} postings had salary data" renders | unit (frontend) | `cd frontend && npm test -- SalaryBandsCard.footnote` | ❌ Wave 0 |
| DASH-03 | `cv_match` returns mean_score / postings_compared / top_3_missing using `match_posting` formula | unit | `pytest tests/test_analytics.py::TestCvMatch -x` | ❌ Wave 0 |
| DASH-03 | Zero-postings filter returns HTTP 200 + `{mean_score: null, ...}` (D-12) | unit | `pytest tests/test_analytics.py::TestCvMatch::test_empty_filter_returns_200 -x` | ❌ Wave 0 |
| DASH-03 | CV-vs-market widget renders big-text score + chip list of missing skills | unit (frontend) | `cd frontend && npm test -- CvVsMarketCard` | ❌ Wave 0 |
| DASH-04 | Dashboard page renders 3 widgets in `grid grid-cols-3` on desktop; stacked on mobile | unit (frontend) | `cd frontend && npm test -- Dashboard.layout` | ❌ Wave 0 |
| DASH-04 | Filter bar shows country dropdown (4 values), seniority dropdown, remote ToggleGroup | unit (frontend) | `cd frontend && npm test -- DashboardFilters` | ❌ Wave 0 |
| DASH-04 | Country filter actually changes SQL — distinct numbers for PL/DE/EU/WW | integration | `pytest tests/test_analytics.py::TestFilterEffects::test_country_filter_changes_results -x` | ❌ Wave 0 |
| DASH-05 | Top-skills "show more" opens Dialog with full ranked list (limit=50) | unit (frontend) | `cd frontend && npm test -- TopSkillsCard.showMore` | ❌ Wave 0 |
| DASH-06 | `/dashboard?country=DE&seniority=senior` deep-link pre-populates filters | unit (frontend) | `cd frontend && npm test -- useDashboardFilters.deepLink` | ❌ Wave 0 |
| DASH-06 | Default elision: selecting country=WW removes the param from URL | unit (frontend) | `cd frontend && npm test -- useDashboardFilters.elision` | ❌ Wave 0 |
| DASH-06 | Refresh on `/dashboard?country=DE` preserves filter state | manual (UAT) | Live verification in close-out runbook | n/a |
| SHEL-03 | All 3 widgets use `useQuery` with `staleTime: 5*60_000` | unit (frontend) | `cd frontend && npm test -- *Card.staleTime` | ❌ Wave 0 |
| SHEL-06 | Each widget renders Skeleton on isPending, EmptyState on zero data, Alert on isError | unit (frontend) | `cd frontend && npm test -- *Card.states` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_analytics.py -x` (backend tasks) OR `cd frontend && npm test --run -- <touched-file>` (frontend tasks).
- **Per wave merge:** `uv run pytest -x && cd frontend && npm test --run` (full suite both sides).
- **Phase gate:** Full suite green + manual UAT runbook (3 widgets render with real data, different numbers per country, deep-link works, default elision works, theme toggle still works) before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_analytics.py` — covers DASH-01..03 backend logic (TestTopSkills, TestSalaryBands, TestCvMatch, TestApplyFilters, TestEuCountrySetMembership)
- [ ] `tests/test_api.py` — extend with `TestDashboardEndpoints` class mirroring `TestMatchEndpoint`/`TestGapsEndpoint` patterns (auth gate fires, response shape valid, 3 country values exercise filter)
- [ ] `tests/conftest.py` — extend with `dashboard_postings_factory` fixture (DE/PL/EU/WW + salary/no-salary + seniority variety + skill_category variety)
- [ ] `frontend/src/components/dashboard/*.test.tsx` — Vitest + RTL component tests per widget (loading / empty / error / data branches)
- [ ] `frontend/src/components/dashboard/useDashboardFilters.test.ts` — hook test with `MemoryRouter` (deep-link reading, default elision writing)

*(No framework install needed — Vitest + RTL + pytest already configured Phase 1/4.)*

### Edge Cases to Cover Explicitly

| Edge case | Test surface | Why it matters |
|-----------|--------------|----------------|
| Empty filter result (country=PL + seniority=staff returns 0 postings) | backend + frontend | D-12 zero-postings contract; per-widget EmptyState branch |
| NULL `location_country` posting (region="EU" / region="Worldwide") | backend | D-07 EU branch checks region; D-09 corpus shape |
| NULL `salary_min` posting | backend | DASH-02 footnote requires accurate `postings_with_salary` count |
| `salary_period='hour'` row | backend | must be excluded from percentiles per Claude's Discretion |
| `salary_period='month'` row | backend | must be normalized × 12 |
| `skill_category='soft'` row | backend | must be excluded from top-skills by default |
| `?include_soft=true` query | backend | accepted, returns soft skills included |
| Default elision write: country=WW deletes param | frontend hook | URL stays clean |
| Default elision read: missing param → WW default | frontend hook | refresh-safe |
| 3 widgets fail independently | frontend | per-widget Alert, others still render |
| `EU=PL+DE+...all-27` returns same numbers as `WW` when corpus is EU-only | backend (manual check) | corpus distribution sanity |
| Currency assumption: USD/GBP salary treated as EUR | documentation only | known limitation |
| `_ALIAS_GROUPS` empty → AWS / Amazon Web Services double-count | documentation only | surface deferred idea if observed |

---

## Out of Scope

Listed verbatim from CONTEXT.md `<deferred>` block, plus additional research-time exclusions:

- Interactive cross-filtering (v2 DASH2-01).
- Skill co-occurrence view (v2 DASH2-02).
- Time-series trends (v2 DASH2-03).
- Per-posting drill-down pages (v2 DASH2-04).
- "Show soft skills" UI toggle.
- Skill alias population.
- Dynamic country dropdown from `SELECT DISTINCT location_country`.
- Hourly salary normalization.
- Currency / FX normalization.
- Pagination beyond 50 skills.
- Widget reorder / drag-and-drop.
- Export to CSV/PNG.
- Always-warm ACA (`min_replicas=1` ≈ €8/mo) — out of v1 budget.
- Replacing `/gaps` with `/dashboard/cv-vs-market` — Phase 6 agent dependency.
- Phase 04.1 follow-ups (parallel, no dependency).
- Soft-skill UI toggle.
- Backend `analytics.py` populating `_ALIAS_GROUPS` (Phase 1 D-12 inherited empty).
- New backend frameworks (frozen stack).
- New frontend top-level deps beyond `recharts` (transitive via shadcn) + `@radix-ui/react-toggle-group` (transitive via shadcn).
- Infrastructure changes (no Terraform, no migrations, no Container App env vars).
- Phase 5 fixing the ACA cold-start UX (Phase 8 candidate).
- Multi-user support (every endpoint accepts `user_id` but query bodies ignore it in v1).

---

## Open Questions

> Questions the **planner** must resolve in PLAN.md, NOT the user. All are research-blocked because the answer depends on CONTEXT-locked decisions plus Phase-5-specific call-site shape that the planner formalizes.

### Q1: Should the 3 endpoints share one `DashboardFiltersDep` Pydantic Query model, or declare params per endpoint?

**Options:**
- (a) Three endpoints each declare `country`, `seniority`, `remote` as separate Query params (DRY violation, easier to read).
- (b) Define a `DashboardFilters(BaseModel)` Pydantic model with the three fields, and use FastAPI's "Query model" feature: `filters: Annotated[DashboardFilters, Query()]`. All 3 endpoints take it as a single dep.

**Recommendation:** **(a) per-endpoint Query params** for v1. Reasons: (i) only 3 fields each; (ii) `include_soft` and `limit` are top-skills-only — bundling makes the shared model awkward; (iii) per-endpoint declaration emits cleaner OpenAPI for openapi-typescript. Revisit if a 4th endpoint joins.

### Q2: Should Pydantic response models live in `src/job_rag/api/dashboard.py` (NEW) or extend `src/job_rag/models.py`?

**Recommendation:** **NEW file `src/job_rag/api/dashboard.py`.** Rationale: `models.py` is for domain models (JobPosting, JobRequirement, Location, enums); API response models are transport. Existing convention in `src/job_rag/api/sse.py` (Phase 1) already establishes "API-specific Pydantic models live under api/." Follow that.

### Q3: Should EU-27 list be a Python `frozenset` literal or a Postgres ENUM/lookup table?

**Recommendation:** **`frozenset` literal in `analytics.py`** (per CONTEXT.md Claude's Discretion). Reasons: (i) zero runtime DB cost; (ii) atomic snapshot — git diff shows membership change; (iii) Postgres ENUM would require an Alembic migration on every change, defeating the rare-update advantage of a literal; (iv) lookup table is overkill at 27 entries with rare changes.

### Q4: Where does `useDashboardFilters` hook live — `frontend/src/components/dashboard/` or `frontend/src/hooks/`?

**Recommendation:** **`frontend/src/components/dashboard/useDashboardFilters.ts`** (per CONTEXT.md D-17). Reason: feature-folder cohesion — the hook is dashboard-specific. If Phase 6 chat or Phase 7 profile needs the same filter shape, refactor up to `frontend/src/hooks/` at that point. No `hooks/` directory exists today; don't create one preemptively.

### Q5: Should the cold-start documentation live in Phase 5 close-out SUMMARY, README.md, or both?

**Recommendation:** **Phase 5 close-out SUMMARY only** (one line: "First dashboard load after idle takes ~3-4 minutes due to ACA cold-start; subsequent requests <1s. See Phase 8 for portfolio polish considerations."). Don't touch README.md — that's Phase 8 DOCS-01 scope.

### Q6: Should the `?limit=` param on top-skills be exposed in the frontend or hardcoded to 50?

**Recommendation:** **Hardcoded to 50 in the frontend** for v1 (the modal shows 50, the card shows top-10). Param remains tunable for future flexibility. If Adrian wants different behavior later, change the frontend literal.

### Q7: Should the route handlers all share a `DashboardSession = Annotated[AsyncSession, Depends(get_session)]` alias, or each declare `session: Session`?

**Recommendation:** **Inherit existing `Session = Annotated[AsyncSession, Depends(get_session)]` alias** from `src/job_rag/api/routes.py` line 60. Adding a new alias for one phase fragments style. Keep one alias.

### Q8: Should the `cv_match` mean_score be rounded server-side (3 decimals) or client-side?

**Recommendation:** **Server-side, 3 decimals**, matching the existing `match_posting()` output convention (`round(score, 3)` at line 113 of `matching.py`). Frontend formats display with 2 decimals (D-23 — `0.42` style). Server returns the precise value; frontend chooses display precision.

---

## Sources

### Primary (HIGH confidence)
- [SQLAlchemy 2.0 — SQL and Generic Functions (`percentile_cont` + `within_group`)](https://docs.sqlalchemy.org/en/20/core/functions.html)
- [SQLAlchemy 2.0 — SQL Element (`case()` positional whens)](https://docs.sqlalchemy.org/en/20/core/sqlelement.html)
- [shadcn/ui — Chart](https://ui.shadcn.com/docs/components/chart) — `npx shadcn@latest add chart`, ChartContainer/Tooltip/Legend exports, CSS vars
- [shadcn/ui — Alert](https://ui.shadcn.com/docs/components/alert)
- [shadcn/ui — Toggle Group](https://ui.shadcn.com/docs/components/toggle-group)
- [React Router v7 — useSearchParams](https://reactrouter.com/api/hooks/useSearchParams) — tuple return, setter shape
- [TanStack Query v5 — Query Keys](https://tanstack.com/query/v5/docs/framework/react/guides/query-keys) — deep-hash, structural sharing
- [openapi-typescript — Introduction](https://openapi-ts.dev/introduction) — named schema codegen from Pydantic
- [Wikipedia — Member state of the European Union](https://en.wikipedia.org/wiki/Member_state_of_the_European_Union) — EU-27 list snapshot 2026-05
- [PostgreSQL — Aggregate Functions (`percentile_cont`)](https://www.postgresql.org/docs/current/functions-aggregate.html) — ordered-set aggregate semantics

### Secondary (MEDIUM confidence — single source / community)
- [Recharts discussions — react-is peer-dep handling on React 19](https://github.com/recharts/recharts/discussions/5701)
- [Medium — Resolving React 19 Dependency Conflicts](https://medium.com/@zachshallbetter/resolving-react-19-dependency-conflicts-without-downgrading-ee0a808af2eb)
- [LogRocket — useSearchParams URL state guide](https://blog.logrocket.com/url-state-usesearchparams/)
- [Robin Wieruch — React Router 7 search params](https://www.robinwieruch.de/react-router-search-params/)
- [GitHub Discussion — typed searchParams and partial updates](https://github.com/remix-run/react-router/discussions/11180)
- [Leafo — PostgreSQL percentile calculation](https://leafo.net/guides/postgresql-calculating-percentile.html)

### Tertiary (LOW confidence — informational only)
- [SQLAlchemy issue #11423 — within_group + filter combo](https://github.com/sqlalchemy/sqlalchemy/issues/11423) — for the planner if future v2 wants conditional percentile aggregation
- [Mantine issue #7356 — recharts + React 19 peer warning](https://github.com/mantinedev/mantine/issues/7356)

### Codebase references (VERIFIED in this session)
- `src/job_rag/db/models.py` lines 11-80 — JobPostingDB + JobRequirementDB schema + indexes
- `src/job_rag/models.py` lines 25-89 — SkillCategory, Seniority, RemotePolicy, SalaryPeriod enums
- `src/job_rag/services/matching.py` lines 14-122 — `load_profile`, `match_posting`, `aggregate_gaps`
- `src/job_rag/services/retrieval.py` lines 69-99 — `selectinload(JobPostingDB.requirements)` pattern
- `src/job_rag/api/routes.py` lines 99-200 — endpoint decorator + dep injection pattern
- `src/job_rag/api/auth.py` lines 59-153 — `get_current_user_id`, `standard_limit`, `require_api_key`
- `src/job_rag/api/deps.py` — `get_session` async session dep
- `frontend/package.json` — Vite 8.0.12, React 19.2.6, TS 5.9, TanStack Query 5.100.11, React Router 7.15.1
- `frontend/components.json` — `style=radix-nova`, `baseColor=neutral`, `iconLibrary=lucide` (NOT new-york/zinc as Phase 4 RESEARCH.md said)
- `frontend/src/App.tsx` — `/dashboard` already lazy-loaded under AuthGate/AppShell
- `frontend/src/api/queryClient.ts` — 30s staleTime default (Phase 5 overrides per-query)
- `frontend/src/api/authedFetch.ts` — Bearer interceptor + 401 retry + signal threading
- `frontend/src/api/jobs.ts` — current stub
- `frontend/src/routes/Dashboard.tsx` — current PhasePlaceholder stub
- `frontend/src/components/ui/` — installed: badge, button, card, dialog, dropdown-menu, input, skeleton, sonner
- `tests/conftest.py` lines 27-97 — `sample_posting` Pydantic fixture (DE / Berlin / hybrid / senior / 5 must + 3 nice)
- `tests/test_api.py` — `TestMatchEndpoint`, `TestGapsEndpoint` pattern Phase 5 mirrors
- `~/.claude/projects/-Users-adrian-Developer-job-rag/memory/aca-cold-start-profile.md` — measured ~225s cold-start

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package version verified against the live npm/PyPI registry on 2026-05-22.
- SQL patterns (`percentile_cont`, `case()`, `func.sum()`, `selectinload` fold): HIGH — syntax cited from official SQLAlchemy 2.0 docs.
- React Router v7 + TanStack Query patterns: HIGH — cited from official docs + the existing Phase 4 implementation.
- shadcn primitives (`alert`, `chart`, `toggle-group`): HIGH — install behavior cited from ui.shadcn.com; existing `components.json` verified on disk.
- EU-27 ISO snapshot: HIGH — list verified against en.wikipedia.org/wiki/Member_state_of_the_European_Union (no changes since UK departure 2020).
- Pitfalls (Recharts peer dep, shadcn style flag, default elision UX): MEDIUM — community-sourced; recommended mitigations verified-by-pattern but not field-tested in this codebase.
- Test data strategy: HIGH — `tests/conftest.py` `sample_posting` fixture confirmed on disk.
- ACA cold-start propagation: HIGH — cited from memory file with measured numbers; Phase 5 explicitly does NOT mitigate.

**Research date:** 2026-05-22
**Valid until:** 2026-06-21 (30 days — stack is stable, no fast-moving libraries except possibly shadcn CLI minor bumps)

**Anti-scope creep boundary (re-affirmed):**
- NO infrastructure changes (no Terraform, no Container App env vars, no migrations)
- NO agent modifications (Phase 6 owns it)
- NO matching/retrieval redesign — `match_posting`, `_skill_matches`, `_ALIAS_GROUPS` all inherited verbatim
- NO new backend libraries — `analytics.py` uses only already-installed sqlalchemy / pydantic / fastapi
- NO new frontend top-level deps beyond the 3 shadcn primitives (`alert`, `chart`, `toggle-group`) — transitive `recharts ^3` + `@radix-ui/react-toggle-group` only
