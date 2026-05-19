# Phase 4: Frontend Shell + Auth — Research

**Researched:** 2026-05-19
**Domain:** Vite 8 + React 19.2 SPA with MSAL React 5.4 against Entra External ID (CIAM); FastAPI 0.135 + fastapi-azure-auth 5.2 JWT validation; openapi-typescript 7.13 codegen; React Router 7 routing; TanStack Query 5.100; Tailwind v4 + shadcn/ui new-york; Terraform `azuread ~> 3.x` local-only app-reg management; Alembic migration 0005
**Confidence:** HIGH (every recommended package version verified against the live npm/PyPI registry on 2026-05-19; fastapi-azure-auth constructor surface verified from upstream GitHub source).

---

## Summary

Phase 4 is a "wire up exactly what CONTEXT.md D-01..D-20 dictated" execution phase, not a design phase. 20 locked decisions cover scaffold location, MSAL config, auth flow, OID bootstrap, alembic migration, fetch wrapper, codegen, SSE helper, router, layered loading/error states, and theme. The researcher's job is to fill the gaps between decisions — exact constructor args, file layouts, idiomatic patterns, and one substantive correction.

**One substantive technical correction the planner MUST address before writing tasks:** CONTEXT.md D-07 names `SingleTenantAzureAuthorizationCodeBearer` as the fastapi-azure-auth class. That class does NOT accept an `openid_config_url` override — its discovery endpoint is hard-coded to `https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration`, which is the **workforce** endpoint. Entra External ID's discovery endpoint is `https://{subdomain}.ciamlogin.com/{tenant_id}/v2.0/.well-known/openid-configuration` (a different host entirely). The correct class for CIAM is `B2CMultiTenantAuthorizationCodeBearer`, which accepts `openid_config_url` precisely for this case. [VERIFIED: source `Intility/fastapi-azure-auth/blob/main/fastapi_azure_auth/auth.py` constructor signatures fetched 2026-05-19]. See **Open Questions §Q1** for the planner-actionable resolution path.

Everything else is mechanical: scaffold the directory, install the verified versions, wire 4 backend Settings fields + `0005_adopt_entra_oid.py` migration + `get_current_user_id()` function-body rewrite + module-level `azure_scheme` instance, scaffold `infra/external/` mirroring `infra/bootstrap/`, extend `.github/workflows/deploy-spa.yml` with VITE_* secrets, add a `frontend-ci` job to `ci.yml`, and ship the React shell with the patterns documented below.

**Primary recommendation:** Open the planner with Wave 0 = scaffolding + technical-correction call-out (auth class choice + class-specific issuer-validation strategy), then proceed Wave 1 backend → Wave 2 infra/external + GHA → Wave 3 frontend in parallelizable plans.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**A. Scaffold + Gap D + build-env wiring**

- **D-01:** Project location = `frontend/` (literal REQUIREMENTS SHEL-01). Sibling top-level dir to `src/`, `infra/`, `tests/`. Scaffolded via `npm create vite@latest frontend -- --template react-ts`.
- **D-02:** Gap D resolution — External-tenant SPA + API app registrations live in a new `infra/external/` Terraform directory with **local-state-only** management (mirrors `infra/bootstrap/`). Adrian runs `terraform apply` from his local `az login` against the External tenant (`azuread.external` provider). State file `infra/external/terraform.tfstate` is gitignored. Outputs (`spa_client_id`, `api_client_id`, `api_audience_uri`) feed both `frontend/.env.local` (manually copied) AND `infra/envs/prod/prod.tfvars.local`. Adrian's local apply is the only execution path for v1.
- **D-03:** MSAL config values into the SPA bundle = **VITE_\* build-time env vars**. Build-time bake: `VITE_TENANT_SUBDOMAIN`, `VITE_TENANT_ID`, `VITE_SPA_CLIENT_ID`, `VITE_API_AUDIENCE`, `VITE_API_BASE_URL`. All five are public-by-design. `frontend/.env.local` (gitignored, dev) + `frontend/.env.production` (committed, prod). `deploy-spa.yml` passes via Vite's standard `import.meta.env` mechanism. No runtime config fetch.
- **D-04:** Backend audience wiring = **plain ACA env vars** (`BACKEND_AUDIENCE`, `ENTRA_TENANT_ID`, `ENTRA_TENANT_SUBDOMAIN`, `SEEDED_USER_ENTRA_OID`). Phase 3 D-13 reserves KV for genuine secrets; these are public-by-design. `SEEDED_USER_ENTRA_OID` from existing KV secret via `secretRef` (Phase 3 D-09 placeholder slot — Phase 4 fills); others from `prod.tfvars` literals derived from `infra/external/` outputs.

**B. End-to-end auth flow**

- **D-05:** AUTH-07 race-fix pattern = **top of `main.tsx`**. Literal: `await msalInstance.initialize(); await msalInstance.handleRedirectPromise();` runs BEFORE `ReactDOM.createRoot(rootEl).render(<App/>)`. No wrapping component, no Suspense + `use()` overengineering, no flash-of-null. Accepts ~50-150ms blank first paint on cold load.
- **D-06:** MSAL cache type = **sessionStorage**. Tab-scoped: tokens are gone when the tab closes. Lower XSS blast radius. Configured via `cacheLocation: 'sessionStorage'` in `PublicClientApplication` config.
- **D-07:** Backend JWT validation = **`fastapi-azure-auth` 5.x `SingleTenantAzureAuthorizationCodeBearer` + chained Depends**. Library handles JWKS caching (LRU), issuer verification (interpolates `tenant_subdomain` + `tenant_id` into the `ciamlogin.com/${tenant_id}/v2.0` issuer URL), audience check (`api://${api_client_id}`), signature, expiry. Wired as a module-level instance in `src/job_rag/api/auth.py`. Add `fastapi-azure-auth ^5.0` + its peer `cryptography` to `pyproject.toml`. **See Open Question Q1 — class choice needs revisit.**
- **D-08:** AUTH-06 single-user `oid` guard placement = **inside `get_current_user_id()` function body** (Phase 1 D-10 function-body rewrite pattern). Every consumer is already wired via `Depends(get_current_user_id)`. One place for the guard; no per-route decorator drift. The 403 detail string is generic — rejected `oid` is logged structurally via structlog for LAW audit, but NOT returned in the response body.
- **D-09:** First-login OID capture UX = **AccessDenied page decodes + displays `oid` client-side**. When AUTH-06 returns 403, the SPA's `/access-denied` route reads `msalInstance.getActiveAccount()?.idTokenClaims?.oid` and shows the value in a `<pre>` code block with a copy-to-clipboard button. Adrian copies, runs `az keyvault secret set --vault-name jobrag-prod-kv --name seeded-user-entra-oid --value <oid>`, restarts the ACA revision. Server-side `rejected_oid` is also logged via structlog for LAW audit.
- **D-10:** Migration `00NN_adopt_entra_oid.py` runs **blocking on container startup** (Phase 1 D-04 pattern). `init_db()` → `alembic upgrade head` → migration reads `os.environ['SEEDED_USER_ENTRA_OID']` and runs an idempotent `UPDATE user_db SET entra_oid = :oid WHERE user_id = :seeded_uuid AND (entra_oid IS NULL OR entra_oid != :oid)`. Skips cleanly on empty env. The `user_db.entra_oid` column itself ships in this migration. Alembic dependency: `down_revision = "0004"`.
- **D-11:** Token acquisition pattern = **`acquireTokenSilent` before every API call (interceptor)**. The `authedFetch` wrapper calls `msalInstance.acquireTokenSilent({scopes: [API_SCOPE]})` for every request, attaches result as `Authorization: Bearer <jwt>`. On `InteractionRequiredAuthError`, wrapper catches and calls `msalInstance.acquireTokenRedirect({scopes: [API_SCOPE]})`. On HTTP 401, wrapper retries once after silent refresh; second 401 ⇒ redirect flow. API_SCOPE = `api://${VITE_API_AUDIENCE}/access_as_user`.
- **D-12:** Logout flow = **`msalInstance.logoutRedirect({postLogoutRedirectUri: SWA_origin})`**. Required `postLogoutRedirectUri` MUST be registered on the SPA app reg in `infra/external/`.

**C. API client + TanStack Query + SSE-readiness**

- **D-13:** Fetch wrapper = **custom native fetch + MSAL interceptor**. ~30-50 LOC in `frontend/src/api/authedFetch.ts`. No `axios`, no `ofetch` — saves ~14kb gzip.
- **D-14:** API type generation = **`openapi-typescript` codegen from `/openapi.json`**. `frontend/package.json` has `"codegen": "openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts"`. Commits `src/api/types.ts`. Phase 1 D-04 AgentEvent discriminated union becomes a TS tagged union for free.
- **D-15:** API service module shape = **typed service module per domain**. `frontend/src/api/{jobs,profile,agent,health}.ts` each export typed async functions that call `authedFetch` + cast against `openapi-typescript` types. Components use TanStack Query with `{queryKey, queryFn: ({signal}) => fn(params, signal)}`.
- **D-16:** SSE helper for Phase 6 = **ship in Phase 4**. `frontend/src/api/readSSEStream.ts` (~60 LOC): `async function* readSSEStream(response: Response): AsyncIterable<AgentEvent>` using `response.body.getReader() + TextDecoder + split-on-\n\n`. Phase 4 ALSO ships a hidden `/debug/agent-stream` page that calls it against the live `/agent/stream`. Phase 6 then only writes the chat presentation layer.

**D. Routing + protected layout + SHEL-06 + shadcn theme**

- **D-17:** Router = **React Router v7**. Declarative `<Routes><Route element={<AppShell/>}><Route .../>}` fits SHEL-04 top-nav layout. No data loaders in v1 — TanStack Query owns data.
- **D-18:** Protected-route pattern (AUTH-04) = **layout route with `<AuthGate>` component wrapping `<AppShell><Outlet/></AppShell>`**. `<AuthGate>` uses MSAL's `useIsAuthenticated()` hook: if false → `msalInstance.loginRedirect({scopes: [API_SCOPE]})`; else → `<Outlet/>`. AccessDenied (`/access-denied`) is OUTSIDE the AuthGate.
- **D-19:** SHEL-06 placement = **layered**: (a) root `<ErrorBoundary>` (react-error-boundary lib) catches any unhandled render error → global error page; (b) per-route `<Suspense fallback={<RouteSkeleton/>}/>` for React.lazy code-split loading; (c) per-feature loading skeletons (shadcn `Skeleton`) shown via `useQuery().isPending`; (d) per-feature empty states (typed `<EmptyState>` per page).
- **D-20:** shadcn theme = **zinc accent / both light+dark (toggle, default dark) / Geist Sans + Geist Mono**. Geist Sans (`@fontsource/geist-sans`) + Geist Mono (`@fontsource/geist-mono`) installed via npm. Tailwind v4 `@theme inline` block in `app.css`.

### Claude's Discretion

