---
phase: 4
slug: frontend-shell-auth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-19
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

Phase 4 spans two stacks (frontend SPA + backend FastAPI) — both must remain green at every wave gate.

### Frontend

| Property | Value |
|----------|-------|
| **Framework** | Vitest 3.x + @testing-library/react + jsdom |
| **Config file** | `frontend/vite.config.ts` (`test:` block) — does not exist yet; installed in Wave 0 |
| **Quick run command** | `cd frontend && npm run test -- --run` |
| **Full suite command** | `cd frontend && npm run typecheck && npm run lint && npm run test -- --run && npm run codegen && git diff --exit-code src/api/types.ts` |
| **Estimated runtime** | ~30 s quick · ~3 min full |

### Backend

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio + httpx + asgi-lifespan (existing per Phase 1) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_auth.py tests/test_alembic.py -x` |
| **Full suite command** | `uv run ruff check src/ tests/ && uv run pyright src/ && uv run pytest -m 'not eval'` |
| **Estimated runtime** | ~30 s quick · ~3 min full |

---

## Sampling Rate

- **After every task commit:** Run the matching quick run for the stack touched — `cd frontend && npm run test -- --run` (frontend) or `uv run pytest tests/test_auth.py tests/test_alembic.py -x` (backend).
- **After every plan wave:** Run the full suite for whichever stack the wave touched (frontend full or backend full above); if a wave crosses both stacks, run both.
- **Before `/gsd-verify-work`:** Both full suites green **and** manual e2e sign-offs captured for AUTH-04 and AUTH-07.
- **Max feedback latency:** 30 s (quick run target).

---

## Per-Task Verification Map

Phase 4 plans/task IDs are assigned by the planner across ~4 waves. This table is rendered per-requirement; the planner maps each REQ-ID to one or more task IDs and inherits the Test Type / Automated Command / Threat Ref / Status from this row.

| Req ID | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| SHEL-01 | Vite + React + TS scaffolds, builds | — | N/A (scaffolding) | smoke | `cd frontend && npm run build` | ❌ W0 | ⬜ pending |
| SHEL-02 | shadcn theme applies; Geist Sans loads; tailwind builds | — | N/A (visual) | smoke + manual visual | `cd frontend && npm run build` + manual visual check | ❌ W0 | ⬜ pending |
| SHEL-03 | TanStack QueryClient mounts; useQuery composes | — | N/A | unit | `cd frontend && npm run test -- queryClient` | ❌ W0 | ⬜ pending |
| SHEL-04 | AppShell renders nav links Dashboard/Chat/Profile | — | N/A | unit | `vitest run tests/AppShell.test.tsx` | ❌ W0 | ⬜ pending |
| SHEL-05 | authedFetch attaches Bearer; 401 triggers retry-after-silent-refresh | Stolen JWT replay / Backend bypassed via direct API call | Bearer attached on every authed call; 401 forces silent token refresh (no anon retry); no token logged | unit | `vitest run tests/authedFetch.test.ts` | ❌ W0 | ⬜ pending |
| SHEL-06 | RouteSkeleton renders during Suspense; ErrorBoundary catches throw; EmptyState typed contract enforced | — | N/A | unit + smoke | `vitest run tests/RouteSkeleton.test.tsx tests/ErrorBoundary.test.tsx tests/EmptyState.test.tsx` + visual check on `/dashboard` | ❌ W0 | ⬜ pending |
| AUTH-01 | Tenant exists, MSAL authority reaches it | Wrong-tenant JWT accepted | OpenID discovery resolves on the CIAM authority used by both SPA + backend | smoke (manual) | `curl https://${subdomain}.ciamlogin.com/${tenant_id}/v2.0/.well-known/openid-configuration` returns JSON | — (Phase 3 D-05 verified) | ⬜ pending |
| AUTH-02 | SPA app reg has SPA platform, PKCE green check | XSS exfiltrates token from sessionStorage / Stolen JWT replay | SPA platform forces PKCE auth-code flow (no implicit grant tokens leaked via URL fragment) | smoke (manual portal) | Adrian visual-verify after `terraform apply` in `infra/external/` | ❌ W0 | ⬜ pending |
| AUTH-03 | API app reg exposes `access_as_user` scope | Backend bypassed via direct API call from another origin | API audience scope is the only one minted into JWT `aud`; backend rejects other audiences | smoke (manual portal) | Adrian visual-verify | ❌ W0 | ⬜ pending |
| AUTH-04 | Unauthenticated visit → loginRedirect | MSAL flash-of-login (UX-as-attack-surface) | No protected route paints before MSAL state resolves; redirect lands on real CIAM authority | manual e2e | (manual — see Manual-Only Verifications) | manual-only | ⬜ pending |
| AUTH-05 | Backend rejects missing/invalid/wrong-audience JWT | Wrong-tenant JWT accepted / Stolen JWT replay / Backend bypassed via direct API call | Signature + iss + aud + exp validated by `B2CMultiTenantAuthorizationCodeBearer`; 401 on any failure before handler runs | unit + integration | `uv run pytest tests/test_auth.py::TestEntraJwtValidation` (unit with mocked azure_scheme); integration via curl + valid token mint | ❌ W0 | ⬜ pending |
| AUTH-06 | Wrong-oid JWT → 403 user_not_allowlisted | User-not-allowlisted reaches business logic / Multi-user reveals existing oid via 403 message | Allowlist check is single trust boundary in `get_current_user_id()`; 403 returns generic literal `user_not_allowlisted`; rejected oid only in structlog (LAW audit) | unit | `uv run pytest tests/test_auth.py::TestOidGuard` | ❌ W0 | ⬜ pending |
| AUTH-07 | Hard refresh while logged-in → no login flash | MSAL flash-of-login (UX-as-attack-surface) | `handleRedirectPromise` resolves before first paint; URL bar never transits ciamlogin authority | manual e2e | (manual — see Manual-Only Verifications) | manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/` directory itself (scaffolded by D-01)
- [ ] `frontend/package.json` + `frontend/package-lock.json` (npm init via Vite template)
- [ ] `frontend/vite.config.ts` with Vitest config
- [ ] `frontend/src/test/setup.ts`
- [ ] `tests/AuthGate.test.tsx`, `tests/authedFetch.test.ts`, `tests/readSSEStream.test.ts`, `tests/ThemeToggle.test.tsx`, `tests/AppShell.test.tsx`
- [ ] `tests/test_entra_jwt.py` (backend) — `TestEntraJwtValidation`, `TestOidGuard`, integration with mocked azure_scheme via `dependency_overrides`
- [ ] `pyproject.toml` += `fastapi-azure-auth>=5.2,<6.0`
- [ ] `src/job_rag/config.py` += 4 new fields (`entra_tenant_id`, `entra_tenant_subdomain`, `backend_audience`, `seeded_user_entra_oid`)
- [ ] `alembic/versions/0005_adopt_entra_oid.py`
- [ ] `infra/external/` directory + 5 .tf files + README
- [ ] `frontend/.env.local` template (gitignored — Adrian fills) + `frontend/.env.production` (committed placeholders)
- [ ] `.github/workflows/ci.yml` — add `frontend-ci` job
- [ ] `.github/workflows/deploy-spa.yml` — add `VITE_*` env block + change `apps/web/` → `frontend/`
- [ ] GitHub repo secrets: `VITE_TENANT_SUBDOMAIN`, `VITE_TENANT_ID`, `VITE_SPA_CLIENT_ID`, `VITE_API_AUDIENCE`, `VITE_API_BASE_URL`
- [ ] `scripts/refresh-external-outputs.sh` (mirrors `scripts/refresh-swa-origin.sh` shape)
- [ ] `frontend/openapi.snapshot.json` (initial snapshot of current `/openapi.json`) — drift-guard reference

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Unauthenticated visit → loginRedirect | AUTH-04 | Requires a real browser navigation from an unsigned-in browser state; MSAL `loginRedirect` cannot be exercised end-to-end in jsdom (no real `window.location` redirect to a remote authority). | 1. Open the deployed SWA URL in a fresh **private / incognito** window (no MSAL cache).<br>2. Within ~1 s, browser should issue a 302 to `https://${subdomain}.ciamlogin.com/${tenant_id}/v2.0/oauth2/v2.0/authorize?...`.<br>3. Confirm the URL bar shows the CIAM authority before any app chrome paints.<br>4. ✅ pass if redirect occurs within 1 s and no protected route content was rendered first. |
| Hard refresh while logged-in → no login flash | AUTH-07 | Reproduces a race condition between `handleRedirectPromise` and first paint; reliable repro needs real browser timing under throttled network — jsdom cannot model this. | 1. Log in normally and land on `/dashboard`.<br>2. Open DevTools → **Network** tab → set **Throttling = Slow 3G**.<br>3. Hit cmd+R (hard refresh) on `/dashboard`.<br>4. Watch the URL bar throughout the reload.<br>5. ✅ pass if the URL bar **never** transits `*.ciamlogin.com` and the page repaints directly on `/dashboard` with no visible login-form flash. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] Manual e2e sign-offs captured for AUTH-04 + AUTH-07
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
