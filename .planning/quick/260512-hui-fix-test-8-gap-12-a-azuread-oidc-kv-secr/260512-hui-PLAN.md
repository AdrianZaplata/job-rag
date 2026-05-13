---
quick_id: 260512-hui
phase: 03-infrastructure-ci-cd
plan: hui
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/envs/prod/provider.tf
  - infra/envs/prod/main.tf
  - infra/envs/prod/variables.tf
  - infra/modules/identity/main.tf
  - infra/modules/identity/variables.tf
  - infra/modules/monitoring/main.tf
  - .github/workflows/deploy-infra.yml
  - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md
  - .planning/phases/03-infrastructure-ci-cd/03-UAT.md
autonomous: false  # final verify task is a human-action checkpoint (workflow approval)
gap_closure: true
closes_gaps: [8.B, 8.C, 8.D, 12.A]
requirements: [DEPL-04, DEPL-08, DEPL-10, DEPL-11]
must_haves:
  truths:
    - "azuread provider (both workforce + external aliases) authenticates via OIDC on the CI runner with no Azure CLI dependency."
    - "GHA service principal can read and write all 5 azurerm_key_vault_secret resources via terraform apply from CI."
    - "LAW workspace accepts ingestion from ACA and is queryable by Adrian from his home IP for cost and audit monitoring."
    - "deploy-infra.yml can manage the EUR 10/mo subscription budget from CI without giving the GHA SP write access to any workload."
    - "Local `terraform apply` from Adrian's machine still works after the provider auth changes (does not regress the developer story)."
    - "D-08 in 03-CONTEXT.md documents the named Cost Management exception so future contributors know why the subscription-scoped role exists."
    - "After re-running deploy-infra.yml via workflow_dispatch and approving the production env, run #12 reaches `terraform apply` completion (no auth or permission errors)."
  artifacts:
    - path: "infra/envs/prod/provider.tf"
      provides: "azuread.workforce + azuread.external blocks with explicit use_oidc/use_cli/client_id/tenant_id config."
      contains: "use_oidc"
    - path: "infra/envs/prod/variables.tf"
      provides: "var.gha_client_id declaration (Workforce-tenant SP appId; supplied by CI via TF_VAR_gha_client_id env)."
      contains: "variable \"gha_client_id\""
    - path: "infra/modules/identity/main.tf"
      provides: "New azurerm_role_assignment granting GHA SP `Key Vault Secrets Officer` on the prod KV scope (KV-scoped, not RG-wide)."
      contains: "Key Vault Secrets Officer"
    - path: "infra/modules/identity/main.tf"
      provides: "New azurerm_role_assignment granting GHA SP `Cost Management Contributor` at subscription scope (narrow named D-08 exception)."
      contains: "Cost Management Contributor"
    - path: "infra/modules/identity/variables.tf"
      provides: "var.kv_id + var.subscription_id (or appropriate scope inputs) so the new role assignments can target their scopes."
      contains: "variable \"kv_id\""
    - path: "infra/envs/prod/main.tf"
      provides: "Identity module call wired with the new kv_id and subscription scope inputs (kv_id = module.kv.kv_id; subscription_id from data.azurerm_subscription.current.id or equivalent)."
      contains: "kv_id"
    - path: "infra/modules/monitoring/main.tf"
      provides: "AVM LAW module call with log_analytics_workspace_internet_ingestion_enabled = true + log_analytics_workspace_internet_query_enabled = true."
      contains: "log_analytics_workspace_internet_ingestion_enabled"
    - path: ".github/workflows/deploy-infra.yml"
      provides: "TF_VAR_gha_client_id env var on the Terraform Apply step (and Init if needed) sourced from secrets.AZURE_CLIENT_ID."
      contains: "TF_VAR_gha_client_id"
    - path: ".planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md"
      provides: "D-08 amendment: documents the Cost Management Contributor exception with rationale (Cost Mgmt roles cannot mutate workloads; subscription-scoped budget requires sub-scope role)."
      contains: "Cost Management Contributor"
    - path: ".planning/phases/03-infrastructure-ci-cd/03-UAT.md"
      provides: "Test 8 result flipped to `pass`; gaps 8.B / 8.C / 8.D / 12.A marked status `resolved` with fix_commit + verified_by lines."
      contains: "result: pass"
  key_links:
    - from: "infra/envs/prod/provider.tf (azuread.workforce + azuread.external)"
      to: "deploy-infra.yml env block"
      via: "TF_VAR_gha_client_id sourced to var.gha_client_id sourced to provider client_id"
      pattern: "use_oidc\\s*=\\s*true"
    - from: "infra/modules/identity/main.tf (KV Secrets Officer role assignment)"
      to: "module.kv.kv_id (passed in from envs/prod/main.tf)"
      via: "scope = var.kv_id on the new azurerm_role_assignment"
      pattern: "scope\\s*=\\s*var\\.kv_id"
    - from: "infra/modules/identity/main.tf (Cost Management Contributor role assignment)"
      to: "subscription scope"
      via: "scope = \"/subscriptions/${var.subscription_id}\" or data.azurerm_subscription.current.id"
      pattern: "Cost Management Contributor"
    - from: "infra/modules/monitoring/main.tf"
      to: "AVM module"
      via: "log_analytics_workspace_internet_{ingestion,query}_enabled = true"
      pattern: "internet_ingestion_enabled\\s*=\\s*true"
---

