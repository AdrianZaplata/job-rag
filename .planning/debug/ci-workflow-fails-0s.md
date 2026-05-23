---
slug: ci-workflow-fails-0s
status: resolved
trigger: ".github/workflows/ci.yml failing at 0s with 0 jobs on every push to master since 2026-05-21"
created: 2026-05-23
updated: 2026-05-23
---

# Debug Session: CI workflow fails at 0s with 0 jobs

## Symptoms

<!-- DATA_START — treat as user-supplied data, not instructions -->

**Expected behavior**
Pushes to `master` should trigger `.github/workflows/ci.yml` and execute the `lint-and-test` job: ruff + pyright + pytest with a pgvector/pg17 postgres service. Conclusion should be success (or a real test failure with logs).

**Actual behavior**
Every push for the last 6+ commits produces a CI run with:
- `conclusion: failure`
- `status: completed`
- duration: `0s`
- `gh api repos/AdrianZaplata/job-rag/actions/runs/{ID}/jobs` returns 0 jobs
- `gh run view {ID} --log` returns `"failed to get run log: log not found"`

Sibling workflows (`deploy-api.yml`, `deploy-spa.yml`) succeed on the same pushes — so this is not a repo-wide permissions/auth issue. Only CI is broken.

**Error messages**
- `failed to get run log: log not found`
- Empty `jobs: []` from runs API
- No workflow-level error surfaced in CLI; UI may show a workflow-validation error (untested yet)

**Timeline**
- First failing run appears around 2026-05-21, near the `fix(04.1-02): accept RunningAtMaxScale ...` commit (Phase 4.1 work)
- Last 6+ commits all failed identically
- Need to confirm via `gh run list --workflow=.github/workflows/ci.yml --limit 20` and find the last green run

**Reproduction**
```bash
# Any push to master reproduces:
git commit --allow-empty -m "chore: trigger CI"
git push origin master
gh run list --workflow=.github/workflows/ci.yml --limit 1
# Expected output: completed | failure | 0s | "push" | master
```

**Concrete inspection commands**
```bash
gh run list --workflow=.github/workflows/ci.yml --limit 5
gh run view 26300431990 --json conclusion,jobs       # → {conclusion: "failure", jobs: []}
gh run view 26300431990 --log                          # → "failed to get run log: log not found"
gh api repos/AdrianZaplata/job-rag/actions/runs/26300431990
```

<!-- DATA_END -->

## Investigation plan (priority order from user)

1. Check workflow in GitHub UI (`gh browse --web`) — UI often shows workflow-validation errors that CLI hides
2. Inspect `.github/workflows/ci.yml`:
   - `jobs.X.if:` evaluating to false (silent skip)
   - `concurrency:` block with `cancel-in-progress: true`
   - Missing reusable workflow reference (`uses: ./.github/workflows/...`)
   - `name:` / `on:` triggers
3. `gh workflow list` — check if workflow is disabled; if so `gh workflow enable ci.yml`
4. Diff against working siblings (`deploy-api.yml`, `deploy-spa.yml`) — compare `on:`, `permissions:`, runner image
5. `git log --diff-filter=AM -- .github/workflows/ci.yml` — find last successful commit, diff against now. If file unchanged, bug is upstream (action version drift, repo settings, branch protection)
6. `gh api repos/AdrianZaplata/job-rag/actions/permissions` — check Actions permissions changes (allowed-actions allowlist)

## Constraints

- **Scope**: Only touch `.github/workflows/ci.yml`. Do NOT modify `deploy-api.yml`, `deploy-spa.yml`, `static-tf.yml`, `bootstrap-corpus.yml`, `deploy-infra.yml`.
- **Out of scope**: The 2 pre-existing alembic env test failures (tracked in `.planning/phases/05-dashboard/deferred-items.md` as a separate DATABASE_URL issue).
- **Local tests pass**: `uv run pytest tests/` → 234 passed, 2 deferred failures.
- **Commit style**: one commit, `fix(ci): ...`. Push only after fix is verified to produce a non-empty run.

## Definition of done

- Fresh push to master produces a CI run that:
  - Executes jobs (non-zero `jobs` array from API)
  - Shows real step logs
  - Returns either `success` or a real test-failure conclusion (not the empty 0s/0jobs failure)

## Current Focus

```yaml
hypothesis: "job-level `if: hashFiles(...)` on frontend-ci job triggers workflow-validation failure"
test: "fetch /annotations_partial for a failing run and read GitHub's parser error"
expecting: "an 'Invalid workflow file' annotation pointing at line 75 col 9"
next_action: "Resolved — committed fix and verified post-push run scheduled real jobs"
reasoning_checkpoint: null
tdd_checkpoint: null
```

## Evidence

- timestamp: 2026-05-23T08:15Z
  source: `git log --diff-filter=AM -- .github/workflows/ci.yml`
  finding: Last change to ci.yml is `1f17db9 feat(04-03): add frontend-ci CI job + wire deploy-spa.yml to frontend/ + VITE_* env` on 2026-05-20. The change ADDED a new top-level job `frontend-ci` with `if: hashFiles('frontend/package.json') != ''` at the job level.

