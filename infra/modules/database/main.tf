terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# 32-char ALPHANUMERIC password per D-11.
# Special chars cause URL-encoding pain (Phase 1 STATE.md lesson: dev DB password
# with `&%!$` broke alembic's ConfigParser ConfigInterpolation). asyncpg + psycopg2
# both URL-decode cleanly with %26 etc., but Alembic's ini parser doesn't.
resource "random_password" "pg_admin" {
  length  = 32
  special = false
  upper   = true
  lower   = true
  numeric = true
}

# Stash the password in KV BEFORE Postgres is created so the secret URI can be
# referenced by the Container App at deploy time. Strict ordering: deployer must
# already have "Key Vault Secrets Officer" on the KV — the role assignment ID is
# passed in via var.kv_admin_role_assignment_id so this resource depends_on it.
resource "azurerm_key_vault_secret" "pg_admin_password" {
  name             = "postgres-admin-password"
  value_wo         = random_password.pg_admin.result
  value_wo_version = 1
  key_vault_id     = var.key_vault_id
  content_type     = "text/plain"

  depends_on = [var.kv_admin_role_assignment_id]
}

# AVM Postgres Flex per CONTEXT.md D-03. Pinned to 0.2.2 (verified Apr 14 2026).
# A5 spike: server_configuration shape per RESEARCH.md §Pitfall — uses
# `azure.extensions` NOT `shared_preload_libraries`. If `terraform-docs markdown
# table .` against the pinned module shows a different key shape, adapt the
# module call (the value 'VECTOR' stays the same).
module "postgres" {
  source  = "Azure/avm-res-dbforpostgresql-flexibleserver/azurerm"
  version = "0.2.2"

  # Region-coded suffix dodges stale ARM name reservations from prior failed
  # applies (LocationIsOfferRestricted leaves the name reserved globally even
  # though no resource is visible via `az resource list`). Bump the suffix on
  # each new region attempt: -de (germanywestcentral), -ie (northeurope), etc.
  name                = "jobrag-${var.env}-pg-ie"
  location            = var.location
  resource_group_name = var.resource_group_name

  sku_name          = "B_Standard_B1ms"
  storage_mb        = 32768 # 32 GB — free-tier max (Discretion)
  auto_grow_enabled = true  # Discretion — fail-soft past 32 GB
  server_version    = "16"

  administrator_login    = var.admin_login # default "jobragadmin" — passed in by composition
  administrator_password = random_password.pg_admin.result

  public_network_access_enabled = true # D-10 — see README knowingly-accepted trade-off
  backup_retention_days         = 7    # Discretion — free-tier default

  high_availability = null # B1ms doesn't support HA

  # CONTEXT.md D-12 + RESEARCH.md Pitfall §azure.extensions:
  # azure.extensions is the per-server allowlist that gates `CREATE EXTENSION`.
  # Alembic migration 0001 (Phase 1) actually runs CREATE EXTENSION IF NOT EXISTS
  # vector against the jobrag database at container startup.
  # AVM 0.2.2: server_configuration entries take `name` + `config` (the value).
  # Earlier docs said `value`; the actual var schema is `config`.
  server_configuration = {
    extensions_allowlist = {
      name   = "azure.extensions"
      config = "VECTOR" # case-insensitive; uppercase matches Microsoft docs convention
    }
  }

  databases = {
    jobrag = {
      name = "jobrag" # D-12: TF creates the DB; Alembic creates the extension
    }
  }

  # CONTEXT.md A1 Path A: 0.0.0.0 "Allow Azure services" + Adrian's home IP.
  # Skip the data.azurerm_container_app_environment.static_ip approach (Consumption-
  # tier outbound IP is documented non-stable per RESEARCH.md Pitfall).
  # AVM 0.2.2 firewall_rules schema requires `name` per entry.
  firewall_rules = merge(
    {
      home = {
        name             = "home"
        start_ip_address = var.home_ip
        end_ip_address   = var.home_ip
      }
    },
    var.use_allow_azure_services ? {
      allow_azure_services = {
        name             = "AllowAzureServices"
        start_ip_address = "0.0.0.0"
        end_ip_address   = "0.0.0.0"
      }
    } : {}
  )

  tags = var.tags
}
