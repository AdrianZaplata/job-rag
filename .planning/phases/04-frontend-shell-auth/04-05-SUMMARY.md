---
phase: 04-frontend-shell-auth
plan: 05
subsystem: frontend
tags: [shadcn, react-router-v7, msal-react, sonner, lucide, tailwind-v4, vitest, jsdom, node-25-localstorage-shim, sse-debug-page, oid-bootstrap-ux]

# Dependency graph
requires:
  - phase: 04-frontend-shell-auth (Plan 04-04)
    provides: "frontend/ scaffold, msalInstance singleton, queryClient, authedFetch, readSSEStream, decodeOidFromJwt, GlobalErrorFallback placeholder, AuthGate/ThemeToggle/AppShell skip-on-missing test scaffolds"
provides:
  - "8 shadcn ui/* primitives installed (button card skeleton dropdown-menu dialog sonner input badge) via npx shadcn add; brings sonner@2.0.7 + next-themes@0.4.6 transitively"
  - "AuthGate component — useIsAuthenticated + msalInstance.loginRedirect dispatch on unauthenticated + inProgress==='none'; RouteSkeleton during in-progress; null during redirect-in-flight; <Outlet/> when authenticated (D-18)"
  - "AppShell — h-12 px-6 top-nav per UI-SPEC §7 anatomy: logo, Dashboard/Chat/Profile NavLinks (2px active accent), ThemeToggle, account DropdownMenu (User icon, aria-label='Open account menu') with destructive 'Sign out' item firing logoutRedirect, Toaster bottom-right"
  - "ThemeToggle — D-20 default-dark, localStorage 'theme' persistence, matchMedia fallback, class='dark' toggle on <html>"
  - "ErrorBoundary re-export wrapper + ErrorBoundaryFallback — role='alert' Card with Back-to-dashboard + Reload + <details> stack truncated to 1000 chars (D-19a, UI-SPEC §9)"
  - "RouteSkeleton — Suspense fallback dimensions match EmptyState (max-w-md mx-auto mt-24 p-8) preventing layout shift (D-19b, UI-SPEC §11)"
  - "EmptyState typed primitive {icon, heading, body, cta?} (D-19c/d, UI-SPEC §10)"
  - "PhasePlaceholder typed composition for Phase 5/6/7 with §13 verbatim copy (BarChart3/MessageSquare/User icons)"
  - "AccessDeniedPage — OUTSIDE AuthGate (D-18 redirect-loop avoidance); synchronous useState lazy initializer reads MSAL active account or decodes JWT; empty-OID EmptyState fallback with Sign-in CTA; populated Card with role='region' OID block + Copy ID button + sonner toast + Administrator runbook code block (UI-SPEC §8 + D-09)"
  - "NotFoundPage — EmptyState with FileQuestion icon + Go-to-dashboard CTA"
  - "DebugAgentStreamPage — gated by import.meta.env.DEV || VITE_DEBUG_PAGES==='true' AND wrapped by AuthGate; consumes authedFetch + readSSEStream; lifecycle copy: '… connecting' / '--- end of stream ---' / '--- error: <reason> ---' (UI-SPEC §12, D-16, T-04-05-01 mitigation)"
  - "App.tsx — UI-SPEC §6 route table: AuthGate → AppShell layout owns /dashboard /chat /profile /debug/agent-stream (lazy-loaded with Suspense + RouteSkeleton); /access-denied + * outside AuthGate; / → /dashboard"
  - "main.tsx now wires the real ErrorBoundaryFallback (replaces Wave 3a GlobalErrorFallback placeholder, which is deleted)"
  - "frontend/src/test/setup.ts — installs in-memory Storage shim on every test (Node 25 experimental localStorage shadows jsdom); stubs window.matchMedia (sonner/next-themes consumer)"
  - "vitest.config.ts — jsdom url='http://localhost/' so the (now-shimmed) localStorage doesn't trigger opaque-origin SecurityError"
  - "eslint.config.js override: react-refresh/only-export-components disabled for src/components/ui/** (shadcn-shipped primitives co-export cva variants by design)"
affects: [04-06-runbook]

