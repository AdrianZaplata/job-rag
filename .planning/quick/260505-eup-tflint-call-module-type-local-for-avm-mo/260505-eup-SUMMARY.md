---
phase: quick-260505-eup
plan: 01
status: incomplete
one_liner: "Flipped tflint call_module_type all→local — fix landed and tflint now passes; static-tf still red on a new, unrelated tfsec finding (bootstrap storage account missing min_tls_version). STOPPED per scope boundary."
completed: 2026-05-05T08:47:54Z
duration_minutes: ~3
tasks_completed: 1
tasks_total: 3
commits:
  - sha: e2a061e
    message: "fix(infra): tflint call_module_type local to skip registry AVMs"
    branch: test/static-tf-smoke
files_modified:
  - infra/.tflint.hcl
files_not_modified_intentionally:
  - .planning/phases/03-infrastructure-ci-cd/03-UAT.md  # gated on green static-tf per scope_boundary rule 3
ci_run:
  workflow: static-tf
  url: https://github.com/AdrianZaplata/job-rag/actions/runs/25366641088
  conclusion: failure
  failing_step: "Setup tfsec"
  scope_disposition: "out-of-scope new failure — surfaced because tflint now passes (workflow advanced past prior gate)"
  fix_landed: true  # tflint step itself went green
requirements_status:
  DEPL-01: not-yet-complete  # truth #3 of must_haves still unmet (static-tf not all-green end-to-end)
---

# Quick Task 260505-eup: tflint call_module_type local — Summary

## One-liner

Flipped `call_module_type = "all"` → `"local"` in `infra/.tflint.hcl`. The fix worked: the tflint step in `static-tf` now passes cleanly. However, the workflow advanced one step further and revealed a NEW, unrelated tfsec finding on `infra/bootstrap/main.tf` (storage account missing `min_tls_version`). Per the plan's `<scope_boundary>` rule 3 and the user's explicit step 5 instruction, execution STOPPED at this new failure without attempting a second fix. Task 3 (UAT update) was deliberately skipped because static-tf is not green.

## Progress

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1    | Flip call_module_type to local + commit | done | `e2a061e` |
| 2    | Push to test/static-tf-smoke and watch static-tf go green | partial — pushed; static-tf failed on a new step (tfsec) | (push only — no commit) |
| 3    | Update 03-UAT.md to reflect Test 2 green | SKIPPED — precondition (static-tf green) not met | — |

## Task 1: Flip + commit (DONE)

**Edit:** `infra/.tflint.hcl` line 15 changed from `  call_module_type = "all"` to `  call_module_type = "local"`. No other lines touched (config block, plugin blocks, three terraform_required_* rules all unchanged).

**Optional local smoke:** attempted but skipped without warning — `tflint` IS on PATH locally but the azurerm plugin is not initialized in the per-subdir cache (each subdir would need `tflint --init`). Per the plan: "Failure of this optional smoke is NOT a blocker." CI was the authoritative check.