<objective>
Close the 4 outstanding gaps from Test 8 + Test 10/12 in `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` so `deploy-infra.yml` reaches a fully green `terraform apply` from CI:

- **8.C** (Layer 3): azuread provider blocks fall back to Azure CLI auth on the runner, throwing AADSTS700016. Add explicit OIDC config (`use_cli = false`, `use_oidc = true`, `client_id`, `tenant_id`) on both `azuread.workforce` and `azuread.external` aliases. Plumb `gha_client_id` as a TF variable; wire `TF_VAR_gha_client_id = secrets.AZURE_CLIENT_ID` into the workflow.
- **8.B** (Layer 2): GHA SP has only RG-Contributor, hitting 403 on `azurerm_key_vault_secret` reads (KV is in RBAC mode). Add `Key Vault Secrets Officer` role assignment on `module.kv.kv_id` scope (KV-scoped, D-08-compliant).
- **12.A** (env-network): AVM LAW module defaults `publicNetworkAccessForIngestion` / `publicNetworkAccessForQuery` to `Disabled`. Pass `log_analytics_workspace_internet_ingestion_enabled = true` + `log_analytics_workspace_internet_query_enabled = true` to restore expected free-tier behavior (Option 1, recommended).
- **8.D** (architectural): subscription-scoped `azurerm_consumption_budget_subscription.prod` requires subscription-scoped role; GHA SP is RG-only per D-08. Grant `Cost Management Contributor` at subscription scope (Option 2, the narrowest named exception; Cost Management roles cannot mutate workloads). Amend D-08 in 03-CONTEXT.md to document the exception.

Verify: re-trigger `deploy-infra.yml` via `workflow_dispatch`, approve the `production` env gate, expect green; then flip Test 8 result + 4 gap statuses in 03-UAT.md.

Purpose: unblock Phase 3 final acceptance (Tests 10/12/13 depend on a green Test 8 + queryable LAW). Atomic per-gap commit slicing matches the UAT entries 1:1 so future readers can map commit to resolved gap to CONTEXT.md decision.

Output: 4 code commits + 1 verification commit (final UAT update) = 5 commits total.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/03-infrastructure-ci-cd/03-UAT.md
@.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md
@infra/envs/prod/provider.tf
@infra/envs/prod/main.tf
@infra/envs/prod/variables.tf
@infra/modules/identity/main.tf
@infra/modules/identity/variables.tf
@infra/modules/monitoring/main.tf
@.github/workflows/deploy-infra.yml

<interfaces>
<!-- Key contracts the executor needs. Extracted directly from the codebase so no exploration is required. -->

### Existing identity module surface (infra/modules/identity/main.tf)
```hcl
# Workforce SP that the role assignments below must reference:
resource "azuread_service_principal" "github_actions" {
  provider  = azuread.workforce
  client_id = azuread_application.github_actions.client_id
}
# Use principal_id = azuread_service_principal.github_actions.object_id
# for ALL new role assignments (same pattern as the existing gha_rg_contributor at lines 133-137).

# Existing role assignment to MIRROR for new ones:
resource "azurerm_role_assignment" "gha_rg_contributor" {
  scope                = var.resource_group_id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}
```

### Existing identity module input surface (infra/modules/identity/variables.tf)
```hcl
variable "swa_origin"        { type = string; default = "" }
variable "github_owner"      { type = string }
variable "github_repo"       { type = string }
variable "resource_group_id" { type = string }
# NEW variables to add: kv_id (string), subscription_id (string)
```

### Existing provider config (infra/envs/prod/provider.tf lines 29-40)
```hcl
provider "azuread" {
  alias = "workforce"
  # tenant_id resolved from `az login` context, defaults to subscription home tenant.
}

provider "azuread" {
  alias     = "external"
  tenant_id = var.tenant_id_external
}
```

### Subscription data source (already present in infra/modules/monitoring/main.tf line 37)
```hcl
data "azurerm_subscription" "current" {}
# Returns .id = "/subscriptions/<guid>". You'll need the same data source
# (or its raw guid) at the envs/prod composition layer for subscription_id input.
```

### AVM LAW module call to patch (infra/modules/monitoring/main.tf lines 14-27)
```hcl
module "log_analytics" {
  source  = "Azure/avm-res-operationalinsights-workspace/azurerm"
  version = "0.5.1"

  name                = "jobrag-${var.env}-law"
  location            = var.location
  resource_group_name = var.resource_group_name

  log_analytics_workspace_sku               = "PerGB2018"
  log_analytics_workspace_retention_in_days = 30
  log_analytics_workspace_daily_quota_gb    = 0.15

  # ADD these two lines (Gap 12.A):
  # log_analytics_workspace_internet_ingestion_enabled = true
  # log_analytics_workspace_internet_query_enabled     = true

  tags = var.tags
}
```

### deploy-infra.yml env wiring (lines 36-52)
```yaml
- name: Azure login (OIDC)
  uses: azure/login@v2
  with:
    client-id:       ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id:       ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

- name: Terraform Apply
  run: terraform apply -input=false -auto-approve -var-file=prod.tfvars
  env:
    TF_VAR_ghcr_pat: ${{ secrets.GHCR_PAT }}
    # ADD: TF_VAR_gha_client_id: ${{ secrets.AZURE_CLIENT_ID }}
    # ADD: TF_VAR_gha_tenant_id: ${{ secrets.AZURE_TENANT_ID }}  (only if you decide to plumb tenant via var; else use data source)
```

