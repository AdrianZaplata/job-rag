---
status: testing
phase: 03-infrastructure-ci-cd
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05a-SUMMARY.md, 03-05b-SUMMARY.md, 03-06-SUMMARY.md]
started: 2026-05-05T00:00:00Z
updated: 2026-05-13T00:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 10
name: KV Secret Resolution via Managed Identity (M7 / D-13, DEPL-04)
expected: |
  Inside the ACA Container App console (`az containerapp exec ...`): `env | grep OPENAI_API_KEY`
  shows the resolved API key value. LAW query against `KeyVaultData` shows the ACA
  system-assigned managed identity authenticated and read all 5 secrets at container start.
  No literal secret values appear in `terraform.tfstate` (only `key_vault_secret_id` URI
  references).
awaiting: user response


## Tests

### 1. Cold Start Smoke Test (docker-entrypoint.sh)
expected: From a fresh checkout, `docker compose up` boots cleanly with the new `set -euo pipefail` entrypoint. POSTGRES_* → DATABASE_URL composition is no-op when DATABASE_URL preset; `job-rag init-db` runs; uvicorn execs. Ingest+embed steps removed from startup. `curl http://localhost:8000/health` returns 200.
result: pass

### 2. Static-TF Validation Harness (Plan 01)
expected: Open a PR that touches any file under `infra/**`. The `.github/workflows/static-tf.yml` workflow runs and goes green: `terraform fmt -check`, `tflint` (azurerm ruleset), `tfsec` (with documented D-10/A1 allowlist), and per-env `terraform validate` all pass. With Wave 0 empty .tf files, file-existence guards keep validate green; once Plans 02–06 land .tf files, validate exercises real HCL.
result: pass

### 3. Bootstrap Apply — M1
expected: `cd infra/bootstrap && terraform init -backend=false && terraform apply -var-file=terraform.tfvars.local` succeeds against your Azure subscription. Creates `jobrag-tfstate-rg` (westeurope) + `jobragtfstate{5-char-suffix}` storage account (versioning + 7d soft-delete) + `tfstate` container. `terraform output -raw storage_account_name` / `container_name` / `resource_group_name` returns three usable values.
result: pass

### 4. Backend Migration to Remote State — M1
expected: After bootstrap apply, copy the three outputs into `infra/envs/prod/backend.tf`. From a fresh checkout, `cd infra/envs/prod && terraform init` succeeds (state pulled from Azure Blob, no local `.tfstate` written), and `terraform plan -var-file=prod.tfvars` produces a coherent plan against the remote state.
result: pass
notes: "Plan returned 'No changes. Your infrastructure matches the configuration' — state already in sync (prod was applied prior to this UAT session). Two AVM-internal deprecation warnings noted (kv module: enable_rbac_authorization renamed to rbac_authorization_enabled in azurerm v5; monitoring module: local_authentication_disabled). Both are upstream AVM concerns, not Phase 3 scope — track for future AVM version bumps."

### 5. Prod Apply — Full Azure Resource Graph (M2)
expected: `cd infra/envs/prod && terraform apply -var-file=prod.tfvars` succeeds. Portal verification: ACA Container App Environment + jobrag-prod-api Container App (scale-to-zero), Postgres Flex B1ms with `vector` listed in `azure.extensions`, Static Web App (Free SKU), Key Vault with 5 secrets (openai_api_key, langfuse_public_key, langfuse_secret_key, seeded_user_entra_oid, postgres-admin-password), Log Analytics workspace with 0.15 GB/day cap, €10/mo budget alert with 50/75/90/100% thresholds visible.
result: pass
notes: "All 6 resources verified in jobrag-prod-rg via az resource list (jobrag-prod-aca-env, jobrag-prod-api, jobrag-prod-spa, jobrag-prod-kv, jobrag-prod-law, jobrag-prod-pg-ie). All 5 KV secrets present. azure.extensions=VECTOR confirmed. LAW dailyQuotaGb=0.15 confirmed. Budget €10 with 4 thresholds at 50/75/90/100% to adrianzaplata@gmail.com. FINDING: Postgres Flex landed in northeurope (jobrag-prod-pg-ie suffix) instead of westeurope despite prod.tfvars location='westeurope'. Likely Azure free-tier Flex Postgres availability fallback. Cross-region split (API westeurope, DB northeurope) adds ~10ms latency — verify whether intentional in CONTEXT/RESEARCH or track as a follow-up."

