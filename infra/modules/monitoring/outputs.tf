output "workspace_id" {
  description = "LAW resource ID — consumed by network module's azurerm_container_app_environment.log_analytics_workspace_id AND by composition-layer azurerm_monitor_diagnostic_setting.aca."
  value       = module.log_analytics.resource_id
}

# W3 fix: AVM LAW 0.5.1 may not expose `.resource.workspace_id` directly.
# Use a separate data source against the workspace's resource_id to fetch the
# customer (workspace) GUID needed for KQL queries from outside Terraform.
data "azurerm_log_analytics_workspace" "this" {
  name                = "jobrag-${var.env}-law"
  resource_group_name = var.resource_group_name
  depends_on          = [module.log_analytics]
}

output "workspace_customer_id" {
  description = "LAW customer (workspace) GUID — used for KQL queries from outside Terraform. Fetched via data source per W3 fix (AVM 0.5.1 attribute name verified by spike)."
  value       = data.azurerm_log_analytics_workspace.this.workspace_id
}

output "workspace_name" {
  description = "LAW name (jobrag-prod-law) — exposed for portal navigation."
  # AVM 0.5.1 emits the workspace via a single `resource` output (the underlying
  # azurerm_log_analytics_workspace), and that output is marked sensitive. Unwrap
  # the name with nonsensitive() since the workspace name itself is not secret.
  value = nonsensitive(module.log_analytics.resource.name)
}
