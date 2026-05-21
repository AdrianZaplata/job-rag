# Phase 5: Dashboard - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning
**Mode:** Auto-resolved (background session; user-locked "Recommended" pattern 20/20 across Phase 4)

<domain>
## Phase Boundary

Phase 5 ships the first shareable surface when the `/dashboard` route renders three
analytical widgets under one shared filter bar, with filter state round-tripping through
URL search params:

1. **Top skills widget** — Top 8-10 hard skills (soft skills hidden by default via
   `SkillCategory` filter) with a must-have / nice-to-have split; "show more" expands
   to the full ranked list. (DASH-01, DASH-05)
2. **Salary bands widget** — p25 / p50 / p75 computed server-side via PostgreSQL
   `percentile_cont`, with a "N of M postings had salary data" footnote. (DASH-02)
3. **CV-vs-market widget** — Aggregate match score (mean of per-posting scores across
   the filtered set) plus top 3 missing must-have skills. (DASH-03)

Shared filter bar = country dropdown (Poland / Germany / EU / Worldwide), seniority
select, remote toggle. State syncs to URL search params; deep-linking and refresh-safe.
(DASH-04, DASH-06)

**In scope:**
- 3 new FastAPI analytical endpoints under `/dashboard/*`, all server-side SQL aggregation
- 1 new backend service module `src/job_rag/services/analytics.py`
- Dashboard React page at `frontend/src/routes/Dashboard.tsx` (replaces placeholder)
- Filter bar component, 3 widget components, shared filter hook
- TanStack Query wiring with per-widget caching
- Per-widget loading skeletons, empty states, error fallbacks
- One chart library install (shadcn `chart` / Recharts) for salary-bands only

**Out of scope (later phases):**
- Chat streaming + tool-call chips (Phase 6 — Phase 4 already shipped `readSSEStream`)
- Resume upload + profile review (Phase 7 — Phase 5 reads profile via existing
  `load_profile()`; Phase 7 will flip its body to DB)
- Interactive cross-filtering charts (v2 — DASH2-01)
- Skill co-occurrence view (v2 — DASH2-02)
- Time-series trends (v2 — DASH2-03)
- Per-posting drill-down pages (v2 — DASH2-04)
- "Show soft skills" UI toggle (deferred — corpus already filtered at extraction)

</domain>

<decisions>
## Implementation Decisions

### A. Backend endpoint architecture

- **D-01: Three independent analytical endpoints under `/dashboard/*`.**
  - `GET /dashboard/top-skills?country=&seniority=&remote=&include_soft=false&limit=50` → `{ skills: [{skill, must_count, nice_count, total}], total_postings, unique_skills }`
  - `GET /dashboard/salary-bands?country=&seniority=&remote=` → `{ p25, p50, p75, postings_with_salary, total_postings, currency: "EUR" }`
  - `GET /dashboard/cv-vs-market?country=&seniority=&remote=` → `{ mean_score, postings_compared, top_missing_must_have: [{skill, count, percentage}] }`

  Rationale: each widget caches/fails/loads independently. Three React Query keys fetch
  in parallel; one slow widget can't stall the others; per-widget error boundaries make
  sense. A bundled `/dashboard` endpoint would couple latencies and force the slowest
  widget's staleTime on the others.

- **D-02: New service module `src/job_rag/services/analytics.py`.** Three async functions
  (`top_skills`, `salary_bands`, `cv_match`) sharing a private `_apply_filters(stmt, *,
  country, seniority, remote)` helper that mutates the SQLAlchemy select. Keeps the
  analytical concern out of `matching.py` (per-posting) and `retrieval.py` (vector search).
  Routes in `src/job_rag/api/routes.py` wire `Depends(get_current_user_id)` +
  `Depends(standard_limit)` (30/min, same as `/search`).

- **D-03: All endpoints use `Depends(get_current_user_id)` even though v1 data isn't
  per-user.** Carries forward Phase 1 D-10 + Phase 4 D-08 pattern: every business endpoint
  goes through the auth dep so AUTH-06 single-user guard fires uniformly. v1 corpus is
  global (`career_id='ai_engineer'`); the `user_id` value is accepted but currently
  unused inside the analytical queries (Phase 7 PROF-01 will use it for CV-vs-market).

### B. SQL aggregation strategy

- **D-04: SQLAlchemy ORM/Core for top-skills; `func.percentile_cont().within_group()`
  for salary-bands; hybrid SQL+Python for cv-vs-market.**
  - **Top-skills** (pure SQL — DASH-01 "no Python-side group-by"):
    ```python
    stmt = (
        select(
            JobRequirementDB.skill,
            func.sum(case((JobRequirementDB.required, 1), else_=0)).label("must_count"),
            func.sum(case((~JobRequirementDB.required, 1), else_=0)).label("nice_count"),
        )
        .join(JobPostingDB, JobRequirementDB.posting_id == JobPostingDB.id)
        .where(JobRequirementDB.skill_category != "soft")  # D-13
        .group_by(JobRequirementDB.skill)
        .order_by(func.count().desc())
        .limit(limit)
    )
    _apply_filters(stmt, country=..., seniority=..., remote=...)
    ```
  - **Salary-bands** (pure SQL with PG `percentile_cont`):
    ```python
    func.percentile_cont(0.5).within_group(JobPostingDB.salary_min.asc())
    ```
    Filter additionally: `WHERE salary_min IS NOT NULL AND salary_period IN ('year', 'month')`
    (normalize month→year by ×12 in SELECT). Sample-size COUNT runs in the same CTE.
  - **CV-vs-market** (hybrid — see D-05).

