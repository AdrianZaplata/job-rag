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
      configuration_aliases = [azuread.workforce]
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# ─── External tenant resources: managed LOCALLY ONLY (Gap D, 2026-05-12) ───────
#
# The SPA + API app registrations (jobrag-spa, jobrag-api), their service
# principals, and the random_uuid for the access_as_user OAuth2 scope used to
# live here behind the azuread.external provider alias. They have been moved
# OUT of CI-managed prod state and into a local-only ops surface.
#
# Rationale: the azuread.external provider cannot authenticate as the Workforce
# GHA SP (AADSTS700016 - app not registered in External tenant 'JobRag').
# Microsoft Entra External ID guidance treats CIAM tenants as deliberately-
# isolated trust boundaries that should NOT be managed with Workforce-tenant
# credentials. CI uses the Workforce-tenant GHA SP; therefore CI cannot manage
# External-tenant resources without re-litigating the trust boundary.
#
# Going forward Adrian manages these 5 resources locally via his multi-tenant
# `az login` context (separate bootstrap surface). See
# `.planning/quick/260512-hui-fix-test-8-gap-12-a-azuread-oidc-kv-secr/260512-hui-SUMMARY.md`
# and `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` Gap D entry for the
# full architectural rationale.

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

# Gap F + G fix: SP needs Microsoft.Authorization/roleAssignments/read at sub scope
# to refresh cross-scope role assignments (gha_tfstate_blob_data_contributor lives in
# the tfstate RG; gha_cost_management_contributor is sub-scoped). Contributor at prod
# RG cascades only within that RG, so refresh would 403 on these.
#
# Reader is "*/read" only - pure information disclosure, no mutation capability.
# This is Microsoft's standard CI/CD principal pattern. D-08's mutation-isolation
# intent is preserved (Reader cannot grant roles, write resources, or modify state).
# See CONTEXT.md D-08 Amendment v2 for the full rationale.
resource "azurerm_role_assignment" "gha_reader_subscription" {
  scope                = var.subscription_id
  role_definition_name = "Reader"
  principal_id         = azuread_service_principal.github_actions.object_id
  description          = "Refresh-permission for cross-scope role assignments (Gaps F, G). Read-only, no mutation outside prod RG (D-08 v2)."
}
