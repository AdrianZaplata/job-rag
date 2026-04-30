terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
    azuread = {
      source                = "hashicorp/azuread"
      version               = "~> 3.0"
      configuration_aliases = [azuread.workforce, azuread.external]
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
      # Dev KV has purge_protection_enabled=false (module default for env != "prod"),
      # so set purge_soft_delete_on_destroy = true so `terraform destroy` actually
      # removes the vault without manual portal cleanup. Mirrors the "easier teardown"
      # rationale documented in this dir's README.
      purge_soft_delete_on_destroy = true
    }
  }
}

# Default azuread provider — workforce tenant (subscription home) per A4.
provider "azuread" {
  alias = "workforce"
  # tenant_id resolved from `az login` context — defaults to subscription home tenant.
}

# External tenant alias — used for SPA + API app registrations only.
# D-06: same External tenant as prod (one tenant, multiple redirect URIs).
provider "azuread" {
  alias     = "external"
  tenant_id = var.tenant_id_external
}
