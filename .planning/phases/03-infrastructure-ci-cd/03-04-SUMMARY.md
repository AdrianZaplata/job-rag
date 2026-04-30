---
phase: 03-infrastructure-ci-cd
plan: 04
subsystem: infra
tags: [terraform, azure, postgres, container-apps, entra-id, oidc, github-actions, key-vault, avm]

requires:
  - phase: 03-infrastructure-ci-cd
    provides: "Plan 03-03 shipped network/kv/monitoring shared modules — compute consumes ACA env_id from network; database+compute consume KV id + secret URIs from kv; monitoring will diagnostic-target the Container App ID emitted here"
  - phase: 03-infrastructure-ci-cd
    provides: "Plan 03-01 ships static-tf.yml CI workflow that runs terraform fmt + validate against modules/ — covers static-validation gate since terraform CLI is not available locally"
provides:
  - "infra/modules/database — AVM Postgres Flex B1ms + 32-char random_password + KV-backed admin secret + jobrag DB + VECTOR allowlist + A1 Path A firewall"
  - "infra/modules/compute — azurerm_container_app (raw) with scale-to-zero, system MI, 5 KV-backed key_vault_secret_id refs, GHCR registry, B5 image lifecycle ignore, full Phase 1 env var contract"
  - "infra/modules/identity — 3 azuread_applications (SPA + API in External tenant; GHA in Workforce tenant) + 2 federated credentials (lowercased subjects) + RG-scoped Contributor role"
  - "Output contracts ready for Plan 05's envs/prod/main.tf composition: database.fqdn/admin_login/db_name/admin_password_secret_uri, compute.aca_id/aca_fqdn/aca_principal_id/aca_name, identity.spa_app_client_id/api_app_client_id/api_app_identifier_uri/gha_client_id/access_as_user_scope_id"
affects: [03-05a, 03-05b, 03-06, 03-07, 03-08, phase-04-frontend, phase-05-deployment]

tech-stack:
  added:
    - "Azure/avm-res-dbforpostgresql-flexibleserver/azurerm @ 0.2.2 (AVM Postgres Flex)"
    - "azurerm_container_app (raw, ~v4.69)"
    - "azuread provider ~v3.0 with configuration_aliases [external, workforce]"
    - "random_password + random_uuid (hashicorp/random ~v3.6)"
  patterns:
    - "Multi-tenant azuread provider via configuration_aliases — composition layer wires aliases"
    - "KV-backed Container App secrets via key_vault_secret_id URIs — values never enter TF state"
    - "lifecycle.ignore_changes for CI-owned image tags — Terraform owns shape, deploy-api.yml owns running image"
    - "compact() + empty-string filter for two-pass DEPL-12 redirect_uris (no list-element-null errors)"
    - "Lowercased OIDC subjects via lower(var.github_owner)/lower(var.github_repo) — AADSTS700213 prevention"

key-files:
  created:
    - "infra/modules/database/main.tf — AVM Postgres + random_password + KV secret"
    - "infra/modules/database/variables.tf — env, location, RG, admin_login, key_vault_id, kv_admin_role_assignment_id, home_ip, use_allow_azure_services, tags"
    - "infra/modules/database/outputs.tf — fqdn, admin_login, db_name, admin_password_secret_uri/name"
    - "infra/modules/database/README.md — D-03 AVM decision, A1 trade-offs, A5 spike, IP refresh runbook"
    - "infra/modules/compute/main.tf — azurerm_container_app with 5 KV refs + GHCR registry + lifecycle ignore"
    - "infra/modules/compute/variables.tf — env, RG, aca_env_id, ghcr_username/pat, image_tag, kv_secret_uris (with 5-key validation), postgres_fqdn/admin_login, allowed_origins, seeded_user_id, tags"
    - "infra/modules/compute/outputs.tf — aca_id, aca_fqdn (ingress[0].fqdn stable accessor), aca_principal_id, aca_name"
    - "infra/modules/compute/README.md — D-03, B5 lifecycle trade-off explanation, env var contract table, entrypoint composition note"
    - "infra/modules/identity/main.tf — 3 app regs + 2 federated creds + RG-scoped Contributor"
    - "infra/modules/identity/variables.tf — swa_origin (default ''), github_owner, github_repo, resource_group_id"
    - "infra/modules/identity/outputs.tf — spa/api/gha client IDs, api_identifier_uri, gha_object_id, access_as_user_scope_id"
    - "infra/modules/identity/README.md — tenant placement table, federated credential subjects, two-pass redirect_uris, Phase 4 hand-off"
  modified: []

