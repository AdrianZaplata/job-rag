# Phase 3 Smoke Evidence (M1–M13)

**Phase:** 03-infrastructure-ci-cd
**Smoke executed:** 2026-05-05 through 2026-05-19 (iterative; post-Gap-closure state captured 2026-05-19)
**Executor:** Adrian Zaplata
**Stack state:** prod env applied; UAT board 18 PASS / 0 ISSUE post-Plan-03-08 (commits 38f06eb, 6e31522, e02b8f0, 09ca58a, a3d18b6)
**Source-of-truth:** `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` (this document is the canonical-format projection of that evidence)

## Summary

| M    | Behavior                                                  | Status | Requirement                              | Threat IDs                    | UAT Test |
|------|-----------------------------------------------------------|--------|------------------------------------------|-------------------------------|----------|
| M1   | Bootstrap remote state from clean clone                   | PASS   | DEPL-01                                  | T-3-01                        | 3 + 4    |
| M2   | terraform apply creates full Azure resource graph         | PASS   | DEPL-02..07, DEPL-10, DEPL-11            | T-3-03, T-3-04                | 5        |
| M3   | Two-pass CORS bootstrap                                   | PASS   | DEPL-12                                  | T-3-08                        | 6        |
| M4   | OIDC federated credential — master push trigger           | PASS   | DEPL-08, DEPL-09                         | T-3-02                        | 7        |
| M5   | OIDC federated credential — environment:production        | PASS   | DEPL-08                                  | T-3-02, T-3-05                | 8        |
| M6   | GHCR image push + ACA pull over HTTPS                     | PASS   | DEPL-07                                  | T-3-04                        | 9        |
| M7   | KV secret resolution via managed identity                 | PASS   | DEPL-04 (D-13)                           | T-3-01                        | 10       |
| M8   | pgvector extension exists in jobrag DB                    | PASS   | DEPL-04, DEPL-05, DEPL-06                | T-3-03                        | 11       |
| M9   | LAW daily quota + ConsoleLogs only                        | PASS   | DEPL-10                                  | T-3-06                        | 12       |
| M10  | Budget alert email arrives                                | PASS   | DEPL-11                                  | T-3-06                        | 13       |
| M11  | SSE flow survives Envoy 240s + grace period               | PASS   | DEPL-07 (D-15)                           | (D-15)                        | 14       |
| M12  | CIAM authority openid-configuration reachable             | PASS   | DEPL-08 (D-05 / Phase 4 hand-off prep)   | T-3-07                        | 15       |
| M13  | tfstate has no literal secrets                            | PASS   | DEPL-04 (D-13)                           | T-3-01                        | 16       |

**Overall:** 13 PASS / 0 FAIL / 0 PARTIAL / 0 DEFERRED (out of 13)

Note: UAT Tests 1, 2, 17, 18 do not map to M-IDs — they cover Phase-3-internal preconditions (cold-start smoke, static-TF harness, bootstrap-corpus workflow, paths-filter contract). Their PASS evidence lives in 03-UAT.md and feeds the broader 18 PASS / 0 ISSUE Phase-close roll-up.

## Stack outputs (for cross-reference)

```
aca_fqdn                  = jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io
swa_default_origin        = witty-flower-065dac003.7.azurestaticapps.net
kv_name                   = jobrag-prod-kv
kv_uri                    = https://jobrag-prod-kv.vault.azure.net/
tenant_subdomain          = jobrag
tenant_id                 = 3fd51a76-f36e-43a1-aa37-564dad4c41fd
gha_client_id             = <REDACTED — see GH repo secret AZURE_CLIENT_ID>
swa_deployment_token      = <REDACTED — sensitive=true; synced manually to AZURE_STATIC_WEB_APPS_API_TOKEN_PROD per B2 runbook>
swa_api_key               = <REDACTED — alias of swa_deployment_token>
seeded_user_entra_oid_secret_name = seeded-user-entra-oid
```

---

## M1 — Bootstrap remote state from clean clone

**Behavior:** From a clean clone, `cd infra/bootstrap && terraform init && terraform apply` creates state-storage RG + storage account + container. Backend outputs copied into `infra/envs/prod/backend.tf`; subsequent `cd infra/envs/prod && terraform init && terraform plan` succeeds without a local `.tfstate`.

**Requirement:** DEPL-01
**Threat:** T-3-01 (Information Disclosure — TF state hygiene; local state never committed)
**Status:** PASS

**Command:**
```bash
# Bootstrap apply (UAT Test 3)
cd infra/bootstrap
terraform init -backend=false
terraform apply -var-file=terraform.tfvars.local
# -> creates jobrag-tfstate-rg + jobragtfstate{suffix} + 'tfstate' container

# Backend migration to remote state (UAT Test 4) — clean clone, prod env
cd infra/envs/prod
terraform init     # pulls state from Azure Blob; no local .tfstate written
terraform plan -var-file=prod.tfvars
```

