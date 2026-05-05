---
phase: quick-260505-eup
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/.tflint.hcl
  - .planning/phases/03-infrastructure-ci-cd/03-UAT.md
autonomous: true
requirements: [DEPL-01]
must_haves:
  truths:
    - "`call_module_type` in infra/.tflint.hcl is set to `local` (not `all`)"
    - "Commit `fix(infra): tflint call_module_type local to skip registry AVMs` exists on branch test/static-tf-smoke"
    - "static-tf workflow on PR #4 goes green end-to-end (fmt + tflint + tfsec + per-env validate all pass)"
    - "03-UAT.md Test 2 reflects the green CI run (result: pass; reported/severity removed; gap closed)"
  artifacts:
    - path: "infra/.tflint.hcl"
      provides: "tflint config with call_module_type = local — lints our wrapper code that calls AVM modules without descending into registry AVM internals"
      contains: 'call_module_type = "local"'
    - path: ".planning/phases/03-infrastructure-ci-cd/03-UAT.md"
      provides: "UAT log updated to reflect Test 2 passing post-fix"
      contains: "passed: 2"
  key_links:
    - from: "infra/.tflint.hcl"
      to: ".github/workflows/static-tf.yml"
      via: "tflint --recursive invocation in workflow consumes this config"
      pattern: 'call_module_type\s*=\s*"local"'
---

<objective>
Fix the static-tf CI gate failure on PR #4 by changing `call_module_type = "all"` → `"local"` in `infra/.tflint.hcl`. With `all`, tflint follows into Azure AVM wrappers (Azure/avm-res-keyvault-vault/azurerm, avm-res-operationalinsights-workspace/azurerm, avm-res-dbforpostgresql-flexibleserver/azurerm); the static-tf workflow never runs `terraform init`, so AVM modules aren't on disk, and tflint exits 1 per directory (modules/kv, modules/monitoring, modules/database, envs/dev, envs/prod) with the message suppressed by `--recursive` mode. Switching to `local` keeps lint coverage on our infra/modules/* wrapper code (which contains AVM CALLS — we lint our code, not AVM internals) and skips the version-pinned registry AVMs that are outside our control.

Purpose: Unblock PR #4 / branch `test/static-tf-smoke` so the static-TF gate goes green and Phase 3 progress on UAT can resume. This is the second issue surfaced by Test 2 in 03-UAT.md (first was `terraform fmt` on prod.tfvars, fixed in ff0697c).

Output: One-line edit in `infra/.tflint.hcl` + commit + push + post-CI-green update to `.planning/phases/03-infrastructure-ci-cd/03-UAT.md`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md
@infra/.tflint.hcl
@.planning/phases/03-infrastructure-ci-cd/03-UAT.md

<scope_boundary>
DO NOT touch:
- `src/job_rag/config.py` and `src/job_rag/services/ingestion.py` (pre-existing ruff failures surfaced by other CI jobs — out of scope for this quick task)
- `infra/envs/prod/prod.tfvars` (already fixed in ff0697c)

DO NOT iterate on new failures. After push:
- Run `gh pr checks --watch` exactly once.
- If `static-tf` goes green: proceed to Task 3 (UAT update).
- If a NEW failure appears beyond static-tf (e.g., a different job fails in a way unrelated to tflint): capture the failing job name + first ~20 lines of its log, STOP, and report back. Do NOT attempt a second fix in this plan.
</scope_boundary>

