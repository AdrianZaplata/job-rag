---
phase: 03-infrastructure-ci-cd
plan: 03
subsystem: infra
tags: [terraform, azure, modules, avm, key-vault, log-analytics, container-apps, consumption-budget]

# Dependency graph
requires:
  - phase: 03-infrastructure-ci-cd
    provides: Static-TF lint harness + .gitignore Terraform block (Plan 01); bootstrap providers + tenant variables pattern (Plan 02)
provides:
  - Three shared Terraform modules (network, kv, monitoring) — 12 files (3 modules × 4 files)
  - network module — raw azurerm_container_app_environment (Consumption tier) consuming log_analytics_workspace_id
  - kv module — AVM Key Vault @ 0.10.2 with RBAC + role_assignments map for ACA system MI
  - monitoring module — AVM LAW @ 0.5.1 (daily_quota_gb=0.15) + consumption budget (€10/mo, 4 thresholds)
  - Output contracts that Plan 04 (database/compute/identity modules) and Plan 05a (envs/prod composition) consume
affects: [03-04 (database/compute/identity sibling modules), 03-05a (envs/prod composition)]

# Tech tracking
tech-stack:
  added:
    - "Azure/avm-res-keyvault-vault/azurerm @ 0.10.2 (AVM Key Vault module)"
    - "Azure/avm-res-operationalinsights-workspace/azurerm @ 0.5.1 (AVM Log Analytics workspace module)"
    - "azurerm_container_app_environment (raw azurerm; Consumption tier)"
    - "azurerm_consumption_budget_subscription (raw azurerm; 4-notification dynamic block)"
  patterns:
    - "Per-module providers block (terraform { required_version, required_providers { azurerm ~> 4.69 } }) — each module is self-contained for terraform validate"
    - "AVM-vs-raw decision documented per module README per CONTEXT.md D-03"
    - "data.azurerm_subscription.current.id over var.subscription_id — auto-prefixed /subscriptions/ resource ID, no hardcoding (W1 fix)"
    - "Diagnostic_setting at composition layer, NOT in monitoring module (W7 fix) — avoids duplicate-resource conflict with envs/prod/main.tf wiring"
    - "Separate data source for LAW customer (workspace) GUID via data.azurerm_log_analytics_workspace (W3 fix) — AVM 0.5.1 attribute name uncertainty"
    - "create_budget gate flag — subscription-scoped budget created exactly once (prod=true, dev=false)"
    - "Conditional purge_protection_enabled = var.env == \"prod\" ? true : false — one-way switch only flipped on in prod"

key-files:
  created:
    - infra/modules/network/main.tf
    - infra/modules/network/variables.tf
    - infra/modules/network/outputs.tf
    - infra/modules/network/README.md
    - infra/modules/kv/main.tf
    - infra/modules/kv/variables.tf
    - infra/modules/kv/outputs.tf
    - infra/modules/kv/README.md
    - infra/modules/monitoring/main.tf
    - infra/modules/monitoring/variables.tf
    - infra/modules/monitoring/outputs.tf
    - infra/modules/monitoring/README.md
  modified: []

key-decisions:
  - "kv module's tenant_id input is wired to the workforce tenant (var.tenant_id_workforce) per A4 — KV roles + RBAC live alongside Azure RM, NOT in the External tenant"
  - "monitoring module uses a count-based gate (var.create_budget) on azurerm_consumption_budget_subscription so the dev scaffold doesn't fight the prod budget for the single subscription-scoped slot"
  - "monitoring outputs use module.log_analytics.resource_id (not .id) per AVM convention — README documents the W3 verification spike (terraform-docs markdown table) for executors to confirm at composition time"
  - "purge_protection_enabled is conditional on env (prod=true, dev=false) — Discretion permits dev easier-teardown; prod is one-way switched on for KV durability"
  - "All three modules use lifecycle/dynamic blocks idiomatically (consumption_budget's dynamic notification + lifecycle.ignore_changes on time_period start_date) — matches RESEARCH.md canonical patterns"

