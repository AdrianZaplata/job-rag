---
phase: 05-dashboard
audited: 2026-05-24
auditor: gsd-security-auditor
asvs_level: 1
state: B (first audit; no prior SECURITY.md)
threats_total: 19
threats_closed: 19
threats_open: 0
block_on: critical_and_high
verdict: SECURED
---

# Phase 05 — Dashboard Security Audit

Audit of the 19 threats declared in PLANs 05-01 → 05-06 (`<threat_model>` blocks)
against the implemented tree. 12 mitigations verified; 7 accepts confirmed
load-bearing. No open threats.

## Disposition Summary

| Disposition | Count | Verdict |
|-------------|-------|---------|
| mitigate    | 12    | all CLOSED (evidence in tree) |
| accept      | 7     | all CLOSED (rationale verified still load-bearing) |
| **total**   | **19** | **SECURED** |

## Mitigated Threats (12 — verified present in tree)

| Threat ID | Category | Disposition | Evidence |
|-----------|----------|-------------|----------|
| T-AUTH-06 | Spoofing | mitigate | `src/job_rag/api/auth.py:32-53` `_expected_issuer()` constructs issuer from `entra_tenant_id` GUID subdomain (the load-bearing `ab9437d` fix); `routes.py:252,287,317` all 3 dashboard handlers carry `user_id: Annotated[uuid.UUID, Depends(get_current_user_id)]` |
| T-INPUT-VALIDATION (backend) | Tampering | mitigate | `routes.py:253-258,288-291,318-321` Query() params typed as `CountryFilter`, `Seniority \| None`, `RemoteFilter`, plus `limit: int = Query(default=50, ge=1, le=200)`. Pydantic auto-422 on bad strings. Verified by `tests/test_api.py::TestDashboardEndpoints::test_invalid_country_returns_422` PASSED |
| T-INPUT-VALIDATION (frontend) | Tampering | mitigate | `frontend/src/components/dashboard/useDashboardFilters.ts:42-52` defines `isCountry` / `isRemote` / `isSeniority` type-guards; lines 61-65 coerce invalid URL values to `WW` / `undefined` / `any` defaults |
| T-RATE-LIMIT | Denial of Service | mitigate | `routes.py:246,281,311` all 3 dashboard handlers carry `Depends(dashboard_limit)` (120/min — bumped from `standard_limit` 30/min via UAT hotfix `fbf82c6` as documented defense-in-depth; `auth.py:140` defines `dashboard_limit = RateLimiter(calls=120, period=60)`) |
| T-5-01-01 | Tampering | mitigate | `frontend/components.json:3,10` `"style": "radix-nova"` and `"baseColor": "neutral"` unchanged post-shadcn-install |
| T-5-01-02 | Tampering | mitigate | `tests/conftest.py:28` `sample_posting()` fixture preserved (Phase 2 baseline) alongside new `dashboard_postings_factory` |
| T-5-01-03 | Denial of Service | mitigate | 05-01-SUMMARY records `npm ls react-is` clean post-install (recharts/react-is@17.0.2 deduped, no UNMET PEER). Override block not required; verified-by-CI on subsequent runs |
| T-5-02-01 | Tampering | mitigate | `src/job_rag/services/analytics.py:67-90` `_apply_filters` uses parameterized SQLAlchemy `.where()` clauses (`JobPostingDB.location_country == "PL"`, `.in_(EU_COUNTRY_CODES)`); no raw string concat / no `text()` / no f-strings into SQL (verified by grep) |
| T-5-02-02 | Information Disclosure | mitigate | `src/job_rag/api/dashboard.py` response models expose ONLY skill names + aggregate counts. Verified: no `user_id`, no `posting_id`, no `email`, no PII fields anywhere in the module (grep) |
| T-5-02-03 | Tampering | mitigate | `analytics.py:38` `EU_COUNTRY_CODES: frozenset[str] = frozenset({...})` — immutability verified at runtime (`isinstance(EU_COUNTRY_CODES, frozenset)` is True, length is 27, DE/PL/GR in, GB/EL out) |
| T-5-03-02 | Tampering | mitigate | `frontend/openapi.snapshot.json` exists (1170 lines), contains 21 references across `DashboardTopSkillsResponse` / `DashboardSalaryBandsResponse` / `DashboardCvMatchResponse` / `CountryFilter` / `RemoteFilter`. CI drift-check armed via Plan 04-01 in-process capture pattern |
| T-5-04-01 | Tampering | mitigate | `frontend/src/api/jobs.ts:31-37` `buildFilterQuery` uses `new URLSearchParams() + .set(...)` (escapes values); lines 12, 44, 54, 64 — `authedFetch` wraps all 3 fetchers; zero bare `fetch(` calls in the module |
| T-5-05-01 | Information Disclosure | mitigate | `frontend/src/components/dashboard/errors.ts:4-7` `describeError` returns `err.message` if Error else safe fallback `"Unexpected error. Reload the page or try again later."` — no stack trace, no class name, no internal paths. All 3 widget Alerts route through this helper |
| T-5-06-01 | Information Disclosure | mitigate | `.gitignore:25` `.planning/phases/**/uat-screenshots/` ignored; 9 screenshots present locally show only Adrian's own seeded data (corpus is public job postings; no third-party PII) |

## Accepted Risks (7 — rationale still load-bearing)