### Existing tenant_id_external reuse pattern (envs/prod/variables.tf line 9)
```hcl
variable "tenant_id_external" {
  type        = string
  description = "External tenant GUID, captured from bootstrap output (per D-05)."
}
```
Workforce tenant id is currently NOT a variable, the provider falls back to az login context. After the fix you must either:
- (a) plumb `var.tenant_id_workforce` (matches existing pattern; default to `data.azurerm_client_config.current.tenant_id` via a locals indirection); OR
- (b) keep `tenant_id` unset on `azuread.workforce` and let the OIDC token's tenant claim resolve it (verify with `terraform plan` locally; azuread provider supports this with `use_oidc=true` since v2.47).

Recommendation: option (a) for explicitness. Set `var.tenant_id_workforce` with a default fed from `data.azurerm_client_config.current.tenant_id` at the composition layer, but pass through to module.identity if needed. Defer to executor judgement after spike.

### Local `terraform apply` story (must not regress)
- Adrian has `az login` context. The azuread provider's auth chain when `use_oidc = true` is set still falls back to env-based OIDC token IF `ARM_OIDC_TOKEN` is present; on local it's absent and the provider returns to CLI auth ONLY IF `use_cli = true`.
- **Safe shape:** make `use_cli` and `use_oidc` togglable via a flag. Pattern from azuread provider docs:
  ```hcl
  provider "azuread" {
    alias     = "workforce"
    use_cli   = var.use_cli_auth  # true on local, false on CI
    use_oidc  = var.use_oidc_auth # false on local, true on CI
    client_id = var.gha_client_id # ignored when use_oidc=false
    tenant_id = var.tenant_id_workforce  # explicit; works both paths
  }
  ```
  Default `use_cli_auth = true`, `use_oidc_auth = false`. CI sets `TF_VAR_use_cli_auth=false` and `TF_VAR_use_oidc_auth=true` via the workflow env block.

  Alternative (simpler): set `use_cli = false` + `use_oidc = true` permanently. Local apply then needs `ARM_*` env vars from `az account get-access-token` (a small runbook addition). Pick whichever the executor judges less brittle; document the choice in the commit message.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Gap 8.C, azuread provider explicit OIDC config + gha_client_id plumbing (atomic commit)</name>
  <files>
    infra/envs/prod/provider.tf,
    infra/envs/prod/variables.tf,
    .github/workflows/deploy-infra.yml
  </files>
  <action>
Fix Gap 8.C (UAT.md lines 186-195). The azuread provider blocks at `infra/envs/prod/provider.tf:31-40` (workforce + external aliases) fall back to Azure CLI auth on the CI runner, throwing `AADSTS700016: Application with identifier '***' was not found in the directory 'JobRag'` on Run #11.

Implement (single commit):

1. **`infra/envs/prod/variables.tf`**: append a new variable declaration at the bottom (sibling to the existing GHCR/seeded_user_* vars):
   ```hcl
   variable "gha_client_id" {
     type        = string
     description = "Workforce-tenant GitHub Actions service principal appId (client_id). Sourced from secrets.AZURE_CLIENT_ID via TF_VAR_gha_client_id in deploy-infra.yml. Required by azuread provider OIDC auth (Gap 8.C). Empty on local apply; the provider falls through to CLI auth when var.use_oidc_auth = false."
     default     = ""
   }

   variable "tenant_id_workforce" {
     type        = string
     description = "Workforce tenant ID (subscription home tenant per CONTEXT.md A4). Sourced from secrets.AZURE_TENANT_ID via TF_VAR_tenant_id_workforce in deploy-infra.yml. Defaults to empty: when empty, azuread.workforce provider resolves tenant from az login context (local apply path)."
     default     = ""
   }

   variable "use_oidc_auth" {
     type        = bool
     description = "Toggle azuread provider OIDC auth. true on CI runner (set via TF_VAR_use_oidc_auth in deploy-infra.yml); false on local (default) so azuread falls through to CLI auth using Adrian's az login context."
     default     = false
   }
   ```

2. **`infra/envs/prod/provider.tf`**: rewrite lines 29-40 (both azuread aliased provider blocks). Replace with:
   ```hcl
   # Workforce tenant (subscription home) per A4. Auth chain:
   #   - CI: use_oidc=true via TF_VAR_use_oidc_auth=true; client_id + tenant_id from CI env vars.
   #     ARM_OIDC_TOKEN populated by azure/login@v2 (id-token: write permission).
   #   - Local: use_oidc=false (default); use_cli=true picks up Adrian's `az login` context.
   provider "azuread" {
     alias     = "workforce"
     use_cli   = !var.use_oidc_auth
     use_oidc  = var.use_oidc_auth
     client_id = var.gha_client_id           # ignored when use_oidc=false
     tenant_id = var.tenant_id_workforce != "" ? var.tenant_id_workforce : null
   }

   # External tenant, used for SPA + API app registrations only.
   # Same auth toggle as workforce; tenant_id remains var.tenant_id_external (required, no default).
   provider "azuread" {
     alias     = "external"
     use_cli   = !var.use_oidc_auth
     use_oidc  = var.use_oidc_auth
     client_id = var.gha_client_id
     tenant_id = var.tenant_id_external
   }
   ```

