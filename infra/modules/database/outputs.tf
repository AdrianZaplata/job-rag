output "fqdn" {
  description = "Postgres server FQDN — e.g. jobrag-prod-pg.postgres.database.azure.com. Consumed by compute module's POSTGRES_HOST env var."
  value       = module.postgres.fqdn
}

output "admin_login" {
  description = "Postgres admin login (jobragadmin) — consumed by compute module's POSTGRES_USER env var."
  value       = var.admin_login
}

output "db_name" {
  description = "Database name created by Terraform (jobrag) — consumed by compute module's POSTGRES_DB env var."
  value       = "jobrag"
}

output "admin_password_secret_uri" {
  description = "Versionless KV secret URI for the postgres-admin-password — consumed by compute module's secret block (key_vault_secret_id) per D-13."
  value       = azurerm_key_vault_secret.pg_admin_password.versionless_id
}

output "admin_password_secret_name" {
  description = "Secret name in KV ('postgres-admin-password') — referenced as the secret_name in the compute module's container.env block."
  value       = azurerm_key_vault_secret.pg_admin_password.name
}