<failing_run_reference>
Failing CI run that motivated this fix: https://github.com/AdrianZaplata/job-rag/actions/runs/25366227087
Branch: `test/static-tf-smoke` (PR #4)
Failure mode: each per-directory `tflint` invocation in `--recursive` mode exits 1 because `call_module_type = "all"` tries to follow registry AVM module sources that aren't on disk (no `terraform init` in workflow).
</failing_run_reference>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Flip call_module_type to local + commit</name>
  <files>infra/.tflint.hcl</files>
  <action>
Single-line edit on line 15 of `infra/.tflint.hcl`:
- Before: `  call_module_type = "all"`
- After:  `  call_module_type = "local"`

Leave every other line of the file untouched (the surrounding `config { format = "compact" }` block, the `plugin "terraform"` and `plugin "azurerm"` blocks, and the three explicit `terraform_required_*` rules all stay verbatim).

After the edit, stage ONLY `infra/.tflint.hcl` and commit with:

```
git add infra/.tflint.hcl
git commit -m "fix(infra): tflint call_module_type local to skip registry AVMs"
```

Use the exact commit message above (no trailers, no body) — this is the message the user pre-specified in the task brief. Do not add a Claude co-author trailer for this commit since the user specified the exact message.

OPTIONAL local smoke (skip if `tflint` CLI is not on PATH — CI is the authoritative gate):
```
tflint --version >/dev/null 2>&1 && (cd infra && tflint --recursive --config=$(pwd)/.tflint.hcl)
```
Failure of this optional smoke is NOT a blocker — proceed to Task 2 regardless.
  </action>
  <verify>
    <automated>grep -E '^\s*call_module_type\s*=\s*"local"\s*$' infra/.tflint.hcl &amp;&amp; git log -1 --pretty=%s | grep -qx "fix(infra): tflint call_module_type local to skip registry AVMs"</automated>
  </verify>
  <done>
- `infra/.tflint.hcl` line 15 reads `  call_module_type = "local"`.
- `git log -1 --pretty=%s` returns exactly `fix(infra): tflint call_module_type local to skip registry AVMs`.
- No other files changed in the commit (`git show --stat HEAD` lists only `infra/.tflint.hcl`).
  </done>
</task>

<task type="auto">
  <name>Task 2: Push to test/static-tf-smoke and watch static-tf go green</name>
  <files>(no file edits — push + CI watch)</files>
  <action>
Push the new commit to the existing remote branch backing PR #4:

```
git push origin test/static-tf-smoke
```

Then watch PR checks ONCE:

```
gh pr checks --watch
```

Interpretation rules (apply strictly — see `<scope_boundary>`):

1. **All checks pass (or only static-tf-relevant checks pass and the rest are unrelated/expected-failing):** Proceed to Task 3.

2. **`static-tf` goes green BUT another check (e.g., a Python lint job, ruff, pyright) fails:** This is the pre-existing, out-of-scope failure mode that the user flagged (`src/job_rag/config.py` + `src/job_rag/services/ingestion.py` ruff failures). Treat static-tf as green for this plan's purpose and proceed to Task 3, but in the SUMMARY note which non-static-tf check is still red so the user has visibility.

3. **`static-tf` itself fails again (any sub-step: fmt / tflint / tfsec / validate-dev / validate-prod):** Capture the failing job name and the first ~20 lines of its log (use `gh run view <run-id> --log-failed | head -80` or `gh pr checks` output). STOP. Do NOT push a second fix from this plan. Report back with the captured log so the user can decide next steps.

4. **A genuinely NEW failure appears in a previously-passing check, unrelated to tflint:** Same as case 3 — capture, STOP, report.

Capture the run URL of the static-tf run for this push (e.g., `gh run list --workflow=static-tf.yml --branch=test/static-tf-smoke --limit=1 --json databaseId,url,conclusion`). It will be referenced in Task 3.
  </action>
  <verify>
    <automated>gh run list --workflow=static-tf.yml --branch=test/static-tf-smoke --limit=1 --json conclusion --jq '.[0].conclusion' | grep -qx "success"</automated>
  </verify>
  <done>
- Commit pushed to `test/static-tf-smoke`.
- Latest static-tf workflow run on that branch has `conclusion: success`.
- If any non-static-tf check is still red, that's noted in the SUMMARY (does not block this plan's completion per scope_boundary rule 2).
- The static-tf run URL is captured for Task 3.
  </done>
</task>

