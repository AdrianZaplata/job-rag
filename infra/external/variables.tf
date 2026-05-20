variable "tenant_id_external" {
  type        = string
  description = "Entra External ID tenant GUID (CIAM, *.ciamlogin.com). NOT the workforce tenant. Source: Phase 3 D-05 manual bootstrap or infra/bootstrap/outputs.tf tenant_id_external output."
}

variable "environment" {
  type        = string
  description = "Environment slug — 'prod' or 'dev'. Used in app-reg display names."
  default     = "prod"
}

variable "spa_redirect_uris" {
  type        = list(string)
  description = "SPA redirect URIs for both dev (http://localhost:5173/) and prod (SWA origin). Multi-redirect per Phase 3 D-06."
  default     = ["http://localhost:5173/"]
}

variable "logout_redirect_uri" {
  type        = string
  description = "Post-logout redirect URI (D-12). Typically the SWA origin. Empty = no special logout target registered."
  default     = ""
}
