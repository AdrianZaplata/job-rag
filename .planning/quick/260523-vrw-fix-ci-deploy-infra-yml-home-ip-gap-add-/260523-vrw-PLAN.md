---
phase: 260523-vrw
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/deploy-infra.yml
autonomous: true
requirements:
  - deploy-infra-home-ip-gap (todo)
user_setup:
  - service: github-actions-secrets
    why: "Inject Adrian's home IP into CI's prod terraform apply (matches OPSEC pattern: residential IP stays out of commit history but is now in GitHub repo secrets — acceptable since the single-IP firewall rule is not a security boundary; Postgres also has Entra + admin password auth)."
    env_vars:
      - name: HOME_IP
        source: "GitHub repo -> Settings -> Secrets and variables -> Actions -> New repository secret. Value: current home IP (run `curl -s ifconfig.me` locally). Refresh on ISP DHCP rotation per infra/modules/database/README.md runbook."
    dashboard_config:
      - task: "Create `HOME_IP` repository secret (NOT environment secret — match existing TF_VAR_* secrets which are repo-level: GHCR_PAT, AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID). Same value as `home_ip` line in `infra/envs/prod/terraform.tfvars.local`."
        location: "GitHub repo Settings -> Secrets and variables -> Actions -> Repository secrets"

must_haves:
  truths:
    - "deploy-infra.yml's `Terraform Apply` step no longer fails with `No value for required variable` for var.home_ip"
    - "The new `TF_VAR_home_ip` injection follows the exact same pattern as the existing TF_VAR_* env entries in the same step"
    - "Only the `Terraform Apply` step is modified — `Terraform Init` is unchanged (init does not need data-plane variables, only the azuread provider auth trio per the inline Gap 8.C comment)"
    - "No terraform files are touched — no default added to variables.tf, no module change, no .tfvars file change"
  artifacts:
    - path: ".github/workflows/deploy-infra.yml"
      provides: "CI workflow with TF_VAR_home_ip wired into prod terraform apply"
      contains: "TF_VAR_home_ip:"
  key_links:
    - from: ".github/workflows/deploy-infra.yml (Terraform Apply step env block)"
      to: "secrets.HOME_IP (GitHub repo secret, operator-provisioned)"
      via: "env: TF_VAR_home_ip: ${{ secrets.HOME_IP }}"
      pattern: "TF_VAR_home_ip:\\s+\\$\\{\\{\\s*secrets\\.HOME_IP\\s*\\}\\}"
    - from: "TF_VAR_home_ip env var on CI runner"
      to: "var.home_ip in infra/envs/prod/variables.tf:39"
      via: "Terraform's standard TF_VAR_<name> -> var.<name> resolution at apply time"
      pattern: "variable \"home_ip\""
---