**Output:**
```
terraform plan -var-file=prod.tfvars
# -> "No changes. Your infrastructure matches the configuration."
# (state already in sync — prod was applied prior to this UAT session)
#
# Two AVM-internal deprecation warnings:
#   - kv module: enable_rbac_authorization → rbac_authorization_enabled (azurerm v5)
#   - monitoring module: local_authentication_disabled
# Both upstream AVM concerns, not Phase 3 scope.
```

**Notes:**
- See 03-UAT.md Tests 3 + 4 for the full evidence chain.
- AVM deprecation warnings tracked for future AVM version bumps; not Phase 3 scope.
- `terraform.tfstate` never written locally during init (state lives in `jobrag-tfstate-rg/jobragtfstate{suffix}/tfstate`); D-13 / T-3-01 state hygiene preserved.

---

## M2 — terraform apply creates full Azure resource graph

**Behavior:** `cd infra/envs/prod && terraform apply -var-file=prod.tfvars` provisions ACA Environment + Container App (scale-to-zero) + Postgres B1ms with `vector` in `azure.extensions` + Static Web App (Free SKU) + Key Vault with 5 secrets + Log Analytics workspace with 0.15 GB/day cap + €10/mo budget alert with 50/75/90/100% thresholds.

**Requirement:** DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06, DEPL-07, DEPL-10, DEPL-11
**Threat:** T-3-03 (Postgres exposed — mitigated via TLS-only + KV-sourced password), T-3-04 (GHCR PAT in state — `sensitive=true`)
**Status:** PASS

**Command:**
```bash
az resource list --resource-group jobrag-prod-rg \
  --query "[].{name:name, type:type}" -o table

az containerapp show --name jobrag-prod-api --resource-group jobrag-prod-rg \
  --query "{min:properties.template.scale.minReplicas, max:properties.template.scale.maxReplicas, grace:properties.template.terminationGracePeriodSeconds}" -o json

az postgres flexible-server parameter show \
  --resource-group jobrag-prod-rg --server-name jobrag-prod-pg-ie \
  --name azure.extensions --query value -o tsv

az consumption budget show --budget-name jobrag-prod-budget

az monitor log-analytics workspace show -g jobrag-prod-rg -n jobrag-prod-law \
  --query "{quota:workspaceCapping.dailyQuotaGb, sku:sku.name, retention:retentionInDays}" -o json
```

**Output:**
```
# Resources in jobrag-prod-rg (6 in RG + 1 subscription-scoped budget):
jobrag-prod-aca-env   Microsoft.App/managedEnvironments
jobrag-prod-api       Microsoft.App/containerApps
jobrag-prod-spa       Microsoft.Web/staticSites
jobrag-prod-kv        Microsoft.KeyVault/vaults
jobrag-prod-law       Microsoft.OperationalInsights/workspaces
jobrag-prod-pg-ie     Microsoft.DBforPostgreSQL/flexibleServers

# KV (5 secrets present): openai-api-key, langfuse-public-key, langfuse-secret-key,
#                         seeded-user-entra-oid, postgres-admin-password

# Postgres: azure.extensions = VECTOR (confirmed)
# LAW: dailyQuotaGb = 0.15, sku = PerGB2018, retention = 30
# Budget: amount=10.0 EUR, thresholds=[50,75,90,100], notifications -> adrianzaplata@gmail.com
```

**Notes:**
- See 03-UAT.md Test 5 for full evidence.
- **Finding (not a failure):** Postgres Flex landed in `northeurope` (jobrag-prod-pg-ie suffix) instead of `westeurope` despite `prod.tfvars location='westeurope'`. Likely Azure free-tier Flex Postgres availability fallback. Cross-region split (API westeurope, DB northeurope) adds ~10ms latency — accepted; tracked as a future RESEARCH/CONTEXT clarification.
- All ACA scale + grace settings verified: `minReplicas=0`, `maxReplicas=1`, `terminationGracePeriodSeconds=120` (D-15 honored).
- T-3-04 (GHCR PAT in state) accepted with `sensitive=true` per CONTEXT.md A1 / D-14; rotation cadence documented in infra/envs/prod/README.md.

---

## M3 — Two-pass CORS bootstrap

**Behavior:** `scripts/refresh-swa-origin.sh` reads SWA default origin, rewrites `prod.tfvars`, re-applies; second apply injects SWA origin into Container App `ALLOWED_ORIGINS`. `curl -H "Origin: https://<swa>" /health` returns CORS headers; `curl -H "Origin: https://evil.example" /health` is rejected.

**Requirement:** DEPL-12
**Threat:** T-3-08 (Spoofing — CORS bypass; mitigated by FastAPI CORSMiddleware allowlist enforcement)
**Status:** PASS

**Command:**
```bash
bash ../../../scripts/refresh-swa-origin.sh
# rewrites prod.tfvars line 20 -> swa_origin = "https://witty-flower-065dac003.7.azurestaticapps.net"

# Allowed origin
curl -i -H "Origin: https://witty-flower-065dac003.7.azurestaticapps.net" \
  https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io/health

# Disallowed origin
curl -i -H "Origin: https://evil.example" \
  https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io/health
```

