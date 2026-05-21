---
phase: 5
slug: dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `05-RESEARCH.md` §"Validation Architecture"; the planner
> fills the Per-Task Verification Map once tasks are assigned plans.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 9.0.3+ + pytest-asyncio (existing) |
| **Framework (frontend)** | Vitest 3.x + Testing Library + jsdom (existing, Phase 4) |
| **Config file (backend)** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Config file (frontend)** | `frontend/vitest.config.ts` (Phase 4 Plan 04-04) |
| **Quick run command (backend)** | `uv run pytest tests/test_analytics.py -x` |
| **Quick run command (frontend)** | `cd frontend && npm test -- --run <touched-file>` |
| **Full suite command (backend)** | `uv run pytest -x` |
| **Full suite command (frontend)** | `cd frontend && npm test -- --run` |
| **Estimated runtime (full)** | ~120 seconds combined (~80s backend, ~40s frontend) |

---

## Sampling Rate

- **After every task commit:** Run quick run command for whichever side (backend/frontend) the task touches.
- **After every plan wave:** Run full suite both sides + `cd frontend && npm run typecheck && npm run lint && npm run build`.
- **Before `/gsd-verify-work`:** Full suite must be green; manual UAT runbook must be exercised.
- **Max feedback latency:** ~80 seconds (backend) / ~40 seconds (frontend) per task commit.

---

## Per-Task Verification Map

> The planner agent populates this table as plans 05-01 … 05-NN are emitted.
> Initial scaffold rows below are seeded from RESEARCH.md §"Phase Requirements → Test Map".

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 0 | DASH-01..06 + SHEL-03/06 | — | n/a | scaffold | `uv run pytest -k analytics --collect-only` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DASH-01 | T-AUTH-06 (carry) | `Depends(get_current_user_id)` rejects unauthed | unit | `pytest tests/test_analytics.py::TestTopSkills -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DASH-02 | T-AUTH-06 (carry) | `Depends(get_current_user_id)` rejects unauthed | unit | `pytest tests/test_analytics.py::TestSalaryBands -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DASH-03 | T-AUTH-06 (carry) | `Depends(get_current_user_id)` rejects unauthed | unit | `pytest tests/test_analytics.py::TestCvMatch -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DASH-01..04 (filter sanity) | — | Filter values validated at Pydantic boundary; no raw client strings in SQL | integration | `pytest tests/test_analytics.py::TestFilterEffects -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DASH-01..03 (API contract) | — | Each endpoint returns named Pydantic response model | integration | `pytest tests/test_api.py::TestDashboardEndpoints -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | DASH-04, DASH-05 | — | Filter bar + 3 widgets render | unit | `cd frontend && npm test -- --run dashboard` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | DASH-06, SHEL-03 | — | `useDashboardFilters` deep-link + default-elision + 5-min staleTime | unit | `cd frontend && npm test -- --run useDashboardFilters` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SHEL-06 | — | Per-widget skeleton / empty / error branches | unit | `cd frontend && npm test -- --run "*Card.states"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 lands BEFORE Wave 1/2 implementation and seeds the test scaffolds so each
subsequent wave can flip its skip-guards off as code lands. This mirrors Phase 1/4
Wave 0 pattern (`importlib.import_module` + `hasattr` skip-gates).

- [ ] `tests/test_analytics.py` — NEW. Skip-guarded test classes for `TestTopSkills`,
      `TestSalaryBands`, `TestCvMatch`, `TestApplyFilters`, `TestEuCountrySetMembership`,
      `TestFilterEffects`. Each class skips cleanly until `src/job_rag/services/analytics.py`
      exports the target symbol.
- [ ] `tests/test_api.py` — extend with `TestDashboardEndpoints` class mirroring the
      existing `TestMatchEndpoint` / `TestGapsEndpoint` shape (auth-override fixture +
      shape assertions + 3 country values exercise filter). Skip-guarded on router
      symbol presence.
- [ ] `tests/conftest.py` — extend with a `dashboard_postings_factory` fixture that
      builds a small set of `JobPostingDB` rows covering: DE/PL/EU/WW · salary/no-salary ·
      seniority variety · `skill_category` variety (hard/soft/domain mix). Reuses the
      Phase 2 `sample_posting` pattern.
- [ ] `frontend/src/components/dashboard/__tests__/*.test.tsx` — Vitest + RTL component
      tests per widget (TopSkillsCard / SalaryBandsCard / CvVsMarketCard /
      DashboardFilters). Skip-on-missing via TS-safe string-concat import (Plan 04-04 pattern).
- [ ] `frontend/src/components/dashboard/useDashboardFilters.test.ts` — hook test with
      `MemoryRouter` covering deep-link reading + default-elision writing. Skip-guarded
      on hook export.

*(No framework install needed — Vitest + RTL + pytest already configured by Phase 1/4.)*

