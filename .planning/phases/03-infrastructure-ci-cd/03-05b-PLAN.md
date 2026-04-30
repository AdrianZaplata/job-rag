---
phase: 03-infrastructure-ci-cd
plan: 05b
type: execute
wave: 2
depends_on: [05a]
files_modified:
  - infra/envs/dev/backend.tf
  - infra/envs/dev/provider.tf
  - infra/envs/dev/main.tf
  - infra/envs/dev/variables.tf
  - infra/envs/dev/outputs.tf
  - infra/envs/dev/locals.tf
  - infra/envs/dev/dev.tfvars
  - infra/envs/dev/README.md
  - scripts/docker-entrypoint.sh
  - .github/workflows/bootstrap-corpus.yml
autonomous: true
requirements: [DEPL-01, DEPL-02]
must_haves:
  truths:
    - "infra/envs/dev/ has the identical file set to envs/prod with backend key=dev.tfstate, dev.tfvars with placeholder values, README.md documenting D-04 scaffold-only decision; mirrors the W7 composition-layer diagnostic_setting pattern"
    - "scripts/docker-entrypoint.sh runs ONLY job-rag init-db + uvicorn (B4 locked decision — A6 addendum). Composition of DATABASE_URL/ASYNC_DATABASE_URL from POSTGRES_* parts is preserved. Corpus ingest + embed are NOT run by the entrypoint."
    - ".github/workflows/bootstrap-corpus.yml exists with workflow_dispatch ONLY trigger; uses azure/login@v2 with the same OIDC federated credential as deploy-api.yml; runs `az containerapp exec` to invoke `job-rag ingest --show-cost && job-rag embed --show-cost` against the live container"
    - "Dev env passes terraform fmt -check + terraform validate -backend=false"
  artifacts:
    - path: "scripts/docker-entrypoint.sh"
      provides: "Composes DATABASE_URL + ASYNC_DATABASE_URL from POSTGRES_* parts; runs job-rag init-db; execs uvicorn. NO ingest/embed (B4)."
    - path: ".github/workflows/bootstrap-corpus.yml"
      provides: "One-shot workflow_dispatch corpus seed via az containerapp exec (A6)"
    - path: "infra/envs/dev/main.tf"
      provides: "Dev-mirror composition (env=dev, create_budget=false, use_allow_azure_services=false)"
  key_links:
    - from: "scripts/docker-entrypoint.sh"
      to: "src/job_rag/db/engine.py"
      via: "DATABASE_URL/ASYNC_DATABASE_URL composed from POSTGRES_HOST/USER/DB/ADMIN_PASSWORD before init_db reads them"
      pattern: "DATABASE_URL"
    - from: ".github/workflows/bootstrap-corpus.yml"
      to: "azurerm_container_app.api (live ACA container)"
      via: "az containerapp exec --command 'job-rag ingest --show-cost && job-rag embed --show-cost'"
      pattern: "az containerapp exec"
    - from: ".github/workflows/bootstrap-corpus.yml"
      to: "azuread_application_federated_identity_credential.master (Plan 04 identity module)"
      via: "workflow_dispatch from default branch matches subject 'repo:<owner>/<repo>:ref:refs/heads/master'"
      pattern: "azure/login@v2"
---

<objective>
Wave 2, Plan B (split from former Plan 05 per W4): Mirror the prod composition into `infra/envs/dev/` as scaffold-only (D-04 — never applied in v1). Update `scripts/docker-entrypoint.sh` to run ONLY `job-rag init-db` + `uvicorn` (B4 locked decision; corpus bootstrap moves to a separate workflow). Create `.github/workflows/bootstrap-corpus.yml` for the one-shot corpus seed (A6 locked decision).

Purpose: Plan 05a already shipped the prod composition. This plan completes the mirror (dev scaffold), implements the B4-required entrypoint scope reduction, and creates the bootstrap-corpus workflow that A6 mandates.

Output: 10 files (8 dev env + 1 entrypoint + 1 new workflow). After this plan, the entire Phase 3 TF + CI surface is in place; Plan 06 ships the deploy workflows; Plan 07 runs the live-Azure smoke.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md
@.planning/phases/03-infrastructure-ci-cd/03-RESEARCH.md
@.planning/phases/03-infrastructure-ci-cd/03-PATTERNS.md
@infra/envs/prod/main.tf
@infra/envs/prod/variables.tf
@infra/envs/prod/outputs.tf
@infra/envs/prod/locals.tf
@infra/envs/prod/prod.tfvars
@scripts/docker-entrypoint.sh
@src/job_rag/db/engine.py

