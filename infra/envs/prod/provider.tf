terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
    azuread = {
      source                = "hashicorp/azuread"
      version               = "~> 3.0"
      configuration_aliases = [azuread.workforce]
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

# Workforce tenant (subscription home) per A4. Auth chain (Gap 8.C):
#   CI:    use_oidc=true via TF_VAR_use_oidc_auth=true; client_id + tenant_id
#          from CI env vars. ARM_OIDC_TOKEN populated by azure/login@v2
#          (id-token: write permission).
#   Local: use_oidc=false (default); use_cli=true picks up Adrian's `az login`.
# Used for the GHA service principal + RG-scoped role assignment.
provider "azuread" {
  alias     = "workforce"
  use_cli   = !var.use_oidc_auth
  use_oidc  = var.use_oidc_auth
  client_id = var.gha_client_id # ignored when use_oidc=false
  tenant_id = var.tenant_id_workforce != "" ? var.tenant_id_workforce : null
}

# External-tenant `azuread.external` provider removed (Gap D, 2026-05-12).
# The SPA + API app registrations have moved to a local-only ops surface; CI
# (Workforce GHA SP) cannot authenticate into the External tenant. See
# infra/modules/identity/main.tf header block for the architectural rationale.