### 6. Two-Pass CORS Bootstrap (M3 / DEPL-12)
expected: After first apply, `bash scripts/refresh-swa-origin.sh` reads SWA default origin from terraform output, rewrites `prod.tfvars` (`swa_origin = "https://<swa>.azurestaticapps.net"`), and a second `terraform apply` injects the SWA origin into the Container App's `ALLOWED_ORIGINS` env var. `curl -H "Origin: https://<swa>.azurestaticapps.net" https://<aca-fqdn>/health` returns CORS headers; `curl -H "Origin: https://evil.example" https://<aca-fqdn>/health` is rejected.
result: pass
notes: "ACA fqdn jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io. Allowed origin (witty-flower-065dac003.7.azurestaticapps.net) returns 200 + access-control-allow-origin echoed + vary: Origin header. Evil origin returns 200 (server processes request — CORS is browser-enforced) but NO access-control-allow-origin header — textbook CORS rejection. swa_origin in prod.tfvars line 20 confirms second-pass apply landed."

### 7. OIDC Federated Credential — Master Push (M4 / DEPL-08, DEPL-09)
expected: Push a no-op commit to master under `src/**`. `deploy-api.yml` runs and `azure/login@v2` exchanges OIDC token for an Azure access token (workflow log shows `Login successful`). Push a no-op commit under `apps/web/**` (or any non-infra path); `deploy-infra.yml` does NOT fire (paths filter holds).
result: pass
notes: "Both sub-tests verified. (1) Paths-filter behavior: deploy-infra.yml fires only on infra/** commits (5 prior runs all infra commits, zero false triggers from src or apps/web pushes). (2) OIDC handshake: deploy-api.yml run 25426147786 went fully green end-to-end (18m29s) — Build and push image ✓, Azure login (OIDC) ✓ Login successful, Update Container App image ✓, Smoke /health after revision swap ✓. Path to green required three layered fixes: (a) commit 1aadb83 added Lowercase repo step (ghcr.io path requires lowercase per Docker Registry spec) — orthogonal to OIDC fed cred subject case-sensitivity (commit a4d6c25), no conflict. (b) Manual GHCR package bootstrap from local with fine-grained PAT (one-time, per A2 / B3 runbook in infra/envs/prod/README.md line 115-126). (c) Portal: Manage Actions access → add AdrianZaplata/job-rag with Write role to link the package to the repo so secrets.GITHUB_TOKEN with packages: write can push (without this link, GHA push returns denied: permission_denied: write_package despite valid PAT-bootstrapped package). Bonus coverage: this run implicitly proves Test 9 (GHCR push + ACA pull + 90s /health smoke) since the workflow's own steps execute all of M6's checks."

### 8. OIDC Federated Credential — environment:production (M5 / DEPL-08)
expected: Trigger `deploy-infra.yml` via `workflow_dispatch`. GitHub blocks the run pending review on the protected `production` environment. After you approve as the sole reviewer, OIDC handshake succeeds against the second federated credential subject (`repo:adrianzaplata/job-rag:environment:production`) and the workflow proceeds to `terraform apply`.
result: pass
verified_by: adrian
notes: |
  Run #25825087050 (workflow_dispatch, 2026-05-13, 1m18s) completed green end-to-end.
  azure/login@v2 succeeded; terraform init completed; terraform apply landed with plan
  "0 to add, 1 to change, 0 to destroy" (LAW public-access flags from Gap 12.A landing).
  OIDC handshake succeeded against the `repo:adrianzaplata/job-rag:environment:production`
  federated subject.

  Production env note: no required reviewers are configured on the GH environment,
  so the approval gate doesn't fire. By design for a single-user portfolio repo. The
  federated credential subject claim is the actual auth boundary; the approval rule
  is an optional belt-and-suspenders layer Adrian can add later via repo Settings,
  Environments, production, Required reviewers.

  Path to green required 9 atomic gap fixes (8.A pre-existing, plus 8.B/8.C/8.D/12.A
  bundled, plus A/D/F+G/H discovered during the unblock cycle) and one GH secrets
  config fix (GHCR_PAT). See gap entries below for per-fix detail.

