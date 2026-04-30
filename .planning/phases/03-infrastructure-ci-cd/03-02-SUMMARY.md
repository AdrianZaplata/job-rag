---
phase: 03-infrastructure-ci-cd
plan: 02
subsystem: infra
tags: [terraform, azure, bootstrap, entra-external-id, state-backend, runbook]

# Dependency graph
requires:
  - phase: 03-infrastructure-ci-cd
    provides: Static-TF lint harness + runbook skeleton + Terraform .gitignore (Plan 01)
  - service: azure-portal
    provides: Manually-created Entra External tenant (D-05 — tenant_id 3fd51a76-f36e-43a1-aa37-564dad4c41fd, subdomain "jobrag")
provides:
  - Bootstrap Terraform tree (main.tf + identity.tf + outputs.tf) — RG + Storage Account (versioning + 7d soft-delete) + tfstate container, NO backend block (LOCAL state per D-02)
  - Aliased azuread.external provider scoped to the External tenant (A4 separation from workforce default provider)
  - Six outputs (storage_account_name, container_name, resource_group_name, tenant_id_external, tenant_subdomain, external_tenant_object_id) consumed by Plans 04/06
  - Filled bootstrap README runbook — 4-step click-path + apply + outputs-into-backend + no-op-import documentation + Knowingly-accepted security trade-offs section
affects: [03-04-envs-prod, 03-05a, 03-05b, 03-06-envs-dev, 03-07-deploy]

# Tech tracking
tech-stack:
  added:
    - hashicorp/azurerm ~> 4.69 (Terraform provider, pinned in bootstrap main.tf)
    - hashicorp/azuread ~> 3.0 (Terraform provider, default + aliased "external" instance)
    - hashicorp/random ~> 3.6 (Terraform provider, 5-char suffix for storage account global uniqueness)
  patterns:
    - "Bootstrap-with-LOCAL-state pattern (no backend block) — solves Azure Storage chicken-and-egg per D-02"
    - "Aliased azuread provider for cross-tenant work — default = workforce tenant (A4), alias.external = External tenant (D-05)"
    - "data \"azuread_client_config\" as soft import anchor — confirms tenant reachable, supports depends_on without a tenant-creation resource"
    - "Variable-for-tenant pattern — tenant_id_external captured as TF variable so it flows into envs/prod/identity.tf without re-prompting"

key-files:
  created:
    - infra/bootstrap/main.tf
    - infra/bootstrap/identity.tf
    - infra/bootstrap/outputs.tf
  modified:
    - infra/bootstrap/README.md

key-decisions:
  - "main.tf has NO backend block — bootstrap intentionally uses LOCAL state per D-02. .gitignore Terraform block (Plan 01) keeps terraform.tfstate out of commits. Confirmed via grep: no `backend \"azurerm\"` substring anywhere in infra/bootstrap/."
  - "Default azuread provider in main.tf has empty config — relies on subscription's home (workforce) tenant per A4. Aliased provider azuread.external in identity.tf takes tenant_id explicitly to scope to the External tenant only."
  - "No `terraform import` command shipped — `azuread ~> 3.x` (April 2026) has no first-class tenant resource; the External tenant's GUID lives as a TF variable and flows into Phase 4's app registrations and Plan 04's prod composition. README Step 4 documents this as the deliberate no-op."
  - "Output description for tenant_subdomain uses literal angle-bracket placeholders `<tenant_subdomain>` not `${tenant_subdomain}` — the latter would have been parsed as a Terraform interpolation against an undefined symbol at plan/apply time. Plan-spec text quoted Markdown `${...}` which is invalid in HCL. Auto-fixed under Rule 1 (bug — code wouldn't have compiled)."

patterns-established:
  - "Pattern: aliased azuread provider for two-tenant topologies. Default provider config (empty) inherits from `az login` context (workforce tenant); alias \"external\" with explicit tenant_id targets the second tenant. Reusable any time a TF root needs to operate against >1 tenant simultaneously."
  - "Pattern: random_string suffix for globally-unique resource names. `length=5, upper=false, special=false, numeric=true` produces a 5-char [a-z0-9] suffix that meets storage-account constraints (3-24 chars, lowercase alphanumeric). Reusable for any Azure resource with a global namespace (storage, KV, container apps env, etc.)."
  - "Pattern: documented Step 4 \"no-op\" with conditional resurrection note. When a Terraform-conventional step is intentionally skipped because of provider limitations, document WHY in the runbook AND name the future condition that would re-activate it. Audit-friendly: future readers see the deliberate choice and the trigger to revisit."

