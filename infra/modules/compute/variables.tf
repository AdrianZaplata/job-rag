variable "env" {
  type        = string
  description = "Environment (prod | dev)."
  validation {
    condition     = contains(["prod", "dev"], var.env)
    error_message = "env must be 'prod' or 'dev'."
  }
}

variable "resource_group_name" {
  type        = string
  description = "Resource group where the Container App is created."
}

variable "aca_env_id" {
  type        = string
  description = "Container App Environment ID — from network module's env_id output."
}

variable "ghcr_username" {
  type        = string
  description = "GitHub username/org for GHCR pulls — e.g. 'adrianzaplata'. Lowercase."
}

variable "ghcr_pat" {
  type        = string
  description = "Fine-grained read-only PAT scoped to the ghcr.io/<owner>/job-rag package. Stored in TF state (sensitive=true) per RESEARCH.md Pitfall §ghcr-pat — chicken-and-egg with KV."
  sensitive   = true
}

variable "image_tag" {
  type        = string
  description = "Image tag to deploy. Default: 'latest'. deploy-api.yml updates to $${{ github.sha }} on each push."
  default     = "latest"
}

variable "kv_secret_uris" {
  type        = map(string)
  description = "Map of secret name → versionless KV secret URI. Required keys: openai-api-key, postgres-admin-password, langfuse-public-key, langfuse-secret-key, seeded-user-entra-oid. Composition layer builds this map."
  validation {
    condition = alltrue([
      contains(keys(var.kv_secret_uris), "openai-api-key"),
      contains(keys(var.kv_secret_uris), "postgres-admin-password"),
      contains(keys(var.kv_secret_uris), "langfuse-public-key"),
      contains(keys(var.kv_secret_uris), "langfuse-secret-key"),
      contains(keys(var.kv_secret_uris), "seeded-user-entra-oid"),
    ])
    error_message = "kv_secret_uris must have all 5 keys: openai-api-key, postgres-admin-password, langfuse-public-key, langfuse-secret-key, seeded-user-entra-oid."
  }
}

variable "postgres_fqdn" {
  type        = string
  description = "Postgres FQDN from database module's fqdn output. Wired into POSTGRES_HOST env var."
}

variable "postgres_admin_login" {
  type        = string
  description = "Postgres admin login from database module's admin_login output."
}

variable "allowed_origins" {
  type        = string
  description = "CSV of allowed CORS origins. First apply: 'http://localhost:5173'. Second apply (after refresh-swa-origin.sh): 'https://<swa-default-host>,http://localhost:5173'. Consumed by FastAPI CORSMiddleware (Phase 1 D-26)."
}

variable "seeded_user_id" {
  type        = string
  description = "Adrian's UUID for SEEDED_USER_ID env var per Phase 1 D-08. Phase 4 swaps this for the JWT-injected oid."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the Container App."
  default     = {}
}

# ─── Phase 4 D-04 — auth-related env vars (plain ACA env) ─────────────────────
# All three are public-by-design (visible in JWT iss/aud claims) per Phase 3 D-13
# KV-vs-plain-env distinction. The fourth (SEEDED_USER_ENTRA_OID) is NOT a module
# variable — it's already wired via kv_secret_uris["seeded-user-entra-oid"] (Phase
# 3 D-09 placeholder slot, Phase 4 D-04 surfaces it via secretRef env entry).

variable "backend_audience" {
  type        = string
  description = "Phase 4 D-04 — JWT aud claim value (api://{api_client_id}). Wired as BACKEND_AUDIENCE plain env on ACA container. Public-by-design per Phase 3 D-13."
  default     = ""
}

variable "entra_tenant_id" {
  type        = string
  description = "Phase 4 D-04 — Entra External ID (CIAM) tenant GUID. Wired as ENTRA_TENANT_ID plain env. Public-by-design."
  default     = ""
}

variable "entra_tenant_subdomain" {
  type        = string
  description = "Phase 4 D-04 — Entra External ID subdomain (e.g. 'jobrag' for jobrag.ciamlogin.com). Wired as ENTRA_TENANT_SUBDOMAIN plain env. Public-by-design."
  default     = ""
}
