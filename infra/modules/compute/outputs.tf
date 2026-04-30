output "aca_id" {
  description = "Container App resource ID — consumed by monitoring module's diagnostic_setting target_resource_id."
  value       = azurerm_container_app.api.id
}

# W5 fix: use ingress[0].fqdn (stable env FQDN) NOT latest_revision_fqdn (revision-specific).
# Verified against azurerm 4.69 docs: `ingress[0].fqdn` is the correct accessor on the
# `azurerm_container_app` resource for the stable hostname (the one mapped to the SWA's
# CORS allowlist). If the executor finds a different attribute name during apply (e.g.
# `ingress.0.fqdn`), use whichever stable accessor azurerm 4.69 exposes and document the
# choice in modules/compute/README.md.
output "aca_fqdn" {
  description = "Container App stable env FQDN (e.g. jobrag-prod-api.greenmushroom-abc1234d.westeurope.azurecontainerapps.io). Stable across revisions. Consumed by Phase 4 frontend MSAL config."
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "aca_principal_id" {
  description = "Object ID of the system-assigned managed identity. Consumed by kv module's role_assignments.aca_system_mi.principal_id."
  value       = azurerm_container_app.api.identity[0].principal_id
}

output "aca_name" {
  description = "Container App name (jobrag-prod-api) — used by deploy-api.yml's `az containerapp update` step."
  value       = azurerm_container_app.api.name
}