- Scaffolding commands and tooling specifics: `npm create vite@latest frontend -- --template react-ts`, ESLint flat config, Prettier config, Vitest setup file.
- **Vite dev proxy target** = local Docker Compose API (`http://localhost:8000`). Forced by Phase 3 D-04.
- Path aliases: `@/*` → `src/*` in both `tsconfig.json` and `vite.config.ts` `resolve.alias`.
- QueryClient defaults: `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 2`, `networkMode: 'online'`.
- Provider nesting order in `main.tsx`: `<MsalProvider>` outer → `<QueryClientProvider>` → `<BrowserRouter>` → `<ErrorBoundary>` → `<App/>`.
- Codegen wiring: `npm run codegen` script + a CI guard that runs codegen against a backend-PR-snapshot OpenAPI doc and fails if it drifts from committed types.
- TanStack Query Devtools: dev-only gate via `import.meta.env.DEV`.
- AbortSignal threading: every `authedFetch` accepts `init.signal`.
- Pre-scaffolded shadcn components first wave: `button`, `card`, `skeleton`, `dropdown-menu`, `dialog`, `toast` (`sonner`), `input`, `badge`.
- Dark mode toggle wiring: top-nav `<ThemeToggle>` reads/writes `localStorage['theme']`, falls back to `window.matchMedia('(prefers-color-scheme: dark)')`. Applies via Tailwind `class="dark"` on `<html>`.
- Route table: `/` (redirect to `/dashboard`), `/dashboard`, `/chat`, `/profile`, `/access-denied` (outside AuthGate), `/debug/agent-stream` (AuthGate'd, dev-only env flag), `*` (404).
- Scope request shape: `loginRequest.scopes = [API_SCOPE]`.
- Settings additions in `src/job_rag/config.py`: `entra_tenant_id: str`, `entra_tenant_subdomain: str`, `backend_audience: str`, `seeded_user_entra_oid: str = ""`.
- fastapi-azure-auth issuer URL builder: `f"https://{settings.entra_tenant_subdomain}.ciamlogin.com/{settings.entra_tenant_id}/v2.0"`.
- Token-refresh-on-tab-focus: MSAL default + TanStack Query `refetchOnWindowFocus: false` ⇒ no spurious refetches.
- `/health` endpoint allowlist exception: unauthenticated, returns 200.
- Resource scaffolding for `infra/external/`: own `main.tf`, `variables.tf`, `outputs.tf`, `provider.tf` (only `azuread.external` provider), `terraform.tfvars` template, `README.md` runbook.
- Vitest setup file: `frontend/src/test/setup.ts` with `@testing-library/jest-dom` matchers + `cleanup()` afterEach. Vitest config in `vite.config.ts`.

### Deferred Ideas (OUT OF SCOPE)

- Conversation history / multi-turn chat persistence (Phase 6 v1 clear-on-refresh)
- Multi-user signup flow with role-based access
- MFA / passkey support
- `/auth/whoami` debug endpoint (D-09 alternative)
- Bootstrap-mode short-circuit (D-09 alternative)
- TanStack Router migration
- shadcn block-level patterns (auto-form, complex data tables)
- Storybook for component-level docs
- React 19 Activity component for nav-state preservation
- TF management of External-tenant app registrations via CI (Gap D blocker)
- Token expiry visual indicator / proactive renewal UX
- Dev ACA proxy target for Vite
- Eventsource-parser npm package (D-16 alternative)
- Axios or ofetch wrapper (D-13 alternatives)
- Stable redirect URI per environment (multi-env redirect URI cardinality)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SHEL-01 | Vite + React 19 + TypeScript project scaffolded in `frontend/` | §Standard Stack (Vite 8.0.13, React 19.2.6, TS 5.9 verified on npm 2026-05-19); §Architecture Patterns "Project Structure"; §Code Examples "Scaffold + Tailwind v4 + shadcn init" |
| SHEL-02 | Tailwind CSS v4 + shadcn/ui installed and themed to Linear-style dense aesthetic | §Code Examples "Tailwind v4 + shadcn init"; UI-SPEC §4 (color), §3 (typography), §2 (spacing); §Standard Stack (`@tailwindcss/vite` 4.3.0, `@fontsource/geist-sans` + `@fontsource/geist-mono`) |
| SHEL-03 | TanStack Query installed; all server state flows through `useQuery`/`useMutation` | §Code Examples "TanStack Query + AuthedFetch composition pattern"; §Standard Stack (`@tanstack/react-query` 5.100.11); QueryClient defaults from CONTEXT.md Claude's Discretion |
| SHEL-04 | App shell with top-nav (Dashboard / Chat / Profile), user indicator, sign-out | UI-SPEC §7 (AppShell anatomy); §Architecture Patterns "Layered routing"; §Code Examples "AppShell.tsx skeleton" |
| SHEL-05 | API client attaches MSAL-issued access token as `Authorization: Bearer <jwt>` on every request | §Code Examples "authedFetch.ts pattern"; D-11, D-13 |
| SHEL-06 | Error boundary + empty/error/loading states for every page; Suspense fallbacks | §Architecture Patterns "Layered loading/error states" (D-19 4 layers); §Code Examples "ErrorBoundary skeleton", "RouteSkeleton skeleton", "EmptyState typed component" |
| AUTH-01 | Entra External ID tenant provisioned via Terraform (external SKU) | Tenant already exists (Phase 3 D-05 manual bootstrap, imported as `var.tenant_id_external`); Phase 4 only wires app regs — see §infra/external/ |
| AUTH-02 | SPA app registration created as a public client using PKCE | §Code Examples "infra/external/main.tf SPA app reg" (`single_page_application` block) |
| AUTH-03 | API app registration created as a resource with a single `access_as_user` scope | §Code Examples "infra/external/main.tf API app reg + identifier_uri + delegated permission + admin consent" |
| AUTH-04 | MSAL React integrated in the frontend; protected routes redirect unauthenticated users | §Code Examples "AuthGate.tsx skeleton"; D-18 |
| AUTH-05 | FastAPI validates Entra JWT on every protected request via `fastapi-azure-auth` 5.x | §Code Examples "src/job_rag/api/auth.py rewrite"; D-07 with planner-action on §Open Question Q1 (class choice) |
| AUTH-06 | Adrian's Entra `oid` is stored in `user_profile` row; app-layer guard rejects any other `oid` in v1 | §Code Examples "get_current_user_id body rewrite" + §Code Examples "alembic 0005 migration"; D-08, D-10 |
| AUTH-07 | MSAL initialization race prevented — `initialize()` and `handleRedirectPromise()` resolved before `ReactDOM.createRoot().render()` | §Code Examples "main.tsx literal AUTH-07 pattern"; D-05 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Backend tech stack frozen**: Python 3.12, FastAPI, LangGraph 1.1.x, PostgreSQL (local 17 / prod 16) + pgvector, SQLAlchemy 2.x async, Instructor, OpenAI SDK. Phase 4 adds only `fastapi-azure-auth>=5.0,<6.0` to backend deps (no other backend frameworks).
- **Frontend stack chosen**: Vite + React 18+ + TypeScript, Tailwind CSS, shadcn/ui, MSAL React for Entra ID. Pure SPA — no SSR.
- **Cloud provider**: Azure only.
- **Budget**: €0/mo on Azure free tier year 1.
- **IaC**: Terraform only — no Bicep / ARM / CLI scripts.
- **Single user (structurally multi-user)**: every table carries `user_id` (already done in Phase 1); every query filters by it (already done in Phase 1).
- **One cloud, one provider per concern**: managed Postgres (Azure DB), KV (managed secrets), Entra ID (managed identity), Container Apps (containers), SWA (static hosting), GitHub Actions + OIDC (CI). Don't mix in third-party equivalents.
- **Educational goal**: frontend and backend must remain cleanly separated. Logic that belongs in the backend cannot live in the frontend and vice versa. Concretely for Phase 4: no JWT decoding for authorization decisions in the frontend (only display in `/access-denied`); no token validation logic in the frontend; no auth state derivation in the backend.
- **GSD enforcement**: Before using Edit/Write tools, start work through a GSD command. (This research run was invoked by `/gsd-plan-phase`; downstream task execution will happen under `/gsd-execute-phase 4`.)
- **Code style**: ruff target-version `py312`, line-length 100, rules `E F I UP`. Pyright basic mode. Python 3.12 `X | Y` syntax. `structlog.get_logger(__name__)` per module. `from job_rag.X import Y` absolute imports (no relatives).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| User authentication (login UI, redirect, token acquisition) | Browser / Client | Entra External ID | MSAL React owns the login flow; Entra owns user store + JWT issuance. No backend involvement in login. |
| JWT validation (signature, iss, aud, exp) | API / Backend | — | fastapi-azure-auth validates every request. Validating in the frontend would be theatre (browser-side signature check is bypassable). |
| AUTH-06 single-user oid guard | API / Backend | — | The 403 must come from the server. Doing this in the frontend leaks who the allowed oid is to anyone who reads the bundle. |
| Token storage | Browser / Client | — | MSAL `cacheLocation: 'sessionStorage'` (D-06). |
| Bearer attach on every API call | Browser / Client | — | `authedFetch` interceptor calls `acquireTokenSilent` before every fetch. |
| Token refresh on 401 | Browser / Client | — | Interceptor catches `InteractionRequiredAuthError` → `acquireTokenRedirect`. Backend just returns 401 on bad/expired tokens. |
| OID-bootstrap UX (display oid for copy-paste) | Browser / Client | — | `/access-denied` decodes `idTokenClaims.oid` client-side (D-09). Backend already gave 403; no backend endpoint needed. |
| OID-bootstrap secret persistence | Out-of-band CLI (`az keyvault secret set`) | API / Backend (consumes env var) | Adrian runs `az keyvault secret set` manually after copying. ACA revision restart picks up new env var. |
| `entra_oid` column adoption | API / Backend (Alembic migration 0005) | — | DB schema change; runs blocking on container startup per Phase 1 D-04. |
| Server state cache | Browser / Client (TanStack Query) | — | All dashboards (Phase 5), chat (Phase 6), profile (Phase 7) consume API via TanStack Query. Phase 4 ships the wiring. |
| SSE event consumption | Browser / Client (`readSSEStream` helper) | API / Backend (`/agent/stream`) | Backend already emits typed AgentEvent SSE frames (Phase 1 D-04). Frontend consumes via native fetch + ReadableStream + TextDecoder. |
| Protected-route guard | Browser / Client (`<AuthGate>`) | — | Routing decisions happen client-side. Backend enforces auth via JWT validation independently — defence in depth, not single point of trust. |
| Theme persistence | Browser / Client (localStorage) | — | Pure UX state. Not user-portable across devices in v1. |
| OpenAPI type generation | Build-time (openapi-typescript codegen) | API / Backend (source `/openapi.json`) | Frontend types generated from backend OpenAPI schema. Committed `src/api/types.ts`. Drift caught in CI. |
| App reg lifecycle (SPA + API + delegated perm + admin consent) | IaC (Adrian-local `infra/external/` Terraform) | — | Gap D: workforce GHA SP can't auth into External tenant; managed locally only. Outputs feed `frontend/.env.production` + `infra/envs/prod/prod.tfvars.local`. |
| Build-time VITE_* env injection | CI (GHA `deploy-spa.yml` build step `env:` block) | — | VITE_* values are public-by-design (D-03). GHA secrets → build step env → Vite reads `import.meta.env` at build time → baked into bundle. |
| CI frontend gate (typecheck, lint, vitest, codegen-drift) | CI (GHA `ci.yml` new `frontend-ci` job) | — | Adds a Node 22 job alongside the existing Python job. |

---

## Standard Stack

### Core (frontend)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vite | 8.0.13 | Dev server + production bundler | Current stable. Node 20.19+ or 22.12+ required. [VERIFIED: `npm view vite version` 2026-05-19] |
| React | 19.2.6 | UI library | MSAL React 5.4 peer-deps `react ^19.2.1`. [VERIFIED: `npm view react version`] |
| TypeScript | 5.9+ | Static types | Vite 8 template ships latest. Use `strict: true` and `moduleResolution: "bundler"`. [CITED: STACK.md §1] |
| Tailwind CSS | 4.3.0 | Utility-first CSS | Tailwind v4 ships `@tailwindcss/vite` plugin (no PostCSS). [VERIFIED: `npm view tailwindcss version`] |
| `@tailwindcss/vite` | 4.3.x | Tailwind v4 Vite integration | Required by Tailwind v4. [CITED: tailwindcss.com/docs/installation/using-vite] |
| shadcn/ui CLI | `@latest` (no canary) | Component primitives (copy-paste) | New-york style + zinc accent locked in D-20. Stable CLI v4 supports React 19 + Tailwind v4. [CITED: ui.shadcn.com/docs/installation/vite] |
| Radix UI primitives | (transitive via shadcn) | Unstyled a11y primitives | Pulled by shadcn; no direct dep management. |
| `class-variance-authority` (cva) | (latest via shadcn init) | Variant-driven class composition | shadcn default. |
| `clsx` + `tailwind-merge` | (latest via shadcn init) | `cn()` utility | shadcn-generated `lib/utils.ts`. |
| `lucide-react` | (latest) | Icon set | shadcn default. Tree-shakeable SVGs. UI-SPEC uses `Sun`, `Moon`, `User`, `BarChart3`, `MessageSquare`, `FileQuestion`. |
| `@azure/msal-react` | 5.4.2 | React hooks + MsalProvider | [VERIFIED: `npm view @azure/msal-react version` 2026-05-19]. CONTEXT.md says 5.3.1; current is 5.4.2 — bump in pin range `^5.3.0` to allow current. Peer dep on `@azure/msal-browser ^5.8.0`. |
| `@azure/msal-browser` | 5.11.0 | PublicClientApplication | [VERIFIED: `npm view @azure/msal-browser version`]. CONTEXT.md says 5.8.x; current is 5.11.0 — bump in pin range `^5.8.0`. |
| `@tanstack/react-query` | 5.100.11 | Server-state cache | All server state flows here. [VERIFIED: npm registry] |
| `@tanstack/react-query-devtools` | (latest 5.x) | Dev-only devtools | Mounted under `import.meta.env.DEV` gate. |
| `react-router` | 7.15.1 | Routing | D-17 locked. v7's declarative `<Routes>/<Route>` syntax for layout routes (the AppShell wrap). [VERIFIED: npm registry] |
| `react-error-boundary` | 6.1.1 | Error boundary lib | D-19a. Hook-friendly wrapping; supplies `ErrorBoundary` + `useErrorBoundary` + reset semantics. [VERIFIED: npm registry] |
| `openapi-typescript` | 7.13.0 (devDep) | Codegen from `/openapi.json` to `src/api/types.ts` | D-14. CLI: `openapi-typescript <input> -o <output>`. Generates `paths` + `components` types. [VERIFIED: npm registry; CITED: openapi-ts.dev/introduction] |
| `@fontsource/geist-sans` | (latest 5.x) | Self-hosted Geist Sans | D-20. Avoids CDN latency, plays with Vite asset pipeline. |
| `@fontsource/geist-mono` | (latest 5.x) | Self-hosted Geist Mono | D-20. Load-bearing for OID code-block (`/access-denied`) and `/debug/agent-stream` log. |

### Supporting (frontend dev)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `vitest` | 3.x | Test runner | All component + helper tests. Config in `vite.config.ts` `test:` block. |
| `@testing-library/react` | latest | Component-render assertions | AuthGate, ThemeToggle, AppShell unit tests. |
| `@testing-library/jest-dom` | latest | DOM matchers (`toBeInTheDocument`, etc.) | Loaded in `frontend/src/test/setup.ts`. |
| `@testing-library/user-event` | latest | User-interaction simulation | Theme toggle click, copy button click. |
| `eslint` | 9.x | Linter | Flat config (`eslint.config.js`). |
| `typescript-eslint` | 8.x | TS-aware lint rules | Required for React 19 + TS 5. |
| `eslint-plugin-react-hooks` | latest | Hooks lint rules | Catches missing deps, conditional hooks. |
| `eslint-plugin-react-refresh` | latest | Vite Fast Refresh hygiene | Ensures only React components are exported from `.tsx` files. |
| `prettier` | 3.x | Formatter | Standard config; integrate with ESLint via `eslint-config-prettier`. |

### Core (backend additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi-azure-auth` | 5.2.0 | Entra JWT validation (JWKS caching, iss/aud/sig/exp) | [VERIFIED: pypi.org/pypi/fastapi-azure-auth/json 2026-05-19] CONTEXT.md says 5.x; latest is 5.2.0 — pin as `>=5.2,<6.0`. Library is mature (MIT licensed, Intility-maintained). **See §Open Question Q1 for which constructor class.** |
| `cryptography` | (transitive via fastapi-azure-auth → PyJWT[crypto]) | RS256 signature validation | Already pulled transitively. No direct add needed. |

### Alternatives Considered (rejected)

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `fastapi-azure-auth` | Hand-rolled `PyJWT + httpx + jwks_client` | ~150 LOC, no JWKS cache invalidation logic, easy to skip `iss`/`aud`/`exp` checks. Reject — STACK.md and CONTEXT.md D-07 both lock the library. |
| Custom `authedFetch` | `axios` + interceptor | +14 KB gzip, redundant retry semantics overlap TanStack Query, no real win for ~30 LOC. Reject — D-13 locks native fetch. |
| `openapi-typescript` | `openapi-generator-cli` Java tool | Heavyweight (Java runtime), generates full client SDK we don't want. Reject — D-14 locks openapi-typescript. |
| React Router v7 | TanStack Router | TanStack Router has better TS-typed `useParams`, but only matters at >10 routes. v1 has 7 routes. Reject — D-17 locks RR7. |
| MSAL React `AuthenticatedTemplate` | Custom `AuthGate` with `useIsAuthenticated()` | Templates work but make conditional logic harder to test. D-18 locks the custom guard. |
| `eventsource-parser` npm package | Custom 60-LOC `readSSEStream` | Adds a dep for ~60 LOC of well-understood code. Reject — D-16 locks the hand-rolled helper. Deferred for v2 if a second SSE consumer appears. |
| `localStorage` for MSAL cache | `sessionStorage` | localStorage persists across tab close (re-login less often) at cost of larger XSS blast radius. D-06 locks sessionStorage. |
| Shipping `/debug/agent-stream` only in dev | Gating via `VITE_DEBUG_PAGES` env flag for portfolio demos | Both supported via composite gate `import.meta.env.DEV || import.meta.env.VITE_DEBUG_PAGES === 'true'`. UI-SPEC §12. |

**Installation:**

```bash
# 1. Frontend scaffold (D-01)
npm create vite@latest frontend -- --template react-ts
cd frontend

# 2. Tailwind v4 + shadcn (D-20)
npm install tailwindcss @tailwindcss/vite
npx shadcn@latest init -t vite
# When prompted: style=new-york, base-color=zinc, css-variables=yes

# 3. First-wave shadcn components (UI-SPEC §5)
npx shadcn@latest add button card skeleton dropdown-menu dialog sonner input badge

# 4. Auth + data + routing
npm install @azure/msal-react @azure/msal-browser @tanstack/react-query react-router react-error-boundary

# 5. Fonts (D-20)
npm install @fontsource/geist-sans @fontsource/geist-mono

# 6. Icons (shadcn pulls, pin explicitly)
npm install lucide-react

# 7. Dev deps (test + lint + codegen)
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event \
  eslint typescript-eslint eslint-plugin-react-hooks eslint-plugin-react-refresh prettier \
  openapi-typescript @tanstack/react-query-devtools jsdom
```

```bash
# Backend (uv)
uv add 'fastapi-azure-auth>=5.2,<6.0'
```

**Version verification log (2026-05-19):**

| Package | CONTEXT.md says | Live registry | Action |
|---------|-----------------|---------------|--------|
| Vite | 8.0.x | 8.0.13 | ✓ |
| React | 19.2.x | 19.2.6 | ✓ |
| Tailwind CSS | v4.2.x | 4.3.0 | ✓ minor bump |
| `@azure/msal-react` | 5.3.1 | 5.4.2 | minor bump — `package.json` should pin `^5.3.0` |
| `@azure/msal-browser` | 5.8.x | 5.11.0 | minor bump — pin `^5.8.0` |
| `@tanstack/react-query` | 5.x | 5.100.11 | ✓ |
| `react-router` | v7 | 7.15.1 | ✓ |
| `react-error-boundary` | (CONTEXT names lib, no version) | 6.1.1 | ✓ |
| `openapi-typescript` | (CONTEXT names lib, no version) | 7.13.0 | ✓ |
| `fastapi-azure-auth` | 5.x | 5.2.0 | ✓ pin `>=5.2,<6.0` |

All bumps are minor-version-compatible; no breaking changes flagged.

---

## Architecture Patterns

### System Architecture Diagram

```
                                          ┌─────────────────────────────────┐
                                          │ Entra External ID tenant         │
                                          │ jobrag.ciamlogin.com             │
                                          │ - SPA app reg (PKCE)             │
                                          │ - API app reg (access_as_user)   │
                                          └──────────┬──────────────────────┘
                                                     │ OIDC discovery
                                                     │ /v2.0/.well-known/openid-configuration
                                                     ▼
                              MSAL JWT (iss=ciamlogin, aud=api://<api-app-id>)
                                                     │
        ┌────────────────────────────────────────────┼────────────────────────────────┐
        │                                            │                                │
        │ Browser (SWA-hosted SPA)                   │ ACA Container App (FastAPI)   │
        │                                            │                                │
        │  ┌─────────────────────┐                   │  ┌──────────────────────────┐ │
        │  │ main.tsx            │                   │  │ azure_scheme =           │ │
        │  │ ─────────────────── │                   │  │  B2CMultiTenantAuthCBear │ │
        │  │ 1. msalInstance     │                   │  │  (openid_config_url=     │ │
        │  │    .initialize()    │                   │  │   ciamlogin.com/{tid}/v2.│ │
        │  │ 2. handleRedirect-  │                   │  │   0/.well-known/...)     │ │
        │  │    Promise()        │                   │  └────────┬─────────────────┘ │
        │  │ 3. createRoot()     │                   │           │                   │
        │  │    .render()        │                   │           ▼                   │
        │  │                     │                   │  ┌──────────────────────────┐ │
        │  │ MsalProvider        │                   │  │ get_current_user_id()    │ │
        │  │  > QueryClientProv  │                   │  │ Depends(azure_scheme)    │ │
        │  │   > BrowserRouter   │                   │  │  ├─ oid == settings.     │ │
        │  │    > ErrorBoundary  │                   │  │  │   seeded_user_entra_  │ │
        │  │     > App           │                   │  │  │   oid?               │ │
        │  └─────────┬───────────┘                   │  │  ├─ no → 403 +          │ │
        │            │                               │  │  │   log_rejected_oid   │ │
        │            ▼                               │  │  └─ yes → seeded_user_id │ │
        │  ┌─────────────────────┐                   │  └────────┬─────────────────┘ │
        │  │ <AuthGate>          │                   │           │                   │
        │  │  useIsAuthenticated │                   │           ▼                   │
        │  │  ├─ false → login-  │                   │  ┌──────────────────────────┐ │
        │  │  │   Redirect       │                   │  │ /match /gaps /ingest     │ │
        │  │  └─ true → Outlet   │  fetch w/ Bearer │  │ /agent /agent/stream     │ │
        │  └─────────┬───────────┘ ─────────────────┼─▶│ (already-wired Depends)  │ │
        │            │                               │  └──────────────────────────┘ │
        │            ▼                               │                                │
        │  ┌─────────────────────┐                   │  ┌──────────────────────────┐ │
        │  │ Route tree          │                   │  │ Alembic 0005 migration   │ │
        │  │ /dashboard /chat... │                   │  │ runs on init_db() at     │ │
        │  │ Suspense + lazy     │                   │  │ container startup        │ │
        │  │ RouteSkeleton       │                   │  │ - ADD COLUMN entra_oid   │ │
        │  └─────────┬───────────┘                   │  │ - UPDATE seeded row if   │ │
        │            │                               │  │   SEEDED_USER_ENTRA_OID  │ │
        │            ▼                               │  │   env set                │ │
        │  ┌─────────────────────┐                   │  └──────────────────────────┘ │
        │  │ authedFetch(...)    │                   │                                │
        │  │ ─────────────────── │   API_SCOPE       └────────────────┬───────────────┘
        │  │ acquireTokenSilent  │  ◀─ silent refresh                  │
        │  │  ├─ ok → Bearer +   │                                     │
        │  │  │   fetch          │                                     │
        │  │  ├─ Interaction-    │                                     │
        │  │  │   Required → re- │                                     │
        │  │  │   direct         │                                     │
        │  │  └─ 401 → retry-1   │                                     │
        │  └─────────┬───────────┘                                     │
        │            │                                                  │
        │            ▼                                                  │
        │  ┌─────────────────────┐                                     │
        │  │ TanStack Query      │                                     │
        │  │ + service modules   │                                     │
        │  │ (jobs/profile/...)  │                                     │
        │  └─────────────────────┘                                     │
        │                                                              │
        │  ┌─────────────────────┐                                     │
        │  │ readSSEStream()     │ ◀── /agent/stream (SSE) ────────────┘
        │  │ async generator     │
        │  │ over response.body  │
        │  │ → AgentEvent[]      │
        │  └─────────────────────┘
        └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │ Adrian-local Terraform (infra/external/, local state, gitignored)              │
  │ ─ creates SPA + API app regs in External tenant                                 │
  │ ─ outputs: spa_client_id, api_client_id, api_audience_uri                       │
  │ ─ outputs pasted into: frontend/.env.production (committed, public)             │
  │                        infra/envs/prod/prod.tfvars.local (gitignored)           │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `msalInstance` (singleton) | `frontend/src/auth/msal.ts` | One `PublicClientApplication` per app. Created from `msalConfig` (env-derived). Exported as default; imported by `main.tsx` (initialize+handleRedirect) and `authedFetch.ts` (acquireTokenSilent). |
| `MsalProvider` (lib) | `frontend/src/main.tsx` | Outermost provider; makes `useMsal()` reachable for `AuthGate`, `authedFetch`, `AccessDenied`. |
| `QueryClient` (singleton) | `frontend/src/api/queryClient.ts` | One TanStack Query client; `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 2`, `networkMode: 'online'`. |
| `BrowserRouter` (lib) | `frontend/src/main.tsx` | Standard React Router v7 router. |
| `<ErrorBoundary>` | `frontend/src/components/ErrorBoundary.tsx` | Wraps `<App/>`. Renders global error card with "Back to dashboard" + "Reload" + `<details>` for stack. |
| `<App>` | `frontend/src/App.tsx` | Routes tree. Layout route wraps `<AuthGate><AppShell/></AuthGate>`. AccessDenied + NotFound outside layout. |
| `<AuthGate>` | `frontend/src/components/AuthGate.tsx` | `useIsAuthenticated()` → false ⇒ `loginRedirect`, true ⇒ `<Outlet/>`. |
| `<AppShell>` | `frontend/src/components/AppShell.tsx` | Top-nav (logo + Dashboard/Chat/Profile tabs + theme toggle + account dropdown) + `<Outlet/>` + sonner Toaster. |
| `<ThemeToggle>` | `frontend/src/components/ThemeToggle.tsx` | Reads/writes `localStorage['theme']`; applies `class="dark"` to `<html>`. |
| `<RouteSkeleton>` | `frontend/src/components/RouteSkeleton.tsx` | Suspense fallback for lazy routes. shadcn `Skeleton` rectangles. |
| `<EmptyState>` | `frontend/src/components/EmptyState.tsx` | Typed primitive `{ icon, heading, body, cta? }`. Used by `PhasePlaceholder` and Phase 5/6/7. |
| `<PhasePlaceholder>` | `frontend/src/components/PhasePlaceholder.tsx` | Composition over EmptyState for Dashboard/Chat/Profile stub pages. |
| `<AccessDeniedPage>` | `frontend/src/routes/AccessDenied.tsx` | Outside AuthGate. Decodes `idTokenClaims.oid` from `msalInstance.getActiveAccount()`; renders copy-block + runbook. |
| `<NotFoundPage>` | `frontend/src/routes/NotFound.tsx` | `*` fallback; EmptyState with "Go to dashboard" CTA. |
| `<DebugAgentStreamPage>` | `frontend/src/routes/DebugAgentStream.tsx` | Dev-flag-gated. Input + Send query + `<pre>` event log + `readSSEStream` consumer. |
| `authedFetch` | `frontend/src/api/authedFetch.ts` | Native fetch wrapper. acquireTokenSilent → Bearer attach → InteractionRequired catch → 401 retry. |
| `readSSEStream` | `frontend/src/api/readSSEStream.ts` | `async function*` over `response.body.getReader()`. Yields typed `AgentEvent`. Cancellable via `init.signal`. |
| Service modules | `frontend/src/api/{jobs,profile,agent,health}.ts` | Typed async functions wrapping `authedFetch` + codegen types. Phase 4 ships `health.ts` (minimum); Phase 5/6/7 add `jobs.ts`/`profile.ts`/`agent.ts`. |
| `types.ts` (codegen) | `frontend/src/api/types.ts` | `openapi-typescript`-generated `paths` + `components` types. Committed; regenerated on backend schema changes. |
| `azure_scheme` (module-level) | `src/job_rag/api/auth.py` | One `B2CMultiTenantAuthorizationCodeBearer` instance (or `SingleTenantAzureAuthorizationCodeBearer` if Q1 resolved otherwise). Validates JWT on every protected request. |
| `get_current_user_id()` rewritten body | `src/job_rag/api/auth.py` | `Depends(azure_scheme)` → User; check `user.claims['oid'] == settings.seeded_user_entra_oid` else 403; return `settings.seeded_user_id`. |
| `0005_adopt_entra_oid.py` migration | `alembic/versions/0005_adopt_entra_oid.py` | ADD COLUMN `entra_oid VARCHAR NULL` on `user_db`; idempotent UPDATE if `SEEDED_USER_ENTRA_OID` env set. |
| `infra/external/` | `infra/external/` | Local-state Terraform. SPA + API app regs + access_as_user scope + admin consent. Mirrors `infra/bootstrap/` shape. |

### Recommended Project Structure

```
frontend/                                          # D-01
├── .env.local                                      # gitignored — dev values (VITE_API_BASE_URL=http://localhost:8000, dev SPA client ID, etc.)
├── .env.production                                 # committed — prod values (no secrets — all VITE_* are public-by-design per D-03)
├── components.json                                 # shadcn config (style=new-york, base-color=zinc)
├── eslint.config.js                                # flat config (typescript-eslint v8 + react-hooks + react-refresh)
├── .prettierrc                                     # standard config
├── index.html                                      # Vite entry HTML; <html lang="en">, <body class="dark"> if first-paint policy demands
├── package.json
├── tsconfig.json                                   # strict: true, moduleResolution: bundler, paths { "@/*": ["./src/*"] }
├── vite.config.ts                                  # plugins: react, tailwindcss; resolve.alias { "@": "./src" }; server.proxy: /api → http://localhost:8000 (SSE-friendly); test.* config
├── public/                                         # static assets (favicon, etc.)
├── src/
│   ├── main.tsx                                    # D-05 race fix LIVES HERE (see Code Examples)
│   ├── App.tsx                                     # Routes tree (D-17, D-18)
│   ├── app.css                                     # @import "tailwindcss"; + @theme inline { ... } (Tailwind v4 token block)
│   ├── api/                                        # D-13, D-14, D-15, D-16
│   │   ├── authedFetch.ts                          # Native fetch + MSAL interceptor
│   │   ├── readSSEStream.ts                        # SSE async generator
│   │   ├── queryClient.ts                          # TanStack Query singleton
│   │   ├── types.ts                                # openapi-typescript codegen output (committed)
│   │   ├── health.ts                               # Service module (only Phase 4 ships)
│   │   ├── jobs.ts                                 # Stub — Phase 5 fills
│   │   ├── profile.ts                              # Stub — Phase 7 fills
│   │   └── agent.ts                                # Stub — Phase 6 fills
│   ├── auth/                                       # MSAL config + scope constants
│   │   ├── msal.ts                                 # msalInstance singleton + msalConfig + loginRequest
│   │   └── scopes.ts                               # export const API_SCOPE = `api://${VITE_API_AUDIENCE}/access_as_user`
│   ├── components/                                 # D-18, D-19, D-20
│   │   ├── AppShell.tsx
│   │   ├── AuthGate.tsx
│   │   ├── ThemeToggle.tsx
│   │   ├── ErrorBoundary.tsx
│   │   ├── RouteSkeleton.tsx
│   │   ├── EmptyState.tsx
│   │   ├── PhasePlaceholder.tsx
│   │   └── ui/                                     # shadcn-generated primitives (button.tsx, card.tsx, skeleton.tsx, dropdown-menu.tsx, dialog.tsx, sonner.tsx, input.tsx, badge.tsx)
│   ├── lib/
│   │   └── utils.ts                                # shadcn-generated `cn()` helper
│   ├── routes/                                     # Page-level components
│   │   ├── AccessDenied.tsx
│   │   ├── NotFound.tsx
│   │   └── DebugAgentStream.tsx
│   └── test/
│       └── setup.ts                                # @testing-library/jest-dom matchers + cleanup() afterEach
├── tests/                                          # Vitest tests colocated by-feature (or src/**/*.test.tsx if preferred)
│   ├── AuthGate.test.tsx
│   ├── authedFetch.test.ts
│   ├── readSSEStream.test.ts
│   ├── ThemeToggle.test.tsx
│   └── AppShell.test.tsx
└── node_modules/                                   # gitignored

infra/external/                                     # D-02 (mirrors infra/bootstrap/)
├── .gitignore                                      # .terraform/ + terraform.tfstate* + *.tfvars.local
├── README.md                                       # Runbook (mirrors infra/bootstrap/README.md shape)
├── main.tf                                         # azuread_application × 2 + azuread_service_principal × 2 + scope UUID + permission grant + admin consent
├── outputs.tf                                      # spa_client_id, api_client_id, api_audience_uri, api_scope_name
├── provider.tf                                     # azuread provider only (NO azurerm); tenant_id from var.tenant_id_external
├── variables.tf                                    # tenant_id_external, tenant_subdomain, swa_origin, dev_redirect_uri (multi-redirect-URI per Phase 3 D-06)
├── terraform.tfvars.local                          # gitignored — Adrian's values
└── terraform.tfstate                               # gitignored

src/job_rag/api/
└── auth.py                                         # D-08 function-body rewrite + module-level azure_scheme instance

src/job_rag/
└── config.py                                       # D-04 — 4 new Settings fields

alembic/versions/
└── 0005_adopt_entra_oid.py                         # D-10 — add entra_oid column + idempotent UPDATE
```

### Pattern 1: Layered routing with AuthGate-wrapped layout

**What:** One layout route owns the `<AuthGate><AppShell><Outlet/></AppShell></AuthGate>` chain. Every protected route mounts inside that `<Outlet/>`. The OID-display `/access-denied` and 404 routes mount OUTSIDE.

**When to use:** Always, when (a) every page needs the same chrome (top-nav) AND (b) every page except a small finite set needs auth.

**Example:**
```tsx
// frontend/src/App.tsx
import { Routes, Route, Navigate } from "react-router"
import { lazy, Suspense } from "react"
import { AuthGate } from "@/components/AuthGate"
import { AppShell } from "@/components/AppShell"
import { RouteSkeleton } from "@/components/RouteSkeleton"
import { AccessDeniedPage } from "@/routes/AccessDenied"
import { NotFoundPage } from "@/routes/NotFound"
import { PhasePlaceholder } from "@/components/PhasePlaceholder"

const DebugAgentStreamPage = lazy(() => import("@/routes/DebugAgentStream"))
const DEBUG_PAGES_ENABLED =
  import.meta.env.DEV || import.meta.env.VITE_DEBUG_PAGES === "true"

export function App() {
  return (
    <Routes>
      {/* Protected layout — AuthGate + AppShell wraps everything inside */}
      <Route
        element={
          <AuthGate>
            <AppShell />
          </AuthGate>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route
          path="/dashboard"
          element={<PhasePlaceholder phase={5} feature="Dashboard" />}
        />
        <Route
          path="/chat"
          element={<PhasePlaceholder phase={6} feature="Chat" />}
        />
        <Route
          path="/profile"
          element={<PhasePlaceholder phase={7} feature="Profile" />}
        />
        {DEBUG_PAGES_ENABLED && (
          <Route
            path="/debug/agent-stream"
            element={
              <Suspense fallback={<RouteSkeleton />}>
                <DebugAgentStreamPage />
              </Suspense>
            }
          />
        )}
      </Route>

      {/* OUTSIDE AuthGate — no infinite-redirect loop on 403 */}
      <Route path="/access-denied" element={<AccessDeniedPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
```

### Pattern 2: Layered loading/error states (D-19)

**What:** Four distinct layers, one per concern:
1. **Root `<ErrorBoundary>`** — render-error catch-all
2. **Per-route `<Suspense fallback={<RouteSkeleton/>}/>`** — React.lazy code-split loading
3. **Per-feature shadcn `Skeleton`** — `useQuery().isPending`
4. **Per-feature typed `<EmptyState>`** — "no data matches filter" / "ask anything" / "upload your resume"

**When to use:** Always. Each layer catches what the layers above don't. Never overlap.

**Example:**
```tsx
// Layer 1 — root error boundary (frontend/src/main.tsx)
<ErrorBoundary FallbackComponent={GlobalErrorFallback}>
  <App />
</ErrorBoundary>

// Layer 2 — per-route Suspense (frontend/src/App.tsx — see Pattern 1)
<Suspense fallback={<RouteSkeleton />}>
  <DashboardPage />
</Suspense>

// Layer 3 — per-feature skeleton (Phase 5 example, not Phase 4)
const { data, isPending } = useQuery({ queryKey: [...], queryFn: ... })
if (isPending) return <Skeleton className="h-12 w-full" />

// Layer 4 — per-feature EmptyState (frontend/src/components/EmptyState.tsx + PhasePlaceholder.tsx)
<EmptyState icon={BarChart3} heading="Dashboard coming soon" body="..." />
```

### Pattern 3: TanStack Query + AuthedFetch composition

**What:** TanStack Query's `queryFn` argument receives `{ signal }`. Pass it through to `authedFetch` → `fetch` → backend. Cancellation propagates naturally.

**Example (Phase 5 will write something like this; Phase 4 ships the wiring):**
```tsx
// frontend/src/api/jobs.ts (Phase 5 fills)
import { authedFetch } from "./authedFetch"
import type { components } from "./types"

type SearchResponse = components["schemas"]["SearchResponse"]
type SearchParams = { query: string; topK?: number }

export async function searchJobs(
  params: SearchParams,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const url = new URL(`${import.meta.env.VITE_API_BASE_URL}/search`)
  url.searchParams.set("query", params.query)
  if (params.topK) url.searchParams.set("top_k", String(params.topK))
  const response = await authedFetch(url.toString(), { signal })
  if (!response.ok) throw new Error(`Search failed: ${response.status}`)
  return response.json()
}

// Component (Phase 5)
const { data, isPending, error } = useQuery({
  queryKey: ["search", params],
  queryFn: ({ signal }) => searchJobs(params, signal),
})
```

### Pattern 4: `function-body rewrite` for backend auth (Phase 1 D-10 carry)

**What:** Phase 1 wired `Depends(get_current_user_id)` on every protected route. The function body returns the seeded UUID. Phase 4 rewrites ONLY the function body — no call-site changes anywhere.

**When to use:** Whenever an early phase pre-wires a dependency hook so a later phase can swap the implementation.

**See "Code Examples" §`get_current_user_id` body rewrite below for the exact rewritten body.**

### Anti-Patterns to Avoid

- **Calling `handleRedirectPromise` inside `useEffect`.** D-05 explicitly forbids. Causes flash-of-login on hard refresh (Pitfall 11). Always do it before `createRoot().render()`.
- **Using MSAL React's `AuthenticatedTemplate` / `UnauthenticatedTemplate` for the protected-route layer.** They work for *display gates* but make conditional redirects awkward. D-18 locks the custom `<AuthGate>` component.
- **Putting `/access-denied` inside the AuthGate.** Infinite redirect loop — backend 403 sends user to `/access-denied`, AuthGate sees they're authenticated (they are), but the call that triggered the 403 doesn't recover. Worse: if the user is NOT authenticated, the AuthGate immediately redirects them to login, never showing them their OID. Keep AccessDenied OUTSIDE the AuthGate.
- **Decoding the JWT on the frontend to make authorization decisions.** Backend already enforces. Frontend-side checks are theatre — anyone can patch the bundle. Only acceptable frontend JWT decode: showing the user their own `oid` for copy-paste on `/access-denied` (D-09).
- **Calling `acquireTokenSilent` from inside a React component using `useMsal()`'s `instance` synchronously without an effect.** The `instance` is stable, but calling silent-token at render time will cause re-render loops on token state change. The `authedFetch` wrapper does this OUTSIDE the React tree — that's the correct boundary.
- **Returning the rejected `oid` in the 403 response body.** Future multi-user surface would leak who-has-tried-to-sign-up. Generic message in body; structured `log.warning("user_not_allowlisted", rejected_oid=...)` for LAW audit (D-09 explicit).
- **`refetchOnWindowFocus: true`** (TanStack Query default). Combined with MSAL's silent refresh on focus, causes a spurious refetch storm on every Cmd+Tab. Locked in CONTEXT.md Claude's Discretion: `refetchOnWindowFocus: false`.
- **`localStorage` for MSAL cache.** D-06 locks `sessionStorage`.
- **Adding `GZipMiddleware` to FastAPI.** Already-known Phase 1 anti-pattern (Pitfall 6). Breaks SSE. Phase 4 doesn't touch the middleware stack but reaffirms the rule.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT signature + iss + aud + exp validation against JWKS | Hand-rolled PyJWT + jwks_client + LRU | `fastapi-azure-auth` 5.2 | Library handles JWKS rotation (24h cache), discovery, leeway, iss callable for tenant whitelist, dependency injection. 5 lines vs 150. |
| OpenAPI → TypeScript types | Manual TS interfaces for every route | `openapi-typescript` 7.13 | One npm script; auto-handles Pydantic discriminated unions (Phase 1 D-04 AgentEvent) as TS tagged unions. Drift caught by `git diff --exit-code`. |
| MSAL-React hooks + provider | Custom MSAL context | `@azure/msal-react` `MsalProvider` + `useMsal()` + `useIsAuthenticated()` | Official Microsoft library; handles initialization order, in-progress state, account-active selection. |
| Error boundary (React class component) | `class extends Component` w/ getDerivedStateFromError | `react-error-boundary` | Hooks-friendly API, `useErrorBoundary` hook for imperative throws, reset semantics built-in. |
| SSE parsing of `text/event-stream` | EventSource (can't attach Bearer per CHAT-01) | `readSSEStream` over `response.body.getReader() + TextDecoder` | 60 LOC; native browser primitives; cancellable via AbortSignal; yields typed events from `openapi-typescript` codegen. eventsource-parser npm package deferred per D-16 alternative. |
| Theme persistence | Custom React context | `localStorage['theme']` + `class="dark"` on `<html>` + `matchMedia('(prefers-color-scheme: dark)')` fallback | Native browser primitives. No React state for global theme — just write the class and re-render via document operation. |
| Toast notifications | Custom positioned overlay | `sonner` (shadcn-shipped) | Accessible (`role="status"`), respects `prefers-reduced-motion`, integrates with shadcn theme tokens, one `<Toaster />` mount in AppShell. |
| Skeleton placeholders | Custom CSS pulse | shadcn `Skeleton` | Theme-token aware; `animate-pulse` respects `prefers-reduced-motion` via `motion-reduce:animate-none` Tailwind utility. |
| Routing | Manual `<a>` + `history.pushState` | `react-router` 7 | First-class TypeScript, layout routes (the AppShell wrap), `<Outlet/>`, `Navigate replace`, lazy-load support. |
| Tailwind config | Manual PostCSS pipeline | `@tailwindcss/vite` (Tailwind v4) | v4 owns its own integration; PostCSS is legacy. |
| Tailwind theme tokens | Custom CSS variables | shadcn-generated `app.css` `@theme inline { ... }` block | shadcn init produces the canonical token set; tweaking outside the set breaks future shadcn component installs. |
| Icons | Custom SVGs | `lucide-react` | shadcn-default; tree-shakeable; UI-SPEC §10 names specific icons (BarChart3, MessageSquare, User, FileQuestion, Sun, Moon). |

**Key insight:** This is a phase where every meaningful problem already has a battle-tested library. The only justified hand-rolls are (a) the ~60-LOC `readSSEStream` (one of one consumer in v1) and (b) the ~30-50-LOC `authedFetch` wrapper (because none of the alternatives — axios, ofetch — give us anything beyond what we'd write ourselves). Everything else gets a library import.

---

## Common Pitfalls

### Pitfall 1: `SingleTenantAzureAuthorizationCodeBearer` cannot reach `ciamlogin.com` discovery

**What goes wrong:** Following CONTEXT.md D-07 literally, you instantiate `SingleTenantAzureAuthorizationCodeBearer(app_client_id=..., tenant_id=...)`. The class hard-codes the discovery URL to `https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration` — the workforce endpoint. Entra External ID's tokens are issued by `https://{subdomain}.ciamlogin.com/{tenant_id}/v2.0` (different host). On first request the library fetches the workforce discovery doc, gets back a JWKS for a different tenant's signing keys, fails to verify Adrian's JWT signature, and returns 401 with "Unable to verify token."

**Why it happens:** Microsoft's `login.microsoftonline.com` and `*.ciamlogin.com` are different identity endpoints. CIAM tenants live on the ciamlogin host. The fastapi-azure-auth `SingleTenantAzureAuthorizationCodeBearer` class predates Entra External ID and was designed for workforce-tenant single-tenant scenarios. [VERIFIED: source `Intility/fastapi-azure-auth/blob/main/fastapi_azure_auth/auth.py` constructor signatures fetched 2026-05-19 — `openid_config_url` is NOT in `SingleTenantAzureAuthorizationCodeBearer`'s parameter list but IS in `B2CMultiTenantAuthorizationCodeBearer`'s.]

**How to avoid:** Use `B2CMultiTenantAuthorizationCodeBearer` instead. It accepts `openid_config_url` precisely for this case. The "B2C" in the name refers to historical naming when CIAM was B2C; it works for Entra External ID because the discovery URL shape is identical. Pass:

```python
azure_scheme = B2CMultiTenantAuthorizationCodeBearer(
    app_client_id=settings.backend_audience.removeprefix("api://"),  # the API app reg client_id
    openid_config_url=(
        f"https://{settings.entra_tenant_subdomain}.ciamlogin.com/"
        f"{settings.entra_tenant_id}/v2.0/.well-known/openid-configuration"
    ),
    scopes={
        f"{settings.backend_audience}/access_as_user": "access_as_user",
    },
    validate_iss=True,  # default; lib validates iss against the discovered openid_cfg['issuer']
)
```

**Warning signs:**
- 401 with `Unable to verify token` even though the JWT looks fine in jwt.io
- `iss` claim in the JWT is `https://{subdomain}.ciamlogin.com/{tenant_id}/v2.0` but the library is fetching from `login.microsoftonline.com`
- A logged warning from fastapi-azure-auth like `Issuer 'https://jobrag.ciamlogin.com/...' does not match expected 'https://login.microsoftonline.com/...'`

**Confidence:** HIGH — verified from upstream source code 2026-05-19.

### Pitfall 2: MSAL redirect URI registered as "Web" instead of "Single-page application"

**What goes wrong:** App registration is created with the default Web platform. Initial `loginRedirect` works (because the initial redirect is OK), but `acquireTokenSilent` returns `invalid_grant` or quiet 404s. User appears logged-in but every API call fails after the first hour. The portal shows green-checkmark "Eligible for PKCE" ONLY when the platform is set to SPA. [CITED: PITFALLS.md §2; HIGH confidence]

**How to avoid:** In `infra/external/main.tf`, use the `single_page_application { redirect_uris = [...] }` block on `azuread_application`, NOT `web {}` and NOT `public_client {}`. Phase 3 D-07 already locks this shape. After apply, verify in portal blade Authentication that redirect URIs appear under "Single-page application" with the green PKCE checkmark.

**Warning signs:** `AADSTS9002326 — Cross-origin token redemption is permitted only for the 'Single-Page Application' client-type`.

### Pitfall 3: Vite `process.env` access vs `import.meta.env`

**What goes wrong:** Old Vite / CRA tutorials use `process.env.REACT_APP_*` for build-time env. Vite uses `import.meta.env.VITE_*`. Confusion produces `undefined` reads at runtime, MSAL config crashes with "tenant ID is empty," and the SPA infinite-redirects.

**How to avoid:** All five VITE_* values accessed exclusively via `import.meta.env.VITE_*`. TypeScript types come from `vite/client` (added to `tsconfig.json` `types` array OR via `/// <reference types="vite/client" />` in `vite-env.d.ts`). For each VITE_* var, ADD an entry to `vite-env.d.ts` so missing-env errors surface at compile time:

```ts
// frontend/src/vite-env.d.ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TENANT_SUBDOMAIN: string
  readonly VITE_TENANT_ID: string
  readonly VITE_SPA_CLIENT_ID: string
  readonly VITE_API_AUDIENCE: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_DEBUG_PAGES?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

**Warning signs:** Build succeeds but runtime `Cannot read properties of undefined (reading 'split')` on MSAL config; or MSAL "Authority URL is invalid" because the subdomain placeholder didn't get baked in.

### Pitfall 4: `acquireTokenSilent` race with `handleRedirectPromise` during cold load

**What goes wrong:** `authedFetch` calls `acquireTokenSilent` from inside a TanStack Query `queryFn` on first paint. MSAL has not yet finished `handleRedirectPromise`. Throws `uninitialized_public_client_application` or `interaction_in_progress`. [CITED: PITFALLS.md §11; MSAL issues #6785/#6893/#7561; HIGH confidence]

**How to avoid:** D-05 race fix in `main.tsx` is the primary mitigation: `await msalInstance.initialize(); await msalInstance.handleRedirectPromise();` BEFORE `createRoot().render()`. With this in place, the first paint is guaranteed to happen with MSAL in a known state. AuthGate then checks `useIsAuthenticated()` synchronously and either redirects to login OR renders the protected content. By the time `authedFetch` runs (component is mounted, query is fired), MSAL is fully initialized.

**Defence in depth:** `authedFetch` catches `BrowserAuthError` with name `uninitialized_public_client_application` and re-throws as a typed network error so TanStack Query's `error` boundary surfaces it cleanly instead of a cryptic MSAL message. (This is belt-and-suspenders — should never fire if D-05 works.)

**Warning signs:** Flash of login page on hard refresh while already logged in. `BrowserAuthError: uninitialized_public_client_application` in console. `monitor_window_timeout` after iframe silent refresh blocked.

### Pitfall 5: SSE chunk boundary breaks JSON parsing

**What goes wrong:** `readSSEStream` reads `response.body.getReader()` in chunks. Each chunk is N bytes — could split a multi-byte UTF-8 character (TextDecoder w/o `{stream: true}` produces a replacement char) AND could split an SSE frame mid-`data:`. Naive implementations call `JSON.parse(chunk.split('data: ')[1])` and crash on partial frames.

**How to avoid:** Two disciplines:

1. **Use `TextDecoder` with `{stream: true}`** — decoder retains incomplete bytes between calls.
2. **Buffer until `\n\n` boundary** — accumulate decoded text in a buffer string; only parse frames bounded by `\n\n`; carry the trailing partial-frame remainder over to the next iteration.

See Code Examples §`readSSEStream.ts` for the canonical implementation.

**Warning signs:** Random `SyntaxError: Unexpected end of JSON input`; corrupted strings in event content; one large response arriving as a single chunk in dev but fragmented in prod (network-dependent).

### Pitfall 6: TanStack Query firing API calls before login completes

**What goes wrong:** A protected page mounts a component with `useQuery({...})` before AuthGate redirects unauthenticated user to login. The query fires, `authedFetch` calls `acquireTokenSilent`, throws, TanStack Query enters error state — the error message is shown instead of the login redirect happening cleanly.

**How to avoid:** `<AuthGate>` is positioned ABOVE `<Outlet/>`. It returns `null` (or `<RouteSkeleton/>`) while redirecting unauthenticated users — Outlet doesn't render — no query mounts. Pattern from Code Examples §AuthGate.tsx:

```tsx
if (!isAuthenticated && inProgress === InteractionStatus.None) {
  msalInstance.loginRedirect(loginRequest)
  return null  // do NOT render children — Outlet won't mount, queries won't fire
}
```

**Warning signs:** Login redirect happens AFTER a brief error flash. `useQuery` cached an error before login completed and continues showing it post-login.

### Pitfall 7: `terminationGracePeriodSeconds` + SSE drain interaction

**What goes wrong:** Phase 1 already wired the FastAPI app-level shutdown drain (anyio.Event + active_streams set + 30s wait_for). Phase 3 wired `terminationGracePeriodSeconds = 120` on the ACA Container App. But Phase 4 adds a new long-running SSE consumer in `/debug/agent-stream`. If Adrian deploys mid-debug-stream, the drain should let his stream finish. **No new code needed** — the existing drain catches it. But: documentation should remind testers that the dev-page is subject to the same drain semantics as `/agent/stream`.

**How to avoid:** Plan a smoke test in 04-SMOKE.md that runs `/debug/agent-stream` against a deployed `/agent/stream`, triggers an ACA revision swap mid-stream, and verifies the stream completes cleanly with a `final` event (not a connection reset). Phase 1's `shutdown` SSE error event reason already covers this case.

### Pitfall 8: Vite dev proxy + SSE buffering

**What goes wrong:** Vite's dev proxy (`server.proxy: { '/api': 'http://localhost:8000' }`) uses `http-proxy` under the hood. By default, http-proxy may buffer responses, causing SSE to arrive all-at-once on `localhost` development. Then prod (where SSE goes direct to ACA, no Vite proxy) works fine — dev behaviour misleads.

**How to avoid:** Configure the dev proxy with SSE-friendly options:

```ts
// vite.config.ts (server section)
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
      // SSE-friendly: don't buffer response
      configure: (proxy) => {
        proxy.on('proxyRes', (proxyRes) => {
          proxyRes.headers['x-accel-buffering'] = 'no'
          proxyRes.headers['cache-control'] = 'no-cache, no-transform'
        })
      },
    },
  },
},
```

Alternative: in dev mode, set `VITE_API_BASE_URL=http://localhost:8000` directly (bypass the proxy entirely). CORS in Phase 1's `ALLOWED_ORIGINS` already includes `http://localhost:5173`. The proxy is optional UX sugar for dev — it gives same-origin semantics matching prod, but adds an SSE-buffering risk. Recommend bypass-by-default; document the proxy as opt-in.

**Warning signs:** SSE works in prod, not in dev. Curling `localhost:5173/api/agent/stream` shows buffered output but `localhost:8000/agent/stream` direct streams correctly.

### Pitfall 9: openapi-typescript codegen needs a running backend

**What goes wrong:** `npm run codegen` calls `openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts`. If backend isn't running (CI, fresh clone, dev machine without docker-compose up), codegen fails with `ENOTFOUND localhost`. CI drift-guard fails confusingly.

**How to avoid:** Two paths:
1. **Local dev:** require docker-compose up before `npm run codegen`. Document in `frontend/README.md`.
2. **CI drift-guard:** generate against a committed snapshot OpenAPI file (`frontend/openapi.snapshot.json`) instead of a live backend. This makes drift detection portable AND catches the case where backend was changed but snapshot wasn't refreshed. Add a paired `npm run codegen:refresh-snapshot` that hits live backend + writes the snapshot file. The drift-guard then:
   - Re-runs `npm run codegen` against the snapshot
   - `git diff --exit-code src/api/types.ts`
   - Fails CI if either is non-zero

Recommend approach: support both — dev workflow uses live backend (`npm run codegen`), CI workflow uses snapshot (`npm run codegen:ci`) + `git diff --exit-code`.

### Pitfall 10: First-paint flash even with D-05 race fix

**What goes wrong:** Even with `await msalInstance.initialize() + await handleRedirectPromise()` in main.tsx, the browser shows a blank window for 50-150ms while those awaits resolve (longer on cold load). UI-SPEC §16 explicitly accepts this: "show nothing — browser's natural blank page" rather than maintain a separate HTML splash.

**How to avoid:** Don't try to. Document the acceptance in `frontend/README.md` and the design contract. If portfolio polish later wants a faux-loading state, add a centered logo to `index.html` body that's instantly replaced by `<App/>` mount — but that's UI-SPEC §16 v2.

**Important nuance:** Setting `<html class="dark">` in `index.html` (before any JS runs) prevents a flash-of-white when the default theme is dark and the user is on a slow connection. Add a small inline script in `<head>`:

```html
<!-- index.html, in <head> -->
<script>
  // Apply persisted theme before paint to avoid FOUC.
  // No imports — must be inline.
  (function () {
    var t = localStorage.getItem('theme');
    if (!t) {
      t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    if (t === 'dark') document.documentElement.classList.add('dark');
  })();
</script>
```

This is one of the few defensible inline `<script>` cases. Document it clearly so it doesn't get sanitized away.

### Pitfall 11: `logoutRedirect` `postLogoutRedirectUri` not registered → 400

**What goes wrong:** D-12 calls `msalInstance.logoutRedirect({ postLogoutRedirectUri: SWA_origin })`. If the literal value of `SWA_origin` (e.g., `https://jobrag-prod-spa.azurestaticapps.net/`) is NOT in the SPA app reg's "Logout URL" / "Front-channel logout URL" list, Entra returns 400 with `AADSTS50011: The reply URL specified in the request does not match the reply URLs configured for the application`.

**How to avoid:** In `infra/external/main.tf`, the SPA app reg's `single_page_application` block must list BOTH:
- `redirect_uris` (for login)
- `logout_url` or post-logout URI separately if the provider expects it

The `azuread_application` v3 resource exposes:
```hcl
single_page_application {
  redirect_uris = [
    "https://${var.swa_origin}/",
    "http://localhost:5173/",  # dev
  ]
}
# Optionally:
web {
  logout_url = "https://${var.swa_origin}/"
}
```

If `logout_url` isn't supported on `single_page_application`, configure it via the broader `web` block — Entra applies post-logout redirect from the union of registered URIs. Document the exact field name in the runbook because the azuread provider's resource shape has shifted between minor versions.

**Warning signs:** Login works; logout produces a 400 on Entra side; user is stuck on `*.ciamlogin.com/oauth2/v2.0/logout?post_logout_redirect_uri=...` error page.

### Pitfall 12: `acquireTokenSilent` failure modes beyond `InteractionRequiredAuthError`

**What goes wrong:** D-11 catches `InteractionRequiredAuthError` → `acquireTokenRedirect`. But MSAL also throws:
- `BrowserAuthError: monitor_window_timeout` (iframe silent refresh blocked by 3rd-party-cookie policy — Pitfall 12 in PITFALLS.md)
- `BrowserAuthError: no_account_error` (active account cleared mid-session)
- `BrowserAuthError: silent_sso_error`

Treating all of these as "ignore + try again" leads to infinite retry loops. Treating them all as "InteractionRequired" → loginRedirect is too aggressive (no_account_error already means there's no session; redirect is the right call, but monitor_window_timeout might just need an interactive re-acquire).

**How to avoid:** Catch the broader `BrowserAuthError` family AND `InteractionRequiredAuthError`. Map to the right action:

```ts
import { InteractionRequiredAuthError, BrowserAuthError } from "@azure/msal-browser"

try {
  const result = await msalInstance.acquireTokenSilent({ scopes: [API_SCOPE] })
  return result.accessToken
} catch (err) {
  if (
    err instanceof InteractionRequiredAuthError ||
    (err instanceof BrowserAuthError &&
      ["monitor_window_timeout", "no_account_error", "silent_sso_error"].includes(err.errorCode))
  ) {
    await msalInstance.acquireTokenRedirect({ scopes: [API_SCOPE] })
    throw err  // unreachable — redirect navigates away; throw for type safety
  }
  throw err
}
```

**Warning signs:** Users intermittently see "Please sign in again" with no obvious cause (often Safari users — third-party-cookie blocking). Console shows `monitor_window_timeout` repeated in a loop.

### Pitfall 13: `sessionStorage` cache + SPA hard refresh = forced re-login per tab close

**What goes wrong:** D-06 picks sessionStorage explicitly for XSS-blast-radius reasons. Tradeoff: every tab close → user re-logs in next session. Acceptable for single-user portfolio. But the SPA-from-scratch experience can be confusing if not communicated — Adrian might think auth is broken.

**How to avoid:** Document the behaviour in `frontend/README.md` "Single-user UX" section. The first time per-session that Adrian opens the SPA, he sees a flash to login then back. No code change — just expectation-setting.

### Pitfall 14: `0005_adopt_entra_oid.py` SQL injection via `:oid` placeholder

**What goes wrong:** Migration reads `os.environ['SEEDED_USER_ENTRA_OID']` and uses it in an `UPDATE`. If naively interpolated as `f"UPDATE ... WHERE entra_oid = '{oid}'"`, a malicious env value injects SQL. The risk is low (env vars are set by Adrian via az keyvault) but trivial to avoid.

**How to avoid:** Use SQLAlchemy parameterized execution: `op.execute(text("UPDATE ... :oid").bindparams(oid=oid))`. See Code Examples §`0005_adopt_entra_oid.py`. Same pattern Phase 1 D-09 lays out.

### Pitfall 15: Codegen committed types and CI drift catch slow-feedback loop

**What goes wrong:** Backend Phase 5 plan changes an endpoint shape. CI drift-guard catches it on the backend PR. But the frontend plan in Phase 5 hasn't run codegen yet — fixing CI requires the backend dev to either run codegen themselves OR add a TODO that the frontend dev resolves. Friction.

**How to avoid:** Run codegen in CI as a step (don't just drift-check). On the backend PR, CI:
1. Spins up FastAPI (test fixtures + minimal startup)
2. Runs `npm run codegen` against the live test backend
3. `git diff --exit-code` — fail if drift
4. If drift: instructions point dev to `npm run codegen` locally + commit

This makes the contract explicit: ANY backend OpenAPI-affecting change requires a paired frontend types refresh in the same PR. The codegen-drift workflow shape is documented in Code Examples §CI frontend-ci job.

### Pitfall 16: SWA + ACA + `/api/` rewrite confusion (Phase 3 D-14 reaffirmed)

**What goes wrong:** Phase 3 D-14 explicitly chose direct CORS (SPA hits ACA hostname directly, NOT through SWA linked-API proxy) — because SWA proxy has 30-45s timeout that kills SSE. Phase 4 must not "fix" this by adding `staticwebapp.config.json` `/api/*` rewrites. PITFALLS.md §10 covers the broader case.

**How to avoid:** Don't add `staticwebapp.config.json`. Don't add `/api/*` rewrites. `VITE_API_BASE_URL` points DIRECTLY at the ACA FQDN in prod. CORS is the boundary. Phase 1 D-26's `ALLOWED_ORIGINS` env var already includes the SWA origin (Phase 3 DEPL-12 two-pass).

**Warning signs:** Anyone adding a `staticwebapp.config.json` with `routes: [{ route: "/api/*", rewrite: ... }]`. PR review red flag.

---

## Code Examples

Verified patterns; tagged by source.

### Scaffold + Tailwind v4 + shadcn init

```bash
# [CITED: STACK.md §1 + ui.shadcn.com/docs/installation/vite + CONTEXT.md D-20]
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install tailwindcss @tailwindcss/vite
npx shadcn@latest init -t vite
# Prompts:
#   - Which style would you like to use?            → New York
#   - Which color would you like to use as base?    → Zinc
#   - Would you like to use CSS variables?           → Yes
#   - Where is your global CSS file?                 → src/app.css
#   - Configure tsconfig paths?                      → Yes (@/* → src/*)

# First-wave components (UI-SPEC §5)
npx shadcn@latest add button card skeleton dropdown-menu dialog sonner input badge
```

Result: `components.json`, `src/app.css` (with `@import "tailwindcss"` and `@theme inline { ... }` block), `src/lib/utils.ts` (`cn()` helper), `src/components/ui/*.tsx` (shadcn primitives), `tsconfig.json` paths updated.

### `vite.config.ts`

```ts
// [VERIFIED: vitejs.dev/guide; CONTEXT.md Claude's Discretion]
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import path from "node:path"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // Direct API base URL (VITE_API_BASE_URL) is the canonical path in v1.
    // Proxy is OPTIONAL convenience for same-origin dev; see Pitfall 8.
    // proxy: {
    //   '/api': {
    //     target: 'http://localhost:8000',
    //     changeOrigin: true,
    //     rewrite: (path) => path.replace(/^\/api/, ''),
    //     configure: (proxy) => {
    //       proxy.on('proxyRes', (proxyRes) => {
    //         proxyRes.headers['x-accel-buffering'] = 'no'
    //       })
    //     },
    //   },
    // },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
  },
})
```

### `tsconfig.json` deltas (shadcn-init sets most; ensure path alias)

```jsonc
{
  "compilerOptions": {
    "strict": true,
    "moduleResolution": "bundler",
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    },
    "types": ["vite/client"]
  },
  "include": ["src", "tests"]
}
```

### `frontend/src/auth/msal.ts` — singleton + config

```ts
// [CITED: learn.microsoft.com/.../tutorial-single-page-app-react-sign-in-configure-authentication 2026 + CONTEXT.md D-03/D-05/D-06]
import { PublicClientApplication, type Configuration, LogLevel } from "@azure/msal-browser"

export const API_SCOPE = `${import.meta.env.VITE_API_AUDIENCE}/access_as_user`

const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_SPA_CLIENT_ID,
    authority: `https://${import.meta.env.VITE_TENANT_SUBDOMAIN}.ciamlogin.com/${import.meta.env.VITE_TENANT_ID}/v2.0`,
    knownAuthorities: [`${import.meta.env.VITE_TENANT_SUBDOMAIN}.ciamlogin.com`],
    redirectUri: window.location.origin + "/",
    postLogoutRedirectUri: window.location.origin + "/",
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: "sessionStorage",  // D-06
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: import.meta.env.DEV ? LogLevel.Verbose : LogLevel.Error,
      piiLoggingEnabled: false,
      loggerCallback: (_level, message) => {
        if (import.meta.env.DEV) console.log("[MSAL]", message)
      },
    },
  },
}

export const msalInstance = new PublicClientApplication(msalConfig)

export const loginRequest = {
  scopes: [API_SCOPE],
}
```

**Why `knownAuthorities`:** Required for non-Microsoft authorities (CIAM tenants on `ciamlogin.com`). Without it MSAL refuses to navigate to a non-`login.microsoftonline.com` authority for security reasons. [CITED: github.com/AzureAD/microsoft-authentication-library-for-js/issues — multiple]

### `frontend/src/main.tsx` — literal AUTH-07 race fix (D-05)

```tsx
// [CITED: PITFALLS.md §11 + CONTEXT.md D-05 + AUTH-07 verbatim]
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { MsalProvider } from "@azure/msal-react"
import { QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter } from "react-router"
import { ErrorBoundary } from "react-error-boundary"
import { msalInstance } from "@/auth/msal"
import { queryClient } from "@/api/queryClient"
import { App } from "@/App"
import { GlobalErrorFallback } from "@/components/ErrorBoundary"
import "@fontsource/geist-sans"
import "@fontsource/geist-mono"
import "@/app.css"

async function bootstrap() {
  // CRITICAL — D-05 / AUTH-07 race-fix.
  // Both awaits MUST resolve BEFORE createRoot().render() so MSAL is in a
  // known state when React first paints. Otherwise hard-refresh while
  // logged-in flashes the login page (PITFALLS.md §11).
  await msalInstance.initialize()
  await msalInstance.handleRedirectPromise()

  const rootEl = document.getElementById("root")
  if (!rootEl) throw new Error("Root element #root not found in index.html")

  createRoot(rootEl).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <ErrorBoundary FallbackComponent={GlobalErrorFallback}>
              <App />
            </ErrorBoundary>
          </BrowserRouter>
        </QueryClientProvider>
      </MsalProvider>
    </StrictMode>
  )
}

