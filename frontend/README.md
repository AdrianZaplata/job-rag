# frontend — job-rag SPA

Vite 8 + React 19.2 + TypeScript 5.9 + Tailwind v4 + shadcn/ui + MSAL React 5.4 + TanStack Query 5
+ React Router 7. The SPA half of Phase 4 (Frontend Shell + Auth). Hosted on Azure Static Web Apps
in prod; backend lives in a separate Azure Container Apps deployment.

See `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` for the authoritative phase-level
decisions (D-01 through D-20).

## Prerequisites

- Node 22.12+ (or Node 20.19+). Vite 8 requires one of these.
- Docker Compose API running locally on `http://localhost:8000` (see repo root
  `docker-compose.yml`).
- `infra/external/` applied (Adrian-local; produces SPA + API client IDs + audience URI).
- `frontend/.env.local` filled from `.env.local.example` with the values produced above.

## Dev workflow

```bash
cd frontend
npm install
cp .env.local.example .env.local   # then fill the 5 VITE_* values from infra/external/
npm run dev                         # http://localhost:5173 — proxies /api → :8000
```

## Build + verify

```bash
npm run typecheck   # tsc -b --noEmit (project references; strict mode)
npm run lint        # eslint flat config
npm run test        # vitest in jsdom
npm run build       # tsc -b && vite build → dist/
```

## Codegen (OpenAPI → TypeScript types)

Backend ships an OpenAPI spec at `/openapi.json`. Frontend pulls a TS tagged union out of it for
the `AgentEvent` SSE contract and every request/response shape. Two flavours:

```bash
# Against live local backend (Docker Compose):
npm run codegen

# Against the committed snapshot (offline, matches Plan 04-03 CI drift-check baseline):
npm run codegen:snapshot
```

Plan 04-03's CI job runs `codegen` against a hot FastAPI fixture and `git diff --exit-code`s on
the result — if a backend schema change lands without a frontend codegen rerun, CI fails.

## First-login OID bootstrap

The backend rejects every JWT until `seeded_user_entra_oid` is populated. To bootstrap:

1. `npm run build && npm run preview` (or hit prod SWA URL).
2. Log in via MSAL — backend returns 403.
3. SPA's `/access-denied` page (Plan 04-05) decodes your JWT and displays your `oid`.
4. `az keyvault secret set --vault-name jobrag-prod-kv --name seeded-user-entra-oid --value <oid>`
5. `az containerapp revision restart …` — Alembic 0005 (Plan 04-02) updates the seeded row.
6. Reload — login now succeeds.

Full runbook: `.planning/phases/04-frontend-shell-auth/04-06-PLAN.md` (Plan 06 ships the runbook
into `infra/envs/prod/README.md`).

## Notable single-user UX behaviour

- MSAL cache is `sessionStorage` (per CONTEXT.md D-06) → each new tab requires a re-login.
- `VITE_DEBUG_PAGES=true` enables `/debug/agent-stream` in the build (Plan 04-05 ships the route).
- Default theme is dark on first load; toggle persists to `localStorage.theme` (Plan 04-05 ships
  the toggle UI).