key-decisions:
  - "Used AVM @ 0.2.2 for database (D-03 compliance) but raw azurerm for compute (AVM still pre-stable for ACA) and raw azuread for identity (no AVM coverage)"
  - "Compute lifecycle.ignore_changes on [template[0].container[0].image, template[0].revision_suffix] — Terraform's view of image will diverge from reality after first deploy-api.yml run, but that's the correct CI-owned-tag trade-off (B5)"
  - "kv_secret_uris validation block enforces all 5 required keys at variable level — fails fast at terraform plan rather than at apply"
  - "SPA redirect_uris uses compact([empty_string_or_url, localhost]) instead of compact([null, localhost]) — Terraform list literals reject null elements; empty-string is the only safe sentinel for compact()"
  - "Federated credential subjects template var.github_owner/var.github_repo through lower() at the HCL level — the deployer's tfvars value can be anything, the OIDC subject claim is always lowercase as GitHub emits it"

patterns-established:
  - "AVM-vs-raw decision documented in each module's README under '## AVM decision (D-03)' heading — future modules follow this format"
  - "Secret block with identity='System' + key_vault_secret_id is the canonical KV-backed Container App secret pattern (5 instances; literal ghcr-pat is the lone exception with documented chicken-and-egg rationale)"
  - "Two-pass DEPL-12 lifecycle: var.swa_origin defaults to '' so first apply works without a SWA; second apply rewrites after refresh-swa-origin.sh"

requirements-completed: [DEPL-02, DEPL-03, DEPL-04, DEPL-06, DEPL-07, DEPL-08, DEPL-09]

duration: 8min
completed: 2026-04-30
---

# Phase 03 Plan 04: Shared TF Modules (database + compute + identity) Summary

**Three Wave-1 shared Terraform modules — AVM Postgres Flex B1ms with VECTOR allowlist + KV-backed admin password, raw `azurerm_container_app` with scale-to-zero and 5 KV-backed `key_vault_secret_id` refs (B5 image-lifecycle ignore), and 3-app-reg azuread identity surface across two tenants with lowercased OIDC subjects and an RG-scoped Contributor role.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-30T00:00:00Z
- **Completed:** 2026-04-30T00:08:00Z
- **Tasks:** 3
- **Files created:** 12

## Accomplishments

- **database module** ships the full AVM Postgres Flex surface (B_Standard_B1ms, 32 GB, server v16, jobrag DB, `azure.extensions=VECTOR` allowlist) plus the `random_password` + `azurerm_key_vault_secret.pg_admin_password` resources that are the password's only persistence — depends_on the externally-passed `kv_admin_role_assignment_id` to avoid RBAC propagation races. Firewall_rules merge the home-IP rule with the optional 0.0.0.0 "Allow Azure services" rule per A1 Path A.
- **compute module** ships the largest single TF resource in the phase (`azurerm_container_app`) with min/max replicas 0/1, terminationGracePeriod 120s (D-15), system-assigned MI (D-13), GHCR registry block with literal `ghcr-pat` secret, 5 KV-backed secret blocks via `key_vault_secret_id` URI references, full Phase-1 env-var contract (POSTGRES_HOST/DB/USER literals + POSTGRES_ADMIN_PASSWORD secret_name, ALLOWED_ORIGINS literal for DEPL-12 second-pass overwrite, OPENAI_API_KEY/LANGFUSE_*/SEEDED_USER_ENTRA_OID via secret_name, plus AGENT_TIMEOUT/HEARTBEAT/SEEDED_USER_ID literals), B5 `lifecycle.ignore_changes` on `[template[0].container[0].image, template[0].revision_suffix]` so deploy-api.yml owns the live tag, and W5 stable `ingress[0].fqdn` output.
- **identity module** ships all three `azuread_application` resources across `azuread.external` (SPA + API) and `azuread.workforce` (GHA) provider aliases, the API's `oauth2_permission_scope = access_as_user` keyed off a `random_uuid` for cross-apply stability, the SPA's `single_page_application { redirect_uris = compact([...]) }` block (B1 empty-string-not-null pattern), two `azuread_application_federated_identity_credential` resources with `lower(var.github_owner)/lower(var.github_repo)` subjects (master push + environment:production), and the `azurerm_role_assignment.gha_rg_contributor` scoped to the resource group (NEVER subscription per D-08).

## Task Commits

1. **Task 1: database module (AVM Postgres Flex + random_password + KV secret + firewall A1 Path A)** — `2c9f9e9` (feat)
2. **Task 2: compute module (azurerm_container_app — scale-to-zero, KV refs, GHCR registry)** — `f4dc613` (feat)
3. **Task 3: identity module (3 app regs + 2 federated credentials + RG-scoped role)** — `887b539` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

All files newly created (12 total = 3 modules × {main.tf, variables.tf, outputs.tf, README.md}). See frontmatter `key-files.created` for the full list and per-file summary.

## Decisions Made

