output "spa_client_id" {
  description = "SPA app registration client ID. Paste into frontend/.env.production VITE_SPA_CLIENT_ID and GitHub repo secret VITE_SPA_CLIENT_ID. Public-by-design (appears in JWT aud claim that any holder can read)."
  value       = azuread_application.spa.client_id
}

output "api_client_id" {
  description = "API app registration client ID. Paste into infra/envs/prod/prod.tfvars.local as api_audience (raw client_id form). Public-by-design."
  value       = azuread_application.api.client_id
}

output "api_audience_uri" {
  description = "API application ID URI in api://{client_id} form. Paste into frontend/.env.production VITE_API_AUDIENCE and infra/envs/prod/prod.tfvars.local backend_audience. This is the literal JWT aud claim value the backend rejects on mismatch."
  value       = azuread_application_identifier_uri.api.identifier_uri
}

output "api_scope_name" {
  description = "Full scope identifier (api://{client_id}/access_as_user). Pass to MSAL.acquireTokenSilent scopes array. Used as API_SCOPE constant in frontend/src/auth/scopes.ts."
  value       = "${azuread_application_identifier_uri.api.identifier_uri}/access_as_user"
}
