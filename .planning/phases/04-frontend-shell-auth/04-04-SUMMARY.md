---
phase: 04-frontend-shell-auth
plan: 04
subsystem: frontend
tags: [vite, react-19, typescript, tailwind-v4, shadcn, msal-react, tanstack-query, react-router, openapi-typescript, vitest, sse, auth-07-race-fix]

# Dependency graph
requires:
  - phase: 04-frontend-shell-auth (Plan 04-01)
    provides: "frontend/openapi.snapshot.json (drift-baseline OpenAPI capture), frontend/.gitignore placeholder, infra/external/ Terraform scaffold (consumed indirectly via .env.local.example shape)"
  - phase: 04-frontend-shell-auth (Plan 04-02)
    provides: "backend B2C JWT validation + AUTH-06 oid allowlist — Plan 04-04 builds the SPA-side Bearer-attach + 401-retry that talks to it"
  - phase: 04-frontend-shell-auth (Plan 04-03)
    provides: "frontend-ci CI job + deploy-spa.yml VITE_* env wiring + ACA compute env vars — Plan 04-04 fills in the actual frontend/ tree the CI job and SPA workflow point at"
provides:
  - "frontend/ greenfield scaffold (Vite 8 + React 19.2 + TS 5.9 + Tailwind v4 + shadcn radix-nova/neutral)"
  - "MSAL React 5.4 singleton (src/auth/msal.ts) with sessionStorage cache + knownAuthorities for *.ciamlogin.com authority"
  - "AUTH-07 race fix verbatim in src/main.tsx (await initialize + await handleRedirectPromise BEFORE createRoot, line 18 < 19 < 24)"
  - "authedFetch (~80 LOC) — acquireTokenSilent → Bearer; InteractionRequiredAuthError + BrowserAuthError(monitor_window_timeout/no_account/silent_sso) → acquireTokenRedirect; 401 retry-after-refresh per D-11"
  - "readSSEStream — async generator over response.body.getReader() yielding typed AgentEvent (6-event manual union over codegen-extracted individual schemas)"
  - "openapi-typescript codegen output (src/api/types.ts, 598 LOC, 10 schemas) — deterministic against frontend/openapi.snapshot.json"
  - "QueryClient singleton with D-defaults (staleTime:30_000, refetchOnWindowFocus:false, retry:2, networkMode:'online')"
  - "Service modules src/api/{health,jobs,profile,agent}.ts — health.ts active; jobs/profile/agent stub for Phase 5/6/7"
  - "decodeOidFromJwt utility (D-09 — Plan 04-05 AccessDenied consumer)"
  - "6 Vitest test files (3 active: authedFetch + readSSEStream + queryClient — SHEL-03 proof; 3 skip-on-missing: AuthGate/ThemeToggle/AppShell — activate when Plan 04-05 ships components)"
affects: [04-05-frontend-routes-components, 04-06-runbook]

# Tech tracking
tech-stack:
  added:
    - vite@8.0.13
    - react@19.2.6 + react-dom@19.2.6
    - typescript@~5.9.0 (Vite scaffold shipped 6.0; downgraded to satisfy openapi-typescript peer ^5.x)
    - tailwindcss@4.3.0 + @tailwindcss/vite@4.3.0 + tw-animate-css
    - shadcn@4.7.0 (radix-nova preset / neutral base — see Deviations)
    - "@azure/msal-react@5.4.2 + @azure/msal-browser@5.11.0"
    - "@tanstack/react-query@5.100.11 + @tanstack/react-query-devtools@5.100.11"
    - react-router@7.15.1
    - react-error-boundary@6.1.1
    - "@fontsource-variable/geist@5.2.9 + @fontsource/geist-sans@5.2.5 + @fontsource/geist-mono@5.2.8"
    - lucide-react@1.16.0
    - class-variance-authority + clsx + tailwind-merge (shadcn deps)
    - openapi-typescript@7.13.0 (devDep)
    - vitest@3.2.4 + @testing-library/{react,jest-dom,user-event} + jsdom
    - prettier@3.8.3
  patterns:
    - "Vite 8 scaffold + post-hoc shadcn init: when shadcn CLI auto-installs `button.tsx`, remove it to match plan scope and rely on Plan 04-05's `npx shadcn add ...` to re-install with the full first-wave set"
    - "Vite 8 vs vitest vite-rollup type collision workaround: keep vite.config.ts on `from 'vite'` and put the `test:` block in a sibling vitest.config.ts using `from 'vitest/config'` — avoids rolldown-vs-rollup plugin shape mismatch"
    - "AgentEvent type reconstruction: when FastAPI's OpenAPI emitter doesn't promote a tagged-union to a named schema, manually union the individual variant types from `components['schemas']` at the codegen boundary — preserves the type-narrowing UX without requiring backend OpenAPI changes"
    - "Skip-on-missing vitest stub (TS-safe): string-concat the import specifier so tsc doesn't try to resolve at type-check time (mirrors Plan 04-01 Python skip-on-missing pattern); test exits silently when target component module + symbol aren't yet shipped"
    - "Fast-Refresh-clean ErrorBoundary fallback: separate `GlobalErrorFallback` into its own file under `src/components/` to satisfy eslint-plugin-react-refresh `only-export-components` while keeping main.tsx as pure bootstrap"