# Tech tracking
tech-stack:
  added:
    - sonner@2.0.7 (toast — shadcn-shipped via npx shadcn add sonner)
    - next-themes@0.4.6 (shadcn Toaster wrapper consumer; not used by ThemeToggle)
  patterns:
    - "Node-25 localStorage shadowing workaround: Node 22+ ships an experimental global `localStorage` (gated by `--localstorage-file`) that on Node 25 leaks into the jsdom environment and overwrites jsdom's per-window Storage implementation. The leaked object is missing the standard Storage methods (getItem/setItem/removeItem/clear/key/length). Fix: install an in-memory Storage shim in setup.ts each test, redefining both `window.localStorage` and `globalThis.localStorage`. Combined with `environmentOptions.jsdom.url='http://localhost/'` to avoid opaque-origin SecurityError."
    - "AccessDenied synchronous oid read via useState lazy initializer (avoid set-state-in-effect lint rule). MSAL state is settled by the time AuthGate-adjacent routes mount, so reading getActiveAccount() synchronously at mount is safe and removes the cascading-render risk."
    - "shadcn-shipped primitives co-export cva variants — eslint-plugin-react-refresh `only-export-components` is per-directory-disabled via a targeted override on `src/components/ui/**`. Keeps Fast Refresh hygiene for app code; respects the shadcn registry-shipped shape for primitives."
    - "Code-split phase placeholders via React.lazy + Suspense + RouteSkeleton fallback (D-19b). Dashboard / Chat / Profile / DebugAgentStream resolve as separate chunks. AuthGate + AppShell + AccessDenied + NotFound stay in the main bundle (always-needed by AuthGate gating)."

