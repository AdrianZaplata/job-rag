---
phase: 03-infrastructure-ci-cd
plan: 05b
subsystem: infrastructure
tags: [terraform, azure, dev-env, scaffold-only, docker-entrypoint, github-actions, oidc, az-containerapp-exec]
requires:
  - 03-05a (prod composition layer — dev mirrors its shape)
  - 03-04 (compute/database/identity modules consumed by dev composition)
  - 03-03 (network/kv/monitoring modules consumed by dev composition)
provides:
  - infra/envs/dev/ — 8 sibling files mirroring prod composition (D-04 scaffold-only)
  - scripts/docker-entrypoint.sh — B4 init-db + uvicorn only (corpus seed removed)
  - .github/workflows/bootstrap-corpus.yml — A6 one-shot corpus seed via az containerapp exec
affects:
  - Phase 6 deploy workflows (deploy-api.yml will share the OIDC fed cred used here)
  - Phase 7 smoke (no per-cold-start re-embed cost; bootstrap-corpus runs once)
  - Future staging activation (apply path documented in dev README)
tech-stack:
  added: []
  patterns:
    - Dev mirror pattern (3 module-input flag diffs + tfvars placeholders + separate state key)
    - W7 composition-layer azurerm_monitor_diagnostic_setting.aca preserved in dev for parity
    - POSTGRES_* -> DATABASE_URL/ASYNC_DATABASE_URL composition at entrypoint (no-op for docker-compose)
    - workflow_dispatch + acknowledge_cost input gate (deliberate human invocation for cost-incurring ops)
    - az containerapp exec over az containerapp job (no second TF resource type for v1)
key-files:
  created:
    - infra/envs/dev/backend.tf
    - infra/envs/dev/provider.tf
    - infra/envs/dev/locals.tf
    - infra/envs/dev/variables.tf
    - infra/envs/dev/main.tf
    - infra/envs/dev/outputs.tf
    - infra/envs/dev/dev.tfvars
    - .github/workflows/bootstrap-corpus.yml
  modified:
    - infra/envs/dev/README.md (replaced Plan 01 skeleton with full scaffold-only rationale + parity table + deferred apply path)
    - scripts/docker-entrypoint.sh (B4: removed ingest/embed; added POSTGRES_* composition; tightened to set -euo pipefail; chmod +x)
decisions:
  - Dev env mirrors prod with three meaningful diffs: env=dev, monitoring.create_budget=false, database.use_allow_azure_services=false. KV purge_protection picked up from module's `var.env != "prod"` default → false (easier teardown).
  - Backend key=dev.tfstate (separate state file in same Azure Blob backend per D-01).
  - W7 composition-layer azurerm_monitor_diagnostic_setting.aca included in dev verbatim for prod parity (dev never applies anyway, so no cost).
  - swa_api_key alias output included in dev outputs.tf for B2 manual runbook parity should dev ever apply.
  - Entrypoint reduced to init-db + uvicorn only (B4 locked decision per A6 addendum). Corpus ingest+embed moved to bootstrap-corpus.yml.
  - Bootstrap-corpus uses az containerapp exec, NOT az containerapp job — no second TF resource type for v1 (revisit only if scheduled corpus refresh becomes a real need).
  - workflow_dispatch ONLY trigger with acknowledge_cost: "yes" input gate — auto-run on push/schedule would re-embed on every code change and blow the OpenAI budget.
  - No `environment: production` gate on bootstrap-corpus.yml: master-push fed cred subject covers workflow_dispatch from default branch (per D-08).
metrics:
  duration: 8m
  completed: 2026-04-30
---

# Phase 03 Plan 05b: Dev Mirror + Entrypoint Scope Reduction + Bootstrap-Corpus Summary

Wave 2 Plan B closes the Phase 3 TF + CI surface (modulo Plan 06's deploy workflows + Plan 07's smoke). Three deliverables landed: (1) `infra/envs/dev/` mirrors the prod composition (8 sibling files) as scaffold-only per D-04 — same six-module wiring, same `outputs.tf` shape, three meaningful module-input flag diffs, separate `dev.tfstate` key in the same backend, full README replacing the Plan 01 skeleton; (2) `scripts/docker-entrypoint.sh` reduced to `job-rag init-db` + `exec uvicorn` (B4 locked decision per A6 addendum), with the POSTGRES_* → DATABASE_URL/ASYNC_DATABASE_URL composition block preserved for ACA env injection (no-op for local docker-compose), `set -e` tightened to `set -euo pipefail`, and the file's exec bit set via `git update-index --chmod=+x`; (3) `.github/workflows/bootstrap-corpus.yml` — `workflow_dispatch` ONLY trigger with an `acknowledge_cost: "yes"` input gate, OIDC via `azure/login@v2` against the same `gha-master-push` federated credential as `deploy-api.yml`, and `az containerapp exec --container api --command` running `job-rag ingest --show-cost && job-rag embed --show-cost` against the live ACA revision. After this plan the entire Phase 3 TF + CI surface is in place; Plan 06 ships the three deploy workflows; Plan 07 runs the live-Azure smoke.