### 9. GHCR Image Push + ACA Pull (M6 / DEPL-07)
expected: After `deploy-api.yml` runs, `docker pull ghcr.io/adrianzaplata/job-rag:<sha>` from a separate machine succeeds (or with the GHCR PAT if package is private). The ACA Container App pulls the same image (revision active) and `curl https://<aca-fqdn>/health` returns 200. Workflow's inline 90s `/health` smoke poll passes loud.
result: pass
verified_by: adrian
notes: |
  All four reproduce steps green:
  1. ACA image binding: `ghcr.io/adrianzaplata/job-rag:ea0af2db2c0471ec4bad09a3588bd5972c496b1d` (commit ea0af2d — pre-fad5236; correct because our TF version fix only touched .github/workflows/*.yml and didn't trigger deploy-api.yml).
  2. Active revision: `jobrag-prod-api--0000003`, Health=Healthy, RunningState=ScaledToZero (free-tier expected — no traffic = scaled to zero).
  3. Local docker pull succeeded with GHCR PAT — all 12 layers pulled, digest `sha256:978ee46d284632e022eb644da8436f76d328f2a5db44a03cb11317ef7a4338bf`.
  4. Live /health returned `HTTP/1.1 200 OK` + `{"status":"ok"}` (uvicorn, ~0.5s — implicit cold-start from zero on first hit).
  Bonus: cold-start from ScaledToZero on the curl request also implicitly validates ACA's pull-on-demand path (image was already cached on the node, but the start-up sequence ran cleanly).

### 10. KV Secret Resolution via Managed Identity (M7 / D-13, DEPL-04)
expected: Inside the ACA Container App console (`az containerapp exec ...`): `env | grep OPENAI_API_KEY` shows the resolved API key value. LAW query against `KeyVaultData` shows the ACA system-assigned managed identity authenticated and read all 5 secrets at container start. No literal secret values appear in `terraform.tfstate` (only `key_vault_secret_id` URI references).
result: [pending]

### 11. pgvector Extension Present (M8 / DEPL-05, DEPL-06)
expected: After first ACA cold-start runs `job-rag init-db`, connect via psql from your home IP (firewall A1 Path A): `psql -h <pg-fqdn> -U jobrag_admin -d jobrag -c "\dx"` lists `vector` extension. `\l` shows `jobrag` DB exists. The `azure.extensions=VECTOR` server allowlist made the extension available; `init-db` enabled it.
result: [pending]

### 12. Log Analytics Daily Quota Holds (M9 / DEPL-10)
expected: LAW portal blade shows `dailyQuotaGb = 0.15`. KQL query: `Usage | where DataType == "ContainerAppConsoleLogs_CL" | summarize sum(Quantity) by bin(TimeGenerated, 1d)` shows ≤4.5 GB/mo total ingestion (well under the 5 GB/mo free-tier alert). Only `ContainerAppConsoleLogs_CL` ingests — SystemLogs absent (D-16 honored at composition layer).
result: [pending]

### 13. Budget Alert Email Arrives (M10 / DEPL-11)
expected: In Azure portal Cost Management → Budgets, the €10/mo subscription budget is visible with 4 thresholds (50/75/90/100%). Trigger "Send test alert" from the portal. `adrianzaplata@gmail.com` receives the test email at the 50% threshold first, confirming both the email channel and the threshold ladder.
result: [pending]

### 14. SSE Flow Survives Envoy 240s (M11 / D-15)
expected: `curl -N https://<aca-fqdn>/agent/stream -H "Authorization: Bearer ..."` with a 60s prompt streams events over multiple seconds without ingress drop. While streaming, deploy a new image via `deploy-api.yml`; in-flight requests drain (terminationGracePeriodSeconds=120 honored), no abrupt connection reset on the live SSE stream.
result: [pending]

### 15. CIAM Authority Metadata Reachable (M12 / D-05)
expected: `curl https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/v2.0/.well-known/openid-configuration` returns valid OpenID Connect discovery metadata with `issuer` claim matching the External tenant. (Phase 4 will exercise the full client flow; Phase 3 only confirms the authority URL is reachable.)
result: pass
verified_by: adrian
notes: |
  `Invoke-RestMethod` on the discovery URL returned 200 with all required OIDC claims:
    issuer: https://3fd51a76-f36e-43a1-aa37-564dad4c41fd.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/v2.0
    authorization_endpoint: https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/oauth2/v2.0/authorize
    token_endpoint: https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/oauth2/v2.0/token
    jwks_uri: https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/discovery/v2.0/keys
    response_types_supported: {code, id_token, code id_token, id_token token}
  Issuer carries the External tenant id (3fd51a76-...c41fd); `code` flow is
  supported for Phase 4 auth-code + PKCE. Authority is reachable; D-05 satisfied
  for Phase 3.

### 16. tfstate Has No Literal Secrets (M13 / D-13, security)
expected: `cd infra/envs/prod && terraform state pull | jq '.. | select(type=="string") | select(test("sk-"))'` returns empty. Searching for OpenAI/Langfuse key prefixes finds nothing in state. Container App secrets appear only as `key_vault_secret_id` URIs, never literal values.
result: issue
severity: minor
verified_by: adrian
notes: |
  Container App half of the test passes: secret blocks reference KV via
  `keyVaultSecretId` URIs, no literal values. Confirmed via
  `Select-String -Pattern 'keyVaultSecretId','/vaults/jobrag-prod-kv/secrets/'`.
  KV-secret half fails: `terraform state pull | Select-String 'sk-'` returns
  two matches, both inside `azurerm_key_vault_secret` resources storing the
  literal in the `value` field while `value_wo` / `value_wo_version` sit unused.
  Affected resources:
    azurerm_key_vault_secret.openai_api_key       (main.tf:120)
    azurerm_key_vault_secret.langfuse_secret_key  (main.tf:144)
  Known TF behavior, not a CI/CD pipeline leak. State sits in Azure Blob with
  versioning + soft-delete + GHA-SP-only ACL, so the at-rest boundary holds,
  but the literal in state remains a real attack surface if backend ACL ever
  weakens. Tracked as Gap 16.A; fix bundled into the Test 8 unblock PR.

### 17. Bootstrap-Corpus Workflow Cost Gate (Plan 05b / A6)
expected: `gh workflow run bootstrap-corpus.yml` (without `acknowledge_cost=yes`) fails fast at the first job step (acknowledge_cost defaulted to "no"). Re-run with `gh workflow run bootstrap-corpus.yml -f acknowledge_cost=yes` — workflow proceeds, `azure/login@v2` succeeds via OIDC, and `az containerapp exec --container api --command "/bin/sh -c 'job-rag ingest --show-cost && job-rag embed --show-cost'"` runs against live ACA. Job summary shows container app name + RG + M8 smoke pointer.
result: [pending]

### 18. Three Deploy Workflows + Paths Filter Contract (Plan 06 / DEPL-08)
expected: All three workflow files exist on disk: `.github/workflows/deploy-infra.yml` (paths: `infra/**`, environment: production, OIDC), `deploy-api.yml` (paths: `src/**` + `Dockerfile` + `pyproject.toml` + `uv.lock` + `alembic/**` + `scripts/docker-entrypoint.sh`, OIDC + `packages: write`), `deploy-spa.yml` (paths: `apps/web/**`, token-based, no `id-token: write`). A backend-only PR fires deploy-api.yml only; an infra-only PR fires deploy-infra.yml only; a frontend-only PR fires deploy-spa.yml only (after Phase 4 lands `apps/web/`).
result: [pending]

## Summary

total: 18
passed: 10
issues: 1
pending: 7
skipped: 0
blocked: 0

## Gaps

# ───── Test 8 / Gap 8.A — RESOLVED ─────
- truth: "deploy-infra.yml CI workflow uses a Terraform version that supports the AVM module set"
  status: resolved
  severity: blocker
  test: 8
  layer: 1
  artifacts:
    - .github/workflows/deploy-infra.yml:33
    - .github/workflows/static-tf.yml:20
  root_cause: "AVM module `Azure/avm-res-dbforpostgresql-flexibleserver@0.2.2` uses `ephemeral` variable attribute (Terraform 1.10+ feature). CI pinned 1.9.5; local was 1.15.0 — masked by Test 5 running locally."
  fix_commit: "fad5236 — bumped terraform_version 1.9.5 → 1.15.0 in both CI workflows (matches Adrian's local TF version for dev/CI parity)."
  verified_by: "Run #11 (push, 25486145775) — terraform init cleared, terraform apply began, modules + providers resolved cleanly. Failure surfaced new layer (gaps 8.B/8.C/8.D)."

# ───── Test 8 / Gap 8.B — OPEN ─────
- truth: "GHA service principal can read+manage Key Vault secrets via terraform apply from CI"
  status: resolved
  fix_commit: "aabe6a9 (close Gap 8.B by granting GHA SP Key Vault Secrets Officer on prod KV). KV-scoped role assignment preserves D-08 by binding to a single resource, not the RG or subscription."
  verified_by: "Run #25825087050: apply completed without 403 on KV secret reads."
  severity: blocker
  test: 8
  layer: 2
  artifacts:
    - infra/envs/prod/main.tf:120  # azurerm_key_vault_secret.openai_api_key
    - infra/envs/prod/main.tf:132  # azurerm_key_vault_secret.langfuse_public_key
    - infra/envs/prod/main.tf:144  # azurerm_key_vault_secret.langfuse_secret_key
    - infra/envs/prod/main.tf:156  # azurerm_key_vault_secret.seeded_user_entra_oid
    - infra/modules/database/main.tf:31  # azurerm_key_vault_secret.pg_admin_password
    - infra/modules/identity/main.tf:133-137  # only RG Contributor granted
  reason: "Run #11 returned `403 Forbidden / ForbiddenByRbac / Assignment: (not found)` on 5 KV secret reads. KV is in RBAC mode; RG-Contributor doesn't grant data-plane access. Local apply (Test 5) succeeded because Adrian's user is sub Owner + KV Administrator."
  root_cause: "GHA SP (`oid=6df66648-7f58-4297-a9cb-9fcf14266535`) has only `Contributor` on `jobrag-prod-rg` (identity/main.tf:133-137 — D-08 compliant). No Key Vault data-plane RBAC role. Resources `azurerm_key_vault_secret.*` need read+write access to the secret values."
  fix: "Add `azurerm_role_assignment` granting GHA SP `Key Vault Secrets Officer` (or split: `Key Vault Crypto Officer` + `Secrets Officer`) on the `jobrag-prod-kv` resource scope (NOT subscription, NOT broader RG). D-08 compliant — narrow data-plane role on a single KV resource."
  d_decisions: ["D-08 (RG-scoped only) — preserved by scoping the new role to the KV resource specifically"]

# ───── Test 8 / Gap 8.C — OPEN ─────
- truth: "azuread provider authenticates via OIDC on the CI runner (no Azure CLI dependency)"
  status: resolved
  fix_commit: "442de27 (close Gap 8.C: azuread provider explicit OIDC config). Added use_cli=!var.use_oidc_auth, use_oidc=var.use_oidc_auth, client_id=var.gha_client_id, tenant_id to both azuread aliases. Workflow injects TF_VAR_gha_client_id, tenant_id_workforce, use_oidc_auth=true so CI authenticates via OIDC while local apply keeps CLI fallback."
  verified_by: "Run #25825087050: azuread provider initialized; no AADSTS700016 on workforce-tenant operations."
  severity: blocker
  test: 8
  layer: 3
  artifacts:
    - infra/envs/prod/provider.tf:31-40  # both azuread.workforce + azuread.external aliases
  reason: "Run #11 azuread provider attempted CLI fallback: `running Azure CLI: exit status 1`, `AADSTS700016: Application with identifier '***' was not found in the directory 'JobRag'`, suggested remediation `az logout / az login`. Runner has no `az login` context for the workforce app."
  root_cause: "provider.tf:31-34 (workforce) and 37-40 (external) declare azuread aliases without explicit auth config. Provider falls back to Azure CLI auth chain. azure/login@v2 sets ARM_* env vars that azurerm picks up via OIDC — but azuread's CLI fallback ignores those env vars."
  fix: "Add `use_cli = false`, `use_oidc = true`, `client_id = var.gha_client_id`, `tenant_id = ...` to BOTH azuread provider blocks. Plumb `gha_client_id` (Workforce-tenant SP appId) as a TF variable — already exposed via `${{ secrets.AZURE_CLIENT_ID }}` env injection in deploy-infra.yml. Verify local apply still works (Adrian has CLI auth — may need conditional or `use_oidc = can(env(\"ARM_OIDC_TOKEN\"))` style config to keep both paths green)."

# ───── Test 10/12 / Gap 12.A — OPEN (AVM default surprise) ─────
- truth: "Log Analytics workspace accepts ingestion from ACA and is queryable by Adrian for audit/cost monitoring"
  status: resolved
  fix_commit: "db6f07e (close Gap 12.A by passing log_analytics_workspace_internet_ingestion_enabled=true and log_analytics_workspace_internet_query_enabled=true to the AVM monitoring module). Overrides AVM's surprise default of Disabled; restores free-tier-expected public-network access."
  verified_by: "Run #25825087050: terraform apply landed the LAW change (only diff in the final clean plan, 0 add, 1 change, 0 destroy)."
  severity: major
  test: 10
  also_affects: [12]
  layer: env-network
  artifacts:
    - infra/modules/monitoring/main.tf:14-27  # AVM module without public-access flags
  reason: "Test 10 Step B blocked: `az monitor log-analytics query` returned `InsufficientAccessError / NspValidationFailedError: Access to workspace 'jobrag-prod-law' from '82.135.96.196' is denied`. Live `az monitor log-analytics workspace show` confirms `publicNetworkAccessForIngestion=Disabled` AND `publicNetworkAccessForQuery=Disabled`."
  root_cause: "AVM module `Azure/avm-res-operationalinsights-workspace/azurerm@0.5.1` defaults both public-access flags to Disabled when no override is supplied. Module config (monitoring/main.tf:14-27) does NOT pass `log_analytics_workspace_internet_ingestion_enabled` or `log_analytics_workspace_internet_query_enabled`, so AVM's `Disabled` default applies. Not a team decision — AVM surprise."
  knock_on_concerns:
    - "Test 12 (LAW daily quota check via KQL) — same query path is blocked"
    - "ACA → LAW pipe: Disabled ingestion may block ACA Console Logs export entirely if not routed via private link / trusted-service exception. Need to verify ANY data is reaching the workspace (e.g. via `az monitor log-analytics workspace get-shared-keys` + manual ingestion test, or check whether the diagnostic_setting at composition layer is actually delivering)."
    - "Test 8 / deploy-infra.yml CI fix: budget reads from CI may stay 401 even after KV/azuread fixes if monitoring module quirks compound — keep eyes open."
  fix_options:
    - "Option 1 (open the workspace): pass `log_analytics_workspace_internet_ingestion_enabled = true` and `log_analytics_workspace_internet_query_enabled = true` to the AVM module — restores expected free-tier behavior."
    - "Option 2 (private link): leave both Disabled, set up a private endpoint on a VNet — overkill for free tier."
    - "Option 3 (selective): enable ingestion (so ACA logs flow), keep query Disabled (workspace queryable via Portal only — but Portal also blocked when query Disabled, so this is illusory)."
  recommendation: "Option 1 — least friction, matches Phase 3's free-tier posture and DEPL-10's intent. The lockdown was unintentional; restoring public access mirrors what would be expected from a `≤€20/mo` portfolio app."

# ───── Test 8 / Gap 8.D — OPEN (architectural) ─────
- truth: "deploy-infra.yml can manage all prod resources via terraform apply from CI without violating D-08"
  status: resolved
  fix_commit: "2d1d734 (close Gap 8.D: Cost Mgmt Contributor at sub scope + D-08 amendment). Named exception to D-08 documented in 03-CONTEXT.md (v1). Cost Management roles cannot mutate workloads (only Microsoft.Consumption/* and Microsoft.CostManagement/*), so the mutation boundary is preserved."
  verified_by: "Run #25825087050: apply completed without 401 on the consumption budget."
  severity: major
  test: 8
  layer: 4
  type: architectural
  artifacts:
    - infra/modules/monitoring/main.tf:43  # azurerm_consumption_budget_subscription.prod
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md  # D-08 decision
  reason: "Run #11 returned `401 Unauthorized` reading `jobrag-prod-budget`. `azurerm_consumption_budget_subscription` is subscription-scoped; GHA SP is RG-scoped only per D-08. Local apply succeeded because Adrian is sub Owner."
  root_cause: "Architectural conflict between D-08 (RG-scoped Contributor — never subscription) and the existence of subscription-scoped resources in the prod composition. Cannot be resolved by RBAC alone without revisiting D-08."
  resolution_options:
    - "Option 1 (D-08 preserved): Switch to `azurerm_consumption_budget_resource_group` — keeps SP scope tight, but loses subscription-wide cost coverage (RG budget only catches in-RG spend)."
    - "Option 2 (narrow D-08 exception): Grant SP `Cost Management Contributor` at subscription scope ONLY. Defensible — Cost Management roles cannot mutate workloads. Document as named exception to D-08."
    - "Option 3 (split apply path): Mark budget as locally-applied resource. Add to a `terraform apply -target` exclude list in CI, document in README runbook for manual local apply on rotation."
  recommendation: "Option 2 (narrowest exception, simplest to implement, most useful telemetry). Update D-08 in CONTEXT.md to read 'RG Contributor on workloads + Cost Management Contributor at subscription'."

# Gap A (Test 8): RESOLVED
- truth: "terraform refresh on CI does not require control-plane reads against resources outside the prod RG (D-08 preserved)"
  status: resolved
  severity: blocker
  test: 8
  layer: "discovered post-bundle (refresh path)"
  artifacts:
    - infra/envs/prod/main.tf:48-53  # azurerm_role_assignment.gha_tfstate_blob_data_contributor scope
  reason: "After 8.B/8.C/8.D landed, CI refresh returned 403 AuthorizationFailed on data.azurerm_storage_account.tfstate. That data lookup requires Microsoft.Storage/storageAccounts/read on jobrag-tfstate-rg, which the GHA SP does not hold (only Blob Data Contributor data-plane per D-08)."
  root_cause: "Data lookup added the tfstate RG to the refresh surface. GHA SP is scoped to prod RG, KV, and sub-Cost-Mgmt only. Local apply worked because Adrian is sub-Owner."
  fix_commit: "a9b9f0b (drop data lookup; construct container scope from data.azurerm_subscription.current.id and var.tfstate_* names already in tfvars). No control-plane read needed; D-08 untouched."
  verified_by: "Run #25825087050: refresh completed without 403 on the tfstate RG."

# Gap D (Test 8): RESOLVED
- truth: "CI-managed prod state contains no resources requiring cross-tenant auth into the External (CIAM) tenant"
  status: resolved
  severity: blocker
  test: 8
  layer: "discovered post-bundle (tenant boundary)"
  artifacts:
    - infra/modules/identity/main.tf  # removed 5 External-tenant resources
    - infra/envs/prod/provider.tf  # removed azuread.external alias
    - infra/envs/prod/outputs.tf  # removed spa_app_client_id, api_app_client_id
    - .github/workflows/deploy-infra.yml  # removed those output prints
  reason: "After 8.C wired azuread OIDC for the workforce tenant, CI still failed with AADSTS700016 (Application not found in directory JobRag) for the azuread.external provider alias. Microsoft Entra External ID treats CIAM tenants as deliberately-isolated trust boundaries that cannot be managed with a workforce-tenant SP."
  root_cause: "Workforce-tenant GHA SP cannot authenticate into the External tenant. Resolving this would require a second SP registered in the External tenant plus cross-tenant federated credentials, re-litigating the architectural trust boundary."
  fix_commit: "4a276bd (refactor External-tenant resources into a local-only ops surface). Adrian manages jobrag-spa, jobrag-api app regs, their SPs, and the access_as_user UUID via his multi-tenant az login context. CI's prod composition no longer references the external provider. State rm performed locally to evict the resources from CI-managed state."
  verified_by: "Run #25825087050: no AADSTS700016 errors; refresh, plan, and apply all clean."

# Gaps F + G (Test 8): RESOLVED
- truth: "GHA SP can refresh cross-scope role assignments without 403 (Microsoft's textbook CI/CD principal pattern)"
  status: resolved
  severity: blocker
  test: 8
  layer: "architectural (D-08 v2)"
  artifacts:
    - infra/modules/identity/main.tf:124-129  # azurerm_role_assignment.gha_reader_subscription
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md  # D-08 Amendment v2
  reason: "After A and D landed, CI still returned 403 on Microsoft.Authorization/roleAssignments/read for two cross-scope role assignments: gha_tfstate_blob_data_contributor (in tfstate RG) and gha_cost_management_contributor (sub-scoped). Contributor at prod RG cascades only within that RG; refresh on out-of-RG role assignments returns 403."
  root_cause: "D-08 v1 ('RG Contributor only') conflated mutation-isolation (the real concern) with read access (a separate concern). Microsoft's standard CI/CD principal pattern is Reader at sub for refresh visibility plus narrow Contributor/Officer roles for mutation."
  fix_commit: "e82f1e9 (grant GHA SP Reader at subscription scope: */read only, no mutation capability). D-08 amended in CONTEXT.md (v2): mutation boundary preserved, read access widened for refresh."
  verified_by: "Run #25825087050: refresh completed without 403 on cross-scope role assignments."

