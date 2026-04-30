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