patterns-established:
  - "Pattern: AVM-vs-raw per-module decision documented in README.md. Each module's README has an 'AVM decision' section that names the AVM module + version + rationale (or names the resource type and rationale for skipping AVM). Future security/cost audits can trace each module's choice back to D-03."
  - "Pattern: subscription resource ID via data.azurerm_subscription.current.id, never via formatted var.subscription_id. Eliminates a class of off-by-one '/subscriptions/{id}' formatting bugs and keeps the module portable across subscriptions without re-templating."
  - "Pattern: composition-layer-only resources (W7). When a resource (diagnostic_setting) needs inputs from TWO sibling modules (workspace_id + aca_id), it lives at the composition layer that imports both — NOT inside either module. Module exports the input it owns; composition layer does the wiring."

requirements-completed: [DEPL-02, DEPL-03, DEPL-06, DEPL-10, DEPL-11]

# Metrics
duration: ~3m
completed: 2026-04-30
---

# Phase 3 Plan 03: Three Shared Modules (network + kv + monitoring) Summary

**Three Terraform modules ship with main.tf + variables.tf + outputs.tf + README.md (12 files): network = raw azurerm Container App Environment, kv = AVM Key Vault @ 0.10.2 with RBAC + role_assignments for ACA system MI, monitoring = AVM Log Analytics @ 0.5.1 + €10/mo consumption budget at subscription scope. Diagnostic_setting moved to composition layer per W7.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-30T16:16:39Z
- **Completed:** 2026-04-30T16:19:02Z
- **Tasks:** 3 (all autonomous, atomic commits)
- **Files created:** 12
- **Files modified:** 0

## Accomplishments

- **network module** ships single-resource `azurerm_container_app_environment` (Consumption tier) with `log_analytics_workspace_id` input and `env_id`/`env_default_domain`/`env_static_ip_address` outputs. README documents the A1 outbound-IP trade-off (informational only — security boundary is TLS + 32-char password per D-10/A1).
- **kv module** ships AVM `Azure/avm-res-keyvault-vault/azurerm @ 0.10.2` with `legacy_access_policies_enabled = false` from first apply (RBAC only per D-13), `purge_protection_enabled` conditional on env, and a `role_assignments.aca_system_mi` map entry granting "Key Vault Secrets User" to the ACA system-assigned MI. Outputs `kv_id`/`kv_uri`/`kv_name` for compute + database + identity consumers.
- **monitoring module** ships AVM `Azure/avm-res-operationalinsights-workspace/azurerm @ 0.5.1` with `log_analytics_workspace_daily_quota_gb = 0.15` + 30-day retention (D-16) plus an `azurerm_consumption_budget_subscription` resource gated by `var.create_budget` (subscription-scoped — only prod creates) using `data.azurerm_subscription.current.id` (W1 fix, no hardcoding) with a 4-notification dynamic block (50/75/90/100% per D-18). `azurerm_monitor_diagnostic_setting.aca` is intentionally NOT defined here (W7 fix — moved to composition layer).
- All three modules pin `azurerm ~> 4.69` and `terraform >= 1.9` per Plan 01 / STACK.md conventions.
- All three READMEs document the AVM-vs-raw decision per CONTEXT.md D-03 (kv = AVM bundles RBAC + role_assignments; monitoring = AVM for LAW only, raw azurerm for diagnostic + budget; network = raw azurerm because AVM ACA env module is pre-stable).

## Task Commits

Each task was committed atomically:

1. **Task 1: network module (ACA Container App Environment)** — `32d2706` (feat)
2. **Task 2: kv module (AVM Key Vault @ 0.10.2)** — `de7deb0` (feat)
3. **Task 3: monitoring module (AVM LAW @ 0.5.1 + budget)** — `102b672` (feat)

**Plan metadata:** _(this commit)_

## Files Created/Modified

