# CONTEXT.md D-05 — the Entra External tenant cannot be Terraformed for creation.
# The tenant is manually provisioned via the Entra admin center (see README.md);
# this file only declares an aliased azuread provider scoped to that tenant so
# downstream `terraform import` calls (and any future tenant-level resources)
# resolve correctly.
#
# CONTEXT.md A4 — the default azuread provider in main.tf targets the WORKFORCE
# tenant (Adrian's subscription home tenant). The aliased "external" provider
# below targets the External tenant only.

variable "tenant_id_external" {
  type        = string
  description = "GUID of the manually-created Entra External tenant (captured from portal after D-05 step)."
}

variable "tenant_subdomain" {
  type        = string
  description = "Subdomain of the External tenant — e.g. 'jobrag' for jobrag.ciamlogin.com."
  default     = "jobrag"
}

provider "azuread" {
  alias     = "external"
  tenant_id = var.tenant_id_external
}

# Data source confirms the External tenant exists and is reachable; used as a
# `depends_on` anchor by other resources that target it.
data "azuread_client_config" "external" {
  provider = azuread.external
}
