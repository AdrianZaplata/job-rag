# ─── Resource group (root container for all prod resources) ────────────────────

resource "azurerm_resource_group" "prod" {
  name     = "${local.prefix}-rg"
  location = var.location
  tags     = local.tags
}

data "azurerm_client_config" "current" {}

# Gap 8.D: subscription resource ID (full /subscriptions/<guid> form) for the
# GHA SP's Cost Management Contributor role assignment scope. client_config
# returns subscription_id as bare GUID; subscription data source returns the
# full resource ID needed by azurerm_role_assignment.scope.
data "azurerm_subscription" "current" {}

# ─── Identity (External tenant app regs + GHA SP federated credentials) ────────

module "identity" {
  source = "../../modules/identity"

  providers = {
    azuread.workforce = azuread.workforce
  }

  swa_origin        = var.swa_origin
  github_owner      = var.github_owner
  github_repo       = var.github_repo
  resource_group_id = azurerm_resource_group.prod.id
  kv_id             = module.kv.kv_id                      # Gap 8.B: KV-scoped Secrets Officer for GHA SP
  subscription_id   = data.azurerm_subscription.current.id # Gap 8.D: sub-scoped Cost Mgmt Contributor (D-08 named exception)
}

# ─── Grant GHA SP the data-plane role needed to read/write remote tfstate ─────
# deploy-infra.yml authenticates as the GHA SP via OIDC and runs `terraform apply`
# from infra/envs/prod/. The backend uses use_azuread_auth=true, so the SP needs
# Storage Blob Data Contributor on the tfstate container — subscription-Contributor
# (granted by the identity module at RG scope) does NOT cover blob data plane.

