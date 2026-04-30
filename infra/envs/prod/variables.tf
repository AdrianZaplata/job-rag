# Resource group + region
variable "location" {
  type        = string
  description = "Azure region for prod resources."
  default     = "westeurope"
}

# Identity (External tenant + workforce GitHub OIDC)
variable "tenant_id_external" {
  type        = string
  description = "External tenant GUID — captured from bootstrap output (per D-05)."
}

variable "tenant_subdomain" {
  type        = string
  description = "External tenant subdomain (e.g. 'jobrag' for jobrag.ciamlogin.com)."
  default     = "jobrag"
}

variable "github_owner" {
  type        = string
  description = "GitHub repo owner — e.g. 'adrianzaplata'. Lowercased automatically in fed-cred subjects."
}

variable "github_repo" {
  type        = string
  description = "GitHub repo name — e.g. 'job-rag'."
  default     = "job-rag"
}

# CORS DEPL-12 two-pass
variable "swa_origin" {
  type        = string
  description = "SWA default origin. Empty on first apply; refreshed by scripts/refresh-swa-origin.sh."
  default     = ""
}

# Database firewall
variable "home_ip" {
  type        = string
  description = "Adrian's home IP for psql access. Refresh runbook in infra/modules/database/README.md."
}

# GHCR registry pull
variable "ghcr_username" {
  type        = string
  description = "GHCR username/org (lowercase) — typically same as github_owner."
}

variable "ghcr_pat" {
  type        = string
  description = "Fine-grained read-only PAT scoped to ghcr.io/<owner>/job-rag package. RESEARCH.md Pitfall §ghcr-pat: lives in TF state (sensitive=true)."
  sensitive   = true
}

variable "image_tag" {
  type        = string
  description = "Image tag — defaults to 'latest'. deploy-api.yml updates to $${{ github.sha }}. Per B5, the compute module's lifecycle.ignore_changes [template[0].container[0].image] means terraform apply will NOT revert the deploy-api.yml-pinned SHA after first push."
  default     = "latest"
}

# Application secrets
variable "openai_api_key" {
  type        = string
  description = "OpenAI API key — written to KV as 'openai-api-key' secret. ACA pulls via MI."
  sensitive   = true
}

variable "langfuse_public_key" {
  type        = string
  description = "Langfuse public key. Written to KV. Optional — empty string disables Langfuse (fail-open per Phase 1)."
  default     = ""
  sensitive   = true
}

variable "langfuse_secret_key" {
  type        = string
  description = "Langfuse secret key. Written to KV."
  default     = ""
  sensitive   = true
}

variable "seeded_user_entra_oid" {
  type        = string
  description = "Adrian's Entra oid placeholder per D-09. Empty on first Phase 3 apply; Phase 4 fills after first MSAL login."
  default     = "00000000-0000-0000-0000-000000000000"
  sensitive   = true
}

variable "seeded_user_id" {
  type        = string
  description = "Adrian's UUID per Phase 1 D-08 (SEEDED_USER_ID). Used by ACA env var until Phase 4 swap."
}

variable "budget_alert_email" {
  type        = string
  description = "Email recipient for budget alerts."
  default     = "adrianzaplata@gmail.com"
}