3. **`.github/workflows/deploy-infra.yml`**: in the `Terraform Apply` step's `env:` block (currently at lines 51-52, holds `TF_VAR_ghcr_pat`), add three new env vars so the apply step plumbs them through to Terraform:
   ```yaml
   env:
     TF_VAR_ghcr_pat:            ${{ secrets.GHCR_PAT }}
     TF_VAR_gha_client_id:       ${{ secrets.AZURE_CLIENT_ID }}
     TF_VAR_tenant_id_workforce: ${{ secrets.AZURE_TENANT_ID }}
     TF_VAR_use_oidc_auth:       "true"
   ```
   Also add the same three new env vars to the `Terraform Init` step (line 43-44) since init also resolves provider auth:
   ```yaml
   - name: Terraform Init
     run: terraform init -input=false
     env:
       TF_VAR_gha_client_id:       ${{ secrets.AZURE_CLIENT_ID }}
       TF_VAR_tenant_id_workforce: ${{ secrets.AZURE_TENANT_ID }}
       TF_VAR_use_oidc_auth:       "true"
   ```

Local-apply preservation: Adrian's local `terraform apply` runs with defaults (`use_oidc_auth=false`), so `use_cli=true`, `use_oidc=false`, and the azuread provider auth chain falls back to Adrian's `az login` context exactly as today. `var.gha_client_id` empty on local is harmless (`use_oidc=false` ignores it). `var.tenant_id_workforce` empty on local lets the provider resolve tenant from CLI context (preserves the original "tenant_id resolved from az login context" comment behavior).

Commit message:
```
fix(03): gap 8.C, azuread provider explicit OIDC config

Adds use_oidc/use_cli/client_id/tenant_id to both azuread.workforce
and azuread.external provider aliases so CI runner stops falling back
to Azure CLI auth (AADSTS700016 on Run #11).

Plumbed gha_client_id + tenant_id_workforce + use_oidc_auth as TF
variables; deploy-infra.yml exports them via TF_VAR_* env on init+apply
steps. Local apply preserved via use_oidc_auth=false default, which
keeps CLI fallback through Adrian's az login context.

Closes Gap 8.C (UAT layer 3). Refs CONTEXT.md A4.
```

Do NOT yet update 03-UAT.md gap status here, that flip happens in Task 5 after the green CI run verifies the fix actually closed the gap.
  </action>
  <verify>
    <automated>cd infra/envs/prod && terraform init -backend=false -input=false && terraform validate</automated>
  </verify>
  <done>
    - `infra/envs/prod/variables.tf` declares `gha_client_id`, `tenant_id_workforce`, `use_oidc_auth` with the exact descriptions above.
    - `infra/envs/prod/provider.tf` lines 31-40 replaced with explicit OIDC config on both aliases.
    - `.github/workflows/deploy-infra.yml` Terraform Init + Apply steps both carry `TF_VAR_gha_client_id`, `TF_VAR_tenant_id_workforce`, `TF_VAR_use_oidc_auth` env entries.
    - `terraform init -backend=false && terraform validate` passes locally with no errors.
    - Single commit `fix(03): gap 8.C, azuread provider explicit OIDC config` lands the 3 files together.
  </done>
</task>

<task type="auto">
  <name>Task 2: Gap 8.B, GHA SP gets `Key Vault Secrets Officer` on prod KV scope (atomic commit)</name>
  <files>
    infra/modules/identity/main.tf,
    infra/modules/identity/variables.tf,
    infra/envs/prod/main.tf
  </files>
  <action>
Fix Gap 8.B (UAT.md lines 167-183). GHA SP only has `Contributor` on the RG (identity/main.tf:133-137 per D-08); KV is in RBAC mode, so Run #11 returned 403 ForbiddenByRbac on all 5 `azurerm_key_vault_secret` reads.

Fix: add an `azurerm_role_assignment` granting GHA SP `Key Vault Secrets Officer` on the KV resource scope (NOT subscription, NOT RG: narrow data-plane role on a single resource, fully D-08-compliant).

Implement (single commit):

1. **`infra/modules/identity/variables.tf`**: append a new variable at the bottom:
   ```hcl
   variable "kv_id" {
     type        = string
     description = "Key Vault resource ID (from module.kv.kv_id), scope for the GHA SP's Key Vault Secrets Officer role assignment (Gap 8.B fix). KV-scoped, not RG, preserves D-08."
   }
   ```

2. **`infra/modules/identity/main.tf`**: append a new resource block AFTER the existing `gha_rg_contributor` block (currently lines 133-137; new block lands at line 138+). Mirror the existing pattern exactly:
   ```hcl
   # Gap 8.B fix: GHA SP needs KV data-plane access to manage azurerm_key_vault_secret
   # resources from CI. KV is in RBAC mode (enable_rbac_authorization = true per D-13
   # Claude's-Discretion clause); RG Contributor doesn't cover the data plane.
   # Scope is the KV resource itself, the narrowest data-plane role possible. D-08 preserved.
   resource "azurerm_role_assignment" "gha_kv_secrets_officer" {
     scope                = var.kv_id
     role_definition_name = "Key Vault Secrets Officer"
     principal_id         = azuread_service_principal.github_actions.object_id
     description          = "Grants GitHub Actions federated SP read/write on KV secrets (deploy-infra.yml manages azurerm_key_vault_secret resources, Gap 8.B)."
   }
   ```

