output "spa_app_client_id" {
  description = "SPA app registration client ID — Phase 4 MSAL config consumes this."
  value       = azuread_application.spa.client_id
}

output "api_app_client_id" {
  description = "API app registration client ID — Phase 4 MSAL config consumes this for the access_as_user scope."
  value       = azuread_application.api.client_id
}

output "api_app_identifier_uri" {
  description = "API identifier URI (api://jobrag-api). Phase 4 fastapi-azure-auth consumes this as the audience."
  value       = "api://jobrag-api"
}

output "gha_client_id" {
  description = "GitHub Actions service principal client ID. Set as GH secret AZURE_CLIENT_ID. Used by azure/login@v2 in all three deploy workflows."
  value       = azuread_application.github_actions.client_id
}

output "gha_object_id" {
  description = "GHA SP object ID — for portal navigation / role assignment debugging."
  value       = azuread_service_principal.github_actions.object_id
}

output "access_as_user_scope_id" {
  description = "UUID of the access_as_user OAuth2 scope on the API. Stable across applies (random_uuid resource preserves)."
  value       = random_uuid.access_as_user_scope.result
}
