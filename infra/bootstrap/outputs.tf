output "storage_account_name" {
  description = "Copy this value into infra/envs/{prod,dev}/backend.tf as the storage_account_name literal."
  value       = azurerm_storage_account.tfstate.name
}

output "container_name" {
  description = "Copy this value into infra/envs/{prod,dev}/backend.tf as the container_name literal."
  value       = azurerm_storage_container.tfstate.name
}

output "resource_group_name" {
  description = "Copy this value into infra/envs/{prod,dev}/backend.tf as the resource_group_name literal."
  value       = azurerm_resource_group.tfstate.name
}

output "tfstate_container_resource_manager_id" {
  description = "ARM resource ID of the tfstate container — passed to prod env for granting the GHA SP the Storage Blob Data Contributor role."
  value       = azurerm_storage_container.tfstate.resource_manager_id
}

output "tenant_id_external" {
  description = "External tenant GUID — referenced by infra/envs/prod/prod.tfvars as var.tenant_id_external."
  value       = var.tenant_id_external
}

output "tenant_subdomain" {
  description = "External tenant subdomain — Phase 4 builds the MSAL authority URL https://<tenant_subdomain>.ciamlogin.com/<tenant_id>/v2.0."
  value       = var.tenant_subdomain
}

output "external_tenant_object_id" {
  description = "Object ID of the External tenant (from the aliased azuread.external provider)."
  value       = data.azuread_client_config.external.tenant_id
}
