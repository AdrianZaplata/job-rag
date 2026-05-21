# Phase 5: Dashboard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 05-dashboard
**Mode:** Auto-resolved (background session; user-locked "Recommended" pattern across Phase 4)
**Areas discussed:** Endpoint architecture, SQL aggregation, Filter semantics, CV scoring, Visualization, URL state, Layout, Loading/empty/error, Soft skills, "Show more" UX, Sample-size footnotes, Caching, Aesthetic

---

## Endpoint architecture (D-01, D-02, D-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Three independent endpoints under `/dashboard/*` | Each widget hits its own URL; parallel React Query fetches; independent caching/failure/rate-limiting | ✓ |
| One bundled `/dashboard` endpoint | Single round-trip; couples latencies; one slow widget stalls the whole page | |
| Extend existing `/gaps` to cover all three | Reuses existing route; muddles the single-purpose intent; can't independently rate-limit | |

**Rationale:** Independent caching keys + parallel fetch + per-widget failure modes won
decisively. Linear-dense ethos also prefers explicit URLs the user can curl/screenshot.

---

## Backend service module placement (D-02)

| Option | Description | Selected |
|--------|-------------|----------|
| New `src/job_rag/services/analytics.py` | New module alongside matching.py / retrieval.py; one home for the analytical concern | ✓ |
| Extend `services/matching.py` | Conflates per-posting with aggregate concerns; matching.py would grow >250 lines | |
| Inline in `api/routes.py` | Violates services-layer convention; route handler becomes 100+ lines | |

---

## SQL aggregation strategy (D-04, D-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Pure SQL for top-skills + salary-bands; hybrid SQL+Python for cv-vs-market | Top-skills uses GROUP BY + SUM CASE; salary-bands uses `percentile_cont().within_group()`; cv-vs-market SQL-fetches then Python-folds match scores per posting | ✓ |
| Pure SQL everywhere | Would require porting fuzzy alias-aware skill matching to SQL — significant scope creep, kills `_ALIAS_GROUPS` extensibility | |
| Python aggregation for all | Violates DASH-01 "no Python-side group-by"; doesn't scale | |

**Rationale:** Match-score fold is irreducibly per-row Python because of the fuzzy
matching helper. DASH-01's "no Python-side group-by" specifically targets the
TOP-SKILLS aggregation (which DOES have a SQL equivalent via `GROUP BY skill`). The
match-score fold is "iterate over already-filtered rows" — semantically different.

---

## Profile source (D-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Continue calling `load_profile()` (reads data/profile.json) | Phase 1 D-07 forward-compat shim; Phase 7 PROF-01 flips the body without call-site changes | ✓ |
| Anticipate Phase 7 + query user_profile table now | Bleeds Phase 7 scope into Phase 5; couples release cadence | |

---

## Country filter cardinality (D-07)

| Option | Description | Selected |
|--------|-------------|----------|
| 4-value enum: PL / DE / EU / WW (literal DASH-04) | Matches requirements verbatim; EU = 27 ISO codes hardcoded + region='EU' branch | ✓ |
| All-countries-in-corpus dynamic dropdown | More flexible; not in DASH-04; deferred to v2 | |
| Hardcoded short list of EU countries + "Other" | Compromise; falls into "scope creep" trap | |

---

## Seniority filter (D-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Single optional value from Seniority enum (junior/mid/senior/staff/lead); hide "unknown" | Clean single-select; "unknown" never useful as a filter (= LLM-failed extraction) | ✓ |
| Multi-select with all 5 values + unknown | Higher complexity; corpus skews senior so MS rarely helps | |
| Junior / Mid / Senior+ (3-bucket simplification) | Loses staff/lead distinction Adrian cares about for target roles | |

---

## Remote filter (D-09)

| Option | Description | Selected |
|--------|-------------|----------|
| 3-state tri-toggle: any / remote / non_remote | Linear-dense ethos: fewer affordances; matches "remote toggle" wording in DASH-04 | ✓ |
| 4-state pass-through: any / remote / hybrid / onsite | Mirrors enum but loses the "remote-or-not" insight Adrian cares about | |
| 2-state boolean toggle: any / remote-only | Loses the "anything but pure onsite" lens many job-seekers want | |

---

## CV-vs-market formula (D-10, D-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing `match_posting()` formula (0.7 must + 0.3 nice); aggregate via mean | No behavior drift from Phase 1; tests stay valid | ✓ |
| Custom Phase 5 formula (e.g. weight bonus signals more heavily) | Diverges from agent matching behavior; confuses Phase 6 chat output | |
| Match-percentage over weighted score | Hides nice-to-have weighting; less expressive | |

---

## Zero-postings edge case (D-12)

| Option | Description | Selected |
|--------|-------------|----------|
| Return `{ mean_score: null, postings_compared: 0, top_missing_must_have: [] }`, HTTP 200 | Widget renders empty-state; UI logic stays uniform across all 3 widgets | ✓ |
| 404 with "no matching postings" | Forces special error-vs-empty handling; ugly UX | |
| Return last successful result with stale flag | TanStack Query handles staleness; backend stale-protocol is overengineering | |

---

