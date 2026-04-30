output "kv_id" {
  description = "Key Vault resource ID — consumed by database module to write postgres-admin-password secret."
  value       = module.key_vault.resource_id
}

output "kv_uri" {
  description = "Key Vault DNS name URI (https://jobrag-prod-kv.vault.azure.net/) — consumed by Phase 4 frontend for hand-off if needed."
  value       = module.key_vault.uri
}

output "kv_name" {
  description = "Key Vault name (jobrag-prod-kv) — exposed for portal navigation + verification scripts."
  value       = module.key_vault.name
}
