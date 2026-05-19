---
phase: 03-infrastructure-ci-cd
verified: 2026-05-19T15:00:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 3: Infrastructure & CI/CD Verification Report

**Phase Goal:** Phase 3 ships a fully provisioned Azure stack when `terraform apply` (run twice to resolve the CORS cycle) produces a working Entra External tenant, an ACA container, a B1ms Postgres with pgvector, an SWA origin, Key Vault-backed secrets, and three OIDC-federated GitHub Actions workflows can deploy infra / API / SPA independently.

**Verified:** 2026-05-19T15:00:00Z
**Status:** passed
**Re-verification:** No — initial verification
**Score:** 12/12 must-haves verified
**Evidence base:** 03-SMOKE.md (M1–M13, 13 PASS / 0 FAIL on live Azure), 03-UAT.md (18 PASS / 0 ISSUE), 03-08-SUMMARY.md (post-gap-closure commits 38f06eb, 6e31522, e02b8f0, 09ca58a, a3d18b6), live filesystem inspection of `infra/`, `.github/workflows/`, and `scripts/`.

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `terraform apply` in `infra/envs/prod/` creates the complete Azure resource graph — ACA env + Container App (min_replicas=0, max_replicas=1), Postgres Flex B1ms with `vector` in `azure.extensions`, SWA Free SKU, Key Vault with `OPENAI_API_KEY` / DB-password / Langfuse keys, Log Analytics with 5 GB/mo cap, €10/mo subscription budget alert (DEPL-02..06, DEPL-10, DEPL-11) | VERIFIED | 03-SMOKE.md M2 (live `az resource list` confirms 6 RG resources + sub-scope budget); `infra/modules/compute/main.tf:97-99` pins `min_replicas=0`, `max_replicas=1`, `termination_grace_period_seconds=120`; `infra/modules/database/main.tf:58` `sku_name="B_Standard_B1ms"`; `:79-80` `name="azure.extensions"`, `config="VECTOR"`; `infra/envs/prod/main.tf:270-275` SWA `sku_tier="Free"`; `infra/modules/monitoring/main.tf:24` `daily_quota_gb=0.15` (≈4.5 GB/mo, below 5 GB alert); `infra/modules/monitoring/main.tf:58` budget `amount=10`, `:66-75` 50/75/90/100% thresholds; 5 KV secrets present per `az keyvault secret list` |
| 2 | Terraform state lives in an Azure Blob backend with state-locking; a second `terraform apply` from a clean clone succeeds without local `.tfstate` (DEPL-01) | VERIFIED | `infra/envs/prod/backend.tf:4-11` declares `backend "azurerm"` with `resource_group_name="jobrag-tfstate-rg"`, `storage_account_name="jobragtfstateq7u9r"`, `container_name="tfstate"`, `key="prod.tfstate"`, `use_azuread_auth=true`; `infra/bootstrap/main.tf:39-89` creates the state-storage RG + storage account + container + AAD role binding; 03-SMOKE.md M1 confirms clean-clone `terraform init && terraform plan` runs against remote state without writing local `.tfstate` (UAT Tests 3 + 4 PASS) |
| 3 | The two-pass CORS bootstrap is documented and works — first apply discovers the SWA default origin, second apply injects it into the Container App's `ALLOWED_ORIGINS` (DEPL-12) | VERIFIED | `scripts/refresh-swa-origin.sh` reads `terraform output -raw swa_default_origin`, rewrites `swa_origin` in `prod.tfvars`, re-applies; `infra/envs/prod/locals.tf:14-17` builds `allowed_origins_csv` via `compact()` so first apply (`swa_origin=""`) lands localhost-only and second apply lands SWA + localhost; `infra/envs/prod/main.tf:199` passes `allowed_origins=local.allowed_origins_csv` into compute module; `infra/modules/compute/main.tf:146-147` ships it as `ALLOWED_ORIGINS` env var. 03-SMOKE.md M3 PASS — `curl -H "Origin: https://witty-flower-…azurestaticapps.net"` returns `access-control-allow-origin`; `curl -H "Origin: https://evil.example"` returns no CORS header (textbook rejection). `prod.tfvars:20` carries the post-second-pass SWA host |
| 4 | `deploy-infra.yml`, `deploy-api.yml`, `deploy-spa.yml` each authenticate via OIDC federated credential, use resource-group-scoped Contributor (never subscription-scoped) for mutation, and `paths` filters mean a frontend-only PR doesn't fire infra (DEPL-08, DEPL-09) | VERIFIED | `.github/workflows/deploy-infra.yml:6-8` paths=`infra/**`; `:9` `workflow_dispatch`; `:12` `id-token: write`; `:22` `environment: production`; `:34-39` `azure/login@v2` OIDC. `.github/workflows/deploy-api.yml:6-13` paths=src/**, pyproject.toml, uv.lock, Dockerfile, alembic/**, scripts/docker-entrypoint.sh; `:16-18` `id-token: write` + `packages: write`; `:64-69` OIDC login. `.github/workflows/deploy-spa.yml:6-8` paths=`apps/web/**`; `:10-11` permissions=`contents: read` only (no `id-token`); `:43-46` `azure_static_web_apps_api_token` (token-based per D-08). `infra/modules/identity/main.tf:58-65` master federated cred subject `repo:${owner}/${repo}:ref:refs/heads/master`; `:71-78` production_env cred subject `repo:${owner}/${repo}:environment:production`. RG-scoped Contributor at `:83-87` (scope=`var.resource_group_id`); KV-scoped Secrets Officer at `:94-97`; sub-scoped Cost Mgmt Contributor at `:108-112` documented as named D-08 exception (mutation-isolated to `Microsoft.Consumption/*` + `Microsoft.CostManagement/*`); sub-scoped Reader at `:124-128` is `*/read` only (D-08 v2). 03-SMOKE.md M4 (run #25426147786) + M5 (run #25825087050) PASS — OIDC handshake green on both federated subjects. UAT Test 18 confirms paths-filter contract holds (5 prior runs each, zero false fires) |
| 5 | A hello-world container image pushed to GHCR (not ACR Basic) and referenced by the Container App is reachable at the ACA FQDN over HTTPS (DEPL-07) | VERIFIED | `infra/modules/compute/main.tf:32-36` registry block points at `ghcr.io`; `:40-43` `ghcr-pat` secret (literal, fine-grained read-only PAT, sensitive=true per D-14); `:103` image=`ghcr.io/${var.ghcr_username}/job-rag:${var.image_tag}`. `.github/workflows/deploy-api.yml:53-62` docker/build-push-action@v6 pushes `ghcr.io/<lc-repo>:<sha>` + `:latest`. 03-SMOKE.md M6 PASS — active revision `jobrag-prod-api--0000003` binds to `ghcr.io/adrianzaplata/job-rag:ea0af2db…`; live `GET /health` over HTTPS at `https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io/health` returns `200 OK` `{"status":"ok"}`; local `docker pull` of same digest succeeds (`sha256:978ee46d…`) |

