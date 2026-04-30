---
phase: 03-infrastructure-ci-cd
plan: 05a
type: execute
wave: 2
depends_on: [02, 03, 04]
files_modified:
  - infra/envs/prod/backend.tf
  - infra/envs/prod/provider.tf
  - infra/envs/prod/main.tf
  - infra/envs/prod/variables.tf
  - infra/envs/prod/outputs.tf
  - infra/envs/prod/locals.tf
  - infra/envs/prod/prod.tfvars
  - infra/envs/prod/README.md
autonomous: true
requirements: [DEPL-01, DEPL-02, DEPL-04, DEPL-05, DEPL-06, DEPL-12]
must_haves:
  truths:
    - "infra/envs/prod/ has backend.tf + provider.tf + main.tf + variables.tf + outputs.tf + locals.tf + prod.tfvars + README.md"
    - "infra/envs/prod/main.tf composes all 6 shared modules (network, kv, monitoring, database, compute, identity) + adds raw azurerm_static_web_app + azurerm_resource_group + 4 raw azurerm_key_vault_secrets (openai, langfuse pub/secret, seeded-user-entra-oid placeholder) + KV admin role assignment for the deployer"
    - "infra/envs/prod/main.tf adds the post-compute azurerm_monitor_diagnostic_setting.aca (W7 — diagnostic now lives at composition layer, not in monitoring module)"
    - "infra/envs/prod/main.tf builds locals.allowed_origins_csv via join + compact for the DEPL-12 two-pass pattern"
    - "infra/envs/prod/main.tf wires SWA api_key into outputs.swa_deployment_token (sensitive=true) for deploy-spa.yml"
    - "infra/envs/prod/outputs.tf declares the Phase 4 hand-off bundle: swa_default_origin, aca_fqdn, kv_name, kv_uri, tenant_subdomain, tenant_id, spa_app_client_id, api_app_client_id, gha_client_id, swa_deployment_token, seeded_user_entra_oid_secret_name"
    - "infra/envs/prod/README.md is the post-apply runbook with the explicit two-pass ordering steps (W2), the B2 manual SWA-token-sync runbook, the B3 GHCR visibility runbook, M1–M13 smoke link, and 180-day SWA token rotation cadence"
    - "Prod env passes terraform fmt -check + terraform validate -backend=false"
  artifacts:
    - path: "infra/envs/prod/main.tf"
      provides: "Top-level prod composition: 6 module calls + SWA + RG + 4 KV secrets + role assignments + diagnostic_setting (W7)"
    - path: "infra/envs/prod/outputs.tf"
      provides: "Phase 4 hand-off bundle (11 outputs)"
    - path: "infra/envs/prod/prod.tfvars"
      provides: "home_ip, ghcr_username, ghcr_pat, swa_origin (empty initially per DEPL-12), tenant_id_external, tenant_subdomain, budget_alert_email, openai_api_key, langfuse_*, seeded_user_id, github_owner, github_repo"
    - path: "infra/envs/prod/README.md"
      provides: "Filled runbook: bootstrap → first apply → two-pass CORS → image push → GHCR visibility → manual SWA-token-sync → smoke checklist → security trade-offs → SWA token rotation → ordered runbook (W2)"
  key_links:
    - from: "infra/envs/prod/main.tf"
      to: "infra/modules/{network,kv,monitoring,database,compute,identity}"
      via: "module composition with explicit output → input wiring"
      pattern: "source.*\\.\\./\\.\\./modules"
    - from: "infra/envs/prod/main.tf"
      to: "FastAPI CORSMiddleware"
      via: "locals.allowed_origins_csv → module.compute.allowed_origins → ACA env var ALLOWED_ORIGINS → settings.allowed_origins (Phase 1 NoDecode)"
      pattern: "allowed_origins_csv"
    - from: "infra/envs/prod/main.tf (azurerm_monitor_diagnostic_setting.aca)"
      to: "module.compute.aca_id + module.monitoring.workspace_id"
      via: "diagnostic_setting at composition layer per W7 (NOT in monitoring module)"
      pattern: "azurerm_monitor_diagnostic_setting"
---

<objective>
Wave 2, Plan A (split from former Plan 05 per W4): Compose the six shared modules from Plans 03+04 into the active prod env. Add the ONE raw resource that didn't fit a module (Static Web App, per D-03). Add the four KV secrets that are not the Postgres password. Wire the role assignment that grants the deployer "Key Vault Secrets Officer". Build `locals.allowed_origins_csv` for the DEPL-12 two-pass CORS pattern. Declare the 11-output Phase 4 hand-off bundle. Add the post-compute `azurerm_monitor_diagnostic_setting.aca` at composition layer per W7 fix. Fill the prod README with the explicit ordered runbook (W2), the B2 manual SWA-token-sync, and the B3 GHCR visibility step.

Purpose: Plan 05a is the prod composition layer. Plan 05b (Wave 2, depends on 05a) handles dev scaffold + entrypoint + bootstrap-corpus workflow + CONTEXT.md A6 addendum.

Output: 8 files (the prod env directory). After this plan, `cd infra/envs/prod && terraform plan -var-file=prod.tfvars` produces a coherent plan against the bootstrap state backend.
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
@.planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md
@.planning/research/PITFALLS.md
@infra/modules/network/outputs.tf
@infra/modules/kv/outputs.tf
@infra/modules/monitoring/outputs.tf
@infra/modules/database/outputs.tf
@infra/modules/compute/outputs.tf
@infra/modules/identity/outputs.tf
@infra/bootstrap/outputs.tf
@src/job_rag/db/engine.py
@src/job_rag/api/app.py
@src/job_rag/config.py

