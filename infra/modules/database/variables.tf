variable "env" {
  type        = string
  description = "Environment (prod | dev)."
  validation {
    condition     = contains(["prod", "dev"], var.env)
    error_message = "env must be 'prod' or 'dev'."
  }
}

variable "location" {
  type        = string
  description = "Azure region for the Postgres server (e.g. 'westeurope')."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group where Postgres + KV secret are created."
}

variable "admin_login" {
  type        = string
  description = "Postgres admin login name. Default: jobragadmin."
  default     = "jobragadmin"
}

variable "key_vault_id" {
  type        = string
  description = "Resource ID of the Key Vault that stores the postgres-admin-password secret. From kv module output."
}

variable "kv_admin_role_assignment_id" {
  type        = string
  description = "Resource ID of the role_assignment that grants the deployer 'Key Vault Secrets Officer' on the KV. azurerm_key_vault_secret.pg_admin_password depends on this — RBAC propagation can race."
}

variable "home_ip" {
  type        = string
  description = "Adrian's home IP for psql access (CIDR notation: just the IP, no mask). Refresh runbook documented in infra/envs/prod/README.md."
}

variable "use_allow_azure_services" {
  type        = bool
  description = "When true, adds the 0.0.0.0 'Allow Azure services' firewall rule (CONTEXT.md A1 Path A). Set true for prod (ACA can reach Postgres); set false for dev scaffold."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to Postgres."
  default     = {}
}