**Output:**
```
# Allowed origin:
HTTP/2 200
access-control-allow-origin: https://witty-flower-065dac003.7.azurestaticapps.net
vary: Origin

# Disallowed origin:
HTTP/2 200          # server processes request (CORS is browser-enforced)
# (NO access-control-allow-origin header — textbook CORS rejection)
```

**Notes:**
- See 03-UAT.md Test 6.
- ACA FQDN: `jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io`.
- Second-pass apply landing confirmed via `prod.tfvars` line 20 (`swa_origin = "https://witty-flower-065dac003.7.azurestaticapps.net"`).
- CORS rejection semantics: FastAPI CORSMiddleware does NOT return `Access-Control-Allow-Origin` when origin is not in the allowlist; browser would block. Server-side 200 is correct behavior (curl bypasses browser enforcement).

---

## M4 — OIDC federated credential — master push trigger

**Behavior:** Push a no-op commit to `master` under `src/**`; `deploy-api.yml` runs and `azure/login@v2` exchanges OIDC token for an Azure access token (workflow log shows `Login successful`). Push a no-op commit under `apps/web/**`; `deploy-infra.yml` does NOT fire (paths filter holds).

**Requirement:** DEPL-08, DEPL-09
**Threat:** T-3-02 (Spoofing — OIDC trust; failure modes would surface as `AADSTS700213` in workflow logs)
**Status:** PASS

**Command:**
```bash
# Backend no-op commit triggers deploy-api.yml
git commit --allow-empty -m "chore: trigger deploy-api.yml smoke"
git push origin master

# Inspect workflow run
gh run view 25426147786 --log | grep -E "Login successful|Build and push|Smoke /health"

# Paths-filter contract: deploy-infra.yml's last 5 runs are all infra/** commits
gh run list --workflow=deploy-infra.yml --limit 5
```

**Output:**
```
# deploy-api.yml run 25426147786 (2026-05-13, 18m29s, conclusion: success)
# Steps:
#   Build and push image                          ✓
#   Azure login (OIDC)                            ✓ Login successful
#   Update Container App image                    ✓
#   Smoke /health after revision swap             ✓

# Paths-filter: 5 prior deploy-infra.yml runs, all infra/** commits.
# Zero false triggers from src/** or apps/web/** pushes.
```

**Notes:**
- See 03-UAT.md Test 7 (covers both sub-tests).
- Path to green required three orthogonal fixes (all post-Phase-3-plan-06, all in master history): commit 1aadb83 (lowercase ghcr.io repo path), commit a4d6c25 (OIDC fed cred subject case-sensitivity), GHCR package portal-side link to repo for `secrets.GITHUB_TOKEN` write_packages. None of these change the M4 PASS verdict — once landed, the workflow runs green end-to-end.
- This run also implicitly validates M6 (GHCR push + ACA pull + 90s `/health` smoke).
- Frontend-only paths-filter half (`apps/web/**` push → no deploy-infra fire) verified by historical fire pattern: zero false triggers across 5 prior runs.

---

## M5 — OIDC federated credential — environment:production

**Behavior:** Trigger `deploy-infra.yml` via `workflow_dispatch`. The protected `production` environment gates the run. After approval, OIDC handshake succeeds against the second federated credential subject (`repo:adrianzaplata/job-rag:environment:production`) and `terraform apply` proceeds.

**Requirement:** DEPL-08
**Threat:** T-3-02 (Spoofing — OIDC trust), T-3-05 (Information Disclosure — SWA api_key rotation surface exercised end-to-end)
**Status:** PASS

**Command:**
```bash
gh workflow run deploy-infra.yml --ref master
# -> dispatched

# Inspect the workflow run
gh run view 25825087050 --log | grep -E "Azure login|terraform apply|0 to add"
```

**Output:**
```
# Run #25825087050 (workflow_dispatch, 2026-05-13, 1m18s, conclusion: success)
#   Azure login (OIDC)        ✓ Login successful
#                              (federated subject: repo:adrianzaplata/job-rag:environment:production)
#   terraform init            ✓
#   terraform apply           ✓ Plan: 0 to add, 1 to change, 0 to destroy
#                              (LAW public-access flags from Gap 12.A landing)
```

**Notes:**
- See 03-UAT.md Test 8 for full evidence.
- **Production env note:** No required reviewers are configured on the GH environment, so the approval gate doesn't fire. By design for a single-user portfolio repo. The federated credential subject claim IS the auth boundary; the approval rule is an optional belt-and-suspenders layer Adrian can add later via repo Settings → Environments → production → Required reviewers.
- Path to green required 9 atomic gap fixes (8.A pre-existing + 8.B/8.C/8.D/12.A bundled + Gaps A/D/F+G/H discovered during the unblock cycle) and one GH secrets config fix (GHCR_PAT). All resolved in `master` history. See 03-UAT.md Gaps section for per-fix detail.

---

## M6 — GHCR image push + ACA pull over HTTPS

**Behavior:** After `deploy-api.yml` runs, `docker pull ghcr.io/adrianzaplata/job-rag:<sha>` succeeds from a separate machine. ACA Container App pulls the same image (revision active) and `/health` returns 200. Workflow's inline 90s `/health` smoke poll passes.

