---
phase: 03-infrastructure-ci-cd
fixed_at: 2026-05-19T12:00:00Z
review_path: .planning/phases/03-infrastructure-ci-cd/03-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 3: Code Review Fix Report

**Fixed at:** 2026-05-19T12:00:00Z
**Source review:** `.planning/phases/03-infrastructure-ci-cd/03-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (0 Critical + 4 Warning; Info deferred by fix_scope=critical_warning)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Dev composition uses incorrect diagnostic category name (would fail on apply)

**Files modified:** `infra/envs/dev/main.tf`
**Commit:** `a821732`
**Applied fix:** Replaced `category = "ContainerAppConsoleLogs_CL"` with `category = "ContainerAppConsoleLogs"` on the dev `azurerm_monitor_diagnostic_setting.aca` resource and corrected the trailing comment (also dropped the `_CL` suffix from `ContainerAppSystemLogs` in the omission note). The `_CL` suffix is the LAW table name; the diagnostic category name drops it. Mirrors prod exactly. The previous value would have caused `terraform apply` to 400 with `"Category 'ContainerAppConsoleLogs_CL' is not supported"` if dev were ever applied. `terraform fmt -check` passes.

### WR-02: Dev KV secrets store plaintext value (lags prod Gap 16.A migration)

**Files modified:** `infra/envs/dev/main.tf`
**Commit:** `11de750`
**Applied fix:** Migrated all four `azurerm_key_vault_secret` resources (`openai_api_key`, `langfuse_public_key`, `langfuse_secret_key`, `seeded_user_entra_oid`) from `value = ...` to `value_wo = ...` + `value_wo_version = 1`, mirroring the prod Gap 16.A pattern verbatim. The `lifecycle.ignore_changes = [value]` block was preserved on the three `managed-out-of-band` secrets (prod keeps it too); `seeded_user_entra_oid` has no lifecycle block in either env. Argument alignment updated to match prod (`name`/`value_wo`/`value_wo_version`/`key_vault_id`/`content_type`/`depends_on`). Now if `var.seeded_user_entra_oid` ever holds a real OID, the value never lands in dev TF state. `terraform fmt -check` passes.

### WR-03: Real residential IP committed to public repo via prod.tfvars

**Files modified:** `infra/envs/prod/prod.tfvars`, `infra/modules/database/README.md`, `infra/envs/prod/terraform.tfvars.local` (gitignored, not part of the commit)
**Commit:** `07b4d26`
**Applied fix:** Chose Option 1 (move `home_ip` out of the committed tfvars) as the more thorough OPSEC fix:
- Removed the `home_ip = "79.228.31.2"` literal from `infra/envs/prod/prod.tfvars` and replaced it with a comment block pointing to `terraform.tfvars.local`. The block explains the OPSEC rationale and confirms TF will fail loudly if the value is absent (the variable has no default in `variables.tf:39-42`).
- Added `home_ip = "79.228.31.2"` to `infra/envs/prod/terraform.tfvars.local` (already gitignored via the `*.tfvars.local` pattern at `.gitignore:31`). Verified via `git check-ignore -v` that the path is ignored.
- Updated the refresh runbook in `infra/modules/database/README.md` to `sed` against `terraform.tfvars.local` (with `.bak` cleanup) instead of `prod.tfvars`, with a note that Terraform auto-loads `terraform.tfvars.local` alongside the explicit `-var-file=prod.tfvars`.

The residential IP is now isolated to a local-only file; future refreshes won't add new entries to the public commit history. Note: the historical IP value remains visible in pre-`07b4d26` git history — a separate history-rewrite (e.g., `git filter-repo`) would be required to scrub it, which is out of scope for this fix.

### WR-04: `refresh-swa-origin.sh` leaves a `.bak` file in the env directory

**Files modified:** `scripts/refresh-swa-origin.sh`
**Commit:** `1c5b062`
**Applied fix:** Two changes per the REVIEW.md guidance:
1. Added validation that `terraform output -raw swa_default_origin` returned a non-empty value before string-templating into `SWA_ORIGIN`. Empty output now triggers `FATAL: terraform output swa_default_origin returned empty` and `exit 1` instead of silently writing `swa_origin = "https://"`.
2. Added `rm -f prod.tfvars.bak` immediately after the `sed -i.bak ...` invocation (only on the branch that actually runs sed) to clean up the macOS-sed-mandated backup file, preventing it from cluttering `git status` after every run.

`bash -n` syntax check passes. The script's existing `set -euo pipefail` posture is preserved; the new validation block surfaces a clean error message instead of relying on `set -u` to trip later.

---

_Fixed: 2026-05-19T12:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
