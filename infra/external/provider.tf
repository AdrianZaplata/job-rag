# Sole provider: azuread aliased to the External (CIAM) tenant.
# NO azurerm — this directory manages NO Azure resources (Gap D constraint).
provider "azuread" {
  alias     = "external"
  tenant_id = var.tenant_id_external
}

# Required default azuread provider — unaliased default needed even when
# only the alias is used (Terraform provider plumbing).
provider "azuread" {
  tenant_id = var.tenant_id_external
}