bootstrap().catch((err) => {
  // Fatal bootstrap failure — render a minimal error message.
  // No React tree yet; can't use ErrorBoundary. Last-resort surface.
  document.body.innerHTML = `
    <div style="font: 14px system-ui; padding: 2rem; max-width: 600px; margin: 4rem auto;">
      <h1>App failed to start</h1>
      <p>An error occurred while initializing the app. Please reload the page.</p>
      <pre style="white-space: pre-wrap; background: #eee; padding: 1rem; border-radius: 4px;">${String(err)}</pre>
    </div>
  `
})
```

### `frontend/src/api/queryClient.ts`

```ts
// [CITED: tanstack.com/query/v5; CONTEXT.md Claude's Discretion]
import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,                // 30s cache freshness
      refetchOnWindowFocus: false,      // see Pitfall §refetch-on-focus
      retry: 2,                         // 1 initial + 2 retries on transient errors
      networkMode: "online",            // pause when offline
    },
    mutations: {
      networkMode: "online",
      retry: 0,                          // never silently retry mutations
    },
  },
})
```

### `frontend/src/components/AuthGate.tsx`

```tsx
// [CITED: learn.microsoft.com/.../msal-react FAQ + CONTEXT.md D-18 + Pitfall 6]
import { useEffect } from "react"
import { Outlet } from "react-router"
import { useIsAuthenticated, useMsal } from "@azure/msal-react"
import { InteractionStatus } from "@azure/msal-browser"
import { loginRequest } from "@/auth/msal"
import { RouteSkeleton } from "./RouteSkeleton"

