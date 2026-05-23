---
phase: 5
phase_name: "dashboard"
project: "job-rag"
generated: "2026-05-23"
counts:
  decisions: 12
  lessons: 10
  patterns: 8
  surprises: 6
missing_artifacts: []
---

# Phase 5 Learnings: dashboard

## Decisions

### EU_COUNTRY_CODES as an immutable frozenset with snapshot-date comment
Use a `frozenset[str]` literal of 27 ISO-3166 alpha-2 codes, declared at module scope with a Wikipedia source citation and a 2026-05-22 snapshot date in the docstring. `EU_COUNTRY_CODES.add(...)` raises `AttributeError` at runtime (T-5-02-03 mitigation).

**Rationale:** The EU membership list is slow-changing audit-relevant data, not a runtime configurable. Freezing it prevents tampering and the snapshot date gives future maintainers an obvious refresh checkpoint. ISO `GR` is the canonical code for Greece (not EU-protocol `EL`); `GB`/`UK` excluded post-Brexit.
**Source:** 05-02-PLAN.md, 05-02-SUMMARY.md

---

### MagicMock + AsyncMock over in-memory SQLite for SQL-heavy async test code
Test the analytics service via `MagicMock(AsyncSession)` + `AsyncMock(execute, side_effect=[...])` rather than introducing `aiosqlite` for an in-memory database.

**Rationale:** (1) `aiosqlite` is not a project dep so adding it would expand surface for tests only. (2) PostgreSQL `percentile_cont` does not exist on SQLite so salary_bands tests cannot use it. (3) pgvector's `Vector(1536)` column would not materialize against SQLite without a type override. (4) The codebase already uses MagicMock+AsyncMock for `AsyncSession` in `tests/test_lifespan.py` and `tests/test_mcp_server.py`.
**Source:** 05-02-SUMMARY.md (Decisions Made)

---

### Patch-target alignment for aliased imports in test mocks
When `routes.py` imports analytics functions with aliases (`from job_rag.services.analytics import top_skills as analytics_top_skills`), tests MUST patch the bound name on the consumer (`patch("job_rag.api.routes.analytics_top_skills", ...)`), NOT the source module (`patch("job_rag.services.analytics.top_skills", ...)`).

**Rationale:** Python `from X import Y as Z` creates a new name binding `Z` in the importing module's namespace. Patching the source rebinds `Y` in `X` but the route still calls its own `Z` reference, so the mock never fires.
**Source:** 05-03-PLAN.md, 05-03-SUMMARY.md (Decisions Made)

---

### D-12 contract: dashboard endpoints return 200 with zero-state body, never 404
`/dashboard/cv-vs-market` returns `{mean_score: null, postings_compared: 0, top_missing_must_have: []}` with HTTP 200 when filters match zero postings, even though the legacy `/gaps` handler returns 404 in the same situation.

**Rationale:** Dashboard widgets need a zero-state UI ("No postings to compare") that's distinct from an error. 404 forces error-Alert branches; 200-with-null lets the widget render its EmptyState. `/gaps` keeps its legacy contract for backward compatibility but new endpoints adopt the cleaner 200-zero-state shape.
**Source:** 05-02-PLAN.md, 05-03-PLAN.md, 05-03-SUMMARY.md (key-decisions / patterns-established)

---

### `user_id` accepted via `Depends(get_current_user_id)` on all 3 dashboard handlers even when unused
All 3 dashboard handlers accept `user_id: Annotated[uuid.UUID, Depends(get_current_user_id)]` for uniformity, even though only `cv_match` actually uses it today. `top-skills` and `salary-bands` explicitly discard the value (`_ = user_id`).

**Rationale:** Wires multi-tenancy hook without a signature change. Phase 7 (PROF-01) will flip `top-skills` / `salary-bands` to per-user corpora; handler signatures stay identical, only the analytics service body changes. Pre-positions D-03 (uniform auth dep across dashboard surface).
**Source:** 05-03-SUMMARY.md (key-decisions)

---

### `standard_limit` (30/min, later 120/min) for dashboard endpoints, not `agent_limit`
Chose `Depends(standard_limit)` over `Depends(agent_limit)` (reserved for Phase 6 chat) for all 3 dashboard endpoints.

**Rationale:** Dashboard widgets fire 3 parallel requests on initial load plus more per-filter toggle. 30/min/IP matches `/search` `/match` `/gaps` cadence. The 10/min `agent_limit` reserved for chat streaming where requests are heavier but rarer.
**Source:** 05-03-SUMMARY.md (key-decisions)