requirements-completed: [DEPL-01]

# Metrics
duration: ~7m
completed: 2026-04-30
---

# Phase 3 Plan 02: Bootstrap Terraform Tree Summary

**Created the `infra/bootstrap/` Terraform tree (main.tf + identity.tf + outputs.tf + filled README runbook) that solves the Azure-Storage-state chicken-and-egg via LOCAL state and provides the import-anchor scaffolding for the manually-created Entra External tenant.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-30 (executor session, sequential mode)
- **Completed:** 2026-04-30
- **Tasks executed:** 2 of 3 (Task 1 was a checkpoint:human-action — Adrian had already completed the manual Entra External tenant creation BEFORE this executor ran; tenant_id 3fd51a76-f36e-43a1-aa37-564dad4c41fd captured in `.planning/phases/03-infrastructure-ci-cd/bootstrap-secrets.local.md`, gitignored)
- **Files created:** 3 (.tf)
- **Files modified:** 1 (README.md — replaced Plan 01 skeleton with full runbook)

## Accomplishments

- `infra/bootstrap/main.tf` — RG `jobrag-tfstate-rg` (westeurope) + Storage Account `jobragtfstate${random_string.suffix.result}` (Standard LRS, versioning + 7d soft-delete) + `tfstate` private container + 5-char random suffix for global-uniqueness; provider pins azurerm `~> 4.69`, azuread `~> 3.0`, random `~> 3.6`; **NO `backend "azurerm"` block** — confirms LOCAL state per D-02
- `infra/bootstrap/identity.tf` — `tenant_id_external` (required) + `tenant_subdomain` (default `"jobrag"`) variables; aliased `azuread.external` provider scoped to the External tenant per A4; `data "azuread_client_config" "external"` data source as a soft import anchor that other resources can `depends_on`
- `infra/bootstrap/outputs.tf` — six outputs: `storage_account_name`, `container_name`, `resource_group_name` (consumed by Plans 04/06's `backend.tf`) + `tenant_id_external`, `tenant_subdomain`, `external_tenant_object_id` (consumed by Phase 4 MSAL authority composition)
- `infra/bootstrap/README.md` — Plan 01 skeleton fully filled: `**Last verified:** 2026-04-29` timestamp + Prerequisites + 4 Step sections (portal click-path with concrete tenant name/domain/RG; `terraform.tfvars.local` template + `terraform init -backend=false` + `terraform apply` commands; literal `backend.tf` copy example; D-05 no-op-import documentation) + "Knowingly-accepted security trade-offs" section (local state / LRS / public network access RBAC-gated)

## Task Commits

Each task was committed atomically:

1. **Task 2: Bootstrap TF tree** (main.tf + identity.tf + outputs.tf) — `8fb1bdf` (feat)
2. **Task 3: Fill bootstrap README runbook** — `cb599b8` (docs)

**Plan metadata:** _(this commit)_

(Task 1 was a checkpoint:human-action that Adrian completed in a prior session — captured via `.planning/phases/03-infrastructure-ci-cd/bootstrap-secrets.local.md`. No code commit corresponds to it.)

## Files Created/Modified

- `infra/bootstrap/main.tf` — bootstrap RG + Storage Account + tfstate container; provider pins; NO backend block (LOCAL state)
- `infra/bootstrap/identity.tf` — tenant_id_external + tenant_subdomain variables + aliased azuread.external provider + azuread_client_config data source
- `infra/bootstrap/outputs.tf` — six outputs for downstream Plans 04/06 + Phase 4 MSAL authority
- `infra/bootstrap/README.md` — replaced Plan 01 skeleton with filled runbook (Prerequisites + Steps 1–4 + Trade-offs)

## Decisions Made

- **Output description string fix.** The plan body specified `description = "External tenant subdomain — Phase 4 builds the MSAL authority URL https://${tenant_subdomain}.ciamlogin.com/${tenant_id}/v2.0."` for `output "tenant_subdomain"`. In HCL string interpolation, `${tenant_subdomain}` references a symbol (and `tenant_subdomain` is not a defined name in that scope). At apply time Terraform would have errored ("Unknown variable"). Replaced with literal angle-bracket placeholders `<tenant_subdomain>` and `<tenant_id>` so the description renders as documentation only. Tracked as deviation Rule 1 below.
- **No live `terraform fmt -check` / `terraform validate` run.** Terraform CLI is not installed on the executor host (Windows; `which terraform` returned not-found) and the user explicitly instructed: "You also do NOT need to actually run `terraform init` / `terraform apply` against live Azure. The plan's must-haves are about the **files existing and being shaped correctly** so Adrian can apply them himself." Files were hand-written in canonical HCL style (2-space indent, aligned `=`, blank lines between resources, lowercase keywords) that matches `terraform fmt`'s default output exactly. Adrian should run `cd infra/bootstrap && terraform fmt -check && terraform init -backend=false && terraform validate` locally before Step 2 of the runbook (the Plan 01 `static-tf.yml` workflow will also run these on the next PR that touches `infra/**`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HCL interpolation in output description**
- **Found during:** Task 2 (writing outputs.tf)
- **Issue:** Plan body specified `description = "... https://${tenant_subdomain}.ciamlogin.com/${tenant_id}/v2.0."` for the `tenant_subdomain` output. HCL parses `${...}` inside a quoted string as an interpolation; `tenant_subdomain` and `tenant_id` are not in scope at output-description evaluation time, so `terraform validate` would have failed with "Unknown variable" (or at minimum produced a misleading error trace).
- **Fix:** Replaced both interpolations with literal angle-bracket placeholders: `https://<tenant_subdomain>.ciamlogin.com/<tenant_id>/v2.0.`. Description now renders as plain documentation. Same intent, no compilation hazard.
- **Files modified:** `infra/bootstrap/outputs.tf` (output `tenant_subdomain`, description string only)
- **Commit:** `8fb1bdf`

### Deferred / Manual Follow-up

- **`terraform fmt -check` + `terraform validate`** — not run by this executor (no Terraform CLI on host). The success-criteria checkbox for these stays open until Adrian runs them locally. File format matches canonical HCL by hand-written convention; risk of failure is low but non-zero.
- **`terraform init -backend=false && terraform apply`** — explicitly NOT run per user instruction (no live Azure provisioning in this plan). Adrian executes Step 2 of the README runbook himself when he's ready to provision the state backend.
- **Filling `bootstrap-secrets.local.md` storage backend section** — `resource_group_name`, `storage_account_name`, `container_name` will be filled after Adrian runs `terraform apply` and `terraform output -raw <name>`. Not a deviation, just the natural runbook flow.

## Issues Encountered

None functionally. CRLF warnings from git on Windows are expected (`core.autocrlf` default) and do not affect commit content.

## Authentication Gates

Task 1 was framed as a `checkpoint:human-action` for the manual Entra External tenant creation. Per the executor prompt's `<critical_user_context>`, Adrian had already completed the portal click-path before this session: tenant_id `3fd51a76-f36e-43a1-aa37-564dad4c41fd`, primary domain `jobrag.onmicrosoft.com`, CIAM authority `jobrag.ciamlogin.com`, subdomain `jobrag`. Values are stored in `.planning/phases/03-infrastructure-ci-cd/bootstrap-secrets.local.md` (gitignored — verified via `git check-ignore`). No checkpoint return needed; treated as completed prerequisite.

## User Setup Required

Before Adrian runs `terraform apply` in `infra/bootstrap/`:

1. **Install Terraform 1.9+** on local machine (`choco install terraform` or `brew install terraform`).
2. **`az login`** with the account that owns the Azure subscription `f9846fbe-e2f2-4220-b714-5dc3ca4059a2` (Owner role required for the first apply).
3. **`az account set --subscription "f9846fbe-e2f2-4220-b714-5dc3ca4059a2"`** to scope CLI calls.
4. **Create `infra/bootstrap/terraform.tfvars.local`** (gitignored via Plan 01's `.gitignore` rules — `*.tfvars.local` is in the Terraform block) with:
   ```hcl
   tenant_id_external = "3fd51a76-f36e-43a1-aa37-564dad4c41fd"
   tenant_subdomain   = "jobrag"
   ```
5. **Run** `terraform init -backend=false && terraform apply -var-file=terraform.tfvars.local`.
6. **Capture three outputs** (`terraform output -raw storage_account_name`, `container_name`, `resource_group_name`) for use by Plans 04/06's `backend.tf` files.
7. **Optionally append the captured outputs to `bootstrap-secrets.local.md`** Storage backend section for convenience (file remains gitignored).

## Next Phase Readiness

- **Plan 03 unblocked** (App registrations: SPA + API in the External tenant). Plan 03 will use the `azuread.external` provider alias from `infra/bootstrap/identity.tf`'s pattern — but Plan 03 likely lives in a separate root module (`infra/envs/prod/identity.tf` or a dedicated `infra/modules/identity/`); aliased provider needs to be re-declared there with `tenant_id = var.tenant_id_external`. Pattern transfers; resource scope does not.
- **Plan 04 unblocked** (envs/prod composition). The three storage outputs (`storage_account_name`, `container_name`, `resource_group_name`) are the literal inputs to `infra/envs/prod/backend.tf` per D-02. Adrian copies them in after running `terraform apply` here, BEFORE `terraform init` in `infra/envs/prod/`.
- **Phase 4 MSAL authority composition** — `tenant_subdomain` and `tenant_id_external` outputs feed the eventual Vite-built MSAL config: `https://${tenant_subdomain}.ciamlogin.com/${tenant_id_external}/v2.0`. Output names are stable and downstream-friendly.

## Threat Flags

None. The plan's threat register (T-3-01, T-3-07, T-3-02) was honored:

- **T-3-01 (Information Disclosure / local tfstate)** — mitigated by Plan 01's `.gitignore` (Terraform block at tail covers `infra/bootstrap/terraform.tfstate*` + `*.tfvars.local`) + this plan's NO-backend confirmation in main.tf. `git check-ignore` on `bootstrap-secrets.local.md` returned the path (still ignored).
- **T-3-07 (Tampering / wrong tenant type)** — mitigated by README Step 1's explicit `Tenant type: **External** (NOT Workforce, NOT B2C — PITFALLS §1)` callout + the `**Last verified: 2026-04-29**` timestamp + the A4-driven separation between default (workforce) and aliased (external) azuread providers.
- **T-3-02 (Tampering / interactive bootstrap apply)** — accepted; bootstrap runs under Adrian's interactive Owner credentials. This is the intentional first-apply model.

## Self-Check: PASSED

Verified on disk:
- `[ -f infra/bootstrap/main.tf ]` — FOUND
- `[ -f infra/bootstrap/identity.tf ]` — FOUND
- `[ -f infra/bootstrap/outputs.tf ]` — FOUND
- `[ -f infra/bootstrap/README.md ]` — FOUND (4955 bytes, replaces 30-line skeleton)
- `git log --oneline | grep 8fb1bdf` — FOUND ("feat(03-02): bootstrap TF tree...")
- `git log --oneline | grep cb599b8` — FOUND ("docs(03-02): fill bootstrap README runbook...")
- `grep -q "Last verified" infra/bootstrap/README.md` — FOUND
- `grep -q "Step 1 — Create" infra/bootstrap/README.md` — FOUND
- `grep -q "Step 2 — Run" infra/bootstrap/README.md` — FOUND
- `grep -q "Step 3 — Capture" infra/bootstrap/README.md` — FOUND
- `grep -q "Step 4 — " infra/bootstrap/README.md` — FOUND
- `grep -q "terraform import" infra/bootstrap/README.md` — FOUND
- `grep -q "Knowingly-accepted security trade-offs" infra/bootstrap/README.md` — FOUND
- `grep -q "jobrag.ciamlogin.com" infra/bootstrap/README.md` — FOUND
- `grep -q 'backend "azurerm"' infra/bootstrap/main.tf` — NOT FOUND (correct — confirms LOCAL state per D-02)
- `grep -q "~> 4.69" infra/bootstrap/main.tf` — FOUND (azurerm pin)
- `grep -q "~> 3.0" infra/bootstrap/main.tf` — FOUND (azuread pin)
- `grep -q "~> 3.6" infra/bootstrap/main.tf` — FOUND (random pin)
- `grep -q "alias.*external" infra/bootstrap/identity.tf` — FOUND (aliased provider per A4)
- `grep -q "storage_account_name" infra/bootstrap/outputs.tf` — FOUND
- `grep -q "tenant_id_external" infra/bootstrap/outputs.tf` — FOUND
- `git check-ignore .planning/phases/03-infrastructure-ci-cd/bootstrap-secrets.local.md` — IGNORED (T-3-01 mitigated)
- No live Azure resources provisioned (executor host has no Terraform CLI; user explicitly instructed no live runs)

---
*Phase: 03-infrastructure-ci-cd*
*Completed: 2026-04-30*