key-files:
  created:
    - frontend/package.json (+ package-lock.json)
    - frontend/vite.config.ts
    - frontend/vitest.config.ts
    - frontend/tsconfig.json
    - frontend/tsconfig.app.json
    - frontend/tsconfig.node.json
    - frontend/eslint.config.js
    - frontend/.prettierrc
    - frontend/index.html (Pitfall-10 FOUC theme script)
    - frontend/components.json (shadcn radix-nova/neutral)
    - frontend/.env.local.example
    - frontend/.env.production
    - frontend/README.md
    - frontend/src/main.tsx (AUTH-07 race fix + provider nesting)
    - frontend/src/App.tsx (Wave 3a placeholder)
    - frontend/src/app.css (Tailwind v4 + shadcn @theme inline tokens + Geist variable font)
    - frontend/src/vite-env.d.ts (typed VITE_* env)
    - frontend/src/auth/msal.ts (PublicClientApplication singleton)
    - frontend/src/auth/scopes.ts (API_SCOPE + loginRequest)
    - frontend/src/api/authedFetch.ts (D-11/D-13 fetch wrapper)
    - frontend/src/api/readSSEStream.ts (D-16 async generator)
    - frontend/src/api/queryClient.ts (TanStack defaults)
    - frontend/src/api/types.ts (openapi-typescript codegen, 598 LOC)
    - frontend/src/api/health.ts (active service module)
    - frontend/src/api/jobs.ts (Phase 5 stub)
    - frontend/src/api/profile.ts (Phase 7 stub)
    - frontend/src/api/agent.ts (Phase 6 stub)
    - frontend/src/lib/utils.ts (shadcn cn() helper)
    - frontend/src/lib/decodeOidFromJwt.ts (D-09 client-side OID decoder)
    - frontend/src/components/GlobalErrorFallback.tsx (Wave 3a placeholder)
    - frontend/src/components/ui/.gitkeep
    - frontend/src/test/setup.ts
    - frontend/src/test/authedFetch.test.ts (2 active tests)
    - frontend/src/test/readSSEStream.test.ts (3 active tests)
    - frontend/src/test/queryClient.test.tsx (1 active test — SHEL-03 proof)
    - frontend/src/test/AuthGate.test.tsx (skip-on-missing — Plan 04-05 activates)
    - frontend/src/test/ThemeToggle.test.tsx (skip-on-missing — Plan 04-05 activates)
    - frontend/src/test/AppShell.test.tsx (skip-on-missing — Plan 04-05 activates)
  modified:
    - frontend/.gitignore (Vite scaffold defaults preserved + Wave 0 entries appended)

