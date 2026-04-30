output "env_id" {
  description = "Container App Environment resource ID — consumed by the compute module's azurerm_container_app.container_app_environment_id."
  value       = azurerm_container_app_environment.main.id
}

output "env_default_domain" {
  description = "Default domain (e.g. 'jobrag-prod-aca-env.greenmushroom-abc1234d.westeurope.azurecontainerapps.io') — Container App FQDNs are subdomains of this."
  value       = azurerm_container_app_environment.main.default_domain
}

output "env_static_ip_address" {
  description = "ACA env outbound IP at apply time. Per CONTEXT.md A1 this value is NOT used for Postgres firewalling (Consumption-tier IP is documented non-stable); kept for portal/debug visibility only."
  value       = azurerm_container_app_environment.main.static_ip_address
}