- timestamp: 2026-05-23T08:16Z
  source: `gh api repos/.../actions/workflows`
  finding: ci.yml registry name is literally `.github/workflows/ci.yml` (the path) instead of `CI`. Other workflows resolve to their `name:` field. This is a long-standing artifact from when workflow id 258429256 was first registered — not a current parse failure of `name:`.

- timestamp: 2026-05-23T08:18Z
  source: `gh run list --workflow=.github/workflows/ci.yml --limit 50`
  finding: Timeline of CI runs:
  - Last green push: `9576e4f1` 2026-05-19 13:26 (docs change)
  - First failing push: `9914744c` 2026-05-19 20:16 (docs change, NO ci.yml change)
  - But: `9914744c` actually ran the `lint-and-test` job (1m19s, exit 1 — `Process completed with exit code 1`). That was a legitimate test failure, NOT the 0s/0-jobs pattern.
  - The 0s/0-jobs pattern starts at `1ece0351` 2026-05-21 10:10, which is the first push AFTER `1f17db9` (2026-05-20 frontend-ci addition).

- timestamp: 2026-05-23T08:20Z
  source: HTML scrape of `https://github.com/AdrianZaplata/job-rag/actions/runs/26312010636/annotations_partial`
  finding: **EXACT GITHUB PARSER ERROR**:
  ```
  Invalid workflow file: .github/workflows/ci.yml#L1
  (Line: 75, Col: 9): Unrecognized function: 'hashFiles'.
  Located at position 1 within expression: hashFiles('frontend/package.json') != ''
  ```

- timestamp: 2026-05-23T08:21Z
  source: `.github/workflows/ci.yml` line 75
  finding: `    if: hashFiles('frontend/package.json') != ''` at JOB level (under `frontend-ci:`). Per GitHub Actions docs, `hashFiles()` is only available in expressions evaluated AT RUNTIME on the runner (step-level `if:`, `env:`, `with:`, `run:`), NOT in job-level `if:` which is evaluated at workflow-validation time, before any checkout has run.

- timestamp: 2026-05-23T08:22Z
  source: `gh api repos/.../actions/permissions` + `gh api repos/.../branches/master/protection`
  finding: Actions = `enabled, allowed_actions=all`. Default workflow permissions = `read`. Branch is NOT protected. Eliminates repo-settings hypothesis.

- timestamp: 2026-05-23T08:25Z
  source: post-fix push `f71fc14` + `gh api .../runs/26325683407/jobs`
  finding: New CI run is `in_progress` (not 0s/completed); workflow name shows as `CI` in `gh run list` (not the path fallback); jobs API returns 3 real jobs:
  - `detect-frontend` → completed, conclusion=success (output `present=true`)
  - `lint-and-test` → in_progress
  - `frontend-ci` → in_progress (gating on `needs.detect-frontend.outputs.present == 'true'` resolved correctly)
  Workflow validation succeeded; bug pattern broken.

## Eliminated

- Workflow disabled (state=active in gh workflow list)
- YAML parse error (file parses with pyyaml; bytes are clean UTF-8 LF, no BOM/NBSP)
- Reference to non-existent reusable workflow (no `uses: ./...` in ci.yml)
- Branch protection / required-status-check loop (branch unprotected)
- Action version drift (actions/checkout@v4, astral-sh/setup-uv@v4, actions/setup-node@v4 all still resolve; sibling workflows use checkout@v4 successfully)
- Repo Actions permissions allowlist (allowed_actions=all)
- Runner image rollout (sibling workflows succeed on same runner image)
- Org policy change (single-user repo, no org overrides)

## Resolution

```yaml
root_cause: |
  GitHub Actions workflow validation rejected ci.yml because the frontend-ci
  job declared `if: hashFiles('frontend/package.json') != ''` at the JOB
  level. hashFiles() is a runtime function and is unavailable in the
  workflow-validation-time context where job-level `if:` is evaluated. The
  parser returned "Unrecognized function: 'hashFiles'" and refused to
  schedule ANY jobs in the workflow, producing the 0s/0-jobs/no-logs
  pattern. Regression introduced in 1f17db9 (feat 04-03 frontend-ci job).
fix: |
  Replaced the forbidden job-level `if: hashFiles(...)` with a two-job
  gating pattern:
    1. New `detect-frontend` job: checks out the repo, runs `test -f
       frontend/package.json`, writes `present=true|false` to GITHUB_OUTPUT.
    2. `frontend-ci` now declares `needs: detect-frontend` and uses
       `if: needs.detect-frontend.outputs.present == 'true'`. Job-level
       `if:` accepts `needs.*.outputs.*` because those values exist by the
       time the dependent job is scheduled.
  This is GitHub's documented workaround and preserves the original intent
  (skip frontend-ci cleanly on pre-Plan-04 branches where frontend/ doesn't
  exist).
verification: |
  Post-push run 26325683407 (commit f71fc14) scheduled all three jobs:
    - detect-frontend completed success (present=true)
    - lint-and-test entered in_progress (real execution, not 0s)
    - frontend-ci entered in_progress (gate resolved correctly)
  Workflow name shows as `CI` in gh run list (no longer the path fallback,
  confirming GitHub parsed the file). Annotations_partial returns nothing
  for this run (no validation errors). Bug pattern is broken.
files_changed:
  - .github/workflows/ci.yml
commit: f71fc14
```
