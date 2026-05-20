---
phase: 04-frontend-shell-auth
plan: 03
subsystem: infra
tags: [github-actions, ci, terraform, azure-container-apps, vite, frontend, msal, entra-external-id]

# Dependency graph
requires:
  - phase: 04-frontend-shell-auth (Plan 04-01)
    provides: Settings fields (entra_tenant_id, entra_tenant_subdomain, backend_audience, seeded_user_entra_oid), fastapi-azure-auth dep, infra/external/ scaffold, frontend/openapi.snapshot.json
  - phase: 04-frontend-shell-auth (Plan 04-02)
    provides: B2C JWT validation in get_current_user_id() + AUTH-06 oid allowlist + Alembic 0005 migration
  - phase: 03-infrastructure-ci-cd (Plan 03-01)
    provides: static-tf.yml (PR-only Terraform lint), .tflint.hcl + .tfsec/config.yml, infra/envs/prod/ skeleton, deploy-spa.yml harness, refresh-swa-origin.sh two-pass CORS helper
  - phase: 03-infrastructure-ci-cd (Plan 03-04)
    provides: compute module (ACA Container App), seeded-user-entra-oid KV placeholder slot
  - phase: 03-infrastructure-ci-cd (Plan 03-05a)
    provides: deploy-api.yml per-revision FQDN smoke pattern (mirrored for shape only — SPA promotion is atomic so no smoke needed)
provides:
  - "frontend-ci sibling job in CI workflow (typecheck + lint + vitest + codegen-drift-check) gated by hashFiles('frontend/package.json')"
  - "deploy-spa.yml wired to frontend/ paths + VITE_* env injection (5 secrets + VITE_DEBUG_PAGES)"
  - "ACA compute module accepts 3 new plain-env vars (BACKEND_AUDIENCE, ENTRA_TENANT_ID, ENTRA_TENANT_SUBDOMAIN) — fourth slot SEEDED_USER_ENTRA_OID was pre-wired in Phase 3"
  - "infra/envs/prod composition layer passes 3 new tfvars through to compute module"
  - "prod.tfvars: 3 empty-string placeholders (bootstrap-pending state per D-04); Plan 06 OID-bootstrap runbook fills prod.tfvars.local + re-applies"
