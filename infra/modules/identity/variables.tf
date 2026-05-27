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

variable "kv_id" {
  type        = string
  description = "Key Vault resource ID (from module.kv.kv_id), scope for the GHA SP's Key Vault Secrets Officer role assignment (Gap 8.B fix). KV-scoped, not RG, preserves D-08."
}

variable "subscription_id" {
  type        = string
  description = "Subscription resource ID (NOT just the GUID, full `/subscriptions/<guid>` form). Scope for the GHA SP's Cost Management Contributor role assignment (Gap 8.D narrow exception to D-08). Sourced from data.azurerm_subscription.current.id at the composition layer."
}
