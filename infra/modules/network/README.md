# Module: network (ACA Container App Environment)

Single-resource module wrapping `azurerm_container_app_environment` on the Consumption tier.

## AVM decision (CONTEXT.md D-03)

**Use raw `azurerm`.** Rationale:
- AVM module `Azure/avm-res-app/container-app-environment/azurerm` is still pre-stable as of April 2026.
- The raw `azurerm_container_app_environment` resource is well-documented and a single line of meaningful config (the `log_analytics_workspace_id` wire to monitoring).
- AVM would add ~30 lines of input plumbing for zero behavioral difference.

## Inputs / Outputs

See `variables.tf` and `outputs.tf`.

## Knowingly-accepted trade-offs

- **No NAT Gateway / no Workload Profiles tier.** Per CONTEXT.md A1, ACA Consumption-tier outbound IP is documented non-stable; we accept this rather than upgrade to Workload Profiles + NAT Gateway (~€30+/mo) since the Postgres security boundary is TLS + 32-char random password, not IP allowlisting.
- **`env_static_ip_address` output is informational only.** Do NOT use it as a Postgres firewall rule input — it will silently rotate.