key-decisions:
  - "TypeScript downgrade Vite-scaffold 6.0 → 5.9.x (Rule 3 — blocking dependency conflict). Vite scaffolder shipped TS 6.0.x; openapi-typescript@7.13.0 declares peer `typescript@^5.x`. Aligned to RESEARCH §Standard Stack (TypeScript 5.9+). All deps install cleanly; tsc -b passes."
  - "shadcn init produced `radix-nova` preset with `neutral` base instead of plan-specified `new-york` + `zinc` (Rule 1 — must-have-vs-CLI-reality). shadcn@4.7.0 CLI replaced the new-york/zinc preset pair with the radix-nova/neutral preset pair; neutral is functionally equivalent to zinc (both are grayscale-pure OKLCH ramps). The `style: new-york` plan instruction was overridden by the only-available preset matching the planned aesthetic intent. Plan 04-05 picks up this preset for any `npx shadcn add ...` operations."
  - "Removed auto-installed `src/components/ui/button.tsx` (shadcn init created it; plan says components ship in 04-05). `.gitkeep` ships the empty directory; Plan 04-05 will reinstall via the explicit `npx shadcn add button card skeleton ...` first-wave list."
  - "Removed `navigateToLoginRequestUrl` + `storeAuthStateInCookie` from msal Configuration (Rule 1 — TS error on unknown properties). @azure/msal-browser 5.x moved `navigateToLoginRequestUrl` to per-request HandleRedirectPromiseOptions and removed `storeAuthStateInCookie` from CacheOptions. Library defaults (`navigateToLoginRequestUrl: true`, no cookie fallback on modern browsers) already match the desired behaviour. AUTH-02 + AUTH-04 + D-06 invariants preserved."
  - "AgentEvent type reconstructed manually as a TS union over the 6 individual event schemas (Rule 1 — codegen output didn't include the unified discriminator). The FastAPI OpenAPI emitter currently inlines the `oneOf` on /agent + /agent/stream endpoints rather than promoting the union to a named schema. readSSEStream now exports `type AgentEvent = TokenEvent | ToolStartEvent | ToolEndEvent | HeartbeatEvent | FinalEvent | ErrorEvent` over the codegen-extracted variant schemas. If a future Phase 1 follow-up makes AgentEvent a named ref, swap to `components['schemas']['AgentEvent']` — one-line change."
  - "Vitest config separated into vitest.config.ts (Rule 1 — Vite-8 rolldown vs vitest-vite-rollup plugin-type collision). Importing `defineConfig` from 'vitest/config' in vite.config.ts produces a 100+ line of nested type-mismatch errors because Vite 8 ships rolldown while vitest still bundles rollup-based vite. Sibling vitest.config.ts file uses 'vitest/config' import; vite.config.ts stays on 'vite' import + no `test:` field. Functionally identical for `npm run test` (vitest auto-detects vitest.config.ts)."
  - "GlobalErrorFallback moved out of main.tsx into src/components/GlobalErrorFallback.tsx (Rule 3 — eslint-plugin-react-refresh `only-export-components` lint error). main.tsx is the entrypoint; mixing non-component exports (the fallback) with rendering breaks Fast Refresh hygiene. Separate file fixes the lint error and keeps main.tsx as pure bootstrap."

patterns-established:
  - "Vite-scaffold-then-restore-wave-0 pattern: when a Wave 0 plan pre-creates a few sentinel files (here openapi.snapshot.json + .gitignore placeholder), wrap the Vite scaffold step in `mv frontend frontend.wave0-stash && npm create vite ... && cp ... && rm -rf frontend.wave0-stash`. Lets Wave 0 ship drift-detection artifacts before the full scaffold is in place."
  - "Manual AgentEvent union reconstruction from individual schemas: applies any time a backend OpenAPI tagged-union is inlined rather than promoted. Cheaper than backend schema-emitter changes; one-line swap to named ref if backend later upgrades."
  - "Vitest separation of vitest.config.ts when on Vite 8: avoids the rolldown/rollup plugin shape collision until vitest catches up to Vite 8's bundler swap. Revisit when vitest releases vite@8-rolldown-aware peer support."

requirements-completed: [SHEL-01, SHEL-02, SHEL-03, SHEL-05, AUTH-04, AUTH-07]

# Metrics
duration: ~14m
tasks: 2
files-created: 38
files-modified: 1
completed: 2026-05-20
---

# Phase 04 Plan 04: Frontend Scaffold + Auth/Data Plumbing Summary

**Wave 3a delivered: Vite 8 + React 19.2 + TS 5.9 + Tailwind v4 + shadcn frontend/ scaffold;
MSAL React 5.4 singleton with AUTH-07 race-fix in main.tsx; authedFetch + readSSEStream + queryClient + service modules + openapi-typescript codegen (598 LOC, 10 schemas); 9 vitest tests (3 active modules, 6 tests + 3 skip-on-missing for Plan 04-05) — typecheck / lint / test / build all green.**

