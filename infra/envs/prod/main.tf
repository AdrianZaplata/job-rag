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
