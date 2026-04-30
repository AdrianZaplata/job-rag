# Module: monitoring (LAW + diagnostic_setting + budget)

Three resources in one module: Log Analytics workspace (AVM), Container App diagnostic setting (raw azurerm), consumption budget (raw azurerm).

## AVM decision

**Use AVM `Azure/avm-res-operationalinsights-workspace/azurerm` @ 0.5.1** for LAW only.
- Diagnostic settings + consumption budget have no AVM coverage — raw `azurerm_*` resources are canonical.

### W3 verification spike (run BEFORE writing module code)

The exact AVM module output attribute names (`resource_id` vs `id` vs `workspace_id`) are not guaranteed across minor versions. Before relying on `module.log_analytics.resource_id` (LAW 0.5.1) and `module.key_vault.resource_id` (KV 0.10.2), run:

```bash
cd infra/modules/monitoring
terraform-docs markdown table .
# Inspect the Outputs section. If LAW exposes `id` instead of `resource_id`, update both
# this module's outputs.tf AND envs/prod/main.tf wiring before terraform validate.
```

Same A5 pattern as the AVM Postgres `server_configuration` spike. Trivial (≤5 min).

If `module.log_analytics.resource.workspace_id` is unavailable on 0.5.1 (this is the W3 finding), the module already uses a separate `data "azurerm_log_analytics_workspace"` for the customer (workspace) GUID — no further change needed.

## Cost guardrails (D-16, D-18)

| Guardrail | Value | Source |
|-----------|-------|--------|
| LAW daily quota | 0.15 GB/day (≈4.5 GB/mo) | D-16; keeps free-tier ingest under the 5 GB/mo alert |
| LAW retention | 30 days | Default; longer needs paid tier |
| Diagnostic categories | `ContainerAppConsoleLogs_CL` ONLY | D-16; `SystemLogs_CL` deliberately omitted (revision-swap noise) |
| Budget | €10/mo, thresholds 50/75/90/100% | D-18; subscription-scoped — exactly ONE prod budget per subscription |

## Why `create_budget` is conditional

Subscription budgets are subscription-scoped, so dev + prod sharing the same subscription must NOT both create one. `envs/prod/main.tf` passes `create_budget = true`; `envs/dev/main.tf` passes `create_budget = false` (dev scaffold piggybacks on the prod budget for cost coverage anyway, since it doesn't apply).

## Where diagnostic_setting lives (W7 fix)

`azurerm_monitor_diagnostic_setting.aca` is **NOT defined in this module**. It lives at the composition layer (`envs/{env}/main.tf`), because:

- Diagnostic settings reference a target resource (ACA Container App) that is itself created at the composition layer.
- Defining the diagnostic setting both here AND at composition would cause a duplicate-resource conflict on `terraform apply`.
- The composition layer already has access to `module.compute.aca_id` and `module.monitoring.workspace_id`, so the wiring is clean.

The monitoring module's job is workspace + budget; the composition layer wires diagnostic_setting against it. This module exposes `workspace_id` for the composition layer to consume.

## Re-enabling SystemLogs

For one-off cold-start / revision-swap forensics, re-enable `ContainerAppSystemLogs_CL` via the portal (NOT in Terraform). When forensics is done, disable in portal again. Documented anti-pattern: adding it permanently to this module — drives ingest cost without observability value.