export function AuthGate() {
  const isAuthenticated = useIsAuthenticated()
  const { instance, inProgress } = useMsal()

  useEffect(() => {
    // Trigger redirect ONLY when there's nothing in flight already.
    // inProgress === None means MSAL is idle (initialize + redirect have completed per D-05).
    if (!isAuthenticated && inProgress === InteractionStatus.None) {
      instance.loginRedirect(loginRequest).catch((err) => {
        // Logging only — MSAL navigates away on success
        console.error("loginRedirect failed", err)
      })
    }
  }, [isAuthenticated, inProgress, instance])

  if (!isAuthenticated) {
    // Render skeleton — NOT a login form. The redirect is the only path to login UI.
    // Defensive: if inProgress !== None (rare with D-05 fix), still show skeleton
    // until MSAL settles.
    return <RouteSkeleton />
  }

  return <Outlet />
}
```

### `frontend/src/api/authedFetch.ts` (D-11, D-13)

```ts
// [CITED: learn.microsoft.com/.../scenario-spa-acquire-token + CONTEXT.md D-11/D-13 + Pitfall §acquireTokenSilent-failure-modes]
import { msalInstance, API_SCOPE } from "@/auth/msal"
import {
  InteractionRequiredAuthError,
  BrowserAuthError,
  type AuthenticationResult,
} from "@azure/msal-browser"

