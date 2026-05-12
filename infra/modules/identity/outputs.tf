# External-tenant outputs (spa_app_client_id, api_app_client_id,
# api_app_identifier_uri, access_as_user_scope_id) removed (Gap D, 2026-05-12).
# The underlying resources moved to a local-only ops surface; see main.tf header
# block for the architectural rationale. Phase 4 will read these values from a
# local-state file (not yet wired) or from `az ad app show` ad-hoc.

output "gha_client_id" {
  description = "GitHub Actions service principal client ID. Set as GH secret AZURE_CLIENT_ID. Used by azure/login@v2 in all three deploy workflows."
  value       = azuread_application.github_actions.client_id
}

output "gha_object_id" {
  description = "GHA SP object ID, used for portal navigation and role-assignment debugging."
  value       = azuread_service_principal.github_actions.object_id
}
