# Phase 4: Frontend Shell + Auth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `04-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 04-frontend-shell-auth
**Areas discussed:** Scaffold + Gap D + build-env wiring, End-to-end auth flow (MSAL + Backend JWT + AUTH-06 + OID bootstrap), API client + TanStack Query + SSE-readiness for Phase 6, Routing + protected layout + SHEL-06 + shadcn theme

---

## Scaffold + Gap D + build-env wiring

### Q1. Project location for the Vite SPA?

| Option | Description | Selected |
|--------|-------------|----------|
| `frontend/` (literal SHEL-01) | REQUIREMENTS SHEL-01 says `frontend/` explicitly; Phase 3 already established sibling top-level dirs (`infra/`, `src/`, `tests/`) without monorepo tooling. Simplest: no nx/turbo overhead for a single SPA + single API. | ✓ |
| `apps/web/` (monorepo path) | Matches the STACK.md research example exactly. Costs a turbo/nx-style workspaces decision (or an empty `apps/` dir). Plausible if Adrian later adds `apps/docs` or `apps/admin`, but YAGNI for v1. | |

**User's choice:** `frontend/` (literal SHEL-01)
**Notes:** None

---

### Q2. How are the External-tenant SPA + API app registrations created and managed (Gap D resolution)?

| Option | Description | Selected |
|--------|-------------|----------|
| `infra/external/` TF dir, local-state-only | Mirrors `infra/bootstrap/` pattern (Phase 3 D-02): own directory, own local `.tfstate` (gitignored), `azuread.external` provider runs from Adrian's local `az login` only. Idempotent re-runs + drift detection without touching CI-managed prod state. Outputs feed `prod.tfvars.local` + `frontend/.env.local`. | ✓ |
| Pure runbook: `az ad app create` script | `scripts/external-app-regs-create.sh` wraps `az ad app create` + `az ad app permission` calls; outputs JSON, Adrian pastes IDs manually. No Terraform = no drift detection, no idempotent updates. Less code but more manual. | |
| Portal-only manual creation | One-time clicks in the Entra admin center; copy IDs by hand. Lowest-tech, but no audit trail in repo. Worst fit for the portfolio-artifact framing. | |

**User's choice:** `infra/external/` TF dir, local-state-only
**Notes:** None

---

### Q3. How do MSAL config values (tenant_id, subdomain, SPA client_id, API audience, ACA FQDN) get into the SPA bundle?

| Option | Description | Selected |
|--------|-------------|----------|
| VITE_* build-time env vars | All five values are public-by-design (client IDs + audience URIs appear in JWT `iss`/`aud` claims). Vite reads `.env.local` for dev + `.env.production` for build; values bake into the bundle. Simplest path; matches Vite conventions. `.env.local` stays gitignored, `.env.production` committed (no secrets). | ✓ |
| Runtime `config.json` fetched at boot | Bundle ships value-agnostic; first thing on app boot is `fetch('/config.json')` from the SWA origin. Lets one bundle serve dev + prod with different config files. Costs an extra fetch on every cold load + a bootstrap-before-MSAL-init choreography that complicates AUTH-07. | |
| Hybrid: API base URL runtime, rest build-time | API base URL via runtime config (swap dev→prod without rebuild); MSAL config baked at build. Marginal value when Vite already handles dev/prod via `.env.*` file split. Adds two config systems for one app. | |

**User's choice:** VITE_* build-time env vars
**Notes:** None

---

### Q4. How does the API app client_id (audience) flow into the FastAPI BACKEND_AUDIENCE env var?

| Option | Description | Selected |
|--------|-------------|----------|
| Plain ACA env var | `client_id` and audience URI are JWT-claim values — explicitly public, never secret. Phase 3 D-13 reserves KV for genuine secrets. Adding `API_AUDIENCE` + `ENTRA_TENANT_ID` as plain env vars on the Container App matches the `ALLOWED_ORIGINS` pattern. | ✓ |
| KV secret + secretRef | Adds these to KV alongside actual secrets for 'consistency'. Costs an extra KV secret without any security benefit since the values are public-by-design. Pure overhead. | |
| Hardcoded constant | Bake the External tenant's audience URI into a Python literal in `config.py`. Couples backend code to the specific tenant; breaks if you ever spin a second External tenant. Worst flexibility, no benefit. | |

**User's choice:** Plain ACA env var
**Notes:** None

---