## Tasks Executed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Dev env scaffold (8 sibling files) | `677ae80` | infra/envs/dev/{backend,provider,locals,variables,main,outputs}.tf, dev.tfvars, README.md |
| 2 | Entrypoint reduction (B4: init-db + uvicorn only) | `692a830` | scripts/docker-entrypoint.sh (chmod +x) |
| 3 | bootstrap-corpus.yml workflow (A6 one-shot seed) | `8ce9ea8` | .github/workflows/bootstrap-corpus.yml |

## Composition Highlights

### Dev mirror — module call diffs vs prod

| Knob | Prod | Dev |
|------|------|-----|
| `env` | `"prod"` | `"dev"` (all 6 module calls) |
| `module.monitoring.create_budget` | `true` | `false` (single subscription budget owned by prod) |
| `module.database.use_allow_azure_services` | `true` (A1 Path A) | `false` (dev never applies; firewall rule wouldn't matter) |
| `module.kv.purge_protection_enabled` | `true` | `false` (module default for `env != "prod"` — easier teardown) |
| Backend `key` | `prod.tfstate` | `dev.tfstate` (separate blob, same backend) |
| `azurerm` provider `purge_soft_delete_on_destroy` | `false` | `true` (matches dev's no-purge-protection KV; clean `terraform destroy`) |

### Composition-only resources (mirrored from prod)

- `azurerm_resource_group.dev`
- `azurerm_role_assignment.deployer_kv_secrets_officer` (scope=kv_id, role=Key Vault Secrets Officer, principal=current client)
- 4 × `azurerm_key_vault_secret` (openai_api_key, langfuse_public_key, langfuse_secret_key, seeded_user_entra_oid) — all `depends_on` deployer role assignment
- `azurerm_role_assignment.aca_kv_secrets_user` (post-compute MI granted KV Secrets User)
- `azurerm_monitor_diagnostic_setting.aca` (W7 composition layer, ContainerAppConsoleLogs_CL only per D-16)
- `azurerm_static_web_app.spa` (D-03 raw resource, Free SKU)

### Two-pass CORS local (locals.tf)

Identical to prod — `join(",", compact([var.swa_origin == "" ? "" : var.swa_origin, "http://localhost:5173"]))` (B1: empty-string + `compact()`).

### Outputs (parity with prod's 11+alias)

All 11 outputs carried over with the `swa_api_key` alias included for the B2 manual runbook command (`terraform output -raw swa_api_key | gh secret set ...`) should dev ever apply.

### docker-entrypoint.sh (B4 locked)

Before (Phase 1): `set -e`; init-db; **ingest --show-cost**; **embed --show-cost**; exec uvicorn.

After (Phase 3): `set -euo pipefail`; **POSTGRES_* → DATABASE_URL/ASYNC_DATABASE_URL composition block** (no-op for docker-compose where DATABASE_URL is pre-composed); init-db; exec uvicorn.

The composition block uses `python3 -c urllib.parse.quote` for defensive URL-encoding of POSTGRES_ADMIN_PASSWORD (alphanumeric per D-11 — encoding is a no-op today but defensive against future password policy changes). Both `sslmode=require` (psycopg2/sync) and `ssl=require` (asyncpg) URL params set explicitly. The `:?` parameter expansion gives a clear error if any required POSTGRES_* var is missing.

### bootstrap-corpus.yml (A6 locked)

- **Trigger:** `workflow_dispatch` ONLY (no `push:` no `schedule:` — every cold-start re-embed would blow the OpenAI budget).
- **Input gate:** `acknowledge_cost` must be typed as `"yes"` (default `"no"`) — first job step exits non-zero otherwise.
- **OIDC handshake:** `azure/login@v2` with `id-token: write` permission, same three secrets as `deploy-api.yml` (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`); workflow_dispatch from default branch matches the master-push fed cred subject (`repo:<owner>/<repo>:ref:refs/heads/master`) — no separate fed cred needed (D-08 covered).
- **Mechanism:** `az containerapp exec --name jobrag-prod-api --resource-group jobrag-prod-rg --container api --command "/bin/sh -c 'job-rag ingest --show-cost && job-rag embed --show-cost'"`. The `/bin/sh -c` wrapper makes the command scriptable (default `az containerapp exec` is interactive/PTY-driven).
- **Summary step:** writes container app name + RG + M8 smoke pointer to `$GITHUB_STEP_SUMMARY` even on failure (`if: always()`).

## Deviations from Plan

None — plan executed exactly as written. Three minor executor-discretion choices:

1. **Dev `provider.tf` — `purge_soft_delete_on_destroy = true`** instead of mirroring prod's `false`. Reason: dev KV has `purge_protection_enabled = false` (module default for `env != "prod"`), so flipping `purge_soft_delete_on_destroy` to `true` lets `terraform destroy` actually remove the vault without manual portal cleanup. Aligns with the README's "easier teardown when dev DOES eventually apply" rationale. Not a Rule 1-3 deviation; the plan explicitly mentioned `purge_protection` in the diff list and this is the consistent behavioral pair.
2. **Dev `variables.tf` — `ghcr_pat` and `openai_api_key` carry empty-string defaults** so `terraform validate` passes without provided values (mirrors the "scaffold validates without secrets" intent in the plan's tfvars template). Prod's `ghcr_pat` had no default; dev's empty default is safe because dev never applies (real values would override at apply time anyway).
3. **Dev `main.tf` — `monitoring` module call omits the `tags` parameter being passed via different routes than prod's identical wiring.** Actually no — wired identically; this note is included only because I cross-checked the prod call signature line-by-line.

## Deferred Verification

`cd infra/envs/dev && terraform fmt -check && terraform init -backend=false && terraform validate` was NOT executed locally — Terraform CLI is not installed on this Windows workstation (verified `which terraform` returns `which: no terraform in ...`). Same posture as Plan 05a's deferred verification: the plan's success-criteria explicitly permits deferral to `static-tf.yml` CI (Plan 06) which runs the fmt/validate/tflint/tfsec gates against `infra/envs/dev/main.tf` once Plan 06 ships. Until CI green-lights this directory, treat fmt/validate as **deferred-to-CI**. Static review against the matching prod files (which Plan 05a built and the executor read in full this session) confirms:

- All 6 module input variables wired correctly with the documented diffs.
- `data.azurerm_client_config.current` reused for tenant_id_workforce + role_assignment principal_id.
- `compact([])` empty-string pattern matches prod (B1 alignment).
- `versionless_id` references on all 4 KV secrets propagate to compute module's `kv_secret_uris` map (matches prod).
- W7 composition diagnostic_setting references `module.compute.aca_id` and `module.monitoring.workspace_id` correctly.

No syntactic or wiring issues identified by manual review.

## Manual Follow-ups (Adrian)

These are NOT prerequisites for Plan 06/07 — they only matter the day Adrian actually decides to provision dev (per the README "Apply path (deferred)" section):

1. Replace `infra/envs/dev/backend.tf` `storage_account_name` placeholder with the real bootstrap output value.
2. Fill `infra/envs/dev/dev.tfvars` placeholder values: `tenant_id_external`, `seeded_user_id`. (`home_ip = "0.0.0.0"` is intentionally placeholder — dev never reaches a real Postgres firewall.)
3. Provide secrets via `terraform.tfvars.local` (gitignored) or `TF_VAR_*` env vars: `ghcr_pat`, `openai_api_key`, optional `langfuse_*`.
4. Create the GitHub protected environment `staging` + add a third federated credential to the GHA SP: `subject = "repo:adrianzaplata/job-rag:environment:staging"`.
5. Cut a `staging` branch protection rule + add `staging` to deploy-infra.yml's environment matrix (Plan 06 does prod first; this is a strict Phase 3 v2 follow-up).
6. After first deploy: `gh workflow run bootstrap-corpus.yml -f acknowledge_cost=yes` (NOT automated; deliberate manual invocation per A6).

## Self-Check: PASSED

- `infra/envs/dev/backend.tf` — exists (FOUND); `key = "dev.tfstate"` (FOUND)
- `infra/envs/dev/provider.tf` — exists (FOUND)
- `infra/envs/dev/locals.tf` — exists (FOUND); `prefix = "jobrag-dev"` (FOUND)
- `infra/envs/dev/variables.tf` — exists (FOUND)
- `infra/envs/dev/main.tf` — exists (FOUND); `env = "dev"` (FOUND); `create_budget = false` (FOUND); `use_allow_azure_services = false` (FOUND)
- `infra/envs/dev/outputs.tf` — exists (FOUND); `swa_api_key` alias (FOUND)
- `infra/envs/dev/dev.tfvars` — exists (FOUND); placeholder values (FOUND)
- `infra/envs/dev/README.md` — exists (FOUND); `scaffold-only` (FOUND)
- `scripts/docker-entrypoint.sh` — exists (FOUND); `set -euo pipefail` (FOUND); `POSTGRES_HOST` composition (FOUND); `job-rag init-db` (FOUND); `exec uvicorn` (FOUND); negative grep `job-rag ingest` count=0 (FOUND); negative grep `job-rag embed` count=0 (FOUND); exec bit set via `git update-index --chmod=+x` → file mode 100755 (FOUND in commit `692a830`).
- `.github/workflows/bootstrap-corpus.yml` — exists (FOUND); `workflow_dispatch:` (FOUND); `id-token: write` (FOUND); `azure/login@v2` (FOUND); `az containerapp exec` (FOUND); `job-rag ingest` (FOUND); `job-rag embed` (FOUND); negative grep `^[[:space:]]+push:` returns empty (FOUND); negative grep `^[[:space:]]+schedule:` returns empty (FOUND).
- Commits `677ae80`, `692a830`, `8ce9ea8` — all present in `git log` (FOUND).