<interfaces>
<!-- Module output contracts (read each module's outputs.tf) -->

network: env_id, env_default_domain, env_static_ip_address (informational only)
kv: kv_id, kv_uri, kv_name
monitoring: workspace_id, workspace_customer_id (via data source per W3), workspace_name
database: fqdn, admin_login, db_name, admin_password_secret_uri, admin_password_secret_name
compute: aca_id, aca_fqdn (via ingress[0].fqdn per W5), aca_principal_id, aca_name
identity: spa_app_client_id, api_app_client_id, api_app_identifier_uri, gha_client_id, gha_object_id, access_as_user_scope_id

bootstrap (Plan 02): storage_account_name, container_name, resource_group_name, tenant_id_external, tenant_subdomain

<!-- Static Web App raw resource per D-03 (RESEARCH.md lines 1147-1165) -->
```hcl
resource "azurerm_static_web_app" "spa" {
  name                = "jobrag-prod-spa"
  resource_group_name = azurerm_resource_group.prod.name
  location            = "westeurope"
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}
output "swa_default_origin"   { value = azurerm_static_web_app.spa.default_host_name }
output "swa_deployment_token" { value = azurerm_static_web_app.spa.api_key; sensitive = true }
```

<!-- Two-pass CORS locals pattern (RESEARCH.md lines 664-676) -->
```hcl
locals {
  allowed_origins_csv = join(",", compact([
    var.swa_origin == "" ? "" : var.swa_origin,
    "http://localhost:5173"
  ]))
}
```
</interfaces>

</context>

<tasks>

<task type="auto">
  <name>Task 1: Prod env composition (backend, provider, main, variables, outputs, locals, tfvars)</name>
  <files>
    - infra/envs/prod/backend.tf
    - infra/envs/prod/provider.tf
    - infra/envs/prod/main.tf
    - infra/envs/prod/variables.tf
    - infra/envs/prod/outputs.tf
    - infra/envs/prod/locals.tf
    - infra/envs/prod/prod.tfvars
  </files>
  <read_first>
    - .planning/phases/03-infrastructure-ci-cd/03-RESEARCH.md lines 462-497 (Pattern 2 — backend.tf + provider.tf canonical)
    - .planning/phases/03-infrastructure-ci-cd/03-RESEARCH.md lines 664-676 (locals.allowed_origins_csv + module call shape)
    - .planning/phases/03-infrastructure-ci-cd/03-RESEARCH.md lines 727-738 (Phase 4 hand-off output bundle — exact 11 outputs)
    - .planning/phases/03-infrastructure-ci-cd/03-RESEARCH.md lines 1147-1165 (azurerm_static_web_app shape + outputs)
    - .planning/phases/03-infrastructure-ci-cd/03-RESEARCH.md lines 313-325 (resource ordering: KV → role assignment → secrets → ACA → MI role assignment → diagnostic_setting)
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md A3 (refresh-swa-origin.sh exists from Plan 01; var.swa_origin starts empty)
    - All 6 module outputs.tf files (Plans 03+04 — read each to confirm exact output names before wiring)
    - infra/bootstrap/outputs.tf (Plan 02 — read to confirm tenant_id_external + tenant_subdomain output names)
  </read_first>
  <action>
Create 7 TF files in `infra/envs/prod/`. The directory already has README.md (Plan 01 skeleton) — Task 2 of this plan replaces its contents.

**File 1: `backend.tf`** — remote state backend pointing to bootstrap-created blob. Use placeholder names; runbook step 3 has Adrian replace them with real bootstrap output values.

```hcl
terraform {
  required_version = ">= 1.9"

  backend "azurerm" {
    # PLACEHOLDERS — replace with bootstrap output values per infra/bootstrap/README.md Step 3.
    # Real values look like: storage_account_name = "jobragtfstateab123" (yours will differ).
    resource_group_name  = "jobrag-tfstate-rg"
    storage_account_name = "REPLACE_FROM_BOOTSTRAP_OUTPUT"
    container_name       = "tfstate"
    key                  = "prod.tfstate"
    use_azuread_auth     = true
  }
}
```

**File 2: `provider.tf`** — pinned providers + `azurerm` features + dual `azuread` providers (workforce default + external alias).

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      # Respect purge_protection on prod KV (D-13). Phase 8 portfolio teardown
      # would require manual portal purge (intentional safety).
      purge_soft_delete_on_destroy = false
    }
  }
}

# Default azuread provider — workforce tenant (subscription home) per A4.
# Used for the GHA service principal + RG-scoped role assignment.
provider "azuread" {
  alias = "workforce"
  # tenant_id resolved from `az login` context — defaults to subscription home tenant.
}

# External tenant alias — used for SPA + API app registrations only.
provider "azuread" {
  alias     = "external"
  tenant_id = var.tenant_id_external
}
```

**File 3: `locals.tf`**:

```hcl
locals {
  prefix = "jobrag-prod"

  tags = {
    project    = "job-rag"
    env        = "prod"
    managed_by = "terraform"
  }

  # DEPL-12 two-pass CORS pattern.
  # First apply: var.swa_origin == "" → compact() drops it → only localhost.
  # Second apply (after scripts/refresh-swa-origin.sh): swa_origin is real → both.
  # B1 alignment: use empty-string + compact() (NOT null), matches identity module.
  allowed_origins_csv = join(",", compact([
    var.swa_origin == "" ? "" : var.swa_origin,
    "http://localhost:5173",
  ]))
}
```

**File 4: `variables.tf`**:

```hcl
# Resource group + region
variable "location" {
  type        = string
  description = "Azure region for prod resources."
  default     = "westeurope"
}