## End-to-end auth flow (MSAL + Backend JWT + AUTH-06 + OID bootstrap)

### Q5. AUTH-07 race-prevention pattern: where do MSAL `initialize()` + `handleRedirectPromise()` run?

| Option | Description | Selected |
|--------|-------------|----------|
| Top of `main.tsx` (await before render) | Literal AUTH-07 wording: `await msalInstance.initialize(); await msalInstance.handleRedirectPromise();` BEFORE `ReactDOM.createRoot(...).render(<App/>)`. Simplest: no extra component, no flash-of-anything, MSAL state settled on first paint. ~50-150ms blank cold-load (acceptable). | ✓ |
| Wrapping `<MsalBootstrap/>` component | App renders `<MsalBootstrap><App/></MsalBootstrap>`; returns null until both promises resolve. More 'Reacty' but introduces a flash-of-null + second render pass. | |
| Suspense + `use()` hook (React 19) | `use(msalInitPromise)` inside a top component, wrap in Suspense. Bleeding-edge; MSAL doesn't natively return a stable Promise. Overengineered. | |

**User's choice:** Top of `main.tsx` (await before render)
**Notes:** None

---

### Q6. MSAL cache location for tokens?

| Option | Description | Selected |
|--------|-------------|----------|
| `sessionStorage` | Tab-scoped: tokens gone when the tab closes. Lower XSS blast radius. Adrian re-logs once per session — acceptable for single-user portfolio app where dwell-time per session is short. | ✓ |
| `localStorage` | Survives tab close + page refresh; fewer re-logins. Persistent token = larger blast radius if XSS slips in. | |
| Cookie storage (httpOnly via server) | Microsoft's default but requires server-side cookie minting; doesn't fit pure-SPA + ACA architecture. Overkill for v1. | |

**User's choice:** `sessionStorage`
**Notes:** None

---

### Q7. Backend JWT validation library adoption shape?

| Option | Description | Selected |
|--------|-------------|----------|
| `fastapi-azure-auth` `SingleTenantAzureAuthorizationCodeBearer` + chained Depends | Library handles JWKS caching, issuer verification, audience check, signature, expiry. Wire module-level, chain into `get_current_user_id()`. STACK.md AUTH-05 names this library. | ✓ |
| PyJWT + jwcrypto directly | More code (hand-roll JWKS fetch + cache + retry + key rotation), fewer deps. Doesn't match REQUIREMENTS AUTH-05 wording. | |
| Authlib AsyncJWKSClient + manual Depends | Middle ground. Authlib has good async story but you still write issuer/audience/expiry checks. Non-standard dep when `fastapi-azure-auth` already does this. | |

**User's choice:** `fastapi-azure-auth` `SingleTenantAzureAuthorizationCodeBearer` + chained Depends
**Notes:** None

---

### Q8. AUTH-06 single-user oid-allowlist guard placement?

| Option | Description | Selected |
|--------|-------------|----------|
| Inside `get_current_user_id()` (function-body rewrite) | Phase 1 D-10 pre-wired every consumer with `Depends(get_current_user_id)`. New body: parse JWT (via `fastapi-azure-auth` dep), compare oid against `settings.seeded_user_entra_oid`, raise 403 on mismatch. One place to read the guard; no per-route decorator drift. | ✓ |
| Separate `require_allowlisted_user` Depends chained after `fastapi-azure-auth` | More decomposed but adds 2 extra decorators on every protected route + a wiring-drift risk if a future route forgets one. | |
| Global middleware | Forces `/health`-allowlist exception logic + breaks the future multi-user-platform-ready story. Worst fit. | |

**User's choice:** Inside `get_current_user_id()` (function-body rewrite)
**Notes:** None

---

### Q9. How does Adrian capture his Entra oid for the first time (operationally)?

| Option | Description | Selected |
|--------|-------------|----------|
| AccessDenied page decodes + displays oid client-side | When AUTH-06 returns 403, the SPA's AccessDenied page reads `msalInstance.getActiveAccount().idTokenClaims.oid` and shows it in a code block with copy button. Adrian copies → `az keyvault secret set` → restart. No backend changes, no debug endpoint to harden later, structlog still logs rejected_oid for LAW audit. | ✓ |
| Dedicated `/auth/whoami` debug endpoint | Signature-only validation, returns `{oid, name, email}`. Gated behind `AUTH_WHOAMI_ENABLED` env. One curl gets you the oid; auditable via Swagger. Cost: a permanently-shipped endpoint that needs disable-after-bootstrap discipline. | |
| Bootstrap-mode short-circuit | Empty `SEEDED_USER_ENTRA_OID` = accept any valid JWT for one revision, log oid. Cleanest UX but External tenant allows external signups — small risk window where another signup lands before Adrian's first login. | |

