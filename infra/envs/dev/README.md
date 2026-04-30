# Dev environment (scaffold-only)

> **Not applied in v1.** Per CONTEXT.md D-04 the dev environment is scaffold-only — `terraform plan -var-file=dev.tfvars` works as a sanity check that the module composition is internally consistent; `terraform apply` is documented but deferred. Cost stays at strict €0.

---

## Why scaffold-only?

V1 is single-user (Adrian). Provisioning a parallel dev stack would burn the €0 budget without delivering value:

- A second Postgres B1ms = ~€12/mo (free tier covers exactly one).
- A second Container App env = within consumption budget but doubles cold-start vCPU-sec usage.
- A second SWA Free = no cost (Free SKU is per-account-unlimited within reason).

Provisioning dev makes sense the day Adrian wants to break prod intentionally without taking the demo offline (e.g. testing a `pg_upgrade` or a major Phase 8 portfolio polish). Until then, scaffold stays.

## Structural parity with prod

Same six-module composition, same `outputs.tf` shape — the diff is in `dev.tfvars` (placeholder values) and three module-input flags:

| Knob | Prod | Dev |
|------|------|-----|
| `env` | `"prod"` | `"dev"` |
| `module.monitoring.create_budget` | `true` | `false` (no second subscription budget) |
| `module.database.use_allow_azure_services` | `true` (A1 Path A) | `false` (dev never applies; firewall rule wouldn't matter) |
| `module.kv.purge_protection_enabled` | `true` | `false` (module default for `env != "prod"` — easier teardown when dev DOES eventually apply) |
| Backend `key` | `prod.tfstate` | `dev.tfstate` (separate state file in same backend) |

The W7 composition-layer `azurerm_monitor_diagnostic_setting.aca` (ContainerAppConsoleLogs_CL only per D-16) is included verbatim for prod parity.

## Apply path (deferred)

When Adrian decides to provision dev:

1. Confirm the External tenant + bootstrap state backend are still healthy.
2. Create the GitHub protected environment `staging` with Adrian as required reviewer.
3. Add a third federated credential to the GHA SP: `subject = "repo:adrianzaplata/job-rag:environment:staging"`.
4. Cut a `staging` branch protection rule + add `staging` to deploy-infra.yml's environment matrix.
5. `cd infra/envs/dev && terraform apply -var-file=dev.tfvars`.

## Sanity-check command

```bash
cd infra/envs/dev
terraform fmt -check
terraform init -backend=false
terraform validate
```

`terraform validate` should pass without reaching the backend (modules compile, variables resolve, dev.tfvars values typecheck). The fmt/validate gates are also exercised by `.github/workflows/static-tf.yml` on every PR.