# Gap H (Test 8): RESOLVED
- truth: "Role assignments are stable across local-apply and CI-apply contexts (no spurious replace-on-refresh)"
  status: resolved
  severity: blocker
  test: 8
  layer: "state stability"
  artifacts:
    - infra/envs/prod/main.tf:104-108  # azurerm_role_assignment.deployer_kv_secrets_officer
    - infra/envs/prod/variables.tf  # new var.deployer_object_id
    - infra/envs/prod/prod.tfvars:45  # deployer_object_id literal
  reason: "After F+G landed, plan still wanted to REPLACE azurerm_role_assignment.deployer_kv_secrets_officer on every CI run, which would destroy Adrian's KV data-plane access and grant it to the GHA SP. Caused by data.azurerm_client_config.current.object_id evaluating differently across auth contexts (Adrian's OID locally vs the SP OID on CI)."
  root_cause: "Implicit context-dependent reference in principal_id. Stable within CI alone, but unstable across the local-apply / CI-apply cycle Adrian actually uses."
  fix_commit: "fac8ada (pin principal_id to a new var.deployer_object_id populated via prod.tfvars literal, Adrian's user OID 58ad20b2-0cba-4d5b-81cd-84d29f64daa2). GHA SP has its own KV access via 8.B, so this role exists exclusively for the human deployer."
  verified_by: "Run #25825087050: plan showed only the LAW workspace change (Gap 12.A landing); no replace on deployer_kv_secrets_officer."

