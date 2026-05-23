terraform {
  required_version = ">= 1.9"
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # NO backend block — local state per D-02. Adrian's local az-login is the
  # sole apply path; workforce GHA SP can't auth into the External tenant
  # (Gap D). State lives in infra/external/terraform.tfstate (gitignored).
}

# ─── API app registration (resource the SPA acquires tokens AGAINST) ───
resource "random_uuid" "access_as_user_scope_id" {}

# Phase 04.1-06 split — azuread_application.api was rejected by the
# resource-graph layer because identifier_uris = ["api://${self.client_id}"]
# is a self-reference (terraform validate passes but terraform plan aborts
# with Error: Self-referential block). The provider has no inline workaround
# for the api://<self.client_id> case. Per provider docs + schema introspection
# (azuread = 3.8.0, Task 01 step 1 verified): azuread_application_registration
# is the decomposable lightweight base, and requested_access_token_version IS
# a direct top-level attribute on it (NOT a nested block). Sibling resources
# (azuread_application_identifier_uri, azuread_application_permission_scope)
# carry the per-feature axes. See
# .planning/debug/external-identifier-uris-self-ref.md for the full diagnosis.
resource "azuread_application_registration" "api" {
  provider                       = azuread.external
  display_name                   = "jobrag-api-${var.environment}"
  sign_in_audience               = "AzureADMyOrg"
  requested_access_token_version = 2 # LOAD-BEARING — CIAM rejects v1 tokens (main.tf:60-62).
  # Direct attribute on the registration in v3.8.0
  # (NOT on azuread_application_api_access — that
  # resource is for OUTBOUND scope grants, not the
  # app's own token version).
}

# Application ID URI as a side resource — references registration's client_id
# (cross-resource reference, NOT self-reference; plans cleanly). Silent-fail
# risk on this resource (state says Created while live identifierUris stays
# empty) is mitigated by the `az ad app show --query identifierUris` assertion
# in scripts/refresh-external-outputs.sh (added 04.1-06). Memory file
# terraform-azuread-identifier-uri-unreliable.md superseded 04.1-06.
resource "azuread_application_identifier_uri" "api" {
  provider       = azuread.external
  application_id = azuread_application_registration.api.id
  identifier_uri = "api://${azuread_application_registration.api.client_id}"
}

# OAuth2 scope — was the `oauth2_permission_scope { … }` nested block inside
# the old `api { … }` block on azuread_application.api. Carries the
# access_as_user scope the SPA acquires tokens against.
# NOTE: azuread_application_api_access is intentionally NOT used here. That
# resource is for an app declaring its OUTBOUND access to ANOTHER api's
# scopes (the equivalent of the SPA's required_resource_access block on
# this file) — it is the wrong abstraction for declaring the API's own scopes,
# and the v3.8.0 schema makes api_client_id required on it (verified via
# `terraform providers schema -json` in Task 01 step 1).
resource "azuread_application_permission_scope" "access_as_user" {
  provider                   = azuread.external
  application_id             = azuread_application_registration.api.id
  scope_id                   = random_uuid.access_as_user_scope_id.result
  value                      = "access_as_user"
  type                       = "User"
  admin_consent_description  = "Allow the SPA to call the job-rag API on behalf of the signed-in user."
  admin_consent_display_name = "Access job-rag API"
  user_consent_description   = "Allow the SPA to call the job-rag API on your behalf."
  user_consent_display_name  = "Access job-rag API"
}

resource "azuread_service_principal" "api" {
  provider  = azuread.external
  client_id = azuread_application_registration.api.client_id # REPOINTED from azuread_application.api.client_id (Phase 04.1-06)
}

# ─── SPA app registration (PKCE auth code flow per AUTH-02 / Pitfall 2) ───
resource "azuread_application" "spa" {
  provider         = azuread.external
  display_name     = "jobrag-spa-${var.environment}"
  sign_in_audience = "AzureADMyOrg"

  # External (CIAM) tenants reject v1 tokens — AccessTokenAcceptedVersion
  # may not be 1 or null. Default on azuread_application is 1, so set
  # explicitly on the SPA too (the API app's equivalent is set as the
  # top-level requested_access_token_version attribute on
  # azuread_application_registration.api above).
  api {
    requested_access_token_version = 2
  }

  single_page_application {
    # Pitfall 2: MUST be single_page_application, NOT `web`. Wrong type =
    # AADSTS9002326 "Cross-origin token redemption is permitted only for
    # the 'Single-Page Application' client-type."
    redirect_uris = var.spa_redirect_uris
  }

  required_resource_access {
    resource_app_id = azuread_application_registration.api.client_id # REPOINTED from azuread_application.api.client_id (Phase 04.1-06)

    resource_access {
      id   = random_uuid.access_as_user_scope_id.result
      type = "Scope"
    }
  }
}

resource "azuread_service_principal" "spa" {
  provider  = azuread.external
  client_id = azuread_application.spa.client_id
}

# ─── Admin consent on the SPA's delegated permission ───
resource "azuread_service_principal_delegated_permission_grant" "spa_to_api" {
  provider                             = azuread.external
  service_principal_object_id          = azuread_service_principal.spa.object_id
  resource_service_principal_object_id = azuread_service_principal.api.object_id
  # Phase 04.1-06 Issue 6 hardening — was `["access_as_user"]` literal string;
  # now an explicit cross-resource reference to the scope value. Adds zero risk
  # and makes the dependency explicit so a future rename of the scope value
  # can't silently break the grant.
  claim_values = [azuread_application_permission_scope.access_as_user.value]
}