---

### Default elision on both wire-side and URL-side (canonical-URL contract)
`useDashboardFilters.setFilters` omits `country=WW` / `seniority=undefined` / `remote=any` from the URL on write; `jobs.ts::buildFilterQuery` omits the same values from the network request. `/dashboard` (no params) is canonical for the all-defaults state.

**Rationale:** Keeps the deep-link URL clean and shareable, and ensures the network URL and history URL stay in lockstep so cache keys behave consistently. Without this, `/dashboard?country=WW` and `/dashboard` would round-trip to the same backend but TanStack Query would treat them as separate cache entries.
**Source:** 05-04-PLAN.md, 05-04-SUMMARY.md (patterns-established)

---

### Type-guard approach (`isCountry`/`isRemote`/`isSeniority`) over `as` casts for URL parsing
Chose user-defined type guards in `useDashboardFilters.ts` that narrow `string | null` to the typed union, with invalid strings coerced to safe defaults (`?country=ZZ` → `WW`), rather than the unsafe `as Seniority` cast shown in an earlier UI-SPEC excerpt.

**Rationale:** T-INPUT-VALIDATION defense-in-depth on the client side. An unguarded cast would let `?seniority=xyz` propagate as a runtime-typed `Seniority` into the network request even though the backend would 422 it; type guards reject at the boundary, so the bad value never enters the cache key or query string.
**Source:** 05-04-PLAN.md, 05-04-SUMMARY.md (Decisions Made)

---

### `staleTime: 5*60_000` per-widget override of Phase 4's 30s default
Each widget passes `staleTime: 5 * 60_000` directly in `useQuery` options, overriding Phase 4's 30s global default. Query keys uniform: `['dashboard', NAME, filters]`.

**Rationale:** Dashboard analytics are aggregate views, not real-time data. 5-minute freshness matches the user's mental model (filter doesn't refetch every 30s on tab refocus); reduces backend pressure during filter exploration. Documented as D-22 override in PATTERNS.
**Source:** 05-05-SUMMARY.md (tech-stack patterns)

---

### Placeholder-forward-then-replace task ordering across multi-task plans
When a later task introduces dependencies that earlier tasks' verify steps need (e.g., `routes/Dashboard.tsx` imports widgets that Tasks 2 and 3 will ship), bundle minimal `export function X() { return null }` placeholders into the earlier task's commit so `tsc --noEmit` passes. Each subsequent task replaces its own placeholder with the full implementation.

**Rationale:** Atomicity at the task-commit level requires the verify gate to pass. Without placeholders, Task 1's typecheck fails with TS2307 on missing imports, blocking commit. Placeholders preserve atomicity without forcing forward-bundling of full implementations (which would make per-task git diffs unreviewable).
**Source:** 05-05-SUMMARY.md (patterns-established), 05-04-SUMMARY.md (Rule 3 hook bundling precedent)

---

### Accept ACA cold-start (~225s) as v1 limitation; defer `min_replicas=1` to Phase 8
First dashboard load after `min_replicas=0` scale-to-zero takes ~225s; subsequent loads are sub-second. Documented in 05-UAT.md M6; not fixed in v1.

**Rationale:** Preserves €0/mo runtime budget per DEPL-03 / Phase 3 D-17. Bumping to `min_replicas=1` would cost ~€8/mo continuous warmth — out of v1 budget. Phase 8 portfolio polish may revisit if demo cadence justifies it. Alternatives noted: synthetic warmup ping every 30 min (free up to 5 tests in Azure Monitor), or surface a "Backend waking up" UI hint.
**Source:** 05-06-PLAN.md, 05-06-SUMMARY.md, 05-UAT.md M6

---

### Defer Polish PLN salary normalization to v2 (not a Phase 5 blocker)
Polish p50 €793,440/yr is implausible — analytics treats raw `salary_min` as EUR regardless of source currency. Already documented in PROJECT.md §Constraints as a v1 limitation ("FX-aware conversion is a v2 platform feature"). Not fixed in Phase 5.

**Rationale:** The inflated number is a tolerable signal to v1 user (Adrian) and doesn't block his Berlin/German target market use case (German postings are priced natively in EUR and read correctly). Either upstream during ingestion (`extractor.py` normalize at write time, preferred) or downstream in `analytics.salary_bands` (FX lookup at query time) is a v2 platform decision.
**Source:** 05-06-SUMMARY.md, 05-UAT.md Finding 1