affects: [04-04 (frontend scaffold — CI picks up frontend/ dir the moment Plan 04 lands), 04-05 (Phase 4 plan placeholder), 04-06 (OID-bootstrap runbook needs ACA env wiring in place to surface SEEDED_USER_ENTRA_OID to the rewritten get_current_user_id)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Node 22 + npm ci frontend-ci pattern with cache-dependency-path: frontend/package-lock.json"
    - "ephemeral FastAPI + postgres-service pattern for in-CI OpenAPI codegen-drift-check (3-step: live OpenAPI capture → snapshot match → openapi-typescript regen → git diff --exit-code)"
    - "hashFiles('<file>') != '' guard pattern for forward-compat sibling jobs (job activates the moment downstream plan lands its target file; skips cleanly until then)"
    - "OOB-secret runbook comment block at workflow head documenting gh secret set commands sourced from terraform output values"
    - "Phase 4 D-04 KV-vs-plain-env discipline applied: 3 public-by-design values (BACKEND_AUDIENCE, ENTRA_TENANT_ID, ENTRA_TENANT_SUBDOMAIN) wired as plain ACA env; 1 secret value (SEEDED_USER_ENTRA_OID) wired via existing KV secretRef from Phase 3 D-09 placeholder slot"
    - "Name-alignment discipline across the stack: module input name = Pydantic Settings field name = uppercase env name (backend_audience → BACKEND_AUDIENCE, etc.) — keeps three layers grep-coupled"

key-files:
  created: []
  modified:
    - ".github/workflows/ci.yml — added frontend-ci sibling job (parallel to lint-and-test)"
    - ".github/workflows/deploy-spa.yml — 4 apps/web/ refs → frontend/ + VITE_* env block + OOB-secret runbook header"
    - "infra/modules/compute/variables.tf — added 3 vars (backend_audience, entra_tenant_id, entra_tenant_subdomain)"
    - "infra/modules/compute/main.tf — added 3 plain env entries in template.container.env block"
    - "infra/envs/prod/variables.tf — declared 3 parallel vars with inline note re tenant_id_external/tenant_subdomain overlap"
    - "infra/envs/prod/main.tf — module \"compute\" call passes 3 new args"
    - "infra/envs/prod/prod.tfvars — appended 3 empty-string placeholders with source-of-truth comments"

key-decisions:
  - "Reused Phase 3 D-09 SEEDED_USER_ENTRA_OID KV secretRef (already wired in Phase 3 compute module + Phase 3 prod env composition layer) instead of duplicating the wiring. Phase 4 only ADDS the 3 plain-env vars + the existing secretRef stays as-is."
  - "Declared parallel prod env vars (entra_tenant_id, entra_tenant_subdomain) even though tenant_id_external + tenant_subdomain already exist in prod variables.tf with conceptually the same values. Rationale: keeps module input + Pydantic Settings field name + uppercase ACA env name 1:1 alignment (entra_tenant_id → ENTRA_TENANT_ID → settings.entra_tenant_id) — three layers stay grep-coupled. Documented overlap inline in the new var descriptions; Plan 06 runbook will fill both vars with the same value from infra/bootstrap/ outputs."
  - "Kept the codegen-drift-check 3-step pattern (snapshot match → openapi-typescript regen → git diff --exit-code) intact per plan author's RESEARCH.md recommendation. The intermediate snapshot-comparison step catches pre-codegen drift early; the final git diff catches post-codegen drift. Both layers are cheap to run; together they pin both surfaces."
  - "No smoke check added to deploy-spa.yml. SWA promotion is atomic (the deploy step either succeeds or fails synchronously, unlike ACA revisions which can ActivationFail post-deploy). The deploy-api.yml per-revision-FQDN smoke pattern (Gap 10.C / aca-deploy-verifier-trap memory) explicitly does NOT apply here."

patterns-established:
  - "Pattern: hashFiles('<file>') != '' gate for forward-compat sibling jobs — Wave 0 CI workflow ships its frontend-ci job before Plan 04 lands frontend/; the job is dormant (skipped) until package.json appears, then auto-activates. Mirror of Phase 1's Wave 0 test-scaffold skip-on-missing-module pattern, at the CI-job granularity."
  - "Pattern: OOB-secret runbook header comment block at top of deploy workflows — workflow file documents the exact `gh secret set --body \"$(terraform output -raw ...)\"` commands needed to bring it online. Adrian's operational muscle memory stays unified across deploy-api.yml + deploy-spa.yml + future deploy-*.yml flows."

requirements-completed: [SHEL-01, SHEL-04, SHEL-05, AUTH-01, AUTH-02, AUTH-03, AUTH-04]

# Metrics
duration: 5min
completed: 2026-05-20
---

# Phase 4 Plan 03: CI + Deploy + ACA Wiring Summary

**Frontend CI sibling job with codegen-drift-check + deploy-spa.yml rewired to frontend/ with 5 VITE_* secret injections + ACA compute module surfaces 4 new auth env vars (3 plain + 1 KV secretRef)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-20T06:28:26Z
- **Completed:** 2026-05-20T06:33:22Z
- **Tasks:** 2
- **Files modified:** 7
- **Commits:** 2 (1f17db9 + c7c16d9)

## Accomplishments

- **CI workflow:** New `frontend-ci` sibling job parallel to `lint-and-test`. Runs npm ci → typecheck → lint → vitest → boots ephemeral FastAPI against postgres service → snapshot-matches `/openapi.json` against committed `frontend/openapi.snapshot.json` → regens `src/api/types.ts` via openapi-typescript → `git diff --exit-code` catches drift. Job gated by `if: hashFiles('frontend/package.json') != ''` so it skips cleanly until Plan 04 lands the frontend dir.
- **deploy-spa.yml:** 4 `apps/web/` path references → `frontend/` (paths glob, cache-dependency-path, working-directory, app_location). Build step now injects 5 VITE_* secrets (TENANT_SUBDOMAIN/TENANT_ID/SPA_CLIENT_ID/API_AUDIENCE/API_BASE_URL) + VITE_DEBUG_PAGES debug flag. Workflow header documents the `gh secret set --body "$(terraform output -raw ...)"` OOB-secret runbook.
- **Compute module:** 3 new plain-env vars (`backend_audience`, `entra_tenant_id`, `entra_tenant_subdomain`) accepted by the module and emitted into the `template.container.env` block of `azurerm_container_app.api`. SEEDED_USER_ENTRA_OID env entry + KV secretRef already shipped in Phase 3 (D-09 placeholder slot) — Phase 4 inherits this wiring as-is.
- **Prod env composition:** 3 parallel vars declared in `infra/envs/prod/variables.tf`, wired through the `module "compute"` call in `main.tf`, and seeded with empty-string placeholders in `prod.tfvars` (bootstrap-pending state). Plan 06 OID-bootstrap runbook fills `prod.tfvars.local` (gitignored) + re-applies.
- **Terraform fmt + validate:** Both pass clean on `infra/` recursive (modulo a pre-existing deprecation warning in `module.monitoring` unrelated to Phase 4 — `local_authentication_disabled`).

## Task Commits

Each task was committed atomically:

1. **Task 1: ci.yml frontend-ci sibling job + deploy-spa.yml apps/web → frontend + VITE_* env injection** — `1f17db9` (feat)
2. **Task 2: infra/modules/compute env-block extension + infra/envs/prod composition + prod.tfvars placeholders** — `c7c16d9` (feat)

**Plan metadata:** to be appended by orchestrator (docs: complete plan).

## Files Created/Modified

- `.github/workflows/ci.yml` — new `frontend-ci` job (parallel to `lint-and-test`); preserves existing job verbatim
- `.github/workflows/deploy-spa.yml` — frontend/ path rewrite + 5 VITE_* secret env block + OOB-secret runbook header
- `infra/modules/compute/variables.tf` — 3 new module variables (all string, default "")
- `infra/modules/compute/main.tf` — 3 new `env { name = "..." value = var.* }` entries in `template.container` block
- `infra/envs/prod/variables.tf` — 3 parallel env-level variable declarations with inline overlap note
- `infra/envs/prod/main.tf` — `module "compute"` call extended with 3 new arg passes
- `infra/envs/prod/prod.tfvars` — 3 empty-string placeholders + source-of-truth comments pointing at `infra/external/` outputs

## Decisions Made

- **Reused Phase 3 D-09 SEEDED_USER_ENTRA_OID KV secretRef as-is.** The Phase 3 compute module already wired the secret block + env entry; the prod env composition already passes `kv_secret_uris["seeded-user-entra-oid"]`. Phase 4 only adds the 3 plain-env vars. The Plan said "If the secret block exists but the env entry doesn't, this task is purely additive" — both existed, so this task is purely additive.
- **Declared parallel prod env vars** (`entra_tenant_id`, `entra_tenant_subdomain`) even though `tenant_id_external` + `tenant_subdomain` already exist with conceptually the same values. Rationale: keeps module input name = Pydantic Settings field name = uppercase ACA env name 1:1 aligned (e.g. `entra_tenant_id` → `ENTRA_TENANT_ID` env → `settings.entra_tenant_id` field). All three layers stay grep-coupled. Overlap documented inline in the new var descriptions; Plan 06 runbook fills both vars from the same `infra/bootstrap/` output.
- **Kept the codegen-drift-check 3-step pattern.** The plan offered to drop the snapshot-comparison step and rely solely on the final `git diff --exit-code` — kept both layers because they're cheap and they pin two distinct surfaces (live OpenAPI bytes vs committed snapshot, and committed types vs regenerated types).
- **No smoke check added to deploy-spa.yml.** SWA `Azure/static-web-apps-deploy@v1` is synchronous and atomic — the Gap 10.C aca-deploy-verifier-trap memory does NOT apply here. Adding a smoke check would be speculative and out of plan scope.

## Deviations from Plan

None — plan executed exactly as written.

The 3 inline variable description annotations in `infra/envs/prod/variables.tf` (documenting overlap with existing `tenant_id_external` + `tenant_subdomain`) are documentation enhancements, not deviations. The plan's Edit 3 said "if it exists, SKIP the duplicate add (the executor MUST verify with grep -n 'entra_tenant_subdomain' infra/envs/prod/variables.tf and only add if not present)" — verified via grep, the literal name `entra_tenant_subdomain` does NOT exist (only `tenant_subdomain` does), so the plan-authorized add proceeded.

## Issues Encountered

None. terraform fmt was a no-op the first run (files were already well-formatted on commit). terraform validate on `infra/envs/prod/` succeeded with a pre-existing deprecation warning about `local_authentication_disabled` in the monitoring module — unrelated to Phase 4 and out of scope per SCOPE BOUNDARY rule.

## User Setup Required

None for this plan. Two downstream user-setup steps are unblocked by this plan but live in their own plans:

- **GitHub repo secrets** (for deploy-spa.yml): Adrian must run the 6 `gh secret set` commands documented in the deploy-spa.yml workflow header — but only AFTER Plan 06 (infra/external/ first apply) produces the SPA + API client IDs and the API audience URI. Until then, deploy-spa.yml is dormant (paths filter doesn't match `frontend/**` until Plan 04 lands).
- **prod.tfvars.local fills** (for compute module env): Adrian must paste the 3 values from `infra/external/` + `infra/bootstrap/` outputs into `prod.tfvars.local` (gitignored) and re-apply `infra/envs/prod/` — happens in Plan 06 OID-bootstrap runbook.

## Threat Flags

No new security-relevant surface introduced beyond what the plan's `<threat_model>` already covered. T-04-03-01 through T-04-03-06 are all mitigated as designed:

- T-04-03-01 (codegen drift) — mitigated by the 3-step drift-check chain in `frontend-ci`.
- T-04-03-02 (prod secret leak via CI logs) — mitigated by the placeholder env values in `frontend-ci`'s "Start FastAPI in background" step (no `${{ secrets.* }}` references in ci.yml's frontend-ci job).
- T-04-03-03 (env-var name mismatch) — mitigated by name-alignment discipline (BACKEND_AUDIENCE → backend_audience module var → settings.backend_audience field).
- T-04-03-04 (SEEDED_USER_ENTRA_OID leaked as plain env) — mitigated by reusing Phase 3's existing `secret_name = "seeded-user-entra-oid"` secretRef wiring; the Phase 4 env additions are all `value = var.*`, no accidental KV-leak path.
- T-04-03-05 (empty backend_audience deployed to prod) — mitigated by Plan 04-02's fastapi-azure-auth `_iss_callable` design + Plan 06 OID-bootstrap runbook's explicit fill-and-reapply step.
- T-04-03-06 (apps/web/ → frontend/ cache invalidation) — mitigated automatically by Actions cache key change (`cache-dependency-path: frontend/package-lock.json` re-keys on first push).

## Next Phase Readiness

- **Plan 04-04** (frontend scaffold) is unblocked. The moment `frontend/package.json` lands on master, `frontend-ci` flips from "skipped" to "active" automatically — no CI workflow edit needed.
- **Plan 04-05** unblocked (no direct dependency on this plan, but Wave 2 fence cleared).
- **Plan 04-06** (OID-bootstrap runbook) is unblocked. The compute module surfaces all 4 auth env vars (3 plain + 1 KV secretRef); `prod.tfvars` has placeholder slots ready for Adrian's fill-and-reapply pass after first MSAL login produces his oid.
- **Phase 4 close-out** waits on Plans 04-04, 04-05, 04-06 to land + Adrian's one-shot OID-bootstrap apply.

## Self-Check: PASSED

Verified the following:

- `[FOUND] .github/workflows/ci.yml` (modified, frontend-ci job present)
- `[FOUND] .github/workflows/deploy-spa.yml` (modified, frontend/ + VITE_* env present)
- `[FOUND] infra/modules/compute/main.tf` (modified, 3 new env entries)
- `[FOUND] infra/modules/compute/variables.tf` (modified, 3 new vars)
- `[FOUND] infra/envs/prod/main.tf` (modified, 3 new args passed to module)
- `[FOUND] infra/envs/prod/variables.tf` (modified, 3 new var declarations)
- `[FOUND] infra/envs/prod/prod.tfvars` (modified, 3 new tfvar placeholders)
- `[FOUND] commit 1f17db9` (Task 1 commit)
- `[FOUND] commit c7c16d9` (Task 2 commit)
- All 8 plan-level verification commands PASS (YAML parse, no apps/web/, terraform fmt+validate, hashFiles gate, 4 Phase 4 env entries, static-tf shape)
- All 7 must-have truths satisfied

---
*Phase: 04-frontend-shell-auth*
*Completed: 2026-05-20*