## Performance

- **Duration:** ~14 min (2 atomic commits)
- **Started:** 2026-05-20T06:39:45Z
- **Tasks:** 2 (Task 1 scaffold; Task 2 MSAL + fetch + SSE + tests)
- **Files created:** 38
- **Files modified:** 1 (frontend/.gitignore)
- **Commits:** `8d7eb9f` (Task 1 scaffold), `a7da112` (Task 2 plumbing)

## Final package.json dependency inventory

**Runtime (18):**

| Package | Version | Purpose |
|---------|---------|---------|
| `@azure/msal-react` | ^5.4.2 | React hooks + MsalProvider |
| `@azure/msal-browser` | ^5.11.0 | PublicClientApplication |
| `@fontsource-variable/geist` | ^5.2.9 | Geist variable font (shadcn-init shipped) |
| `@fontsource/geist-sans` | ^5.2.5 | Geist Sans (static) |
| `@fontsource/geist-mono` | ^5.2.8 | Geist Mono (static) |
| `@radix-ui/react-slot` | (transitive) | shadcn primitive base |
| `@tailwindcss/vite` | ^4.3.0 | Tailwind v4 Vite integration |
| `@tanstack/react-query` | ^5.100.11 | Server-state cache |
| `@tanstack/react-query-devtools` | ^5.100.11 | Dev-only devtools (gated by import.meta.env.DEV) |
| `class-variance-authority` | ^0.7.1 | shadcn variant composition |
| `clsx` | ^2.1.1 | shadcn `cn()` |
| `lucide-react` | ^1.16.0 | Icon set |
| `react` | ^19.2.6 | UI library |
| `react-dom` | ^19.2.6 | DOM renderer |
| `react-error-boundary` | ^6.1.1 | Top-level ErrorBoundary |
| `react-router` | ^7.15.1 | Routing |
| `tailwind-merge` | ^3.6.0 | shadcn `cn()` |
| `tailwindcss` | ^4.3.0 | Utility-first CSS |
| `tw-animate-css` | ^1.4.0 | shadcn animations |

**Dev (16):**

| Package | Version | Purpose |
|---------|---------|---------|
| `@eslint/js` | ^10.0.1 | ESLint flat-config recommended set |
| `@testing-library/jest-dom` | ^6.9.1 | DOM matchers |
| `@testing-library/react` | ^16.3.2 | Component-render assertions |
| `@testing-library/user-event` | ^14.6.1 | Interaction simulation |
| `@types/node` | ^24.12.3 | Node types (for vite.config) |
| `@types/react` | ^19.2.14 | React types |
| `@types/react-dom` | ^19.2.3 | ReactDOM types |
| `@vitejs/plugin-react` | ^6.0.1 | Vite React plugin |
| `eslint` | ^10.3.0 | Linter |
| `eslint-plugin-react-hooks` | ^7.1.1 | Hooks rules |
| `eslint-plugin-react-refresh` | ^0.5.2 | Vite Fast Refresh hygiene |
| `globals` | ^17.6.0 | ESLint globals presets |
| `jsdom` | ^29.1.1 | DOM env for vitest |
| `openapi-typescript` | ^7.13.0 | OpenAPI → TS codegen |
| `prettier` | ^3.8.3 | Formatter |
| `typescript` | ~5.9.0 | Static types (downgraded from 6.0 per Deviation 1) |
| `typescript-eslint` | ^8.59.2 | TS-aware lint rules |
| `vite` | ^8.0.12 | Bundler + dev server |
| `vitest` | ^3.2.4 | Test runner |

## AUTH-07 race-fix ordering (frontend/src/main.tsx)

Verified via `python3 ... assert init < handle < createRoot`:

```
L18: await msalInstance.initialize()
L19: await msalInstance.handleRedirectPromise()
L24: createRoot(rootEl).render(
```

Both promises resolve BEFORE first React render. No flash-of-login on hard refresh.

## Provider nesting (src/main.tsx lines 25-36)