---

## Lessons

### Phase 4 left the `_expected_issuer()` bug latent because no shipped surface exercised full token-acquire-validate roundtrip
Entra External ID issues tokens with the tenant GUID as subdomain (`3fd51a76-....ciamlogin.com`), NOT the friendly hostname (`jobrag.ciamlogin.com`). `_expected_issuer()` in `src/job_rag/api/auth.py` was constructing the friendly subdomain form, so every authenticated request 401'd at the auth dep. Phase 4 left this latent because `/health` is unauthenticated, `/chat` is a Phase 6 placeholder, and `/profile` is a Phase 7 placeholder — Phase 5 dashboard was the FIRST surface to fire an `Authorization: Bearer <jwt>` round-trip end-to-end.

**Context:** UAT M1 morning attempt 2026-05-22 ~09:07Z showed widgets stuck in 429 cascade. Three hotfix commits (fbf82c6, 8c8037a, ab9437d) landed before UAT could pass; ab9437d was the root cause fix. Phase verification flows that only prove sign-in lands and protected routes redirect are insufficient — they must include at least one authenticated API round-trip per protected endpoint shape, or latent auth bugs will surface in the next phase that adds the first real authenticated surface.
**Source:** 05-UAT.md (Issues Found During UAT), 05-06-SUMMARY.md (Issues Encountered)

---

### Defense-in-depth mitigations can mask a root cause without resolving it
`fbf82c6` (bump per-IP dashboard rate limit 30 → 120/min) and `8c8037a` (React Query: skip retries on 4xx) were both reasonable hardening responses to the observed 429 cascade. They reduced amplification (~13× → ~3× per loop iteration) but did not stop the underlying redirect loop. Only after investigating the root cause did `ab9437d` (`_expected_issuer()` subdomain fix) eliminate the symptom entirely.

**Context:** Symptoms looked like a rate-limit / retry problem and the two mitigations were applied first because they're cheap and obviously correct on their own merit. The actual problem was at the auth-validation layer two levels deeper. Lesson: when symptoms point at infrastructure (rate limits, retries) but the corpus and request shape don't justify the volume, suspect a downstream loop and trace the response code chain before reflexively raising limits.
**Source:** 05-06-SUMMARY.md (Issues Encountered), 05-UAT.md (Hotfix commits chronological table)

---

### Plan acceptance criteria written as literal grep checks can be defeated by codebase patterns the planner didn't know about
Plan 05-01 acceptance criterion #6 required `grep -q '"@radix-ui/react-toggle-group"' frontend/package.json` to return 0. But the codebase already uses the `radix-ui` umbrella package (see `dropdown-menu.tsx`), and `npx shadcn@latest add toggle-group` emits `{ ToggleGroup as ToggleGroupPrimitive } from "radix-ui"` to match. The literal grep returns no match even though the substantive contract (ToggleGroup primitive accessible, ToggleGroupItem exported) is satisfied.

**Context:** The plan was written from an unbundled-radix assumption; the actual codebase uses the umbrella package. Lesson: literal grep checks in acceptance criteria are fragile against legitimate codebase variation. Prefer behavioral assertions (`grep -q "ToggleGroupItem" frontend/src/components/ui/toggle-group.tsx`) over dep-shape assertions (`grep -q '"@radix-ui/react-toggle-group"' frontend/package.json`).
**Source:** 05-01-SUMMARY.md (Deviations)

---

### `select(JobPostingDB)` includes every column in SELECT, so substring-matching the compiled SQL false-positives WHERE assertions
In `TestApplyFilters::test_country_ww_no_filter`, asserting `"location_country" not in compiled_sql` to verify the WW branch adds no filter failed because `select(JobPostingDB)` always includes `location_country` in the SELECT column list. The substring matched even when no WHERE clause was added.