const INTERACTION_REQUIRED_CODES = new Set([
  "monitor_window_timeout",
  "no_account_error",
  "silent_sso_error",
])

async function acquireToken(): Promise<string> {
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0]
  if (!account) {
    // No account at all — must login. Throws by way of navigation.
    await msalInstance.acquireTokenRedirect({ scopes: [API_SCOPE] })
    throw new Error("Token acquisition required login redirect")
  }
  msalInstance.setActiveAccount(account)

  try {
    const result: AuthenticationResult = await msalInstance.acquireTokenSilent({
      scopes: [API_SCOPE],
      account,
    })
    return result.accessToken
  } catch (err) {
    if (
      err instanceof InteractionRequiredAuthError ||
      (err instanceof BrowserAuthError && INTERACTION_REQUIRED_CODES.has(err.errorCode))
    ) {
      // Hand off to MSAL — navigates away; this promise never resolves.
      await msalInstance.acquireTokenRedirect({ scopes: [API_SCOPE] })
      throw err
    }
    throw err
  }
}

export async function authedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  let token = await acquireToken()
  const headers = new Headers(init.headers)
  headers.set("Authorization", `Bearer ${token}`)

  let response = await fetch(input, { ...init, headers })

  // 401 retry-once after silent refresh (D-11)
  if (response.status === 401) {
    token = await acquireToken()
    headers.set("Authorization", `Bearer ${token}`)
    response = await fetch(input, { ...init, headers })
    if (response.status === 401) {
      // Two 401s in a row — token is fundamentally invalid; bounce to login.
      await msalInstance.acquireTokenRedirect({ scopes: [API_SCOPE] })
      throw new Error("Authentication required")
    }
  }

  return response
}
```

### `frontend/src/api/readSSEStream.ts` (D-16, ~60 LOC)

```ts
// [CITED: developer.mozilla.org/.../ReadableStream + html.spec.whatwg.org/multipage/server-sent-events + CONTEXT.md D-16 + Pitfall 5]
import type { components } from "./types"

// Type comes from openapi-typescript codegen (Phase 1 D-04 AgentEvent → tagged union)
export type AgentEvent = components["schemas"]["AgentEvent"]

/**
 * Parse a fetch Response with text/event-stream body into typed AgentEvent values.
 *
 * Pattern: response.body.getReader() yields Uint8Array chunks. TextDecoder
 * with {stream: true} handles partial multi-byte chars between chunks. Buffer
 * decoded text until \n\n frame boundary; parse data: lines as JSON.
 *
 * Cancellation: pass init.signal into the fetch call; the reader will throw
 * AbortError when signal fires, propagating cleanly out of for-await-of.
 *
 * Yields the JSON-parsed `data` payload (already typed as AgentEvent via the
 * codegen union). The SSE `event:` line is informational — the AgentEvent's
 * own `type` field is the discriminator.
 */
