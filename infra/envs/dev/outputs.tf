# Dev outputs — identical names + shape to prod (values differ).
# Provides parity with the B2 manual SWA-token-sync runbook should dev ever apply.

output "swa_default_origin" {
  description = "SWA default host name (without https://). scripts/refresh-swa-origin.sh reads this."
  value       = azurerm_static_web_app.spa.default_host_name
}

output "aca_fqdn" {
  description = "Container App stable env FQDN — Phase 4 frontend axios baseURL (per W5)."
  value       = module.compute.aca_fqdn
}

output "kv_name" {
  description = "Key Vault name (jobrag-dev-kv)."
  value       = module.kv.kv_name
}

output "kv_uri" {
  description = "Key Vault DNS URI (https://jobrag-dev-kv.vault.azure.net/)."
  value       = module.kv.kv_uri
}

output "tenant_subdomain" {
  description = "External tenant subdomain (jobrag) — same tenant as prod per D-06."
  value       = var.tenant_subdomain
}

output "tenant_id" {
  description = "External tenant GUID — same as prod per D-06."
  value       = var.tenant_id_external
}

# spa_app_client_id and api_app_client_id outputs removed (Gap D, 2026-05-12).
# Mirrors prod: External-tenant app registrations moved to a local-only ops
# surface. See infra/modules/identity/main.tf header block.

output "gha_client_id" {
  description = "GitHub Actions SP client ID."
  value       = module.identity.gha_client_id
}

# B2 parity — same shape as prod for runbook readability when dev applies.
output "swa_deployment_token" {
  description = "SWA api_key — sync MANUALLY to AZURE_STATIC_WEB_APPS_API_TOKEN_DEV via runbook."
  value       = azurerm_static_web_app.spa.api_key
  sensitive   = true
}

output "swa_api_key" {
  description = "Alias of swa_deployment_token — used by manual `terraform output -raw swa_api_key | gh secret set ...`."
  value       = azurerm_static_web_app.spa.api_key
  sensitive   = true
}

output "seeded_user_entra_oid_secret_name" {
  description = "KV secret name for the placeholder seeded oid."
  value       = "seeded-user-entra-oid"
}