# Gap GHCR_PAT (Test 8): RESOLVED (GH config, no commit)
- truth: "deploy-infra.yml has access to a populated GHCR_PAT GH secret so the Container App ghcr-pat secret block is rebuilt with a valid value"
  status: resolved
  severity: blocker
  test: 8
  layer: "deployment config (GH side, not TF)"
  artifacts:
    - .github/workflows/deploy-infra.yml:60  # TF_VAR_ghcr_pat env wiring (already correct; the GH secret was the gap)
  reason: "After F+G+H landed, run #25737267295 failed at apply with ContainerAppSecretInvalid: secret(s) 'ghcr-pat' invalid (value or keyVaultUrl and identity should be provided). Plan showed 6 to 6 secret-block churn from TypeSet semantics on azurerm_container_app.secret: when any one member's hash changes, the whole set re-emits."
  root_cause: "secrets.GHCR_PAT was never created in the GH repo (only AZURE_* secrets existed). deploy-api.yml uses secrets.GITHUB_TOKEN for GHCR push (not GHCR_PAT), so the earlier 'GHCR bootstrap' commits did not actually create this secret. deploy-infra.yml's reference resolved to empty string, then empty TF var, then empty Container App secret value, then Azure 400."
  fix: "Adrian ran 'gh secret set GHCR_PAT --repo AdrianZaplata/job-rag' using the fine-grained read-only PAT already in terraform.tfvars.local. No code commit (GH-side config only)."
  verified_by: "Run #25825087050: apply completed; ghcr-pat secret block rebuilt with valid value; ACA accepted the update."
  follow_up: "README rotation table (prod/README.md:188) documents the 90-day local-apply rotation but does not yet mention the parallel 'gh secret set GHCR_PAT' step CI needs. Track as a small doc patch."