- **D-05: CV-vs-market uses SQL pre-filter + Python per-posting fold.** The fuzzy
  alias-aware skill matching in `matching.py::_skill_matches()` and `match_posting()`
  cannot trivially become SQL (alias index, case-insensitive normalize, must/nice split).
  Strategy:
  1. SQL fetches the filtered postings with `selectinload(JobPostingDB.requirements)` —
     this is the existing `/gaps` pattern.
  2. Python loops: `for p in postings: score = match_posting(profile, p)["score"]`, then
     `mean = sum(scores) / len(scores)`.
  3. Top-3 missing must-have skills via `Counter` on `match_posting(...)["missed_must_have"]`.

  This is **Python fold over already-filtered rows**, not Python-side GROUP BY. DASH-01's
  "no Python-side group-by" wording targets the top-skills/salary aggregations that DO
  have a SQL equivalent (`GROUP BY skill`, `percentile_cont`). The match-score fold is
  irreducibly per-row Python because of fuzzy matching.

  Trade-off: O(n) Python per request where n = filtered posting count (≤108 in v1).
  At Postgres B1ms latency budget this is fine. If corpus grows >1000 postings, revisit
  by porting `_skill_matches` to SQL via `ANY(array)` + canonical alias resolution at
  ingest time.

- **D-06: Profile source = continue calling `load_profile()` (reads `data/profile.json`
  via the existing function-body forward-compat shim).** Phase 7 PROF-01 flips the
  function body to query `user_profile` table; Phase 5 doesn't anticipate the change.
  The `load_profile(user_id=...)` signature already accepts user_id keyword-only.

### C. Filter semantics

- **D-07: Country filter = canonical 4-value enum (`?country=PL|DE|EU|WW`).**
  - `PL` → `WHERE p.location_country = 'PL'`
  - `DE` → `WHERE p.location_country = 'DE'`
  - `EU` → `WHERE p.location_country IN (<EU-27 ISO codes>) OR p.location_region = 'EU'`
    (the `location_region = 'EU'` branch catches Phase 2 D-09 "Remote (EU)" postings
    with NULL country)
  - `WW` (Worldwide) → no country filter (returns all rows)

  `EU_COUNTRY_CODES: frozenset[str]` hardcoded in `analytics.py` as the 27 ISO-3166
  alpha-2 codes for EU member states. Corpus is 108 postings — ESCO/REST taxonomy lookup
  would be overkill. Document the snapshot date in a comment so future maintainers know
  to refresh if EU membership changes.

- **D-08: Seniority filter = single optional value from `Seniority` enum** (`junior` |
  `mid` | `senior` | `staff` | `lead`). Omitted = no filter. UI hides `unknown` as a
  filter option since selecting it would only narrow to LLM-failed postings — not useful
  for browsing. Backend accepts `?seniority=unknown` defensively but UI doesn't surface it.

- **D-09: Remote filter = 3-state tri-toggle** (`?remote=any|remote|non_remote`).
  - `any` (default, param omitted) → no filter
  - `remote` → `WHERE p.remote_policy = 'remote'`
  - `non_remote` → `WHERE p.remote_policy IN ('hybrid', 'onsite')`

  Simpler than exposing all 4 `RemotePolicy` enum values (which would include `unknown`
  and confuse users). Matches Linear-dense ethos: fewer affordances, each one meaningful.
  Soft-bias choice for the Berlin remote market — Adrian cares most about "remote or not".

### D. CV-vs-market scoring semantics

- **D-10: Match score formula = existing `match_posting()` formula unchanged.**
  `score = (matched_must / total_must) * 0.7 + (matched_nice / total_nice) * 0.3`.
  Aggregate widget value = arithmetic mean across filtered postings.
  Phase 1 verified this; do NOT introduce a new formula in Phase 5 (would invalidate
  existing matching tests + behaviour).

- **D-11: Top-3 missing must-have skills = top 3 by frequency in
  `match_posting(...)["missed_must_have"]` across filtered postings.** Uses
  `collections.Counter`. Returned with `count` and `percentage` (count / total_postings).
  Matches the existing `aggregate_gaps` output shape so the frontend can render it with
  a similar component.

- **D-12: Zero-postings filter case = return `{ mean_score: null, postings_compared: 0,
  top_missing_must_have: [] }`, HTTP 200.** Do NOT 404 (DASH widget should render an
  empty-state, not error). Aligns with all 3 widgets returning meaningful zero values so
  empty-state UI logic stays uniform.

### E. Soft-skill default + filter

- **D-13: Soft skills hidden by default; no UI toggle in v1.** DASH-01 wording is "soft
  skills hidden by default via `SkillCategory` filter". Backend accepts
  `?include_soft=true` for future flexibility, but Phase 5 does NOT surface a UI
  affordance. Rationale: corpus has already been filtered at extraction (Phase 2 D-22
  REJECTED_SOFT_SKILLS), and Adrian's analysis explicitly avoided soft-skill noise.
  Adding the toggle is YAGNI; tracked as deferred idea if interview behaviour changes.

