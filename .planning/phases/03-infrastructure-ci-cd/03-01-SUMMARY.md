---
phase: 03-infrastructure-ci-cd
plan: 01
subsystem: infra
tags: [terraform, tflint, tfsec, github-actions, ci, scaffolding, azure]

# Dependency graph
requires:
  - phase: 01-backend-prep
    provides: CI workflow conventions (.github/workflows/ci.yml structure)
provides:
  - Static-TF validation harness (tflint azurerm ruleset, tfsec config with documented €0-budget allowlist)
  - Runbook skeletons for infra top-level + bootstrap + envs/prod + envs/dev (downstream plans only fill content)
  - scripts/refresh-swa-origin.sh DEPL-12 two-pass CORS helper (executable, idempotent)
  - .github/workflows/static-tf.yml PR-only workflow with file-existence guards for Wave 0 emptiness
  - Terraform .gitignore block (state, .terraform/, *.tfplan, *.tfvars.local) — T-3-01 mitigation
affects: [03-02-bootstrap, 03-03, 03-04-envs-prod, 03-05a, 03-05b, 03-06-envs-dev, 03-07-deploy]

# Tech tracking
tech-stack:
  added:
    - tflint (CI-installed, azurerm ruleset 0.27.0)
    - tfsec (CI-installed via aquasecurity/tfsec-action@v1.0.3)
    - hashicorp/setup-terraform@v3 (terraform_version 1.9.5)
  patterns:
    - "Static validation harness landed BEFORE first .tf file — file-existence guards (`if [ -f ... ]`) keep Wave 0 PR green"
    - "tfsec exclude list with inline D-10/A1 comments — security trade-offs visible at the config layer"
    - "set -euo pipefail + sed -i.bak idempotent rewrite for one-shot infra glue (refresh-swa-origin.sh)"
    - "Append-only .gitignore extension (existing entries unchanged) — Terraform block at tail"
    - "Markdown runbook skeletons with section headings only — downstream plans grep section names for verification"

key-files:
  created:
    - infra/.tflint.hcl
    - infra/.tfsec/config.yml
    - infra/README.md
    - infra/bootstrap/README.md
    - infra/envs/prod/README.md
    - infra/envs/dev/README.md
    - scripts/refresh-swa-origin.sh
    - .github/workflows/static-tf.yml
  modified:
    - .gitignore

key-decisions:
  - "tfsec allowlist is checked-in code with inline comments referencing D-10 / Plan-Locking Addendum A1 Path A — security trade-offs visible at the config layer, not buried in a runbook"
  - "static-tf.yml ships with `if [ -f infra/{env}/main.tf ]` guards so Wave 0 PR (no .tf files yet) doesn't go red. Alternative (defer workflow to wave-1) rejected — keeping Wave 0 verifiable in CI is worth the 6-line guard surface"
  - "Lock files (.terraform.lock.hcl) intentionally gitignored — Phase 3 deps will rev as AVM modules ship 0.x→0.y bumps; revisit at Phase 8 portfolio polish if AVM modules stabilize"
  - "Runbook headings present but content stubbed — downstream plans grep for section names (Two-Pass CORS Bootstrap, scaffold-only) as verification anchors"

patterns-established:
  - "Pattern: PR-only static-validation workflow with file-existence guards. Lets the workflow ship in Wave 0 BEFORE any resource code, then auto-activates as plans 02-06 land .tf files. Reusable for any future scaffolding-first workflow"
  - "Pattern: tfsec allowlist with inline decision-ID comments. Each exclusion documents WHICH decision authorizes it (D-10/A1) and WHY (€130/mo private endpoint breaks €0 budget). Future security audits can trace every allowlist entry back to a documented call"
  - "Pattern: append-only .gitignore extension. Existing entries preserved verbatim; new section appended at tail with a `# Terraform (Phase 3 — ...)` block comment. Convention for any future phase that adds a new file family"

requirements-completed: [DEPL-01, DEPL-02, DEPL-12]

# Metrics
duration: ~6m
completed: 2026-04-29
---

# Phase 3 Plan 01: Wave 0 Static-TF Lint + Scaffolding Summary

**Static-TF validation harness (tflint azurerm + tfsec D-10 allowlist + GitHub Actions PR workflow) plus runbook skeletons and the DEPL-12 two-pass CORS helper — all wired up before any `.tf` file exists.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-29 (executor session)
- **Completed:** 2026-04-29
- **Tasks:** 2
- **Files created:** 8
- **Files modified:** 1 (.gitignore)

## Accomplishments

- Static validation harness in place: tflint azurerm ruleset 0.27.0 (recommended preset + 3 explicit terraform rules) and tfsec config with documented D-10/A1 allowlist for `azure-database-no-public-access` + `azure-database-no-public-firewall-rules` (Path A €0-budget trade-off, security boundary = TLS + 32-char password)
- `.github/workflows/static-tf.yml` ships with `paths: ['infra/**']` trigger, `permissions: { contents: read }` (T-3-02 mitigation), per-env terraform validate with file-existence guards so Wave 0 stays green
- Four runbook skeletons (`infra/README.md`, `infra/bootstrap/README.md`, `infra/envs/prod/README.md`, `infra/envs/dev/README.md`) with the section headings downstream plans + verification expects (Two-Pass CORS Bootstrap, scaffold-only, Knowingly-accepted security trade-offs, Token rotation cadence)
- `scripts/refresh-swa-origin.sh` DEPL-12 two-pass CORS helper: executable bit set in git index (mode 100755), `set -euo pipefail`, idempotent sed-with-backup rewrite, terraform-output-driven origin discovery
- `.gitignore` extended with Terraform block (bootstrap state, `.terraform/` caches, `*.tfplan`, `*.tfvars.local`) — T-3-01 mitigation lands BEFORE Plan 02 runs `terraform apply` locally