- `infra/modules/network/main.tf` — `azurerm_container_app_environment` (Consumption); provider pin `azurerm ~> 4.69`; `terraform >= 1.9`
- `infra/modules/network/variables.tf` — env (validated prod|dev), location, resource_group_name, log_analytics_workspace_id, tags
- `infra/modules/network/outputs.tf` — env_id, env_default_domain, env_static_ip_address (informational only)
- `infra/modules/network/README.md` — AVM-skipped rationale; A1 outbound-IP trade-off documented
- `infra/modules/kv/main.tf` — AVM KV `0.10.2`; `legacy_access_policies_enabled = false`; `purge_protection_enabled` conditional; `role_assignments.aca_system_mi` with "Key Vault Secrets User"
- `infra/modules/kv/variables.tf` — env, location, resource_group_name, tenant_id_workforce (A4), aca_principal_id (nullable for late-bind), tags
- `infra/modules/kv/outputs.tf` — kv_id, kv_uri, kv_name (sourced from `module.key_vault.resource_id` / `.uri` / `.name` per AVM convention)
- `infra/modules/kv/README.md` — AVM choice rationale; tenant placement (A4); scope clarification (which secrets live elsewhere)
- `infra/modules/monitoring/main.tf` — AVM LAW `0.5.1`; daily_quota_gb=0.15; 30-day retention; `azurerm_consumption_budget_subscription` gated on `var.create_budget` with 4-threshold dynamic notification; `data.azurerm_subscription.current` (W1)
- `infra/modules/monitoring/variables.tf` — env, location, resource_group_name, create_budget (bool gate), budget_alert_email, tags. NO aca_id (W7) and NO subscription_id (W1).
- `infra/modules/monitoring/outputs.tf` — workspace_id (from `module.log_analytics.resource_id`), workspace_customer_id (via `data.azurerm_log_analytics_workspace.this.workspace_id` per W3), workspace_name
- `infra/modules/monitoring/README.md` — AVM choice + W3 verification spike + cost guardrails (D-16/D-18) + create_budget rationale + W7 "where diagnostic_setting lives" rationale + SystemLogs re-enable note

## Decisions Made

- All decisions inherited from CONTEXT.md / RESEARCH.md / plan body. Notable executor-time choices:
  - Used `data.azurerm_subscription.current.id` directly (auto-prefixed `/subscriptions/{guid}`) per W1 — no manual prefix concatenation.
  - Kept `aca_principal_id` as `default = null` in kv variables — composition layer wires it AFTER ACA Container App is created (late-bind pattern; downstream Plan 05a will pass `module.compute.aca_principal_id`).
  - Preserved canonical HCL formatting (2-space indent, aligned `=` in resource blocks, blank lines between resources, lowercase keywords) so files match `terraform fmt`'s default output even though the CLI was unavailable to enforce it locally.

## Deviations from Plan

None — plan executed exactly as written. The plan body provided verbatim file contents for all 12 files and they were applied byte-for-byte (with the standard CRLF-on-Windows git checkout warning, which is content-neutral).

## Issues Encountered

- **Terraform CLI unavailable on executor host.** `which terraform` returned not-found. Per `<critical_context>` ("if not, skip and note in SUMMARY (will be caught by static-tf.yml CI)"), `terraform fmt -check` and `terraform validate -backend=false` were not run locally. Static validation will be enforced by Plan 01's `.github/workflows/static-tf.yml` workflow on the next PR that touches `infra/**`. CRLF warnings from git on Windows checkout are expected (`core.autocrlf` default) and do not affect commit content.

## Authentication Gates

None — this plan is pure module authoring with no live Azure provisioning.

## User Setup Required

None at this time. Composition (Plan 05a) will require:
1. The kv module's `aca_principal_id` will be wired AFTER the compute module creates the Container App with system-assigned MI — that's a Plan 05a concern, not this plan's.
2. The monitoring module's `var.create_budget = true` should be set in `envs/prod/main.tf` only; `envs/dev/main.tf` should pass `false`.
3. The monitoring module's `var.budget_alert_email` should be `adrianzaplata@gmail.com` per D-18.
4. Before composition, run `terraform-docs markdown table .` against each module to confirm AVM module output attribute names (`resource_id` vs `id`) per the W3 verification spike documented in `monitoring/README.md`. Trivial (≤5 min).

## Next Phase Readiness

- **Plan 04 unblocked** (database + compute + identity sibling modules — files_modified disjoint with this plan, parallel-eligible). It will consume:
  - `module.network.env_id` → `azurerm_container_app.container_app_environment_id`
  - `module.kv.kv_id` → database module's `azurerm_key_vault_secret.postgres-admin-password.key_vault_id`
  - `module.monitoring.workspace_id` → composition layer's `azurerm_monitor_diagnostic_setting.aca.log_analytics_workspace_id` (Plan 05a)
