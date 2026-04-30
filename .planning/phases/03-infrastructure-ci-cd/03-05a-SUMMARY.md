---
phase: 03-infrastructure-ci-cd
plan: 05a
subsystem: infrastructure
tags: [terraform, azure, prod-env, composition, cors-two-pass, kv-secrets, swa]
requires:
  - 03-02 (bootstrap state backend)
  - 03-03 (network/kv/monitoring modules)
  - 03-04 (database/compute/identity modules)
provides:
  - infra/envs/prod/ — composed prod environment ready for `terraform plan`
  - 11-output Phase 4 hand-off bundle (+ swa_api_key alias for B2)
  - W2 ordered runbook + B2 manual SWA-token-sync + B3 GHCR visibility runbook + A6 corpus bootstrap
affects:
  - Phase 4 frontend (consumes spa_app_client_id, api_app_client_id, aca_fqdn, swa_default_origin)
  - Phase 6 deploy workflows (deploy-api.yml uses gha_client_id; deploy-spa.yml uses AZURE_STATIC_WEB_APPS_API_TOKEN_PROD)
  - Phase 7 smoke (M1–M13 against composed env)
tech-stack:
  added: []
  patterns:
    - DEPL-12 two-pass CORS via locals.allowed_origins_csv (compact + join)
    - W7 composition-layer azurerm_monitor_diagnostic_setting.aca (out of monitoring module)
    - B2 manual SWA api_key sync (no GH_PAT_FOR_SECRETS automated step)
    - dual azuread provider aliases (workforce default + external)
key-files:
  created:
    - infra/envs/prod/backend.tf
    - infra/envs/prod/provider.tf
    - infra/envs/prod/locals.tf
    - infra/envs/prod/variables.tf
    - infra/envs/prod/main.tf
    - infra/envs/prod/outputs.tf
    - infra/envs/prod/prod.tfvars
  modified:
    - infra/envs/prod/README.md (filled section bodies, added W2/B2/B3/A6 sections)
decisions:
  - W7 fix locked: azurerm_monitor_diagnostic_setting.aca lives at composition layer (references module.compute.aca_id + module.monitoring.workspace_id) — NOT in the monitoring module
  - B2 locked: SWA api_key sync stays manual (terraform output -raw swa_api_key | gh secret set ...); no automated `gh secret set` step in deploy-infra.yml (avoids long-lived GH_PAT_FOR_SECRETS)
  - Deployer KV Secrets Officer role assignment lives at composition layer (correct: deployer identity differs between local az login and GHA SP)
  - 4 raw azurerm_key_vault_secret resources at composition (openai, langfuse pub/secret, seeded-user-entra-oid); postgres password stays inside the database module (no duplication)
metrics:
  duration: 12m
  completed: 2026-04-30
---

# Phase 03 Plan 05a: Prod Composition Layer Summary

Composed all six shared modules from Plans 03+04 into the active `infra/envs/prod/` directory, added the four KV application-secret resources, the deployer KV-Secrets-Officer + post-compute ACA-Secrets-User role assignments, the W7 composition-layer ACA diagnostic_setting, the raw Static Web App resource (D-03 single-resource path), and the 11-output Phase 4 hand-off bundle. Filled the prod README with the explicit W2 ordered runbook, the B2 manual SWA-token-sync section, the B3 GHCR visibility runbook, the A6 corpus-bootstrap pointer, the M1–M13 smoke link, and the 180-day SWA token rotation cadence. After this plan, `cd infra/envs/prod && terraform plan -var-file=prod.tfvars` produces a coherent plan against the bootstrap state backend (deferred verification — terraform CLI not installed locally; see CI note below).

## Tasks Executed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Prod env composition (7 TF files) | `2b4cfba` | backend.tf, provider.tf, locals.tf, variables.tf, main.tf, outputs.tf, prod.tfvars |
| 2 | Fill prod README with ordered runbook + W2/B2/B3/A6 sections | `0d2db53` | README.md |

## Composition Highlights

### Module wiring (infra/envs/prod/main.tf)

| Module | Outputs consumed | Inputs supplied |
|--------|------------------|-----------------|
| identity | spa/api/gha client IDs | swa_origin, github_owner, github_repo, resource_group_id; explicit `providers = { azuread.external, azuread.workforce }` map |
| monitoring | workspace_id | env, location, RG, create_budget=true, budget_alert_email |
| network | env_id | env, location, RG, log_analytics_workspace_id (← monitoring.workspace_id) |
| kv | kv_id, kv_uri, kv_name | env, location, RG, tenant_id_workforce (data.azurerm_client_config.current.tenant_id), aca_principal_id=null |
| database | fqdn, admin_login, admin_password_secret_uri | env, location, RG, key_vault_id, kv_admin_role_assignment_id, home_ip, use_allow_azure_services=true |
| compute | aca_id, aca_fqdn, aca_principal_id | env, RG, aca_env_id, ghcr_*, image_tag, kv_secret_uris (5 keys), postgres_*, allowed_origins (← locals.allowed_origins_csv), seeded_user_id |

### Composition-only resources

