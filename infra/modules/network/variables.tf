variable "env" {
  type        = string
  description = "Environment name (e.g. 'prod', 'dev'). Used in resource naming jobrag-{env}-aca-env."
  validation {
    condition     = contains(["prod", "dev"], var.env)
    error_message = "env must be 'prod' or 'dev'."
  }
}

variable "location" {
  type        = string
  description = "Azure region for the Container App Environment (e.g. 'westeurope')."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group where the Container App Environment is created."
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Resource ID of the Log Analytics workspace that receives ACA diagnostic logs. Wired in envs/prod/main.tf from module.monitoring.workspace_id."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources created by this module."
  default     = {}
}
