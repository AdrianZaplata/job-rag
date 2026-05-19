# Phase 4: Frontend Shell + Auth - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 ships a logged-in-end-to-end SPA when:

1. A new `frontend/` Vite 8 + React 19.2 + TypeScript shell loads from the Phase 3 SWA origin with shadcn/ui (new-york style, zinc accent, light+dark toggle, Geist Sans/Mono).
2. MSAL React 5.3.x completes a real round-trip against `https://${tenant_subdomain}.ciamlogin.com/${tenant_id}/v2.0` from the Phase 3 External tenant — SPA + API app registrations created/managed in a new `infra/external/` Terraform directory (local-state-only, mirrors `infra/bootstrap/`) per the Gap D resolution.
3. Every protected FastAPI route validates the Entra JWT via `fastapi-azure-auth` 5.x (issuer, audience, signature, expiry, JWKS) AND rejects any `oid` other than `settings.seeded_user_entra_oid` with a 403 inside the rewritten `get_current_user_id()` function body (Phase 1 D-10 pattern), all wiring downstream already in place via `Depends(get_current_user_id)`.
4. The MSAL initialization race (AUTH-07) is closed by awaiting `initialize()` + `handleRedirectPromise()` at the top of `main.tsx` BEFORE `ReactDOM.createRoot().render()` — no flash-of-login on hard refresh.
5. Every SPA→API request flows through a custom native-fetch wrapper that calls `acquireTokenSilent` before every call, attaches Bearer, and falls back to `acquireTokenRedirect` on `InteractionRequiredAuthError`. Server state runs through TanStack Query 5.x; types come from `openapi-typescript` codegen against the live FastAPI `/openapi.json`.
6. The route tree uses React Router v7 with a layout route whose `<AuthGate><AppShell/></AuthGate>` wraps `<Outlet/>`; SHEL-06 ships as a layered pattern (root `<ErrorBoundary>` + per-route `<Suspense fallback>` + per-feature shadcn `Skeleton` + empty/error components).
7. A `readSSEStream()` helper + hidden `/debug/agent-stream` page proves end-to-end auth + SSE works in Phase 4 itself, so Phase 6 (Chat) only writes UI.
8. First-login OID bootstrap: Adrian logs in once, backend returns 403, the SPA's AccessDenied page decodes his JWT client-side and shows his `oid` in a copy-block; he sets the KV secret `seeded-user-entra-oid` via `az keyvault secret set`; ACA revision restart triggers a new Alembic migration `00NN_adopt_entra_oid.py` (blocking on startup per Phase 1 D-04) which UPDATEs the seeded row's `entra_oid` column.

Out of scope here (later phases): Dashboard widgets / filter bar (Phase 5), Chat UI / `tool_start`-`tool_end` chips (Phase 6 — Phase 4 only ships the SSE helper), Resume upload + profile CRUD (Phase 7), RAGAS-on-CI + production docs (Phase 8). Phase-2 follow-up to triage 10 persistent extraction failures stays its own Phase-2-rev plan.

</domain>

<decisions>
## Implementation Decisions

### A. Scaffold + Gap D + build-env wiring

- **D-01:** Project location = `frontend/` (literal REQUIREMENTS SHEL-01). Sibling top-level dir to `src/`, `infra/`, `tests/` — matches the Phase 3 layout convention (no monorepo tooling). The single `apps/web/` mention in Phase 3 03-CONTEXT.md `<code_context>` line 187 is a stray quote from STACK.md research; Phase 4 supersedes it. Scaffolded via `npm create vite@latest frontend -- --template react-ts` per STACK.md §1.
- **D-02:** Gap D resolution — External-tenant SPA + API app registrations live in a new `infra/external/` Terraform directory with **local-state-only** management (mirrors `infra/bootstrap/` per Phase 3 D-02). Adrian runs `terraform apply` from his local `az login` against the External tenant (`azuread.external` provider). State file `infra/external/terraform.tfstate` is gitignored. Outputs (`spa_client_id`, `api_client_id`, `api_audience_uri`) feed both `frontend/.env.local` (manually copied or via `scripts/refresh-external-outputs.sh`) AND `infra/envs/prod/prod.tfvars.local` (for two new tfvars: `api_audience` + `tenant_id_external` are already there, but `api_audience_uri` is new). Adrian's local apply is the only execution path for the lifetime of v1 — workforce-tenant GHA SP cannot auth into the External tenant (AADSTS700016, see Phase 3 Gap D doc).
- **D-03:** MSAL config values into the SPA bundle = **VITE_\* build-time env vars**. Build-time bake: `VITE_TENANT_SUBDOMAIN`, `VITE_TENANT_ID`, `VITE_SPA_CLIENT_ID`, `VITE_API_AUDIENCE`, `VITE_API_BASE_URL`. All five are public-by-design (they appear in JWT `iss`/`aud` claims that any holder can read). `frontend/.env.local` (gitignored, dev values + localhost API base) + `frontend/.env.production` (committed, prod values pointing at `aca_fqdn` + SWA origin). `deploy-spa.yml` passes these via Vite's standard `import.meta.env` mechanism — Vite reads from process env at build time. No runtime config fetch, no second config system.
- **D-04:** Backend audience wiring = **plain ACA env vars** (`BACKEND_AUDIENCE`, `ENTRA_TENANT_ID`, `ENTRA_TENANT_SUBDOMAIN`, `SEEDED_USER_ENTRA_OID`). Phase 3 D-13 reserves KV for genuine secrets; these are public-by-design values from JWT claims. Matches `ALLOWED_ORIGINS` pattern (Phase 1 D-26 — also plain env). Source: `SEEDED_USER_ENTRA_OID` from the existing KV secret `seeded-user-entra-oid` via `secretRef` (Phase 3 D-09 placeholder slot — Phase 4 fills); the other three from `prod.tfvars` literals derived from `infra/external/` outputs.

