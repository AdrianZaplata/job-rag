terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
  }
}

# AVM Key Vault module per CONTEXT.md D-03.
# Pinned to 0.10.2 (verified Oct 14 2025; bundles RBAC + role_assignments + secrets baseline).
#
# legacy_access_policies_enabled = false from first apply per RESEARCH.md Pitfall
# (flipping later removes existing policies' effect; set correctly the first time).
module "key_vault" {
  source  = "Azure/avm-res-keyvault-vault/azurerm"
  version = "0.10.2"

  name                = "jobrag-${var.env}-kv"
  location            = var.location
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id_workforce # workforce tenant per A4 — KV lives next to the subscription

  sku_name                       = "standard"
  legacy_access_policies_enabled = false # RBAC only per D-13
  purge_protection_enabled       = var.env == "prod" ? true : false
  soft_delete_retention_days     = 7
  public_network_access_enabled  = true # ACA Consumption can't reach private endpoints

  # ACA system-assigned MI gets "Key Vault Secrets User" — read-only for secret values.
  # In the standard composition (envs/prod/main.tf), this role is assigned at
  # composition layer AFTER compute creates the MI (resource
  # `azurerm_role_assignment.aca_kv_secrets_user`), so var.aca_principal_id is
  # null and we skip the inline assignment here. Inline assignment is preserved
  # for callers that already have a principal_id at module-call time.
  role_assignments = var.aca_principal_id == null ? {} : {
    aca_system_mi = {
      role_definition_id_or_name = "Key Vault Secrets User"
      principal_id               = var.aca_principal_id
    }
  }

  tags = var.tags
}