```
<StrictMode>
  <MsalProvider instance={msalInstance}>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary FallbackComponent={GlobalErrorFallback}>
          <App />
        </ErrorBoundary>
      </BrowserRouter>
      {import.meta.env.DEV && <ReactQueryDevtools />}
    </QueryClientProvider>
  </MsalProvider>
</StrictMode>
```

Matches CONTEXT.md Claude's Discretion immutable nesting order verbatim.

## shadcn init outcome

`frontend/components.json`:
- **Style:** `radix-nova` (shadcn@4.7.0 replaced the historical `new-york` / `default` style pair with named presets; nova is the Lucide/Geist preset)
- **Base color:** `neutral` (functionally equivalent to zinc — both are grayscale-pure OKLCH ramps; see Deviations)
- **CSS variables:** yes
- **Global CSS:** `src/app.css`
- **Aliases:** `@/components` / `@/lib/utils` / `@/components/ui` / `@/lib` / `@/hooks`
- **Icon library:** lucide

`src/app.css` includes:
- `@import "tailwindcss"` + `@import "tw-animate-css"` + `@import "shadcn/tailwind.css"` + `@import "@fontsource-variable/geist"`
- `@custom-variant dark (&:is(.dark *))` for class-based dark mode (matches index.html FOUC theme script)
- `@theme inline { ... }` with full neutral palette in OKLCH, sidebar tokens, radius tokens, font-family tokens (Geist Variable)
- `:root` (light) + `.dark` (dark) palette overrides

`src/lib/utils.ts`: shadcn-generated `cn()` helper (clsx + tailwind-merge).

`src/components/ui/`: empty (`.gitkeep` only); Plan 04-05 runs `npx shadcn add button card skeleton dropdown-menu dialog sonner input badge` for the first wave.

## Codegen result

`frontend/src/api/types.ts`:
- 598 lines
- 10 schemas exported via `components.schemas`:
  - `AgentQuery`, `Body_ingest_ingest_post`, `HTTPValidationError`, `ValidationError`
  - 6 SSE events: `TokenEvent`, `ToolStartEvent`, `ToolEndEvent`, `HeartbeatEvent`, `FinalEvent`, `ErrorEvent`
- 7 paths exported via `paths`: `/health`, `/search`, `/match/{posting_id}`, `/gaps`, `/ingest`, `/agent`, `/agent/stream`
- Generated from `frontend/openapi.snapshot.json` (Plan 04-01 baseline)
- `npm run codegen:snapshot` is deterministic — `git diff --exit-code` clean (matches Plan 04-03 CI drift-check gate)

## Test count + results

| File | Status | Tests | Active? |
|------|--------|-------|---------|
| `src/test/authedFetch.test.ts` | ✓ pass | 2 | ACTIVE — Bearer attach + 401 retry |
| `src/test/readSSEStream.test.ts` | ✓ pass | 3 | ACTIVE — typed events + heartbeat + partial-chunk buffering |
| `src/test/queryClient.test.tsx` | ✓ pass | 1 | ACTIVE — **SHEL-03 proof** (QueryClient + useQuery + QueryClientProvider composition) |
| `src/test/AuthGate.test.tsx` | ✓ pass | 1 | skip-on-missing — Plan 04-05 activates |
| `src/test/ThemeToggle.test.tsx` | ✓ pass | 1 | skip-on-missing — Plan 04-05 activates |
| `src/test/AppShell.test.tsx` | ✓ pass | 1 | skip-on-missing — Plan 04-05 activates |
| **Total** | **9/9 pass** | **9** | 6 active + 3 skip-on-missing |

## SHEL-03 confirmation

`cd frontend && npm run test -- --run queryClient` exits 0 with exactly 1 test passing:

```
✓ src/test/queryClient.test.tsx (1 test) 16ms
  Test Files  1 passed (1)
       Tests  1 passed (1)
```

`src/test/queryClient.test.tsx` mounts `<QueryClientProvider client={queryClient}>` around a probe component that calls `useQuery({ queryFn: async () => 'ok' })` and asserts the resolved value renders. Proves TanStack Query is correctly wired and the singleton from `src/api/queryClient.ts` composes without throwing.

## Plan verification (final gates)