### B. End-to-end auth flow (MSAL + Backend JWT + AUTH-06 + OID bootstrap)

- **D-05:** AUTH-07 race-fix pattern = **top of `main.tsx`**. Literal AUTH-07 wording — `await msalInstance.initialize(); await msalInstance.handleRedirectPromise();` runs BEFORE `ReactDOM.createRoot(rootEl).render(<App/>)`. No wrapping component, no Suspense + `use()` overengineering, no flash-of-null. Accepts ~50-150ms of blank first paint on cold load (PROJECT.md doesn't budget LCP).
- **D-06:** MSAL cache type = **sessionStorage**. Tab-scoped: tokens are gone when the tab closes. Lower XSS blast radius (no token survives between sessions). Adrian re-logs once per session; acceptable for a single-user portfolio app where per-session dwell time is short. Configured via `cacheLocation: 'sessionStorage'` in `PublicClientApplication` config.
- **D-07:** Backend JWT validation = **`fastapi-azure-auth` 5.x `SingleTenantAzureAuthorizationCodeBearer` + chained Depends**. Library handles JWKS caching (LRU), issuer verification (interpolates `tenant_subdomain` + `tenant_id` into the `ciamlogin.com/${tenant_id}/v2.0` issuer URL), audience check (`api://${api_client_id}`), signature, expiry. Wired as a module-level instance in `src/job_rag/api/auth.py`. Add `fastapi-azure-auth ^5.0` + its peer `cryptography` (already present transitively) to `pyproject.toml`. STACK.md AUTH-05 calls out this library by name.
- **D-08:** AUTH-06 single-user `oid` guard placement = **inside `get_current_user_id()` function body** (Phase 1 D-10 function-body rewrite pattern). Every consumer is already wired via `Depends(get_current_user_id)`. New body:
  ```
  async def get_current_user_id(
      user: User = Depends(azure_scheme),  # fastapi-azure-auth's typed user
  ) -> uuid.UUID:
      claims = user.claims  # or however fastapi-azure-auth exposes them
      oid = claims.get("oid")
      if oid != settings.seeded_user_entra_oid:
          raise HTTPException(status_code=403, detail="user_not_allowlisted")
      return settings.seeded_user_id
  ```
  One place for the guard; no per-route decorator drift; integrates with Phase 1's already-wired `/match` `/gaps` `/ingest` `/agent` `/agent/stream` deps. The 403 detail string is generic — the rejected `oid` is logged structurally via structlog (`log.warning("user_not_allowlisted", rejected_oid=oid)`) for LAW audit, but NOT returned in the response body (so future multi-user wouldn't leak signups).
- **D-09:** First-login OID capture UX = **AccessDenied page decodes + displays `oid` client-side**. When AUTH-06 returns 403, the SPA's `/access-denied` route reads `msalInstance.getActiveAccount()?.idTokenClaims?.oid` and shows the value in a `<pre>` code block with a copy-to-clipboard button. Adrian copies, runs `az keyvault secret set --vault-name jobrag-prod-kv --name seeded-user-entra-oid --value <oid>`, restarts the ACA revision. No backend changes (no debug endpoint to harden later), no DevTools spelunking. Server-side `rejected_oid` is also logged via structlog for LAW audit. Explicitly rejected bootstrap-mode short-circuit (D-09a alternative) because External tenant allows public signup — accepting any valid JWT for one revision creates a small risk window.
- **D-10:** Migration `00NN_adopt_entra_oid.py` runs **blocking on container startup** (Phase 1 D-04 / D-09 pattern). `init_db()` → `alembic upgrade head` → migration reads `os.environ['SEEDED_USER_ENTRA_OID']` and runs an idempotent `UPDATE user_db SET entra_oid = :oid WHERE user_id = :seeded_uuid AND (entra_oid IS NULL OR entra_oid != :oid)`. Skips cleanly on empty env (bootstrap-pending state, before D-09 KV-fill). The `user_db.entra_oid` column itself ships in this migration (NOT in Phase 1 — Phase 1 only laid the conceptual hook in D-09, not the schema). Alembic dependency: previous head = `0004_corpus_cleanup`. Pgvector caveat (Phase 1 plan 01-02 D-02): the `connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector` line MUST be in `env.py` before `context.configure()` — already in place.
- **D-11:** Token acquisition pattern = **`acquireTokenSilent` before every API call (interceptor)**. The `authedFetch` wrapper calls `msalInstance.acquireTokenSilent({scopes: [API_SCOPE]})` for every request, attaches result as `Authorization: Bearer <jwt>`. MSAL handles in-memory cache + automatic refresh before expiry. On `InteractionRequiredAuthError` (hard expiry, consent withdrawn, etc.), wrapper catches and calls `msalInstance.acquireTokenRedirect({scopes: [API_SCOPE]})`. On HTTP 401 (signature/audience/expiry rejected by `fastapi-azure-auth`), wrapper retries once after silent refresh; second 401 ⇒ same redirect flow. API_SCOPE = `api://${VITE_API_AUDIENCE}/access_as_user`.
- **D-12:** Logout flow = **`msalInstance.logoutRedirect({postLogoutRedirectUri: SWA_origin})`**. Tells Entra to clear the SSO session AND redirects back to the SWA origin (which then shows the login page via AuthGate). Required `postLogoutRedirectUri` MUST be registered on the SPA app reg in `infra/external/`. Matches Microsoft's recommended pattern; doesn't lie about "sign out" semantics.

