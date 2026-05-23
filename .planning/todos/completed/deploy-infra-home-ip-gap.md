---
id: deploy-infra-home-ip-gap
title: deploy-infra.yml fails on `var.home_ip` — CI prod-apply step silently broken
area: infra/ci
priority: medium
status: pending
created: 2026-05-23T20:44:00.000Z
discovered_in: 04.1-06 operator action (Task 09 step 8)
---

## Gap

`.github/workflows/deploy-infra.yml`'s `terraform apply (prod)` step fails on every push with:

```
Error: No value for required variable
  on variables.tf line 39:
  variable "home_ip"
```

Evidenced by run #25 (2026-05-23, commit `c28bb13`), and at least the two prior pushes (run #24 on `docs(phase-04.1): evolve PROJECT.md` 2026-05-22, run #23 on `docs(04-06): flip Phase 4 to COMPLETE` 2026-05-21). The CI failure has been silent throughout — there is no branch protection or required check gating master on this workflow's success.

## Root cause

`home_ip` is defined in `infra/envs/prod/variables.tf:39` with no default. Its value lives only in the two gitignored local files (`infra/envs/prod/prod.tfvars.local`, `infra/envs/prod/terraform.tfvars.local`) per the OPSEC pattern documented in `infra/modules/database/README.md` (residential IP kept out of public commit history).

`deploy-infra.yml` does not inject an equivalent — it passes `TF_VAR_ghcr_pat`, `TF_VAR_gha_client_id`, `TF_VAR_tenant_id_workforce`, `TF_VAR_use_oidc_auth`, but no `TF_VAR_home_ip`. So CI `terraform apply -var-file=prod.tfvars` aborts on a missing variable before doing any work.

The prod apply path has been operator-run-from-local since Phase 4 close-out (Adrian's mac with `prod.tfvars.local` + `terraform.tfvars.local` loaded explicitly). The CI workflow is structurally redundant for prod env apply in the current setup but is still wired to fire on every master push — producing a misleading red ✗ in the run history.

## Options to consider

1. **Add `TF_VAR_home_ip` as a GitHub secret + wire it in the workflow.** Simplest; preserves CI parity with local. Trade-off: residential IP enters a GitHub secret (vs the current "kept out of commit history" OPSEC). Acceptable since the firewall rule is single-IP, not a security boundary (Postgres also has Entra auth + admin password).
2. **Remove `terraform apply (prod)` from `deploy-infra.yml` entirely.** Accept that prod env apply is operator-only (matches the External tenant pattern from 04.1-06). Trade-off: lose CI's automated convergence check; have to remember to apply by hand after every secret/config change.
3. **Make `home_ip` optional with a sentinel default** (e.g. `""` → skip firewall rule). Lets CI plan/apply succeed; firewall rule is then operator-toggled from local apply. Adds conditional complexity to the database module.

## Pointers

- Failing step: `.github/workflows/deploy-infra.yml` → "Terraform Apply" job → `terraform apply -input=false -auto-approve -var-file=prod.tfvars` on prod env
- Variable definition: `infra/envs/prod/variables.tf:39`
- Local value sources (gitignored): `infra/envs/prod/prod.tfvars.local`, `infra/envs/prod/terraform.tfvars.local`
- IP refresh runbook: `infra/modules/database/README.md`
- Related discovery context: Phase 04.1-06 operator action (Task 09 step 8) — surfaced when re-applying prod env locally to roll `BACKEND_AUDIENCE` after the API client_id rotation