| Gate | Result |
|------|--------|
| `npm run typecheck` (tsc -b --noEmit) | exits 0 |
| `npm run lint` (eslint flat config) | exits 0 |
| `npm run test -- --run` | 6 files, 9 tests, all pass |
| `npm run test -- --run queryClient` | 1 test, passes (SHEL-03) |
| `npm run build` (tsc -b && vite build) | exits 0, dist/ produced (482kB JS, 11kB CSS gzipped) |
| `npm run codegen:snapshot` + git diff | no drift (matches snapshot baseline) |
| AUTH-07 ordering check (init < handle < createRoot) | passes (L18 < L19 < L24) |
| Required deps grep (msal-react, msal-browser, react-query, react-router, react-error-boundary, openapi-typescript, tailwindcss, @tailwindcss/vite) | all present |
| msal.ts `cacheLocation: 'sessionStorage'` + `knownAuthorities` + `ciamlogin.com` | all present |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] TypeScript downgrade 6.0 → 5.9.x**
- **Found during:** Task 1 dev-deps install
- **Issue:** Vite 8 scaffolder shipped TS 6.0.x; `openapi-typescript@7.13.0` declares peer `typescript@^5.x` and npm install refused with ERESOLVE.
- **Fix:** `npm install -D typescript@~5.9.0` (matches RESEARCH §Standard Stack TS 5.9+).
- **Files modified:** package.json, package-lock.json
- **Commit:** `8d7eb9f`

**2. [Rule 1 - shadcn CLI evolution] new-york/zinc → radix-nova/neutral**
- **Found during:** Task 1 shadcn init
- **Issue:** `shadcn@4.7.0` CLI replaced the historical `new-york` / `default` style pair with named presets. `npx shadcn@latest init -t vite -b radix -p nova -y` is the closest functional equivalent to the plan's new-york + zinc spec.
- **Fix:** Accepted `radix-nova` style + `neutral` base — neutral is the grayscale-pure OKLCH ramp matching the plan's zinc aesthetic intent (UI-SPEC §1 Linear-dense look).
- **Files modified:** components.json, src/app.css, src/lib/utils.ts
- **Commit:** `8d7eb9f`

**3. [Rule 1 - Bug] MSAL config unknown properties**
- **Found during:** Task 2 typecheck
- **Issue:** `navigateToLoginRequestUrl: true` (BrowserAuthOptions) and `storeAuthStateInCookie: false` (CacheOptions) are no longer valid in `@azure/msal-browser@5.x`. TS errors with TS2353.
- **Fix:** Removed both lines from `msalConfig`. Library defaults already match the desired behaviour (navigateToLoginRequestUrl defaults to true on the per-request path; cookie-based fallback was removed from CacheOptions because modern browsers no longer need it).
- **Files modified:** src/auth/msal.ts
- **Commit:** `a7da112`

**4. [Rule 1 - Codegen gap] AgentEvent type manual union**
- **Found during:** Task 2 readSSEStream wiring
- **Issue:** `openapi-typescript@7.13.0` extracted the 6 individual event schemas (TokenEvent / ToolStartEvent / ToolEndEvent / HeartbeatEvent / FinalEvent / ErrorEvent) from the snapshot but did NOT emit `AgentEvent` as a unified named schema. FastAPI's OpenAPI emitter inlines the `oneOf` on the path operation rather than promoting it.
- **Fix:** Manually unioned the 6 event types in `readSSEStream.ts`: `export type AgentEvent = TokenEvent | ToolStartEvent | ... | ErrorEvent`. Comment notes the one-line swap to `components['schemas']['AgentEvent']` if a future Phase 1 follow-up promotes the union.
- **Files modified:** src/api/readSSEStream.ts
- **Commit:** `a7da112`

**5. [Rule 1 - Bug] Fast Refresh non-component export in main.tsx**
- **Found during:** Task 2 lint
- **Issue:** `GlobalErrorFallback` was defined inline in main.tsx alongside the createRoot().render() bootstrap. `eslint-plugin-react-refresh`'s `only-export-components` rule errors because main.tsx is parsed as a component module but exports a non-component (the bootstrap is a top-level await + side-effect call).
- **Fix:** Extracted `GlobalErrorFallback` to its own file `src/components/GlobalErrorFallback.tsx`. main.tsx now imports and uses it. Lint clean.
- **Files modified:** src/main.tsx, src/components/GlobalErrorFallback.tsx (new)
- **Commit:** `a7da112`