export async function* readSSEStream(
  response: Response,
): AsyncIterable<AgentEvent> {
  if (!response.body) {
    throw new Error("Response has no body — cannot stream")
  }
  if (!response.ok) {
    throw new Error(`SSE stream failed: ${response.status} ${response.statusText}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Process complete frames (separated by \n\n per SSE spec)
      let boundary: number
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)

        // Parse the frame's lines — only `data:` lines carry the JSON payload.
        // Ignore `event:`, `id:`, `retry:` lines (the AgentEvent.type field is
        // our actual discriminator; sse-starlette emits both but we don't need
        // the redundant event: line).
        const dataLines = frame
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
        if (dataLines.length === 0) continue

        const payload = dataLines.join("\n")
        try {
          const event = JSON.parse(payload) as AgentEvent
          yield event
        } catch (err) {
          console.warn("Failed to parse SSE frame", { payload, err })
          // Continue processing — don't blow up the stream on one bad frame
        }
      }
    }

    // Drain any remaining buffered text (rare — last frame should end with \n\n)
    const tail = decoder.decode()
    if (tail || buffer) {
      const final = buffer + tail
      if (final.trim()) {
        console.warn("SSE stream ended with unframed data", final)
      }
    }
  } finally {
    reader.releaseLock()
  }
}
```

**Usage (Phase 6 example):**
```ts
const response = await authedFetch(
  `${import.meta.env.VITE_API_BASE_URL}/agent/stream`,
  { method: "POST", body: JSON.stringify({ query }), headers: { "Content-Type": "application/json" }, signal },
)
for await (const event of readSSEStream(response)) {
  switch (event.type) {
    case "token": appendToken(event.content); break
    case "tool_start": renderToolChip(event); break
    case "tool_end": expandToolChip(event); break
    case "heartbeat": /* keepalive */ break
    case "final": markComplete(event); break
    case "error": showError(event); break
  }
}
```

### `frontend/src/routes/AccessDenied.tsx` (D-09)

```tsx
// [CITED: UI-SPEC §8 + CONTEXT.md D-09]
import { useEffect, useState } from "react"
import { msalInstance, loginRequest } from "@/auth/msal"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { toast } from "sonner"

export function AccessDeniedPage() {
  const [oid, setOid] = useState<string | null>(null)

  useEffect(() => {
    const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0]
    setOid((account?.idTokenClaims?.oid as string | undefined) ?? null)
  }, [])

  async function copyOid() {
    if (!oid) return
    try {
      await navigator.clipboard.writeText(oid)
      toast.success("Copied to clipboard")
    } catch {
      toast.error("Couldn't copy — please select and copy manually")
    }
  }

  if (!oid) {
    // Empty-OID fallback — user landed here without logging in
    return (
      <Card className="max-w-2xl mx-auto mt-12 p-8 text-center">
        <h1 className="text-lg font-semibold mb-2">Sign in first</h1>
        <p className="text-sm text-muted-foreground mb-4">
          Sign in to see the account ID you need to share.
        </p>
        <Button onClick={() => msalInstance.loginRedirect(loginRequest)}>
          Sign in
        </Button>
      </Card>
    )
  }

  return (
    <Card className="max-w-2xl mx-auto mt-12 p-8">
      <h1 className="text-2xl font-semibold mb-2">Access denied</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Your account is not on the allowlist. Send the ID below to the administrator
        to request access.
      </p>

      <div role="region" aria-label="Your account ID" className="mb-6">
        <div className="text-xs text-muted-foreground mb-1">Your account ID</div>
        <pre className="font-mono text-sm bg-muted p-4 rounded mb-2 break-all">
          {oid}
        </pre>
        <Button onClick={copyOid}>Copy ID</Button>
      </div>

      <h2 className="text-lg font-semibold mb-2">Administrator runbook</h2>
      <pre className="font-mono text-xs bg-muted p-4 rounded leading-snug whitespace-pre-wrap">
{`1. az keyvault secret set \\
     --vault-name jobrag-prod-kv \\
     --name seeded-user-entra-oid \\
     --value <paste here>

2. az containerapp revision restart \\
     --name jobrag-api-prod \\
     --resource-group jobrag-prod-rg

3. Reload this page and sign in again.`}
      </pre>
    </Card>
  )
}
```

### `frontend/src/components/ThemeToggle.tsx` (D-20)

```tsx
// [CITED: UI-SPEC §15 aria-label dynamic + CONTEXT.md D-20]
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Sun, Moon } from "lucide-react"

type Theme = "light" | "dark"

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("theme") as Theme | null
  if (stored === "light" || stored === "dark") return stored
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark")
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    applyTheme(theme)
    localStorage.setItem("theme", theme)
  }, [theme])

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label={`Toggle theme (currently ${theme})`}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  )
}
```

### `frontend/src/components/AppShell.tsx` (UI-SPEC §7)

```tsx
import { Link, NavLink, Outlet } from "react-router"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu"
import { Toaster } from "@/components/ui/sonner"
import { User } from "lucide-react"
import { msalInstance } from "@/auth/msal"
import { ThemeToggle } from "./ThemeToggle"

function navClass({ isActive }: { isActive: boolean }) {
  return [
    "text-sm py-2 border-b-2 transition-colors",
    isActive
      ? "border-primary text-foreground"
      : "border-transparent text-muted-foreground hover:border-muted-foreground/50",
  ].join(" ")
}

export function AppShell() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-12 border-b flex items-center px-6 justify-between">
        <nav aria-label="Primary" className="flex items-center gap-6">
          <Link to="/dashboard" className="text-sm font-semibold">job-rag</Link>
          <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>
          <NavLink to="/chat" className={navClass}>Chat</NavLink>
          <NavLink to="/profile" className={navClass}>Profile</NavLink>
        </nav>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Open account menu">
                <User className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                variant="destructive"
                onClick={() => msalInstance.logoutRedirect({ postLogoutRedirectUri: window.location.origin + "/" })}
              >
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <Toaster position="bottom-right" richColors />
    </div>
  )
}
```

### `frontend/src/components/ErrorBoundary.tsx` (D-19a / UI-SPEC §9)

```tsx
import type { FallbackProps } from "react-error-boundary"
import { useNavigate } from "react-router"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export function GlobalErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const navigate = useNavigate()
  return (
    <Card
      role="alert"
      className="max-w-2xl mx-auto mt-12 p-8"
    >
      <h1 className="text-lg font-semibold mb-2">Something went wrong</h1>
      <p className="text-sm text-muted-foreground mb-6">
        The app hit an unexpected error. You can try going back to the dashboard,
        or reload the page.
      </p>
      <div className="flex gap-2 mb-6">
        <Button onClick={() => { resetErrorBoundary(); navigate("/dashboard") }}>
          Back to dashboard
        </Button>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Reload page
        </Button>
      </div>
      <details>
        <summary className="text-xs text-muted-foreground cursor-pointer">
          Technical details
        </summary>
        <pre className="font-mono text-xs bg-muted p-4 rounded mt-2 whitespace-pre-wrap break-all">
          {(error?.message ?? "").slice(0, 1000)}
          {error?.stack ? "\n\n" + error.stack.slice(0, 1000) : ""}
        </pre>
      </details>
    </Card>
  )
}
```

### `frontend/src/components/EmptyState.tsx` + `PhasePlaceholder.tsx` (D-19d / UI-SPEC §10)

```tsx
// EmptyState.tsx
import type { LucideIcon } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export type EmptyStateProps = {
  icon: LucideIcon
  heading: string
  body: string
  cta?: { label: string; onClick: () => void }
}

export function EmptyState({ icon: Icon, heading, body, cta }: EmptyStateProps) {
  return (
    <Card className="max-w-md mx-auto mt-24 p-8 text-center">
      <Icon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <h1 className="text-2xl font-semibold mb-2">{heading}</h1>
      <p className="text-sm text-muted-foreground">{body}</p>
      {cta && (
        <div className="mt-4">
          <Button onClick={cta.onClick}>{cta.label}</Button>
        </div>
      )}
    </Card>
  )
}

// PhasePlaceholder.tsx
import { BarChart3, MessageSquare, User as UserIcon } from "lucide-react"
import { EmptyState } from "./EmptyState"

const PHASE_CONFIG = {
  5: { feature: "Dashboard", icon: BarChart3, body: "The dashboard widgets land in Phase 5. Check the roadmap for progress." },
  6: { feature: "Chat", icon: MessageSquare, body: "The streaming chat surface lands in Phase 6. Check the roadmap for progress." },
  7: { feature: "Profile", icon: UserIcon, body: "Resume upload and profile editing land in Phase 7. Check the roadmap for progress." },
} as const

export function PhasePlaceholder({ phase, feature }: { phase: keyof typeof PHASE_CONFIG; feature: string }) {
  const config = PHASE_CONFIG[phase]
  return <EmptyState icon={config.icon} heading={`${feature} coming soon`} body={config.body} />
}
```

### `frontend/src/components/RouteSkeleton.tsx` (D-19b / UI-SPEC §11)

```tsx
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function RouteSkeleton() {
  return (
    <Card
      role="status"
      aria-label="Loading"
      className="max-w-md mx-auto mt-24 p-8 space-y-3"
    >
      <Skeleton className="h-6 w-1/3 motion-reduce:animate-none" />
      <Skeleton className="h-4 w-full motion-reduce:animate-none" />
      <Skeleton className="h-4 w-2/3 motion-reduce:animate-none" />
      <Skeleton className="h-9 w-32 motion-reduce:animate-none" />
    </Card>
  )
}
```

### `frontend/src/routes/DebugAgentStream.tsx` (D-16 / UI-SPEC §12)

```tsx
import { useRef, useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { authedFetch } from "@/api/authedFetch"
import { readSSEStream } from "@/api/readSSEStream"

export default function DebugAgentStreamPage() {
  const [query, setQuery] = useState("")
  const [log, setLog] = useState<string[]>([])
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  async function send() {
    if (streaming) return
    abortRef.current?.abort()
    abortRef.current = new AbortController()
    setLog([`… connecting (query: ${query})`])
    setStreaming(true)
    try {
      const response = await authedFetch(
        `${import.meta.env.VITE_API_BASE_URL}/agent/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query }),
          signal: abortRef.current.signal,
        },
      )
      for await (const event of readSSEStream(response)) {
        setLog((prev) => [...prev, `event: ${event.type}  data: ${JSON.stringify(event)}`])
      }
      setLog((prev) => [...prev, "--- end of stream ---"])
    } catch (err) {
      setLog((prev) => [...prev, `--- error: ${String(err)} ---`])
    } finally {
      setStreaming(false)
    }
  }

  return (
    <Card className="max-w-3xl mx-auto mt-12 p-8 space-y-4">
      <div className="flex items-center gap-2">
        <Badge variant="outline">DEV</Badge>
        <h1 className="text-lg font-semibold">Agent stream probe</h1>
      </div>
      <div className="flex gap-2">
        <Input
          placeholder="Ask the agent something…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={streaming}
        />
        <Button onClick={send} disabled={streaming || !query.trim()}>
          Send query
        </Button>
      </div>
      <pre className="max-h-96 overflow-y-auto bg-muted p-4 font-mono text-xs leading-snug break-all">
        {log.length === 0 ? "(no events yet)" : log.join("\n")}
      </pre>
    </Card>
  )
}
```

### `src/job_rag/api/auth.py` rewrite (D-07 + D-08)

```python
# [VERIFIED: Intility/fastapi-azure-auth/blob/main/fastapi_azure_auth/auth.py constructor]
# [CITED: CONTEXT.md D-07/D-08 + Phase 1 D-10 function-body rewrite pattern]
"""API authentication and rate limiting.

Phase 4 rewrites get_current_user_id() body to validate Entra JWT + guard against
non-allowlisted oid. Module-level azure_scheme instance handles JWT validation
(signature, iss, aud, exp, JWKS) once per request.

CIAM/External ID note: SingleTenantAzureAuthorizationCodeBearer does NOT support
overriding the openid_config_url; its discovery endpoint is hard-coded to
login.microsoftonline.com (workforce). For Entra External ID (ciamlogin.com)
the correct class is B2CMultiTenantAuthorizationCodeBearer, which accepts
openid_config_url precisely for this case. See RESEARCH.md Open Question Q1
for the technical correction context.
"""
import hmac
import time
import uuid
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi_azure_auth import B2CMultiTenantAuthorizationCodeBearer
from fastapi_azure_auth.user import User

from job_rag.config import settings
from job_rag.logging import get_logger

log = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