**Commit:** `e2a061e` — message exactly `fix(infra): tflint call_module_type local to skip registry AVMs` (single-line, no body, no co-author trailer per user's exact spec).

**Stat:** `1 file changed, 1 insertion(+), 1 deletion(-)`. Only `infra/.tflint.hcl` in the commit.

## Task 2: Push + watch CI (PARTIAL — fix landed, new failure surfaced)

**Push:** `git push origin test/static-tf-smoke` — fast-forward `ff0697c..e2a061e`.

**Watch:** `gh pr checks 4 --watch` ran ~17s before static-tf concluded.

### Step-by-step result on run [25366641088](https://github.com/AdrianZaplata/job-rag/actions/runs/25366641088)

| # | Step | Conclusion | Notes |
|---|------|-----------|-------|
| 1 | Set up job | success | |
| 2 | Build aquasecurity/tfsec-action@v1.0.3 | success | |
| 3 | Run actions/checkout@v4 | success | |
| 4 | Run hashicorp/setup-terraform@v3 | success | |
| 5 | Terraform fmt | success | (held from prior commit `ff0697c`) |
| 6 | Setup tflint | success | |
| 7 | Init tflint | success | |
| 8 | **Run tflint** | **success** | **THIS PLAN'S FIX WORKED** — `call_module_type=local` skipped registry AVMs cleanly. |
| 9 | **Setup tfsec** | **FAILURE** | NEW tfsec finding (see below). |
| 10 | Terraform validate (envs/prod) | skipped | (depends on tfsec) |
| 11 | Terraform validate (envs/dev) | skipped | |
| 12 | Terraform validate (bootstrap) | skipped | |
| 24 | Post Run actions/checkout@v4 | success | |
| 25 | Complete job | success | |

### Why the failure is new and out of scope

The previous run (25366227087) died at step 8 (`Run tflint`) with the AVM `call_module_type=all` issue. With that gate fixed, the workflow advanced one step further and hit a tfsec finding that has *always* been latent in the bootstrap code but was masked by the earlier failure. This is exactly the failure mode described in `<scope_boundary>` rule 3 — "static-tf itself fails again (any sub-step: ... tfsec ...)" — and rule 4 — "a genuinely NEW failure appears in a previously-passing check." Both clauses say: capture and STOP, do NOT push a second fix.

### tfsec failure — first 30-ish lines of the finding

```
Result #1  CRITICAL  Storage account uses an insecure TLS version.
────────────────────────────────────────────────────────────────────────────────
  bootstrap/main.tf:52-81
────────────────────────────────────────────────────────────────────────────────
   52  ┌ resource "azurerm_storage_account" "tfstate" {
   53  │   name                     = "jobragtfstate${random_string.suffix.result}"
   54  │   resource_group_name      = azurerm_resource_group.tfstate.name
   55  │   location                 = azurerm_resource_group.tfstate.location
   56  │   account_tier             = "Standard"
   57  │   account_replication_type = "LRS"
   58  │
   59  │   # Versioning + 7-day soft delete protect against state corruption / accidental deletion
   60  └   blob_properties {
   ..
────────────────────────────────────────────────────────────────────────────────
          ID  azure-storage-use-secure-tls-policy
      Impact  The TLS version being outdated and has known vulnerabilities
  Resolution Use a more recent TLS/SSL policy for the load balancer
  More Information
  - https://aquasecurity.github.io/tfsec/v1.28.14/checks/azure/storage/use-secure-tls-policy/
  - https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account#min_tls_version

  counts:
    modules processed: 1
    blocks processed:  20
    files read:        3
  results:
    passed:   2
    critical: 1
    high:     0
    medium:   0
    low:      0

  2 passed, 1 potential problem(s) detected.
```

### Recommended follow-up (not done in this plan)

The fix is well-scoped and one line — add `min_tls_version = "TLS1_2"` to `azurerm_storage_account.tfstate` in `infra/bootstrap/main.tf` (recommended: actually pin to `"TLS1_2"`; AzureRM provider 4.x defaults the property to `"TLS1_2"` but tfsec wants it explicit). That belongs in a separate quick task (e.g., `260505-tlspol`) or a one-line follow-up to Plan 03-02 (Bootstrap), since it touches Plan 02's bootstrap module. NOT done here per scope.

## Task 3: UAT update (SKIPPED)

**Precondition not met.** Plan Task 3 explicitly says: "Only run this task if Task 2 confirmed `static-tf` is green. If Task 2 stopped per scope_boundary rule 3 or 4, skip this task and exit with the captured log."

`.planning/phases/03-infrastructure-ci-cd/03-UAT.md` therefore remains in its current state (Test 2 still `result: issue`, but the underlying *gap entry* description is now partially out of date — the tflint sub-issue listed in the gap is fixed; the gap should be rewritten when the tfsec follow-up lands and static-tf finally goes all-green). No commit, no push made for UAT.

The `03-UAT.md` file is currently **untracked** in the working tree per the executor's start state — it remains untracked. The orchestrator-level docs commit can address whether to track it now (with the new gap status) or wait until the follow-up tlspol task closes the loop.

## Out-of-scope check states

Per scope_boundary, the following were not touched and remain untouched:
- `src/job_rag/config.py` (pre-existing ruff failure in `lint-and-test` — out of scope)
- `src/job_rag/services/ingestion.py` (pre-existing ruff failure in `lint-and-test` — out of scope)
- `infra/envs/prod/prod.tfvars` (already fixed in `ff0697c`)
- `infra/bootstrap/main.tf` (NEW tfsec finding — not in scope of this plan; recommended follow-up above)

The `lint-and-test` workflow on this run also failed (47s, the pre-existing ruff issues). Per env note + scope_boundary rule 2, this is documented but not addressed.

## Must-haves status (from PLAN.md frontmatter)

| Truth | Status | Notes |
|------|--------|-------|
| `call_module_type` in infra/.tflint.hcl is `local` | ✓ MET | line 15 verified |
| Commit `fix(infra): tflint call_module_type local to skip registry AVMs` exists on `test/static-tf-smoke` | ✓ MET | `e2a061e`, pushed |
| static-tf workflow on PR #4 goes green end-to-end (fmt + tflint + tfsec + per-env validate all pass) | ✗ NOT MET | tflint passes; tfsec fails on a NEW unrelated finding |
| 03-UAT.md Test 2 reflects the green CI run | ✗ NOT MET | UAT update gated on green static-tf |

DEPL-01 cannot be marked complete on this plan — truth #3 unmet.

## Deviations from Plan

None — the plan was executed exactly as written. Task 3 was skipped per the plan's own explicit precondition language; that is not a deviation, it's the plan's stop condition firing as designed.

## Self-Check: PASSED

- File `infra/.tflint.hcl` line 15 reads `  call_module_type = "local"` — VERIFIED via grep
- Commit `e2a061e` exists on local + remote `test/static-tf-smoke` — VERIFIED via `git log` + `gh run view headSha`
- Run `25366641088` on `e2a061e`, conclusion `failure`, failing step `Setup tfsec` — VERIFIED via `gh run list --json` + `gh run view --json jobs`
- `03-UAT.md` not edited (per Task 3 precondition) — VERIFIED: file still untracked in working tree, no edits made
- No other files in the Task 1 commit (`git show --stat HEAD~0` shows only `infra/.tflint.hcl`) — VERIFIED