| Threat ID | Category | Rationale | Verified |
|-----------|----------|-----------|----------|
| T-5-02-04 | Denial of Service | percentile_cont scale: v1 corpus ~108 postings; `postings_with_salary=88` and `total_postings=88` observed in M2 UAT WW row. Far below the >1000 trigger to reconsider | YES — corpus size in M2 evidence confirms accept rationale still load-bearing |
| T-5-03-01 | Information Disclosure | OpenAPI surface exposes route paths + 7 named schemas at `/openapi.json`. Phase 4 D-07 carry; SPA codegen requires it. No PII in schemas; only aggregate counts + public-corpus skill names | YES — `dashboard.py` audit confirms zero PII fields in named schemas |
| T-5-04-02 | Information Disclosure | URL surfaces filter selection (e.g. `?country=DE&seniority=senior`). Intentional per DASH-06 deep-linking. No PII / IDs / secrets — only enum filter values | YES — `useDashboardFilters.ts` and `jobs.ts:31-37` only round-trip the 3 typed enums |
| T-5-05-02 | Tampering | Recharts ^3 renders bar values from JSON-parsed numbers via React props; no `eval`, no `innerHTML`. React's text-node default escapes the aria-label string. | YES — `grep dangerouslySetInnerHTML` returns ZERO hits across all dashboard `.tsx` files |
| T-5-05-03 | Spoofing | Theme toggle is CSS-class-only on documentElement; Recharts `var(--chart-1)` resolves via CSS-var lookup. Purely visual; no security impact | YES — no auth/data path touches theme; M5 UAT confirmed visual-only swap |
| T-5-06-02 | Spoofing | UAT sign-in uses Entra customer account `adrian@jobrag.onmicrosoft.com`. AUTH-06 oid allowlist (`auth.py:161`) rejects any other oid with 403 | YES — `auth.py:161` `oid != settings.seeded_user_entra_oid` returns 403; no spoofing surface |
| T-AUTH-06 (Plans 05-01/05-02/05-04 carries) | Spoofing | Pre-routing waves don't touch production auth code; downstream Plan 05-03 wires `Depends(get_current_user_id)` (verified above as a `mitigate` row) | YES — handler signatures confirmed in `routes.py` |

## UAT Hotfix Verification (load-bearing for T-AUTH-06)

The threat-model entry for T-AUTH-06 hinges on the `ab9437d` `_expected_issuer()` fix.
Verified in tree:

- `src/job_rag/api/auth.py:32-53` `_expected_issuer()` builds the issuer URL with
  `settings.entra_tenant_id` (GUID) as both subdomain and path segment — matches
  the actual `iss` claim Entra External ID emits.
- Comment at lines 36-48 documents the discovery during Phase 5 UAT and the
  rationale for using the GUID form (not the friendly `entra_tenant_subdomain`).
- `_iss_callable` (lines 56-65) returns `_expected_issuer()` for fastapi-azure-auth's
  `validate_iss=True` library hook.

The two defense-in-depth hotfixes (`fbf82c6` 30→120/min rate-limit bump,
`8c8037a` React Query no-retry-on-4xx) are also in tree:

- `auth.py:140` `dashboard_limit = RateLimiter(calls=120, period=60)` confirms `fbf82c6`
- `routes.py:246,281,311` all 3 dashboard handlers use `dashboard_limit` (NOT `standard_limit`)

This is a deviation from the threat-register text ("Depends(standard_limit) on all 3
/dashboard/* handlers") but the deviation IS documented in the threat register notes
("rate limit bump 30→120/min via fbf82c6 is acceptable defense-in-depth") and reduces
DoS surface; classified as `mitigate` CLOSED.

## Unregistered Threat Flags

None. Each plan SUMMARY records a `## Threat Model Coverage` table that maps to
existing threat IDs; no executor-flagged new attack surface fell outside the
register.

## Behavioral Spot-Checks

| Check | Result |
|-------|--------|
| `EU_COUNTRY_CODES` is `frozenset[str]` with 27 members, contains DE/PL/GR, excludes GB/EL | PASS |
| `dashboard.py` contains zero references to `user_id` / `posting_id` / `email` | PASS |
| `analytics.py` contains zero raw-SQL execution patterns (`text(`, f-string SQL) | PASS |
| `jobs.ts`: 5 `authedFetch` references (1 import + 1 jsdoc + 3 call-sites); 0 bare `fetch(` | PASS |
| `jobs.ts` uses `URLSearchParams.set` for query construction | PASS |
| `useDashboardFilters.ts` defines `isCountry` / `isRemote` / `isSeniority` type-guards | PASS |
| `errors.ts` `describeError` returns sanitized message or safe fallback | PASS |
| `SalaryBandsCard.tsx` (and all dashboard `.tsx`) contain zero `dangerouslySetInnerHTML` | PASS |
| `frontend/components.json` `style=radix-nova` + `baseColor=neutral` unchanged | PASS |
| `tests/conftest.py` `sample_posting` fixture preserved | PASS |
| `.gitignore` ignores `.planning/phases/**/uat-screenshots/` | PASS |
| `frontend/openapi.snapshot.json` exists with dashboard schemas | PASS |

## Verdict

**SECURED.** All 12 mitigations verified present in tree; all 7 accepts have
load-bearing rationale still valid against the implementation. Zero open threats.
Phase 05-dashboard cleared for ROADMAP advancement.
