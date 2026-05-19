# Dev composition — SCAFFOLD ONLY (CONTEXT.md D-04). Never applied in v1.
# Mirrors infra/envs/prod/main.tf with three meaningful diffs:
#   1) env = "dev" everywhere
#   2) module.monitoring.create_budget = false (single subscription budget owned by prod)
#   3) module.database.use_allow_azure_services = false (dev never applies; flag intent only)
# Plus: KV purge_protection picked up from module's `var.env != "prod"` default → false.

# ─── Resource group ───────────────────────────────────────────────────────────

resource "azurerm_resource_group" "dev" {
  name     = "${local.prefix}-rg"
  location = var.location
  tags     = local.tags
}

data "azurerm_client_config" "current" {}

# Gap A / Gap D parity with prod: subscription resource ID (full
# /subscriptions/<guid> form) needed for the GHA SP Cost Management Contributor
# scope wired through module.identity. Mirrors prod; required input now that
# the identity module declares var.subscription_id.
data "azurerm_subscription" "current" {}

# ─── Identity (Workforce GHA SP + role assignments) ────────────────────────────
# External-tenant SPA + API app registrations are now managed locally only
# (Gap D, 2026-05-12). The identity module no longer takes the azuread.external
# provider alias; only azuread.workforce remains.

module "identity" {
  source = "../../modules/identity"

  providers = {
    azuread.workforce = azuread.workforce
  }

  swa_origin        = var.swa_origin
  github_owner      = var.github_owner
  github_repo       = var.github_repo
  resource_group_id = azurerm_resource_group.dev.id
  kv_id             = module.kv.kv_id                      # parity with prod (Gap 8.B)
  subscription_id   = data.azurerm_subscription.current.id # parity with prod (Gap 8.D)
}

# ─── Monitoring (LAW workspace; NO budget — owned by prod) ────────────────────

module "monitoring" {
  source = "../../modules/monitoring"

  env                 = "dev"
  location            = var.location
  resource_group_name = azurerm_resource_group.dev.name
  create_budget       = false # single subscription budget lives in prod
  budget_alert_email  = var.budget_alert_email
  tags                = local.tags
}

# ─── Network (ACA Container App Environment) ──────────────────────────────────

module "network" {
  source = "../../modules/network"

  env                        = "dev"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.dev.name
  log_analytics_workspace_id = module.monitoring.workspace_id
  tags                       = local.tags
}

# ─── KV (Key Vault) ───────────────────────────────────────────────────────────
# purge_protection_enabled defaults to (var.env != "prod" ? false : true) inside the
# module → false here, easier teardown when dev DOES eventually apply.

module "kv" {
  source = "../../modules/kv"

  env                 = "dev"
  location            = var.location
  resource_group_name = azurerm_resource_group.dev.name
  tenant_id_workforce = data.azurerm_client_config.current.tenant_id
  aca_principal_id    = null # wired separately AFTER compute creates the MI
  tags                = local.tags
}

resource "azurerm_role_assignment" "deployer_kv_secrets_officer" {
  scope                = module.kv.kv_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ─── Database (Postgres Flex + random_password + KV secret) ────────────────────

module "database" {
  source = "../../modules/database"

  env                         = "dev"
  location                    = var.location
  resource_group_name         = azurerm_resource_group.dev.name
  key_vault_id                = module.kv.kv_id
  kv_admin_role_assignment_id = azurerm_role_assignment.deployer_kv_secrets_officer.id
  home_ip                     = var.home_ip
  use_allow_azure_services    = false # dev never applies; firewall rule wouldn't matter
  tags                        = local.tags
}

# ─── Application secrets in KV ────────────────────────────────────────────────
# Out-of-band seeding (Option B) — see prod/main.tf for rationale. Same pattern
# applied to dev for parity even though dev is scaffold-only (D-04).

resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  value        = "managed-out-of-band"
  key_vault_id = module.kv.kv_id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets_officer]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "langfuse_public_key" {
  name         = "langfuse-public-key"
  value        = "managed-out-of-band"
  key_vault_id = module.kv.kv_id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets_officer]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "langfuse_secret_key" {
  name         = "langfuse-secret-key"
  value        = "managed-out-of-band"
  key_vault_id = module.kv.kv_id
  content_type = "text/plain"
  depends_on   = [azurerm_role_assignment.deployer_kv_secrets_officer]

  lifecycle {
    ignore_changes = [value]
  }
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

  env                  = "dev"
  resource_group_name  = azurerm_resource_group.dev.name
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

# ─── Monitoring diagnostic setting (W7: composition layer, NOT in module) ─────
# Mirrors prod for parity even though dev never applies. D-16: console logs only.

resource "azurerm_monitor_diagnostic_setting" "aca" {
  name                       = "${local.prefix}-aca-diag"
  target_resource_id         = module.compute.aca_id
  log_analytics_workspace_id = module.monitoring.workspace_id

  enabled_log {
    category = "ContainerAppConsoleLogs" # drop _CL suffix; that suffix is the LAW table name, not the category
  }
  # NOTE: ContainerAppSystemLogs intentionally omitted per D-16.
}

# ─── Static Web App (raw — D-03 single-resource, no AVM) ──────────────────────

resource "azurerm_static_web_app" "spa" {
  name                = "${local.prefix}-spa"
  resource_group_name = azurerm_resource_group.dev.name
  location            = var.location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}