### C. API client + TanStack Query + SSE-readiness

- **D-13:** Fetch wrapper = **custom native fetch + MSAL interceptor**. ~30-50 LOC in `frontend/src/api/authedFetch.ts`: signature `authedFetch(input: RequestInfo, init?: RequestInit) → Promise<Response>`. Calls `acquireTokenSilent`, attaches Bearer, threads `init?.signal` through (TanStack Query cancellation). 401 retry-after-refresh path per D-11. No `axios`, no `ofetch` — saves ~14kb gzip, no redundant retry semantics overlapping TanStack Query.
- **D-14:** API type generation = **`openapi-typescript` codegen from `/openapi.json`**. `frontend/package.json` has `"codegen": "openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts"`. Commits `src/api/types.ts`. Re-run on backend schema changes (Phase 6 will add agent SSE event types, Phase 7 will add upload routes — both automatic). The Phase 1 D-04 AgentEvent discriminated union becomes a TS tagged union for free, ready for D-16 SSE helper.
- **D-15:** API service module shape = **typed service module per domain**. `frontend/src/api/{jobs,profile,agent,health}.ts` each export typed async functions like `searchJobs(params: SearchParams): Promise<SearchResponse>` that call `authedFetch` + cast against `openapi-typescript` types. Components use TanStack Query with `{queryKey: ['search', params], queryFn: ({signal}) => searchJobs(params, signal)}`. One place to add a new endpoint; query keys colocated with the domain module.
- **D-16:** SSE helper for Phase 6 = **ship in Phase 4**. `frontend/src/api/readSSEStream.ts` (~60 LOC): `async function* readSSEStream(response: Response): AsyncIterable<AgentEvent>` using `response.body.getReader() + TextDecoder + split-on-\n\n`. Yields typed `AgentEvent`s pulled from D-14 codegen. Phase 4 ALSO ships a hidden `/debug/agent-stream` page that calls it against the live `/agent/stream` to prove end-to-end auth + SSE works during Phase 4 — catches Phase 6 surprises (CORS preflight on `text/event-stream`, Microsoft auth-cookie pollution, ACA Envoy SSE quirks) when they're isolated rather than blocking the Chat UI critical path. Phase 6 then only writes the chat presentation layer (`tool_start`/`tool_end` chips, transcript rendering).

### D. Routing + protected layout + SHEL-06 + shadcn theme

- **D-17:** Router = **React Router v7**. Most mature, biggest docs ecosystem, React 19 + Vite first-class. Declarative `<Routes><Route element={<AppShell/>}><Route .../>}` fits SHEL-04 top-nav layout. No data loaders in v1 — TanStack Query owns data. Adrian's existing React experience is RR-shaped.
- **D-18:** Protected-route pattern (AUTH-04) = **layout route with `<AuthGate>` component wrapping `<AppShell><Outlet/></AppShell>`**. `<AuthGate>` uses MSAL's `useIsAuthenticated()` hook: if false → `msalInstance.loginRedirect({scopes: [API_SCOPE]})`; else → `<Outlet/>`. All protected routes share one guard; sign-out clears state in one place. AccessDenied (`/access-denied`, the D-09 OID-display page) is OUTSIDE the AuthGate so the user can land there without an infinite redirect loop.
- **D-19:** SHEL-06 placement = **layered**: (a) one root `<ErrorBoundary>` (react-error-boundary lib) catches any unhandled render error → global error page with "back to dashboard" + technical-details disclosure; (b) per-route `<Suspense fallback={<RouteSkeleton/>}/>` for React.lazy code-split loading; (c) per-feature loading skeletons (shadcn `Skeleton`) shown via `useQuery().isPending`; (d) per-feature empty states (typed `<EmptyState>` per page — different illustration/CTA for Dashboard "no postings match filter" vs Chat "ask anything" vs Profile "upload your resume"). One pattern per layer; no overlap.
- **D-20:** shadcn theme = **zinc accent / both light+dark (toggle, default dark) / Geist Sans + Geist Mono**. Zinc is the most grayscale-pure (matches PROJECT.md "Linear-style dense grayscale + one accent" — Linear-canonical). Both light + dark with a top-nav toggle covers screenshot scenarios for portfolio (light reads cleaner in README; dark looks more "serious"). Default dark on first load (Linear default; toggle persists to localStorage `theme` key + falls back to `prefers-color-scheme`). Geist Sans (`@fontsource/geist-sans`) + Geist Mono (`@fontsource/geist-mono`) installed via npm (avoids CDN latency, plays nicely with Vite asset pipeline). Tailwind v4 `@theme inline` block in `app.css` per STACK.md §1.

