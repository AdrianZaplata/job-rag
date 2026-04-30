# Module: kv (Key Vault)

AVM-based Key Vault module per CONTEXT.md D-03.

## AVM decision

**Use AVM `Azure/avm-res-keyvault-vault/azurerm` @ 0.10.2** (verified live Oct 14 2025).
- Bundles RBAC defaults (`legacy_access_policies_enabled = false`), soft-delete (`soft_delete_retention_days = 7`), and a `role_assignments` map that takes principal IDs declaratively.
- Saves ~30-50 lines of equivalent raw `azurerm_key_vault` + `azurerm_role_assignment` plumbing.

## Inputs / Outputs

See `variables.tf` and `outputs.tf`.

## What this module does NOT do

- It does **not** create the secrets. Secrets are created by other modules:
  - `database` module writes `postgres-admin-password` (it owns the random_password).
  - `envs/prod/main.tf` (composition layer) writes `openai-api-key`, `langfuse-public-key`, `langfuse-secret-key`, `seeded-user-entra-oid`.
- It does **not** assign the deployer the "Key Vault Secrets Officer" role — that role assignment lives in `envs/prod/main.tf` (composition concern, varies between local apply and GHA SP apply).

## Tenant placement (CONTEXT.md A4)

The KV's `tenant_id` is the **workforce tenant** (Adrian's subscription home tenant), NOT the External tenant. The External tenant is for end-user identity only (SPA + API app registrations).