<interfaces>
<!-- Existing entrypoint (current contents — verify before edit per revision_context) -->

From `scripts/docker-entrypoint.sh` (current Phase 1+ content):
```bash
#!/bin/bash
set -e

echo "Initializing database..."
job-rag init-db

echo "Ingesting postings..."
job-rag ingest --show-cost

echo "Generating embeddings..."
job-rag embed --show-cost

echo "Starting API server..."
exec uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000
```

The B4 locked decision: drop `job-rag ingest --show-cost` and `job-rag embed --show-cost` entirely. Add the Phase 3 ACA composition block that builds DATABASE_URL/ASYNC_DATABASE_URL from POSTGRES_* env vars when running in ACA.

<!-- bootstrap-corpus.yml shape (NEW per A6) -->

The workflow uses `az containerapp exec` against the live container. The reason `az containerapp exec` over `az containerapp job` (one-shot ACA Job): no second resource type to provision in TF, simpler v1 scope. If A6 ever requires a long-running scheduled job, revisit `az containerapp job`.

`az containerapp exec` requires `--container` (the container name from compute module — `api`) and `--command` (the shell command). The container's PATH already has `job-rag` from the Docker image, so no setup step is needed inside.

Since `az containerapp exec` is interactive (PTY-driven) by default, the workflow uses `--command "/bin/sh -c '<cmd>'"` to make it scriptable.
</interfaces>

</context>

<tasks>

