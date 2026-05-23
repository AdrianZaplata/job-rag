---
phase: 260523-vrw
plan: 01
type: quick
subsystem: ci-cd
tags: [ci, github-actions, terraform, opsec, infra]
status: complete
completed: 2026-05-23
requires: []
provides:
  - deploy-infra-ci-applies-prod-without-home-ip-error
affects:
  - .github/workflows/deploy-infra.yml
tech-stack:
  added: []
  patterns:
    - TF_VAR_<name> env injection on CI runner (standard Terraform pattern, matches existing TF_VAR_ghcr_pat / TF_VAR_gha_client_id / TF_VAR_tenant_id_workforce / TF_VAR_use_oidc_auth)
key-files:
  created: []
  modified:
    - .github/workflows/deploy-infra.yml
decisions:
  - Option 1 from the todo (inject via GH repo secret) chosen over Option 2 (drop prod-apply from CI) and Option 3 (sentinel default on var.home_ip); preserves CI/local parity without adding conditional complexity to the database module.
  - Placed `TF_VAR_home_ip` as the FIRST entry in the Terraform Apply env block (before TF_VAR_ghcr_pat) per plan's recommended visual grouping — separates the single "data-plane" var from the four "azuread-provider-auth" vars.
metrics:
  duration: 4m
  completed: 2026-05-23
---

# Quick task 260523-vrw: Fix CI `deploy-infra.yml` home_ip gap Summary

One-line addition to `.github/workflows/deploy-infra.yml` wiring `secrets.HOME_IP` into the `Terraform Apply` step as `TF_VAR_home_ip`, resolving 3+ consecutive silent CI failures (most recently run #25 on `c28bb13`) with `Error: No value for required variable / variable "home_ip"`.

## What Changed

Exactly one line added to `.github/workflows/deploy-infra.yml`, inside the `Terraform Apply` step's `env:` block (line 60), placed first so the single "data-plane" var is visually grouped apart from the four azuread-provider-auth vars:

```diff
@@ -57,6 +57,7 @@ jobs:
         # Gap 8.C: TF_VAR_gha_client_id / tenant_id_workforce / use_oidc_auth flip
         # the azuread provider into OIDC auth on the CI runner (no Azure CLI dep).
         env:
+          TF_VAR_home_ip:             ${{ secrets.HOME_IP }}
           TF_VAR_ghcr_pat:            ${{ secrets.GHCR_PAT }}
           TF_VAR_gha_client_id:       ${{ secrets.AZURE_CLIENT_ID }}
           TF_VAR_tenant_id_workforce: ${{ secrets.AZURE_TENANT_ID }}
```

Column alignment matches the surrounding entries (longest key `TF_VAR_tenant_id_workforce:` sets the value column; new key padded with spaces accordingly).

## Verification

Plan's automated verification block executed locally — **PASSED**:

1. `grep -E "TF_VAR_home_ip:\s+\$\{\{\s*secrets\.HOME_IP\s*\}\}" .github/workflows/deploy-infra.yml` → match found:
   ```
   TF_VAR_home_ip:             ${{ secrets.HOME_IP }}
   ```
2. `yaml.safe_load(...)` of the workflow file → clean parse.
3. Python assertion `'TF_VAR_home_ip' in apply_step['env']` → PASS.
4. Python assertion `'TF_VAR_home_ip' not in init_step['env']` → PASS (`Terraform Init` env still contains only the azuread-provider-auth trio — `gha_client_id`, `tenant_id_workforce`, `use_oidc_auth`).
5. Output: `OK: TF_VAR_home_ip in Apply only, not Init`.

Pre-commit `git status --short` showed only `.github/workflows/deploy-infra.yml` as modified — no scope creep. `git diff` shows exactly one added line.

System Python lacked PyYAML; verification was run via `uv run --with pyyaml python -c '...'` (uv-managed Python 3.12 with on-the-fly pyyaml install). Equivalent to the plan's `python3 -c` command.

## Commit

- `f6480e6` — `fix(260523-vrw-01): inject TF_VAR_home_ip into deploy-infra CI apply step`

Atomic single-file commit. Per the orchestrator contract, this SUMMARY.md and STATE.md are NOT in this commit — the orchestrator will create the docs commit separately.

## Deviations from Plan

None. Plan executed exactly as written:
- One added line, no other files touched.
- Placed first in the env block per plan's recommended "data-plane var visually distinct" grouping.
- `Terraform Init` step left untouched (per the inline Gap 8.C comment — init only needs azuread-provider-OIDC-auth trio at provider-plugin-schema-download time; data-plane vars resolve at apply time).
- No terraform files modified (no default added to `infra/envs/prod/variables.tf`, no `prod.tfvars` change, no module change).
- No other workflow files modified.

## Operator Action Required (Post-Merge)

Before the next push to master that touches `infra/**` or `.github/workflows/deploy-infra.yml`, **the `HOME_IP` GitHub repository secret MUST exist**, or the apply step will fail with the same `No value for required variable` error (because `${{ secrets.HOME_IP }}` expands to empty string and Terraform treats unset string vars with no default as missing).

**To provision:**

```bash
# Get current home IP
curl -s ifconfig.me

# Set via gh CLI (requires gh auth login with repo:admin scope)
echo "<the IP from above>" | gh secret set HOME_IP --repo adrianzaplata/job-rag
```

Or via GitHub UI: repo Settings → Secrets and variables → Actions → New repository secret → Name `HOME_IP`, Value `<the IP>`.

Same value as the `home_ip` line in `infra/envs/prod/terraform.tfvars.local`. Refresh on ISP DHCP rotation per `infra/modules/database/README.md` runbook.

**OPSEC trade-off (accepted per todo Option 1):** residential IP now lives in GitHub repo secrets in addition to the local gitignored tfvars. Acceptable because the single-IP firewall rule is not a security boundary — Postgres also enforces Entra + admin-password auth — and the secret remains out of commit history.

## Follow-up Housekeeping (Operator)

After the operator confirms a green CI run on the next infra-touching push:

1. Move `.planning/todos/pending/deploy-infra-home-ip-gap.md` → `.planning/todos/done/`.
2. (Optional) Tag the resolving commit in the todo's body for traceability.

End-to-end validation is operator-driven (requires (a) the GitHub secret to exist and (b) a real push); not in scope for this quick task's local verification.

## Self-Check: PASSED

- `.github/workflows/deploy-infra.yml` modified — FOUND (commit `f6480e6` shows `1 file changed, 1 insertion(+)`)
- Commit `f6480e6` — FOUND (verified via `git log --oneline -1` after commit)
- Plan automated verification — PASSED (grep match + yaml parse + Apply-only assertion all green)