## Visualization library (D-14, D-15)

| Option | Description | Selected |
|--------|-------------|----------|
| Single chart lib (shadcn `chart` / Recharts) for salary-bands only; Tailwind bars + big-text elsewhere | Minimum chart-lib use; ~93 KB only buys real value once | ✓ |
| Recharts everywhere | Heavier, but uniform styling; overkill for top-skills bar list | |
| visx (lower-level d3) | More flexible; significantly higher integration cost | |
| Pure Tailwind / no chart lib | Salary-band visualization is worse without proper axis ticks | |

**Rationale:** Linear-dense aesthetic prefers number-forward over chart-forward. One
chart where it earns its weight; everywhere else, numerics + sparse bars.

---

## URL state management (D-17)

| Option | Description | Selected |
|--------|-------------|----------|
| `useSearchParams` + typed `useDashboardFilters` wrapper hook | Vanilla RR v7; lightweight; type safety at hook boundary | ✓ |
| Migrate to TanStack Router for typed search params | Major migration; 4 routes don't justify (Phase 4 D-17 deferred) | |
| Zustand / Redux for filter state | Server URL is the source of truth — adding client store fragments state | |

---

## Layout (D-18)

| Option | Description | Selected |
|--------|-------------|----------|
| 3-up grid on `md+`, single column on mobile | Linear-dense scales horizontally; gives each widget breathing room | ✓ |
| 2 + 1 layout (top-skills full-width, salary + cv-match below) | Top-skills gets emphasis but breaks horizontal rhythm | |
| Vertical stack always | Wastes desktop width | |

---

## Loading / empty / error states (D-19)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-widget skeletons + per-widget empty states + per-widget error fallbacks | One widget erroring doesn't kill others; composability over special cases | ✓ |
| Whole-page error banner + whole-page skeleton | Couples failure modes; one stuck request blocks dashboard | |
| Inline error toasts via sonner (Phase 4 primitive) | Less discoverable than in-card alert; widget body stays useless | |

---

## Soft-skill default (D-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden by default, no UI toggle; `?include_soft=true` accepted at API for future | DASH-01 wording is exactly this; UI YAGNI for v1 since corpus is already filtered | ✓ |
| Hidden by default + UI toggle "Include soft skills" | Adds affordance Adrian explicitly de-prioritized | |
| Shown by default, "Hide soft" toggle | Inverts DASH-01 default | |

---

## "Show more" UX (D-20)

| Option | Description | Selected |
|--------|-------------|----------|
| shadcn `Dialog` modal opens with full ranked list (50 skills cap) | Dialog primitive already landed in Phase 4; modal scoped to one task | ✓ |
| Drawer (slide-in from right) | Needs new shadcn primitive; no clear win | |
| Separate page route (`/dashboard/top-skills`) | Adds route surface for a transient view | |
| Inline expand-in-place | Forces page layout shift; loses 3-up grid integrity | |

---

## Sample-size footnotes (D-21)

| Option | Description | Selected |
|--------|-------------|----------|
| Every widget shows its `n` in card footer | Visual proof filters flow through to SQL; DASH-02 footnote literal | ✓ |
| Only salary-bands shows N/M (per DASH-02) | Underutilizes the trust-building affordance | |
| Hide N's; show only on hover via tooltip | Less discoverable; trust signal hidden | |

---

## TanStack Query caching (D-22)

| Option | Description | Selected |
|--------|-------------|----------|
| `staleTime: 5 * 60_000` per dashboard query | Analytical data changes rarely; reduces Postgres load on filter-toggling | ✓ |
| Use global 30s default from queryClient | Hammers Postgres on every filter change | |
| `staleTime: Infinity` + manual invalidation | Stale data after corpus reingest unless someone remembers to invalidate | |

---

## Visual style (D-23)

| Option | Description | Selected |
|--------|-------------|----------|
| Linear-dense: number-forward, sparse bars, minimal chrome | Matches Phase 4 D-20 + PROJECT.md aesthetic decision | ✓ |
| Stripe-polish: animated charts, gradient fills | Out of style band for the project | |
| Pure-text dashboard (no charts) | Salary-band visualization is worse this way | |

---

## Claude's Discretion

The following areas were resolved with reasonable defaults (no explicit user choice):
backend route file placement (extend routes.py), OpenAPI tag, query parameter parsing
style (FastAPI `Query`), salary period normalization (month→year ×12, drop hour),
Recharts theme via CSS vars, test placement, test data (real 98 postings, no synthetic
seed), filter bar reuse, alias-index inheritance (empty per Phase 1), EU-27 list source,
currency assumption, pagination (cap-50 top-skills only), responsive breakpoints,
accessibility patterns, empty filter combos UX.

## Deferred Ideas

See CONTEXT.md `<deferred>` section for the 15+ ideas surfaced and explicitly punted to
v2 / later phases (interactive cross-filtering, skill co-occurrence, time-series trends,
per-posting drill-down, soft-skill toggle UI, all-countries dropdown, hourly salary
normalization, currency FX, modal pagination, widget order, CSV/PNG export, always-warm
ACA, response-model filename, /gaps replacement, Phase 04.1 interaction).