<task type="auto">
  <name>Task 1: Dev env scaffold (8 sibling files; never applied per D-04)</name>
  <files>
    - infra/envs/dev/backend.tf
    - infra/envs/dev/provider.tf
    - infra/envs/dev/main.tf
    - infra/envs/dev/variables.tf
    - infra/envs/dev/outputs.tf
    - infra/envs/dev/locals.tf
    - infra/envs/dev/dev.tfvars
    - infra/envs/dev/README.md
  </files>
  <read_first>
    - infra/envs/prod/backend.tf, provider.tf, main.tf, variables.tf, outputs.tf, locals.tf, prod.tfvars (Plan 05a output — dev mirrors them with key=dev.tfstate, env=dev, create_budget=false, use_allow_azure_services=false)
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md D-04 (scaffold-only — never applied)
    - infra/envs/dev/README.md (Plan 01 skeleton — Task 1's File 8 fills it)
  </read_first>
  <action>
Create 8 files in `infra/envs/dev/`. Mirror the prod env structure with three meaningful diffs:

1. `backend.tf`: `key = "dev.tfstate"` (different state file in same backend)
2. `dev.tfvars` with placeholder/dummy values
3. Module calls in `main.tf`: `env = "dev"`, `create_budget = false`, `use_allow_azure_services = false`, `purge_protection_enabled` stays at module's `var.env != "prod"` default (false)

The mechanically simpler route: literally copy the 7 prod TF files, then replace `prod` with `dev` and `local.prefix = "jobrag-dev"`, then set `create_budget = false` in the monitoring module call. README.md gets fully filled (replacing Plan 01's skeleton).

Specific file-by-file:

**`backend.tf`**: identical to prod's except `key = "dev.tfstate"`.

**`provider.tf`**: identical to prod's.

**`locals.tf`**: identical except `prefix = "jobrag-dev"` and `tags.env = "dev"`.

**`variables.tf`**: identical to prod's (same input shape; values differ via dev.tfvars).

**`main.tf`**: identical structure to prod's with these changes:
- All `env = "prod"` → `env = "dev"`
- Monitoring module call: `create_budget = false`
- Database module call: `use_allow_azure_services = false` (dev never applies, so the firewall rule wouldn't matter; documenting intent)
- KV: purge_protection picked up from module's `var.env != "prod" ? false : true` default → false
- The `azurerm_static_web_app` resource: `name = "${local.prefix}-spa"` resolves to `jobrag-dev-spa`
- The W7 composition-layer `azurerm_monitor_diagnostic_setting.aca` is included (mirrors prod for parity; dev never applies anyway)

**`outputs.tf`**: identical to prod's (same output names + the `swa_api_key` alias for parity with B2 runbook; values differ).

**`dev.tfvars`** — placeholder values:

```hcl
# Dev environment — SCAFFOLD ONLY (CONTEXT.md D-04). Never applied in v1.
# Values here exist solely so `terraform plan -var-file=dev.tfvars` is a sanity check.

location = "westeurope"

# External tenant — same as prod (D-06 — single tenant for both)
tenant_id_external = "REPLACE_FROM_BOOTSTRAP_OUTPUT"
tenant_subdomain   = "jobrag"

github_owner = "adrianzaplata"
github_repo  = "job-rag"

swa_origin = ""

# Placeholder home IP — never reaches a real Postgres firewall (dev never applies).
home_ip = "0.0.0.0"

ghcr_username = "adrianzaplata"
image_tag     = "latest"

budget_alert_email = "adrianzaplata@gmail.com"

seeded_user_id        = "REPLACE_WITH_ADRIAN_UUID"
seeded_user_entra_oid = "00000000-0000-0000-0000-000000000000"

# Application secrets — placeholders; dev never applies so these never reach KV.
# openai_api_key      = "dev-placeholder"
# langfuse_public_key = ""
# langfuse_secret_key = ""
```

**`README.md`** — REPLACE Plan 01's skeleton with:

```markdown
# Dev environment (scaffold-only)

> **Not applied in v1.** Per CONTEXT.md D-04 the dev environment is scaffold-only — `terraform plan -var-file=dev.tfvars` works as a sanity check that the module composition is internally consistent; `terraform apply` is documented but deferred. Cost stays at strict €0.

---

## Why scaffold-only?

V1 is single-user (Adrian). Provisioning a parallel dev stack would burn the €0 budget without delivering value:
- A second Postgres B1ms = ~€12/mo (free tier covers exactly one).
- A second Container App env = within consumption budget but doubles cold-start vCPU-sec usage.
- A second SWA Free = no cost (Free SKU is per-account-unlimited within reason).

Provisioning dev makes sense the day Adrian wants to break prod intentionally without taking the demo offline (e.g. testing a `pg_upgrade` or a major Phase 8 portfolio polish). Until then, scaffold stays.

## Structural parity with prod

Same six module composition, same `outputs.tf` shape — the diff is in `dev.tfvars` (placeholder values) and three module-input flags:

| Knob | Prod | Dev |
|------|------|-----|
| `env` | `"prod"` | `"dev"` |
| `module.monitoring.create_budget` | `true` | `false` (no second subscription budget) |
| `module.database.use_allow_azure_services` | `true` (A1 Path A) | `false` (dev never applies; firewall rule wouldn't matter) |
| `module.kv.purge_protection_enabled` | `true` | `false` (easier teardown when dev DOES eventually apply) |
| Backend `key` | `prod.tfstate` | `dev.tfstate` (separate state file in same backend) |

## Apply path (deferred)

When Adrian decides to provision dev:

1. Confirm the External tenant + bootstrap state backend are still healthy.
2. Create the GitHub protected environment `staging` with Adrian as required reviewer.
3. Add a third federated credential to the GHA SP: `subject = "repo:adrianzaplata/job-rag:environment:staging"`.
4. Cut a `staging` branch protection rule + add `staging` to deploy-infra.yml's environment matrix.
5. `cd infra/envs/dev && terraform apply -var-file=dev.tfvars`.

## Sanity-check command

```bash
cd infra/envs/dev
terraform fmt -check
terraform init -backend=false
terraform validate
```
```
  </action>
  <verify>
    <automated>cd infra/envs/dev && terraform fmt -check && terraform init -backend=false && terraform validate && grep -q "scaffold-only" infra/envs/dev/README.md && grep -q "key.*dev.tfstate" infra/envs/dev/backend.tf && grep -q "create_budget.*false" infra/envs/dev/main.tf</automated>
  </verify>
  <done>All 8 files exist; backend.tf uses `key = "dev.tfstate"`; main.tf passes `env = "dev"` to all modules; monitoring module call has `create_budget = false`; database module call has `use_allow_azure_services = false`; locals.tf prefix is `jobrag-dev`; dev.tfvars has placeholder values; README.md replaces Plan 01 skeleton with full scaffold rationale + structural parity table + deferred apply path; W7 composition-layer diagnostic_setting included for prod parity; outputs include the `swa_api_key` alias for B2 parity; `terraform validate` passes.</done>
</task>

<task type="auto">
  <name>Task 2: Update scripts/docker-entrypoint.sh per B4 locked decision (init-db + uvicorn ONLY)</name>
  <files>
    - scripts/docker-entrypoint.sh
  </files>
  <read_first>
    - scripts/docker-entrypoint.sh (CURRENT FILE — read full contents before editing per revision_context)
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md A6 (B4 locked decision rationale)
    - src/job_rag/db/engine.py (DATABASE_URL + ASYNC_DATABASE_URL consumer expectations)
  </read_first>
  <action>
**B4 locked decision (per CONTEXT.md A6):** the ACA entrypoint runs ONLY `job-rag init-db` + `uvicorn`. Corpus ingest (`job-rag ingest --show-cost`) and embedding (`job-rag embed --show-cost`) are MOVED to `.github/workflows/bootstrap-corpus.yml` (Task 3 of this plan).

REPLACE `scripts/docker-entrypoint.sh` entirely with the EXACT content below. Do NOT use "preserve original lines" placeholder comments — emit the full final content explicitly.

```bash
#!/bin/bash
set -euo pipefail

# Phase 3 ACA composition: when POSTGRES_HOST is set (ACA env vars from compute
# module) AND DATABASE_URL is not pre-composed, build it from the parts.
# Local docker-compose sets DATABASE_URL pre-composed so this branch is a no-op there.
if [[ -n "${POSTGRES_HOST:-}" && -z "${DATABASE_URL:-}" ]]; then
  : "${POSTGRES_USER:?POSTGRES_USER required when POSTGRES_HOST is set}"
  : "${POSTGRES_DB:?POSTGRES_DB required when POSTGRES_HOST is set}"
  : "${POSTGRES_ADMIN_PASSWORD:?POSTGRES_ADMIN_PASSWORD required when POSTGRES_HOST is set}"

  # URL-encode the password (alphanumeric per D-11 — encoding is a no-op but
  # defensive in case of future password policy change).
  ENCODED_PWD="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$POSTGRES_ADMIN_PASSWORD")"

  export DATABASE_URL="postgresql://${POSTGRES_USER}:${ENCODED_PWD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
  export ASYNC_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${ENCODED_PWD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?ssl=require"

  echo "Composed DATABASE_URL/ASYNC_DATABASE_URL from POSTGRES_* parts (ACA env)."
fi

echo "Running database migrations..."
job-rag init-db

echo "Starting API server..."
exec uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000
```

**Critical changes from the prior Phase 1 entrypoint:**
- `set -e` → `set -euo pipefail` (stricter; matches PATTERNS.md line 365-366)
- Added the POSTGRES_* → DATABASE_URL composition block (Phase 3 ACA support; no-op for docker-compose)
- **REMOVED** `job-rag ingest --show-cost` line (B4: corpus seed lives in bootstrap-corpus.yml)
- **REMOVED** `job-rag embed --show-cost` line (B4: corpus seed lives in bootstrap-corpus.yml)
- **PRESERVED** `job-rag init-db` and `exec uvicorn ...` (the only two cold-start-safe operations)

This makes every ACA cold-start cheap: just init-db (idempotent — alembic upgrade head is a no-op once at head) + uvicorn boot. No per-cold-start OpenAI cost, no minutes-long re-embed.
  </action>
  <verify>
    <automated>bash -n scripts/docker-entrypoint.sh && grep -q "POSTGRES_HOST" scripts/docker-entrypoint.sh && grep -q "DATABASE_URL" scripts/docker-entrypoint.sh && grep -q "asyncpg" scripts/docker-entrypoint.sh && grep -q "job-rag init-db" scripts/docker-entrypoint.sh && grep -q "exec uvicorn" scripts/docker-entrypoint.sh && ! grep -q "job-rag ingest" scripts/docker-entrypoint.sh && ! grep -q "job-rag embed" scripts/docker-entrypoint.sh && grep -q "set -euo pipefail" scripts/docker-entrypoint.sh</automated>
  </verify>
  <done>scripts/docker-entrypoint.sh has `set -euo pipefail` (NOT `set -e`); has the POSTGRES_* composition block at top; has `job-rag init-db`; has `exec uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000`; has NEITHER `job-rag ingest` NOR `job-rag embed` (negative grep confirms); bash -n parses cleanly. (B4 locked decision implemented in full.)</done>
</task>

<task type="auto">
  <name>Task 3: Create .github/workflows/bootstrap-corpus.yml (A6 — one-shot corpus seed)</name>
  <files>
    - .github/workflows/bootstrap-corpus.yml
  </files>
  <read_first>
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md A6 (locked decision: workflow_dispatch only, OIDC same as deploy-api.yml, az containerapp exec)
    - .github/workflows/deploy-api.yml (Plan 06 — read AFTER Plan 06 ships; OIDC pattern reference)
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md D-08 (federated credential subjects: master push subject covers workflow_dispatch from default branch)
  </read_first>
  <action>
Create `.github/workflows/bootstrap-corpus.yml`. The workflow:
- Trigger: `workflow_dispatch` ONLY (no auto-run on push or schedule)
- OIDC handshake via the same `gha-master-push` federated credential (subject `repo:<owner>/<repo>:ref:refs/heads/master`); workflow_dispatch from the default branch (master) emits this subject.
- Mechanism: `az containerapp exec --command '/bin/sh -c "job-rag ingest --show-cost && job-rag embed --show-cost"'`

Full content:

```yaml
name: Bootstrap corpus (one-shot)

# A6 (locked decision per CONTEXT.md): the ACA entrypoint runs ONLY init-db + uvicorn,
# so corpus ingest + embed live HERE — invoked manually by Adrian after first deploy
# and on PROMPT_VERSION bumps that require full re-extraction.
#
# Trigger: workflow_dispatch ONLY. NO push/schedule trigger — every cold-start re-running
# embed would blow the €0 OpenAI budget (Phase 1 D-25 + Phase 2 prompt-version drift).

on:
  workflow_dispatch:
    inputs:
      acknowledge_cost:
        description: 'Type "yes" to acknowledge that this will incur OpenAI ingest+embed cost (~€0.20 per 108-posting full re-extract).'
        required: true
        default: 'no'

permissions:
  id-token: write   # OIDC handshake to Azure (same fed cred as deploy-api.yml)
  contents: read

jobs:
  bootstrap-corpus:
    name: ingest + embed via az containerapp exec
    runs-on: ubuntu-latest
    # NOTE: no `environment: production` gate — this workflow uses the master-push
    # federated credential (workflow_dispatch from default branch matches subject
    # "repo:<owner>/<repo>:ref:refs/heads/master"). Same auth as deploy-api.yml.
    steps:
      - name: Acknowledge cost
        run: |
          if [[ "${{ inputs.acknowledge_cost }}" != "yes" ]]; then
            echo "::error::Cost not acknowledged. Re-run with input 'yes'."
            exit 1
          fi
          echo "Cost acknowledged — proceeding."

      - name: Checkout
        uses: actions/checkout@v4

      - name: Azure login (OIDC)
        uses: azure/login@v2
        with:
          client-id:       ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id:       ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Run job-rag ingest + embed inside the live container
        run: |
          # az containerapp exec runs the command inside the active revision's
          # `api` container. The container's PATH already has `job-rag` (Typer CLI
          # installed via the multi-stage Dockerfile). Stdout is streamed back to
          # the workflow log so Adrian sees ingest + embed cost reports inline.
          az containerapp exec \
            --name jobrag-prod-api \
            --resource-group jobrag-prod-rg \
            --container api \
            --command "/bin/sh -c 'job-rag ingest --show-cost && job-rag embed --show-cost'"

      - name: Print summary
        if: always()
        run: |
          {
            echo "## Corpus bootstrap result"
            echo ""
            echo "- Triggered: $(date -u +%Y-%m-%dT%H:%M:%SZ) UTC"
            echo "- Container app: jobrag-prod-api"
            echo "- Resource group: jobrag-prod-rg"
            echo ""
            echo "Verify corpus state with M8 from Plan 07 smoke (psql \\dx + row counts)."
          } >> "$GITHUB_STEP_SUMMARY"
```

**Why `az containerapp exec` over `az containerapp job`:**
- `az containerapp job` would require provisioning a separate ACA Job resource in Terraform (additional `azurerm_container_app_job` resource + per-job env wiring + secret refs).
- `az containerapp exec` runs against the existing Container App's active revision — no second resource type, no TF changes for v1.
- A6 locked decision: pick `az containerapp exec` for v1 simplicity. Revisit `az containerapp job` only if a scheduled / queue-driven corpus refresh becomes a real need.

**Why `workflow_dispatch` only:**
- Auto-running on `push` would re-embed on every code change (€).
- Auto-running on `schedule` would re-embed without operator intent.
- Manual `workflow_dispatch` with the `acknowledge_cost` input forces deliberate invocation.
  </action>
  <verify>
    <automated>test -f .github/workflows/bootstrap-corpus.yml && grep -q "workflow_dispatch:" .github/workflows/bootstrap-corpus.yml && grep -q "id-token: write" .github/workflows/bootstrap-corpus.yml && grep -q "azure/login@v2" .github/workflows/bootstrap-corpus.yml && grep -q "az containerapp exec" .github/workflows/bootstrap-corpus.yml && grep -q "job-rag ingest" .github/workflows/bootstrap-corpus.yml && grep -q "job-rag embed" .github/workflows/bootstrap-corpus.yml && ! grep -qE "^[[:space:]]+push:" .github/workflows/bootstrap-corpus.yml && ! grep -qE "^[[:space:]]+schedule:" .github/workflows/bootstrap-corpus.yml</automated>
  </verify>
  <done>.github/workflows/bootstrap-corpus.yml exists; trigger is `workflow_dispatch` ONLY (no `push:` or `schedule:` keys at the `on:` level); has `id-token: write` permission for OIDC; uses `azure/login@v2` with the same three secrets as deploy-api.yml; runs `az containerapp exec --command` invoking `job-rag ingest --show-cost && job-rag embed --show-cost`; has `acknowledge_cost` input that requires "yes" to proceed; prints summary to GITHUB_STEP_SUMMARY.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| ACA entrypoint → DATABASE_URL composition | Reads POSTGRES_* env vars (set by compute module from KV refs); composes with URL-encoding; no secret value reaches stdout. |
| bootstrap-corpus.yml → live ACA container via `az containerapp exec` | OIDC-authenticated; `az containerapp exec` requires `Container App Contributor` or higher on the Container App resource (covered by RG-scoped Contributor per D-08). |
| Adrian's manual workflow_dispatch invocation | The `acknowledge_cost: "yes"` input is a deliberate human gate (no auto-run). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-06 (HIGH — cost) | Denial of Service / Cost | bootstrap-corpus.yml | mitigate | `workflow_dispatch` ONLY (no auto-trigger); `acknowledge_cost: "yes"` input required; no scheduled re-runs. The reason this exists per A6: every ACA cold-start re-embedding the corpus would cost ~€0.20/cold-start, blowing the OpenAI budget under heavy demo days. |
| T-3-02 (MEDIUM) | Spoofing | bootstrap-corpus.yml OIDC | mitigate | Uses same `gha-master-push` federated credential as deploy-api.yml (subject covers workflow_dispatch from default branch). RG-scoped Contributor caps blast radius to `jobrag-prod-rg`. No PR trigger. |
| T-3-01 (POSTGRES_ADMIN_PASSWORD in entrypoint) | Information Disclosure | docker-entrypoint.sh | accept | The entrypoint reads `POSTGRES_ADMIN_PASSWORD` from the env (injected by ACA from KV via MI). The composed DATABASE_URL contains the password but is exported to the process env only — not echoed to stdout. The `python3 -c` URL-encoding subshell receives it as argv (visible briefly in `/proc/<pid>/cmdline`) but the container is single-tenant (only `api` container in the pod). Acceptable. |
</threat_model>

<verification>
- `cd infra/envs/dev && terraform fmt -check && terraform init -backend=false && terraform validate` exits 0
- `bash -n scripts/docker-entrypoint.sh` exits 0
- `grep -q "scaffold-only" infra/envs/dev/README.md` matches
- `! grep -q "job-rag ingest" scripts/docker-entrypoint.sh` (negative grep — corpus moved out per B4)
- `! grep -q "job-rag embed" scripts/docker-entrypoint.sh` (negative grep — corpus moved out per B4)
- bootstrap-corpus.yml triggers ONLY on workflow_dispatch
</verification>

<success_criteria>
1. Dev env scaffold (8 files) passes `terraform fmt -check` + `terraform validate -backend=false`; never applied per D-04.
2. `scripts/docker-entrypoint.sh` runs ONLY init-db + uvicorn (B4 locked decision); composition of DATABASE_URL/ASYNC_DATABASE_URL preserved; corpus ingest + embed lines REMOVED.
3. `.github/workflows/bootstrap-corpus.yml` exists with `workflow_dispatch`-only trigger and runs `job-rag ingest --show-cost && job-rag embed --show-cost` via `az containerapp exec` with the same OIDC pattern as deploy-api.yml.
4. The CONTEXT.md A6 addendum (already added during revision) is honored: entrypoint scope, bootstrap-corpus workflow.
</success_criteria>

<output>
After completion, create `.planning/phases/03-infrastructure-ci-cd/03-05b-SUMMARY.md`.
</output>
