# Phase 3: Infrastructure & CI/CD - Pattern Map

**Mapped:** 2026-04-29
**Files analyzed:** 47 (40 NEW Terraform/runbook/script files, 3 NEW GHA workflows, 0 modified backend files [env-var-injection only], 1 modified `.gitignore`, 3 modified GitHub repo settings entries)
**Analogs found:** 6 / 47 (12.7%) — Phase 3 is overwhelmingly green-field infrastructure. The remaining 41 files have NO codebase analog and rely on RESEARCH.md §Code Examples (lines 403–1217) as the canonical pattern source. See **Truthful Gaps** at the bottom.

---

## File Classification

### NEW: Bootstrap Terraform (green-field — no analog in repo)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `infra/bootstrap/main.tf` | config (IaC) | provisioning | none — green-field | none — use RESEARCH.md §Pattern 1 (lines 409–453) |
| `infra/bootstrap/identity.tf` | config (IaC import) | import | none — green-field | none — use RESEARCH.md `azuread_application` shapes (lines 1072–1143) + D-05 manual portal runbook |
| `infra/bootstrap/outputs.tf` | config (IaC) | output | none — green-field | none — use RESEARCH.md §Pattern 1 outputs (lines 450–452) |
| `infra/bootstrap/README.md` | runbook (markdown) | docs | `README.md` (repo root) | style-match only |
| `infra/bootstrap/.gitignore` (or root `.gitignore` entry) | config | n/a | repo `.gitignore` (existing) | style-match only |

### NEW: Module Terraform (green-field, six modules)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `infra/modules/network/{main,variables,outputs}.tf` + `README.md` | module (IaC) | provisioning | none | none — raw `azurerm_container_app_environment` per RESEARCH.md §Don't Hand-Roll |
| `infra/modules/database/{main,variables,outputs}.tf` + `README.md` | module (IaC) | provisioning | none | none — RESEARCH.md §Postgres Flex code (lines 853–926) |
| `infra/modules/compute/{main,variables,outputs}.tf` + `README.md` | module (IaC) | provisioning | none | none — RESEARCH.md §Pattern 4 (lines 539–632) |
| `infra/modules/identity/{main,variables,outputs}.tf` + `README.md` | module (IaC) | provisioning | none | none — RESEARCH.md §azuread (lines 1070–1143) |
| `infra/modules/monitoring/{main,variables,outputs}.tf` + `README.md` | module (IaC) | provisioning | none | none — RESEARCH.md §Diagnostic + LAW (lines 1169–1217) |
| `infra/modules/kv/{main,variables,outputs}.tf` + `README.md` | module (IaC) | provisioning | none | none — RESEARCH.md §Pattern 3 (lines 506–531) |

### NEW: Environment Terraform (green-field — `dev/` scaffold-only, `prod/` actively applied)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `infra/envs/prod/{backend,provider,main,variables,outputs}.tf` | config (IaC) | provisioning | none | none — RESEARCH.md §Pattern 2 (lines 462–497), §Static Web App (lines 1147–1165) |
| `infra/envs/prod/prod.tfvars` | config | n/a | none | none — D-10 §A1 firewall + var.home_ip + var.swa_origin |
| `infra/envs/prod/README.md` | runbook (markdown) | docs | `README.md` (repo root) | style-match only |
| `infra/envs/dev/*` (parallel set, scaffold-only) | config | provisioning | `infra/envs/prod/*` (sibling, after first write) | exact (intra-phase sibling) |
| `infra/README.md` | runbook (markdown) | docs | `README.md` (repo root) | style-match only |

### NEW: GitHub Actions deploy workflows (closest analog IS in repo)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `.github/workflows/deploy-infra.yml` | CI/CD pipeline | event-driven (push + workflow_dispatch) | `.github/workflows/ci.yml` | partial-role-match (extract YAML structure, OIDC adds new pieces) |
| `.github/workflows/deploy-api.yml` | CI/CD pipeline | event-driven (push, paths-filtered) | `.github/workflows/ci.yml` | partial-role-match (same harness, different action set) |
| `.github/workflows/deploy-spa.yml` | CI/CD pipeline | event-driven (push, paths-filtered) | `.github/workflows/ci.yml` | partial-role-match (Node toolchain instead of Python) |

