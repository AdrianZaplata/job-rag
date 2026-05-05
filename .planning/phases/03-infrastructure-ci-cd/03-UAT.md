---
status: testing
phase: 03-infrastructure-ci-cd
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05a-SUMMARY.md, 03-05b-SUMMARY.md, 03-06-SUMMARY.md]
started: 2026-05-05T00:00:00Z
updated: 2026-05-05T11:50:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 3
name: Bootstrap Apply — M1
expected: |
  `cd infra/bootstrap && terraform init -backend=false && terraform apply -var-file=terraform.tfvars.local`
  succeeds against your Azure subscription. Creates `jobrag-tfstate-rg` (westeurope) +
  `jobragtfstate{5-char-suffix}` storage account (versioning + 7d soft-delete) +
  `tfstate` container. `terraform output -raw storage_account_name` / `container_name` /
  `resource_group_name` returns three usable values.
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
result: [pending]

### 4. Backend Migration to Remote State — M1
expected: After bootstrap apply, copy the three outputs into `infra/envs/prod/backend.tf`. From a fresh checkout, `cd infra/envs/prod && terraform init` succeeds (state pulled from Azure Blob, no local `.tfstate` written), and `terraform plan -var-file=prod.tfvars` produces a coherent plan against the remote state.
result: [pending]

### 5. Prod Apply — Full Azure Resource Graph (M2)
expected: `cd infra/envs/prod && terraform apply -var-file=prod.tfvars` succeeds. Portal verification: ACA Container App Environment + jobrag-prod-api Container App (scale-to-zero), Postgres Flex B1ms with `vector` listed in `azure.extensions`, Static Web App (Free SKU), Key Vault with 5 secrets (openai_api_key, langfuse_public_key, langfuse_secret_key, seeded_user_entra_oid, postgres-admin-password), Log Analytics workspace with 0.15 GB/day cap, €10/mo budget alert with 50/75/90/100% thresholds visible.
result: [pending]

### 6. Two-Pass CORS Bootstrap (M3 / DEPL-12)
expected: After first apply, `bash scripts/refresh-swa-origin.sh` reads SWA default origin from terraform output, rewrites `prod.tfvars` (`swa_origin = "https://<swa>.azurestaticapps.net"`), and a second `terraform apply` injects the SWA origin into the Container App's `ALLOWED_ORIGINS` env var. `curl -H "Origin: https://<swa>.azurestaticapps.net" https://<aca-fqdn>/health` returns CORS headers; `curl -H "Origin: https://evil.example" https://<aca-fqdn>/health` is rejected.
result: [pending]

### 7. OIDC Federated Credential — Master Push (M4 / DEPL-08, DEPL-09)
expected: Push a no-op commit to master under `src/**`. `deploy-api.yml` runs and `azure/login@v2` exchanges OIDC token for an Azure access token (workflow log shows `Login successful`). Push a no-op commit under `apps/web/**` (or any non-infra path); `deploy-infra.yml` does NOT fire (paths filter holds).
result: [pending]

### 8. OIDC Federated Credential — environment:production (M5 / DEPL-08)
expected: Trigger `deploy-infra.yml` via `workflow_dispatch`. GitHub blocks the run pending review on the protected `production` environment. After you approve as the sole reviewer, OIDC handshake succeeds against the second federated credential subject (`repo:adrianzaplata/job-rag:environment:production`) and the workflow proceeds to `terraform apply`.
result: [pending]

### 9. GHCR Image Push + ACA Pull (M6 / DEPL-07)
expected: After `deploy-api.yml` runs, `docker pull ghcr.io/adrianzaplata/job-rag:<sha>` from a separate machine succeeds (or with the GHCR PAT if package is private). The ACA Container App pulls the same image (revision active) and `curl https://<aca-fqdn>/health` returns 200. Workflow's inline 90s `/health` smoke poll passes loud.
result: [pending]

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
result: [pending]

### 16. tfstate Has No Literal Secrets (M13 / D-13, security)
expected: `cd infra/envs/prod && terraform state pull | jq '.. | select(type=="string") | select(test("sk-"))'` returns empty. Searching for OpenAI/Langfuse key prefixes finds nothing in state. Container App secrets appear only as `key_vault_secret_id` URIs, never literal values.
result: [pending]

### 17. Bootstrap-Corpus Workflow Cost Gate (Plan 05b / A6)
expected: `gh workflow run bootstrap-corpus.yml` (without `acknowledge_cost=yes`) fails fast at the first job step (acknowledge_cost defaulted to "no"). Re-run with `gh workflow run bootstrap-corpus.yml -f acknowledge_cost=yes` — workflow proceeds, `azure/login@v2` succeeds via OIDC, and `az containerapp exec --container api --command "/bin/sh -c 'job-rag ingest --show-cost && job-rag embed --show-cost'"` runs against live ACA. Job summary shows container app name + RG + M8 smoke pointer.
result: [pending]

### 18. Three Deploy Workflows + Paths Filter Contract (Plan 06 / DEPL-08)
expected: All three workflow files exist on disk: `.github/workflows/deploy-infra.yml` (paths: `infra/**`, environment: production, OIDC), `deploy-api.yml` (paths: `src/**` + `Dockerfile` + `pyproject.toml` + `uv.lock` + `alembic/**` + `scripts/docker-entrypoint.sh`, OIDC + `packages: write`), `deploy-spa.yml` (paths: `apps/web/**`, token-based, no `id-token: write`). A backend-only PR fires deploy-api.yml only; an infra-only PR fires deploy-infra.yml only; a frontend-only PR fires deploy-spa.yml only (after Phase 4 lands `apps/web/`).
result: [pending]

## Summary

total: 18
passed: 2
issues: 0
pending: 16
skipped: 0
blocked: 0

## Gaps

[none yet]