**User's choice:** AccessDenied page decodes + displays oid client-side
**Notes:** None

---

### Q10. When does migration `00NN_adopt_entra_oid.py` run?

| Option | Description | Selected |
|--------|-------------|----------|
| Blocking on container startup (`init_db` → `alembic upgrade head`) | Phase 1 D-04 pattern: `alembic upgrade head` runs at container boot. Migration reads `SEEDED_USER_ENTRA_OID` env, UPDATEs the seed row idempotently. Skips on empty env. Standard pattern, no new tooling. | ✓ |
| Detached one-shot via `az containerapp exec` + new CLI subcommand | Adrian runs `job-rag adopt-oid` AFTER KV is filled. Decouples migration from startup; survives forgetting to restart. Costs a new Typer subcommand + documented runbook step. | |

**User's choice:** Blocking on container startup
**Notes:** None

---

### Q11. Access token acquisition pattern from SPA to API?

| Option | Description | Selected |
|--------|-------------|----------|
| `acquireTokenSilent` before every API call (interceptor) | Fetch wrapper calls `msalInstance.acquireTokenSilent({scopes: [API_SCOPE]})` on every request. MSAL handles in-memory cache + automatic refresh BEFORE expiry. Standard MSAL pattern. | ✓ |
| Acquire once on login, attach as Bearer until 401 | Store one token after login, attach to every request; on 401, re-acquire. Misses MSAL's smart pre-expiry refresh; user sees a hiccup every ~1h. | |
| MSAL `useMsal` hook per-component, manual Bearer plumbing | Each component using API calls `useMsal` + `acquireTokenSilent` inline. Pushes auth into every component — wrong layer; violates SHEL-03 centralization. | |

**User's choice:** `acquireTokenSilent` before every API call (interceptor)
**Notes:** None

---

### Q12. Logout flow shape?

| Option | Description | Selected |
|--------|-------------|----------|
| `msalInstance.logoutRedirect()` + post-logout URI | Full Entra logout: tells Entra to clear the SSO session AND redirects back. Next login forces fresh credential entry. Microsoft's recommended pattern. | ✓ |
| `msalInstance.clearCache()` only (SPA-local) | Wipes tokens from sessionStorage; doesn't kill the Entra SSO session. 'Sign out' semantically lies — underlying Entra session is alive. | |
| Mixed: `logoutRedirect` on click, `clearCache` on tab close | Two paths. Premature complexity for v1. | |

**User's choice:** `msalInstance.logoutRedirect()` + post-logout URI
**Notes:** None

---

## API client + TanStack Query + SSE-readiness

### Q13. API fetch wrapper + Bearer interceptor + 401 handling shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Custom native fetch wrapper with MSAL interceptor | ~30-50 LOC: `authedFetch(url, init)` calls `msalInstance.acquireTokenSilent`, attaches Bearer, calls fetch. On `InteractionRequiredAuthError`, falls through to `acquireTokenRedirect`. On 401, retries once after silent refresh. No extra deps. | ✓ |
| `ofetch` (unjs/ofetch) | Modern wrapper with interceptors + auto-JSON + retries. ~12kb gzip. Saves wrapper code but ofetch's retry semantics overlap TanStack Query's, risking double-retry. | |
| `axios` + interceptor | Heavier (~14kb gzip), API client/server split, you still write the MSAL interceptor. No advantage over native fetch in 2026. | |

**User's choice:** Custom native fetch wrapper with MSAL interceptor
**Notes:** None

---

### Q14. API type generation strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| `openapi-typescript` codegen from `/openapi.json` | `npm run codegen` reads FastAPI's `/openapi.json` (Phase 1 already exposes AgentEvent), emits `frontend/src/api/types.ts`. Zero drift; AgentEvent discriminated union becomes a TS tagged union for free. | ✓ |
| Hand-written TS types matching Pydantic models | More flexible but drift risk. Costs the very thing Phase 1 D-04 built. | |
| Zod schemas + runtime validation | Heaviest (zod parse on every response), still drifts unless regen'd from `/openapi.json`. Overkill for an API you own. | |