# Identity (External tenant + workforce GitHub OIDC)
variable "tenant_id_external" {
  type        = string
  description = "External tenant GUID — captured from bootstrap output (per D-05)."
}

variable "tenant_subdomain" {
  type        = string
  description = "External tenant subdomain (e.g. 'jobrag' for jobrag.ciamlogin.com)."
  default     = "jobrag"
}

variable "github_owner" {
  type        = string
  description = "GitHub repo owner — e.g. 'adrianzaplata'. Lowercased automatically in fed-cred subjects."
}

variable "github_repo" {
  type        = string
  description = "GitHub repo name — e.g. 'job-rag'."
  default     = "job-rag"
}

# CORS DEPL-12 two-pass
variable "swa_origin" {
  type        = string
  description = "SWA default origin. Empty on first apply; refreshed by scripts/refresh-swa-origin.sh."
  default     = ""
}

# Database firewall
variable "home_ip" {
  type        = string
  description = "Adrian's home IP for psql access. Refresh runbook in infra/modules/database/README.md."
}

# GHCR registry pull
variable "ghcr_username" {
  type        = string
  description = "GHCR username/org (lowercase) — typically same as github_owner."
}

variable "ghcr_pat" {
  type        = string
  description = "Fine-grained read-only PAT scoped to ghcr.io/<owner>/job-rag package. RESEARCH.md Pitfall §ghcr-pat: lives in TF state (sensitive=true)."
  sensitive   = true
}

variable "image_tag" {
  type        = string
  description = "Image tag — defaults to 'latest'. deploy-api.yml updates to ${{ github.sha }}. Per B5, the compute module's lifecycle.ignore_changes [template[0].container[0].image] means terraform apply will NOT revert the deploy-api.yml-pinned SHA after first push."
  default     = "latest"
}

# Application secrets
variable "openai_api_key" {
  type        = string
  description = "OpenAI API key — written to KV as 'openai-api-key' secret. ACA pulls via MI."
  sensitive   = true
}

variable "langfuse_public_key" {
  type        = string
  description = "Langfuse public key. Written to KV. Optional — empty string disables Langfuse (fail-open per Phase 1)."
  default     = ""
  sensitive   = true
}

variable "langfuse_secret_key" {
  type        = string
  description = "Langfuse secret key. Written to KV."
  default     = ""
  sensitive   = true
}

variable "seeded_user_entra_oid" {
  type        = string
  description = "Adrian's Entra oid placeholder per D-09. Empty on first Phase 3 apply; Phase 4 fills after first MSAL login."
  default     = "00000000-0000-0000-0000-000000000000"
  sensitive   = true
}

variable "seeded_user_id" {
  type        = string
  description = "Adrian's UUID per Phase 1 D-08 (SEEDED_USER_ID). Used by ACA env var until Phase 4 swap."
}

variable "budget_alert_email" {
  type        = string
  description = "Email recipient for budget alerts."
  default     = "adrianzaplata@gmail.com"
}
```

(Note: `subscription_id` variable is NOT declared at composition layer — the monitoring module uses `data "azurerm_subscription" "current"` per W1.)

**File 5: `main.tf`** — the composition. Sequencing per RESEARCH.md lines 313-325:

```hcl
# ─── Resource group (root container for all prod resources) ────────────────────

resource "azurerm_resource_group" "prod" {
  name     = "${local.prefix}-rg"
  location = var.location
  tags     = local.tags
}

data "azurerm_client_config" "current" {}

# ─── Identity (External tenant app regs + GHA SP federated credentials) ────────

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
}

# ─── Monitoring (LAW workspace + budget) ───────────────────────────────────────

module "monitoring" {
  source = "../../modules/monitoring"

  env                 = "prod"
  location            = var.location
  resource_group_name = azurerm_resource_group.prod.name
  create_budget       = true # prod owns the single subscription-scoped budget
  budget_alert_email  = var.budget_alert_email
  tags                = local.tags
  # NOTE (W7): aca_id no longer wired — diagnostic_setting moved to composition layer below.
  # NOTE (W1): subscription_id NOT passed — monitoring module uses data.azurerm_subscription.current.
}

# ─── Network (ACA Container App Environment) ──────────────────────────────────

module "network" {
  source = "../../modules/network"

  env                        = "prod"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.prod.name
  log_analytics_workspace_id = module.monitoring.workspace_id
  tags                       = local.tags
}

# ─── KV (Key Vault) ───────────────────────────────────────────────────────────

module "kv" {
  source = "../../modules/kv"

  env                 = "prod"
  location            = var.location
  resource_group_name = azurerm_resource_group.prod.name
  tenant_id_workforce = data.azurerm_client_config.current.tenant_id
  aca_principal_id    = null # wired separately AFTER compute creates the MI
  tags                = local.tags
}

