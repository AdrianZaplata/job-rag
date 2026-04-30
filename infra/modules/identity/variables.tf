variable "swa_origin" {
  type        = string
  description = "Static Web App default origin (e.g. https://jobrag-prod-spa-xxxxxxxx.azurestaticapps.net). Empty string on first apply (DEPL-12 two-pass) — SPA redirect_uris filters empties via compact()."
  default     = ""
}

variable "github_owner" {
  type        = string
  description = "GitHub repo owner (org or user). Lowercased automatically in subject claims."
}

variable "github_repo" {
  type        = string
  description = "GitHub repo name. Lowercased automatically in subject claims."
}

variable "resource_group_id" {
  type        = string
  description = "Resource group resource ID for the RG-scoped Contributor role assignment per D-08 (NEVER subscription)."
}
