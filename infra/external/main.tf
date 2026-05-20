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

resource "azuread_application" "api" {
  provider         = azuread.external
  display_name     = "jobrag-api-${var.environment}"
  sign_in_audience = "AzureADMyOrg"

  api {
    requested_access_token_version = 2
    oauth2_permission_scope {
      admin_consent_description  = "Allow the SPA to call the job-rag API on behalf of the signed-in user."
      admin_consent_display_name = "Access job-rag API"
      enabled                    = true
      id                         = random_uuid.access_as_user_scope_id.result
      type                       = "User"
      user_consent_description   = "Allow the SPA to call the job-rag API on your behalf."
      user_consent_display_name  = "Access job-rag API"
      value                      = "access_as_user"
    }
  }
}

# Application ID URI must be set AFTER application exists (chicken-and-egg
# avoidance — client_id only exists post-create). Per RESEARCH line 1950-1952.
resource "azuread_application_identifier_uri" "api" {
  provider       = azuread.external
  application_id = azuread_application.api.id
  identifier_uri = "api://${azuread_application.api.client_id}"
}

resource "azuread_service_principal" "api" {
  provider  = azuread.external
  client_id = azuread_application.api.client_id
}

# ─── SPA app registration (PKCE auth code flow per AUTH-02 / Pitfall 2) ───
resource "azuread_application" "spa" {
  provider         = azuread.external
  display_name     = "jobrag-spa-${var.environment}"
  sign_in_audience = "AzureADMyOrg"

  single_page_application {
    # Pitfall 2: MUST be single_page_application, NOT `web`. Wrong type =
    # AADSTS9002326 "Cross-origin token redemption is permitted only for
    # the 'Single-Page Application' client-type."
    redirect_uris = var.spa_redirect_uris
  }

  required_resource_access {
    resource_app_id = azuread_application.api.client_id

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
  claim_values                         = ["access_as_user"]
}
