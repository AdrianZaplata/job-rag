variable "env" {
  type        = string
  description = "Environment (prod | dev). Drives jobrag-{env}-kv naming + purge_protection."
  validation {
    condition     = contains(["prod", "dev"], var.env)
    error_message = "env must be 'prod' or 'dev'."
  }
}

variable "location" {
  type        = string
  description = "Azure region for the KV (typically 'westeurope')."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group where KV is created."
}

variable "tenant_id_workforce" {
  type        = string
  description = "Workforce tenant ID (subscription's home tenant) per CONTEXT.md A4. KV's tenant_id MUST be the workforce tenant — NOT the External tenant — because KV roles + RBAC live alongside Azure RM."
}

variable "aca_principal_id" {
  type        = string
  description = "Object ID of the ACA Container App's system-assigned managed identity. Receives the 'Key Vault Secrets User' role. Must be passed in by envs/prod/main.tf AFTER the compute module creates the Container App."
  default     = null
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to KV."
  default     = {}
}