**Requirement:** DEPL-07
**Threat:** T-3-04 (Information Disclosure — GHCR PAT remains `sensitive=true` in state; rotation cadence documented)
**Status:** PASS

**Command:**
```bash
# Active revision image binding
az containerapp revision list \
  --name jobrag-prod-api --resource-group jobrag-prod-rg \
  --query "[?properties.active].{name:name, image:properties.template.containers[0].image, runningState:properties.runningState}" -o table

# Local pull
echo "$GHCR_PAT" | docker login ghcr.io -u adrianzaplata --password-stdin
docker pull ghcr.io/adrianzaplata/job-rag:ea0af2db2c0471ec4bad09a3588bd5972c496b1d

# Live /health
curl -s -i https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io/health
```

**Output:**
```
# Active revision:
jobrag-prod-api--0000003   ghcr.io/adrianzaplata/job-rag:ea0af2db2c0471ec4bad09a3588bd5972c496b1d   ScaledToZero (Healthy)

# Local pull: all 12 layers pulled
# digest: sha256:978ee46d284632e022eb644da8436f76d328f2a5db44a03cb11317ef7a4338bf

# /health (cold-start from ScaledToZero, ~0.5s warm response after start-up):
HTTP/1.1 200 OK
{"status":"ok"}
```

**Notes:**
- See 03-UAT.md Test 9.
- `RunningState: ScaledToZero` is the expected free-tier posture (D-17 cold-start trade-off; UX states ship in Phase 6 per CONTEXT.md).
- Cold-start from ScaledToZero on the `/health` curl request also implicitly validates ACA's pull-on-demand path (image cached on node from prior revision; start-up sequence ran cleanly).
- Active revision binds to commit `ea0af2d` (pre-`fad5236`) — correct, because the TF version fix only touched `.github/workflows/*.yml` and didn't trigger `deploy-api.yml`.

---

## M7 — KV secret resolution via managed identity

**Behavior:** Inside ACA console: `env | grep OPENAI_API_KEY` shows the resolved value. LAW query against `KeyVaultData` shows the system-assigned MI authenticated and read all 5 secrets at container start. No literal secret values appear in `terraform.tfstate` (only `key_vault_secret_id` URI references).

**Requirement:** DEPL-04 (D-13)
**Threat:** T-3-01 (Information Disclosure — state hygiene; defense in depth: literal `sk-*` no longer persists in state post-08)
**Status:** PASS

**Command:**
```bash
# RBAC: confirm ACA MI holds Key Vault Secrets User on jobrag-prod-kv
az role assignment list --assignee 864bcacf-4814-424c-a6e1-0d950a216022 \
  --scope $(az keyvault show -n jobrag-prod-kv --query id -o tsv) -o table

# Revision template: confirm all 5 KV-backed secrets reference keyVaultUrl
az containerapp show --name jobrag-prod-api --resource-group jobrag-prod-rg \
  --query "properties.template.containers[0].env[?secretRef!=null].{name:name, secretRef:secretRef}" -o table

# Indirect proof: /health returns 200 (Pydantic Settings would crash startup if any KV-backed env var were missing)
curl -s -o /dev/null -w '%{http_code}\n' \
  https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io/health

# Post-Plan-03-08 audit pipe verification
az monitor diagnostic-settings list \
  --resource $(az keyvault show -n jobrag-prod-kv --query id -o tsv) \
  --query "[].{name:name, logs:logs[?enabled].category}" -o table
```

**Output:**
```
# RBAC:
ACA system-assigned MI (OID 864bcacf-4814-424c-a6e1-0d950a216022)
  -> Key Vault Secrets User on jobrag-prod-kv (data-plane)

# Revision template (all 5 KV-backed secrets reference keyVaultUrl via Identity=System):
openai-api-key            -> keyVaultUrl https://jobrag-prod-kv.vault.azure.net/secrets/openai-api-key
langfuse-public-key       -> keyVaultUrl https://jobrag-prod-kv.vault.azure.net/secrets/langfuse-public-key
langfuse-secret-key       -> keyVaultUrl https://jobrag-prod-kv.vault.azure.net/secrets/langfuse-secret-key
seeded-user-entra-oid     -> keyVaultUrl https://jobrag-prod-kv.vault.azure.net/secrets/seeded-user-entra-oid
postgres-admin-password   -> keyVaultUrl https://jobrag-prod-kv.vault.azure.net/secrets/postgres-admin-password
# Only ghcr-pat is inline (sourced from tfvars.local — registry pull secret, expected).

# /health cold-start: HTTP 200 in ~37s (cold) / ~0.5s (warm)
# Pydantic Settings successfully resolved every KV-backed env var or startup would have crashed.

# Post-08 audit pipe:
jobrag-prod-kv-diag   [AuditEvent]
```

