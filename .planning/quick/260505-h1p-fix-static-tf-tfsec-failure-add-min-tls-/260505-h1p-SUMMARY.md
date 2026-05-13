---
quick_id: 260505-h1p
slug: fix-static-tf-tfsec-failure-add-min-tls-
description: Fix static-tf tfsec failure — add min_tls_version=TLS1_2 to tfstate storage account
date: 2026-05-05
status: incomplete
outcome: stated_goal_met_new_blocker_surfaced
fix_commit: bd65e3f
ci_run_after_fix: 25370681564
---

# Quick Task 260505-h1p — Summary

## Stated goal

Fix the `azure-storage-use-secure-tls-policy` (CRITICAL) tfsec failure on PR #4 by
setting `min_tls_version = "TLS1_2"` on the bootstrap tfstate storage account.

## What changed

- **`infra/bootstrap/main.tf`**: Added `min_tls_version = "TLS1_2"` to
  `resource "azurerm_storage_account" "tfstate"` between `account_replication_type`
  and `blob_properties`. Single-line addition, no block reorganization.
- Commit: `bd65e3f` — `fix(infra/bootstrap): set min_tls_version=TLS1_2 on tfstate storage account`
- Pushed to `origin/test/static-tf-smoke` together with `a387143` (local-only docs
  commit from previous quick task `260505-eup`).

## Local verification

- `terraform fmt` — no changes (already formatted correctly)
- `terraform validate` (after `terraform init -backend=false`) — `Success! The
  configuration is valid` (with two pre-existing deprecation warnings on
  `azurerm_storage_container.tfstate.resource_manager_id` — unrelated to this
  change).

## CI result on PR #4 after the fix (run 25370681564)

Static TF workflow steps:

| Step | Before fix | After fix |
|---|---|---|
| Terraform fmt | ✓ | ✓ |
| Setup tflint | ✓ | ✓ |
| Init tflint | ✓ | ✓ |
| Run tflint | ✓ | ✓ |
| **Setup tfsec** | ✗ CRITICAL azure-storage-use-secure-tls-policy | **✓** |
| Terraform validate (envs/prod) | (not reached) | **✗ NEW FAILURE** |
| Terraform validate (envs/dev) | (not reached) | (skipped) |
| Terraform validate (bootstrap) | (not reached) | (skipped) |

Stated goal achieved: tfsec gate is now green. The TLS regression is closed.

## NEW failure surfaced (out of scope — STOP per instructions)

`Terraform validate (envs/prod)` step now fails with exit 1:

```
Error: Unsupported argument
  on .terraform/modules/database.postgres/variables.server.tf line 16,
  in variable "administrator_password_wo":
  16:   ephemeral   = true

An argument named "ephemeral" is not expected here.
```

**Origin:** Downloaded module `registry.terraform.io/Azure/avm-res-dbforpostgresql-flexibleserver/azurerm 0.2.2`
declares an `administrator_password_wo` variable using the `ephemeral` argument,
which requires Terraform ≥ 1.10 (write-only / ephemeral input variables). The CI
runner's Terraform version (via `hashicorp/setup-terraform@v3` default) does not
support it. Local Terraform here is v1.15.0 — which is why local `terraform
validate` passed but CI fails. The bootstrap directory does not pull this AVM
module, so local bootstrap validation never exercised it.

This was masked previously because tfsec failed first and short-circuited the
job. It is unrelated to the tfsec fix and not a regression introduced by this
quick task.

**Likely fix paths (NOT done here):**
- Pin `terraform_version` in `hashicorp/setup-terraform@v3` to `>= 1.10` (or a
  specific version that supports `ephemeral` on input variables) in
  `.github/workflows/static-tf.yml`.
- Or pin the AVM module to a version predating its adoption of ephemeral
  variables.

Per user instruction "If a NEW failure appears on a different gate, capture it
and STOP — do not iterate," this is left for the user to triage as a separate
task.

## UAT impact

**Test 2 in `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` was NOT updated.**
The UAT update was conditional on the static-tf workflow going fully green
(per user instruction). Since `Terraform validate (envs/prod)` now fails,
static-tf is still red and Test 2 cannot be promoted to `pass` yet.

The tfsec issue itself is resolved — Test 2's existing `reported`/`severity`
fields no longer reflect the live state of the storage account, but updating the
UAT row before the workflow is end-to-end green would misrepresent CI status.
Recommend re-running the UAT step of this task once the AVM/Terraform-version
issue is resolved.

## Out-of-scope items left untouched (as instructed)

- `lint-and-test` ruff failures in `src/job_rag/config.py` and
  `src/job_rag/services/ingestion.py` — pre-existing, not addressed.
- `infra/.tflint.hcl` and `infra/envs/prod/prod.tfvars` — already fixed in
  `ff0697c` and `e2a061e`, not modified here.

## Links

- PR #4: https://github.com/AdrianZaplata/job-rag/pull/4
- Original failing run: https://github.com/AdrianZaplata/job-rag/actions/runs/25366641088
- Post-fix run (new failure): https://github.com/AdrianZaplata/job-rag/actions/runs/25370681564
- Fix commit: bd65e3f
