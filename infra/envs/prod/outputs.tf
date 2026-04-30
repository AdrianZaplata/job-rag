output "swa_default_origin" {
  description = "SWA default host name (without https://). scripts/refresh-swa-origin.sh reads this for the DEPL-12 two-pass."
  value       = azurerm_static_web_app.spa.default_host_name
}

output "aca_fqdn" {
  description = "Container App stable env FQDN (per W5, via ingress[0].fqdn) — Phase 4 frontend axios baseURL."
  value       = module.compute.aca_fqdn
}

output "kv_name" {
  description = "Key Vault name (jobrag-prod-kv) — Phase 4 reference for portal navigation."
  value       = module.kv.kv_name
}

output "kv_uri" {
  description = "Key Vault DNS URI (https://jobrag-prod-kv.vault.azure.net/)."
  value       = module.kv.kv_uri
}

output "tenant_subdomain" {
  description = "External tenant subdomain (jobrag) — Phase 4 builds MSAL authority."
  value       = var.tenant_subdomain
}

output "tenant_id" {
  description = "External tenant GUID — Phase 4 MSAL authority + audience."
  value       = var.tenant_id_external
}

output "spa_app_client_id" {
  description = "SPA app reg client ID — Phase 4 MSAL clientId."
  value       = module.identity.spa_app_client_id
}

output "api_app_client_id" {
  description = "API app reg client ID — Phase 4 MSAL apiClientId."
  value       = module.identity.api_app_client_id
}

output "gha_client_id" {
  description = "GitHub Actions SP client ID — set as repo secret AZURE_CLIENT_ID."
  value       = module.identity.gha_client_id
}

# B2 (locked decision): swa_deployment_token is exposed as a sensitive output.
# Adrian copies it into AZURE_STATIC_WEB_APPS_API_TOKEN_PROD MANUALLY from his local
# terminal after first apply (see prod README "Phase-close: GitHub secrets sync").
# Aliased as `swa_api_key` for runbook readability since the manual command pipes
# `terraform output -raw swa_api_key`.
output "swa_deployment_token" {
  description = "SWA api_key — sole long-lived secret in the system (per A2/D-08). Sync MANUALLY to AZURE_STATIC_WEB_APPS_API_TOKEN_PROD via the runbook in prod README. NO automated `gh secret set` step (B2)."
  value       = azurerm_static_web_app.spa.api_key
  sensitive   = true
}

output "swa_api_key" {
  description = "Alias of swa_deployment_token — used by the manual runbook command `terraform output -raw swa_api_key | gh secret set ...` (B2 locked decision)."
  value       = azurerm_static_web_app.spa.api_key
  sensitive   = true
}

output "seeded_user_entra_oid_secret_name" {
  description = "KV secret name for the placeholder seeded oid — Phase 4 writes the real oid here after first MSAL login (D-09)."
  value       = "seeded-user-entra-oid"
}
