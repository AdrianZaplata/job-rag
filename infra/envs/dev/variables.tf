# Dev variables — identical shape to prod (values differ via dev.tfvars).
# Kept in sync verbatim so the module call signatures stay symmetric.

variable "location" {
  type        = string
  description = "Azure region for dev resources."
  default     = "westeurope"
}

variable "tenant_id_external" {
  type        = string
  description = "External tenant GUID — same External tenant as prod per D-06 (one tenant, multiple redirect URIs)."
}

variable "tenant_subdomain" {
  type        = string
  description = "External tenant subdomain (e.g. 'jobrag' for jobrag.ciamlogin.com)."
  default     = "jobrag"
}

variable "github_owner" {
  type        = string
  description = "GitHub repo owner — e.g. 'adrianzaplata'."
}

variable "github_repo" {
  type        = string
  description = "GitHub repo name — e.g. 'job-rag'."
  default     = "job-rag"
}

variable "swa_origin" {
  type        = string
  description = "SWA default origin. Empty on first apply; refreshed by scripts/refresh-swa-origin.sh."
  default     = ""
}

variable "home_ip" {
  type        = string
  description = "Adrian's home IP for psql access. Placeholder in dev (D-04 — never applied)."
}

variable "ghcr_username" {
  type        = string
  description = "GHCR username/org (lowercase) — typically same as github_owner."
}

variable "ghcr_pat" {
  type        = string
  description = "Fine-grained read-only PAT scoped to ghcr.io/<owner>/job-rag package. Sensitive."
  sensitive   = true
  default     = ""
}

variable "image_tag" {
  type        = string
  description = "Image tag — defaults to 'latest'. deploy-api.yml updates to $${{ github.sha }} on apply."
  default     = "latest"
}

variable "openai_api_key" {
  type        = string
  description = "OpenAI API key — written to KV. Placeholder in dev (D-04 — never applied)."
  sensitive   = true
  default     = ""
}

variable "langfuse_public_key" {
  type        = string
  description = "Langfuse public key. Optional."
  default     = ""
  sensitive   = true
}

variable "langfuse_secret_key" {
  type        = string
  description = "Langfuse secret key. Optional."
  default     = ""
  sensitive   = true
}

variable "seeded_user_entra_oid" {
  type        = string
  description = "Adrian's Entra oid placeholder per D-09. Empty default (Phase 4 fills)."
  default     = "00000000-0000-0000-0000-000000000000"
  sensitive   = true
}

variable "seeded_user_id" {
  type        = string
  description = "Adrian's UUID per Phase 1 D-08 (SEEDED_USER_ID). Used by ACA env var until Phase 4 swap."
}

variable "budget_alert_email" {
  type        = string
  description = "Email recipient for budget alerts (unused in dev — create_budget=false, single subscription budget owned by prod)."
  default     = "adrianzaplata@gmail.com"
}