---

## Edge Cases — MUST be covered

> From RESEARCH.md §"Edge Cases to Cover Explicitly". Each one MUST have an automated
> test row above (or a Manual-Only entry below). Planner audits this list against the
> Per-Task Verification Map before plans pass the checker.

| # | Edge case | Test surface | Why it matters |
|---|-----------|--------------|----------------|
| E1 | Empty filter result (e.g. `country=PL&seniority=staff` → 0 postings) | backend + frontend | D-12 zero-postings contract returns HTTP 200; per-widget EmptyState branch |
| E2 | NULL `location_country` posting (region="EU" / region="Worldwide") | backend | D-07 EU branch checks `OR location_region = 'EU'`; D-09 corpus shape |
| E3 | NULL `salary_min` posting | backend | DASH-02 footnote requires accurate `postings_with_salary` count |
| E4 | `salary_period='hour'` row | backend | excluded from percentiles (Claude's Discretion) |
| E5 | `salary_period='month'` row | backend | normalized × 12 in the SELECT |
| E6 | `skill_category='soft'` row | backend | excluded from top-skills by default; included when `?include_soft=true` |
| E7 | `?include_soft=true` query | backend | accepts and returns soft skills |
| E8 | Default elision write: `setFilters({country:'WW'})` deletes the `country` URL param | frontend hook | URL stays clean for sharing |
| E9 | Default elision read: missing `country` param → `WW` default; missing `remote` → `any` default | frontend hook | refresh-safe deep-link |
| E10 | 3 widgets fail independently (one network 500 doesn't kill the other two) | frontend | per-widget Alert; filter bar stays interactive |
| E11 | `EU` filter returns same numbers as `WW` when corpus is EU-only | backend (manual sanity) | corpus distribution canary |
| E12 | Country filter actually changes SQL (different numbers PL vs DE vs EU vs WW) | backend integration | Phase 5 success criterion #5; the canary that proves filter flows through to SQL |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live SPA renders 3 widgets with real data from dev/prod ACA | DASH-01..05 | Cross-system smoke; cold-start cost makes CI flaky | Open `https://<swa-fqdn>/dashboard` after sign-in; confirm 3 widgets render numbers within ~5s warm |
| Flipping country PL → DE → EU → WW shows genuinely different numbers across all 3 widgets | DASH-04 / Phase 5 success criterion #5 | Requires real corpus distribution; CI uses synthetic fixtures | Live click-through; eyeball the sample-size footers as the canary |
| Refresh on `/dashboard?country=DE&seniority=senior&remote=remote` preserves state without re-login flash | DASH-06, AUTH-07 (carry) | Refresh integration is a Phase 4 carry-forward, validated end-to-end | Hard-refresh the URL while signed-in |
| "Show more" Dialog displays 50-row scrollable table | DASH-05 | shadcn Dialog overflow behaviour | Click "Show more" on TopSkillsCard; confirm scroll inside DialogContent |
| Theme toggle (Phase 4 carry) still works on dashboard page | SHEL-* carry | Recharts theme via `--chart-N` CSS vars is a visual concern | Toggle theme on `/dashboard`; chart colors swap |
| Cold-start ACA first-load takes ~225s but subsequent loads <1s | n/a (documented limitation) | Production-only; documented in Phase 5 SUMMARY | Verify subsequent loads serve <1s after the first |

---

## Threat Model References

Phase 5 inherits the Phase 4 auth surface (no new threat surface). All endpoints
go through `Depends(get_current_user_id)` (Phase 4 D-08 — single-user `oid`
allowlist guard). Filter parameters are validated at the Pydantic `Query(...)`
boundary so no client-supplied string reaches SQL unfiltered.

| Threat | Mitigation | Verified by |
|--------|------------|-------------|
| T-AUTH-06 (carry-forward) | Every `/dashboard/*` endpoint requires `Depends(get_current_user_id)` | `tests/test_api.py::TestDashboardEndpoints::test_unauthed_request_returns_401` |
| T-INPUT-VALIDATION | All filter params declared as `Query(...)` with enum types (`Country`, `Seniority`, `RemoteFilter`) — Pydantic rejects unknown values with 422 | `tests/test_api.py::TestDashboardEndpoints::test_invalid_country_returns_422` |
| T-RATE-LIMIT (carry) | `Depends(standard_limit)` (30/min) on all 3 endpoints | Existing rate-limit middleware tests |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all `❌ W0` references in the Per-Task Verification Map
- [ ] No watch-mode flags (`-x` not `-f`; `npm test -- --run` not bare `npm test`)
- [ ] Feedback latency < 120s
- [ ] All 12 Edge Cases (E1..E12) mapped to either an automated row or a Manual-Only row
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (planner fills Per-Task Verification Map; checker validates against this contract)