<objective>
Fix the silent CI failure in `.github/workflows/deploy-infra.yml` where `terraform apply (prod)` has aborted on every push for 3+ runs (most recently run #25 on c28bb13) with `Error: No value for required variable / variable "home_ip"`.

The cause is unambiguous: `var.home_ip` (defined at `infra/envs/prod/variables.tf:39`, no default) has its value only in two gitignored local files; the CI workflow already injects `TF_VAR_ghcr_pat`, `TF_VAR_gha_client_id`, `TF_VAR_tenant_id_workforce`, `TF_VAR_use_oidc_auth` into the apply step but does NOT inject `TF_VAR_home_ip`. The fix is to wire `TF_VAR_home_ip: ${{ secrets.HOME_IP }}` into the existing `env:` block, matching the surrounding pattern exactly. The OPSEC trade-off (residential IP enters GitHub repo secrets) is accepted per the todo's Option 1 disposition.

Purpose: Stop the misleading red ✗ in CI run history and restore CI parity with local apply, so the prod env can be reapplied from CI on infra changes without operator intervention (operator-from-local still works; this just unblocks the CI path).

Output: One-line addition to `.github/workflows/deploy-infra.yml` placed in the `Terraform Apply` step's `env:` block, alphabetically/visually fitting with the existing entries.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/todos/pending/deploy-infra-home-ip-gap.md
@.github/workflows/deploy-infra.yml
@infra/envs/prod/variables.tf
@infra/modules/database/README.md

<interfaces>
Existing `Terraform Apply` step env block (`.github/workflows/deploy-infra.yml` lines 59-63) — the new entry must visually match this style:

```yaml
      - name: Terraform Apply
        run: terraform apply -input=false -auto-approve -var-file=prod.tfvars
        # Option B: openai/langfuse secret VALUES are seeded out-of-band via
        # `az keyvault secret set ...` (see prod/README.md). TF only needs ghcr_pat
        # at apply time. OPENAI_API_KEY and LANGFUSE_* are NOT GitHub secrets.
        # Gap 8.C: TF_VAR_gha_client_id / tenant_id_workforce / use_oidc_auth flip
        # the azuread provider into OIDC auth on the CI runner (no Azure CLI dep).
        env:
          TF_VAR_ghcr_pat:            ${{ secrets.GHCR_PAT }}
          TF_VAR_gha_client_id:       ${{ secrets.AZURE_CLIENT_ID }}
          TF_VAR_tenant_id_workforce: ${{ secrets.AZURE_TENANT_ID }}
          TF_VAR_use_oidc_auth:       "true"
```

Note the column-aligned colons (the longest key `TF_VAR_tenant_id_workforce:` sets the column at position 30). The new line `TF_VAR_home_ip:` is shorter and must be padded with spaces to land its value at the same column for visual consistency with the surrounding entries.

The `Terraform Init` step (lines 43-50) intentionally does NOT need `TF_VAR_home_ip` — its inline Gap 8.C comment explains that init only needs the azuread-provider-OIDC-auth trio (`gha_client_id`, `tenant_id_workforce`, `use_oidc_auth`) at provider-plugin-schema-download time. Data-plane variables like `home_ip` are only resolved at apply time. Keep init untouched.
</interfaces>

<scope_boundaries>
DO modify:
- `.github/workflows/deploy-infra.yml` (one new line in the `Terraform Apply` step's `env:` block)

DO NOT modify:
- `infra/envs/prod/variables.tf` — no default for `home_ip` (the variable stays required; CI gets its value from the new secret)
- `infra/envs/prod/prod.tfvars` or `terraform.tfvars.local` — local apply path is unchanged
- `infra/modules/database/main.tf` or `README.md` — no module changes; the runbook stays valid
- The `Terraform Init` step in `deploy-infra.yml` — only `Terraform Apply` needs the new var
- Any other workflow (`deploy-api.yml`, `deploy-spa.yml`, etc.) — `home_ip` is prod-Postgres-firewall-only and only `deploy-infra.yml` runs the prod terraform stack

Out of scope (acknowledge but do not address):
- Option 2 from the todo (remove prod apply from CI): not chosen — Option 1 preserves CI/local parity
- Option 3 from the todo (sentinel default): not chosen — adds conditional complexity to the database module
- Adding branch protection / required check gating on this workflow: orthogonal to this fix
- Validating that the value of `secrets.HOME_IP` actually matches Adrian's current home IP: that is operator runbook responsibility, not CI-enforceable
</scope_boundaries>

<operator_prerequisite>
**Before merging / pushing this change to master, the `HOME_IP` GitHub repository secret MUST exist.** If the secret does not exist when the workflow next fires, the apply step will fail with the same `No value for required variable` error (because `${{ secrets.HOME_IP }}` expands to empty string, and Terraform treats unset string vars with no default as missing).

To provision (operator-only, NOT a Claude task):

```bash
# Get current home IP
curl -s ifconfig.me

# Set the secret via gh CLI (requires `gh auth login` with repo:admin scope)
echo "<the IP from above>" | gh secret set HOME_IP --repo adrianzaplata/job-rag
```

Or via GitHub UI: repo Settings -> Secrets and variables -> Actions -> New repository secret -> Name: `HOME_IP`, Value: `<the IP>`.

The user can also choose to merge first, accept that the next push will still fail, then add the secret and re-run the workflow via `workflow_dispatch` (or via the failing run's "Re-run all jobs" button — which will succeed once the secret is in place because secrets are read at job-start time).
</operator_prerequisite>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add TF_VAR_home_ip to the Terraform Apply step's env block</name>
  <files>.github/workflows/deploy-infra.yml</files>
  <action>
Open `.github/workflows/deploy-infra.yml` and locate the `Terraform Apply` step's `env:` block (currently lines 59-63, containing TF_VAR_ghcr_pat, TF_VAR_gha_client_id, TF_VAR_tenant_id_workforce, TF_VAR_use_oidc_auth).

Add ONE new line: `TF_VAR_home_ip:            ${{ secrets.HOME_IP }}` (note the column-aligned colon — pad with spaces so the `${{` lands at the same column as the surrounding entries; the alignment column is set by the longest key `TF_VAR_tenant_id_workforce:`).

Order the new line FIRST in the block (before `TF_VAR_ghcr_pat`) so it groups the only "data-plane" var visually distinct from the four azuread-provider-auth vars. Alternatively, alphabetical order works fine; the surrounding block is not alphabetical (it's grouped by purpose), so prepending it is the cleanest visual fit. Either placement is acceptable as long as it's inside the `env:` block of the `Terraform Apply` step (NOT the `Terraform Init` step).

Do NOT modify the `Terraform Init` step's env block — its inline Gap 8.C comment explains that init only needs the azuread-provider-OIDC trio; data-plane vars like `home_ip` are apply-time only.

Do NOT modify the inline comment above the apply step's env block. The comment ("Option B: openai/langfuse secret VALUES are seeded out-of-band...") remains accurate; adding `home_ip` does not break its assertion that openai/langfuse stay out of GH secrets. If a future maintainer is curious why `home_ip` is the lone data-plane var in the env block, the todo `.planning/todos/pending/deploy-infra-home-ip-gap.md` is the breadcrumb (do not duplicate it inline — keep the diff minimal).

Do NOT touch any terraform file, any other workflow, or any tfvars file.

After editing, the apply step's env block should look like (exact indentation: 10 spaces for keys, value-column padded to match):

```yaml
        env:
          TF_VAR_home_ip:             ${{ secrets.HOME_IP }}
          TF_VAR_ghcr_pat:            ${{ secrets.GHCR_PAT }}
          TF_VAR_gha_client_id:       ${{ secrets.AZURE_CLIENT_ID }}
          TF_VAR_tenant_id_workforce: ${{ secrets.AZURE_TENANT_ID }}
          TF_VAR_use_oidc_auth:       "true"
```
  </action>
  <verify>
    <automated>grep -E "TF_VAR_home_ip:\s+\\$\\{\\{\\s*secrets\\.HOME_IP\\s*\\}\\}" .github/workflows/deploy-infra.yml && python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/deploy-infra.yml')); apply_step=[s for s in d['jobs']['apply']['steps'] if s.get('name')=='Terraform Apply'][0]; assert 'TF_VAR_home_ip' in apply_step['env'], 'TF_VAR_home_ip missing from Terraform Apply env'; init_step=[s for s in d['jobs']['apply']['steps'] if s.get('name')=='Terraform Init'][0]; assert 'TF_VAR_home_ip' not in init_step.get('env', {}), 'TF_VAR_home_ip should NOT be in Terraform Init env'; print('OK: TF_VAR_home_ip in Apply only, not Init')"</automated>
  </verify>
  <done>
- `.github/workflows/deploy-infra.yml` contains exactly one new `TF_VAR_home_ip: ${{ secrets.HOME_IP }}` entry inside the `Terraform Apply` step's `env:` block
- The grep pattern `TF_VAR_home_ip:\s+\$\{\{\s*secrets\.HOME_IP\s*\}\}` matches in the file
- YAML still parses (the python3 yaml check above confirms structure)
- `TF_VAR_home_ip` does NOT appear in the `Terraform Init` step's env (init untouched)
- No other files were modified (verify with `git status --short` showing only `.github/workflows/deploy-infra.yml`)
- Diff is minimal: exactly one added line (no whitespace-only changes elsewhere in the file)
  </done>
</task>

</tasks>

<verification>
After the task completes, before pushing:

1. `git diff .github/workflows/deploy-infra.yml` shows exactly one added line: `TF_VAR_home_ip: ${{ secrets.HOME_IP }}` (with appropriate alignment whitespace).
2. `git status --short` shows ONLY `.github/workflows/deploy-infra.yml` as modified (no other files touched).
3. The YAML parses cleanly (the inline python3 yaml.safe_load assertion in `<verify>` confirms this; if a maintainer wants a separate check: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-infra.yml'))"`).
4. The grep pattern from `key_links` matches: `grep -E "TF_VAR_home_ip:\s+\\\$\\\{\\\{\s*secrets\.HOME_IP\s*\\\}\\\}" .github/workflows/deploy-infra.yml`.

End-to-end validation (operator-driven, happens after the operator sets the `HOME_IP` secret and merges):
- Next push to master that touches `infra/**` or `.github/workflows/deploy-infra.yml` fires the workflow.
- The `Terraform Apply` step runs through to completion (the `No value for required variable / variable "home_ip"` error does NOT appear).
- The job result is green (modulo any unrelated drift — but the home_ip gap specifically is closed).

This is NOT in the task `<verify>` block because it requires (a) the GitHub secret to exist and (b) a real push. The task-level `<verify>` is the local automated check; the workflow-run verification is the operator's post-merge sanity check.
</verification>

<success_criteria>
- `.github/workflows/deploy-infra.yml` injects `TF_VAR_home_ip` from `secrets.HOME_IP` into the `Terraform Apply` step (only).
- The diff is one added line, no other file changes.
- YAML parses cleanly.
- Operator has been told (in this plan and in any follow-up summary) that they must provision the `HOME_IP` GitHub repository secret before the next push to master, or accept that the first push after merge will still fail until the secret is added.
- The todo `.planning/todos/pending/deploy-infra-home-ip-gap.md` can be moved to `.planning/todos/done/` after the operator confirms a green CI run (NOT in this plan — that's the operator's post-verify housekeeping).
</success_criteria>

<output>
After completion, create `.planning/quick/260523-vrw-fix-ci-deploy-infra-yml-home-ip-gap-add-/260523-vrw-SUMMARY.md` capturing:
- The exact one-line diff applied
- Confirmation that grep + YAML parse checks pass
- A reminder to the operator to (a) provision `HOME_IP` repo secret if not already done, and (b) move `.planning/todos/pending/deploy-infra-home-ip-gap.md` to `done/` after first green CI run
- Any notable deviation (e.g., if the line was placed in a different position within the env block than the suggested "first" placement)
</output>