**Context:** Fixed by inspecting `stmt.whereclause` directly (`assert stmt.whereclause is None` for no-filter cases, `str(stmt.whereclause.compile(literal_binds=True))` for filter-applied cases). Lesson: when asserting absence of a SQL clause, inspect the AST property specifically rather than substring-matching the full compiled string.
**Source:** 05-02-SUMMARY.md (Deviations #2)

---

### `dashboard_postings_factory` fixture from Plan 05-01 had a stale `user_id` kwarg that broke against the actual ORM schema
Plan 05-01's `<interfaces>` block listed `user_id: Mapped[uuid.UUID]` on `JobPostingDB`, but the actual code (`src/job_rag/db/models.py:11-59`) does not have it — v1 corpus is global, keyed by `career_id='ai_engineer'`. Per-user data lives on `UserProfileDB` only. The factory's `JobPostingDB(user_id=user_id, ...)` raised `TypeError: 'user_id' is an invalid keyword argument`.

**Context:** Discovered in Plan 05-02 Task 1 when TestCvMatch tried to use the fixture. Lesson: when authoring `<interfaces>` blocks for downstream plans, extract from the source file at the time of writing rather than from memory or a previous plan's `<interfaces>`. Even verbatim-looking ORM schemas can drift between phases.
**Source:** 05-02-SUMMARY.md (Deviations #1)

---

### Esbuild's `.ts` loader refuses JSX even with `verbatimModuleSyntax: true`; vitest tests using JSX wrappers must be `.test.tsx`
Plan 05-01 created `useDashboardFilters.test.ts` (no JSX in the stub). Plan 05-04's active tests use a `<MemoryRouter>` wrapper which is JSX. Esbuild's `.ts` loader rejected with `Expected ">" but found "initialEntries"`. Renamed via `git mv` to `.test.tsx` to preserve git history.

**Context:** The plan body's example code already used JSX syntax for the wrapper, so the extension change was implicitly required. Lesson: vitest test files using any JSX (including `MemoryRouter`, `QueryClientProvider`, custom wrappers) MUST end in `.test.tsx`. Don't trust `.test.ts` to be a safe default; choose the extension based on whether the tests will need JSX wrappers.
**Source:** 05-04-SUMMARY.md (Deviations #2)

---

### Pytest-asyncio's module-level `pytestmark = pytest.mark.asyncio` warns on sync test methods inside `class TestX:` and class-level overrides don't suppress it
`TestEuCountrySetMembership` contained 6 sync test methods (pure constant inspection); pytest-asyncio emitted 6 warnings "marked with @pytest.mark.asyncio but it is not an async function". A class-level `pytestmark: list = []` override did NOT suppress the warning under the current pytest-asyncio version.

**Context:** Fixed by converting all 6 methods to `async def` (trivially awaitable, no actual await needed). Lesson: module-level `pytestmark = pytest.mark.asyncio` is sticky; if a test class has sync methods, the simplest fix is making them async. Don't expect class-level overrides to work.
**Source:** 05-02-SUMMARY.md (Deviations #3)

---

### TypeScript flow narrowing through derived-const checks doesn't propagate to nested field access inside JSX subtrees
Plan body's example: `hasData && (<>{data.mean_score.toFixed(2)}</>)` where `hasData = data != null && data.mean_score != null`. TypeScript narrows `data` from `data != null` but does NOT propagate `data.mean_score != null` through the derived `hasData` const into the JSX subtree. `.toFixed(2)` errors with "Object is possibly null".

**Context:** Fixed in CvVsMarketCard by adding explicit `data.mean_score !== null && data.mean_score !== undefined` re-check directly in the JSX gate. Lesson: TypeScript's control-flow narrowing has limits — a hoisted `hasData` boolean loses the nested-property narrowing. Either re-check inline at the use site, or use a `!` non-null assertion (avoided here for stricter typing).
**Source:** 05-05-SUMMARY.md (Deviations #3)

---

### Plan acceptance criteria phrased as "grep ... returns 0" can also fail because of literal text in comments
Plan 05-05 required `grep -c "PhasePlaceholder" frontend/src/routes/Dashboard.tsx` to return 0 (stub removed). The plan body's example comment text included `// Replaces the Phase 4 PhasePlaceholder stub.` which would leave the literal word in the file even after the import was removed.

**Context:** Edited the comment to `// Replaces the Phase 4 placeholder stub.` so the grep returns 0. Lesson: when authoring acceptance criteria that check for absence of a literal token, ensure example code blocks in the plan body don't reintroduce the token in comments. Or weaken the criterion to scope it: `grep -c "PhasePlaceholder" ... | grep -v "//"`.
**Source:** 05-05-SUMMARY.md (Deviations #2)

---

### Ruff I001 splits aliased imports into separate `from ... import` statements; combined-aliases form not accepted
Initial attempt in routes.py was a single grouped import:
```python
from job_rag.services.analytics import (
    cv_match as analytics_cv_match,
    salary_bands as analytics_salary_bands,
    top_skills as analytics_top_skills,
)
```
Ruff I001 rejected this with "Import block is un-sorted or un-formatted" and auto-fixed it by splitting into 3 separate `from job_rag.services.analytics import (...)` statements. Manual recombination was re-rejected.

**Context:** Accepted the auto-fix output as semantically identical (just verbose at lexical level). Lesson: the project's ruff isort config insists on split-aliased-imports. Don't fight it; the auto-fix is the canonical form for this repo.
**Source:** 05-03-SUMMARY.md (Issues Encountered, Decisions Made)

---

## Patterns

### Wave 0 foundation: scaffold tests + UI primitives BEFORE implementation lands
Plan 05-01 ships skip-guarded test classes (`pytest.mark.skipif(not _has("top_skills"), ...)`) and 4 frontend vitest stubs (`describe.skipIf(!TopSkillsCard)`) BEFORE any analytics service or widget exists. When Plans 05-02 / 05-03 / 05-04 / 05-05 land their target symbols, the skip-guards flip from `True` to `False` automatically — tests transition from SKIPPED to PASSED without test edits.

**When to use:** Multi-wave phases where downstream plans depend on upstream artifacts. Eliminates the "implementation lands, no tests, find bugs in next phase" failure mode. Mirrors Phase 1 + Phase 4 Wave 0 pattern; established now as the canonical multi-wave shape.
**Source:** 05-01-PLAN.md, 05-01-SUMMARY.md

---

### Service-layer analytics module with shared `_apply_filters` helper
`src/job_rag/services/analytics.py` exports `top_skills`, `salary_bands`, `cv_match` as async functions that accept `AsyncSession` + filter kwargs and return plain dicts. They all delegate to a private `_apply_filters(stmt, *, country, seniority, remote)` helper that mutates a SQLAlchemy select with the canonical 4-value country / Seniority enum / 3-state remote filter shapes. Routes layer wraps these with Pydantic response models from `api/dashboard.py`.

**When to use:** Any new dashboard-style analytical endpoint that shares the same filter surface. Adding a new widget (e.g., "Top companies" in v1.1) becomes: write `async def top_companies(session, *, country, seniority, remote)`, call `_apply_filters` once, return dict. The route handler is a 10-line thin wrapper.
**Source:** 05-02-PLAN.md, 05-02-SUMMARY.md (patterns-established)

---

### Hybrid SQL pre-filter + Python fold for fuzzy-matching aggregations
`cv_match` uses SQL `_apply_filters` + `selectinload(JobPostingDB.requirements)` to narrow postings, then Python folds `match_posting()` per posting (preserves the alias-aware fuzzy skill matching that cannot trivially be SQL). `selectinload` avoids N+1 (Pitfall 14).

**When to use:** Any analytical surface where the aggregation logic uses domain-aware matching that resists pure SQL (alias tables, fuzzy comparison, scoring formulas). At v1 corpus size (~108 postings) the Python fold is sub-millisecond; revisit at >1000 rows. Mirrors the existing `/gaps` handler shape.
**Source:** 05-02-PLAN.md, 05-02-SUMMARY.md

---

### Dashboard widget 4-state branch render contract
Each widget implements: `isPending → Skeleton (role=status aria-label=Loading X)`; `isError → Alert variant=destructive + describeError(error)`; `data && empty → EmptyState`; `data && non-empty → main view`. Footer rendered iff `data && !isError` (so it renders during loading transition out).

**When to use:** Every widget on the dashboard surface and any future analytical widget. The pattern is identical across TopSkillsCard / SalaryBandsCard / CvVsMarketCard so scaffolding new widgets in Plan 05-06+ is mechanical. Shared `describeError` helper in `errors.ts` centralizes safe error message extraction (returns `err.message` or fallback `"Unexpected error. Reload the page or try again later."`).
**Source:** 05-05-SUMMARY.md (tech-stack patterns), 05-VERIFICATION.md

---

### Hermetic widget test pattern: `vi.mock('@/api/jobs')` + QueryClientProvider with `retry: false` + MemoryRouter wrapper
Even when a single widget only calls one fetcher, `vi.mock('@/api/jobs')` must return all 3 (`topSkills` / `salaryBands` / `cvVsMarket`) because the module exports them all. The unused mocks are `vi.fn()` no-ops. Per-test, override the relevant mock via `mockResolvedValue` / `mockRejectedValue` / never-resolving promise (for `isPending` testing).

**When to use:** Any widget test that exercises a TanStack Query + fetcher combo. `retry: false` on the QueryClient prevents tests timing out on error-state tests; MemoryRouter wrapper supplies the `useSearchParams` substrate the `useDashboardFilters` hook needs.
**Source:** 05-05-SUMMARY.md (patterns-established)

---

### OpenAPI named-schema via explicit `response_model=...` drives clean openapi-typescript codegen
Each `@router.get("/dashboard/X")` handler declares `response_model=DashboardXResponse` (Pydantic class from `api/dashboard.py`). FastAPI emits a `$ref` to `#/components/schemas/DashboardXResponse` in the OpenAPI; openapi-typescript codegens a named TS interface `components['schemas']['DashboardXResponse']` instead of an inline `dict[str, Any]` shape.

**When to use:** Every new FastAPI route that returns structured data. The named-schema codegen path makes frontend types stable across backend changes (a new field on the Pydantic model auto-propagates to TS without hand-editing types); the inline-dict path requires frontend handcoding and drifts silently.
**Source:** 05-03-PLAN.md, 05-03-SUMMARY.md (tech-stack patterns)

---

### Deterministic OpenAPI snapshot capture via in-process `app.openapi()` (no port binding)
Regenerate `frontend/openapi.snapshot.json` via a one-liner Python script: `from job_rag.api.app import app; Path('frontend/openapi.snapshot.json').write_text(json.dumps(app.openapi(), indent=2) + '\n')`. Back-to-back captures diff-clean. Plan 04-01 established the pattern; Plan 05-03 confirmed determinism continued.

**When to use:** Anytime the OpenAPI surface changes. Avoids the uvicorn-boot + curl + port-collision dance. CI smoke step (Phase 1 Plan 01-06) re-runs the capture and diffs against the committed file — drift = build red. Pydantic v2's JSON Schema emitter is deterministic for the app surface; no canonicalization needed.
**Source:** 05-03-PLAN.md, 05-03-SUMMARY.md (Determinism note)

---

### UAT.md template: frontmatter + M-marker tables + Roadmap Success-Criteria Map + Overall Verdict + Deviations
6 numbered M-markers (each with a property table + verdict cell + screenshot reference + notes), a Roadmap Success-Criteria Map mapping markers to ROADMAP criteria, an Overall Phase Verdict line, and a Deviations section triaging any FAIL or polish candidates. Screenshots go in `.planning/phases/XX-NAME/uat-screenshots/` (gitignored).

**When to use:** Every phase close-out that has user-visible surface to verify against a live deployed stack. Reusable for Phase 6 (Chat) and Phase 7 (Profile) UATs. The marker count scales with surface complexity (Phase 5 used 6; simpler phases may use 3-4).
**Source:** 05-06-PLAN.md, 05-06-SUMMARY.md (patterns-established), 05-UAT.md

---

## Surprises

### EU ≡ WW because the corpus is entirely EU-sourced
Country filter outputs for EU and WW returned identical numbers (PL + DE = 88 postings ≡ EU = 88 ≡ WW = 88). Initially looked like a SQL bug. Investigation confirmed the corpus is curated EU-only; the country filter is correctly implemented (D-07 EU branch correctly aggregates all EU-27 ISO codes + `location_region='EU'` Worldwide-remote catch-all).

**Impact:** No code change. Tracked as Phase 8 polish candidate to add a "(corpus is EU-only)" hint under the country dropdown. Important to document because a viewer not familiar with the corpus shape would assume the country filter is broken. The M2 canary success depended on PL vs DE differing (which they did, on every column).
**Source:** 05-UAT.md (M2 Documented findings #2), 05-06-SUMMARY.md

---

### Polish PLN salary p50 of €793,440/yr (currency normalization bug)
M2 Country=PL returned p50 €793,440/yr. PLN 793,440 ≈ €185k/yr at 2026 FX — implausibly high for Polish AI-Engineer roles even after conversion. Confirmed by contrast: German p50 €67,500/yr is realistic (postings priced natively in EUR). The EU and WW p50 (€684,864/yr) is also inflated because Polish PLN outliers pull the percentile up.

**Impact:** Already documented in PROJECT.md §Constraints as a v1 limitation ("salary values treated as EUR; FX-aware conversion is a v2 platform feature"). Deferred — visible inflated number is a tolerable signal to the v1 user (Adrian) and doesn't block his Berlin/German target use case. The bug pattern: analytics treats raw `salary_min` as EUR regardless of source currency; likely fix sites are `extractor.py` (normalize at write time) or `analytics.salary_bands` (FX lookup at query time).
**Source:** 05-UAT.md (M2 Documented findings #1), 05-06-SUMMARY.md (Decisions)

---

### N=1 salary-bands rendering is degenerate (Recharts BarChart collapses with clipped labels)
M3's deep-link filter combo (`country=DE&seniority=senior&remote=remote`) matched 5 postings, of which only 1 had salary data. The Recharts BarChart rendered under-resolved bars with labels truncating at the card top. The number itself is correct; the chart shape is visually broken.

**Impact:** No data integrity issue. Tracked as Phase 8 polish candidate: when `postings_with_salary <= 1`, render an EmptyState chip with the literal number instead of the degenerate chart. Surface this pattern as a class of "chart-vs-statistic" decision — bar charts assume N >= 2 for meaningful comparison; fall back to a single statistic when N is too small.
**Source:** 05-UAT.md (M3 Notes), 05-06-SUMMARY.md (Decisions)

---

### Auth bug masked by Phase 4 placeholders surfaced as a 429 rate-limit cascade in Phase 5 UAT
Dashboard widgets returned 429 within 1-2 minutes of mount on the morning UAT attempt. Symptoms pointed at rate limits and React Query retries. Two reasonable mitigations (`fbf82c6`, `8c8037a`) reduced but did not eliminate the cascade. The actual root cause was two levels deeper: `_expected_issuer()` was rejecting all valid tokens because of an `iss` subdomain mismatch with Entra External ID's actual issuer format. The 429 was downstream — `authedFetch`'s 401-retry path called `acquireTokenRedirect`, triggering a page-level redirect loop; each iteration fired 3 widget queries → ~39 requests in 3.5s → rate-limit bucket exhausted.

**Impact:** Three hotfix commits before UAT could pass (`fbf82c6` rate limit bump, `8c8037a` skip 4xx retries, `ab9437d` root cause subdomain fix). `ab9437d` is load-bearing; the other two retained as defense-in-depth. Phase 5 ended up incidentally validating Phase 4's auth path as well — useful side effect, but a heavy cost paid in UAT time (entire morning lost). Lesson: phase verification should probe at least one real authenticated round-trip per endpoint shape, even if downstream features are placeholders.
**Source:** 05-UAT.md (Issues Found During UAT), 05-06-SUMMARY.md (Issues Encountered)

---

### Mysterious `GET /` 404s every 10-20s from ACA's egress IP, observed but never identified
During UAT, the ACA logs showed unexplained `GET /` 404 hits every 10-20 seconds from what appeared to be ACA's egress IP. Not investigated to root cause; suspected benign infra polling (health probe from Azure Front Door or container scaler), but never confirmed.

**Impact:** No functional effect on Phase 5 UAT (the 404s are for `/`, not `/dashboard/*`, and don't count against the dashboard's rate limit). Documented here so future phases that look at logs aren't surprised. Possible Phase 8 investigation: trace via ACA log query to identify the source IP and the calling user-agent. If it's Azure Monitor scheduled health-check or a misconfigured ACA probe, the 404s are noise; if it's an external scanner, it's worth filing a Defender alert.
**Source:** Session context (observed during UAT; not formally documented in artifacts)

---

### Recharts theme swap via `var(--chart-1)` works but is visually subtle under the radix-nova preset
M5 theme toggle test confirmed the Recharts BarChart bar color swaps via CSS variable. However, the radix-nova `--chart-1` preset resolves to a neutral gray (gray-dark in dark mode, gray-light in light mode) rather than a vibrant accent color, so the swap is functionally correct but visually understated.

**Impact:** Marked as PASS for M5 (functionality verified). Tracked as Phase 8 polish candidate to bump `--chart-1` to a more saturated accent color for stronger visual signal during theme transitions. Not a blocker — Phase 4 D-20 chose radix-nova for its Linear-dense ethos which prefers grayscale + 1 accent, and the current setting honors that constraint. Surface this as a tension: a visually subtle correct-implementation can register as a UX gap during demo / portfolio review.
**Source:** 05-UAT.md (M5 Notes), 05-06-SUMMARY.md (Decisions)

---
