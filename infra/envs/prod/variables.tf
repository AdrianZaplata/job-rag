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

# Application secrets — OUT-OF-BAND (Option B): openai/langfuse values live only
# in Key Vault, seeded once via `az keyvault secret set ...` (see README "Out-of-band
# secret seeding"). TF owns the secret resource shells with lifecycle.ignore_changes
# on value. No `var.openai_api_key` / `var.langfuse_*` declarations here on purpose —
# this keeps OPENAI_API_KEY out of GitHub Actions secrets entirely.

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

# Bootstrap state container — needed so this env can grant the GHA SP
# Storage Blob Data Contributor on the tfstate container, allowing
# deploy-infra.yml's federated identity to read/write remote state via AAD auth.
variable "tfstate_storage_account_name" {
  type        = string
  description = "Bootstrap storage account name (from `terraform output -raw storage_account_name` in infra/bootstrap/). Same value used in backend.tf."
}

variable "tfstate_resource_group_name" {
  type        = string
  description = "Bootstrap state RG name. Same value used in backend.tf."
  default     = "jobrag-tfstate-rg"
}

variable "tfstate_container_name" {
  type        = string
  description = "Bootstrap state container name. Same value used in backend.tf."
  default     = "tfstate"
}

# azuread provider OIDC auth (Gap 8.C). CI runner has no `az login` context for
# the workforce tenant; without explicit OIDC config the azuread provider falls
# back to Azure CLI auth and throws AADSTS700016. On local apply Adrian's
# `az login` context is used (defaults below keep CLI path live).
variable "gha_client_id" {
  type        = string
  description = "Workforce-tenant GitHub Actions service principal appId (client_id). Sourced from secrets.AZURE_CLIENT_ID via TF_VAR_gha_client_id in deploy-infra.yml. Required by azuread provider OIDC auth (Gap 8.C). Empty on local apply; the provider falls through to CLI auth when var.use_oidc_auth = false."
  default     = ""
}

variable "tenant_id_workforce" {
  type        = string
  description = "Workforce tenant ID (subscription home tenant per CONTEXT.md A4). Sourced from secrets.AZURE_TENANT_ID via TF_VAR_tenant_id_workforce in deploy-infra.yml. Defaults to empty: when empty, azuread.workforce provider resolves tenant from az login context (local apply path)."
  default     = ""
}

variable "use_oidc_auth" {
  type        = bool
  description = "Toggle azuread provider OIDC auth. true on CI runner (set via TF_VAR_use_oidc_auth in deploy-infra.yml); false on local (default) so azuread falls through to CLI auth using Adrian's az login context."
  default     = false
}

variable "deployer_object_id" {
  type        = string
  description = "AAD object ID of the human deployer who runs `terraform apply` locally (Adrian's user OID). Pinned via variable so CI plan does not try to swap principal_id to the GHA SP OID when refreshing the deployer_kv_secrets_officer role assignment (Gap H fix). The SP has its own KV access via gha_kv_secrets_officer (Gap 8.B), so this resource is exclusively for the human deployer's KV data-plane access during local apply."
}