- **Plan 05a unblocked** (envs/prod composition): all three modules' outputs are stable + descriptive enough for composition wiring. Diagnostic_setting + KV "Secrets Officer" deployer role + 5 KV-secrets-from-non-database-modules all live at composition per D-13 + W7.
- **Wave 1 disjoint-files invariant honored**: this plan touches only `infra/modules/{network,kv,monitoring}/*`; Plan 04's anticipated files_modified (`infra/modules/{database,compute,identity}/*`) are disjoint, so the two plans can run in parallel without merge conflicts.

## Threat Flags

None new. The plan's threat register (T-3-01, T-3-06) was honored:

- **T-3-01 (Information Disclosure / KV via ACA MI)** — `legacy_access_policies_enabled = false` from first apply (kv main.tf line `legacy_access_policies_enabled = false`); `role_assignments.aca_system_mi` grants only "Key Vault Secrets User" (read-only). Deployer "Secrets Officer" role lives at composition per D-13.
- **T-3-01 (Tampering / KV purge protection)** — `purge_protection_enabled = var.env == "prod" ? true : false` — prod is one-way protected; dev scaffold (D-04) accepts easier-teardown trade-off.
- **T-3-06 (Denial of Service / Cost — LAW)** — `log_analytics_workspace_daily_quota_gb = 0.15` caps ingest at ≈4.5 GB/mo, below the 5 GB/mo free-tier alert.
- **T-3-06 (Denial of Service / Cost — Budget)** — `azurerm_consumption_budget_subscription` with 4-threshold dynamic notifications (50/75/90/100% on €10/mo); subscription-scoped via `data.azurerm_subscription.current.id`.
- **T-3-06 (LAW SystemLogs ingestion)** — diagnostic_setting deferred to composition layer per W7; composition will enable ONLY `ContainerAppConsoleLogs_CL` per D-16. README documents the SystemLogs re-enable anti-pattern.

## Self-Check: PASSED

Verified on disk + in git:
- `[ -f infra/modules/network/main.tf ]` — FOUND
- `[ -f infra/modules/network/variables.tf ]` — FOUND
- `[ -f infra/modules/network/outputs.tf ]` — FOUND
- `[ -f infra/modules/network/README.md ]` — FOUND
- `[ -f infra/modules/kv/main.tf ]` — FOUND
- `[ -f infra/modules/kv/variables.tf ]` — FOUND
- `[ -f infra/modules/kv/outputs.tf ]` — FOUND
- `[ -f infra/modules/kv/README.md ]` — FOUND
- `[ -f infra/modules/monitoring/main.tf ]` — FOUND
- `[ -f infra/modules/monitoring/variables.tf ]` — FOUND
- `[ -f infra/modules/monitoring/outputs.tf ]` — FOUND
- `[ -f infra/modules/monitoring/README.md ]` — FOUND
- `git log --oneline | grep 32d2706` — FOUND ("feat(03-03): network module — ACA Container App Environment")
- `git log --oneline | grep de7deb0` — FOUND ("feat(03-03): kv module — AVM Key Vault @ 0.10.2")
- `git log --oneline | grep 102b672` — FOUND ("feat(03-03): monitoring module — AVM LAW @ 0.5.1 + budget")
- `grep -q "0.10.2" infra/modules/kv/main.tf` — FOUND
- `grep -q "0.5.1" infra/modules/monitoring/main.tf` — FOUND
- `grep -q "azurerm ~> 4.69" infra/modules/network/main.tf` — equivalent match `version = "~> 4.69"` FOUND
- `grep -q "Key Vault Secrets User" infra/modules/kv/main.tf` — FOUND
- `grep -q "data \"azurerm_subscription\" \"current\"" infra/modules/monitoring/main.tf` — FOUND (W1 fix)
- `grep -q "diagnostic_setting" infra/modules/monitoring/main.tf` — only in NOTE comment (W7 — diagnostic_setting NOT defined as a resource)
- `grep -q "AVM" infra/modules/network/README.md` — FOUND
- `grep -q "AVM" infra/modules/kv/README.md` — FOUND
- `grep -q "AVM" infra/modules/monitoring/README.md` — FOUND
- `terraform fmt -check` / `terraform validate -backend=false` — DEFERRED to static-tf.yml CI (no Terraform CLI on executor host; files hand-formatted to canonical HCL conventions)

---
*Phase: 03-infrastructure-ci-cd*
*Completed: 2026-04-30*