**6. [Rule 3 - Blocking] Vite 8 / vitest plugin-type collision**
- **Found during:** Task 1 typecheck
- **Issue:** `defineConfig({ test: { ... } })` from `vite`'s exports doesn't accept the `test` field; from `vitest/config`'s exports it produces a 100+ line nested type-mismatch error because Vite 8 uses rolldown internally while vitest bundles a rollup-based vite.
- **Fix:** Split the Vitest config into a sibling `frontend/vitest.config.ts` that imports `from 'vitest/config'` and excludes the Tailwind plugin (CSS off in tests anyway). `vite.config.ts` stays pure `from 'vite'` with no `test:` field. Vitest auto-detects the sibling config file.
- **Files modified:** vite.config.ts, vitest.config.ts (new)
- **Commit:** `8d7eb9f`

**7. [Rule 1 - Plan scope adherence] Removed auto-installed button.tsx**
- **Found during:** Task 1 shadcn init
- **Issue:** `npx shadcn init` automatically installed `src/components/ui/button.tsx`. Plan says "shadcn primitives live in src/components/ui/ — install only `.gitkeep` here in Plan 04-04; actual components ship in Plan 04-05."
- **Fix:** Removed `button.tsx`. `.gitkeep` ships the directory. Plan 04-05 will reinstall via the explicit `npx shadcn add button card ...` first-wave list.
- **Files modified:** src/components/ui/.gitkeep (kept); src/components/ui/button.tsx (deleted before staging)
- **Commit:** `8d7eb9f`

### Plan-Aligned Notes (not deviations)

- The plan's vitest test stubs reference `@/components/AuthGate` / `ThemeToggle` / `AppShell` via `import('@/components/AuthGate')`. TS errors on the unresolved module at typecheck time. Mirrored Plan 04-01's Python skip-on-missing pattern by string-concatenating the import specifier (`const spec = '@/components/' + 'AuthGate'`) so tsc doesn't try to resolve the path until runtime. Adds a `/* @vite-ignore */` comment for Vite. Mirror of three-guard skip pattern from `tests/test_entra_jwt.py`.
- The plan instructed the eslint config to be a flat-config import of `@eslint/js + typescript-eslint + react-hooks + react-refresh`. The Vite scaffold shipped exactly that shape, so no rewrite needed.
- The plan said "preserve the shadcn `@theme inline` block — supplement with @fontsource imports at the top". shadcn-init's app.css already imports `@fontsource-variable/geist` (variable Geist Sans is the new shadcn font default). No supplement needed.

## Self-Check: PASSED

Required files present (all 38 created):
- FOUND: frontend/package.json
- FOUND: frontend/vite.config.ts
- FOUND: frontend/vitest.config.ts
- FOUND: frontend/tsconfig.json + tsconfig.app.json + tsconfig.node.json
- FOUND: frontend/eslint.config.js + .prettierrc
- FOUND: frontend/index.html (FOUC script verified)
- FOUND: frontend/components.json (radix-nova + neutral)
- FOUND: frontend/.env.local.example + .env.production
- FOUND: frontend/README.md
- FOUND: frontend/src/main.tsx (AUTH-07 ordering verified L18 < L19 < L24)
- FOUND: frontend/src/App.tsx (Wave 3a placeholder)
- FOUND: frontend/src/app.css (Tailwind v4 + shadcn @theme inline)
- FOUND: frontend/src/vite-env.d.ts
- FOUND: frontend/src/auth/msal.ts + scopes.ts
- FOUND: frontend/src/api/authedFetch.ts + readSSEStream.ts + queryClient.ts + types.ts (598 LOC)
- FOUND: frontend/src/api/health.ts (active) + jobs.ts + profile.ts + agent.ts (stubs)
- FOUND: frontend/src/lib/utils.ts (shadcn cn) + decodeOidFromJwt.ts
- FOUND: frontend/src/components/GlobalErrorFallback.tsx + ui/.gitkeep
- FOUND: frontend/src/test/setup.ts + 6 test files

Required commits present:
- FOUND: 8d7eb9f (Task 1 scaffold)
- FOUND: a7da112 (Task 2 plumbing)

All plan must-have truths satisfied. typecheck + lint + test (9/9) + build all exit 0.