### Claude's Discretion

- Scaffolding commands and tooling specifics: `npm create vite@latest frontend -- --template react-ts`, ESLint flat config (`eslint.config.js` with `typescript-eslint` v8 + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`), Prettier config, Vitest setup file.
- **Vite dev proxy target** = local Docker Compose API (`http://localhost:8000`). Forced by Phase 3 D-04 (dev environment scaffold-only-never-applied); resolves the STATE.md open question.
- Path aliases: `@/*` → `src/*` in both `tsconfig.json` and `vite.config.ts` `resolve.alias`.
- QueryClient defaults: `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 2`, `networkMode: 'online'`.
- Provider nesting order in `main.tsx`: `<MsalProvider>` outer → `<QueryClientProvider>` → `<BrowserRouter>` → `<ErrorBoundary>` → `<App/>` (MSAL must be outermost so `useMsal()` is reachable from `authedFetch` interceptor; ErrorBoundary inside Router so its fallback can use route APIs).
- Codegen wiring: `npm run codegen` script + a CI guard that runs codegen against a backend-PR-snapshot OpenAPI doc and fails if it drifts from committed types (cheap drift detector).
- TanStack Query Devtools: dev-only gate via `import.meta.env.DEV`.
- AbortSignal threading: every `authedFetch` accepts `init.signal`; service module fns pass `signal` from TanStack Query's `queryFn` arg.
- Pre-scaffolded shadcn components: install incrementally as features need them (per SHEL-02 plan). Likely first wave: `button`, `card`, `skeleton`, `dropdown-menu`, `dialog`, `toast` (`sonner`), `input`, `badge`. Later waves per phase.
- Dark mode toggle wiring: top-nav `<ThemeToggle>` reads/writes `localStorage['theme']`, falls back to `window.matchMedia('(prefers-color-scheme: dark)')`. Applies via Tailwind `class="dark"` on `<html>`.
- Route table (preliminary): `/` (redirect to `/dashboard`), `/dashboard` (Phase 5 placeholder), `/chat` (Phase 6 placeholder), `/profile` (Phase 7 placeholder), `/access-denied` (D-09 OID-display, outside AuthGate), `/debug/agent-stream` (D-16 SSE proof, AuthGate'd, dev-only env flag), `*` (404 page).
- Scope request shape: `loginRequest.scopes = [API_SCOPE]` configured once at the SDK init; `acquireTokenSilent` calls use the same array.
- Settings additions in `src/job_rag/config.py`: `entra_tenant_id: str`, `entra_tenant_subdomain: str`, `backend_audience: str` (the `api://${api_client_id}` URI), `seeded_user_entra_oid: str = ""` (empty default = bootstrap-pending state; D-08 guard treats empty as "deny all"; D-10 migration skips on empty).
- fastapi-azure-auth issuer URL builder: `f"https://{settings.entra_tenant_subdomain}.ciamlogin.com/{settings.entra_tenant_id}/v2.0"`. Audience: `settings.backend_audience`. Pass to `SingleTenantAzureAuthorizationCodeBearer(app_client_id=..., openid_config_url=...)`.
- Token-refresh-on-tab-focus behaviour: MSAL default + TanStack Query `refetchOnWindowFocus: false` ⇒ no spurious refetches; MSAL only refreshes silently before expiry. Acceptable.
- `/health` endpoint allowlist exception: leave as-is (unauthenticated, returns 200 — needed for ACA's liveness probe). All OTHER routes require `get_current_user_id` Depends.
- Resource scaffolding for `infra/external/`: own `main.tf`, `variables.tf`, `outputs.tf`, `provider.tf` (only `azuread.external` provider, NO `azurerm`), `terraform.tfvars` template, `README.md` runbook (mirrors `infra/bootstrap/README.md` shape — bootstrap step-by-step + drift-recovery + apply-and-paste-outputs flow).
- Vitest setup file: `frontend/src/test/setup.ts` with `@testing-library/jest-dom` matchers + `cleanup()` afterEach. Vitest config in `vite.config.ts`.

### Folded Todos

None — `gsd-tools todo match-phase 4` returned `todo_count: 0`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing Phase 4.**

### Phase scope and requirements
- `.planning/REQUIREMENTS.md` §SHEL-01 through §SHEL-06 — the 6 v1 frontend-shell requirements Phase 4 owns
- `.planning/REQUIREMENTS.md` §AUTH-01 through §AUTH-07 — the 7 v1 auth requirements Phase 4 owns (AUTH-01/02/03 already physically created in Phase 3 Gap D local-Terraform path; Phase 4 wires them end-to-end)
- `.planning/ROADMAP.md` §Phase 4 — goal + 5 must-be-TRUE success criteria
- `.planning/PROJECT.md` §Constraints — Vite + React + TS frozen, MSAL React + Entra ID External Identities, Linear-dense aesthetic, Azure-only, €0/mo budget
- `.planning/PROJECT.md` §Key Decisions — Vite SPA over Next.js (frontend↔backend separation), Entra External over passphrase (real Azure skill), Linear-dense aesthetic
- `.planning/PROJECT.md` §Context.User-profile — Adrian's React + TypeScript existing skills (not net-new)

### Prior phase decisions (carried forward — do NOT re-litigate)
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-08 — `SEEDED_USER_ID` Python constant; Phase 4 D-10 migration UPDATEs row matching this UUID
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-09 — pre-planned `00NN_adopt_entra_oid.py` migration (Phase 4 D-10 implements it)
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-10 — function-body rewrite pattern; Phase 4 D-08 implements it for `get_current_user_id()`
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-04 — `init_db()` wraps `alembic upgrade head`; Phase 4 D-10 migration auto-runs at ACA startup
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-04 (AgentEvent) — Pydantic discriminated union in `api/sse.py`; Phase 4 D-14 openapi-typescript pulls this into TS tagged union for D-16 SSE helper
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-26 — `CORSMiddleware` env-driven (`ALLOWED_ORIGINS`); Phase 4 doesn't add CORS, uses existing
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-25 — `/agent/stream` 60s timeout; Phase 4 D-16 SSE helper must not enforce a shorter client-side timeout
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §D-05 — External tenant manually bootstrapped + imported in `infra/bootstrap/`
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §D-06 — one External tenant for dev+prod; SPA app reg multi-redirect-URI
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §D-07 — `single_page_application { redirect_uris = [...] }` + `access_as_user` scope + admin consent on SPA delegated perm; `api://<api-client-id>` audience
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §D-09 — KV slot `seeded-user-entra-oid` exists as placeholder; Phase 4 D-09 fills it after first login
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §D-13 — KV reserved for genuine secrets only; Phase 4 D-04 uses plain ACA env for public-by-design IDs
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §D-14 — direct CORS (NOT SWA linked-API); SWA proxy 30-45s timeout would kill SSE
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §A4 — workforce tenant for GHA SP; External for end-user identity only
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` §"Gap D, 2026-05-12" — External-tenant app regs moved to local-only ops surface; Phase 4 D-02 builds `infra/external/` per this constraint

### Stack research (HIGH confidence)
- `.planning/research/STACK.md` §1 — Vite 8.x, React 19.2, TS 5.x, Tailwind v4 (`@tailwindcss/vite`), shadcn/ui new-york style, `@azure/msal-react` 5.3.1, `@azure/msal-browser` 5.8.x, `@tanstack/react-query` 5.x, Vitest 3.x; ESLint flat config + Prettier
- `.planning/research/STACK.md` §3 — Entra External ID flow: SPA → MSAL loginRedirect → `*.ciamlogin.com` authority → access token audienced to `api://<api-app-id>`, scope `access_as_user`
- `.planning/research/STACK.md` §3 Anti-choices — MSAL 1.x deprecated, implicit/hybrid flow deprecated by OAuth 2.1, MUI/Chakra not Linear-aligned
- `.planning/research/STACK.md` §1 Anti-choices — Redux/Zustand for server state ⇒ React Query

### Pitfalls research (HIGH confidence, critical for this phase)
- `.planning/research/PITFALLS.md` §1 — wrong tenant type; Phase 3 D-05 + Phase 4 D-02 alignment
- `.planning/research/PITFALLS.md` §2 — SPA platform vs Web platform; Phase 3 D-07 + Phase 4 D-02 alignment
- `.planning/research/PITFALLS.md` §4 — scale-to-zero cold start; Phase 4 D-16 SSE helper must handle the "connecting" state gracefully so Phase 6 chat UI can show distinct connecting → warming → streaming labels (Phase 3 D-17 defers UX mitigation to Phase 6)
- `.planning/research/PITFALLS.md` §"Looks Done But Isn't Checklist" — verifiers Phase 4 owns: JWT `iss` is `ciamlogin.com/${tenant_id}/v2.0` not workforce, SSE streams to DevTools EventStream tab (Phase 6 verification on the helper Phase 4 ships), CORS rejects unknown origins, AUTH-07 race fix means no flash-of-login on hard refresh

### Codebase audit (Phase 4 must not break)
- `.planning/codebase/ARCHITECTURE.md` — three-tier layering; Phase 4 adds a Frontend tier alongside existing Ingestion/Retrieval/Intelligence tiers
- `.planning/codebase/STACK.md` — backend frozen; Phase 4 only adds `fastapi-azure-auth ^5.0` + its peer
- `src/job_rag/api/auth.py` §`get_current_user_id` (lines 64-83 approx) — function body rewrite target (D-08); module-level `azure_scheme = SingleTenantAzureAuthorizationCodeBearer(...)` instance added above it
- `src/job_rag/api/app.py` §lifespan — already wires CORS via `settings.allowed_origins`; Phase 4 adds NOTHING to lifespan
- `src/job_rag/config.py` §Settings — new fields: `entra_tenant_id`, `entra_tenant_subdomain`, `backend_audience`, `seeded_user_entra_oid` (D-04 + D-08)
- `src/job_rag/api/sse.py` (Phase 1 D-04) — AgentEvent discriminated union; Phase 4 D-14 codegen consumes this via `/openapi.json`
- `alembic/versions/` — existing 4 migrations (0001, 0002, 0003, 0004); Phase 4 adds `0005_adopt_entra_oid.py` per D-10
- `alembic/env.py` — pgvector ischema_names registration already in place
- `Dockerfile` + `scripts/docker-entrypoint.sh` — entrypoint runs `init-db + uvicorn` (Phase 3 A6); D-10 migration auto-runs via `init-db → alembic upgrade head`
- `infra/envs/prod/main.tf` lines 177-208 — placeholder KV secret `seeded_user_entra_oid` already exists; Phase 4 NEW additions to the compute module env block: `BACKEND_AUDIENCE`, `ENTRA_TENANT_ID`, `ENTRA_TENANT_SUBDOMAIN` (plain env), `SEEDED_USER_ENTRA_OID` (via existing `secretRef` to KV)
- `infra/envs/prod/outputs.tf` — TF outputs Phase 4 consumes: `swa_default_origin`, `aca_fqdn`, `tenant_subdomain`, `tenant_id`, `kv_name`. `spa_app_client_id` + `api_app_client_id` removed (Gap D) — Phase 4 D-02 re-creates them in `infra/external/` outputs
- `.github/workflows/deploy-spa.yml` — Phase 4 EXTENDS this workflow to pass `VITE_*` env vars from GitHub Action secrets to the build step (D-03)
- `.github/workflows/deploy-api.yml` — Phase 4 does NOT modify; the new env vars (D-04) flow via Terraform-managed Container App env, not GHA
- `.github/workflows/ci.yml` — Phase 4 ADDS a `frontend-ci` job (typecheck, lint, vitest, codegen-drift-check) alongside the existing Python job

### Phase 4 outputs that Phase 5/6/7 will consume
- `frontend/src/api/authedFetch.ts` (D-13) — Phase 5 dashboard widgets + Phase 7 profile upload all call this
- `frontend/src/api/readSSEStream.ts` (D-16) — Phase 6 chat UI consumes
- `frontend/src/api/types.ts` (D-14 codegen) — all phases consume; re-run codegen as backend schema changes
- `frontend/src/api/{jobs,profile,agent,health}.ts` (D-15) — Phase 5 adds dashboard SQL endpoints in `jobs.ts`, Phase 7 adds resume upload in `profile.ts`
- `frontend/src/components/AppShell.tsx` (D-18) — top-nav with Dashboard/Chat/Profile tabs; Phase 5/6/7 plug their routes into the existing layout slot
- `<AuthGate>` + theme toggle (D-18 + D-20) — landed once in Phase 4, used everywhere
- `infra/external/outputs.tf` (D-02) — `spa_client_id`, `api_client_id`, `api_audience_uri` consumed by `frontend/.env.production` + `infra/envs/prod/prod.tfvars.local`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`get_current_user_id()` function-body rewrite target** (`src/job_rag/api/auth.py` ~line 64-83): every consumer is already wired via `Depends(get_current_user_id)` on `/match`, `/gaps`, `/ingest`, `/agent`, `/agent/stream`. Phase 4 D-08 rewrites only the function body — no call-site changes. Phase 1 D-10's whole point was to make this a one-function-body change.
- **CORSMiddleware env-driven wiring** (`src/job_rag/api/app.py` after lifespan setup): `settings.allowed_origins` already accepts CSV via Phase 1 D-26. Phase 4 doesn't touch CORS; the SWA origin was injected via Phase 3 DEPL-12 two-pass.
- **AgentEvent Pydantic discriminated union** (`src/job_rag/api/sse.py`, Phase 1 D-04): exposed in OpenAPI as a tagged union; Phase 4 D-14 codegen converts it to a TS tagged union that Phase 6's chat UI can `switch` on without runtime parsing.
- **`init_db()` Alembic wrapper** (Phase 1 D-04, in `src/job_rag/db/init.py` or similar): runs at ACA Container App startup via `scripts/docker-entrypoint.sh`. Phase 4 D-10's new migration `0005_adopt_entra_oid.py` rides this rail with no additional plumbing.
- **Phase 3 KV slot** `seeded-user-entra-oid` (`infra/envs/prod/main.tf` line 177-182): placeholder secret with `value_wo = var.seeded_user_entra_oid` already wired. Phase 4 D-09 fills via `az keyvault secret set`; Phase 4 D-04 wires `SEEDED_USER_ENTRA_OID` env var via existing `secretRef` to this slot.
- **Phase 3 TF outputs** (`infra/envs/prod/outputs.tf`): `swa_default_origin`, `aca_fqdn`, `tenant_subdomain`, `tenant_id`, `kv_name` feed Phase 4's `.env.production` + `infra/external/` `terraform.tfvars`.
- **Phase 3 SWA + ACA infrastructure** — no new core infrastructure needed beyond `infra/external/` (app regs) + small additions to the existing `azurerm_container_app` env block.
- **Phase 1 SSE event contract** (`/agent/stream`) — works AS-IS for Phase 4 D-16's `readSSEStream()` helper. Heartbeat events flow through the helper as-is, ready for Phase 6 to render or ignore.

### Established Patterns
- **`structlog get_logger(__name__)`** — Phase 4 backend code follows the same pattern; the AUTH-06 rejected-oid warning uses `log.warning("user_not_allowlisted", rejected_oid=oid)`.
- **`SettingsConfigDict` + `pydantic_settings`** (Phase 1 D-26 / config.py): new Settings fields follow the existing model; `SEEDED_USER_ENTRA_OID` is `str = ""` (default empty = bootstrap-pending) — no `validation_alias`, no special parsing.
- **Phase 1 D-10 function-body rewrite** — the entire AUTH-06/AUTH-05 backend wiring rides this pre-built rail. Pattern: pre-wire Depends() in an early phase, swap the body in a later phase.
- **Phase 3 D-02 / `infra/bootstrap/` pattern** — Phase 4 D-02 `infra/external/` MIRRORS this exactly: dedicated dir, local state (gitignored), one-time-ish run, README runbook, outputs documented for downstream consumption.
- **Phase 3 D-13 KV-vs-plain-env distinction** — KV for genuine secrets, plain env for public-by-design values. Phase 4 D-04 follows this.
- **`uv` for Python deps** — Phase 4 backend additions (`fastapi-azure-auth ^5.0`) go through `uv add` and bump `uv.lock`.
- **Phase 1 D-04 SSE event contract via `to_sse()` helper** — Phase 4 D-16 SSE helper on the SPA side mirrors this exact event shape, so what the backend yields = what the helper yields (modulo deserialization).
- **Phase 2 D-22 PROMPT_VERSION bump pattern for schema-relevant changes** — Phase 4 doesn't change extraction prompts, but the same discipline applies if a future phase needs `entra_oid` shaping in skill extraction (it doesn't).

### Integration Points
- **`src/job_rag/api/auth.py`** — Phase 4 D-08 rewrites `get_current_user_id()` body; adds module-level `azure_scheme = SingleTenantAzureAuthorizationCodeBearer(...)` instance.
- **`src/job_rag/config.py`** — Phase 4 D-04 adds 4 Settings fields (`entra_tenant_id`, `entra_tenant_subdomain`, `backend_audience`, `seeded_user_entra_oid`).
- **`alembic/versions/0005_adopt_entra_oid.py`** — Phase 4 D-10 new migration: adds `entra_oid` column to `user_db` + idempotent UPDATE of seeded row.
- **`pyproject.toml`** — Phase 4 adds `fastapi-azure-auth>=5.0,<6.0` to project deps; `uv.lock` bumps.
- **`frontend/`** (NEW top-level dir) — Phase 4 D-01 creates this; subdirs `src/api`, `src/components`, `src/routes`, `src/test`, etc.
- **`infra/external/`** (NEW top-level dir) — Phase 4 D-02 creates this mirroring `infra/bootstrap/` shape.
- **`infra/envs/prod/main.tf`** — Phase 4 adds 3 new plain env vars + 1 secretRef to the existing `azurerm_container_app` resource's `template.container.env` block.
- **`infra/envs/prod/variables.tf`** + **`prod.tfvars`** — Phase 4 adds `api_audience`, `entra_tenant_subdomain` tfvars (sourced from `infra/external/` outputs); `tenant_id_external` + `tenant_subdomain` + `seeded_user_entra_oid` already exist.
- **`infra/envs/prod/prod.tfvars.local`** (NEW, gitignored) — Phase 4 D-02 outputs are pasted here for prod TF re-apply.
- **`frontend/.env.local`** (NEW, gitignored) — dev VITE_* values + localhost API base.
- **`frontend/.env.production`** (NEW, committed — no secrets) — prod VITE_* values derived from Phase 3 outputs + `infra/external/` outputs.
- **`.github/workflows/deploy-spa.yml`** — Phase 4 EXTENDS to pass VITE_* env vars from GitHub Action secrets at build time (D-03).
- **`.github/workflows/ci.yml`** — Phase 4 ADDS a `frontend-ci` job (Node 20.19+, npm ci, typecheck, lint, vitest, codegen-drift-check) alongside the existing Python job.
- **GitHub repository settings** — Phase 4 adds repo secrets: `VITE_TENANT_ID`, `VITE_TENANT_SUBDOMAIN`, `VITE_SPA_CLIENT_ID`, `VITE_API_AUDIENCE`, `VITE_API_BASE_URL` (referenced by `deploy-spa.yml`).
- **Adrian's local environment** — `infra/external/` apply requires `az login` to Adrian's workforce account with delegated rights into the External tenant (the External tenant admin user, set up during Phase 3 D-05 manual bootstrap).

</code_context>

<specifics>
## Specific Ideas

- Adrian's pattern (17/17 Recommended in Phase 1, 16/16 in Phase 2, 16/16 in Phase 3, 20/20 in Phase 4): downstream agents should keep presenting concrete recommendations + rationale + counterfactuals; bare alternatives waste a turn.
- **STATE.md open question "Vite dev proxy → Compose or dev ACA"** is now closed by Phase 3 D-04 (dev env scaffold-only-never-applied): local Docker Compose API only. Document in `frontend/README.md` proxy section.
- **AUTH-07 race fix wording is literal**: Adrian's REQUIREMENTS.md says "`initialize()` and `handleRedirectPromise()` resolved before `ReactDOM.createRoot().render()`" — Phase 4 D-05 implements exactly this pattern verbatim in `main.tsx`. Do NOT introduce a wrapping component.
- **First-login bootstrap is concrete + documented**: Adrian deploys → logs in → 403 → `/access-denied` shows oid → `az keyvault secret set --vault-name jobrag-prod-kv --name seeded-user-entra-oid --value <oid>` → `az containerapp revision restart` (or auto via secret-change-rotation if enabled) → migration `0005_adopt_entra_oid.py` UPDATEs seed row → next login accepted. Document in `frontend/README.md` + `infra/envs/prod/README.md` as a phase-close runbook.
- **The `apps/web/` stray reference** in Phase 3 03-CONTEXT.md `<code_context>` line 187 is superseded by Phase 4 D-01's `frontend/`. Update Phase 3 CONTEXT.md as a documentation correction in Phase 4's first commit if the planner deems it worth a one-line touch.
- **Linear-dense aesthetic decision lands concretely**: zinc accent / both light+dark (toggle, default dark) / Geist Sans + Geist Mono / shadcn new-york style. PROJECT.md Key Decisions table should reflect this at phase close as: "Linear-dense aesthetic — zinc + Geist + new-york shadcn + default-dark theme toggle".
- **`/debug/agent-stream` route is dev-only**: gate behind `import.meta.env.DEV` so it ships only to the dev build (or behind a `VITE_DEBUG_PAGES` env flag if Adrian wants it in prod for portfolio demos — probably yes given the framing).
- **`infra/external/` is Adrian-local-only forever**: there is no path in v1 (or v1.x) for CI to apply this. Document the every-time-bootstrap-and-paste-outputs flow as the canonical workflow.
- **Reusable-tool framing reminder** (from `~/.claude/projects/.../memory/feedback_reusable_tools.md`): Phase 4 generates `scripts/refresh-external-outputs.sh` (mirror of `scripts/refresh-swa-origin.sh`) — keep as `scripts/`, low reuse expected. The OID-bootstrap `az keyvault secret set` flow is one-shot — keep as a runbook command, NOT a `job-rag` Typer subcommand.

</specifics>

<deferred>
## Deferred Ideas

- **Conversation history / multi-turn chat persistence** — Phase 6 v1 is clear-on-refresh per ROADMAP §Phase 6 success criterion 4; v2.
- **Multi-user signup flow with role-based access** — v1 single-user is structural-platform-ready; v2 platform-era.
- **MFA / passkey support** — Entra External ID supports both; single-user v1 doesn't need them.
- **`/auth/whoami` debug endpoint** (D-09 alternative) — rejected for v1 because client-side decode is simpler; revisit if a future multi-user phase needs a server-validated "who am I" surface.
- **Bootstrap-mode short-circuit** (D-09 alternative) — rejected because External tenant allows public signup; revisit if a future re-tenant operation needs a clean bootstrap path.
- **TanStack Router migration** — revisit if `/dashboard?country=...` query-param typing becomes painful enough; React Router v7 fine for 4 routes.
- **shadcn block-level patterns** (auto-form, complex data tables) — defer until Dashboard Phase 5 actually needs them.
- **Storybook for component-level docs** — portfolio-polish, post-v1.
- **React 19 Activity component for nav-state preservation** — defer until Profile upload (Phase 7) actually needs to preserve form state across nav.
- **TF management of External-tenant app registrations via CI** — Gap D blocker: workforce GHA SP can't auth into External tenant. Revisit when (a) Microsoft ships a cross-tenant `azuread` provider auth flow, or (b) Adrian creates a dedicated External-tenant SP for app-reg management only (would still be a separate trust boundary; not a clear win).
- **Token expiry visual indicator / proactive renewal UX** — `acquireTokenSilent` handles transparently; only revisit if Adrian sees friction.
- **Dev ACA proxy target for Vite** — Phase 3 D-04 left dev as scaffold-only-never-applied; defer until staging-vs-prod is a real need. Forces D-21 Claude's Discretion answer (Compose).
- **Eventsource-parser npm package** (D-16 alternative) — defer; ~60 LOC is fine for one SSE consumer. Revisit if a second consumer appears.
- **Axios or ofetch wrapper** (D-13 alternatives) — defer; native fetch is sufficient for v1.
- **Stable redirect URI per environment** — dev uses `http://localhost:5173/`; prod uses SWA origin. Multi-env redirect URI cardinality might force separate app regs in v2.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 4` returned `todo_count: 0`.

</deferred>

---

*Phase: 04-frontend-shell-auth*
*Context gathered: 2026-05-19*
*Decisions: 20 (all Recommended)*