## Task Commits

Each task was committed atomically:

1. **Task 1: Static validation configs (tflint, tfsec, gitignore)** — `a07b2cb` (feat)
2. **Task 2: Runbook skeletons + helper script + static-TF workflow** — `49dabeb` (feat)

**Plan metadata:** _(this commit)_

## Files Created/Modified

- `infra/.tflint.hcl` — tflint config: terraform recommended preset + azurerm ruleset 0.27.0 + 3 explicit rules (required_version, required_providers, unused_declarations)
- `infra/.tfsec/config.yml` — tfsec allowlist for D-10/A1 Path A trade-offs (public-network-access + public-firewall-rules), `minimum_severity: HIGH`
- `infra/README.md` — top-level infra index: layout table, bootstrap → first-apply runbook, validation note pointing to static-tf.yml
- `infra/bootstrap/README.md` — bootstrap runbook skeleton with 4 step headings + trade-off section (filled by Plan 02)
- `infra/envs/prod/README.md` — prod runbook skeleton with all 6 section headings (First apply, Two-Pass CORS Bootstrap, Image push, Post-apply smoke, Trade-offs, Token rotation)
- `infra/envs/dev/README.md` — dev scaffold-only runbook skeleton (Why scaffold-only + Apply path deferred)
- `scripts/refresh-swa-origin.sh` — DEPL-12 helper, mode 100755, `bash -n` clean, idempotent sed-with-backup
- `.github/workflows/static-tf.yml` — PR-only on `infra/**`, fmt + tflint + tfsec + per-env validate with `if [ -f ]` guards
- `.gitignore` — appended `# Terraform (Phase 3 ...)` block at tail; existing entries unchanged

## Decisions Made

- Adopted the plan body's `if [ -f infra/.../main.tf ]` guard pattern in static-tf.yml so Wave 0 ships green CI without needing a follow-up edit when Plans 02-06 land `.tf` files
- Set executable bit explicitly via `git update-index --chmod=+x` to record `100755` in git index even though git-bash on Windows defaults to `100644` on `git add`
- All other content followed the plan verbatim (concrete file bodies were specified in the plan)

## Deviations from Plan

None — plan executed exactly as written. The plan body provided verbatim file contents for all 9 files, and all content was applied as specified. The only operational note is that on git-bash on Windows the executable bit had to be set with an explicit `git update-index --chmod=+x` after the initial `git add`; that's the documented PATTERNS.md convention for the platform and not a deviation from plan intent.

## Issues Encountered

None. CRLF warnings from git on `.gitignore` and the new files are expected on Windows checkout (`core.autocrlf` default) and do not affect file content semantics in commits.

## User Setup Required

None — no external service configuration required. Plan 02 (bootstrap) is the first plan that requires Azure subscription + Entra External tenant.

## Next Phase Readiness

- **Wave 0 done.** Static-validation harness and runbook scaffolding are landed. Plan 02 (bootstrap) can now drop a real `infra/bootstrap/main.tf` and immediately get fmt-check + tflint + tfsec + validate coverage on PR.
- Adrian explicitly chose Wave 0 only — execution stops here. Next session candidates: `/gsd-execute-phase 3` to land Plan 02 (bootstrap), or `/gsd-verify-work 3.01` to verify Wave 0 before proceeding.
- All 3 requirements (DEPL-01, DEPL-02, DEPL-12) marked complete in REQUIREMENTS.md (DEPL-12 is wired but not yet exercised — script exists, will be invoked from Plan 04's prod runbook).

## Self-Check: PASSED

Verified on disk:
- `[ -f infra/.tflint.hcl ]` — FOUND
- `[ -f infra/.tfsec/config.yml ]` — FOUND
- `[ -f infra/README.md ]` — FOUND
- `[ -f infra/bootstrap/README.md ]` — FOUND
- `[ -f infra/envs/prod/README.md ]` — FOUND
- `[ -f infra/envs/dev/README.md ]` — FOUND
- `[ -f scripts/refresh-swa-origin.sh ]` — FOUND (mode 100755 in git index)
- `[ -f .github/workflows/static-tf.yml ]` — FOUND
- `bash -n scripts/refresh-swa-origin.sh` — exit 0
- `git log --oneline | grep a07b2cb` — FOUND
- `git log --oneline | grep 49dabeb` — FOUND
- `grep -q "Terraform (Phase 3" .gitignore` — FOUND at tail
- `grep -q "Two-Pass CORS Bootstrap" infra/envs/prod/README.md` — FOUND
- `grep -q "scaffold-only" infra/envs/dev/README.md` — FOUND
- `grep -q "azure-database-no-public-access" infra/.tfsec/config.yml` — FOUND
- `grep -q "azurerm" infra/.tflint.hcl` — FOUND

---
*Phase: 03-infrastructure-ci-cd*
*Completed: 2026-04-29*