# Gap A fix (2026-05-12): the prior shape used a `data "azurerm_storage_account"`
# block to look up the tfstate account id. That data lookup requires control-plane
# permission `Microsoft.Storage/storageAccounts/read` on jobrag-tfstate-rg, which
# the GHA SP does NOT hold (it only has Blob Data Contributor, data plane only,
# per D-08). Local apply works because Adrian is sub-Owner; CI fails on refresh
# with 403 AuthorizationFailed. The scope string below is now constructed from
# values already in state (subscription id + var.tfstate_* names) so no
# control-plane read is needed. D-08 stays untouched.
resource "azurerm_role_assignment" "gha_tfstate_blob_data_contributor" {
  scope                = "${data.azurerm_subscription.current.id}/resourceGroups/${var.tfstate_resource_group_name}/providers/Microsoft.Storage/storageAccounts/${var.tfstate_storage_account_name}/blobServices/default/containers/${var.tfstate_container_name}"
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.identity.gha_object_id
  description          = "Grants the GitHub Actions federated SP read/write access to terraform state blobs via AAD auth (deploy-infra.yml)."
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
# Gap H fix (2026-05-12): principal_id is pinned via var.deployer_object_id
# rather than data.azurerm_client_config.current.object_id. The data source
# evaluates differently across contexts (Adrian's user OID on local apply vs
# the GHA SP OID under CI's OIDC auth), so refresh on CI wants to REPLACE the
# role assignment (destroy Adrian's KV access, grant to the SP). Pinning makes
# state stable across local + CI contexts. The GHA SP has its own KV access
# via gha_kv_secrets_officer (Gap 8.B), so this resource is exclusively for
# the human deployer's data-plane access during local apply.
resource "azurerm_role_assignment" "deployer_kv_secrets_officer" {
  scope                = module.kv.kv_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.deployer_object_id
}

# ─── Database (Postgres Flex + random_password + KV secret) ────────────────────

module "database" {
  source = "../../modules/database"

  env = "prod"
  # Postgres Flex is offer-restricted on this subscription in westeurope AND
  # germanywestcentral (LocationIsOfferRestricted). northeurope (Ireland) is
  # the standard fallback for free-tier PG Flex on German subscriptions.
  # Cross-region ACA(westeurope)→PG(northeurope) is acceptable for v1.
  location                    = "northeurope"
  resource_group_name         = azurerm_resource_group.prod.name
  key_vault_id                = module.kv.kv_id
  kv_admin_role_assignment_id = azurerm_role_assignment.deployer_kv_secrets_officer.id
  home_ip                     = var.home_ip
  use_allow_azure_services    = true # A1 Path A
  tags                        = local.tags
}

# ─── Application secrets in KV (4 secrets — postgres password is owned by database module) ─
#
# OUT-OF-BAND SEEDING (Option B):
# openai/langfuse secret VALUES are NOT managed by Terraform. TF creates the secret
# resource shells with a placeholder value; Adrian seeds the real values once via
# `az keyvault secret set ...` (see prod/README.md "Out-of-band secret seeding"),
# and `lifecycle.ignore_changes = [value]` keeps subsequent applies from clobbering
# them. This keeps OPENAI_API_KEY out of GitHub Actions secrets entirely.

resource "azurerm_key_vault_secret" "openai_api_key" {
  name             = "openai-api-key"
  value_wo         = "managed-out-of-band"
  value_wo_version = 1
  key_vault_id     = module.kv.kv_id
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.deployer_kv_secrets_officer]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "langfuse_public_key" {
  name             = "langfuse-public-key"
  value_wo         = "managed-out-of-band"
  value_wo_version = 1
  key_vault_id     = module.kv.kv_id
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.deployer_kv_secrets_officer]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "langfuse_secret_key" {
  name             = "langfuse-secret-key"
  value_wo         = "managed-out-of-band"
  value_wo_version = 1
  key_vault_id     = module.kv.kv_id
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.deployer_kv_secrets_officer]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "seeded_user_entra_oid" {
  name             = "seeded-user-entra-oid"
  value_wo         = var.seeded_user_entra_oid
  value_wo_version = 1
  key_vault_id     = module.kv.kv_id
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.deployer_kv_secrets_officer]
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
# Diagnostic categories ContainerAppConsoleLogs / ContainerAppSystemLogs are
# only exposed at the Microsoft.App/managedEnvironments resource level — the
# individual containerApp resource does NOT accept them (verified by 400
# "Category 'ContainerAppConsoleLogs' is not supported" against the app ID).
# Target the env instead; logs from every Container App in the env flow into
# the same LAW table.
# D-16: ContainerAppConsoleLogs only; ContainerAppSystemLogs deliberately omitted.
# (The `_CL` suffix is the LAW *table name* — diagnostic category names drop it.)

resource "azurerm_monitor_diagnostic_setting" "aca" {
  name                       = "${local.prefix}-aca-diag"
  target_resource_id         = module.network.env_id
  log_analytics_workspace_id = module.monitoring.workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs"
  }
  # NOTE: ContainerAppSystemLogs intentionally omitted per D-16.
}

# ─── KV diagnostic setting (Gap 10.A: KV -> LAW audit pipe) ───────────────────
# Wires Key Vault secret-read operations into LAW so the ACA managed identity's
# secret access is auditable. Without this, `az monitor diagnostic-settings list
# --resource <kv-id>` returns empty and any LAW KQL query against AzureDiagnostics
# for jobrag-prod-kv has nothing to return.
#
# Placed at the composition layer for the same reason as azurerm_monitor_diagnostic_setting.aca:
# the diagnostic_setting needs both module.kv.kv_id AND module.monitoring.workspace_id,
# which only exist together at this layer. Folding into infra/modules/kv/ would
# require the kv module to take a workspace_id input, breaking the existing
# "monitoring module depends on nothing; kv module depends on nothing" boundary.
#
# log category 'AuditEvent' captures every secret read/write + role assignment
# change. Volume impact: trivial — ACA cold-start reads 5 secrets once per revision
# activation. LAW daily quota is 0.15 GB/day; KV audit rows are ~1 KB each; even
# with 100 reads/day the cost is approximately 0.0001% of the daily cap.

resource "azurerm_monitor_diagnostic_setting" "kv" {
  name                       = "${local.prefix}-kv-diag"
  target_resource_id         = module.kv.kv_id
  log_analytics_workspace_id = module.monitoring.workspace_id

  enabled_log {
    category = "AuditEvent"
  }
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
