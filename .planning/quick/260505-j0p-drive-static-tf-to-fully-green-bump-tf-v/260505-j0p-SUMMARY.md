---
quick_id: 260505-j0p
slug: drive-static-tf-to-fully-green-bump-tf-v
description: Drive static-tf to fully green — bump TF version + sweep fmt/tflint/tfsec/validate
date: 2026-05-05
status: complete
outcome: static_tf_fully_green
fix_commit: b709eed
ci_run_green: 25374378624
---

# Quick Task 260505-j0p — Summary

## Stated goal

Drive `static-tf` CI to fully green on PR #4 by bumping the CI Terraform pin
to support AVM 0.2.2's `ephemeral` requirement, then sweeping fmt / tflint /
tfsec / validate locally and fixing every finding atomically.

## Result

✅ **`static-tf` workflow is fully green on PR #4 (run 25374378624).** All 8
steps pass:

| # | Step | Result |
|---|---|---|
| 1 | Setup tfsec (build) | ✓ |
| 2 | actions/checkout@v4 | ✓ |
| 3 | hashicorp/setup-terraform@v3 (1.15.0) | ✓ |
| 4 | Terraform fmt | ✓ |
| 5 | Setup tflint | ✓ |
| 6 | Init tflint | ✓ |
| 7 | Run tflint | ✓ |
| 8 | Setup tfsec | ✓ |
| 9 | Terraform validate (envs/prod) | ✓ |
| 10 | Terraform validate (envs/dev) | ✓ |
| 11 | Terraform validate (bootstrap) | ✓ |

Total runtime: 37s.

## What changed

Single commit on `test/static-tf-smoke`:

- **`b709eed`** `chore(ci): bump terraform_version to 1.15.0` — `.github/workflows/static-tf.yml`,
  `terraform_version: 1.9.5` → `terraform_version: 1.15.0`. This was the only
  fix the sweep required; the AVM `ephemeral` blocker dissolved as soon as CI
  ran on Terraform ≥ 1.10.

Push also carried two local-only commits from prior quick tasks:
- `a2cf2f5` `docs(quick-260505-h1p): tfsec fix landed; new validate(envs/prod) blocker captured`
- (and `a387143` from `260505-eup` had already been pushed in 260505-h1p's session)

## Local sweep — all gates clean (with terraform 1.15.0 + tflint 0.62.0)

| Gate | Command | Result |
|---|---|---|
| **fmt** | `terraform -chdir=infra fmt -check -recursive .` | exit 0 — no drift |
| **validate (bootstrap)** | `terraform init -backend=false && terraform validate` | Success (only pre-existing `resource_manager_id` deprecation warnings on `azurerm_storage_container.tfstate` — non-blocking) |
| **validate (envs/prod)** | same | Success (only deprecation warnings originating in vendored AVM module `monitoring.log_analytics`'s `local_authentication_disabled` — non-blocking) |
| **validate (envs/dev)** | same | Success (same vendored-AVM deprecation warning) |
| **tflint** | `tflint --init && tflint --recursive --config="$(pwd)/.tflint.hcl"` | exit 0 — no findings |
| **tfsec** | not installed locally | deferred to CI — passed |

No fmt drift, validate errors, tflint findings, or tfsec findings emerged. The
TF version bump alone unblocked everything: the prior validate failure was a
classic minimum-version mismatch between vendored AVM module syntax and the CI
runner's Terraform pin.

## UAT promoted

`.planning/phases/03-infrastructure-ci-cd/03-UAT.md` updated:

- **Test 2 (Static-TF Validation Harness)**: `result: issue` → `result: pass`;
  removed `reported` and `severity` fields.
- **Summary counts**: `passed: 1 → 2`, `issues: 1 → 0` (`pending: 16` unchanged).
- **Gaps section**: removed the Test 2 entry; section body now `[none yet]`.
- Frontmatter `updated:` bumped to `2026-05-05T11:50:00Z`.

## Why a single one-line fix worked

Each prior CI failure on this branch was a fix-this-then-the-next-thing-surfaces
chain. The `260505-h1p` summary correctly diagnosed the AVM `ephemeral` issue
as a Terraform version pin problem, but stopped at "capture and report" per
its scope. This task did the simplest possible follow-up — bump the pin —
and that turned out to be the last item in the chain. fmt, tflint, validate
(prod/dev/bootstrap), and tfsec all came up clean with no further fixes.

## PAUSE conditions — none triggered

No tfsec findings touched documented design decisions; no validate failure
suggested a wrong resource shape; no rule needed relaxing; no findings
appeared outside `infra/` or `.github/workflows/static-tf.yml`.

## Out of scope (untouched, as instructed)

- `src/job_rag/config.py`, `src/job_rag/services/ingestion.py` ruff failures
  (pre-existing `lint-and-test` failures).

## Links

- PR #4: https://github.com/AdrianZaplata/job-rag/pull/4
- Failing run before fix: https://github.com/AdrianZaplata/job-rag/actions/runs/25370681564
- Green run after fix: https://github.com/AdrianZaplata/job-rag/actions/runs/25374378624
- Fix commit: b709eed