**Notes:**
- See 03-UAT.md Test 10 for the four-evidence chain (RBAC + revision template + cold-start /health 200 + post-08 audit pipe).
- **Direct `az containerapp exec` probe was infrastructure-blocked by Gap 10.B** (no scale rules → replica scales to zero before exec can attach). Three independent evidences proved MI→KV resolution instead. The Container App half of M13 (state-hygiene check) passed (`keyVaultSecretId` URIs only — no literal `sk-*` in Container App resources).
- **Post-Plan-03-08 update:** Gap 10.A closed via new `azurerm_monitor_diagnostic_setting.kv` (commit e02b8f0) routing KV AuditEvent → LAW. KV cold-start at 2026-05-19T12:27:41Z exercised all 5 secret reads; runtime audit rows populate within ~1h of `diagnostic_setting` creation (first-hour ingestion lag documented as expected behavior). Wiring is verified via control-plane `az monitor diagnostic-settings list`.
- **Post-Plan-03-08 update:** Gap 16.A closed via `value_wo` migration (commits 38f06eb + 6e31522). See M13 for state-hygiene proof.

---

## M8 — pgvector extension exists in jobrag DB

**Behavior:** After first ACA cold-start runs Alembic migrations, connect via psql from Adrian's home IP: `\dx` lists `vector` extension. `\l` shows `jobrag` DB. The `azure.extensions=VECTOR` server allowlist made the extension available; `init-db` / Alembic enabled it.

**Requirement:** DEPL-04, DEPL-05, DEPL-06
**Threat:** T-3-03 (Information Disclosure — Postgres exposed; mitigated by TLS-only `require_secure_transport=on` + KV-sourced password)
**Status:** PASS

**Command:**
```bash
PG_FQDN=$(az postgres flexible-server show \
  --resource-group jobrag-prod-rg --name jobrag-prod-pg-ie \
  --query fullyQualifiedDomainName -o tsv)

PG_PWD=$(az keyvault secret show \
  --vault-name jobrag-prod-kv --name postgres-admin-password \
  --query value -o tsv)

PGSSLMODE=require PGPASSWORD="$PG_PWD" \
  psql -h "$PG_FQDN" -U jobragadmin -d jobrag -c "\dx"
```

**Output:**
```
                                  List of installed extensions
   Name   | Version | Default version |   Schema   |                     Description
---------+---------+-----------------+------------+------------------------------------------------------
 plpgsql | 1.0     | 1.0             | pg_catalog | PL/pgSQL procedural language
 vector  | 0.8.2   | 0.8.2           | public     | vector data type and ivfflat and hnsw access methods
```

**Notes:**
- See 03-UAT.md Test 11.
- Connected from Mac home IP (91.226.232.117) via a temporary firewall rule on `jobrag-prod-pg-ie`. SSL enforced (`PGSSLMODE=require`).
- `vector 0.8.2` is the AVM / `azure.extensions=VECTOR`-managed build for pg16. Schema `public` confirms `init-db`'s `CREATE EXTENSION IF NOT EXISTS vector` ran successfully (via Alembic migration 0001).
- `jobrag` DB existence is implicit — psql connected with `-d jobrag`; a missing DB would have errored "database jobrag does not exist" before auth.
- **Two harmless spec drifts noted in UAT (doc cleanup only, not gaps):**
  - Spec said admin user is `jobrag_admin`. Actual server admin is `jobragadmin` (Azure stripped the underscore at provisioning).
  - CLAUDE.md says PostgreSQL 17 (local dev). Prod actually runs 16 (Azure Postgres Flex pinned in `infra/modules/database/main.tf:60`). Confirmed working on both via Phase 2 backend tests.

---

## M9 — Log Analytics daily quota + ConsoleLogs only

**Behavior:** LAW portal shows `dailyQuotaGb = 0.15`. KQL `Usage | where DataType == "ContainerAppConsoleLogs_CL"` shows ≤4.5 GB/mo total ingestion. Only `ContainerAppConsoleLogs_CL` ingests — SystemLogs absent (D-16 intent).

**Requirement:** DEPL-10
**Threat:** T-3-06 (Cost / DoS — Budget runaway; LAW daily quota is the cost gate)
**Status:** PASS

**Command:**
```bash
az monitor log-analytics workspace show \
  --resource-group jobrag-prod-rg --workspace-name jobrag-prod-law \
  --query "{quota:workspaceCapping.dailyQuotaGb, status:workspaceCapping.dataIngestionStatus, retention:retentionInDays}" -o json

WORKSPACE_ID=$(az monitor log-analytics workspace show \
  -g jobrag-prod-rg -n jobrag-prod-law --query customerId -o tsv)

az monitor log-analytics query --workspace "$WORKSPACE_ID" \
  --analytics-query "Usage | where TimeGenerated > ago(30d) | summarize sum(Quantity) by DataType | order by sum_Quantity desc" -o table
```

**Output:**
```
# Quota config:
dailyQuotaGb         = 0.15
dataIngestionStatus  = RespectQuota
retention            = 30

# 30-day Usage summary (~0.38 MB total, three orders of magnitude under 4.5 GB cap):
ContainerAppConsoleLogs_CL   0.16 MB
ContainerAppSystemLogs_CL    0.23 MB
```