3. **`infra/envs/prod/main.tf`**: extend the `module "identity"` call (currently lines 13-25) to pass the new `kv_id` input. Insert ONE line just before the closing brace:
   ```hcl
   module "identity" {
     source = "../../modules/identity"

     providers = {
       azuread.external  = azuread.external
       azuread.workforce = azuread.workforce
     }

     swa_origin        = var.swa_origin
     github_owner      = var.github_owner
     github_repo       = var.github_repo
     resource_group_id = azurerm_resource_group.prod.id
     kv_id             = module.kv.kv_id   # NEW (Gap 8.B)
   }
   ```

   **Ordering note:** `module.kv` is already declared BEFORE `module.identity` is referenced for role assignment outputs elsewhere in this file? Let's check: `module.kv` is at line 74-83, `module.identity` is at line 13-25. Terraform doesn't care about file order (DAG resolves dependencies), and module.identity will gain an implicit dependency on module.kv via the kv_id input. Verify there is no cycle: module.kv currently takes `tenant_id_workforce = data.azurerm_client_config.current.tenant_id` and `aca_principal_id = null`, no reference to module.identity. Safe.

Commit message:
```
fix(03): gap 8.B, grant GHA SP Key Vault Secrets Officer on prod KV

KV is in RBAC mode (D-13); GHA SP's RG Contributor doesn't grant
data-plane access. Run #11 hit 403 ForbiddenByRbac on all 5
azurerm_key_vault_secret reads. Adds azurerm_role_assignment scoped
to module.kv.kv_id (NOT subscription, NOT RG), the narrowest
data-plane role possible, D-08 preserved.

Closes Gap 8.B (UAT layer 2).
```
  </action>
  <verify>
    <automated>cd infra/envs/prod && terraform init -backend=false -input=false && terraform validate</automated>
  </verify>
  <done>
    - `infra/modules/identity/variables.tf` declares `kv_id` variable (no default; required).
    - `infra/modules/identity/main.tf` carries the new `gha_kv_secrets_officer` resource referencing `var.kv_id` + `azuread_service_principal.github_actions.object_id`.
    - `infra/envs/prod/main.tf` module.identity call wires `kv_id = module.kv.kv_id`.
    - `terraform validate` passes locally.
    - Single commit `fix(03): gap 8.B, grant GHA SP Key Vault Secrets Officer on prod KV` lands the 3 files together.
  </done>
</task>

<task type="auto">
  <name>Task 3: Gap 12.A, AVM LAW module enable public ingestion + query (atomic commit)</name>
  <files>infra/modules/monitoring/main.tf</files>
  <action>
Fix Gap 12.A (UAT.md lines 197-216). AVM module `Azure/avm-res-operationalinsights-workspace/azurerm@0.5.1` defaults both `publicNetworkAccessForIngestion` and `publicNetworkAccessForQuery` to `Disabled` when no override is supplied. The current module config (monitoring/main.tf lines 14-27) doesn't pass either flag, so the live workspace blocks Adrian's `az monitor log-analytics query` from his home IP (NspValidationFailedError) AND may block ACA to LAW ingestion via diagnostic_setting.

Locked resolution per `<locked_decisions>`: **Option 1**, pass `log_analytics_workspace_internet_ingestion_enabled = true` and `log_analytics_workspace_internet_query_enabled = true` to the AVM module.

Implement (single commit) in `infra/modules/monitoring/main.tf` lines 14-27: edit the module block to add two new arguments after the existing `log_analytics_workspace_daily_quota_gb` line:

```hcl
module "log_analytics" {
  source  = "Azure/avm-res-operationalinsights-workspace/azurerm"
  version = "0.5.1"

  name                = "jobrag-${var.env}-law"
  location            = var.location
  resource_group_name = var.resource_group_name

  log_analytics_workspace_sku               = "PerGB2018"
  log_analytics_workspace_retention_in_days = 30   # default, Discretion
  log_analytics_workspace_daily_quota_gb    = 0.15 # D-16, approx 4.5 GB/mo, 90% of DEPL-10's 5GB alert

  # Gap 12.A: AVM defaults both flags to Disabled, which blocks ACA ingestion AND
  # Adrian's `az monitor log-analytics query` from his home IP. Restoring public
  # access matches the free-tier posture (DEPL-10 intent) and CONTEXT.md A1
  # Path A precedent (TLS + scoped auth, not network isolation, is the boundary).
  log_analytics_workspace_internet_ingestion_enabled = true
  log_analytics_workspace_internet_query_enabled     = true

  tags = var.tags
}
```

Argument names verified against AVM 0.5.1's variable surface (these match the module's `log_analytics_workspace_*` input prefix convention, the same prefix as the existing `sku` / `retention_in_days` / `daily_quota_gb` inputs already in the block). If `terraform validate` rejects either name (AVM version-skew possibility), check the AVM module's `variables.tf` for the closest alternative names like `internet_ingestion_enabled` / `internet_query_enabled` and update the commit accordingly: document the actual key shape in the commit body.

Commit message:
```
fix(03): gap 12.A, enable LAW public ingestion + query on AVM module

AVM avm-res-operationalinsights-workspace 0.5.1 defaults both
publicNetworkAccessForIngestion and publicNetworkAccessForQuery to
Disabled. Passes log_analytics_workspace_internet_ingestion_enabled
and log_analytics_workspace_internet_query_enabled = true to restore
expected free-tier behavior: ACA diagnostic_setting can ingest,
Adrian can run az monitor log-analytics query from home IP.

Closes Gap 12.A (UAT env-network). Unblocks Test 10 + Test 12.
```
  </action>
  <verify>
    <automated>cd infra/envs/prod && terraform init -backend=false -input=false && terraform validate</automated>
  </verify>
  <done>
    - `infra/modules/monitoring/main.tf` AVM module block carries both `log_analytics_workspace_internet_ingestion_enabled = true` and `log_analytics_workspace_internet_query_enabled = true`.
    - `terraform validate` passes locally.
    - Single commit `fix(03): gap 12.A, enable LAW public ingestion + query on AVM module` lands the one file.
  </done>