- **AVM only for database; raw for compute + identity** — D-03 says "use AVM where reasonably stable". AVM for Postgres Flex is at 0.2.2 with stable inputs, so we used it. AVM for ACA is documented pre-stable; raw `azurerm_container_app` has stabilized and Microsoft samples are battle-tested. No AVM coverage exists for `azuread`.
- **Compute `lifecycle.ignore_changes` accepts a permanent Terraform↔reality drift on the image field** — this is the correct trade-off for a CI-driven image lifecycle where deploy-api.yml is the source of truth for the running tag. Drift detection runs are documented in compute/README.md as expected (use `terraform apply -refresh-only` if drift output ever needs reconciling).
- **`kv_secret_uris` variable validation enforces all 5 required keys** — fails at `terraform plan` rather than later at `apply` when the missing key would error inside an unhelpful map-lookup expression.
- **`compact([var.swa_origin == "" ? "" : "${var.swa_origin}/", "http://localhost:5173/"])` instead of `compact([var.swa_origin == "" ? null : ...])`** — Terraform forbids `null` as a list element when constructing the list literal (the original RESEARCH.md sketch used `null` and would have errored on `terraform plan`). Empty-string is the only safe sentinel that `compact()` strips cleanly. This is the B1 fix called out in CONTEXT.md and was carried into the implementation faithfully.

## Deviations from Plan

None — plan executed exactly as written. The plan body already incorporated B1, B5, W5, A1, A2, A4, D-03, D-05/06/07/08, D-10/11/12, D-13, D-15, D-17, and DEPL-12 fixes/decisions; the implementation is a faithful transcription of the canonical skeletons in RESEARCH.md (lines 539-632 for compute, 853-926 for database, 1070-1143 for identity).

## Issues Encountered

- **Terraform CLI not available on this Windows dev machine** — `which terraform` returns "command not found". Per the plan's deferred-validation note, `terraform fmt -check` + `terraform validate -backend=false` could not be run locally. Plan 03-01's `static-tf.yml` GitHub Actions workflow runs both gates against `infra/modules/**` on every PR and on push to master, which catches any HCL syntax or shape errors before any deployer runs `terraform apply`. This is the documented fallback path; no work is blocked.
- **CRLF line-ending warnings on commit** — Windows-default `core.autocrlf=true` rewrote LF→CRLF in the working copy after add. The committed blob retains LF (Git normalizes to LF in the repo); `static-tf.yml` runs in Linux and will see LF as expected. No action needed.

## User Setup Required

None — no external service configuration introduced. (Plan 02 already documented bootstrap-tier portal click-paths; this plan is pure shared-module Terraform code that the prod composition layer in Plan 05 will instantiate.)

## Next Phase Readiness

- **Plan 05 (envs/prod/main.tf composition) is unblocked**: it can now `module "database" { source = "../../modules/database" ... }`, `module "compute" { source = "../../modules/compute" ... }`, `module "identity" { source = "../../modules/identity" ... providers = { azuread.external = azuread.external, azuread.workforce = azuread.workforce } }` and wire the outputs of network/kv/monitoring (from 03-03) + database (from this plan) into compute's inputs.
- **Plan 06 (deploy workflows)** can now reference identity's `gha_client_id` output as the `AZURE_CLIENT_ID` GitHub secret value.
- **Phase 4 (frontend MSAL config)** has the full hand-off bundle: `spa_app_client_id`, `api_app_client_id`, `api_app_identifier_uri`, `access_as_user_scope_id`, plus the bootstrap-tier `tenant_id_external` + `tenant_subdomain` from Plan 02.
- **Open follow-up for Plan 05**: `scripts/docker-entrypoint.sh` currently expects a pre-composed `DATABASE_URL` / `ASYNC_DATABASE_URL`. Plan 03 emits POSTGRES_* parts. Either Plan 05's prod composition adds entrypoint-side composition logic (preferred — keeps Phase 1's local docker-compose flow unchanged) or it adds composed `DATABASE_URL` / `ASYNC_DATABASE_URL` env entries. Documented in `infra/modules/compute/README.md` "Entrypoint composition" section.

## Threat Flags

None — all new TF surface aligns with the plan's `<threat_model>` register. T-3-01/03/04/06/07/08 mitigations are all implemented as specified; no new endpoints, auth paths, or trust boundaries were introduced beyond what the plan already enumerated.

## Self-Check: PASSED

- All 12 created files verified present on disk.
- All 3 task commits verified in git history (`2c9f9e9`, `f4dc613`, `887b539`).
- `terraform fmt -check` + `terraform validate -backend=false`: deferred to Plan 03-01's `static-tf.yml` CI workflow (terraform CLI not installed locally; this is the documented fallback path).

---
*Phase: 03-infrastructure-ci-cd*
*Completed: 2026-04-30*
