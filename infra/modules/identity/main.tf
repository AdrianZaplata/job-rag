terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.69"
    }
    azuread = {
      source                = "hashicorp/azuread"
      version               = "~> 3.0"
      configuration_aliases = [azuread.external, azuread.workforce]
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# A consistent UUID for the API's access_as_user scope (id stays the same across
# applies — generated once, hardcoded). Per RESEARCH.md line 1100.
resource "random_uuid" "access_as_user_scope" {}

# ─── External tenant: SPA + API app registrations (D-05, D-06, D-07) ───────────

resource "azuread_application" "api" {
  provider = azuread.external

  display_name    = "jobrag-api"
  identifier_uris = ["api://jobrag-api"]

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = random_uuid.access_as_user_scope.result
      admin_consent_description  = "Allow the SPA to act on behalf of the signed-in user."
      admin_consent_display_name = "Access job-rag API as user"
      enabled                    = true
      type                       = "User"
      user_consent_description   = "Allow the SPA to access job-rag on your behalf."
      user_consent_display_name  = "Access job-rag API"
      value                      = "access_as_user"
    }
  }
}

resource "azuread_service_principal" "api" {
  provider  = azuread.external
  client_id = azuread_application.api.client_id
}

resource "azuread_application" "spa" {
  provider = azuread.external

  display_name = "jobrag-spa"

  # External tenant rejects v1 access tokens — the application object must
  # declare requested_access_token_version = 2. azuread provider's default is
  # null which the API rejects with InvalidAccessTokenVersion.
  api {
    requested_access_token_version = 2
  }

  # B1 fix: compact() drops null AND empty-string entries. The original
  # ternary produced `null` which Terraform rejects when constructing the
  # list (lists cannot contain null). Use empty-string + compact() instead.
  single_page_application {
    redirect_uris = compact([
      var.swa_origin == "" ? "" : "${var.swa_origin}/",
      "http://localhost:5173/", # local dev per D-06
    ])
  }

  required_resource_access {
    resource_app_id = azuread_application.api.client_id

    resource_access {
      id   = random_uuid.access_as_user_scope.result
      type = "Scope"
    }
  }
}

resource "azuread_service_principal" "spa" {
  provider  = azuread.external
  client_id = azuread_application.spa.client_id
}

# ─── Workforce tenant: GitHub Actions service principal (A4) ───────────────────

resource "azuread_application" "github_actions" {
  provider     = azuread.workforce
  display_name = "jobrag-gha"
}

resource "azuread_service_principal" "github_actions" {
  provider  = azuread.workforce
  client_id = azuread_application.github_actions.client_id
}

# Federated credential #1: master push (deploy-api.yml + deploy-spa.yml).
# Subject MUST match GitHub's actual case (Microsoft tightened case-sensitivity
# in Aug 2024 — AADSTS7002138 is thrown if the registered subject differs from
# the presented assertion in case). Pass var.github_owner / var.github_repo
# in the exact case as they appear on GitHub. Earlier guidance to `lower()`
# everything is obsolete and now actively breaks the OIDC handshake.
resource "azuread_application_federated_identity_credential" "master" {
  provider = azuread.workforce

  application_id = azuread_application.github_actions.id
  display_name   = "gha-master-push"
  description    = "GHA OIDC for master push (deploy-api.yml, deploy-spa.yml uses long-lived SWA token)"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_owner}/${var.github_repo}:ref:refs/heads/master"
  audiences      = ["api://AzureADTokenExchange"]
}

# Federated credential #2: environment:production (deploy-infra.yml).
# Gates infra apply behind GH protected environment with Adrian as required reviewer.
resource "azuread_application_federated_identity_credential" "production_env" {
  provider = azuread.workforce

  application_id = azuread_application.github_actions.id
  display_name   = "gha-environment-production"
  description    = "GHA OIDC for environment:production (deploy-infra.yml)"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_owner}/${var.github_repo}:environment:production"
  audiences      = ["api://AzureADTokenExchange"]
}

# RG-scoped Contributor — never subscription per CONTEXT.md D-08.
resource "azurerm_role_assignment" "gha_rg_contributor" {
  scope                = var.resource_group_id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}

# Gap 8.B fix: GHA SP needs KV data-plane access to manage azurerm_key_vault_secret
# resources from CI. KV is in RBAC mode (enable_rbac_authorization = true per
# CONTEXT.md / D-13 Claude's-Discretion clause); RG Contributor does not cover the
# data plane. Scope is the KV resource itself, the narrowest data-plane role
# possible. D-08 preserved (KV-scoped, not subscription, not RG-wide).
resource "azurerm_role_assignment" "gha_kv_secrets_officer" {
  scope                = var.kv_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = azuread_service_principal.github_actions.object_id
  description          = "Grants GitHub Actions federated SP read/write on KV secrets (deploy-infra.yml manages azurerm_key_vault_secret resources, Gap 8.B)."
}

# Gap 8.D fix + named D-08 exception (see CONTEXT.md D-08 Amendment 2026-05-12):
# azurerm_consumption_budget_subscription.prod (monitoring module) is
# subscription-scoped; RG Contributor doesn't cover it. Cost Management
# Contributor at subscription scope CANNOT mutate workloads (only operates on
# Microsoft.Consumption/* and Microsoft.CostManagement/* providers), so this is
# the narrowest widening that resolves the architectural conflict. Documented
# exception.
resource "azurerm_role_assignment" "gha_cost_management_contributor" {
  scope                = var.subscription_id
  role_definition_name = "Cost Management Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
  description          = "Named exception to D-08: required so deploy-infra.yml can manage the EUR 10/mo subscription-scoped consumption budget (DEPL-11). Cost Mgmt roles cannot mutate workloads."
}