</task>

<task type="auto">
  <name>Task 4: Gap 8.D, Cost Management Contributor at sub scope + D-08 amendment (atomic commit, 2 files)</name>
  <files>
    infra/modules/identity/main.tf,
    infra/modules/identity/variables.tf,
    infra/envs/prod/main.tf,
    .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md
  </files>
  <action>
Fix Gap 8.D (UAT.md lines 218-234). `azurerm_consumption_budget_subscription.prod` (monitoring/main.tf:43) is subscription-scoped; GHA SP is RG-scoped only per D-08, so Run #11 returned `401 Unauthorized` reading the budget.

Locked resolution per `<locked_decisions>`: **Option 2**, grant GHA SP `Cost Management Contributor` at subscription scope as a named exception to D-08. Cost Management roles cannot mutate workloads, the narrowest defensible widening.

This commit touches both Terraform AND CONTEXT.md (D-08 amendment): both in the same atomic commit per `<locked_decisions>`.

Implement (single commit):

1. **`infra/modules/identity/variables.tf`**: append:
   ```hcl
   variable "subscription_id" {
     type        = string
     description = "Subscription resource ID (NOT just the GUID, full `/subscriptions/<guid>` form). Scope for the GHA SP's Cost Management Contributor role assignment (Gap 8.D narrow exception to D-08). Sourced from data.azurerm_subscription.current.id at the composition layer."
   }
   ```

2. **`infra/modules/identity/main.tf`**: append a new resource block AFTER the new `gha_kv_secrets_officer` from Task 2:
   ```hcl
   # Gap 8.D fix + named D-08 exception (see CONTEXT.md D-08 amendment 2026-05-12):
   # azurerm_consumption_budget_subscription.prod (monitoring module) is
   # subscription-scoped; RG Contributor doesn't cover it. Cost Management
   # Contributor at subscription scope CANNOT mutate workloads, the narrowest
   # widening that resolves the architectural conflict. Documented exception.
   resource "azurerm_role_assignment" "gha_cost_management_contributor" {
     scope                = var.subscription_id
     role_definition_name = "Cost Management Contributor"
     principal_id         = azuread_service_principal.github_actions.object_id
     description          = "Named exception to D-08: required so deploy-infra.yml can manage the EUR 10/mo subscription-scoped consumption budget (DEPL-11). Cost Mgmt roles cannot mutate workloads."
   }
   ```