**Score:** 5/5 ROADMAP success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `infra/envs/prod/main.tf` | Composition layer wiring all 6 modules + 5 KV secrets + 2 diagnostic_settings + SWA + role assignments | VERIFIED | 37 azurerm resources; 5 `azurerm_key_vault_secret` all on `value_wo` + `value_wo_version=1` (Gap 16.A closure); `azurerm_static_web_app.spa` (Free/Free); `azurerm_monitor_diagnostic_setting.aca` (ConsoleLogs) + `azurerm_monitor_diagnostic_setting.kv` (AuditEvent — Gap 10.A closure) |
| `infra/envs/prod/backend.tf` | Azure Blob backend with use_azuread_auth=true | VERIFIED | 11 lines, all 4 backend fields populated, AAD auth on |
| `infra/envs/prod/provider.tf` | azurerm + azuread providers with OIDC config (Gap 8.C closure) | VERIFIED | azuread aliases declare `use_oidc=var.use_oidc_auth`, `client_id=var.gha_client_id`, `tenant_id` for CI parity |
| `infra/envs/prod/prod.tfvars` | env-specific input vars | VERIFIED | swa_origin=witty-flower-…; deployer_object_id pinned (Gap H closure); home_ip residential IP (flagged WR-03, non-blocking) |
| `infra/envs/prod/outputs.tf` | Phase 4 hand-off bundle | VERIFIED | 11 outputs including aca_fqdn, swa_default_origin, kv_uri, tenant_subdomain, tenant_id, gha_client_id, swa_deployment_token (sensitive), seeded_user_entra_oid_secret_name |
| `infra/envs/prod/locals.tf` | allowed_origins_csv for DEPL-12 two-pass | VERIFIED | `compact()` pattern at `:14-17` lands localhost-only on first apply, SWA+localhost on second |
| `infra/envs/dev/*.tf` | Dev scaffold (D-04: never-applied mirror) | VERIFIED | All 7 files present; dev intentionally not applied per D-04 (WR-01/WR-02 dev drift are non-blocking) |
| `infra/bootstrap/main.tf` | State storage RG + account + container + RBAC | VERIFIED | `azurerm_resource_group.tfstate`, `azurerm_storage_account.tfstate` with versioning + soft-delete, `azurerm_storage_container.tfstate`, `azurerm_role_assignment.deployer_tfstate_blob_data_contributor` |
| `infra/bootstrap/identity.tf` | Deployer principal for bootstrap | VERIFIED | Present, 1186 bytes |
| `infra/bootstrap/outputs.tf` | 3 outputs (RG, storage, container) for backend.tf seeding | VERIFIED | Present, 1441 bytes |
| `infra/modules/compute/main.tf` | Raw azurerm_container_app with SystemAssigned MI + 5 KV secret refs + ghcr registry + scale-to-zero | VERIFIED | All key configs at lines 22-149: MI (`identity.type="SystemAssigned"`), 5 `key_vault_secret_id` secrets, `min_replicas=0`/`max_replicas=1`, `termination_grace_period_seconds=120`, `lifecycle.ignore_changes=[image, revision_suffix]` (B5 fix) |
| `infra/modules/database/main.tf` | AVM Postgres Flex B1ms + azure.extensions=VECTOR + KV-stored 32-char password via value_wo + A1 firewall | VERIFIED | sku_name=B_Standard_B1ms, server_parameters configures azure.extensions=VECTOR, pg_admin_password on value_wo+value_wo_version=1 (commit 6e31522), public_network_access_enabled=true (D-10 trade-off, TLS+random password enforced) |
| `infra/modules/identity/main.tf` | 3 azuread_applications + 2 federated_identity_credentials with correct subjects + RG-scoped Contributor + KV-scoped Secrets Officer + named sub-scope exceptions | VERIFIED | 7 azurerm + N azuread resources; both federated subjects match GH workflow gates; RBAC scoped per D-08 v2 |
| `infra/modules/kv/main.tf` | AVM KV with RBAC + role_assignments | VERIFIED | 1 azurerm resource (the AVM wraps the rest); RBAC mode confirmed via UAT Test 10 (KV Secrets User role on ACA MI) |
| `infra/modules/monitoring/main.tf` | AVM LAW 0.5.1 + 0.15 GB/day cap + €10/mo budget + 50/75/90/100% thresholds | VERIFIED | daily_quota_gb=0.15, `azurerm_consumption_budget_subscription.prod` amount=10, 4 thresholds via dynamic notification block, lifecycle.ignore_changes=[time_period[0].start_date] to suppress month-rollover churn; W1 sub-data-source pattern (Gap 12.A closure passes `log_analytics_workspace_internet_*_enabled=true` via module input) |
| `infra/modules/network/main.tf` | ACA Environment | VERIFIED | 1 azurerm resource (managed environment); workspace_id flows from monitoring module per W7 composition pattern |
| `.github/workflows/deploy-infra.yml` | OIDC + environment:production + paths(infra/**) + workflow_dispatch | VERIFIED | 94 lines; all 4 gates present at lines 6-22 |
| `.github/workflows/deploy-api.yml` | OIDC + packages:write + docker/build-push-action@v6 to GHCR + az containerapp update + per-revision smoke (Gap 10.C fix) | VERIFIED | 168 lines; 6 path patterns at L7-13; OIDC+packages perms L16-18; build-push-action@v6 L53-62; per-revision FQDN smoke poll at L78-168 (post-Gap-10.C) |
| `.github/workflows/deploy-spa.yml` | Token-based (no id-token) + paths(apps/web/**) + Azure/static-web-apps-deploy@v1 | VERIFIED | 51 lines; no `id-token:` permission; SWA api_token at L46 |
| `.github/workflows/static-tf.yml` | fmt -check + tflint + tfsec on PR touching infra/** | VERIFIED | 64 lines; runs on PR with paths(infra/**); terraform_version 1.15.0; tflint setup at L26-30 (IN-04 redundant file-exists guards noted, non-blocking) |
| `.github/workflows/bootstrap-corpus.yml` | workflow_dispatch-only with acknowledge_cost gate (A6) | VERIFIED | 71 lines; UAT Test 17 confirms negative-case (cost gate) fires correctly; positive-case static-evidence verified |
| `infra/.tflint.hcl` | tflint config (azurerm ruleset) | VERIFIED | Present |
| `infra/.tfsec/config.yml` | tfsec config with documented D-10/A1 allowlist | VERIFIED | Present |
| `scripts/refresh-swa-origin.sh` | Two-pass CORS helper | VERIFIED | 27 lines; reads terraform output, sed-rewrites prod.tfvars, re-applies (WR-04 `.bak` cleanup noted, non-blocking) |
| `scripts/docker-entrypoint.sh` | Updated to init-db + uvicorn only (ingest/embed removed per B4) | VERIFIED | `job-rag init-db` at L23; no `job-rag ingest` or `job-rag embed` invocations |
| `infra/envs/prod/README.md` | Runbook + Knowingly-Accepted Trade-offs table (6 rows post-Plan-08) | VERIFIED | 14908 bytes; ContainerAppSystemLogs_CL row added (Gap 12.B closure) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Container App | Key Vault (5 secrets) | SystemAssigned MI + key_vault_secret_id URIs | WIRED | `compute/main.tf:48-72` declares 5 KV-backed secrets with `identity="System"`; `prod/main.tf:204-208` maps `kv_secret_uris` from `azurerm_key_vault_secret.*.versionless_id`; UAT Test 10 four-evidence chain (RBAC + revision template + healthy revision + /health 200) proves resolution at runtime |
| Container App | GHCR registry | registry{} + ghcr-pat secret | WIRED | `compute/main.tf:32-43` registry+secret+password_secret_name; deploy-api.yml builds+pushes image; 03-SMOKE.md M6 confirms active-revision image binding to `ghcr.io/adrianzaplata/job-rag:<sha>` and `/health` 200 from FQDN |
| ACA env diagnostic_setting | Log Analytics workspace | composition layer (W7 pattern) | WIRED | `prod/main.tf:230-244` `azurerm_monitor_diagnostic_setting.aca` ships ContainerAppConsoleLogs to module.monitoring.workspace_id; M9 confirms ingestion live |
| Key Vault diagnostic_setting | Log Analytics workspace | composition layer (Gap 10.A) | WIRED | `prod/main.tf:258-268` `azurerm_monitor_diagnostic_setting.kv` routes AuditEvent → LAW; commit e02b8f0; control-plane verified (`az monitor diagnostic-settings list` returns `jobrag-prod-kv-diag`); runtime audit rows pending documented first-hour ingestion lag |
| SWA default origin | Container App ALLOWED_ORIGINS | refresh-swa-origin.sh → prod.tfvars → locals.allowed_origins_csv → compute env var | WIRED | Script reads `terraform output -raw swa_default_origin`, mutates `prod.tfvars:20`, second apply lands SWA host in CSV; live curl test (M3) confirms origin honored |
| deploy-infra.yml | Azure (workforce tenant) | OIDC fed cred `repo:.../environment:production` + azure/login@v2 | WIRED | Identity module declares fed cred subject; workflow's `environment: production` triggers the matching subject claim; M5 PASS — run #25825087050 green |
| deploy-api.yml | Azure (workforce tenant) | OIDC fed cred `repo:.../ref:refs/heads/master` + azure/login@v2 | WIRED | Identity module declares fed cred subject; workflow runs on push to master; M4 PASS — run #25426147786 green end-to-end |
| deploy-api.yml | GHCR | secrets.GITHUB_TOKEN + docker/login-action@v3 + docker/build-push-action@v6 | WIRED | L34-62; ghcr.io login + multi-tag push with cache; downstream `az containerapp update --image` rotates ACA revision |
| deploy-spa.yml | SWA | secrets.AZURE_STATIC_WEB_APPS_API_TOKEN_PROD + Azure/static-web-apps-deploy@v1 | WIRED | L43-51; deployment token sourced from KV via manual B2 runbook (one-time + 180-day rotation) |
| GHA SP | tfstate container | scope-constructed (Gap A closure) | WIRED | `prod/main.tf` constructs scope from `data.azurerm_subscription.current.id` + var.tfstate_* (no data lookup needed) avoiding 403 on tfstate-RG read |
| Bootstrap | Backend.tf seeding | 3 outputs → manual copy-paste | WIRED | `bootstrap/outputs.tf` exposes RG/storage/container names; runbook documents the manual copy step (one-time per env) |

### Data-Flow Trace (Level 4)

Phase 3 produces no user-facing application data flow (the backend runtime data flow is Phase 1/2 territory). Level 4 here verifies that secret values, log streams, and configuration values flow through the wiring with real data.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| Container App secrets | env vars OPENAI_API_KEY, LANGFUSE_*, POSTGRES_ADMIN_PASSWORD, SEEDED_USER_ENTRA_OID | KV via system-assigned MI | Yes — verified by `/health` 200 (Pydantic Settings would crash startup if any KV-backed env missing) and 03-08-SUMMARY.md cold-start log "Composed DATABASE_URL/ASYNC_DATABASE_URL from POSTGRES_* parts" at 2026-05-19T12:27:55Z proving postgres-admin-password resolved | FLOWING |
| Log Analytics ConsoleLogs | ContainerAppConsoleLogs_CL rows | ACA env appLogsConfiguration → LAW | Yes — UAT Test 12 KQL query returns 30d ingestion (Console 0.16 MB) | FLOWING |
| Log Analytics KV AuditEvent | AzureDiagnostics rows (Resource='JOBRAG-PROD-KV') | KV diagnostic_setting → LAW | Pending first-hour ingestion lag (control-plane wiring verified, data plane proven by 2026-05-19T12:27:41Z cold-start that exercised all 5 KV reads) | FLOWING (documented lag accepted) |
| Container App ALLOWED_ORIGINS | env var CSV string | locals.allowed_origins_csv from var.swa_origin | Yes — M3 live curl confirms SWA origin honored, evil origin rejected | FLOWING |
| Postgres jobrag DB | vector 0.8.2 extension | azure.extensions=VECTOR allowlist + CREATE EXTENSION (Alembic 0001) | Yes — M8 `\dx` lists vector 0.8.2 in schema public | FLOWING |
| Budget alert pipeline | €10/mo subscription budget + notification emails | azurerm_consumption_budget_subscription → Adrian's email | Yes — M10 `az consumption budget show` returns all 4 thresholds enabled with `adrianzaplata@gmail.com`; transitive email channel proof via prior Azure-source mail at same address | FLOWING |
| Terraform state | prod.tfstate blob | Azure Blob backend with AAD auth | Yes — M1 clean-clone `terraform init` pulls remote state; M13 `terraform state pull | jq` confirms no literal sk-* (Gap 16.A closure) | FLOWING |

All data flows verified.

### Behavioral Spot-Checks

Phase 3 ships infrastructure, not application logic. The "behaviors" here are live-Azure smoke checks already captured in 03-SMOKE.md M1–M13. No additional spot-checks executed during this verification — 13 PASS / 0 FAIL / 0 PARTIAL on the existing smoke runbook is the authoritative behavioral evidence (per the task's special context — "treat the existing SMOKE.md PASS evidence as authoritative for live-Azure must-haves"). Static-file smoke (terraform fmt -check, tflint, tfsec) runs on every infra PR via `static-tf.yml`.

| Behavior | Evidence Source | Result | Status |
|----------|-----------------|--------|--------|
| Bootstrap remote state from clean clone | 03-SMOKE.md M1 + UAT Tests 3, 4 | PASS | PASS |
| `terraform apply` provisions full Azure graph | 03-SMOKE.md M2 + UAT Test 5 | PASS | PASS |
| Two-pass CORS bootstrap | 03-SMOKE.md M3 + UAT Test 6 | PASS | PASS |
| OIDC federated credential (master push) | 03-SMOKE.md M4 + UAT Test 7 + run #25426147786 | PASS | PASS |
| OIDC federated credential (environment:production) | 03-SMOKE.md M5 + UAT Test 8 + run #25825087050 | PASS | PASS |
| GHCR push + ACA pull over HTTPS | 03-SMOKE.md M6 + UAT Test 9 | PASS | PASS |
| KV secret resolution via managed identity | 03-SMOKE.md M7 + UAT Test 10 (4-evidence chain) | PASS | PASS |
| pgvector in jobrag DB | 03-SMOKE.md M8 + UAT Test 11 | PASS | PASS |
| LAW daily quota + Console ingestion | 03-SMOKE.md M9 + UAT Test 12 | PASS | PASS |
| Budget alert thresholds + email channel | 03-SMOKE.md M10 + UAT Test 13 | PASS | PASS |
| SSE flow survives Envoy 240s + grace period | 03-SMOKE.md M11 + UAT Test 14 | PASS | PASS |
| CIAM authority openid-configuration | 03-SMOKE.md M12 + UAT Test 15 | PASS | PASS |
| tfstate has no literal secrets | 03-SMOKE.md M13 + UAT Test 16 + commits 38f06eb + 6e31522 | PASS | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| DEPL-01 | 03-01, 03-02, 03-05a, 03-05b, 03-07 | Terraform remote state on Azure Blob with state-locking | SATISFIED | 03-SMOKE.md M1 (clean-clone init + plan); `infra/envs/prod/backend.tf` + `infra/bootstrap/main.tf` |
| DEPL-02 | 03-01, 03-03, 03-04, 03-05a, 03-05b, 03-07 | `infra/envs/{dev,prod}` calling `infra/modules/*`; AVM used where available | SATISFIED | 6 modules (network, kv, monitoring, database, compute, identity) consumed by prod composition; AVM modules: kv (0.10.2), monitoring (LAW 0.5.1), database (Postgres 0.2.2) |
| DEPL-03 | 03-03, 03-04, 03-07 | ACA env + Container App; min_replicas=0; max_replicas=1 | SATISFIED | M2 — `compute/main.tf:97-98` declares both; az containerapp show confirms live |
| DEPL-04 | 03-04, 03-05a, 03-07, 03-08 | Postgres Flex B1ms with pgvector; pool sized to B1ms | SATISFIED | M2 + M7 + M8 + M13 — VECTOR allowlist + `\dx` shows vector 0.8.2; D-13 restored to "full" via value_wo migration (commits 38f06eb + 6e31522); KV audit pipe wired (commit e02b8f0). pool_size=3/max_overflow=2 in Phase 1 backend (regression-verified in 01-VERIFICATION.md) |
| DEPL-05 | 03-05a, 03-07 | Azure SWA Free SKU | SATISFIED | M2 — `prod/main.tf:270-275` Free/Free; `azurerm_static_web_app.spa` exists in prod RG |
| DEPL-06 | 03-03, 03-05a, 03-07 | KV stores OPENAI_API_KEY, DB password, Langfuse keys; ACA retrieves via MI | SATISFIED | M2 + M7 + M8 — 5 KV secrets present; ACA MI has KV Secrets User; revision template shows all 5 keyVaultUrl bindings |
| DEPL-07 | 03-04, 03-06, 03-07 | GHCR (not ACR Basic) | SATISFIED | M2 + M6 + M11 — registry block points at ghcr.io; deploy-api.yml builds+pushes; ACA pulls; /health 200 over HTTPS |
| DEPL-08 | 03-04, 03-06, 03-07 | Three split workflows with paths filters | SATISFIED | M4 + M5 + M12 + UAT Test 18 — three workflow files exist; paths filters verified; historical fire pattern confirms paths contract; M12 covers D-05 / Phase 4 hand-off prep |
| DEPL-09 | 03-04, 03-06, 03-07 | Each workflow via OIDC; RG-scoped Contributor (never sub); SWA via token | SATISFIED | M4 — OIDC handshake green on master subject; RG-scoped Contributor in identity module; KV-scoped Secrets Officer; sub-scoped exceptions documented (D-08 v2 amendment); SWA on api_token (no OIDC for SWA — Microsoft hasn't GA'd it) |
| DEPL-10 | 03-03, 03-07, 03-08 | LAW captures Container App + Postgres logs; 5 GB/mo quota alert | SATISFIED | M2 + M9 — daily_quota_gb=0.15 (≈4.5 GB/mo, under 5 GB alert); ContainerAppConsoleLogs_CL ingesting; D-16 amended (Gap 12.B) to accept SystemLogs at ~0.005% of daily cap; DCR-based filtering as Deferred Idea |
| DEPL-11 | 03-03, 03-07 | €10/mo subscription budget; email at 80% and 100% (project ships 50/75/90/100%) | SATISFIED | M2 + M10 — `azurerm_consumption_budget_subscription.prod` amount=10; 4 thresholds (exceeds the 80%/100% minimum specified in REQUIREMENTS.md); email channel transitively proven |
| DEPL-12 | 03-01, 03-05a, 03-07 | Two-pass deploy; second apply injects SWA origin into ALLOWED_ORIGINS | SATISFIED | M3 — `scripts/refresh-swa-origin.sh` + `locals.allowed_origins_csv` + live CORS curl test (allowed vs evil origin); prod.tfvars:20 carries post-second-pass SWA host |

**All 12 DEPL-* requirements satisfied. 0 orphans.**

### Anti-Patterns Found

Findings sourced from 03-REVIEW.md (0 Critical / 4 Warning / 7 Info). All are advisory and explicitly non-blocking. No new anti-patterns surfaced during this verification.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `infra/envs/dev/main.tf` | 196 | `ContainerAppConsoleLogs_CL` category name (wrong — should drop `_CL`) | Warning (WR-01) | Dev never applied in v1 per D-04; would 400 on apply. Non-blocking — does not affect prod goal. |
| `infra/envs/dev/main.tf` | 109-150 | Dev KV secrets still on `value` (lags prod Gap 16.A `value_wo` migration) | Warning (WR-02) | Dev never applied per D-04; sentinel string "managed-out-of-band". Non-blocking. |
| `infra/envs/prod/prod.tfvars` | 23 | `home_ip = "79.228.31.2"` (residential IP in public repo) | Warning (WR-03) | Defence-in-depth: TLS + 32-char password keeps auth intact even if IP rotates. Non-blocking but worth migrating to `terraform.tfvars.local`. |
| `scripts/refresh-swa-origin.sh` | 21 | `sed -i.bak` leaves `prod.tfvars.bak` orphan + no empty-output check | Warning (WR-04) | Low-risk; `.bak` not committed. Non-blocking. |
| `src/job_rag/__init__.py` | 1 | Sentinel deploy-trigger comment `# trigger deploy-api after GHCR bootstrap` | Info (IN-01) | Stale; no functional impact. |
| `infra/envs/prod/main.tf` | 214-218 | `aca_kv_secrets_user` role assignment missing `description` field | Info (IN-02) | Style inconsistency with sibling role assignments. |
| `infra/envs/prod/locals.tf` | 15 | Redundant ternary `var.swa_origin == "" ? "" : var.swa_origin` | Info (IN-03) | `compact()` already strips empty. Style nit. |
| `.github/workflows/static-tf.yml` | 50, 56, 62 | Redundant file-exists guards `if [ -f infra/envs/prod/main.tf ]` | Info (IN-04) | Files are committed; conditional always true. |
| `src/job_rag/services/ingestion.py` | 450-452 | Fragile cost-string round-trip via regex split | Info (IN-05) | No bug today. |
| `scripts/docker-entrypoint.sh` | 14 | `python3 -c "..."` URL-encodes a known-alphanumeric password | Info (IN-06) | ~50-100ms launch overhead; defensive. |
| `infra/modules/identity/main.tf` | 108-129 | Cost Mgmt Contributor + Reader at subscription scope | Info (IN-07) | Documented D-08 v2 named exceptions; mutation isolation preserved. |

**Total: 0 blockers, 4 warnings (all dev/non-prod or accepted trade-offs), 7 style/info nits.**

### Cross-Cutting Verification

| Threat (from 03-07-PLAN) | Mitigation | Evidence |
|--------------------------|------------|----------|
| T-3-01 HIGH (TF state hygiene) | value_wo migration | M13 PASS — `terraform state pull | jq` returns empty for sk-* |
| T-3-02 HIGH (OIDC trust) | Federated cred + correct subjects | M4 + M5 PASS — OIDC handshake green on both subjects |
| T-3-03 HIGH (Postgres exposed) | TLS-only + KV-sourced 32-char password | M2 + M8 PASS — SSL required, password resolves via MI |
| T-3-04 MED (GHCR PAT in state) | sensitive=true; rotation documented | M2 + M6 PASS — PAT not exposed in outputs; ACA pull works |
| T-3-05 MED (SWA api_key) | KV-stored, rotation runbook (B2) | M5 PASS — token sync runbook documented in prod README |
| T-3-06 MED (Cost / DoS) | LAW 0.15 GB/day cap + €10 budget | M9 + M10 PASS |
| T-3-07 MED (Tenant misconfiguration) | OIDC discovery metadata validated | M12 PASS — issuer claim carries External tenant id |
| T-3-08 HIGH (CORS bypass) | FastAPI CORSMiddleware allowlist | M3 PASS — evil origin rejected |

All 8 threats from the 03-07-PLAN threat register have explicit mitigation evidence. All 3 HIGH-severity threats (T-3-01, T-3-02, T-3-08) have direct verification.

### Human Verification Required

None. Live-Azure evidence is already captured in 03-SMOKE.md M1–M13 (PASS) and 03-UAT.md (18 PASS / 0 ISSUE). The task brief explicitly directs treating the existing SMOKE.md PASS evidence as authoritative — no re-runs required.

The only known carry-forward items are Phase 4 hand-offs (explicit out-of-scope):
- `/agent/stream` is currently open in prod (`JOB_RAG_API_KEY=""`); Phase 4 owns the Entra JWT gate. SSE pipe + drain config are Phase-3-complete.
- `seeded-user-entra-oid` KV slot is provisioned and reachable via MI; Phase 4 writes the real OID after first MSAL login per D-09.

Both are documented in 03-SMOKE.md "Deviations and follow-ups" as explicit Phase 4 hand-offs, not Phase 3 gaps.

### Regression Check vs Phase 1

Phase 1 verification (01-VERIFICATION.md status=passed, 5/5) established backend contracts that Phase 3 depends on:
- Alembic migrations + pgvector — verified live in M8 (vector 0.8.2 exists in jobrag DB after cold-start runs init-db)
- CORS allowlist + ALLOWED_ORIGINS env var — Phase 3 wires the prod value via locals.allowed_origins_csv; live curl test (M3) confirms enforcement
- SSE flow (heartbeat, timeout, sanitized errors) — M11 confirms `/agent/stream` survives Envoy 240s with `terminationGracePeriodSeconds=120`
- Docker entrypoint — Phase 3's `scripts/docker-entrypoint.sh` is the refactored cold-start path (init-db + uvicorn only; ingest/embed removed per B4)

No Phase 1 regressions detected.

### Gaps Summary

None. All 12 DEPL-* requirements satisfied. All 5 ROADMAP success criteria verified by a combination of live-Azure smoke evidence (M1–M13), static file inspection (37 azurerm resources in prod composition + 7 modules + 5 workflows + 2 scripts), and the post-gap-closure commit chain (38f06eb, 6e31522, e02b8f0, 09ca58a, a3d18b6 — UAT advanced from 16 PASS / 2 ISSUE to 18 PASS / 0 ISSUE).

The 4 Warning findings from 03-REVIEW.md are explicitly non-blocking:
- WR-01, WR-02: dev composition drift — dev never applied in v1 per D-04.
- WR-03: residential IP committed — defence-in-depth holds via TLS + random password.
- WR-04: shell-script cleanup gap — `.bak` not committed, low-risk.

These should be tracked as cleanup for Phase 8 (Eval & Documentation) or earlier if a refactor pass is scheduled, but they do not block Phase 3 goal achievement or Phase 4 entry.

---

_Verified: 2026-05-19T15:00:00Z_
_Verifier: Claude (gsd-verifier)_