### F. Frontend stack & visualization

- **D-14: Single chart library install = `recharts` via shadcn `chart` block.**
  - `npx shadcn@latest add chart` lands `frontend/src/components/ui/chart.tsx` and adds
    `recharts ^3` to deps. ~93 KB gzipped, tree-shakeable; theme-aware (light/dark via
    CSS vars).
  - **Salary-bands widget** uses Recharts `BarChart` showing 3 bars (p25/p50/p75) with
    EUR axis ticks. One real chart in v1 — earns its weight here.
  - **Top-skills widget** uses Tailwind-native horizontal bars (no chart lib): a list of
    `<div>`s with width-proportional bars + numeric labels. Matches Linear-dense ethos
    and is faster to ship than configuring Recharts for a list view.
  - **CV-vs-market widget** uses big-text score + a chip list for missing skills. No
    chart needed; the score IS the visualization. Optionally a small Recharts
    `RadialBarChart` if it adds visual interest at zero cost (Claude's Discretion).

- **D-15: Dashboard component tree.**
  ```
  routes/Dashboard.tsx
    components/dashboard/
      DashboardFilters.tsx        — country dropdown + seniority dropdown + remote toggle
      TopSkillsCard.tsx           — Card wrapper + Tailwind bars + "show more" Dialog
      SalaryBandsCard.tsx         — Card wrapper + Recharts BarChart
      CvVsMarketCard.tsx          — Card wrapper + big-text score + missing-skills chips
      useDashboardFilters.ts      — typed wrapper around useSearchParams
      api.ts                      — service module: topSkills(), salaryBands(), cvVsMarket()
  ```
  Routes folder gets one file (`Dashboard.tsx`); the rest lives under
  `components/dashboard/` so the feature surface is one folder.

- **D-16: API service module shape per Phase 4 D-15 = one file per feature surface.**
  `frontend/src/api/jobs.ts` (currently a stub) becomes the analytics service module —
  exports typed `searchJobs` (existing), `topSkills`, `salaryBands`, `cvVsMarket`. All
  call `authedFetch` + cast against `openapi-typescript`-generated types (re-run
  `npm run codegen` after backend lands the 3 endpoints).

  Filename rationale: keep `jobs.ts` as the umbrella for "anything about job postings
  data" — splitting into `dashboard.ts` would fragment for no clear win at v1 scale.

### G. URL state + filter hook

- **D-17: `useDashboardFilters()` typed hook wraps `useSearchParams`.**
  - Reads/writes `country`, `seniority`, `remote` params with default elision (omit
    `country=WW` / `remote=any` since they're defaults — keeps URLs clean for sharing)
  - Returns `{ country: 'PL'|'DE'|'EU'|'WW', seniority?: Seniority, remote: 'any'|'remote'|'non_remote', setFilters }`
  - Lives in `frontend/src/components/dashboard/useDashboardFilters.ts`
  - All 3 widget query functions accept the same `filters` object and pass to API
  - React Query keys: `['dashboard', 'top-skills', filters]`, etc. — filter object is
    the cache key, so identical filter combos hit cache instantly

  Why not TanStack Router migration: 4 routes don't justify migration (Phase 4 D-17
  deferred this; Phase 5 doesn't change the calculus).

### H. Layout & widget framing

- **D-18: 3-up grid on desktop, single column on mobile.**
  - `grid grid-cols-1 md:grid-cols-3 gap-4` on the widget container
  - Filter bar above grid: horizontal flex on `md+`, stacked on mobile
  - Each widget = shadcn `Card` with `CardHeader` (title + sample-size footnote) +
    `CardContent` (the viz)
  - Filter bar component: country `DropdownMenu` (shadcn primitive from Phase 4) +
    seniority `DropdownMenu` + remote `ToggleGroup` (NEW shadcn primitive — install via
    `npx shadcn@latest add toggle-group` in same wave as `chart`)

### I. Loading / empty / error states

- **D-19: Per-widget skeletons + per-widget empty states + per-widget error fallbacks.**
  - **Loading**: `useQuery({ ... }).isPending` → shadcn `Skeleton` shaped like the
    widget body (3 bar-shaped skeletons for top-skills, 1 wide skeleton for salary-bands,
    1 small + 1 chip-list skeleton for cv-vs-market). Filter bar always interactive.
  - **Empty (zero postings)**: each widget shows its own `<EmptyState>` (Phase 4
    component) with widget-specific copy:
    - Top-skills: "No skills match these filters"
    - Salary-bands: "No postings with salary data match these filters"
    - CV-vs-market: "No postings to compare against — try adjusting filters"
  - **Error**: per-widget `<Alert variant="destructive">` inside the `Card`. shadcn
    `alert` primitive not yet installed — add in same wave (`npx shadcn@latest add alert`).
    One widget erroring doesn't kill the other two; filter bar stays alive.
  - **No whole-page error/empty branch** — composability over special cases.

### J. Top-skills "show more" UX

- **D-20: Click "Show more" → shadcn `Dialog` modal with full ranked list.**
  - `Dialog` primitive landed in Phase 4
  - Dialog body = scrollable table (`<table>` styled with Tailwind, since shadcn `table`
    primitive not yet installed and a `<table>` is fine for a static modal at this scale).
    Columns: rank, skill, must-have count, nice-to-have count, total
  - Backend: `GET /dashboard/top-skills?limit=50` (default) — client renders top-10 in
    card, modal shows all 50. Tunable via `?limit=` if Adrian wants different behavior.

### K. Sample size & metadata footnotes

- **D-21: Every widget surfaces its `n` in the card footer.**
  - Top-skills: `"{total_postings} postings · {unique_skills} unique hard skills"`
  - Salary-bands: `"{postings_with_salary} of {total_postings} postings had salary data"`
    (literal DASH-02 footnote)
  - CV-vs-market: `"Score across {postings_compared} postings"`

  Visible eyeball check that filter changes actually flow through to SQL (proves the
  Phase 5 success-criterion 5 "different numbers for PL/DE/EU/WW" claim in the UI
  itself, not just DevTools).

### L. Caching

- **D-22: TanStack Query `staleTime: 5 * 60_000` for all dashboard queries.** Override
  Phase 4 D-Discretion default of 30s — analytical results only change when the corpus
  re-ingests (rare; manual CLI action). Five-minute stale window avoids hammering
  Postgres on every filter-bar toggle. Apply per-query via `staleTime` option, not
  globally (Phase 6 chat needs the 30s default).

### M. Linear-dense aesthetic

- **D-23: Number-forward over chart-forward.** Linear's data surfaces prefer dense
  numerics + sparse bars to richly-styled charts. Apply to widgets:
  - Top-skills: numeric counts beside each bar, no axis ticks
  - Salary-bands: 3 bars labeled `€{value}/yr` directly on the bar (no separate legend)
  - CV-vs-market: big number (`0.42` style with 2 decimals) + thin baseline indicator
  - Card titles `text-sm font-medium`, body data `text-2xl` for hero numbers, `text-xs`
    for footnotes — matches existing Phase 4 spacing scale

### Claude's Discretion

- **Backend route file placement**: extend `src/job_rag/api/routes.py` directly (single
  routes file pattern). If file grows >500 lines, split into `routes/__init__.py +
  routes/dashboard.py` — but not preemptively.
- **OpenAPI tag**: tag all 3 endpoints with `"dashboard"` so the codegen-typed client
  groups them together.
- **Query parameter parsing**: use FastAPI's native `Query(...)` for type+validation;
  Pydantic-validated enum params for `country`/`remote` to reject bad strings at the
  boundary.
- **Salary period normalization**: in `salary_bands`, multiply `salary_min` by 12 when
  `salary_period = 'month'`, drop rows with `salary_period = 'hour'` (too noisy to
  normalize without hours/week assumption).
- **Recharts theme**: pull colors from CSS vars (`--chart-1`, `--chart-2`, ...) which
  shadcn's `chart` block wires up. Theme toggle (Phase 4 D-20) Just Works.
- **Test placement**: backend tests in `tests/test_analytics.py` (mirrors existing
  `tests/test_matching.py` etc.); frontend tests as `*.test.tsx` colocated with
  components, plus integration test for `useDashboardFilters` hook.
- **Test data**: use existing 98 reextracted postings in the dev DB — no need to seed
  synthetic data for analytics tests; the SQL queries are best validated against real
  shape variation (country distribution, salary nulls, soft-skill leakage).
- **Filter bar reuse**: `DashboardFilters.tsx` lives under `components/dashboard/`. If
  Phase 6 chat or Phase 7 profile ever needs the same filter shape, refactor up to
  `components/` at that point — not preemptively.
- **Match alias-index**: `_ALIAS_GROUPS` in `matching.py` is currently empty (D-12
  Phase 1 — populated as aliases surface). Phase 5 doesn't add aliases; if widget
  output looks wrong (e.g. "AWS" and "Amazon Web Services" counted separately), surface
  as a Phase 5 deferred idea.
- **EU-27 list source-of-truth**: hardcoded `frozenset` in `analytics.py` with a
  comment citing the ISO-3166 snapshot date. No runtime lookup, no external dep.
- **Currency assumption**: all salary values treated as EUR. Postings outside EU/Berlin
  with USD/GBP salaries are accepted as-is in v1 (LLM extracts the numeric; no FX
  normalization). Document as a known limitation in the salary-bands tooltip.
- **Pagination**: not needed — top-skills capped at 50 server-side (modal shows all);
  salary-bands returns 3 numbers; cv-vs-market returns 3 missing skills.
- **Dashboard layout breakpoints**: `md:grid-cols-3` (≥768px). Below 768px, single
  column. Tablet (768-1024) gets 3-up — Linear-dense scales horizontally well.
- **Accessibility**: filter bar dropdowns inherit shadcn a11y; charts add `aria-label`
  with the data summary; skeletons use `role="status"` `aria-live="polite"`.
- **Empty filter combos**: `country=PL` + `seniority=staff` may legitimately return 0
  postings. Per-widget empty state handles this; no need for "no matches at all" page.

### Folded Todos

None — no `gsd-tools todo match-phase 5` was invoked in this auto-resolved session;
the previous 4 phases reported `todo_count: 0` so unlikely to be relevant.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or
implementing Phase 5.**

### Phase scope and requirements

- `.planning/REQUIREMENTS.md` §DASH-01 through §DASH-06 — the 6 v1 dashboard requirements
  Phase 5 owns
- `.planning/REQUIREMENTS.md` §SHEL-03, §SHEL-06 — TanStack Query usage + error/empty/
  loading state requirement (cross-phase; Phase 4 wired Query, Phase 5 uses it for the
  3 analytical widgets)
- `.planning/ROADMAP.md` §Phase 5 — goal + 5 must-be-TRUE success criteria
- `.planning/PROJECT.md` §Constraints — Vite + React + TS frozen, Linear-dense aesthetic,
  Azure-only, €0/mo budget
- `.planning/PROJECT.md` §"Context — Skill-gap data" — corpus snapshot showing the
  expected shape (AWS/SQL/Azure top must-have gaps); validates the dashboard's reason
  to exist
- `.planning/PROJECT.md` §"Context — Target market" — Berlin/Germany/remote framing
  motivates the country filter values (PL / DE / EU / WW)

### Prior phase decisions (carried forward — do NOT re-litigate)

- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-08 — `SEEDED_USER_ID` Python
  constant; `load_profile(user_id=...)` signature pre-wired; Phase 5 calls
  `load_profile()` with no args (defaults to seeded user)
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-10 — function-body rewrite pattern;
  `load_profile()` body will flip in Phase 7 PROF-01 to read from DB. Phase 5 doesn't
  anticipate.
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-12 — `_ALIAS_GROUPS` in
  `matching.py` starts empty; populated as aliases surface. Phase 5 inherits as-is.
- `.planning/phases/02-corpus-cleanup/02-CONTEXT.md` §D-02, §D-03 — `SkillCategory`
  3-value enum (hard/soft/domain); derived from `SkillType` deterministically. Phase 5
  filters `WHERE skill_category != 'soft'` by default (DASH-01).
- `.planning/phases/02-corpus-cleanup/02-CONTEXT.md` §D-06, §D-07, §D-11 — `Location`
  Pydantic submodel + flat 3-column DB representation (`location_country`,
  `location_city`, `location_region`). Phase 5 country filter targets these columns.
- `.planning/phases/02-corpus-cleanup/02-CONTEXT.md` §D-09 — "Worldwide" / "Remote (EU)"
  postings store as `country=NULL, region='EU' | 'Worldwide'`. Phase 5 country filter
  must handle this (D-07 EU branch checks `location_region = 'EU'`).
- `.planning/phases/02-corpus-cleanup/02-CONTEXT.md` §D-22 — REJECTED_SOFT_SKILLS prompt
  filter; corpus already has minimal soft-skill noise. Phase 5 hides remaining via
  `skill_category != 'soft'`.
- `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` §D-13 — `authedFetch` wrapper;
  Phase 5 dashboard service module uses it for all 3 analytical fetches.
- `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` §D-14 — `openapi-typescript`
  codegen; Phase 5 backend lands 3 endpoints, then re-run `npm run codegen` to pull
  typed request/response schemas.
- `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` §D-15 — typed service module
  per domain shape; Phase 5 extends `frontend/src/api/jobs.ts` (currently a stub).
- `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` §D-17, §D-18 — React Router v7
  + `AuthGate` + `AppShell` layout; Phase 5 plugs into `/dashboard` route inside
  AuthGate.
- `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` §D-19 — SHEL-06 layered
  loading/empty/error pattern; Phase 5 applies at widget level.
- `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` §D-20 — shadcn theme (zinc +
  Geist + new-york + default-dark). Phase 5 inherits.
- `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` §D-08 + Plan 04-02 — backend
  `get_current_user_id` rewrite + AUTH-06 single-user guard; Phase 5 endpoints inherit
  via `Depends(get_current_user_id)`.

### Stack research (HIGH confidence)

- `.planning/research/STACK.md` §1 — Vite 8.x, React 19.2, TS 5.x, Tailwind v4
  (`@tailwindcss/vite`), shadcn/ui new-york style, `@tanstack/react-query` 5.x. Phase 5
  inherits stack frozen.
- `.planning/codebase/STACK.md` — backend frozen: SQLAlchemy 2.x async + asyncpg +
  pgvector + FastAPI 0.135.3. Phase 5 adds NOTHING to backend stack.

### Codebase audit (Phase 5 must not break)

- `.planning/codebase/ARCHITECTURE.md` — three-tier backend layering (Ingestion →
  Retrieval+Matching → Intelligence/Tools); Phase 5 adds an Analytics sub-layer under
  `services/analytics.py` alongside `matching.py` and `retrieval.py`.
- `src/job_rag/api/routes.py` lines 99-200 — existing endpoint patterns (`/search`,
  `/match`, `/gaps`); Phase 5 adds 3 endpoints below `/agent` block following the same
  decorator pattern.
- `src/job_rag/api/auth.py` §`get_current_user_id` — Phase 4 D-08 already rewrites this
  to enforce AUTH-06; Phase 5 just passes the dep through.
- `src/job_rag/services/matching.py` §`load_profile`, §`match_posting`,
  §`aggregate_gaps`, §`_skill_matches` — Phase 5 cv-vs-market reuses ALL of these
  unchanged; do NOT modify `match_posting()` formula.
- `src/job_rag/db/models.py` §`JobPostingDB` lines 11-59 — schema reference:
  `location_country` String(2), `salary_min`/`salary_max` int nullable, `salary_period`
  String(10), `seniority` String(20), `remote_policy` String(20). All have indexes
  (lines 54-59) so the dashboard filters are index-served.
- `src/job_rag/db/models.py` §`JobRequirementDB` lines 62-80 — `skill_category` String(20)
  with index; Phase 5 top-skills `WHERE skill_category != 'soft'` is index-served.
- `src/job_rag/models.py` — `Seniority`, `RemotePolicy`, `SalaryPeriod`, `SkillCategory`
  enum definitions; Phase 5 backend imports these for query validation.
- `alembic/versions/0004_*.py` (Phase 2 D-11) — migration that landed `location_*`
  columns + `skill_category`; verifies schema baseline.
- `frontend/src/routes/Dashboard.tsx` — current stub (PhasePlaceholder); Phase 5
  replaces.
- `frontend/src/api/jobs.ts` — current stub; Phase 5 fills with `topSkills`,
  `salaryBands`, `cvVsMarket` + (later) `searchJobs`.
- `frontend/src/components/ui/{card,skeleton,dropdown-menu,dialog,button,badge}.tsx` —
  shadcn primitives landed in Phase 4 plan 04-05; Phase 5 uses all of these.
  Net-new primitives to install: `alert`, `chart`, `toggle-group` (`npx shadcn@latest
  add ...`).
- `frontend/src/components/{AppShell,AuthGate,EmptyState,RouteSkeleton,ThemeToggle,
  ErrorBoundary}.tsx` — Phase 4 components Phase 5 wraps inside (AppShell + AuthGate)
  or composes (EmptyState).
- `frontend/src/api/{authedFetch,queryClient,types}.ts` — Phase 4 infrastructure
  Phase 5 plugs into.
- `frontend/src/App.tsx` — route table; `/dashboard` is already wired to `DashboardPage`
  via `lazy(() => import('@/routes/Dashboard'))`. Phase 5 doesn't touch routing.

### Phase 5 outputs that downstream phases will consume

- `src/job_rag/services/analytics.py` — Phase 8 EVAL set may add eval queries that touch
  these endpoints
- `GET /dashboard/{top-skills,salary-bands,cv-vs-market}` — Phase 8 docs cover these in
  the API surface section
- `frontend/src/components/dashboard/` — Phase 7 profile + Phase 6 chat may reuse the
  filter bar pattern (cross-phase pattern, not a hard dep)

### Pitfalls research (HIGH confidence, relevant for this phase)

- `.planning/research/PITFALLS.md` §4 — scale-to-zero cold start; Phase 5's 3 parallel
  fetches from Dashboard mount = 3 simultaneous cold-start requests. Phase 1 D-04
  reranker preload doesn't help analytics (no reranker invoked); Phase 5 should be
  aware that first dashboard load after idle WILL pay the ~225s ACA cold-start cost (see
  `~/.claude/projects/-Users-adrian-Developer-job-rag/memory/aca-cold-start-profile.md`).
  Phase 5 doesn't fix this — Phase 8 portfolio polish may revisit.
- `.planning/research/PITFALLS.md` §"Looks Done But Isn't Checklist" — Phase 5
  verification owns: changing country filter actually changes SQL (not just URL) — the
  "different numbers per country" success criterion proves this.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`load_profile(*, user_id=None, path=None)`** (`src/job_rag/services/matching.py`)
  — Phase 5 cv-vs-market calls this with no args; defaults to seeded user via Phase 1
  D-07 signature. Phase 7 PROF-01 will swap the function body to DB lookup — no
  Phase 5 call-site change needed.
- **`match_posting(profile, posting)`** (`src/job_rag/services/matching.py` line 78) —
  Phase 5 cv-vs-market loops this per filtered posting; reuses the 0.7 must + 0.3 nice
  formula verbatim. Returns `score`, `missed_must_have`, `missed_nice_to_have` —
  exactly what cv-vs-market needs.
- **`aggregate_gaps(profile, postings)`** (`src/job_rag/services/matching.py` line 124)
  — output shape (`{ must_have_gaps: [{skill, count, percentage}] }`) is the model
  Phase 5 cv-vs-market should mirror for its `top_missing_must_have` field. Don't call
  it directly (Phase 5's filter shape differs); duplicate the Counter pattern but
  cap at 3 items.
- **`get_current_user_id` Depends** (`src/job_rag/api/auth.py`) — Phase 4 D-08 already
  enforces AUTH-06. Phase 5 endpoints inherit by adding `Depends(get_current_user_id)`.
- **`standard_limit` rate limiter** (`src/job_rag/api/auth.py`) — 30/min same as
  `/search`; Phase 5 uses for all 3 endpoints. `agent_limit` (10/min) reserved for
  Phase 6.
- **`get_session` async session dep** (`src/job_rag/api/deps.py`) — Phase 5 endpoints
  use this for the AsyncSession injection.
- **Existing JobPostingDB / JobRequirementDB indexes** (lines 54-59, 76-79 of
  `db/models.py`) — `ix_job_postings_location_country`, `ix_job_postings_seniority`,
  `ix_job_postings_remote_policy`, `ix_job_requirements_skill_category` all exist.
  Phase 5 filters are index-served; no new migrations needed.
- **shadcn primitives already shipped** (`frontend/src/components/ui/`): `card`,
  `skeleton`, `dropdown-menu`, `dialog`, `button`, `badge`, `input`, `sonner`. Phase 5
  uses card/skeleton/dropdown-menu/dialog/badge.
- **`authedFetch`** (`frontend/src/api/authedFetch.ts`) — Phase 5 service module calls
  via this; MSAL token attachment + 401 retry already wired.
- **`EmptyState`** (`frontend/src/components/EmptyState.tsx`) — Phase 4 D-19 widget-level
  empty pattern; Phase 5 uses inside each Card for the zero-postings case.
- **`useQuery` defaults** (`frontend/src/api/queryClient.ts`) — Phase 4 D-Discretion
  default 30s staleTime; Phase 5 overrides per-query to 5 min for analytics.

### Established Patterns

- **`structlog get_logger(__name__)`** — Phase 5 backend code follows the same pattern.
  `log.info("dashboard_query", endpoint="top-skills", filters=..., n=...)` for each
  endpoint hit.
- **Endpoint pattern with `Depends`** (routes.py lines 153-200) —
  `@router.get("/dashboard/X", dependencies=[Depends(require_api_key),
  Depends(standard_limit)])` + `user_id: Annotated[uuid.UUID,
  Depends(get_current_user_id)]` + `session: Session`. Phase 5 mirrors verbatim.
- **`load_profile(user_id=user_id)`** call pattern (routes.py line 174 for `/match`)
  — Phase 5 cv-vs-market follows.
- **Pydantic response models** — current code returns `dict[str, Any]` (routes.py
  return types). Phase 5 SHOULD define explicit Pydantic response models
  (`DashboardTopSkillsResponse`, etc.) so openapi-typescript codegen produces named
  schemas the frontend can import — cleaner than relying on inline dict shape.
- **SQLAlchemy ORM patterns** (matching.py, retrieval.py) — Phase 5 analytics.py uses
  `select(...).join(...).where(...).group_by(...).order_by(...).limit(...)` style.
  Async session execute pattern: `result = await session.execute(stmt); rows =
  result.all()`.
- **shadcn install via `npx shadcn@latest add <primitive>`** — Phase 4 Plan 04-05 D
  pattern; Phase 5 adds `alert`, `chart`, `toggle-group` in one go at start of frontend
  wave.
- **TanStack Query keying** — Phase 4 patterns: `['health']`, `['agent']`. Phase 5
  follows `['dashboard', 'top-skills', filters]` shape.
- **Phase 4 D-15 service module shape** — typed async functions per file. Phase 5
  extends `jobs.ts` rather than creating `dashboard.ts` (one umbrella per data domain).

### Integration Points

- **`src/job_rag/api/routes.py`** — Phase 5 adds 3 new `@router.get` handlers (likely
  in a Phase 5 plan's late wave so backend service module is in place first)
- **`src/job_rag/services/analytics.py`** (NEW) — Phase 5 D-02 creates this with 3
  async functions
- **`src/job_rag/api/dashboard.py`** (NEW, recommended) — explicit Pydantic response
  models for the 3 endpoints (Claude's Discretion on filename; alternative:
  `src/job_rag/models.py`)
- **`tests/test_analytics.py`** (NEW) — backend unit tests for `top_skills`,
  `salary_bands`, `cv_match` with fixture postings
- **`tests/test_api.py`** (EXISTING) — Phase 5 adds 3 endpoint integration tests
  following the existing `/match` / `/gaps` test pattern
- **`frontend/src/routes/Dashboard.tsx`** — replace placeholder with feature
  implementation
- **`frontend/src/api/jobs.ts`** — fill stub with `topSkills`, `salaryBands`,
  `cvVsMarket` typed functions
- **`frontend/src/api/types.ts`** — re-run `npm run codegen` after backend lands new
  endpoints to refresh OpenAPI-derived types
- **`frontend/src/components/dashboard/`** (NEW DIR) — `DashboardFilters.tsx`,
  `TopSkillsCard.tsx`, `SalaryBandsCard.tsx`, `CvVsMarketCard.tsx`,
  `useDashboardFilters.ts`
- **`frontend/src/components/ui/{alert,chart,toggle-group}.tsx`** (NEW) — shadcn primitives
  installed via `npx shadcn@latest add`
- **`frontend/package.json`** — adds `recharts ^3.x` peer dep automatically via shadcn
  `chart` install
- **No infrastructure changes** — no Terraform, no Key Vault, no Container App env vars,
  no migrations. Pure code phase.

</code_context>

<specifics>
## Specific Ideas

- **Linear-dense aesthetic for analytics**: prefer number-forward over chart-forward.
  Stripe's analytics dashboards lean on big numbers + sparse bars; Linear's roadmap
  view shows the pattern at info-density. Phase 5 widgets follow this — one real chart
  (salary-bands), the other two are number + Tailwind bars + chip list.
- **Filter values are LITERAL from REQUIREMENTS DASH-04**: "Poland / Germany / EU /
  Worldwide" — don't add Switzerland / Netherlands / etc. even if Adrian has postings
  from those countries. Future v2 can offer all-countries-in-corpus dynamic dropdown.
- **The "different numbers per country" success criterion is the canary**: Phase 5
  verification owns proving filter changes flow through to SQL. Adrian should be able
  to flip PL → DE → EU and see top-skills order change (Berlin postings have higher
  AWS/Azure must-have weight than Polish postings probably do; corpus distribution
  will tell). The sample-size footer ("{n} postings") is the eyeball check.
- **`/gaps` is NOT replaced**: existing endpoint stays. The Chat agent (Phase 6) calls
  it via `analyze_gaps` tool; ripping it out would break the agent. Phase 5 adds
  analytics endpoints alongside.
- **No top-of-page summary banner**: keep the dashboard chrome minimal — filter bar
  → 3 widgets. Linear doesn't preface dashboards with hero copy.
- **Theme toggle (Phase 4 D-20) lives in AppShell top-nav**: Phase 5 doesn't add a
  per-page toggle. Recharts theme via `--chart-N` CSS vars Just Works.
- **Backend test corpus**: use existing 98 reextracted postings (~10 with broken
  extraction per Phase 2 known limitation). Don't seed synthetic data — real shape
  variation catches edge cases like NULL country, NULL salary, empty must-have lists.
- **Cold-start ACA caveat**: first dashboard load after idle hits ~225s cold start (per
  memory `aca-cold-start-profile.md`). Phase 5 doesn't mitigate; document in Phase 5
  README or RUNBOOK note that "if dashboard takes a long time, the container is cold-
  starting; subsequent requests are <1s". Phase 8 portfolio polish can revisit (e.g.,
  always-warm via 1 min-replica costs ~€8/mo — out of budget).

</specifics>

<deferred>
## Deferred Ideas

- **Interactive cross-filtering** (click skill → filter dashboard by postings requiring
  it) — v2 (DASH2-01). Phase 5 widgets are read-only.
- **Skill co-occurrence view** — v2 (DASH2-02). Out of scope.
- **Time-series trends** (skill demand over time) — v2 (DASH2-03). Corpus has no
  ingestion-time tracking; would need new schema.
- **Per-posting drill-down pages** — v2 (DASH2-04). Phase 5 stays at aggregate level.
- **"Show soft skills" UI toggle** — corpus already filtered at extraction; YAGNI for
  v1. Revisit if Adrian sees soft-skill noise actually leaking through.
- **Skill alias matching** — `_ALIAS_GROUPS` is empty (Phase 1 D-12). If Phase 5
  reveals duplicate counting (e.g. "AWS" + "Amazon Web Services" both showing in
  top-skills), open a focused phase to populate aliases. Don't expand Phase 5 scope.
- **All-countries-in-corpus dropdown**: dynamic country list pulled from
  `SELECT DISTINCT location_country FROM job_postings` — v2 when Adrian wants more
  geo granularity.
- **Hourly/contract salary normalization**: Phase 5 drops `salary_period='hour'` rows
  from salary-bands. v2 may add a "$X/hr × Y hr/wk × 52" normalization with a default
  Y. Track if Adrian sees a lot of contract postings being silently excluded.
- **Currency normalization**: salaries are all treated as EUR in v1. FX-aware
  conversion is a v2 platform feature.
- **Pagination on top-skills modal**: 50-skill cap should be plenty for 108-posting
  corpus; deferred until proven insufficient.
- **Widget order configurability**: top-skills | salary-bands | cv-vs-market is fixed
  in v1. User-draggable widget order is a v2 personalization feature.
- **Export to CSV/PNG**: not in v1 requirements. Defer.
- **Always-warm ACA** to eliminate cold-start UX hit — costs €8/mo (out of budget).
  Phase 8 portfolio polish may revisit if Adrian deems demo experience worth it.
- **Pydantic response models in `src/job_rag/models.py` vs `api/dashboard.py`** —
  filename choice deferred to the planner. Either works; Claude's Discretion.
- **Replacing `/gaps` with `/dashboard/cv-vs-market`** — `/gaps` is consumed by the
  agent's `analyze_gaps` tool (Phase 6); cannot rip out until Phase 6 either rewires
  or accepts the dashboard endpoint. Defer to Phase 8 cleanup if relevant.
- **Phase 04.1 in-flight** — the 5 follow-up fixes (init_db UPDATE refactor, CI smoke
  check, MSAL bootError catch, customer-vs-B2B-guest doc, identifier_uri inline) are
  parallel-eligible with Phase 5. Phase 5 does NOT depend on any of them landing
  first. If 04.1's Fix 1 (init_db UPDATE refactor) lands during Phase 5 execution,
  Phase 5 doesn't care — different files, different code paths.

### Reviewed Todos (not folded)

None — todo check skipped in this auto-resolved session.

</deferred>

---

*Phase: 05-dashboard*
*Context gathered: 2026-05-21*
*Decisions: 23 (all auto-resolved with Recommended pattern per user-locked Phase 4
precedent — Adrian, please redirect any that don't match your intent)*
