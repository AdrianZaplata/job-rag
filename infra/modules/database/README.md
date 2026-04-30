# Module: database (Postgres Flex B1ms + KV-backed admin password)

AVM Postgres module + random_password + KV secret. Owns the postgres-admin-password lifecycle end-to-end.

## AVM decision (D-03)

**Use AVM `Azure/avm-res-dbforpostgresql-flexibleserver/azurerm` @ 0.2.2** (verified Apr 14 2026).
- Bundles `databases` map (D-12 sequencing — TF creates `jobrag`).
- Bundles `firewall_rules` map (no separate `azurerm_postgresql_flexible_server_firewall_rule` calls).
- Bundles `server_configuration` for the `azure.extensions` allowlist (D-12 + RESEARCH.md Pitfall §azure.extensions vs shared_preload_libraries).

## What this module owns

- The 32-char alphanumeric admin password (`random_password.pg_admin`).
- The `postgres-admin-password` KV secret (the password's only persistence).
- The Postgres Flex server itself (B1ms SKU; 32 GB storage; 7d backup retention).
- The `jobrag` database.
- The firewall rules (per A1 Path A).

## What this module does NOT own

- The KV itself — that's `infra/modules/kv/`.
- The deployer's "Key Vault Secrets Officer" role — that's at `envs/prod/main.tf` composition layer (the role assignment ID is passed in as `kv_admin_role_assignment_id` for `depends_on`).
- The `vector` extension — Alembic migration 0001 (Phase 1, already shipped) creates it at Container App startup against the `jobrag` DB. This module only allowlists VECTOR via `azure.extensions`.

## Knowingly-accepted security trade-offs (CONTEXT.md A1 Path A)

| Trade-off | Rationale |
|-----------|-----------|
| `public_network_access_enabled = true` | Private endpoint costs ~€130/mo and breaks €0 budget. Defer to v2. |
| Firewall includes `0.0.0.0` "Allow Azure services" rule | ACA Consumption-tier outbound IP is documented non-stable; per-IP allowlist would silently break on platform rotation. The security boundary is TLS (`require_secure_transport=on`) + 32-char random password. |
| Admin password is alphanumeric only (no special chars) | URL-encoding of `&%!$` caused alembic ConfigParser issues in Phase 1's dev DB. Alphanumeric-only avoids the entire URL-encoding surface. Still 32 chars of entropy. |
| Public access toggle | The `azure-database-no-public-access` and `azure-database-no-public-firewall-rules` tfsec checks are explicitly allowlisted in `infra/.tfsec/config.yml` per Plan 01. |

## A5 spike

Per CONTEXT.md A5: confirm `server_configuration` shape on first apply by running `terraform-docs markdown table .` against the pinned AVM module. RESEARCH.md uses `extensions_allowlist = { name = "azure.extensions", value = "VECTOR" }`. If the live module's input shape differs (key naming, nested structure), update `main.tf` accordingly — the value `"VECTOR"` stays the same.

## Home IP refresh runbook

Adrian's home IP rotates with ISP DHCP cycles. To refresh:

```bash
# Get current public IP
curl -s ifconfig.me

# Update the value in infra/envs/prod/prod.tfvars
sed -i.bak "s|^home_ip.*|home_ip = \"$(curl -s ifconfig.me)\"|" infra/envs/prod/prod.tfvars

# Re-apply (only the firewall_rules.home rule changes)
cd infra/envs/prod && terraform apply -var-file=prod.tfvars
```

(Per the user's reusable-tools default, this stays as a documented runbook rather than a `scripts/firewall-update-home-ip.sh` — reuse expected ~once a month.)