<task type="auto">
  <name>Task 3: Update 03-UAT.md to reflect Test 2 green</name>
  <files>.planning/phases/03-infrastructure-ci-cd/03-UAT.md</files>
  <action>
PRECONDITION: Only run this task if Task 2 confirmed `static-tf` is green. If Task 2 stopped per scope_boundary rule 3 or 4, skip this task and exit with the captured log.

Edit `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` with three precise changes:

**Change 1 — Test 2 block (currently lines ~29-34):**

Before:
```
### 2. Static-TF Validation Harness (Plan 01)
expected: Open a PR that touches any file under `infra/**`. The `.github/workflows/static-tf.yml` workflow runs and goes green: `terraform fmt -check`, `tflint` (azurerm ruleset), `tfsec` (with documented D-10/A1 allowlist), and per-env `terraform validate` all pass. With Wave 0 empty .tf files, file-existence guards keep validate green; once Plans 02–06 land .tf files, validate exercises real HCL.
result: issue
reported: "static-tf workflow failed in 11s — `terraform fmt -check -recursive infra/` flagged `infra/envs/prod/prod.tfvars` as unformatted; exit code 3 (PR #4, run 25365496050)"
severity: major
```

After:
```
### 2. Static-TF Validation Harness (Plan 01)
expected: Open a PR that touches any file under `infra/**`. The `.github/workflows/static-tf.yml` workflow runs and goes green: `terraform fmt -check`, `tflint` (azurerm ruleset), `tfsec` (with documented D-10/A1 allowlist), and per-env `terraform validate` all pass. With Wave 0 empty .tf files, file-existence guards keep validate green; once Plans 02–06 land .tf files, validate exercises real HCL.
result: pass
```

(Remove the `reported:` and `severity:` lines entirely. Keep the trailing blank line before `### 3.`.)

**Change 2 — Summary block (currently lines ~99-106):**

Before:
```
total: 18
passed: 1
issues: 1
pending: 16
skipped: 0
blocked: 0
```

After:
```
total: 18
passed: 2
issues: 0
pending: 16
skipped: 0
blocked: 0
```

(Only `passed` and `issues` change. `total`, `pending`, `skipped`, `blocked` stay identical.)

**Change 3 — Gaps section (currently lines ~108-120):**

Before:
```
## Gaps

- truth: "static-tf.yml workflow goes green on any PR touching infra/**"
  status: failed
  reason: "User reported: static-tf workflow failed in 11s — `terraform fmt -check -recursive infra/` flagged `infra/envs/prod/prod.tfvars` as unformatted; exit code 3 (PR #4, run 25365496050). Fmt fixed in commit ff0697c. Re-run 25366227087 then failed at the next step `Run tflint`: each per-directory invocation (modules/kv, modules/monitoring, modules/database, envs/dev, envs/prod) exits 1, message suppressed by --recursive mode."
  severity: major
  test: 2
  artifacts:
    - path: "infra/.tflint.hcl"
      issue: "`call_module_type = \"all\"` makes tflint follow into registry AVM modules that aren't downloaded — each sub-dir invocation fails because the module source isn't on disk"
  missing:
    - "Change `call_module_type = \"all\"` → `\"local\"` in infra/.tflint.hcl so tflint only lints our own local modules and skips registry AVMs"
```

After (Test 2's gap was the only entry, so replace the body with the placeholder per the plan brief):
```
## Gaps

[none yet]
```

Also bump the `updated:` timestamp in frontmatter to the current UTC time of execution (e.g., `updated: 2026-05-05T<HH:MM>:00Z` — pick the actual hour:minute when this task runs). Do NOT change `started:`, `status:`, `phase:`, `source:`.

After edits, stage ONLY `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` and commit:

```
git add .planning/phases/03-infrastructure-ci-cd/03-UAT.md
git commit -m "$(cat <<'EOF'
docs(03): mark UAT Test 2 (static-TF) pass after tflint AVM fix

Static-TF workflow on PR #4 goes green after `call_module_type` flip from
`all` → `local` (commit on test/static-tf-smoke). Closes the only outstanding
03-UAT.md gap; passed 1→2, issues 1→0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Push the UAT commit to whichever branch the workflow has the user on (most likely also `test/static-tf-smoke` if the user is keeping fix + UAT bookkeeping together — verify with `git rev-parse --abbrev-ref HEAD` first; if the active branch differs, push to that branch). Use `git push origin HEAD`.
  </action>
  <verify>
    <automated>grep -A1 '^### 2\. Static-TF' .planning/phases/03-infrastructure-ci-cd/03-UAT.md | grep -q "result: pass" &amp;&amp; ! grep -q '^reported:' .planning/phases/03-infrastructure-ci-cd/03-UAT.md &amp;&amp; grep -q '^passed: 2$' .planning/phases/03-infrastructure-ci-cd/03-UAT.md &amp;&amp; grep -q '^issues: 0$' .planning/phases/03-infrastructure-ci-cd/03-UAT.md &amp;&amp; grep -q '^\[none yet\]$' .planning/phases/03-infrastructure-ci-cd/03-UAT.md</automated>
  </verify>
  <done>
- Test 2 block: `result: pass`, with `reported:` and `severity:` lines removed.
- Summary: `passed: 2`, `issues: 0`, others (`total: 18`, `pending: 16`, `skipped: 0`, `blocked: 0`) unchanged.
- Gaps section body is `[none yet]` (because Test 2 was the only entry).
- Frontmatter `updated:` timestamp bumped to today.
- Commit `docs(03): mark UAT Test 2 (static-TF) pass after tflint AVM fix` exists.
- Commit pushed to remote.
  </done>
</task>

</tasks>

<verification>
End-to-end smoke (run after Task 3 completes):

1. `git log --oneline -5` shows two new commits:
   - `fix(infra): tflint call_module_type local to skip registry AVMs`
   - `docs(03): mark UAT Test 2 (static-TF) pass after tflint AVM fix`

2. `gh run list --workflow=static-tf.yml --branch=test/static-tf-smoke --limit=1` shows the latest run with `conclusion: success`.

3. `grep '^passed:' .planning/phases/03-infrastructure-ci-cd/03-UAT.md` returns `passed: 2`.

4. `grep -c '^reported:' .planning/phases/03-infrastructure-ci-cd/03-UAT.md` returns `0`.

5. `grep -A2 '^## Gaps' .planning/phases/03-infrastructure-ci-cd/03-UAT.md` shows `[none yet]` as the only non-blank content under that header.
</verification>

<success_criteria>
- `infra/.tflint.hcl` line 15 reads `  call_module_type = "local"`.
- Static-TF workflow run on `test/static-tf-smoke` (post-push) has `conclusion: success`.
- 03-UAT.md frontmatter `updated:` is today; Test 2 is `result: pass`; Summary `passed: 2 / issues: 0`; Gaps body is `[none yet]`.
- Two commits exist on the active branch with the exact messages specified in Tasks 1 and 3.
- No edits made to `src/job_rag/config.py`, `src/job_rag/services/ingestion.py`, or `infra/envs/prod/prod.tfvars` (verified via `git show --stat HEAD~1 HEAD`).
- If a NEW non-static-tf CI failure surfaced, it is reported in the SUMMARY.md without further iteration (per scope_boundary rule 2/3/4).
</success_criteria>

<output>
After completion, create `.planning/quick/260505-eup-tflint-call-module-type-local-for-avm-mo/260505-eup-SUMMARY.md` summarizing:
- The two commits (SHAs + messages).
- Static-TF run URL with `conclusion: success`.
- 03-UAT.md before/after summary deltas (`passed 1→2`, `issues 1→0`).
- Any non-static-tf check that's still red (per scope_boundary rule 2), noted as out-of-scope follow-up.
</output>