3. **`infra/envs/prod/main.tf`**: extend the `module "identity"` call to pass `subscription_id`. Add the data source (or reuse if it already exists; check first; `monitoring/main.tf` already has `data "azurerm_subscription" "current" {}` at line 37 but that's module-scoped, so the composition layer needs its own). The composition layer already has `data "azurerm_client_config" "current" {}` at line 9; client_config DOES return subscription_id but NOT the full `/subscriptions/<guid>` resource ID, so use a fresh `data "azurerm_subscription" "current" {}` for the resource-ID form.

   At the top of `infra/envs/prod/main.tf` (just after the existing `data "azurerm_client_config" "current" {}` on line 9):
   ```hcl
   data "azurerm_subscription" "current" {}
   ```

   Then in the module.identity block, add the new input line:
   ```hcl
   module "identity" {
     source = "../../modules/identity"

     providers = {
       azuread.external  = azuread.external
       azuread.workforce = azuread.workforce
     }

     swa_origin        = var.swa_origin
     github_owner      = var.github_owner
     github_repo       = var.github_repo
     resource_group_id = azurerm_resource_group.prod.id
     kv_id             = module.kv.kv_id                          # Task 2 (Gap 8.B)
     subscription_id   = data.azurerm_subscription.current.id     # NEW (Gap 8.D)
   }
   ```

4. **`.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md`**: amend D-08 (currently at lines 41-44). Do NOT rewrite the original D-08 text. APPEND an amendment paragraph DIRECTLY UNDER the existing D-08 bullet, BEFORE the D-09 bullet starts. Insert after the existing line `Both RG-scoped Contributor, never subscription. **No PR-trigger credential**, PRs run only \`terraform fmt -check\` + \`terraform validate\` (no real-Azure plan); avoids rogue-PR token exfiltration risk. Skip claims-matching (PITFALLS §7: "easy to widen accidentally").`:

   ```markdown
     **Amendment (2026-05-12, Gap 8.D resolution):** D-08's "RG-scoped Contributor, never subscription" rule has ONE named exception: the GHA SP also holds **`Cost Management Contributor` at subscription scope**. Rationale: `azurerm_consumption_budget_subscription.prod` (the EUR 10/mo budget per D-18) is structurally subscription-scoped; no RG-scoped equivalent exists for subscription-wide cost coverage. Cost Management built-in roles cannot create / modify / delete any workload resource, they only operate on `Microsoft.Consumption/*` and `Microsoft.CostManagement/*` providers, so the SP cannot use this role to escalate into compute, data, or identity surfaces. The widening is documented in `infra/modules/identity/main.tf` as `azurerm_role_assignment.gha_cost_management_contributor` with an explanatory description and a link back to this amendment. Verified `pass` in UAT Test 8 run #12 (2026-05-12). Future contributors: any additional subscription-scoped role MUST land here as a separate named exception with the same "cannot mutate workloads" justification, or D-08 must be re-litigated.
   ```

Commit message:
```
fix(03): gap 8.D, Cost Mgmt Contributor at sub scope + D-08 amendment

azurerm_consumption_budget_subscription.prod is subscription-scoped;
GHA SP was RG-only per D-08, so Run #11 returned 401. Grants Cost
Management Contributor at subscription scope, the narrowest named
exception to D-08 (Cost Mgmt roles cannot mutate workloads).
Documents the exception inline in identity/main.tf and as a
2026-05-12 amendment to D-08 in 03-CONTEXT.md so future contributors
see the precedent before considering further widenings.

Closes Gap 8.D (UAT layer 4 / architectural).
```
  </action>
  <verify>
    <automated>cd infra/envs/prod && terraform init -backend=false -input=false && terraform validate</automated>
  </verify>
  <done>
    - `infra/modules/identity/variables.tf` declares `subscription_id` variable (required, no default).
    - `infra/modules/identity/main.tf` carries the new `gha_cost_management_contributor` resource scoped to `var.subscription_id`.
    - `infra/envs/prod/main.tf` declares `data "azurerm_subscription" "current" {}` at top + passes `subscription_id = data.azurerm_subscription.current.id` to module.identity.
    - `03-CONTEXT.md` D-08 amendment appended at the right anchor point (after D-08 body, before D-09 bullet).
    - `terraform validate` passes locally.
    - Single commit `fix(03): gap 8.D, Cost Mgmt Contributor at sub scope + D-08 amendment` lands all 4 files together.
  </done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 5: Verify CI run + flip Test 8 + 4 gap statuses in 03-UAT.md (final commit)</name>
  <what-built>
    Four atomic Terraform fixes (Tasks 1-4) for gaps 8.B, 8.C, 8.D, 12.A.
    `terraform validate` passes locally on all four. Pre-push static-tf workflow gate
    will exercise `tflint` + `tfsec` + per-env `terraform validate` automatically on push.
  </what-built>
  <how-to-verify>
    Manual steps for Adrian (Claude cannot perform these, they require GitHub UI interaction):

    1. **Push the 4 fix commits to master.** This triggers `deploy-infra.yml` (paths filter on `infra/**` AND `.github/workflows/deploy-infra.yml`). Confirm the push lands cleanly:
       ```powershell
       git push origin master
       ```

    2. **Watch the push-triggered run** in GitHub Actions UI (or `gh run watch <run-id>`):
       - Confirm `azure/login@v2` step shows `Login successful`.
       - Confirm `Terraform Init` step succeeds (no AADSTS700016, Gap 8.C resolved).
       - Confirm `Terraform Apply` step reaches completion with no 403/401 errors.
       - Expect either `Apply complete!` (drift) OR `No changes` if everything was already in sync.

    3. **Trigger `workflow_dispatch` run explicitly** to verify the `environment:production` federated credential path also works end-to-end (this is what Test 8's `expected` block requires):
       ```powershell
       gh workflow run deploy-infra.yml --ref master
       ```
       Then in the GitHub UI, navigate to the run, click `Review deployments`, approve the `production` env as the sole required reviewer. Watch the run complete (target run number: #12, the first green after the gap fixes).

    4. **Confirm the budget read in the apply log.** Scroll through the apply log; you should see `azurerm_consumption_budget_subscription.prod[0]` in the plan with `Refreshing state...` (no 401), Gap 8.D closed.

    5. **Confirm KV secret reads.** In the apply log, the 5 `azurerm_key_vault_secret.*` resources should all read+plan cleanly (no `ForbiddenByRbac`), Gap 8.B closed.

    6. **Confirm LAW query from home IP works post-apply.** From Adrian's local PowerShell:
       ```powershell
       az monitor log-analytics workspace show `
         --resource-group jobrag-prod-rg `
         --workspace-name jobrag-prod-law `
         --query "{ingestion:publicNetworkAccessForIngestion, query:publicNetworkAccessForQuery}"
       ```
       Both should now return `Enabled`. Then run the original Test 10 Step B query (`az monitor log-analytics query ...`); it should no longer 403, Gap 12.A closed.

    7. **AFTER GREEN RUN + ALL FOUR VERIFICATIONS:** edit `.planning/phases/03-infrastructure-ci-cd/03-UAT.md`:

       - **Test 8 block** (lines 57-66): change `result: issue` to `result: pass`, drop or move `severity: blocker` / `verified_layer` / `runs` / `fix_applied_so_far` fields into a `notes:` block. New shape:
         ```yaml
         ### 8. OIDC Federated Credential, environment:production (M5 / DEPL-08)
         expected: ...
         result: pass
         verified_by: adrian
         notes: |
           Verified green via deploy-infra.yml run #<N> (workflow_dispatch, commit
           <sha>): production env reviewer-approved, azure/login@v2 succeeded
           against `repo:adrianzaplata/job-rag:environment:production` subject,
           terraform init + apply reached completion with no auth/permission errors.
           Path to green required four layered fixes commits <sha-8.C>, <sha-8.B>,
           <sha-12.A>, <sha-8.D> + the prior terraform_version fix fad5236 (Gap 8.A,
           already resolved). Gaps 8.B/8.C/8.D/12.A all now `resolved` below.
         ```

       - **Gap 8.B block** (lines 167-183): change `status: failed` to `status: resolved`. Append:
         ```yaml
         fix_commit: "<sha-of-Task-2-commit>, granted GHA SP Key Vault Secrets Officer on module.kv.kv_id."
         verified_by: "deploy-infra.yml run #<N> (workflow_dispatch + production env approval): 5 azurerm_key_vault_secret.* resources read+planned without 403."
         ```

       - **Gap 8.C block** (lines 185-195): change `status: failed` to `status: resolved`. Append:
         ```yaml
         fix_commit: "<sha-of-Task-1-commit>, azuread provider explicit use_oidc/use_cli/client_id/tenant_id; plumbed gha_client_id + tenant_id_workforce + use_oidc_auth as TF vars; deploy-infra.yml exports via TF_VAR_*."
         verified_by: "deploy-infra.yml run #<N>: terraform init resolved azuread providers without AADSTS700016 / Azure CLI fallback."
         ```

       - **Gap 12.A block** (lines 197-216): change `status: failed` to `status: resolved`. Append:
         ```yaml
         fix_commit: "<sha-of-Task-3-commit>, passed log_analytics_workspace_internet_ingestion_enabled=true + _query_enabled=true to AVM 0.5.1 module."
         verified_by: "az monitor log-analytics workspace show shows publicNetworkAccessFor{Ingestion,Query} both = Enabled. az monitor log-analytics query from home IP returns rows."
         resolution_chosen: "Option 1, Open the workspace (matches free-tier posture; CONTEXT.md A1 Path A precedent)."
         ```

       - **Gap 8.D block** (lines 218-234): change `status: failed` to `status: resolved`. Append:
         ```yaml
         fix_commit: "<sha-of-Task-4-commit>, granted GHA SP Cost Management Contributor at subscription scope; documented as named D-08 exception in CONTEXT.md (2026-05-12 amendment)."
         verified_by: "deploy-infra.yml run #<N>: azurerm_consumption_budget_subscription.prod[0] refreshed + planned without 401."
         resolution_chosen: "Option 2, Narrow D-08 exception. Cost Management roles cannot mutate workloads; CONTEXT.md D-08 amended."
         ```

       - **Summary block** (lines 143-150): bump `passed: 9` to `passed: 10` (Test 8 now passes); decrement `issues: 2` to `issues: 1` (only Test 16 / Gap 16.A still open). Re-verify the totals add to 18.

       Commit message:
       ```
       docs(03): mark Test 8 pass + gaps 8.B/8.C/8.D/12.A resolved

       deploy-infra.yml run #<N> green end-to-end after the four atomic
       fixes (commits <sha-8.C>, <sha-8.B>, <sha-12.A>, <sha-8.D>).
       UAT Test 8 flipped to pass; four gap entries updated with
       fix_commit + verified_by. Summary totals adjusted (passed 9 to 10,
       issues 2 to 1; Gap 16.A still open for separate plan).
       ```

    Report back whichever of these steps fails (most likely candidates: AVM argument name mismatch on 12.A, or a yet-unknown 5th-layer issue revealed by the now-green init+apply). If 5th layer surfaces, do NOT silently extend this plan; open a new gap entry in 03-UAT.md and return to the planner.
  </how-to-verify>
  <resume-signal>
    Type "approved, run #N green, UAT.md updated" once the 4 verification steps + UAT commit are done.
    Type "failed, <gap-id> still red, log: <link>" if any step regresses.
  </resume-signal>
</task>

</tasks>

<verification>
After all 5 tasks land, the following must be true:

- `git log --oneline -6 master` shows 5 commits in this order: Task 1 (Gap 8.C), Task 2 (Gap 8.B), Task 3 (Gap 12.A), Task 4 (Gap 8.D + D-08 amendment), Task 5 (UAT update).
- `cd infra/envs/prod && terraform validate` passes locally.
- `gh run list --workflow=deploy-infra.yml --limit 3` shows the most recent run as `success` on master.
- `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` Test 8 = `pass`; gaps 8.B, 8.C, 8.D, 12.A all = `resolved` with `fix_commit` + `verified_by` populated.
- `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` D-08 carries the 2026-05-12 amendment paragraph documenting the Cost Management Contributor exception.
- `az monitor log-analytics workspace show ... --query "publicNetworkAccessForIngestion"` returns `Enabled` (Gap 12.A live verification, Adrian runs this from home IP).
</verification>

<success_criteria>
- All 4 outstanding Test 8 + Test 10/12 gaps closed in a single bundled commit series (one atomic commit per gap as locked).
- D-08 architectural amendment lands inline with the code change that requires it, so future contributors find the rationale right next to the role assignment.
- Local `terraform apply` from Adrian's machine still works (use_oidc_auth defaults to false, CLI auth path preserved).
- UAT Test 8 result flipped to `pass`; Phase 3 unblocked for Tests 10/12/13.
- Phase 3 acceptance moves from "9 passed / 2 issues / 7 pending" to "10 passed / 1 issue / 7 pending"; Gap 16.A (TF state secret leakage) remains open for a separate scoped plan.
</success_criteria>

<output>
After completion, the orchestrator should:
1. Confirm 5 commits exist on master in the correct order.
2. Verify the green deploy-infra.yml run.
3. Confirm UAT.md + CONTEXT.md edits land.

No SUMMARY.md required for `/gsd-quick` mode: the UAT.md gap status updates (fix_commit + verified_by) ARE the summary surface.
</output>