# Module-level azure_scheme instance — instantiated ONCE at import time.
# fastapi-azure-auth caches JWKS in-process (LRU) so per-request validation
# is just a signature check, not a network round-trip.
azure_scheme = B2CMultiTenantAuthorizationCodeBearer(
    app_client_id=settings.backend_audience.removeprefix("api://"),
    openid_config_url=(
        f"https://{settings.entra_tenant_subdomain}.ciamlogin.com/"
        f"{settings.entra_tenant_id}/v2.0/.well-known/openid-configuration"
    ),
    scopes={
        f"{settings.backend_audience}/access_as_user": "access_as_user",
    },
    validate_iss=True,
)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """Validate Bearer token against the configured API key.

    Legacy dev-only auth — Phase 4 protected routes use get_current_user_id
    instead. Kept for /health-style unauthenticated dev endpoints.

    Auth is skipped when ``settings.api_key`` is empty (local development).
    """
    if not settings.api_key:
        return
    if not credentials or not hmac.compare_digest(credentials.credentials, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class RateLimiter:
    # ... unchanged from Phase 1 ...
    def __init__(self, calls: int, period: int) -> None:
        self.calls = calls
        self.period = period
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = [t for t in self._requests[client_ip] if now - t < self.period]
        if len(window) >= self.calls:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        window.append(now)
        self._requests[client_ip] = window
        stale = [ip for ip, ts in self._requests.items() if ip != client_ip and ts and now - ts[-1] >= self.period]
        for ip in stale:
            del self._requests[ip]


standard_limit = RateLimiter(calls=30, period=60)
agent_limit = RateLimiter(calls=10, period=60)
ingest_limit = RateLimiter(calls=5, period=60)


async def get_current_user_id(
    user: User = Depends(azure_scheme),
) -> uuid.UUID:
    """Resolve the current user's UUID (Phase 4 / AUTH-06 rewrite).

    Phase 1 D-10 function-body rewrite: every consumer was already wired via
    Depends(get_current_user_id) on /match /gaps /ingest /agent /agent/stream.
    Phase 4 swaps the body in place — no call-site changes.

    AUTH-06 single-user guard (D-08): reject any oid != settings.seeded_user_entra_oid.
    Rejected oid is logged via structlog (LAW audit) but NOT returned in the response
    body (would leak who-has-signed-up if multi-user is enabled later).

    The seeded_user_entra_oid env var starts EMPTY in bootstrap-pending state
    (before D-09 first-login OID capture). Treat empty as "deny all" — no token
    can match an empty string.
    """
    oid = user.claims.get("oid") if isinstance(user.claims, dict) else None
    if not settings.seeded_user_entra_oid or oid != settings.seeded_user_entra_oid:
        log.warning(
            "user_not_allowlisted",
            rejected_oid=oid,
            seeded_configured=bool(settings.seeded_user_entra_oid),
        )
        raise HTTPException(status_code=403, detail="user_not_allowlisted")
    return settings.seeded_user_id
```

### `src/job_rag/config.py` deltas (D-04)

```python
# Add to existing Settings class:

# Entra External ID tenant identifiers (D-04 — plain env vars, public-by-design
# per Phase 3 D-13).
entra_tenant_id: str = ""
entra_tenant_subdomain: str = ""

# Backend audience for fastapi-azure-auth (D-04). Format: api://{api_client_id}.
# Compared against the JWT aud claim by the library; rejected on mismatch.
backend_audience: str = ""

# Adrian's Entra oid for AUTH-06 single-user guard (D-04, D-08, D-09).
# Empty string = bootstrap-pending state — D-08 guard treats empty as "deny all";
# D-10 migration skips on empty.
seeded_user_entra_oid: str = ""
```

### `alembic/versions/0005_adopt_entra_oid.py` skeleton (D-10)

```python
"""adopt entra oid: add user_db.entra_oid + idempotent UPDATE of seeded row

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-XX

D-10 (Phase 4): Adds the entra_oid column to user_db and runs an idempotent
UPDATE bridging Phase 1's seeded_user_id to Adrian's real Entra oid (captured
out-of-band via D-09 AccessDenied UX → az keyvault secret set).

Runs blocking on container startup per Phase 1 D-04 (init_db() wraps
alembic upgrade head). On empty SEEDED_USER_ENTRA_OID env (bootstrap-pending
state), the UPDATE is a no-op — migration completes cleanly so container
starts; AUTH-06 guard then rejects every token until KV secret is filled.

[Pgvector caveat per Phase 1 plan 01-02 D-02: env.py already registers
pgvector.sqlalchemy.Vector on connection.dialect.ischema_names BEFORE
context.configure(). No change here.]
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Phase 1 D-08 invariant: the canonical seeded_user_id literal MUST match
# config.py settings.seeded_user_id and the row inserted by 0002_add_user_profile.py.
SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Upgrade schema to Phase 4 shape."""
    # 1. Add entra_oid column to user_db (nullable; first-login OID may not
    #    be known yet at migration time — D-09 bootstrap dance).
    op.add_column(
        "user_db",
        sa.Column("entra_oid", sa.String(255), nullable=True),
    )

    # 2. Idempotent UPDATE — bridge Phase 1's seeded UUID to Adrian's real oid
    #    when SEEDED_USER_ENTRA_OID is set. On empty env (bootstrap-pending),
    #    this is a no-op; migration still completes.
    oid = os.environ.get("SEEDED_USER_ENTRA_OID", "").strip()
    if oid:
        op.execute(
            sa.text(
                "UPDATE user_db SET entra_oid = :oid "
                "WHERE user_id = :seeded_uuid AND (entra_oid IS NULL OR entra_oid != :oid)"
            ).bindparams(oid=oid, seeded_uuid=SEEDED_USER_UUID)
        )

    # 3. Create unique index on entra_oid (when populated) — structural prep
    #    for future multi-user where oid is the authoritative lookup. Partial
    #    index excludes NULLs so existing rows without an oid don't violate.
    op.create_index(
        "ix_user_db_entra_oid_unique",
        "user_db",
        ["entra_oid"],
        unique=True,
        postgresql_where=sa.text("entra_oid IS NOT NULL"),
    )


def downgrade() -> None:
    """Reverse — drop index then column. Loses any captured oid value."""
    op.drop_index("ix_user_db_entra_oid_unique", table_name="user_db")
    op.drop_column("user_db", "entra_oid")
```

### `infra/external/main.tf` (D-02)

```hcl
# [CITED: PITFALLS.md §1/§2 + Phase 3 D-06/D-07 + CONTEXT.md D-02 + Phase 3 03-CONTEXT.md §A4]
# Local-state only; mirrors infra/bootstrap/main.tf. Run from Adrian's az login
# context against the External tenant (NOT the workforce tenant).

terraform {
  required_version = ">= 1.9"
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # NO backend block — intentionally local state per D-02.
}

# Sole provider: azuread targeted at the External tenant.
# CI cannot manage these resources (Gap D); only Adrian's local az-login.
provider "azuread" {
  tenant_id = var.tenant_id_external
}

# ─── API app registration ─────────────────────────────────────────────────────
#
# The API app reg is the "resource" the SPA acquires a token AGAINST. It
# exposes one delegated scope (access_as_user). Audience = api://<client_id>.

resource "azuread_application" "api" {
  display_name     = "jobrag-api"
  sign_in_audience = "AzureADMyOrg"  # External-tenant: single-tenant within the CIAM tenant

  api {
    requested_access_token_version = 2  # v2 tokens

    oauth2_permission_scope {
      id                         = random_uuid.access_as_user.result
      type                       = "User"  # delegated
      admin_consent_display_name = "Access job-rag API as the signed-in user"
      admin_consent_description  = "Allows the SPA to call the job-rag API on behalf of the signed-in user."
      user_consent_display_name  = "Access job-rag API"
      user_consent_description   = "Allows the app to call the job-rag API on your behalf."
      value                      = "access_as_user"
      enabled                    = true
    }
  }
}

resource "random_uuid" "access_as_user" {}

# Set the Application ID URI to api://<client_id> AFTER the application exists
# (chicken-and-egg: identifier_uris want the client_id, which only exists post-create).
# Use the separate identifier_uris attribute.
resource "azuread_application_identifier_uri" "api" {
  application_id = azuread_application.api.id
  identifier_uri = "api://${azuread_application.api.client_id}"
}

resource "azuread_service_principal" "api" {
  client_id = azuread_application.api.client_id
}

# ─── SPA app registration ─────────────────────────────────────────────────────

resource "azuread_application" "spa" {
  display_name     = "jobrag-spa"
  sign_in_audience = "AzureADMyOrg"

  single_page_application {
    redirect_uris = [
      "https://${var.swa_origin}/",
      "http://localhost:5173/",  # dev — Phase 3 D-06 multi-redirect-URI
    ]
  }

  # API permission: delegated access_as_user against the API app reg
  required_resource_access {
    resource_app_id = azuread_application.api.client_id  # the API app reg

    resource_access {
      id   = random_uuid.access_as_user.result  # the scope id
      type = "Scope"  # delegated
    }
  }
}

resource "azuread_service_principal" "spa" {
  client_id = azuread_application.spa.client_id
}

# ─── Admin consent for SPA's delegated permission on API ───────────────────────
#
# Grants the SPA the access_as_user scope WITHOUT requiring per-user consent on
# first login. Phase 3 D-07 already documents this pattern. Resource shape uses
# azuread_service_principal_delegated_permission_grant.

resource "azuread_service_principal_delegated_permission_grant" "spa_to_api" {
  service_principal_object_id          = azuread_service_principal.spa.object_id
  resource_service_principal_object_id = azuread_service_principal.api.object_id
  claim_values                         = ["access_as_user"]
}
```

### `infra/external/outputs.tf`

```hcl
output "spa_client_id" {
  description = "SPA app reg client ID — bake into frontend/.env.production as VITE_SPA_CLIENT_ID."
  value       = azuread_application.spa.client_id
}

output "api_client_id" {
  description = "API app reg client ID — passed to backend as part of BACKEND_AUDIENCE."
  value       = azuread_application.api.client_id
}

output "api_audience_uri" {
  description = "api://<api_client_id> — backend BACKEND_AUDIENCE env var AND frontend VITE_API_AUDIENCE."
  value       = "api://${azuread_application.api.client_id}"
}

output "api_scope_name" {
  description = "Fully-qualified scope name — bake into frontend authedFetch as API_SCOPE = '<api_scope_name>'."
  value       = "api://${azuread_application.api.client_id}/access_as_user"
}
```

### `infra/external/variables.tf`

```hcl
variable "tenant_id_external" {
  type        = string
  description = "External tenant GUID — captured from infra/bootstrap output (same value as infra/envs/prod/variables.tf var.tenant_id_external)."
}

variable "tenant_subdomain" {
  type        = string
  description = "External tenant subdomain (e.g. 'jobrag' for jobrag.ciamlogin.com). Used as MSAL authority host."
  default     = "jobrag"
}

variable "swa_origin" {
  type        = string
  description = "SWA default origin (host only, no scheme). E.g. 'jobrag-prod-spa.azurestaticapps.net'. Sourced from infra/envs/prod/ output swa_default_origin."
}
```

### `infra/external/README.md` skeleton

```markdown
# Infra External Tenant (local-only)

> Adrian-local Terraform managing SPA + API app registrations + admin consent in the Entra External (CIAM) tenant. **Never run from CI.** Gap D blocker: workforce GHA SP cannot auth into the External tenant.

## Prerequisites

- Adrian's `az login` context includes the External tenant (`az login --allow-no-subscriptions --tenant <subdomain>.onmicrosoft.com`)
- The External tenant exists (Phase 3 D-05 portal click-path; tenant_id captured in infra/bootstrap/)
- `infra/envs/prod/` has been applied at least once and `swa_default_origin` is available

## Step 1 — Prepare tfvars

```bash
cd infra/external

cat > terraform.tfvars.local <<EOF
tenant_id_external = "<paste from infra/bootstrap output>"
tenant_subdomain   = "jobrag"
swa_origin         = "<paste swa_default_origin from infra/envs/prod output>"
EOF
```

## Step 2 — Apply

```bash
terraform init -backend=false  # local state per D-02
terraform apply -var-file=terraform.tfvars.local
```

## Step 3 — Wire outputs into downstream consumers

```bash
# Capture outputs
SPA_CLIENT_ID=$(terraform output -raw spa_client_id)
API_CLIENT_ID=$(terraform output -raw api_client_id)
API_AUDIENCE=$(terraform output -raw api_audience_uri)

# Frontend .env.production (committed — public-by-design per D-03)
# Update VITE_SPA_CLIENT_ID, VITE_API_AUDIENCE in frontend/.env.production

# Backend prod tfvars.local (gitignored)
# Update api_audience, entra_tenant_subdomain in infra/envs/prod/prod.tfvars.local
# Then re-apply infra/envs/prod/ to push the new env vars to ACA

# Refresh script (optional helper)
bash ../../scripts/refresh-external-outputs.sh
```

## Knowingly-accepted security trade-offs

- **Local state.** terraform.tfstate lives on Adrian's machine, gitignored. Blast radius if leaked: client IDs only (public by design). No secrets.
- **No CI path.** Re-applying these app regs requires Adrian's local apply. For a multi-user product this would be unacceptable; for single-user portfolio v1 it's fine.

## When to re-apply

- SWA origin changes (new SWA tier or region) — `swa_origin` tfvar update + apply
- Adding a second redirect URI (e.g., staging URL) — edit `redirect_uris` list + apply
- Rotating the random_uuid for access_as_user scope — almost never; would invalidate every existing JWT
```

### `frontend/.env.production` (committed) + `frontend/.env.local` (gitignored)

```bash
# frontend/.env.production (COMMITTED — all values public-by-design per D-03)
VITE_TENANT_SUBDOMAIN=jobrag
VITE_TENANT_ID=<from infra/external/ output via infra/envs/prod outputs>
VITE_SPA_CLIENT_ID=<from infra/external/ output spa_client_id>
VITE_API_AUDIENCE=api://<api_client_id from infra/external/>
VITE_API_BASE_URL=https://<aca_fqdn from infra/envs/prod outputs>
# Optional:
# VITE_DEBUG_PAGES=true

# frontend/.env.local (GITIGNORED — dev overrides)
VITE_TENANT_SUBDOMAIN=jobrag
VITE_TENANT_ID=<same as prod>
VITE_SPA_CLIENT_ID=<same as prod — single External tenant per Phase 3 D-06>
VITE_API_AUDIENCE=<same as prod>
VITE_API_BASE_URL=http://localhost:8000
VITE_DEBUG_PAGES=true
```

### `.github/workflows/deploy-spa.yml` extension (D-03)

Add to the existing workflow (existing file in repo currently has the structure for Phase 3's hello-world build):

```yaml
      - name: Build
        run: npm run build
        working-directory: frontend  # was apps/web — update path
        env:
          VITE_TENANT_SUBDOMAIN: ${{ secrets.VITE_TENANT_SUBDOMAIN }}
          VITE_TENANT_ID: ${{ secrets.VITE_TENANT_ID }}
          VITE_SPA_CLIENT_ID: ${{ secrets.VITE_SPA_CLIENT_ID }}
          VITE_API_AUDIENCE: ${{ secrets.VITE_API_AUDIENCE }}
          VITE_API_BASE_URL: ${{ secrets.VITE_API_BASE_URL }}
```

(Plus path corrections — current workflow references `apps/web/` per the Phase 3 STACK.md scaffold; Phase 4 D-01 standardizes on `frontend/`.) **GitHub repo secrets to add:** `VITE_TENANT_SUBDOMAIN`, `VITE_TENANT_ID`, `VITE_SPA_CLIENT_ID`, `VITE_API_AUDIENCE`, `VITE_API_BASE_URL`. Sync via `gh secret set` after `infra/external/` apply.

### `.github/workflows/ci.yml` — add `frontend-ci` job

Add ALONGSIDE the existing `lint-and-test` job (Python). Runs in parallel.

```yaml
  frontend-ci:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg17
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend dependencies
        run: npm ci
        working-directory: frontend

      - name: Typecheck
        run: npm run typecheck
        working-directory: frontend

      - name: Lint
        run: npm run lint
        working-directory: frontend

      - name: Vitest
        run: npm run test -- --run
        working-directory: frontend

      # Codegen drift guard — backend must be reachable.
      # Spin up a minimal Python env to bring up FastAPI just long enough to
      # serve /openapi.json, then re-run codegen and assert no drift.
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true

      - name: Setup Python
        run: uv python install 3.12

      - name: Install backend deps
        run: uv sync --frozen

      - name: Start FastAPI (background)
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
          ASYNC_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test
        run: |
          uv run alembic upgrade head
          uv run uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000 &
          # wait for /openapi.json
          for i in $(seq 1 20); do
            curl -sf http://localhost:8000/openapi.json > /dev/null && break
            sleep 1
          done

      - name: Codegen + drift check
        working-directory: frontend
        run: |
          npm run codegen
          git diff --exit-code src/api/types.ts || {
            echo "::error::Frontend types drifted from backend OpenAPI — run 'npm run codegen' locally and commit src/api/types.ts"
            exit 1
          }
```

### `frontend/package.json` script section (codegen + testing)

```jsonc
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "format": "prettier --write .",
    "typecheck": "tsc --noEmit",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "codegen": "openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts"
  }
}
```

### `frontend/src/test/setup.ts`

```ts
import "@testing-library/jest-dom"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

