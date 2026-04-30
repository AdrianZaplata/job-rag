# Module: identity (3 app regs + 2 federated credentials + RG-scoped role)

Owns Entra app registrations, OIDC trust, and the RG-scoped Contributor role assignment.

## AVM decision (D-03)

**Use raw `azuread`.** No AVM coverage exists for `azuread` resources as of April 2026.

## Tenant placement

| App reg | Tenant | Provider alias |
|---------|--------|----------------|
| `jobrag-spa` | External (`*.ciamlogin.com`) | `azuread.external` |
| `jobrag-api` | External | `azuread.external` |
| `jobrag-gha` | Workforce (subscription home) | `azuread.workforce` |

The provider aliases MUST be passed in by the composition layer (`envs/prod/main.tf`) per `configuration_aliases = [azuread.external, azuread.workforce]` declaration. CONTEXT.md A4 mandates this separation.

## Federated credentials (D-08)

Two explicit per-trigger credentials on the GHA SP. NO PR-trigger credential — PRs run only static checks (Plan 01's `static-tf.yml`).

| Credential | Subject | Trigger |
|------------|---------|---------|
| `gha-master-push` | `repo:<owner>/<repo>:ref:refs/heads/master` | push to master (deploy-api.yml) |
| `gha-environment-production` | `repo:<owner>/<repo>:environment:production` | environment:production gate (deploy-infra.yml) |

Both subjects are LOWERCASED via `lower(var.github_owner)` + `lower(var.github_repo)` per RESEARCH.md Pitfall §AADSTS700213 (case-sensitive subject mismatch is the #1 OIDC failure mode).

## SPA redirect_uris compact() pattern

The first apply leaves `var.swa_origin = ""` (DEPL-12 two-pass). `compact()` drops the empty string from the redirect_uris list, so `single_page_application.redirect_uris = ["http://localhost:5173/"]` on first apply. Second apply (after `scripts/refresh-swa-origin.sh`) sets `swa_origin` to the SWA default host, and `redirect_uris = ["https://<swa-default>/", "http://localhost:5173/"]`.

D-06: One External tenant for both dev + prod. The SPA app registration carries multiple redirect_uris to support local dev alongside production.

## RG-scoped role assignment (D-08)

`azurerm_role_assignment.gha_rg_contributor.scope = var.resource_group_id` — NEVER subscription scope. Verification: `az role assignment list --assignee <gha-sp-id> --scope <subscription-id>` MUST return empty.

## What this module does NOT do

- It does NOT create the External tenant — that's bootstrap's portal click-path (D-05).
- It does NOT update the SPA's `redirect_uris` on second apply — Plan 05's composition layer feeds `var.swa_origin` from `data.azurerm_static_web_app.spa.default_host_name` and triggers the apply.
- It does NOT manage the GH protected environment (`production`) — that's a GitHub repo settings concern (out-of-tree; documented in Plan 06's GHA workflow runbook).

## Hand-off to Phase 4

Phase 4 consumes:
- `spa_app_client_id` → MSAL `clientId`
- `api_app_client_id` → MSAL `apiClientId`
- `api_app_identifier_uri` → fastapi-azure-auth audience
- `access_as_user_scope_id` → MSAL `scopes: ["api://jobrag-api/access_as_user"]`
- (from bootstrap) `tenant_id_external` + `tenant_subdomain` → MSAL authority `https://${tenant_subdomain}.ciamlogin.com/${tenant_id}/v2.0`