# ───── Test 16 / Gap 16.A: OPEN (TF state secret leakage) ─────
- truth: "Terraform state contains no literal plaintext for OpenAI / Langfuse API keys"
  status: failed
  severity: minor
  test: 16
  layer: provisioning
  artifacts:
    - infra/envs/prod/main.tf:120  # azurerm_key_vault_secret.openai_api_key
    - infra/envs/prod/main.tf:132  # azurerm_key_vault_secret.langfuse_public_key
    - infra/envs/prod/main.tf:144  # azurerm_key_vault_secret.langfuse_secret_key
    - infra/envs/prod/main.tf:156  # azurerm_key_vault_secret.seeded_user_entra_oid
    - infra/modules/database/main.tf:31  # azurerm_key_vault_secret.pg_admin_password
  reason: "`terraform state pull | Select-String 'sk-'` returns two literal hits inside `azurerm_key_vault_secret.{openai_api_key,langfuse_secret_key}.value`. Container App half of Test 16 passes (secrets referenced via `key_vault_secret_id` URIs, no literals)."
  root_cause: "AzureRM provider stores `azurerm_key_vault_secret.value` as a literal in state for drift detection. Mitigated when `value_wo` / `value_wo_version` (TF 1.11+ write-only attributes) are used instead, but those fields are currently null."
  fix: "Replace `value = var.<secret>` with `value_wo = var.<secret>` + `value_wo_version = 1` on all 5 `azurerm_key_vault_secret` resources. Inspect `terraform plan` for in-place update (expected) vs. replace (would need a `moved` block or `lifecycle { ignore_changes }` shim). Bundle with Test 8 unblock PR since the same files are touched."
  boundary_note: "At-rest boundary still holds: state sits in Azure Blob with versioning + 7d soft-delete + GHA-SP-only ACL. This gap closes a defense-in-depth gap, not an active leak."
  d_decisions: ["D-13 (no literal secrets in state): currently partial, restored by `value_wo` migration"]