### NEW: Operational scripts (no analog; bash glue)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `scripts/refresh-swa-origin.sh` | utility (shell) | one-shot transform | `scripts/docker-entrypoint.sh` | partial — same `set -e` shebang style; very different purpose |
| `scripts/firewall-update-home-ip.sh` (optional, per Discretion) | utility (shell) | one-shot CRUD | `scripts/docker-entrypoint.sh` | partial — style only |

### MODIFIED: existing repo files (config-only, no source code change)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `.gitignore` (add `infra/bootstrap/*.tfstate*`, `infra/**/.terraform/`, `*.tfplan`) | config | n/a | itself (existing entries) | exact |
| GitHub repo settings → protected environment `production` (out-of-tree) | config | n/a | none | n/a — portal/`gh` CLI |
| GitHub repo settings → secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` | config | n/a | none | n/a — `gh secret set` |

### NOT MODIFIED in Phase 3 (despite conceptual coupling)

| File | Why Phase 3 leaves it alone |
|------|----------------------------|
| `src/job_rag/api/app.py` | CORSMiddleware already accepts `settings.allowed_origins` from env (lines 142–148). Phase 3 only **injects the env var at deploy time** via `azurerm_container_app.template.container.env { name = "ALLOWED_ORIGINS"; value = local.allowed_origins_csv }`. Zero code change. |
| `src/job_rag/config.py` | `allowed_origins: Annotated[list[str], NoDecode]` already CSV-aware (lines 34, 50–56). Phase 3 only injects the value. Zero code change. |
| `Dockerfile` | Multi-stage CPU-only PyTorch build is final. Phase 3 builds + tags it (`ghcr.io/<owner>/job-rag:${{ github.sha }}` + `:latest`) and pushes to GHCR. Zero Dockerfile change. |
| `scripts/docker-entrypoint.sh` | Phase 3 only **prepends** `DATABASE_URL`/`ASYNC_DATABASE_URL` composition into the container env (via ACA `secret_name` references); the entrypoint script itself stays identical. May add inline `export` lines if `init_db` needs them — but verify in plan; current script already calls `job-rag init-db` which reads from settings. |
| `.github/workflows/ci.yml` | Per CONTEXT.md `<canonical_refs>` line 140: "Phase 3 adds three NEW workflows but does NOT touch ci.yml." |
| `tests/**`, `alembic/**`, `pyproject.toml`, `uv.lock` | Per VALIDATION.md scope: Phase 3 does NOT add tests, migrations, or dep changes. |

---

## Pattern Assignments

### `.github/workflows/deploy-infra.yml` (CI/CD pipeline, event-driven)

**Analog:** `.github/workflows/ci.yml` (the only existing GHA workflow in the repo)

**Imports/header pattern** (`ci.yml` lines 1–8):
```yaml
name: CI
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
```

**Adapt for `deploy-infra.yml`:**
- Replace trigger with `paths: ['infra/**', '.github/workflows/deploy-infra.yml']` + `workflow_dispatch`.
- Add `environment: production` to the job (NEW concept — protected env gate per A2 + D-08 cred #2).
- Add `permissions: { id-token: write, contents: read }` (NEW — required for OIDC; `ci.yml` doesn't have this because it never authenticates outward).

**Action invocation pattern** (`ci.yml` lines 26–37):
```yaml
- uses: actions/checkout@v4
- name: Install uv
  uses: astral-sh/setup-uv@v4
  with:
    enable-cache: true
- name: Set up Python
  run: uv python install 3.12
- name: Install dependencies
  run: uv sync --frozen
```

**Adapt:** Same `actions/checkout@v4` pattern. Replace uv setup with `hashicorp/setup-terraform@v3` + `azure/login@v2`. RESEARCH.md §Three GHA workflows lines 952–976 has the concrete sequence; copy verbatim modulo project-specific variable names.

**Secrets injection pattern** (`ci.yml` lines 58–62 — service env, not GH secrets):
```yaml
env:
  DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
```

**Adapt:** GH secrets get referenced as `${{ secrets.AZURE_CLIENT_ID }}` instead — `ci.yml` doesn't model this, so use RESEARCH.md lines 957–961 as the pattern source.

---

### `.github/workflows/deploy-api.yml` (CI/CD pipeline, event-driven, paths-filtered)

**Analog:** `.github/workflows/ci.yml`

**Reuse:** The exact `actions/checkout@v4` + `paths:` filter pattern. Add Docker buildx + GHCR push steps that have NO analog in `ci.yml` — copy verbatim from RESEARCH.md lines 1001–1015.

**`paths:` filter rationale (D-08, D-04 spec):** keeps the three deploy workflows independent — push that touches only `apps/web/**` triggers `deploy-spa.yml` only, etc.

**Adapt for `deploy-api.yml`:** Use the master-push subject federated credential (D-08 cred #1), not the environment one. RESEARCH.md lines 1019–1027 has the `az containerapp update --image ghcr.io/...` step.

---

### `.github/workflows/deploy-spa.yml` (CI/CD pipeline, event-driven, Node toolchain)

**Analog:** `.github/workflows/ci.yml` (Python toolchain — only the harness pattern transfers)

**Reuse:** `actions/checkout@v4`, top-level `name`, `on.push.paths:`, `runs-on: ubuntu-latest`, `jobs.<name>.steps:` skeleton.

**Replace:** `astral-sh/setup-uv@v4` + `uv run *` with `actions/setup-node@v4` + `npm ci` + `npm run build`. SWA-specific deploy step has no analog — use RESEARCH.md lines 1058–1066 (`Azure/static-web-apps-deploy@v1`).

**Note:** SWA deploy uses `azure_static_web_apps_api_token` (the long-lived secret per A2/D-08 — only non-OIDC auth in Phase 3), NOT OIDC. So this workflow does NOT need `permissions: { id-token: write }` for the deploy step itself — only if `azure/login@v2` is also called (it isn't, per RESEARCH.md skeleton).

---

### `scripts/refresh-swa-origin.sh` (utility, one-shot transform)

**Analog:** `scripts/docker-entrypoint.sh` (lines 1–15 — only existing shell script in the repo)

**Imports/header pattern** (`docker-entrypoint.sh` lines 1–2):
```bash
#!/bin/bash
set -e
```

**Adapt:** Use `set -euo pipefail` (stricter — RESEARCH.md line 646 uses this). Same shebang style.

**Sequencing pattern** (`docker-entrypoint.sh` — sequential commands, fail-fast):
```bash
echo "Initializing database..."
job-rag init-db

echo "Ingesting postings..."
job-rag ingest --show-cost
```

**Adapt:** Same sequential `command || exit` style. Use `cd "$(dirname "$0")/../infra/envs/prod"` (RESEARCH.md line 647) + `terraform output -raw swa_default_origin` + idempotent `sed -i.bak` + re-`apply`. Full script in RESEARCH.md lines 643–660; copy verbatim.

**Idempotency note (per CONTEXT.md A3 + user's `feedback_reusable_tools.md` memory):** the script uses `if grep -q '^swa_origin' prod.tfvars; then sed ... else echo ... >> ... fi` so re-runs on the same SWA origin produce a no-op `apply`. This satisfies the user's "idempotent selection" preference while staying as a `scripts/`-folder one-shot (low reuse expected, NOT folded into the `job-rag` Typer CLI).

---

### `infra/envs/prod/README.md` (runbook, markdown)

**Analog:** `README.md` (repo root) — only existing markdown of comparable size + structure

**Style pattern** (`README.md` lines 1–8):
```markdown
# Job RAG

> A RAG system I built during a pivot into AI engineering — to read AI Engineer job postings and tell me which skills I'm missing so I can go learn them.

It ingests raw LinkedIn markdown into structured skill data, identifies gaps...

---
```

**Reuse:** First-line `#` title + blockquote one-liner abstract + horizontal rule between sections. Mermaid diagrams are valid (root README uses them).

**Section structure (root README has):** Architecture / Stack / Setup / Usage. Adapt for prod runbook: **Bootstrap** / **First apply pass** / **Two-pass CORS apply** (DEPL-12 + A3) / **Image push** / **Verification checklist** / **Knowingly-accepted security trade-offs** (per A1: document `0.0.0.0` firewall rule + 32-char password as the security boundary).

**Tables for ops checklists** (root README lines 17–24 — IU Group fit table):
```markdown
| IU Group | Job RAG |
|---|---|
| Build agentic AI systems | LangGraph ReAct agent |
```

**Adapt:** Use the same compact `| col | col |` style for "What this resource does / Where its state lives / How to debug" tables.

---

### `infra/bootstrap/README.md` (runbook, markdown)

**Analog:** `README.md` (repo root) — same style guide as `infra/envs/prod/README.md`

**Specific content (per D-05):** portal click-path for manual External tenant creation, then `terraform import` command. PITFALLS §1 note: External ID admin UX is changing, so include a "Last verified: 2026-04-DD" timestamp at top.

---

### `.gitignore` (existing, MODIFIED — add Terraform exclusions)

**Analog:** itself

**Pattern:** the existing `.gitignore` already excludes Python build artifacts. Phase 3 appends a `# Terraform` block:
```gitignore
# Terraform (Phase 3 — bootstrap state must NEVER be committed; prod state is in Azure Blob)
infra/bootstrap/.terraform/
infra/bootstrap/terraform.tfstate*
infra/bootstrap/.terraform.lock.hcl
infra/envs/*/.terraform/
infra/envs/*/.terraform.lock.hcl
*.tfplan
```

(Lock files are debatable — convention is to commit them. Above is the conservative version; the planner should pick one with rationale.)

---

## Shared Patterns

### Project conventions (apply to all NEW Terraform files)

**Source:** CONTEXT.md `<decisions>` Claude's Discretion section (lines 68–82) + RESEARCH.md §Recommended Project Structure (lines 330–401)

**Naming:** `jobrag-{env}-{kind}` (e.g., `jobrag-prod-aca-env`, `jobrag-prod-pg`, `jobrag-prod-kv`). Centralize in `infra/envs/{env}/locals.tf`:
```hcl
locals {
  prefix = "jobrag-${var.env}"
  tags   = { project = "job-rag", env = var.env, managed_by = "terraform" }
}
```

**Tags:** every resource carries `tags = local.tags` (or `var.tags` from module-level passthrough).

**Provider pins:** `azurerm ~> 4.69`, `azuread ~> 3.0`, `random ~> 3.6` per STACK.md and Discretion.

**Apply to:** all `infra/modules/*/main.tf`, all `infra/envs/*/provider.tf`.

---

### OIDC authentication (apply to all three deploy workflows)

**Source:** RESEARCH.md §Three GHA workflows (lines 957–961, 1017–1021); CONTEXT.md D-08, A4

```yaml
permissions:
  id-token: write     # OIDC handshake
  contents: read

# ...
- uses: azure/login@v2
  with:
    client-id:       ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id:       ${{ secrets.AZURE_TENANT_ID }}        # workforce tenant per A4
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

**Apply to:** `deploy-infra.yml` (uses environment-subject cred), `deploy-api.yml` (uses master-push-subject cred), `deploy-spa.yml` (only if calling `azure/login` — current skeleton does not).

**Trigger-shape contract (D-08):**
| Workflow | Subject | GH trigger |
|----------|---------|------------|
| `deploy-infra.yml` | `repo:adrianzaplata/job-rag:environment:production` | `push` to master + `environment: production` gate |
| `deploy-api.yml` | `repo:adrianzaplata/job-rag:ref:refs/heads/master` | `push` to master |
| `deploy-spa.yml` | (uses long-lived `AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` instead) | `push` to master |

---

### KV-backed secret references (apply to compute module + all secret consumers)

**Source:** RESEARCH.md §Pattern 4 (lines 539–632); CONTEXT.md D-13

**Anti-pattern to avoid (loud-fail in TF state):**
```hcl
# DON'T — pulls secret value into TF state
data "azurerm_key_vault_secret" "openai" { name = "openai-api-key"; key_vault_id = ... }
env { name = "OPENAI_API_KEY"; value = data.azurerm_key_vault_secret.openai.value }
```

**Correct pattern (URI reference, value never in state):**
```hcl
secret {
  name                = "openai-api-key"
  identity            = "System"        # literal string, system-assigned MI
  key_vault_secret_id = var.kv_secret_uris["openai-api-key"]
}
container {
  env { name = "OPENAI_API_KEY"; secret_name = "openai-api-key" }
}
```

**Apply to:** `infra/modules/compute/main.tf` (5 secrets per D-13: `openai-api-key`, `postgres-admin-password`, `langfuse-public-key`, `langfuse-secret-key`, `seeded-user-entra-oid`).

---

### Resource ordering (apply to envs/prod/main.tf)

**Source:** RESEARCH.md lines 864–872; CONTEXT.md `<code_context>` line 171 ("TF dependency ordering: KV secret + access role assignment created BEFORE Container App resource")

**Pattern:** Use explicit `depends_on = [var.kv_admin_role_assignment_id]` on KV secrets that get written DURING the apply (not just at module-graph layer) — Azure's RBAC propagation is eventually consistent and can race. Specifically:
1. Create KV first.
2. Assign current deployer "Key Vault Secrets Officer" role.
3. Then write secrets (with `depends_on` on the role assignment).
4. Then create ACA Container App with system-assigned MI.
5. Then assign ACA's MI "Key Vault Secrets User" role.
6. Then secret references resolve at container start.

---

### Two-pass CORS apply (apply to envs/prod only — not modules)

**Source:** RESEARCH.md §Pattern 5 (lines 636–677); CONTEXT.md D-14, A3, DEPL-12

**Pattern (locals composition):**
```hcl
locals {
  allowed_origins_csv = join(",", compact([var.swa_origin, "http://localhost:5173"]))
}
module "compute" {
  allowed_origins = local.allowed_origins_csv
  # ...
}
```

**Why CSV not list:** matches `src/job_rag/config.py` line 34's `Annotated[list[str], NoDecode]` + `_split_origins` validator — CSV is the wire format the existing FastAPI Settings model already accepts. Zero backend code change.

**Apply to:** `infra/envs/prod/main.tf` only. Dev scaffold (D-04) sets `var.swa_origin = ""` placeholder — `compact()` drops empties, so `allowed_origins_csv` resolves to `"http://localhost:5173"` and `terraform plan` succeeds even though dev is never `apply`d.

---

### Markdown style (apply to all four `README.md` files Phase 3 ships)

**Source:** `README.md` (repo root)

- `# Title` + blockquote abstract + horizontal rule sections
- Tables for compact comparison data (`| col | col |`)
- Mermaid diagrams allowed (root README uses them in Architecture section)
- Inline code with backticks for command names + paths
- "Last verified: YYYY-MM-DD" timestamps recommended for portal-click-path content (External ID UX is changing per PITFALLS §1)

**Apply to:** `infra/README.md`, `infra/bootstrap/README.md`, `infra/envs/prod/README.md`, `infra/envs/dev/README.md`, all six `infra/modules/*/README.md`.

---

### Shell script style (apply to `scripts/refresh-swa-origin.sh` and any future `scripts/*.sh`)

**Source:** `scripts/docker-entrypoint.sh`

- `#!/bin/bash` shebang
- `set -e` minimum (`set -euo pipefail` preferred for one-shot ops glue per RESEARCH.md line 646)
- Sequential commands with `echo "doing X..."` progress logging — same style as docker-entrypoint
- File rights: `chmod +x` after first commit (Dockerfile line 37 documents the convention `RUN chmod +x /app/docker-entrypoint.sh`)

---

## No Analog Found (Truthful Gaps)

Files with no close match in the codebase. Planner SHOULD use RESEARCH.md §Code Examples as the canonical pattern source for these — not invent novel structures or hand-roll from first principles.

| File or class of file | Role | Data Flow | Reason | Pattern source |
|------|------|-----------|--------|----------------|
| `infra/bootstrap/*.tf` | IaC | provisioning | Repo has zero existing Terraform | RESEARCH.md lines 409–453 (Pattern 1) |
| `infra/modules/network/main.tf` | IaC | provisioning | No existing ACA env code | RESEARCH.md §Don't Hand-Roll line 696 + RESEARCH.md `azurerm_container_app_environment` references throughout |
| `infra/modules/database/main.tf` | IaC | provisioning | No existing Postgres provisioning code | RESEARCH.md lines 853–926 (full module body) |
| `infra/modules/compute/main.tf` | IaC | provisioning | No existing ACA Container App code | RESEARCH.md lines 539–632 (Pattern 4 — full body) |
| `infra/modules/identity/main.tf` | IaC | provisioning | No existing azuread code | RESEARCH.md lines 1070–1143 (full body) |
| `infra/modules/monitoring/main.tf` | IaC | provisioning | No existing diagnostic + budget code | RESEARCH.md lines 1169–1217 (full body) |
| `infra/modules/kv/main.tf` | IaC | provisioning | No existing KV code | RESEARCH.md lines 506–531 (Pattern 3) |
| `infra/envs/{dev,prod}/backend.tf` | IaC | state | No existing remote backend config | RESEARCH.md lines 469–497 (Pattern 2) |
| `infra/envs/{dev,prod}/provider.tf` | IaC | provider config | No existing provider blocks | RESEARCH.md lines 486–497 + STACK.md pin guidance |
| `infra/envs/prod/main.tf` | IaC | module composition | No existing top-level env file | RESEARCH.md lines 664–676 (locals + module call) + Static Web App lines 1149–1165 |
| `infra/envs/prod/outputs.tf` | IaC | output | No existing outputs file | RESEARCH.md lines 727–738 (Phase 4 hand-off output bundle) |
| `infra/envs/prod/prod.tfvars` | config | n/a | No existing tfvars | A1: `home_ip`, `use_allow_azure_services = true`, `swa_origin` (placeholder pre-pass-2), `tenant_id_external`, `tenant_subdomain`, `budget_alert_email` |

**Why this matters for the planner:** the lift here is "translate the RESEARCH.md skeletons into module-shaped, variable-parameterized Terraform" — not "extend an existing pattern." Treat RESEARCH.md as the analog. Do NOT cite the FastAPI app or any Python file as a pattern source for IaC files; the only legitimate cross-file references are config.py (CSV CORS contract) and app.py (CORSMiddleware confirmation that Phase 3's env-var injection lands correctly with zero code change).

---

## A5 Spike (planner-time, not pattern-relevant)

CONTEXT.md A5 flags: AVM `avm/res/db-for-postgresql/flexible-server@0.2.2` `server_configuration` shape needs verification at plan time. The planner's first execution task in the database module plan should run `terraform-docs markdown table .` against the pinned module to confirm the key shape compiles. RESEARCH.md uses `extensions_allowlist = { name = "azure.extensions", value = "VECTOR" }` — if the live shape differs, update the plan, not this PATTERNS.md (no code analog exists either way).

---

## Metadata

**Analog search scope:** `.github/workflows/`, `scripts/`, `src/job_rag/api/`, `src/job_rag/config.py`, `Dockerfile`, `docker-compose.yml`, repo-root `README.md`, `.gitignore`. No `infra/` directory exists pre-Phase-3.
**Files scanned (read in full):** 6 (`ci.yml`, `docker-entrypoint.sh`, `app.py`, `config.py`, `Dockerfile`, `README.md` partial).
**Pattern extraction date:** 2026-04-29.
**Skills directory:** `.claude/skills/` and `.agents/skills/` not present in the repo (per CLAUDE.md "No project skills found").
**User memory observed:** `feedback_reusable_tools.md` — applied to `scripts/refresh-swa-origin.sh` keep-as-script decision (matches CONTEXT.md A3 + Reusable-tool framing reminder).