# Deployer gets "Key Vault Secrets Officer" — required to WRITE secrets.
resource "azurerm_role_assignment" "deployer_kv_secrets_officer" {
  scope                = module.kv.kv_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ─── Database (Postgres Flex + random_password + KV secret) ────────────────────

module "database" {
  source = "../../modules/database"

  env                         = "prod"
  location                    = var.location
  resource_group_name         = azurerm_resource_group.prod.name
  key_vault_id                = module.kv.kv_id
  kv_admin_role_assignment_id = azurerm_role_assignment.deployer_kv_secrets_officer.id
  home_ip                     = var.home_ip
  use_allow_azure_services    = true # A1 Path A
  tags                        = local.tags
}

# ─── Application secrets in KV (4 secrets — postgres password is owned by database module) ─

resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  value        = var.openai_api_key
  key_vault_id = module.kv.kv_id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "langfuse_public_key" {
  name         = "langfuse-public-key"
  value        = var.langfuse_public_key
  key_vault_id = module.kv.kv_id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "langfuse_secret_key" {
  name         = "langfuse-secret-key"
  value        = var.langfuse_secret_key
  key_vault_id = module.kv.kv_id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "seeded_user_entra_oid" {
  name         = "seeded-user-entra-oid"
  value        = var.seeded_user_entra_oid
  key_vault_id = module.kv.kv_id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets_officer]
}

# ─── Compute (Container App) ──────────────────────────────────────────────────

module "compute" {
  source = "../../modules/compute"

  env                  = "prod"
  resource_group_name  = azurerm_resource_group.prod.name
  aca_env_id           = module.network.env_id
  ghcr_username        = var.ghcr_username
  ghcr_pat             = var.ghcr_pat
  image_tag            = var.image_tag
  postgres_fqdn        = module.database.fqdn
  postgres_admin_login = module.database.admin_login
  allowed_origins      = local.allowed_origins_csv
  seeded_user_id       = var.seeded_user_id
  tags                 = local.tags

  kv_secret_uris = {
    "openai-api-key"          = azurerm_key_vault_secret.openai_api_key.versionless_id
    "postgres-admin-password" = module.database.admin_password_secret_uri
    "langfuse-public-key"     = azurerm_key_vault_secret.langfuse_public_key.versionless_id
    "langfuse-secret-key"     = azurerm_key_vault_secret.langfuse_secret_key.versionless_id
    "seeded-user-entra-oid"   = azurerm_key_vault_secret.seeded_user_entra_oid.versionless_id
  }
}

# ─── Post-Compute role assignment: ACA system MI gets KV Secrets User ─────────

resource "azurerm_role_assignment" "aca_kv_secrets_user" {
  scope                = module.kv.kv_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = module.compute.aca_principal_id
}

# ─── Monitoring diagnostic setting (W7: lives at composition, NOT in monitoring module) ─
# References module.compute.aca_id (Container App created above) and
# module.monitoring.workspace_id (LAW created in monitoring module).
# D-16: ContainerAppConsoleLogs_CL only; SystemLogs_CL deliberately omitted.

resource "azurerm_monitor_diagnostic_setting" "aca" {
  name                       = "${local.prefix}-aca-diag"
  target_resource_id         = module.compute.aca_id
  log_analytics_workspace_id = module.monitoring.workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs_CL"
  }
  # NOTE: ContainerAppSystemLogs_CL intentionally omitted per D-16.
}

# ─── Static Web App (raw — D-03 single-resource, no AVM) ──────────────────────

resource "azurerm_static_web_app" "spa" {
  name                = "${local.prefix}-spa"
  resource_group_name = azurerm_resource_group.prod.name
  location            = var.location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}
```

**File 6: `outputs.tf`** — 11-output Phase 4 hand-off bundle:

```hcl
output "swa_default_origin" {
  description = "SWA default host name (without https://). scripts/refresh-swa-origin.sh reads this for the DEPL-12 two-pass."
  value       = azurerm_static_web_app.spa.default_host_name
}

output "aca_fqdn" {
  description = "Container App stable env FQDN (per W5, via ingress[0].fqdn) — Phase 4 frontend axios baseURL."
  value       = module.compute.aca_fqdn
}

output "kv_name" {
  description = "Key Vault name (jobrag-prod-kv) — Phase 4 reference for portal navigation."
  value       = module.kv.kv_name
}

output "kv_uri" {
  description = "Key Vault DNS URI (https://jobrag-prod-kv.vault.azure.net/)."
  value       = module.kv.kv_uri
}

output "tenant_subdomain" {
  description = "External tenant subdomain (jobrag) — Phase 4 builds MSAL authority."
  value       = var.tenant_subdomain
}

output "tenant_id" {
  description = "External tenant GUID — Phase 4 MSAL authority + audience."
  value       = var.tenant_id_external
}

output "spa_app_client_id" {
  description = "SPA app reg client ID — Phase 4 MSAL clientId."
  value       = module.identity.spa_app_client_id
}

output "api_app_client_id" {
  description = "API app reg client ID — Phase 4 MSAL apiClientId."
  value       = module.identity.api_app_client_id
}

output "gha_client_id" {
  description = "GitHub Actions SP client ID — set as repo secret AZURE_CLIENT_ID."
  value       = module.identity.gha_client_id
}

# B2 (locked decision): swa_deployment_token is exposed as a sensitive output.
# Adrian copies it into AZURE_STATIC_WEB_APPS_API_TOKEN_PROD MANUALLY from his local
# terminal after first apply (see prod README "Phase-close: GitHub secrets sync").
# Aliased as `swa_api_key` for runbook readability since the manual command pipes
# `terraform output -raw swa_api_key`.
output "swa_deployment_token" {
  description = "SWA api_key — sole long-lived secret in the system (per A2/D-08). Sync MANUALLY to AZURE_STATIC_WEB_APPS_API_TOKEN_PROD via the runbook in prod README. NO automated `gh secret set` step (B2)."
  value       = azurerm_static_web_app.spa.api_key
  sensitive   = true
}

output "swa_api_key" {
  description = "Alias of swa_deployment_token — used by the manual runbook command `terraform output -raw swa_api_key | gh secret set ...` (B2 locked decision)."
  value       = azurerm_static_web_app.spa.api_key
  sensitive   = true
}

output "seeded_user_entra_oid_secret_name" {
  description = "KV secret name for the placeholder seeded oid — Phase 4 writes the real oid here after first MSAL login (D-09)."
  value       = "seeded-user-entra-oid"
}
```

**File 7: `prod.tfvars`**:

```hcl
# Adrian's prod environment values.
# tfvars files are committed (no secrets in literal form — secrets come from terraform.tfvars.local
# or `-var` CLI flags or environment TF_VAR_*).

# Region
location = "westeurope"

# External tenant — replace tenant_id_external with bootstrap output value
tenant_id_external = "REPLACE_FROM_BOOTSTRAP_OUTPUT"
tenant_subdomain   = "jobrag"

# GitHub
github_owner = "adrianzaplata"
github_repo  = "job-rag"

# CORS — DEPL-12 two-pass.
# First apply: leave empty → ALLOWED_ORIGINS = "http://localhost:5173".
# Second apply (after scripts/refresh-swa-origin.sh): script rewrites to "https://<swa-default>".
swa_origin = ""

# Postgres firewall — Adrian's home IP (refresh via runbook in modules/database/README.md)
home_ip = "REPLACE_WITH_CURRENT_HOME_IP"

# GHCR
ghcr_username = "adrianzaplata"
# ghcr_pat — DO NOT commit; provide via TF_VAR_ghcr_pat or terraform.tfvars.local
image_tag     = "latest"

# Budget
budget_alert_email = "adrianzaplata@gmail.com"

# Application IDs
seeded_user_id        = "REPLACE_WITH_ADRIAN_UUID" # Phase 1 D-08 SEEDED_USER_ID
seeded_user_entra_oid = "00000000-0000-0000-0000-000000000000" # Phase 4 fills after first login

# Application secrets — DO NOT commit; provide via terraform.tfvars.local or TF_VAR_*
# openai_api_key       = "..."
# langfuse_public_key  = "..."
# langfuse_secret_key  = "..."
```
  </action>
  <verify>
    <automated>cd infra/envs/prod && terraform fmt -check && terraform init -backend=false && terraform validate</automated>
  </verify>
  <done>All 7 files exist; `backend.tf` has `backend "azurerm"` block with `key = "prod.tfstate"`; `provider.tf` has dual `azuread` providers (workforce + external alias); `locals.tf` has `allowed_origins_csv` with `compact()` + `join(",", ...)` pattern using empty-string filter (B1 alignment); `main.tf` calls all 6 modules with explicit `providers = { azuread.external, azuread.workforce }` map on identity module; main.tf creates 4 KV secrets all depends_on `deployer_kv_secrets_officer` role assignment; main.tf has the post-compute `aca_kv_secrets_user` role assignment; **main.tf has the W7 composition-layer `azurerm_monitor_diagnostic_setting.aca` referencing module.compute.aca_id + module.monitoring.workspace_id**; main.tf has raw `azurerm_static_web_app.spa` with sku_tier/sku_size = Free; `outputs.tf` declares all 11 hand-off outputs PLUS `swa_api_key` alias for the B2 manual runbook; `prod.tfvars` has placeholder values; `terraform validate` passes.</done>
</task>

<task type="auto">
  <name>Task 2: Fill prod README with explicit ordered runbook (W2), B2 manual SWA-token-sync, B3 GHCR visibility</name>
  <files>
    - infra/envs/prod/README.md
  </files>
  <read_first>
    - infra/envs/prod/README.md (Plan 01 skeleton — fill the section bodies)
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md A1 (Path A trade-offs documentation contract)
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md A2 (public repo, B2 manual SWA token rotation)
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md A6 (NEW — entrypoint scope + bootstrap-corpus.yml)
    - .planning/phases/03-infrastructure-ci-cd/03-RESEARCH.md lines 805-809 (SWA api_key 180-day rotation cadence)
    - .planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md lines 70-89 (Manual-Only Verifications M1–M13)
    - infra/modules/database/README.md (cross-reference home IP refresh runbook)
  </read_first>
  <action>
REPLACE Plan 01's skeleton stubs with concrete content. Preserve the section heading structure (verification grep depends on these): `# Prod environment`, `## First apply (pass 1)`, `## Two-Pass CORS Bootstrap`, `## Image push and ACA revision update`, `## Post-apply smoke checklist`, `## Knowingly-accepted security trade-offs`, `## Token rotation cadence`. Add NEW sections per W2/B2/B3: `## Ordered runbook (numbered steps)`, `## Phase-close: GitHub secrets sync` (B2), `## Image push: GHCR visibility` (B3), and a phase-close pointer to `bootstrap-corpus.yml` (A6).

Concrete content:

```markdown
# Prod environment

> Active production environment for the job-rag stack. Provisions ACA + Postgres B1ms with pgvector + SWA Free + KV with 5 secrets + LAW with daily quota + €10/mo budget alert. Two-pass apply per DEPL-12 to resolve the SWA-origin ↔ ALLOWED_ORIGINS cycle.

---

## Prerequisites

- `infra/bootstrap/` has already been applied (per `infra/bootstrap/README.md`).
- `backend.tf` placeholder values have been replaced with real bootstrap outputs (Step 3 of bootstrap runbook).
- `terraform.tfvars.local` (gitignored) provides the secret variables: `ghcr_pat`, `openai_api_key`, `langfuse_public_key`, `langfuse_secret_key` (or use `TF_VAR_*` env vars).
- Adrian is signed in via `az login` to the subscription that owns `jobrag-tfstate-rg`.

## Ordered runbook (W2 — explicit step ordering)

The two-pass apply is sequenced per the W2 fix to make the "image not deployed yet" expectation explicit:

1. **Bootstrap apply** (one-time, separate directory): `cd infra/bootstrap && terraform apply` — creates state-storage RG. (See `infra/bootstrap/README.md`.)
2. **Prod env pass 1**: `cd infra/envs/prod && terraform init && terraform apply -var-file=prod.tfvars` — creates ACA + SWA + KV + Postgres + LAW + budget. **Expected behavior:** the Container App revision will fail to start (image tag `latest` doesn't exist in GHCR yet). This is normal at this stage; the resource exists, just no image to run.
3. **First image push**: either run `deploy-api.yml` manually via `gh workflow run deploy-api.yml --ref master`, OR push from local: `docker push ghcr.io/adrianzaplata/job-rag:latest`. (See "Image push: GHCR visibility" below for the B3 visibility step.)
4. **Prod env pass 2** (CORS injection): `bash ../../../scripts/refresh-swa-origin.sh` — script rewrites `swa_origin` in tfvars and re-applies. The Container App revision now starts cleanly (image exists, ALLOWED_ORIGINS now includes the SWA origin).
5. **GitHub secrets sync** (manual, B2): `terraform output -raw swa_api_key | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD --repo adrianzaplata/job-rag`. (See "Phase-close: GitHub secrets sync" below.)
6. **Corpus bootstrap** (one-time, A6): `gh workflow run bootstrap-corpus.yml --ref master`. (See "Corpus bootstrap" below.)
7. **M1–M13 smoke** (Plan 07): execute the live-Azure smoke per `.planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md`.

## First apply (pass 1)

```bash
cd infra/envs/prod

terraform init
terraform plan -var-file=prod.tfvars -out=plan-pass-1.tfplan
terraform apply plan-pass-1.tfplan
```

After apply succeeds, the SWA exists and `terraform output -raw swa_default_origin` returns its hostname. The Container App's `ALLOWED_ORIGINS` env var contains only `http://localhost:5173` at this point (per `locals.allowed_origins_csv` with `var.swa_origin = ""`). The Container App revision will fail to start (no image yet) — that's expected; proceed to image push.

## Two-Pass CORS Bootstrap

```bash
bash ../../../scripts/refresh-swa-origin.sh
```

The script:
1. Reads `terraform output -raw swa_default_origin`.
2. Rewrites `prod.tfvars` to set `swa_origin = "https://<swa-default-host>"` (idempotent).
3. Runs `terraform apply -var-file=prod.tfvars -auto-approve`.

Result: the Container App's `ALLOWED_ORIGINS` env var becomes `"https://<swa-default-host>,http://localhost:5173"`; the SPA app reg's `redirect_uris` includes both local + prod.

Verify: `curl -H "Origin: https://<swa-default-host>" https://<aca-fqdn>/health` returns 200 with CORS headers; `curl -H "Origin: https://evil.example" https://<aca-fqdn>/health` is rejected.

## Image push: GHCR visibility (B3)

After the first `docker push` (manual or via `deploy-api.yml`), the GHCR package's visibility may default to private. ACA must be able to pull. Two paths:

**Recommended (portfolio repo per A2 — public):**
1. Visit `https://github.com/adrianzaplata/job-rag/pkgs/container/job-rag` → "Package settings" → "Manage Actions access" + "Change visibility" → set to **Public**.
2. ACA can pull anonymously; no PAT scope required at runtime (the registry block in compute module still uses `var.ghcr_pat` for first-pull but reads anonymous if package is public).

**Alternative (private package):**
1. Generate a fine-grained PAT with `read:packages` scope on the `job-rag` package only (90-day expiry max).
2. Update `var.ghcr_pat` in `terraform.tfvars.local` and re-apply.

Reference: [GitHub Docs — Configuring a package's access control and visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

## Image push and ACA revision update

The first apply uses `image_tag = "latest"` (default in prod.tfvars). The actual image push happens via `deploy-api.yml` (Plan 06):

1. Push to `master` with changes under `src/**` / `pyproject.toml` / `uv.lock` / `Dockerfile` / `alembic/**`.
2. `deploy-api.yml` builds + pushes to `ghcr.io/adrianzaplata/job-rag:${{ github.sha }}` + `:latest`.
3. `az containerapp update --image ghcr.io/.../job-rag:${{ github.sha }}` swaps the revision.

**B5 alignment:** the compute module has `lifecycle { ignore_changes = [template[0].container[0].image, template[0].revision_suffix] }` so subsequent `terraform apply` runs do NOT revert the SHA-pinned revision deployed by CI.

Manual fallback (when GHA is broken or image needs a hand-fix):

```bash
docker build -t ghcr.io/adrianzaplata/job-rag:manual .
echo "$GHCR_PAT" | docker login ghcr.io -u adrianzaplata --password-stdin
docker push ghcr.io/adrianzaplata/job-rag:manual

az containerapp update \
  --name jobrag-prod-api \
  --resource-group jobrag-prod-rg \
  --image ghcr.io/adrianzaplata/job-rag:manual
```

## Phase-close: GitHub secrets sync (B2 — manual runbook)

The SWA `api_key` is the sole long-lived secret in the system (A2 + D-08). It must reach `AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` so `deploy-spa.yml` can authenticate. The B2 locked decision: **NO automated `gh secret set` step in `deploy-infra.yml`** (avoids needing a long-lived `GH_PAT_FOR_SECRETS`). Adrian runs the sync manually from a local terminal:

```bash
cd infra/envs/prod
terraform output -raw swa_api_key | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD --repo adrianzaplata/job-rag
```

**When to run:**
- After the first prod apply.
- On SWA token rotation (~180 days, Microsoft default — `learn.microsoft.com/en-us/azure/static-web-apps/deployment-token-management`).
- Set a calendar reminder for the 180-day cadence.

The `terraform output -raw` reads from local TF state (must run from a clone with backend.tf pointing at the bootstrap state); `gh secret set` reads from stdin and never echoes the value to the terminal. Both ends respect the secret boundary.

## Corpus bootstrap (A6 — one-time)

Per CONTEXT.md A6, the ACA `docker-entrypoint.sh` runs ONLY `job-rag init-db` + `uvicorn`. Corpus ingest + embed are decoupled into `.github/workflows/bootstrap-corpus.yml` (created in Plan 05b). After the first deploy, run once:

```bash
gh workflow run bootstrap-corpus.yml --ref master
```

The workflow uses the same OIDC federated credential as `deploy-api.yml`, then `az containerapp exec` to run `job-rag ingest --show-cost && job-rag embed --show-cost` against the live container.

**When to run:**
- After the first prod apply (one-time corpus seed).
- On `PROMPT_VERSION` bumps that require full re-extraction (rare — Phase 2-rev plans).

The workflow is `workflow_dispatch` only — never auto-runs. Re-running it without a corpus refresh is a safe no-op (ingest skips already-ingested files via content hash dedup).

## Post-apply smoke checklist

Run the M1–M13 smoke runbook documented in `.planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md` lines 70–89. Plan 07 ships the evidence file `03-SMOKE.md`. Highlights:

- **M3** CORS: `curl -H "Origin: https://evil.example" <aca-fqdn>/health` rejected.
- **M7** KV resolution: `az containerapp exec ... -- env | grep OPENAI_API_KEY` shows resolved value.
- **M8** pgvector: `psql -h <pg-fqdn> -U jobragadmin -d jobrag -c "\dx"` shows `vector` extension.
- **M11** SSE survival: `curl -N <aca-fqdn>/agent/stream` streams over multiple seconds; revision swap during stream drains cleanly per `termination_grace_period_seconds=120`.
- **M13** TF state hygiene: `terraform state pull | jq '.. | select(type=="string") | select(test("sk-"))'` returns empty.

## Knowingly-accepted security trade-offs

Per CONTEXT.md Plan-Locking Addendum A1 (Path A) and Plan 04 module READMEs:

| Trade-off | Rationale | Mitigation |
|-----------|-----------|------------|
| Postgres `public_network_access_enabled = true` | Private endpoint costs ~€130/mo; breaks €0 budget. | TLS-only (`require_secure_transport=on`) + 32-char random alphanumeric password in KV. |
| Postgres firewall includes `0.0.0.0` "Allow Azure services" rule | ACA Consumption-tier outbound IP is documented non-stable; per-IP allowlist would silently break. | Same TLS + password boundary; tfsec allowlist documented in `infra/.tfsec/config.yml`. |
| GHCR PAT lives in TF state | Chicken-and-egg: ACA needs to pull image before MI can resolve KV refs. | PAT is fine-grained read-only on the package; `var.ghcr_pat` is `sensitive = true`; rotate per below. (Or set package public per B3 to skip the PAT path entirely.) |
| SWA `api_key` flows through TF state | SWA does not yet support OIDC GA. | `sensitive = true`; rotated per below; only consumed by deploy-spa.yml; B2: synced manually, no `GH_PAT_FOR_SECRETS` in the system. |
| `min_replicas = 0` causes cold-start latency | Free-tier vCPU-sec budget would be blown by `min_replicas = 1` (~€15-20/mo). | Phase 6 ships UX states (`connecting` / `warming` / `streaming`) per CONTEXT.md D-17. |

## Token rotation cadence

| Token | Cadence | Procedure |
|-------|---------|-----------|
| `var.openai_api_key` (KV: `openai-api-key`) | When OpenAI rotates or exposed | `terraform apply -var openai_api_key="<new>"` updates KV; ACA picks up on next revision swap |
| `var.langfuse_public_key` / `secret_key` | When rotated in Langfuse Cloud | Same as above |
| `var.ghcr_pat` | 90 days (GitHub fine-grained PAT max) | Generate new PAT; `terraform apply -var ghcr_pat="<new>"` rotates registry secret |
| Postgres admin password (KV: `postgres-admin-password`) | On-demand only | `terraform taint module.database.random_password.pg_admin && terraform apply` |
| SWA api_key (KV: N/A — direct GH secret) | **180 days** (Microsoft default) | Run the B2 manual sync command above (`terraform output -raw swa_api_key | gh secret set ...`) from local. NO automated rotation in workflow per B2. |
| GHA SP federated credentials | Never (OIDC = no long-lived secret to rotate) | n/a |

The SWA api_key is the **sole long-lived secret** in the system per A2 + D-08 + RESEARCH.md Pitfall §SWA api_key.

## Home IP refresh

Adrian's home IP rotates with ISP DHCP. Refresh procedure documented in `infra/modules/database/README.md` (sed-based one-liner update of `prod.tfvars`).

## Drift detection

Run `terraform plan -var-file=prod.tfvars` periodically. A non-empty plan against an unchanged repo means someone portal-edited a resource, OR the live image diverged from `var.image_tag` (expected per B5 — terraform's view of the image is intentionally stale after first deploy-api.yml run).
```
  </action>
  <verify>
    <automated>grep -q "First apply (pass 1)" infra/envs/prod/README.md && grep -q "Two-Pass CORS Bootstrap" infra/envs/prod/README.md && grep -q "Knowingly-accepted security trade-offs" infra/envs/prod/README.md && grep -q "Token rotation cadence" infra/envs/prod/README.md && grep -q "180" infra/envs/prod/README.md && grep -q "M1" infra/envs/prod/README.md && grep -q "M13" infra/envs/prod/README.md && grep -q "Phase-close: GitHub secrets sync" infra/envs/prod/README.md && grep -q "gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD" infra/envs/prod/README.md && grep -q "Image push: GHCR visibility" infra/envs/prod/README.md && grep -q "Ordered runbook" infra/envs/prod/README.md && grep -q "bootstrap-corpus.yml" infra/envs/prod/README.md</automated>
  </verify>
  <done>infra/envs/prod/README.md has all required sections filled with concrete commands + tables; **W2: explicit numbered "Ordered runbook" section enumerates the 7-step sequence (bootstrap → pass 1 → image push → pass 2 → secrets sync → corpus bootstrap → smoke)**; **B2: "Phase-close: GitHub secrets sync" section documents the manual `terraform output -raw swa_api_key | gh secret set ...` command + 180-day cadence**; **B3: "Image push: GHCR visibility" section documents the public-package recommendation + private-package PAT path with a link to GitHub docs**; **A6: "Corpus bootstrap" section documents the one-time `gh workflow run bootstrap-corpus.yml` command**; rotation table includes the 180-day SWA token entry with manual procedure; smoke checklist references M1 + M13 (links to VALIDATION.md).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| TF state ← composition layer | 4 application secrets are written to KV via `azurerm_key_vault_secret` resources. The literal values land in TF state; sensitive=true marking + RBAC-only state access (`use_azuread_auth = true`) is the boundary. |
| Container App ← KV (5 secret references) | All resolution happens via system MI + key_vault_secret_id URIs at container start; values never enter the Container App resource's TF state. |
| GHA-driven `terraform apply` ← OIDC | Authenticates via `azure/login@v2`; `gha-environment-production` federated credential. RG-scoped Contributor caps blast radius. |
| Adrian's local terminal → AZURE_STATIC_WEB_APPS_API_TOKEN_PROD secret (B2) | Manual `terraform output -raw swa_api_key | gh secret set ...` reads from local TF state + writes to repo secret via Adrian's authenticated `gh` CLI. No long-lived `GH_PAT_FOR_SECRETS` in the system. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-3-01 (HIGH) | Information Disclosure | App-supplied secrets in TF state | mitigate | All 4 secret variables are `sensitive = true`; TLS-encrypted-at-rest blob backend + RBAC-only access (`use_azuread_auth = true`). M13 smoke (Plan 07) verifies state has no `sk-` literals. |
| T-3-08 (HIGH) | Spoofing | CORS bypass | mitigate | `locals.allowed_origins_csv` uses `compact()` (B1 empty-string filter); CSV format matches Phase 1 NoDecode contract; two-pass guarantees only Adrian's SWA + localhost are allowed. |
| T-3-03 (HIGH) | Information Disclosure | Postgres exposed | accept (per A1) | Documented in prod README "Knowingly-accepted security trade-offs". |
| T-3-05 (MEDIUM) | Information Disclosure | SWA api_key in TF state | mitigate | `sensitive = true`; **B2: synced manually via local `gh secret set` command** — no `GH_PAT_FOR_SECRETS` in the system; 180-day rotation cadence in prod README. |
| T-3-04 (MEDIUM) | Information Disclosure | GHCR PAT in TF state | mitigate | `sensitive = true`; 90-day cadence; **B3: alternative path is public-package visibility (no runtime PAT needed)** — documented in prod README. |
| T-3-02 | Spoofing | Wrong tenant for KV | mitigate | KV's `tenant_id_workforce` wired from `data.azurerm_client_config.current.tenant_id` (workforce); `azuread.external` provider alias only used for SPA + API app regs. |
</threat_model>

<verification>
- `cd infra/envs/prod && terraform fmt -check && terraform init -backend=false && terraform validate` exits 0
- All 11 hand-off outputs declared in `infra/envs/prod/outputs.tf` PLUS `swa_api_key` alias for B2
- `infra/envs/prod/main.tf` references all 6 modules from `../../modules/`
- `infra/envs/prod/main.tf` has `azurerm_monitor_diagnostic_setting.aca` at composition layer per W7
- prod README has W2/B2/B3/A6 sections and the M1–M13 smoke link
</verification>

<success_criteria>
1. Prod env composition (8 files) passes `terraform fmt -check` + `terraform validate -backend=false`.
2. All 6 modules from Plans 03+04 are wired in `envs/prod/main.tf` with explicit output→input wiring.
3. `azurerm_role_assignment.deployer_kv_secrets_officer` lives at composition layer (correct: deployer identity varies between local and GHA).
4. Post-compute `azurerm_role_assignment.aca_kv_secrets_user` + W7 `azurerm_monitor_diagnostic_setting.aca` lift to composition layer.
5. Phase 4 hand-off bundle (11 outputs) is exhaustive; `swa_api_key` alias added for B2.
6. Prod README has the W2 ordered runbook, B2 manual SWA-token-sync section, B3 GHCR visibility section, A6 corpus bootstrap section, M1–M13 smoke link, 180-day SWA token rotation cadence.
</success_criteria>

<output>
After completion, create `.planning/phases/03-infrastructure-ci-cd/03-05a-SUMMARY.md`.
</output>