- `azurerm_resource_group.prod` (root container)
- `azurerm_role_assignment.deployer_kv_secrets_officer` (scope=kv_id, role=Key Vault Secrets Officer, principal=current client)
- 4 × `azurerm_key_vault_secret` (openai_api_key, langfuse_public_key, langfuse_secret_key, seeded_user_entra_oid) — all `depends_on` deployer role assignment
- `azurerm_role_assignment.aca_kv_secrets_user` (scope=kv_id, role=Key Vault Secrets User, principal=module.compute.aca_principal_id) — post-compute
- `azurerm_monitor_diagnostic_setting.aca` (W7 — composition layer, references module.compute.aca_id + module.monitoring.workspace_id; ContainerAppConsoleLogs_CL only per D-16)
- `azurerm_static_web_app.spa` (D-03 raw resource, Free SKU)

### Two-pass CORS (locals.tf)

```hcl
allowed_origins_csv = join(",", compact([
  var.swa_origin == "" ? "" : var.swa_origin,
  "http://localhost:5173",
]))
```

B1-aligned: empty-string + `compact()` (NOT null), matches the identity module's pattern.

### Phase 4 hand-off (outputs.tf — 11 + alias)

`swa_default_origin`, `aca_fqdn`, `kv_name`, `kv_uri`, `tenant_subdomain`, `tenant_id`, `spa_app_client_id`, `api_app_client_id`, `gha_client_id`, `swa_deployment_token` (sensitive=true), `seeded_user_entra_oid_secret_name`, plus `swa_api_key` alias (sensitive=true) for the B2 manual runbook command (`terraform output -raw swa_api_key | gh secret set ...`).

## README sections added/filled

- `## Prerequisites` (bootstrap dependency, terraform.tfvars.local, az login)
- `## Ordered runbook (W2)` — 7 numbered steps (bootstrap → pass 1 → image push → pass 2 → secrets sync → corpus bootstrap → smoke)
- `## First apply (pass 1)` — concrete `terraform init/plan/apply` commands; expected first-revision-fail call-out
- `## Two-Pass CORS Bootstrap` — refresh-swa-origin.sh script behavior + curl verification
- `## Image push: GHCR visibility (B3)` — public-package recommended + private-PAT alternative + GitHub Docs link
- `## Image push and ACA revision update` — deploy-api.yml flow + B5 lifecycle.ignore_changes alignment + manual fallback
- `## Phase-close: GitHub secrets sync (B2)` — manual `gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` command + 180-day cadence
- `## Corpus bootstrap (A6)` — one-time `gh workflow run bootstrap-corpus.yml` pointer
- `## Post-apply smoke checklist` — link to VALIDATION.md M1–M13 + curated highlights (M3 CORS, M7 KV, M8 pgvector, M11 SSE, M13 state hygiene)
- `## Knowingly-accepted security trade-offs` — 5-row table per A1 Path A
- `## Token rotation cadence` — 6-row table including 180-day SWA + 90-day GHCR PAT + on-demand pg password
- `## Home IP refresh` and `## Drift detection`

## Deviations from Plan

None — plan executed exactly as written. The only intentional addition is the swa_api_key alias output called out in the plan's `<done>` criteria for Task 1; that is in the plan, not a deviation.

## Deferred Verification

`terraform fmt -check && terraform init -backend=false && terraform validate` was NOT executed locally — Terraform CLI is not installed on this Windows workstation (verified `which terraform` and `terraform version` both fail). The plan's success-criteria explicitly permits deferral to `static-tf.yml` CI (Plan 06) which runs the fmt/validate/tflint/tfsec gates against the same files. Until Plan 06 ships and CI green-lights this directory, treat fmt/validate as **deferred-to-CI**. Static review of the produced HCL was performed against:

- All 6 module variable files (each input variable verified to match module signature including required validation conditions in compute.kv_secret_uris)
- bootstrap/outputs.tf (tenant_id_external + tenant_subdomain hand-off)
- identity module's `configuration_aliases = [azuread.external, azuread.workforce]` (matched by composition `providers = { ... }` map)

No syntactic or wiring issues identified by manual review.

## Manual Follow-ups (Adrian)

When Adrian is ready to run the first apply:

1. Replace `infra/envs/prod/backend.tf` placeholders with real bootstrap output values per `infra/bootstrap/README.md` Step 3.
2. Fill `infra/envs/prod/prod.tfvars` placeholder values: `tenant_id_external`, `home_ip`, `seeded_user_id`.
3. Provide secrets via `terraform.tfvars.local` (gitignored) or `TF_VAR_*` env vars: `ghcr_pat`, `openai_api_key`, optional `langfuse_*`.
4. After first apply: run `bash scripts/refresh-swa-origin.sh` for the CORS pass 2.
5. Run the B2 manual sync: `terraform output -raw swa_api_key | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD --repo adrianzaplata/job-rag`.
6. Set GHCR package visibility per B3 (public recommended for portfolio repo).

## Self-Check: PASSED

- `infra/envs/prod/backend.tf` — exists (FOUND)
- `infra/envs/prod/provider.tf` — exists (FOUND)
- `infra/envs/prod/locals.tf` — exists (FOUND)
- `infra/envs/prod/variables.tf` — exists (FOUND)
- `infra/envs/prod/main.tf` — exists (FOUND)
- `infra/envs/prod/outputs.tf` — exists (FOUND)
- `infra/envs/prod/prod.tfvars` — exists (FOUND)
- `infra/envs/prod/README.md` — exists with all 12 required section anchors (FOUND)
- Commit `2b4cfba` — present in `git log` (FOUND)
- Commit `0d2db53` — present in `git log` (FOUND)
- README grep gate (12 anchors): all present (verified)