**User's choice:** `openapi-typescript` codegen from `/openapi.json`
**Notes:** None

---

### Q15. API service-module shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Typed service module per domain (jobs, profile, agent, health) | `frontend/src/api/{jobs,profile,agent,health}.ts` each export typed async fns. Components use TanStack Query with `{queryKey, queryFn: () => searchJobs(params)}`. One place to add a new endpoint; query keys colocated. | ✓ |
| Inline fetchers per `useQuery` call | Components write `useQuery({queryKey, queryFn: () => authedFetch('/search?q=...')})` inline. Path strings + parameter serialization repeat across pages. | |
| Auto-generated `useQuery` hooks via `openapi-typescript-codegen-fetch` | One tool generates types + hooks. Generated hooks have fixed shape — hard to customize query keys, hard to compose. | |

**User's choice:** Typed service module per domain
**Notes:** None

---

### Q16. SSE helper for Phase 6 (Chat) — ship now in Phase 4 or defer?

| Option | Description | Selected |
|--------|-------------|----------|
| Ship `readSSEStream()` helper in Phase 4 | ~60 LOC: `authedFetch` + `Response.body.getReader()` + `TextDecoder` + split on `\n\n` + yield typed `AgentEvent`. Phase 4 also ships a hidden `/debug/agent-stream` page to PROVE end-to-end auth + SSE works during Phase 4. Phase 6 then only writes UI. | ✓ |
| Defer entirely to Phase 6 | Phase 4 doesn't touch SSE; Phase 6 writes both helper + UI. Cleaner phase-boundary but risks discovering SSE+Bearer interaction problems on the critical path. | |
| Use `eventsource-parser` npm package | Trade ~60 LOC for ~3kb gzip + a dep. Worth it for multiple SSE consumers; overkill for one. | |

**User's choice:** Ship `readSSEStream()` helper in Phase 4
**Notes:** None

---

## Routing + protected layout + SHEL-06 + shadcn theme

### Q17. Router choice for the SPA?

| Option | Description | Selected |
|--------|-------------|----------|
| React Router v7 (declarative routes) | Most mature, biggest docs ecosystem, React 19 + Vite first-class. Declarative `<Routes><Route element={<AppShell/>}>...children</Route>}` fits SHEL-04 layout. No data loaders in v1 — TanStack Query owns data. | ✓ |
| TanStack Router | Compile-time type-safe route params/paths/query strings; pairs with TanStack Query. Newer (smaller community), file-based router adds tooling weight. Marginal gain for 4 routes. | |
| Wouter | ~1kb, hooks-only. Insufficient for SHEL-04 layout pattern + SHEL-06 route loader hooks. | |

**User's choice:** React Router v7
**Notes:** None

---

### Q18. Protected-route + AUTH-04 pattern?

| Option | Description | Selected |
|--------|-------------|----------|
| Layout route with `<AuthGate>` component + `<Outlet/>` | `<Route element={<AuthGate><AppShell/></AuthGate>}>...children</Route>`. AuthGate uses MSAL `useIsAuthenticated`: if false → `loginRedirect`; else → `<Outlet/>`. All protected routes share one guard. | ✓ |
| `<MsalAuthenticationTemplate interactionType=Redirect>` | Built-in component that wraps protected pages. Redirect can fire mid-render (Suspense-incompatible) and offers less control over SHEL-06 'loading-while-we-check' state. | |
| Per-page hook check | Each page calls `useIsAuthenticated()` in its own `useEffect`. Drift risk: forgetting it on a new page silently exposes it. | |

**User's choice:** Layout route with `<AuthGate>` component + `<Outlet/>`
**Notes:** None

---

### Q19. SHEL-06 (loading / empty / error / ErrorBoundary) placement?

| Option | Description | Selected |
|--------|-------------|----------|
| Layered: root ErrorBoundary + per-route Suspense fallback + per-feature empty states | Single root `<ErrorBoundary>` (react-error-boundary lib) for any unhandled render error. Per-route `<Suspense fallback={<RouteSkeleton/>}>` for code-split loading. Per-feature loading skeletons inline (shadcn Skeleton + feature-specific EmptyState). One pattern per layer. | ✓ |
| Single global loading overlay | One page-level spinner during any pending query. Hides which surface is loading; bad UX for dashboard's 3-widget split. | |
| Per-page everything | Each page defines its own ErrorBoundary, Suspense fallback, empty states inline. Lots of repetition. | |