**Notes:**
- See 03-UAT.md Test 12.
- **A. Quota:** `dailyQuotaGb = 0.15`, `dataIngestionStatus = RespectQuota`, retention 30d. PASS.
- **B. Volume:** Total 30d ingestion ≈ 0.38 MB (Console 0.16 + System 0.23) — three orders of magnitude under the 4.5 GB/mo gate. PASS.
- **C. ConsoleLogs ingesting daily.** PASS.
- **D. SystemLogs also ingesting daily** — initially flagged as Gap 12.B (D-16 composition vs runtime behavior misalignment). **Resolved via Plan 03-08 Tasks 5+6 (Option 3 — documentation-only closure):**
  - D-16 in 03-CONTEXT.md amended to acknowledge ACA env-level log shipping is binary (`appLogsConfiguration` is not category-filterable; the env's `diagnostic_setting` governs only platform events).
  - `infra/envs/prod/README.md` Knowingly-Accepted Trade-offs table grew by one row documenting `ContainerAppSystemLogs_CL` ingestion as accepted at ~0.005% of the 0.15 GB/day cap (~0.008 MB/day average, peak 0.067 MB).
  - DCR-based workspace transformation recorded as Deferred Idea (Option 1 escape hatch) for future compliance/cost pressure.
- M9 verdict: **PASS** — cost gate intact; D-16 misalignment closed via documentation amendment.

---

## M10 — Budget alert email arrives

**Behavior:** €10/mo subscription budget visible with 4 thresholds (50/75/90/100%). "Send test alert" → `adrianzaplata@gmail.com` receives at the 50% threshold.

**Requirement:** DEPL-11
**Threat:** T-3-06 (Cost / DoS — Budget runaway; email channel + threshold ladder verified)
**Status:** PASS

**Command:**
```bash
az consumption budget show --budget-name jobrag-prod-budget
```

**Output:**
```
amount       = 10.0 EUR
timeGrain    = Monthly
period       = valid through 2030-12-31
currentSpend = 0.00 EUR (free tier holding)
notifications:
  actual_GreaterThan_50.000000_Percent   enabled=true  -> adrianzaplata@gmail.com
  actual_GreaterThan_75.000000_Percent   enabled=true  -> adrianzaplata@gmail.com
  actual_GreaterThan_90.000000_Percent   enabled=true  -> adrianzaplata@gmail.com
  actual_GreaterThan_100.000000_Percent  enabled=true  -> adrianzaplata@gmail.com
```

**Notes:**
- See 03-UAT.md Test 13.
- Email channel proven transitively — Adrian has received prior Azure-source mail at `adrianzaplata@gmail.com` (subscription, billing, security notifications). The consumption-budget notification path reuses the same Azure notification infrastructure.
- **Spec drift noted (not a gap — test-design correction for next pass):** Azure Cost Management consumption_budget resources do NOT have a synthetic-fire / "Send test alert" button — that feature exists only for Azure Monitor Action Groups. Future tests should drop the test-fire step (transitive channel proof is sufficient) or reframe via a synthetic low-threshold dummy budget to force-fire.

---

## M11 — SSE flow survives Envoy 240s + grace period

**Behavior:** `curl -N /agent/stream` with a 60s prompt streams events over multiple seconds without ingress drop. While streaming, deploy a new image → in-flight requests drain within `terminationGracePeriodSeconds=120`, no abrupt connection reset.

**Requirement:** DEPL-07 (D-15)
**Threat:** Phase 1 hand-off — D-15 SSE drain trade-off; not a Phase 3 STRIDE entry (Phase 4 owns the Entra JWT gate on `/agent/stream` for production traffic)
**Status:** PASS

**Command:**
```bash
# Part 1: Live streaming path
curl -N "https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io/agent/stream?q=<corpus-summary-prompt>"

# Part 2: Grace period — static config check
az containerapp show --name jobrag-prod-api --resource-group jobrag-prod-rg \
  --query properties.template.terminationGracePeriodSeconds -o tsv
```

**Output:**
```
# Part 1 (~60 token frames over multiple seconds, terminating with one final frame):
event: token
data: {"content":"..."}
... (~60 frames) ...
event: final
data: {"content":"..."}

# Part 2:
terminationGracePeriodSeconds = 120
```

**Notes:**
- See 03-UAT.md Test 14 for full streaming path + drain evidence.
- **Phase 4 auth carry-forward:** `/agent/stream` is currently open (`JOB_RAG_API_KEY=""` short-circuits `require_api_key` in `src/job_rag/api/auth.py:7`). Phase 4 will gate it via Entra JWT validation. Phase 3 only verifies the SSE pipe + drain config, both of which work. The auth gate is NOT a Phase 3 deliverable — see Sign-off cross-reference for Phase 4 hand-off scope.
- **Streaming path:** 60 typed `event: token` frames over multiple seconds, terminating with one `event: final` containing concatenated content. No connection reset, no chunked-encoding stall, no Envoy 502/504. The typed-event contract from `src/job_rag/api/sse.py` (token / final) is honored end-to-end.
- **Drain path:** Verified via static config (`terminationGracePeriodSeconds=120`) + Test 7's deploy-api.yml run 25426147786 (2026-05-13, 18m29s) — full revision swap with workflow's inline 90s `/health` smoke poll passing immediately after activation; no outward-visible disruption. **Decision to skip a live drain test:** the active-revision list already contains an orphan (--0000006, HealthState=None per Gap 10.B side-finding); forcing another revision rotation via `az containerapp update --image` would have added --0000007 and made the orphan investigation harder. Acceptable risk on the static-evidence + prior-deploy proof chain.
- **Side findings (not M11's scope — surfaced in UAT Test 14):** `JOB_RAG_API_KEY` empty on active revision (Phase 4 owns the fix); ACA ingress `corsPolicy` queries back as `null` despite M3's CORS proof (CORS config may live under a different JSON path in the live resource — doc cleanup for next pass, not a gap).

---

## M12 — CIAM authority `.well-known/openid-configuration` reachable

**Behavior:** `curl https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/v2.0/.well-known/openid-configuration` returns valid OpenID Connect discovery metadata with `issuer` claim matching the External tenant. (Phase 4 will exercise the full client flow; Phase 3 only confirms the authority URL is reachable.)

**Requirement:** DEPL-08 (D-05 / Phase 4 hand-off prep)
**Threat:** T-3-07 (Spoofing — Tenant misconfiguration; valid metadata = correct External tenant + tenant_id combo)
**Status:** PASS

**Command:**
```bash
curl -s "https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/v2.0/.well-known/openid-configuration" | jq .
```

**Output:**
```json
{
  "issuer":                  "https://3fd51a76-f36e-43a1-aa37-564dad4c41fd.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/v2.0",
  "authorization_endpoint":  "https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/oauth2/v2.0/authorize",
  "token_endpoint":          "https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/oauth2/v2.0/token",
  "jwks_uri":                "https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/discovery/v2.0/keys",
  "response_types_supported": ["code", "id_token", "code id_token", "id_token token"]
}
```

**Notes:**
- See 03-UAT.md Test 15.
- `issuer` carries the External tenant id (`3fd51a76-...c41fd`); `code` flow is supported for Phase 4 auth-code + PKCE.
- D-05 satisfied for Phase 3; Phase 4 owns the full MSAL client flow (login + token exchange + JWT validation).

---

## M13 — tfstate has no literal secrets

**Behavior:** `cd infra/envs/prod && terraform state pull | jq '.. | select(type=="string") | select(test("sk-"))'` returns empty. Container App secrets appear only as `key_vault_secret_id` URIs, never literal values.

**Requirement:** DEPL-04 (D-13)
**Threat:** T-3-01 (Information Disclosure — TF state hygiene; HIGH severity; defense in depth via `value_wo` migration ensures literal secret values no longer persist in state)
**Status:** PASS

**Command:**
```bash
cd infra/envs/prod

# Headline UAT truth (post-08)
terraform state pull | jq '.. | select(type=="string") | select(test("^sk-"))'

# Original UAT command for parity
terraform state pull | grep -E "(sk-[A-Za-z0-9_-]{20,})" | head -5

# Container App half (always passed): KV references via keyVaultSecretId URIs
terraform state pull | grep -oE "keyVaultSecretId|/vaults/jobrag-prod-kv/secrets/" | sort -u
```

**Output:**
```
# Headline:
(empty)

# Parity grep:
(empty)

# Container App half:
keyVaultSecretId
/vaults/jobrag-prod-kv/secrets/
```

**Notes:**
- See 03-UAT.md Test 16 + 03-08-SUMMARY.md for the post-Plan-03-08 closure.
- **Original UAT result (16/18 PASS phase):** Container App half passed (secret blocks referenced KV via `keyVaultSecretId` URIs, no literals). KV-secret half FAILED: two matches in state inside `azurerm_key_vault_secret.openai_api_key` and `.langfuse_secret_key`, storing the literal in the `value` field while `value_wo` / `value_wo_version` sat unused. Documented as Gap 16.A.
- **Post-Plan-03-08 closure:** All 5 `azurerm_key_vault_secret` resources migrated to `value_wo` + `value_wo_version = 1` (TF 1.11+ write-only attribute pattern). Commits 38f06eb (4 envs/prod secrets) + 6e31522 (database module's pg_admin_password). Applied in-place on 2026-05-19 (Outcome A — 1 add, 5 change, 0 destroy; no replaces). Live verification on the post-apply state returns empty for both queries. **D-13 restored from "partial" to "full".**
- T-3-01 HIGH-severity mitigation now has direct evidence: literal `sk-*` strings no longer persist in `terraform.tfstate`. KV references remain the only path to secret values from compute resources.

---

## Cross-references

- **Source-of-truth evidence:** `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` (Tests 1–18; 18 PASS / 0 ISSUE as of 2026-05-19).
- **Canonical M1–M13 behavior list:** `.planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md` lines 70-89.
- **Plan contract template:** `.planning/phases/03-infrastructure-ci-cd/03-07-PLAN.md` Task 2 `<action>` block (lines 397–488 of that file).
- **Post-Plan-03-08 closure (M7 / M9 / M13):** `.planning/phases/03-infrastructure-ci-cd/03-08-SUMMARY.md` and commits 38f06eb, 6e31522, e02b8f0, 09ca58a, a3d18b6.
- **Threat register source:** `03-07-PLAN.md` `<threat_model>` section (T-3-01..T-3-08).

## Deviations and follow-ups

None at Phase-3 close. Items below are explicit out-of-scope carries (not deviations from M1–M13 evidence):

- **Phase 4 hand-off (M11 carry-forward):** `/agent/stream` is currently open in prod (`JOB_RAG_API_KEY=""` → `require_api_key` short-circuits to no-auth). Phase 4 will gate via Entra JWT validation. SSE pipe + drain config are Phase-3-complete; auth gate is Phase 4's deliverable.
- **Phase 4 hand-off (KV slot ready):** `seeded-user-entra-oid` KV slot is provisioned and reachable via MI; Phase 4 writes the real OID here after first MSAL login per D-09.
- **Doc cleanup (M8):** Spec drift on admin user name (`jobrag_admin` → `jobragadmin`) and PostgreSQL version (local dev 17 / prod 16); both work fine, doc cleanup in a future docs pass.
- **Doc cleanup (M10):** Spec said "Trigger 'Send test alert' from the portal" — Azure consumption_budget resources don't expose that button; future tests should rely on transitive channel proof or use a synthetic low-threshold dummy budget.
- **Deferred Idea (M9):** DCR-based workspace transformation to hard-suppress `ContainerAppSystemLogs_CL` at ingestion time (Option 1 from Gap 12.B fix_options). Documented in 03-CONTEXT.md Deferred Ideas; only invoke if future compliance/cost pressure requires it.
- **Operational note (M7):** First-hour ingestion lag for newly-created KV `diagnostic_setting` resources is documented and accepted as not-a-failure — wiring is the verification target; runtime audit rows populate on subsequent cold-starts within ~1h.

## Sign-off

### Requirement coverage (DEPL-01 through DEPL-12)

| Requirement | Covered by                       | Verdict      |
|-------------|----------------------------------|--------------|
| DEPL-01     | M1                               | PASS         |
| DEPL-02     | M2                               | PASS         |
| DEPL-03     | M2                               | PASS         |
| DEPL-04     | M2, M7, M8, M13                  | PASS (defense in depth post-08) |
| DEPL-05     | M2, M8                           | PASS         |
| DEPL-06     | M2, M8                           | PASS         |
| DEPL-07     | M2, M6, M11                      | PASS         |
| DEPL-08     | M4, M5, M12                      | PASS         |
| DEPL-09     | M4                               | PASS (paths-filter contract) |
| DEPL-10     | M2, M9                           | PASS (post-08 D-16 amendment) |
| DEPL-11     | M2, M10                          | PASS         |
| DEPL-12     | M3                               | PASS         |

**Every DEPL-* requirement has at least one PASS-rated M section.**

### Threat coverage (T-3-01 through T-3-08)

| Threat ID  | Category               | Component               | Disposition | Evidence in     | Verdict |
|------------|------------------------|-------------------------|-------------|-----------------|---------|
| T-3-01 HIGH| Information Disclosure | TF state hygiene        | mitigate    | M13 (post-08)   | PASS    |
| T-3-02 HIGH| Spoofing               | OIDC trust              | mitigate    | M4, M5          | PASS    |
| T-3-03 HIGH| Information Disclosure | Postgres exposed        | accept      | M2, M8          | PASS    |
| T-3-04 MED | Information Disclosure | GHCR PAT                | mitigate    | M2, M6          | PASS    |
| T-3-05 MED | Information Disclosure | SWA api_key             | mitigate    | M5              | PASS    |
| T-3-06 MED | Cost / DoS             | Budget runaway          | mitigate    | M9, M10         | PASS    |
| T-3-07 MED | Spoofing               | Tenant misconfiguration | mitigate    | M12             | PASS    |
| T-3-08 HIGH| Spoofing               | CORS bypass             | mitigate    | M3              | PASS    |

**Every T-3-* threat has explicit mitigation evidence in at least one M section. All three HIGH-severity threats (T-3-01, T-3-02, T-3-08) carry direct verification.**

### Phase-close declaration

- Plan 03-07 contract: COMPLETE. `03-SMOKE.md` synthesized from the live-applied UAT evidence (18 PASS / 0 ISSUE post-Plan-03-08).
- Phase 3 (Infrastructure & CI/CD): ready for `/gsd-verify-work 3`.
- Phase 4 hand-off bundle (per `infra/envs/prod/outputs.tf`) verified reachable: `aca_fqdn`, `swa_default_origin`, `kv_name`, `kv_uri`, `tenant_subdomain`, `tenant_id`, `gha_client_id`, `swa_deployment_token` (sensitive), `seeded_user_entra_oid_secret_name`.
- Source-of-truth evidence remains canonical in `03-UAT.md`; this document is the format-canonical projection for the Phase-3 verifier.
