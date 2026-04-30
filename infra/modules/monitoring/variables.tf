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
  description = "Azure region for the LAW workspace."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group where LAW is created."
}

# W7 fix: aca_id variable removed — diagnostic_setting moved to composition layer.
# The monitoring module no longer needs to know about the Container App.
# W1 fix: subscription_id variable removed; module uses data.azurerm_subscription.current
# to derive the subscription resource ID directly (auto-prefixed with /subscriptions/).

variable "create_budget" {
  type        = bool
  description = "When true, creates the subscription-scoped consumption budget. Set true ONLY in envs/prod (one budget per subscription). dev scaffold sets false."
  default     = false
}

variable "budget_alert_email" {
  type        = string
  description = "Email recipient for budget alert notifications. Default: adrianzaplata@gmail.com."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to LAW."
  default     = {}
}