**User's choice:** Layered: root ErrorBoundary + per-route Suspense fallback + per-feature empty states
**Notes:** None

---

### Q20. shadcn theme: accent + dark mode + typography?

| Option | Description | Selected |
|--------|-------------|----------|
| Accent zinc / both light+dark (toggle, default dark) / Geist Sans + Geist Mono | Zinc most grayscale-pure (Linear-canonical). Both modes covers portfolio screenshot scenarios (light for README, dark for serious-looking). Default dark on first load. Geist Sans + Mono (Vercel's, Linear-vibe). v4 `@theme inline` in app.css. | ✓ |
| Accent slate / dark-only / Inter | Slate has subtle blue undertone, less pure-gray. Inter feels 'startup default'. Dark-only locks Adrian out of light-mode screenshots. | |
| Accent stone / light-only / system stack | Stone is warm-gray (not Linear-canonical), light-only deviates from dense-dashboard aesthetic, system stack gives up portfolio polish. | |

**User's choice:** Accent zinc / both light+dark (toggle, default dark) / Geist Sans + Geist Mono
**Notes:** None

---

## Claude's Discretion

Areas where Adrian explicitly left flexibility for downstream agents:

- Scaffolding command + tooling details (`npm create vite`, ESLint flat config, Vitest setup file, Prettier)
- Vite dev proxy → local Docker Compose API (forced by Phase 3 D-04, not a real gray area)
- Path aliases (`@/*` → `src/*`)
- QueryClient defaults (`staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 2`, `networkMode: 'online'`)
- Provider nesting in `main.tsx` (`MsalProvider` → `QueryClientProvider` → `BrowserRouter` → `ErrorBoundary` → `App`)
- Codegen npm-script wiring + CI drift guard
- TanStack Query Devtools dev-only gate
- AbortSignal threading from TanStack Query queryFn through `authedFetch`
- Pre-scaffolded shadcn component set (button, card, skeleton, dropdown-menu, dialog, toast, input, badge — incremental)
- Dark-mode toggle persistence (localStorage `theme` key + `prefers-color-scheme` fallback)
- Route table (`/` → `/dashboard` redirect, `/dashboard`, `/chat`, `/profile`, `/access-denied`, `/debug/agent-stream`, `*` 404)
- Top-nav layout (Dashboard / Chat / Profile tabs + sign-out + theme toggle)
- Scope request shape (`loginRequest.scopes` once at SDK init)
- Settings field defaults in `config.py` (`seeded_user_entra_oid: str = ""` empty = bootstrap-pending)
- fastapi-azure-auth issuer URL builder + openid_config_url
- Token-refresh-on-tab-focus (MSAL default + Query `refetchOnWindowFocus: false`)
- `/health` endpoint allowlist exception (stays unauthenticated for liveness probe)
- `infra/external/` Terraform module shape (mirrors `infra/bootstrap/`)
- Vitest setup file + matchers + cleanup

## Deferred Ideas

Captured for future phases; explicitly out of scope for Phase 4:

- Conversation history / multi-turn chat persistence (Phase 6 v1 is clear-on-refresh; v2)
- Multi-user signup flow with RBAC (post-v1 platform-era)
- MFA / passkey support (single-user v1 unnecessary)
- `/auth/whoami` debug endpoint (D-09 alternative; revisit if multi-user)
- Bootstrap-mode short-circuit (D-09 alternative; rejected per external signup risk)
- TanStack Router migration (revisit if /dashboard?country=... typing pain emerges)
- shadcn block-level patterns (auto-form, complex tables) — defer to Phase 5
- Storybook (portfolio-polish, post-v1)
- React 19 Activity component for nav-state preservation (defer to Phase 7)
- TF management of External-tenant app regs via CI (Gap D blocker; needs Microsoft cross-tenant azuread auth)
- Token expiry visual indicator / proactive renewal UX
- Dev ACA proxy target for Vite (Phase 3 D-04 deferred; revisit when staging needed)
- `eventsource-parser` npm package (D-16 alternative; revisit on second SSE consumer)
- Axios or ofetch wrapper (D-13 alternatives; native fetch sufficient for v1)
- Stable redirect URI per environment / separate app regs per env (multi-env redirect URI scaling)