afterEach(() => {
  cleanup()
})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Azure AD B2C for CIAM | Entra External ID (CIAM tenant) | B2C End-of-Sale 2025-05-01 | All new CIAM work goes to External ID. Already locked in Phase 3 D-05. |
| MSAL React 4.x | MSAL React 5.x | React 18+ support requires v5 | Library API mostly stable; v5 added native React 19 support. |
| Implicit / hybrid OAuth flow | Auth Code + PKCE | Deprecated by OAuth 2.1 + MSAL since v2 | Already locked; MSAL default. |
| Vite 6 (PostCSS-based Tailwind) | Vite 8 + `@tailwindcss/vite` plugin | Tailwind v4 release | Faster builds, simpler config, but Node 20.19+ required. |
| `apps/web/` monorepo convention | `frontend/` flat sibling dir | Phase 4 D-01 supersedes Phase 3 STACK.md mention | Update needed in Phase 3 03-CONTEXT.md `<code_context>` line 187 (per CONTEXT.md `<specifics>`). |
| `text-base` (16px) body | `text-sm` (14px) body | Linear-dense aesthetic decision | UI-SPEC §3 — 4 sizes, 2 weights cap. |
| `EventSource` for SSE | `fetch + ReadableStream + TextDecoder` (this `readSSEStream`) | Bearer header support needed (EventSource can't attach Bearer) | CHAT-01 / D-16. Phase 6 chat consumes via this helper. |
| `axios` interceptor | Native fetch + MSAL silent token | Same DX with smaller bundle (~14kb gzip saved) | D-13 locks native fetch. |

**Deprecated/outdated (do not use):**
- Azure AD B2C P1 SKU (P2 retiring 2026-03-15; P1 hard-deprecation 2030; new builds go to External ID)
- MSAL.js v1 / the `msal` package (pre-v2 — deprecated)
- `npx shadcn-ui@latest` (renamed to `shadcn@latest` in CLI v4)
- Tailwind v3 with PostCSS config (v4 is the line)
- `EventSource` for authenticated SSE (cannot attach Bearer headers)
- `apps/web/` (Phase 3 STACK.md mention; superseded by `frontend/`)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `B2CMultiTenantAuthorizationCodeBearer` validates Entra External ID JWTs correctly when given the ciamlogin discovery URL (i.e., the "B2C" in the name is purely historical; CIAM tokens look enough like B2C tokens that the library's validation logic works) | Open Q1 + Code Examples | Backend rejects every JWT; planner must add a triangulation test on Wave 0 (mint a token via MSAL → POST to a test endpoint → assert 200, not 401) before relying on the choice. Fallback: use the lower-level `azuread_application` claims + PyJWT + jwks_client manual stack. |
| A2 | `azuread_service_principal_delegated_permission_grant` is the right azuread v3 resource for admin-consenting the SPA's `access_as_user` permission against the API app reg | Code Examples §infra/external/ | Without admin consent, every first-login shows a user-consent prompt — fine for Adrian but ugly. Plan should manually-verify post-apply in portal blade Enterprise Applications → Permissions; if missing, fall back to `az ad app permission admin-consent --id <spa-app-id>` runbook in `infra/external/README.md`. |
| A3 | The dev-only `/debug/agent-stream` route can be gated via `import.meta.env.VITE_DEBUG_PAGES === 'true'` so it ships into prod builds when the env is set | UI-SPEC §12, Pattern 1 | If the gate misfires, the debug page leaks into prod for the entire org's worth of users to see. Mitigation: it's behind AuthGate, so still requires Adrian's oid to reach it. UI-SPEC §12 already commits to this; verified safe. |
| A4 | `random_uuid` from the `random` Terraform provider produces a stable scope ID that survives apply/destroy/re-apply cycles via state | Code Examples §infra/external/ | If the UUID drifts on re-apply (random_uuid lifecycle = keep), every issued JWT becomes invalid. The provider's `random_uuid` resource explicitly persists in state — verified pattern. Risk LOW. |
| A5 | `azuread_application_identifier_uri` is the right v3 resource shape for setting `api://<client_id>` on an app reg (vs the deprecated inline `identifier_uris` attribute) | Code Examples §infra/external/ | If wrong shape, apply fails with helpful error. LOW risk — apply-time discovery. |
| A6 | The MSAL `account.idTokenClaims.oid` field is reliably populated for Entra External ID tokens (vs being only on v1 workforce tokens) | Code Examples §AccessDenied.tsx | If `oid` is on `idTokenClaims.sub` for CIAM v2.0 tokens, the AccessDenied page shows an empty/null oid. Mitigation: fall back to `account.idTokenClaims.sub` if `oid` is undefined. Add to plan checklist. |
| A7 | `user.claims` on fastapi-azure-auth's `User` model is a `dict[str, Any]` keyed by claim name | Code Examples §auth.py | If actually a typed Pydantic model, `user.claims['oid']` doesn't work; need `user.oid` directly. Cross-check: VERIFIED from upstream source 2026-05-19 — both fields exist: `User.oid` (typed) AND `User.claims` (full dict). Using `user.claims.get('oid')` is safe but `user.oid` would be more typed. Either works; pattern shown uses claims-dict for explicitness. |

---

## Open Questions

### Q1: `SingleTenantAzureAuthorizationCodeBearer` vs `B2CMultiTenantAuthorizationCodeBearer` for Entra External ID — CONTEXT.md D-07 names the wrong class

- **What we know:** CONTEXT.md D-07 specifies `SingleTenantAzureAuthorizationCodeBearer`. fastapi-azure-auth's `SingleTenantAzureAuthorizationCodeBearer` constructor does NOT accept `openid_config_url`. Its discovery endpoint is hard-coded to `login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration` (the workforce endpoint). Entra External ID tokens are issued by `{subdomain}.ciamlogin.com/{tenant_id}/v2.0` — a DIFFERENT discovery endpoint. Workforce JWKS will not verify CIAM tokens. [VERIFIED: upstream source code fetched 2026-05-19; PYPI version 5.2.0.]
- **What's unclear:** Whether CONTEXT.md's naming was a research-time imprecision (researcher meant "the SingleTenant pattern" generically) or an explicit class-name commitment.
- **Recommendation:** Treat this as a TECHNICAL CORRECTION that the planner MUST act on, not a question requiring a new discussion round. Use `B2CMultiTenantAuthorizationCodeBearer` with the `openid_config_url` parameter set to the ciamlogin discovery URL. The "B2C" in the class name is historical — CIAM (External ID) replaced B2C and the discovery URL shape is what the library cares about, not the marketing-tier name. Add a Wave 0 smoke test (mint MSAL token → POST → assert 200) to triangulate before relying on this. Update CONTEXT.md D-07 in the planner's first commit (one-line correction: "`B2CMultiTenantAuthorizationCodeBearer`" not "`SingleTenantAzureAuthorizationCodeBearer`").

### Q2: First-paint flash mitigation — single inline `<script>` in `<head>` for theme

- **What we know:** D-05 race fix means React doesn't render until MSAL initializes (~50-150ms). Background color is whatever the default browser is, OR what `<body>` CSS sets, OR what an inline `<head>` script applies. Without an inline theme-apply script, dark-mode users see a flash of white.
- **What's unclear:** Whether the inline `<script>` workaround is acceptable for an otherwise-no-inline-script codebase (CSP-friendly stance).
- **Recommendation:** ACCEPT the inline script per Pitfall §First-paint flash mitigations. CSP can use `'unsafe-inline'` for the SPA index OR a hash-based exemption. The alternative — accepting the flash — is worse UX for the most common first-paint case (dark mode). UI-SPEC §16 explicitly accepts blank-window for 50-150ms; this just makes the blank window match the theme.

### Q3: Phase 3 03-CONTEXT.md `apps/web/` reference correction — one-line edit?

- **What we know:** CONTEXT.md `<specifics>` notes "The `apps/web/` stray reference in Phase 3 03-CONTEXT.md `<code_context>` line 187 is superseded by Phase 4 D-01's `frontend/`. Update Phase 3 CONTEXT.md as a documentation correction in Phase 4's first commit if the planner deems it worth a one-line touch."
- **What's unclear:** Is editing a prior-phase CONTEXT.md acceptable? Phase 3 is already verified — would the planner trigger re-verification?
- **Recommendation:** YES, one-line touch. Phase 3 is COMPLETE (verified per STATE.md). Updating a doc-only reference doesn't invalidate verification. Include in Phase 4 Plan 01 (Wave 0 scaffolding) commit message: `docs: correct apps/web reference to frontend (Phase 4 D-01)`.

### Q4: Vitest minimum test set — what's the MVP?

- **What we know:** CONTEXT.md and UI-SPEC don't specify a Wave-0 test count or coverage threshold; just "Vitest setup file + jest-dom matchers."
- **What's unclear:** The minimum-viable Vitest set Phase 4 ships.
- **Recommendation:** Ship 5 tests as Phase 4 Wave 0 + 1 baseline:
  1. `AuthGate.test.tsx` — renders RouteSkeleton when unauthenticated, renders Outlet when authenticated
  2. `authedFetch.test.ts` — attaches `Authorization: Bearer <jwt>` header; on 401 retries once with refreshed token
  3. `readSSEStream.test.ts` — yields three sample frames from a fixed-input ReadableStream; handles partial \n\n
  4. `ThemeToggle.test.tsx` — clicking toggles dark class on documentElement; persists to localStorage
  5. `AppShell.test.tsx` — renders nav links for Dashboard / Chat / Profile
  Plus a smoke that the build succeeds with `tsc --noEmit` (CI typecheck step). Phase 5/6/7 add per-feature tests in their own waves.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node | Vite 8, frontend tooling | ✓ | v25.9.0 (exceeds 20.19+/22.12+ Vite 8 min) | — |
| npm | Frontend dep install | ✓ | 11.12.1 | — |
| Python 3.12 | Backend, alembic | ✓ | (existing) | — |
| uv | Backend dep mgmt | ✓ | (existing per Phase 1) | — |
| Docker | docker-compose for local Postgres | ✓ | (existing per Phase 1) | — |
| Terraform 1.9+ | infra/external/ apply | ✓ | (existing per Phase 3) | — |
| `az` CLI with External-tenant login | infra/external/ apply | ✓ (Adrian) | (existing per Phase 3 D-05 bootstrap) | — |
| `gh` CLI for `gh secret set` | Wiring VITE_* GH Actions secrets | ✓ | (assumed; Phase 3 used) | Manual portal click-path |
| PostgreSQL 17 + pgvector | Local Alembic 0005 migration smoke test | ✓ | pgvector/pgvector:pg17 via docker-compose (existing) | — |
| `clipboard-write` permission | AccessDenied copy-button | ✓ | Modern browser API; falls back to "select-and-copy-manually" toast on insecure context | Toast error message + manual select |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Frontend framework | Vitest 3.x + @testing-library/react + jsdom |
| Frontend config file | `frontend/vite.config.ts` (test: block) |
| Frontend quick run | `cd frontend && npm run test -- --run` |
| Frontend full suite | `cd frontend && npm run typecheck && npm run lint && npm run test -- --run && npm run codegen && git diff --exit-code src/api/types.ts` |
| Backend framework | pytest 9.x + pytest-asyncio + httpx + asgi-lifespan (existing per Phase 1) |
| Backend config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Backend quick run | `uv run pytest tests/test_auth.py tests/test_alembic.py -x` |
| Backend full suite | `uv run ruff check src/ tests/ && uv run pyright src/ && uv run pytest -m 'not eval'` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SHEL-01 | Vite + React + TS scaffolds, builds | smoke | `cd frontend && npm run build` | ❌ Wave 0 |
| SHEL-02 | shadcn theme applies; Geist Sans loads; tailwind builds | smoke | `cd frontend && npm run build` + manual visual check | ❌ Wave 0 |
| SHEL-03 | TanStack QueryClient mounts; useQuery composes | unit | `cd frontend && npm run test -- queryClient` (light unit) | ❌ Wave 0 |
| SHEL-04 | AppShell renders nav links Dashboard/Chat/Profile | unit | `vitest run tests/AppShell.test.tsx` | ❌ Wave 0 |
| SHEL-05 | authedFetch attaches Bearer; 401 triggers retry-after-silent-refresh | unit | `vitest run tests/authedFetch.test.ts` | ❌ Wave 0 |
| SHEL-06 | RouteSkeleton renders during Suspense; ErrorBoundary catches throw; EmptyState typed contract enforced | unit + smoke | `vitest run tests/RouteSkeleton.test.tsx tests/ErrorBoundary.test.tsx tests/EmptyState.test.tsx` + visual check on `/dashboard` | ❌ Wave 0 |
| AUTH-01 | Tenant exists, MSAL authority reaches it | smoke (manual) | `curl https://${subdomain}.ciamlogin.com/${tenant_id}/v2.0/.well-known/openid-configuration` returns JSON | — (Phase 3 D-05 already verified) |
| AUTH-02 | SPA app reg has SPA platform, PKCE green check | smoke (manual portal) | Adrian visual-verify after `terraform apply` in `infra/external/` | ❌ Wave 0 |
| AUTH-03 | API app reg exposes `access_as_user` scope | smoke (manual portal) | Adrian visual-verify | ❌ Wave 0 |
| AUTH-04 | Unauthenticated visit → loginRedirect | manual e2e | Open SWA URL in private browser; expect redirect to `*.ciamlogin.com` | manual-only |
| AUTH-05 | Backend rejects missing/invalid/wrong-audience JWT | unit + integration | `uv run pytest tests/test_auth.py::TestEntraJwtValidation` (unit with mocked azure_scheme); integration via curl + valid token mint | ❌ Wave 0 |
| AUTH-06 | Wrong-oid JWT → 403 user_not_allowlisted | unit | `uv run pytest tests/test_auth.py::TestOidGuard` | ❌ Wave 0 |
| AUTH-07 | Hard refresh while logged-in → no login flash | manual e2e | DevTools throttle → Slow 3G → cmd+R on /dashboard → assert no `*.ciamlogin.com/oauth2/...` URL appears in navigation history | manual-only |

### Sampling Rate

- **Per task commit:** quick run (`pytest -x` on changed files OR `vitest run` on changed files)
- **Per wave merge:** full suite (typecheck + lint + vitest + pytest + drift-check)
- **Phase gate:** Full frontend + backend suite green; manual e2e checks (AUTH-04, AUTH-07) sign-off before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `frontend/` directory itself (scaffolded by D-01)
- [ ] `frontend/package.json` + `frontend/package-lock.json` (npm init via Vite template)
- [ ] `frontend/vite.config.ts` with Vitest config
- [ ] `frontend/src/test/setup.ts`
- [ ] `tests/AuthGate.test.tsx`, `tests/authedFetch.test.ts`, `tests/readSSEStream.test.ts`, `tests/ThemeToggle.test.tsx`, `tests/AppShell.test.tsx`
- [ ] `tests/test_entra_jwt.py` (backend) — TestEntraJwtValidation, TestOidGuard, integration with mocked azure_scheme via dependency_overrides
- [ ] `pyproject.toml` += `fastapi-azure-auth>=5.2,<6.0`
- [ ] `src/job_rag/config.py` += 4 new fields (`entra_tenant_id`, `entra_tenant_subdomain`, `backend_audience`, `seeded_user_entra_oid`)
- [ ] `alembic/versions/0005_adopt_entra_oid.py`
- [ ] `infra/external/` directory + 5 .tf files + README
- [ ] `frontend/.env.local` template (gitignored — Adrian fills) + `frontend/.env.production` (committed placeholders)
- [ ] `.github/workflows/ci.yml` — add `frontend-ci` job
- [ ] `.github/workflows/deploy-spa.yml` — add VITE_* env block + change `apps/web/` → `frontend/`
- [ ] GitHub repo secrets: VITE_TENANT_SUBDOMAIN, VITE_TENANT_ID, VITE_SPA_CLIENT_ID, VITE_API_AUDIENCE, VITE_API_BASE_URL
- [ ] `scripts/refresh-external-outputs.sh` (mirrors `scripts/refresh-swa-origin.sh` shape)
- [ ] `frontend/openapi.snapshot.json` (initial snapshot of current `/openapi.json`) — drift-guard reference

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | MSAL React 5.4 (PKCE auth code flow); fastapi-azure-auth 5.2 (JWT validation: signature/iss/aud/exp + JWKS LRU) |
| V3 Session Management | yes | sessionStorage MSAL cache (D-06 — tab-scoped, lower XSS blast radius); JWT lifetime per Entra default (1h access token, refresh in MSAL); no server-side session state |
| V4 Access Control | yes | App-layer AUTH-06 guard in `get_current_user_id()` — single-user oid allowlist; structural multi-user prep (`user_id` per row + per-query filter already in place from Phase 1) |
| V5 Input Validation | yes | Pydantic models on every request body (existing); openapi-typescript codegen propagates the same shape to frontend |
| V6 Cryptography | yes | fastapi-azure-auth + PyJWT[crypto] handle RS256 signature validation — never hand-rolled; HTTPS-only via SWA + ACA (Phase 3) |
| V7 Error Handling | yes | Generic 403 detail (no leaked oid in response body); structured `log.warning("user_not_allowlisted", rejected_oid=...)` for LAW audit (D-09) |
| V8 Data Protection | yes | `entra_oid` column nullable but unique (partial index); seeded oid lives in KV (Phase 3 D-09 placeholder filled by Phase 4 D-09 OOB capture); VITE_* env vars public-by-design (no secrets shipped to client) |
| V9 Communications | yes | HTTPS-only on SWA + ACA (Phase 3); MSAL authority enforces HTTPS to ciamlogin.com; CORS allowlist exact-origin (Phase 1 D-26) |
| V11 Business Logic | yes | One-allowed-oid policy enforced at one place (function body); structural prep for per-user filters already in Phase 1 |
| V13 API + Web Service | yes | OpenAPI doc is the contract; openapi-typescript codegen + CI drift-guard prevents schema drift |

### Known Threat Patterns for {Vite SPA + FastAPI + Entra External ID + ACA}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stolen JWT replay | Spoofing | 1h JWT lifetime + signature/iss/aud/exp validation; refresh token in sessionStorage (tab-scoped); HTTPS-only (no plaintext interception); CORS allowlist (no cross-origin token reuse from rogue sites) |
| XSS exfiltrates token from sessionStorage | Tampering / Info Disclosure | sessionStorage (smaller blast radius than localStorage); Content-Security-Policy (TODO in deploy phase — not Phase 4 explicit, but defensive); only first-party scripts loaded; `npm audit` in CI catches known-vuln deps |
| Backend bypassed via direct API call from another origin | Spoofing | Exact-origin CORS allowlist (Phase 1 D-26); JWT required on every protected route (no anon endpoints except `/health`) |
| Wrong-tenant JWT accepted | Spoofing | `validate_iss=True` on `B2CMultiTenantAuthorizationCodeBearer`; iss compared against the discovered openid_cfg's issuer; CIAM iss differs from workforce (Pitfall 1 + PITFALLS.md §1) |
| User-not-allowlisted reaches business logic | Elevation of Privilege | AUTH-06 guard in `get_current_user_id()` is the single trust boundary; every protected route Depends on it; 403 before any handler runs |
| Multi-user reveals existing oid via 403 message | Info Disclosure | Generic 403 detail (`user_not_allowlisted` literal); rejected oid in structlog only (LAW audit), never in response body (D-09 explicit) |
| `seeded_user_entra_oid` set to attacker's oid by misconfig | Tampering (via supply chain) | KV-stored secret; reading it requires KV Secrets User RBAC on ACA managed identity; out-of-band `az keyvault secret set` requires Adrian's az login + KV Secrets Officer role |
| Build-time VITE_* secret leakage | Info Disclosure | NONE leaked — all five values are public-by-design (D-03). Documented expectation: tenant ID, subdomain, client ID, audience URI, API base URL are all visible in JWT claims that any holder can read. |
| MSAL flash-of-login (UX-as-attack-surface) | Spoofing (via phishing-flash) | D-05 race fix eliminates flash; user sees consistent UI; no opportunity for a fake login form to be mistaken for the real flow |
| Codegen drift hides API contract changes | Tampering | CI drift-guard runs `git diff --exit-code src/api/types.ts` after `npm run codegen`; any backend change requires paired frontend types update in same PR |
| Open `/debug/agent-stream` in prod | Info Disclosure | Behind AuthGate (Adrian-oid required); gated by `import.meta.env.DEV || VITE_DEBUG_PAGES === 'true'`; UI-SPEC §12 explicit gate |

---

## Sources

### Primary (HIGH confidence)

- [Vite Releases (8.0.13 verified npm 2026-05-19)](https://vite.dev/releases) — current stable, Node 20.19+/22.12+ required
- [Tailwind CSS — Using Vite](https://tailwindcss.com/docs/installation/using-vite) — v4 + `@tailwindcss/vite` plugin
- [shadcn/ui — Vite installation](https://ui.shadcn.com/docs/installation/vite) — `npx shadcn@latest init -t vite`
- [@azure/msal-react package + CHANGELOG](https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-react/CHANGELOG.md) — 5.4.2 verified via npm registry 2026-05-19
- [Tutorial: Prepare a React SPA for authentication (Entra External ID)](https://learn.microsoft.com/en-us/entra/external-id/customers/tutorial-single-page-app-react-sign-in-prepare-app) — MSAL config (clientId / authority `*.ciamlogin.com` / redirectUri pattern)
- [React SPA + MSAL + Entra External ID sample](https://learn.microsoft.com/en-us/samples/azure-samples/ms-identity-ciam-javascript-tutorial/ms-identity-ciam-javascript-tutorial-1-sign-in-react/) — config shape
- [fastapi-azure-auth source: auth.py constructor signatures](https://github.com/Intility/fastapi-azure-auth/blob/main/fastapi_azure_auth/auth.py) — verified `SingleTenantAzureAuthorizationCodeBearer` lacks `openid_config_url`; `B2CMultiTenantAuthorizationCodeBearer` has it
- [fastapi-azure-auth source: openid_config.py](https://github.com/Intility/fastapi-azure-auth/blob/main/fastapi_azure_auth/openid_config.py) — default URL builder & `config_url` override path
- [fastapi-azure-auth source: user.py — User Pydantic model](https://github.com/Intility/fastapi-azure-auth/blob/main/fastapi_azure_auth/user.py) — User has `claims: dict[str, Any]` + typed `oid`, `sub`, `tid`, etc.
- [fastapi-azure-auth on PyPI](https://pypi.org/project/fastapi-azure-auth/) — 5.2.0 verified 2026-05-19
- [openapi-typescript on npm + docs](https://openapi-ts.dev/introduction) — 7.13.0 verified npm 2026-05-19
- [MDN ReadableStream](https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream) — getReader() + async iter
- [WHATWG SSE spec](https://html.spec.whatwg.org/multipage/server-sent-events.html) — frame boundary `\n\n`, field parsing
- [MSAL React error handling](https://learn.microsoft.com/en-us/entra/identity-platform/msal-error-handling-js) — InteractionRequiredAuthError + acquireTokenRedirect pattern
- [MSAL React FAQ — handleRedirectPromise note](https://learn.microsoft.com/en-us/entra/msal/javascript/react/faq) — MSAL React handles it under the hood (caveat: D-05 explicit-call pre-render is the canonical race-free pattern)
- [PITFALLS.md §1 §2 §3 §5 §10 §11 §12 (already-verified HIGH confidence)](./../../research/PITFALLS.md) — wrong tenant, SPA platform, 240s timeout, drain, SWA-linked-API confusion, MSAL race, sessionStorage tradeoffs
- [STACK.md §1 §3 (already-verified HIGH confidence)](./../../research/STACK.md) — frontend SPA + identity stack

### Secondary (MEDIUM confidence)

- [Azure Static Web Apps + Entra External ID Q&A](https://learn.microsoft.com/en-us/answers/questions/1464702/authorization-broken-well-known-openid-configurati) — iss URL shape for CIAM
- [SWA CIAM login loop fix](https://en.ittrip.xyz/windows/troubleshooting/swa-ciam-login-loop) — ciamlogin discovery URL form `https://{subdomain}.ciamlogin.com/{tenant_id}/v2.0/.well-known/openid-configuration`
- [Configure authentication in a React.js app — Medium tutorial](https://medium.com/@parfaitkouess/configure-authentication-in-a-react-js-app-by-using-microsoft-entra-external-id-5382004e34b9) — knownAuthorities pattern
- [Server-Sent Events Deep Dive — agentfactory](https://agentfactory.panaversity.org/docs/TypeScript-Language-Realtime-Interaction/async-patterns-streaming/server-sent-events-deep-dive) — async generator + TextDecoder + split-on-\n\n pattern
- [The Python–TypeScript Contract — DEV.to](https://dev.to/nicolas_vbgh/the-python-typescript-contract-3a8d) — `git diff --exit-code` drift-guard pattern

### Tertiary (LOW confidence — verify before relying)

- [DeepWiki: fastapi-azure-auth Azure Entra ID Setup](https://deepwiki.com/intility/fastapi-azure-auth/2.2-azure-entra-id-setup) — community wiki, supplementary
- [DeepWiki: Multi-Tenant Settings](https://deepwiki.com/intility/fastapi-azure-auth/4.2-multi-tenant-settings) — iss_callable usage

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every package version verified via live npm/PyPI 2026-05-19; minor version bumps documented vs CONTEXT.md baseline.
- Architecture: HIGH for documented patterns; MEDIUM for `B2CMultiTenantAuthorizationCodeBearer` choice (verified from source but unproven against a live CIAM endpoint — A1 + Q1).
- Pitfalls: HIGH — Pitfall 1 verified from upstream source 2026-05-19; Pitfalls 2-16 cross-referenced against existing PITFALLS.md (already HIGH confidence).
- Code examples: HIGH for component skeletons (composed from official MS samples + library docs); HIGH for backend rewrite (composed from upstream constructor signature + Phase 1 D-10 pattern); HIGH for Terraform (mirrors Phase 3 D-05/D-06/D-07 patterns); MEDIUM for `azuread_service_principal_delegated_permission_grant` admin-consent resource name (A2).

**Research date:** 2026-05-19
**Valid until:** 2026-06-18 (30 days for stable infra; key MSAL/openapi-typescript/fastapi-azure-auth versions verified live; fastapi-azure-auth is the most likely to ship a breaking change in that window — re-verify constructor shape if planner sees a v5.3 release before phase execution begins)