key-files:
  created:
    - frontend/src/components/AuthGate.tsx
    - frontend/src/components/AppShell.tsx
    - frontend/src/components/ThemeToggle.tsx
    - frontend/src/components/ErrorBoundary.tsx (thin re-export wrapper)
    - frontend/src/components/ErrorBoundaryFallback.tsx
    - frontend/src/components/RouteSkeleton.tsx
    - frontend/src/components/EmptyState.tsx
    - frontend/src/components/PhasePlaceholder.tsx
    - frontend/src/components/ui/button.tsx (shadcn-shipped)
    - frontend/src/components/ui/card.tsx (shadcn-shipped)
    - frontend/src/components/ui/skeleton.tsx (shadcn-shipped)
    - frontend/src/components/ui/dropdown-menu.tsx (shadcn-shipped)
    - frontend/src/components/ui/dialog.tsx (shadcn-shipped)
    - frontend/src/components/ui/sonner.tsx (shadcn-shipped)
    - frontend/src/components/ui/input.tsx (shadcn-shipped)
    - frontend/src/components/ui/badge.tsx (shadcn-shipped)
    - frontend/src/routes/AccessDenied.tsx
    - frontend/src/routes/NotFound.tsx
    - frontend/src/routes/Dashboard.tsx
    - frontend/src/routes/Chat.tsx
    - frontend/src/routes/Profile.tsx
    - frontend/src/routes/DebugAgentStream.tsx
    - frontend/src/test/shellPrimitives.test.tsx
  modified:
    - frontend/src/App.tsx (Wave 3a placeholder → full route tree)
    - frontend/src/main.tsx (GlobalErrorFallback → ErrorBoundaryFallback wiring)
    - frontend/src/test/AuthGate.test.tsx (skip-on-missing → real loginRedirect assertion)
    - frontend/src/test/ThemeToggle.test.tsx (skip-on-missing → real toggle + persistence assertion)
    - frontend/src/test/AppShell.test.tsx (skip-on-missing → real nav landmark + tabs assertion)
    - frontend/src/test/setup.ts (matchMedia + Node-25 localStorage shim)
    - frontend/vitest.config.ts (jsdom url + environmentOptions)
    - frontend/eslint.config.js (src/components/ui/** override)
    - frontend/package.json (sonner + next-themes added by `npx shadcn add`)
    - frontend/package-lock.json
  deleted:
    - frontend/src/components/GlobalErrorFallback.tsx (Wave 3a placeholder; replaced by ErrorBoundaryFallback)

key-decisions:
  - "Sonner Toaster shipped uses next-themes via shadcn registry default — next-themes ends up as a transitive dep we don't directly consume. Accepted: the shadcn-shipped sonner.tsx is the canonical registry shape; rewriting it to drop next-themes would diverge from upstream. ThemeToggle still owns localStorage / matchMedia / class='dark' directly (D-20)."
  - "AccessDenied OID read switched from useEffect+setState to useState lazy initializer (Rule 1 — react-hooks/set-state-in-effect new lint rule fires on the original useEffect pattern). MSAL state is settled at mount; reading synchronously is correct and removes the cascading-render risk."
  - "Node-25 experimental localStorage shadowing required a setup-file Storage shim + jsdom URL config. Two-line fix (vitest.config.ts + setup.ts) — no test code changes needed (ThemeToggle.test.tsx uses bare `localStorage.getItem` / `setItem` which now hits the shim)."
  - "Eslint override for src/components/ui/** instead of modifying shadcn-shipped files. Cheaper to keep registry-shipped shape verbatim — re-runs of `npx shadcn add ...` won't regress the project."
  - "DropdownMenuItem uses the `variant='destructive'` prop directly (shadcn 4.7 radix-nova preset supports it native) instead of the className fallback noted in the plan as a defensive option."

patterns-established:
  - "vitest jsdom-environment-options + storage-shim pattern: when running tests on Node 22+ with jsdom, the experimental Node global localStorage can leak into the jsdom window. Fix is two-fold: (1) set `environmentOptions.jsdom.url` so jsdom's localStorage is non-opaque-origin, (2) install an in-memory Storage shim in setup.ts that re-fixes window.localStorage AND globalThis.localStorage each test. Solves Node-25 + jsdom-29 compatibility."
  - "shadcn registry-shipped primitive ESLint scope: react-refresh/only-export-components is per-directory disabled for src/components/ui/** so co-exported cva variants don't fight the registry shape. App-level components stay under the strict rule."
  - "Route placeholder code-splitting via React.lazy + Suspense + RouteSkeleton: cheap path to keep the main bundle small while still providing a layout-stable loading state. Pattern reusable by Phase 5/6/7 routes."

requirements-completed: [SHEL-02, SHEL-04, SHEL-06, AUTH-04]

# Metrics
duration: ~12m
tasks: 2
files-created: 23
files-modified: 10
files-deleted: 1
completed: 2026-05-20
---

# Phase 04 Plan 05: Frontend Shell — Components + Routes + App.tsx Summary

**Wave 3b delivered: AuthGate-wrapped AppShell layout with Dashboard/Chat/Profile tabs + ThemeToggle + Sign-out dropdown; OID-bootstrap AccessDenied page outside AuthGate; dev-gated SSE-probe DebugAgentStream; SHEL-06 layered loading/error states (ErrorBoundary + RouteSkeleton + EmptyState + PhasePlaceholder); 8 shadcn primitives installed; 3 Plan-04 skip-on-missing tests activated + 3 new SHEL-06 rendering tests. 12/12 vitest tests, typecheck + lint + build + codegen-drift all green.**

## Performance

- **Duration:** ~12 min (2 atomic commits)
- **Tasks:** 2 (Task 1 primitives + SHEL-06 tests; Task 2 AppShell + routes + App + activate stubs)
- **Files created:** 23
- **Files modified:** 10
- **Files deleted:** 1 (GlobalErrorFallback Wave 3a placeholder)
- **Commits:**
  - `4a579ce` Task 1 — 8 shadcn primitives + 7 app components + shellPrimitives.test.tsx
  - `11b0186` Task 2 — AppShell + 6 routes + App.tsx + main.tsx ErrorBoundary wiring + activate stub tests + setup/config fixes

## Final shadcn install set

`npx shadcn@latest add button card skeleton dropdown-menu dialog sonner input badge --yes`

Created 8 files in `src/components/ui/`:

| Primitive | Used in Plan 04-05 by | Notes |
|-----------|----------------------|-------|
| `button.tsx` | AppShell, ThemeToggle, ErrorBoundaryFallback, EmptyState (CTA), AccessDenied (Copy + Sign-in), DebugAgentStream | variants: default, ghost (icon-only), outline, destructive |
| `card.tsx` | EmptyState, ErrorBoundaryFallback, AccessDenied | new-york shape — subtle border + shadow-sm |
| `skeleton.tsx` | RouteSkeleton | pulse animation default; `motion-reduce` aware via RouteSkeleton wrapper |
| `dropdown-menu.tsx` | AppShell account menu | DropdownMenuItem.variant='destructive' for Sign out |
| `dialog.tsx` | (not rendered in Plan 04-05; installed per UI-SPEC §5 inventory for Phase 5+) | — |
| `sonner.tsx` | AppShell `<Toaster />`; AccessDenied `toast.success/error` | brings `sonner@2.0.7` + `next-themes@0.4.6` transitively |
| `input.tsx` | DebugAgentStream prompt field | — |
| `badge.tsx` | DebugAgentStream DEV label | `variant='outline'` |

Package.json delta:

```diff
+ "next-themes": "^0.4.6",
+ "sonner": "^2.0.7",
```

Both added transitively by `npx shadcn add` — `next-themes` is the shadcn Toaster's theme-sync consumer (we don't use it directly; ThemeToggle owns localStorage/class-toggle independently).

## App.tsx route table (UI-SPEC §6 + D-17)

| Path | Inside AuthGate? | Component | Code-split | Outlet behavior |
|------|------------------|-----------|------------|-----------------|
| `/` | yes | `<Navigate to="/dashboard" replace/>` | no | immediate |
| `/dashboard` | yes | `<DashboardPage/>` (PhasePlaceholder phase=5) | lazy | Suspense + RouteSkeleton |
| `/chat` | yes | `<ChatPage/>` (PhasePlaceholder phase=6) | lazy | Suspense + RouteSkeleton |
| `/profile` | yes | `<ProfilePage/>` (PhasePlaceholder phase=7) | lazy | Suspense + RouteSkeleton |
| `/debug/agent-stream` | yes | `<DebugAgentStreamPage/>` (lazy, dev-flag gated) | lazy | Suspense + RouteSkeleton |
| `/access-denied` | **no** (D-18) | `<AccessDeniedPage/>` | no | immediate (no Suspense) |
| `*` | no | `<NotFoundPage/>` | no | immediate |

Layout route shape:

```tsx
<Routes>
  <Route element={<AuthGate />}>
    <Route element={<AppShell />}>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="dashboard" element={<Lazy><DashboardPage/></Lazy>} />
      <Route path="chat" element={<Lazy><ChatPage/></Lazy>} />
      <Route path="profile" element={<Lazy><ProfilePage/></Lazy>} />
      {DebugAgentStreamPage && (
        <Route path="debug/agent-stream" element={<Lazy><DebugAgentStreamPage/></Lazy>} />
      )}
    </Route>
  </Route>
  <Route path="/access-denied" element={<AccessDeniedPage/>} />
  <Route path="*" element={<NotFoundPage/>} />
</Routes>
```

`debugEnabled = import.meta.env.DEV || import.meta.env.VITE_DEBUG_PAGES === 'true'` — when false at build time, the `<Route path="debug/agent-stream">` is omitted entirely, so a deep-link falls through to `*` NotFound. AuthGate is still wrapping the surface for defense-in-depth (T-04-05-01).

## AppShell anatomy (UI-SPEC §7)

- **Container:** `min-h-screen flex flex-col bg-background text-foreground` (light/dark via Tailwind tokens)
- **Header:** `h-12 border-b border-border flex items-center px-6 justify-between`
- **Left cluster (`<nav aria-label="Primary">`):** logo `<Link to="/dashboard">job-rag</Link>` + 3 NavLinks (gap-6) with `border-b-2 border-primary` on active
- **Right cluster:** `<ThemeToggle/>` + `<DropdownMenu>` with `<Button variant="ghost" size="icon" aria-label="Open account menu">` trigger
- **DropdownMenu content:** single `<DropdownMenuItem variant="destructive" onSelect>` → `msalInstance.logoutRedirect({postLogoutRedirectUri: window.location.origin})` (D-12)
- **`<main>`:** wraps `<Outlet/>` with `flex-1`
- **`<Toaster position="bottom-right" richColors />`** mounted after `<Outlet/>` so toasts persist across route transitions

Line count: 87 lines (AppShell.tsx).

## AccessDenied anatomy (UI-SPEC §8 + D-09)

OUTSIDE AuthGate per D-18 (else infinite redirect loop on 403).

- **OID compute:** synchronous `useState(computeInitialOid)` reads `msalInstance.getActiveAccount()?.idTokenClaims?.oid`, falls back to `decodeOidFromJwt(account.idToken)` from Plan 04. No `useEffect` → no set-state-in-effect lint warning.
- **Empty-OID fallback:** `<EmptyState icon={ShieldX} heading="Sign in first" body="Sign in to see the account ID you need to share." cta={{label: 'Sign in', onClick: () => msalInstance.loginRedirect(loginRequest)}}/>` — UI-SPEC §8 explicitly avoids an empty `<pre>` block.
- **Populated OID:** `<Card className="max-w-2xl mx-auto mt-12 p-8">` with:
  - `<CardTitle className="text-2xl font-semibold">Access denied</CardTitle>`
  - body copy (UI-SPEC §13 verbatim)
  - `<div role="region" aria-label="Your account ID" className="mb-8 p-4 bg-muted rounded">` containing `<pre><code>{oid}</code></pre>` + `<Button onClick={copyOid}><CopyIcon/> Copy ID</Button>`
  - `<h2>Administrator runbook</h2>` + `<pre className="font-mono text-xs bg-muted p-4">` with the three-step `az keyvault secret set ... && az containerapp revision restart ...` runbook interpolating the live `${oid}`
- **Clipboard UX:** `await navigator.clipboard.writeText(oid)` → `toast.success('Copied to clipboard')`. Failure path → `toast.error("Couldn't copy — please select and copy manually")`.

Line count: 109 lines (AccessDenied.tsx including the `computeInitialOid` helper).

## SHEL-06 layered loading/error states

| Layer | File | Mechanism | Tested by |
|-------|------|-----------|-----------|
| (a) Global render-error boundary | `ErrorBoundary.tsx` re-export + `ErrorBoundaryFallback.tsx` | react-error-boundary lib + `FallbackComponent` in main.tsx; role='alert' Card; Back-to-dashboard + Reload + `<details>` truncated stack | `shellPrimitives.test.tsx` (1/3) — throws Boom, expects "Something went wrong" |
| (b) Per-route Suspense fallback | `RouteSkeleton.tsx` | wraps every lazy-loaded `<Route element>` via `<Lazy>` helper in App.tsx | `shellPrimitives.test.tsx` (3/3) — `getByRole('status', {name: /loading/i})` |
| (c) Per-feature loading skeletons | `Skeleton` from `ui/skeleton.tsx` | Phase 5/6/7 consume via `useQuery().isPending` (not Phase 4 surface) | n/a — Phase 5+ |
| (d) Per-feature empty states | `EmptyState.tsx` + `PhasePlaceholder.tsx` + `NotFound.tsx` + AccessDenied empty-OID fallback | typed primitive with optional CTA | `shellPrimitives.test.tsx` (2/3) — heading + body assertions |

## Test count + results

| File | Status | Tests | Notes |
|------|--------|-------|-------|
| `src/test/authedFetch.test.ts` | pass | 2 | Plan 04-04 active |
| `src/test/readSSEStream.test.ts` | pass | 3 | Plan 04-04 active |
| `src/test/queryClient.test.tsx` | pass | 1 | Plan 04-04 active (SHEL-03 proof) |
| `src/test/AuthGate.test.tsx` | pass | 1 | Plan 04-05 **activated** — loginRedirect called when unauthenticated |
| `src/test/ThemeToggle.test.tsx` | pass | 1 | Plan 04-05 **activated** — toggle persists + class='dark' switches |
| `src/test/AppShell.test.tsx` | pass | 1 | Plan 04-05 **activated** — nav landmark + tabs + account menu present |
| `src/test/shellPrimitives.test.tsx` | pass | 3 | Plan 04-05 **new** — SHEL-06 rendering proof (ErrorBoundary + EmptyState + RouteSkeleton) |
| **Total** | **12/12 pass** | **12** | 7 test files; 9 carried + 3 new |

## Plan verification (final gates)

| Gate | Result |
|------|--------|
| `cd frontend && npm run typecheck` | exits 0 |
| `cd frontend && npm run lint` | exits 0 |
| `cd frontend && npm run test -- --run` | 7 files, 12 tests, all pass |
| `cd frontend && npm run test -- --run shellPrimitives` | 3/3 SHEL-06 rendering tests pass |
| `cd frontend && npm run test -- --run AuthGate ThemeToggle AppShell` | 3/3 reactivated stubs pass |
| `cd frontend && npm run build` | exits 0; `dist/index.html` produced; main bundle 594.97 kB / 174.17 kB gzipped + per-route chunks |
| `cd frontend && npm run codegen:snapshot && git diff --exit-code src/api/types.ts` | no drift (Plan 04-03 drift gate still passes) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] react-hooks/set-state-in-effect on AccessDenied OID read**
- **Found during:** Task 2 lint
- **Issue:** The plan's `useEffect(() => { setOid(...) }, [])` pattern fires the new React 19 / eslint-plugin-react-hooks `set-state-in-effect` rule (cascading-renders warning).
- **Fix:** Refactored to a synchronous `useState(computeInitialOid)` lazy initializer. MSAL state is settled by the time AccessDenied mounts (main.tsx awaits initialize + handleRedirectPromise per AUTH-07), so a synchronous read is correct.
- **Files modified:** `frontend/src/routes/AccessDenied.tsx`
- **Commit:** `11b0186`

**2. [Rule 3 - Blocking] Node 25 experimental localStorage shadows jsdom**
- **Found during:** Task 2 test run (ThemeToggle.test.tsx failed with `localStorage.clear is not a function`)
- **Issue:** Node 22+ ships an experimental global `localStorage` (gated by `--localstorage-file`). On Node 25.9.0 it leaks into the jsdom env and overwrites jsdom's per-window Storage implementation. The leaked object is missing the standard `getItem/setItem/removeItem/clear/key/length` methods.
- **Fix:** Two-line config change:
  1. `vitest.config.ts` — added `environmentOptions: { jsdom: { url: 'http://localhost/' } }` so jsdom's localStorage isn't opaque-origin gated.
  2. `setup.ts` — installs an in-memory Storage shim each `beforeEach`, redefining both `window.localStorage` and `globalThis.localStorage`. The shim is a `Storage`-compatible object backed by a `Map<string, string>`.
- **Files modified:** `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`
- **Commit:** `11b0186`

**3. [Rule 3 - Blocking] jsdom missing window.matchMedia**
- **Found during:** Task 2 test run (AppShell.test.tsx failed with `window.matchMedia is not a function` from sonner via next-themes)
- **Issue:** jsdom 29 doesn't implement `window.matchMedia`. Sonner's `<Toaster>` (rendered by AppShell) consumes next-themes's `useTheme()`, which calls `matchMedia` for prefers-color-scheme detection.
- **Fix:** `setup.ts` polyfills `window.matchMedia` with a deterministic stub that returns `{matches: false, addEventListener: noop, ...}`.
- **Files modified:** `frontend/src/test/setup.ts`
- **Commit:** `11b0186`

**4. [Rule 1 - Lint] shadcn ui/button.tsx + ui/badge.tsx co-export cva variants**
- **Found during:** Task 2 lint
- **Issue:** shadcn-shipped `button.tsx` and `badge.tsx` co-export `buttonVariants` / `badgeVariants` (cva constants) alongside the component. The `eslint-plugin-react-refresh` `only-export-components` rule errors on these by design — Fast Refresh requires component-only modules.
- **Fix:** Targeted eslint override for `src/components/ui/**` (the shadcn-shipped primitive directory): `'react-refresh/only-export-components': 'off'`. App-level components stay under the strict rule. This preserves the shadcn registry-shipped shape (re-runs of `npx shadcn add` won't regress).
- **Files modified:** `frontend/eslint.config.js`
- **Commit:** `11b0186`

**5. [Rule 1 - Cleanup] Deleted unused GlobalErrorFallback.tsx**
- **Found during:** Task 2 main.tsx wiring
- **Issue:** Plan 04-04 shipped `GlobalErrorFallback.tsx` as a Wave 3a placeholder. Plan 04-05 replaces the import in main.tsx with `ErrorBoundaryFallback`. The placeholder was left orphaned.
- **Fix:** `git rm frontend/src/components/GlobalErrorFallback.tsx`. The deletion is intentional and documented per Plan 04-04's summary (line 84 of 04-04-SUMMARY.md: "GlobalErrorFallback.tsx (Wave 3a placeholder)").
- **Files deleted:** `frontend/src/components/GlobalErrorFallback.tsx`
- **Commit:** `11b0186`

**6. [Rule 1 - Lint] Unused eslint-disable in AuthGate**
- **Found during:** Task 2 lint
- **Issue:** Plan template had `// eslint-disable-next-line no-console` above the catch's `console.error`; the project's ESLint config doesn't include the `no-console` rule, so the disable was unused (warning).
- **Fix:** Removed the disable comment.
- **Files modified:** `frontend/src/components/AuthGate.tsx`
- **Commit:** `11b0186`

**7. [Rule 1 - Type] FallbackProps.error is `unknown`, not `Error`**
- **Found during:** Task 1 typecheck
- **Issue:** `react-error-boundary@6.x` types `FallbackProps.error` as `unknown`. The plan's `error.stack ?? error.message` reads off `unknown` and TS errors.
- **Fix:** Narrowed via `error instanceof Error ? error.stack ?? error.message : String(error)`. Same UX, type-safe.
- **Files modified:** `frontend/src/components/ErrorBoundaryFallback.tsx`
- **Commit:** `4a579ce`

**8. [Rule 1 - Type] `Boom` test component as JSX type**
- **Found during:** Task 1 typecheck (shellPrimitives.test.tsx)
- **Issue:** A function that always throws is typed `() => void` by default, which TS rejects as a JSX component.
- **Fix:** Annotated return type as `: never`, which TS accepts as a valid JSX component.
- **Files modified:** `frontend/src/test/shellPrimitives.test.tsx`
- **Commit:** `4a579ce`

### Plan-Aligned Notes (not deviations)

- **DropdownMenuItem `variant="destructive"`** — shadcn radix-nova preset's DropdownMenuItem supports the `variant` prop directly via `data-variant=destructive` styling. No className fallback needed. (The plan's NOTE about checking the generated source confirmed this.)
- **PhasePlaceholder `phase` prop unused in render** — accepted per the plan's explicit note. Kept in the typed contract for future per-phase customization.
- **shadcn Sonner ships `next-themes`** — accepted as a transitive dep. The shadcn-shipped `sonner.tsx` calls `useTheme()` from next-themes for toast-theme sync. We don't wire next-themes anywhere else; ThemeToggle owns `class='dark'` on `<html>` directly. If the toast theme ends up looking off, a future tweak can drop next-themes by setting `theme={'dark'|'light'}` on the Toaster prop instead.
- **`vitest.config.ts environmentOptions`** — added under `test:` (not `defineConfig` top level). Standard vitest config shape; no inheritance conflict with vite.config.ts.

## TDD Gate Compliance

Plan type: `execute` (not `tdd`). No RED/GREEN/REFACTOR gate sequence required. Tests ship alongside implementation per plan instruction (Task 1 includes the SHEL-06 rendering tests; Task 2 activates the three skip-on-missing stubs).

## Self-Check: PASSED

Required files present (all 23 created):
- FOUND: frontend/src/components/AuthGate.tsx
- FOUND: frontend/src/components/AppShell.tsx
- FOUND: frontend/src/components/ThemeToggle.tsx
- FOUND: frontend/src/components/ErrorBoundary.tsx
- FOUND: frontend/src/components/ErrorBoundaryFallback.tsx
- FOUND: frontend/src/components/RouteSkeleton.tsx
- FOUND: frontend/src/components/EmptyState.tsx
- FOUND: frontend/src/components/PhasePlaceholder.tsx
- FOUND: frontend/src/components/ui/{button,card,skeleton,dropdown-menu,dialog,sonner,input,badge}.tsx (8 shadcn primitives)
- FOUND: frontend/src/routes/AccessDenied.tsx
- FOUND: frontend/src/routes/NotFound.tsx
- FOUND: frontend/src/routes/Dashboard.tsx
- FOUND: frontend/src/routes/Chat.tsx
- FOUND: frontend/src/routes/Profile.tsx
- FOUND: frontend/src/routes/DebugAgentStream.tsx
- FOUND: frontend/src/test/shellPrimitives.test.tsx

Required modifications verified:
- FOUND: frontend/src/App.tsx contains `AuthGate`, `AccessDeniedPage`, `import.meta.env.DEV || import.meta.env.VITE_DEBUG_PAGES`
- FOUND: frontend/src/components/AppShell.tsx contains `aria-label="Primary"`, `logoutRedirect`, `Dashboard`, `Chat`, `Profile`, `Sign out`
- FOUND: frontend/src/routes/AccessDenied.tsx contains `decodeOidFromJwt`, `Copy ID`, `seeded-user-entra-oid`, `containerapp revision restart`
- FOUND: frontend/src/main.tsx imports `ErrorBoundaryFallback` (placeholder replaced)
- FOUND: frontend/src/components/GlobalErrorFallback.tsx DELETED

Required commits present:
- FOUND: 4a579ce (Task 1 — primitives + SHEL-06 tests)
- FOUND: 11b0186 (Task 2 — AppShell + routes + App + activations)

All plan must-have truths satisfied. typecheck + lint + test (12/12) + build + codegen-drift all exit 0.
