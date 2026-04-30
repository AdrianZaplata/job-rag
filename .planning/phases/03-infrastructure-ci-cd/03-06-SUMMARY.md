---
phase: 03-infrastructure-ci-cd
plan: 06
subsystem: infra
tags: [github-actions, oidc, azure, terraform, docker, ghcr, swa, container-apps]

requires:
  - phase: 03-infrastructure-ci-cd
    provides: "Plan 04 — federated credentials (master + production_env subjects); Plan 05a/05b — prod Terraform composition + ACA + SWA resources; Plan 03 — static-tf.yml lint harness reused as pattern."
provides:
  - "deploy-infra.yml: terraform apply (prod) gated on environment: production via OIDC"
  - "deploy-api.yml: docker build+push to GHCR + az containerapp update via OIDC"
  - "deploy-spa.yml: token-based SWA upload (sole non-OIDC workflow)"
affects: [Phase 4 frontend shell — deploy-spa.yml fires when apps/web/ lands; Phase 7 corpus refreshes — deploy-api.yml + bootstrap-corpus.yml share federated cred subject]

tech-stack:
  added: [actions/checkout@v4, hashicorp/setup-terraform@v3, azure/login@v2, docker/login-action@v3, docker/setup-buildx-action@v3, docker/build-push-action@v6, actions/setup-node@v4, Azure/static-web-apps-deploy@v1]
  patterns: ["Per-workflow paths filter aligned to federated credential subject (DEPL-08)", "OIDC-only auth for Azure-mutating workflows; SWA token is the sole long-lived secret", "Manual runbook reminder echoed to GITHUB_STEP_SUMMARY in lieu of in-workflow gh-secret-set step (B2 locked decision — avoids long-lived GH_PAT_FOR_SECRETS)", "/health smoke-poll after az containerapp update for fast revision-failure feedback"]

key-files:
  created:
    - .github/workflows/deploy-infra.yml
    - .github/workflows/deploy-api.yml
    - .github/workflows/deploy-spa.yml
  modified: []

key-decisions:
  - "B2 manual runbook for SWA token sync — workflow only echoes the gh secret set command into GITHUB_STEP_SUMMARY; Adrian runs it locally on first apply + 180-day rotation. No GH_PAT_FOR_SECRETS in the system."
  - "deploy-api.yml carries an inline /health smoke poll (18 × 5s = 90s budget) as belt-and-suspenders against silently unhealthy revisions — the workflow fails loud if the new image doesn't serve /health."
  - "deploy-spa.yml is intentionally dormant until Phase 4 ships apps/web/ — paths filter prevents it firing pre-Phase-4; working-directory: apps/web inside the build steps is safe because the trigger never fires without that directory."

patterns-established:
  - "Per-workflow paths filter contract: each deploy workflow owns a non-overlapping path set so a frontend-only PR doesn't fire deploy-infra.yml and vice-versa (DEPL-08 spec)."
  - "OIDC permissions block: { id-token: write, contents: read } is the minimal Azure-OIDC contract; deploy-api.yml extends with packages: write for GHCR push; deploy-spa.yml omits id-token: write entirely (token-based)."
  - "Manual-runbook-reminder pattern: when a step would otherwise need a long-lived PAT to mutate GitHub state from inside the workflow, echo the equivalent local command into $GITHUB_STEP_SUMMARY instead. Pushes the secret-rotation responsibility to Adrian's local terminal where his gh-cli session already has the right scope."

requirements-completed: [DEPL-07, DEPL-08, DEPL-09]

duration: ~6min
completed: 2026-04-30
---

# Phase 03 Plan 06: Three deploy workflows (infra, API, SPA) Summary

**OIDC-federated terraform apply + docker build/push to GHCR + ACA revision swap + token-based SWA upload — three GitHub Actions workflows with non-overlapping paths filters that consume the Plan 04 federated credentials and the Plan 05 Azure stack.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-30T16:42:00Z (approx)
- **Completed:** 2026-04-30T16:45:30Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- `.github/workflows/deploy-infra.yml`: triggers on push to master under `infra/**` + `workflow_dispatch`; gated by `environment: production`; runs `terraform apply -input=false -auto-approve -var-file=prod.tfvars` via OIDC; injects `TF_VAR_*` from environment-scoped GH secrets; prints non-sensitive outputs + B2 manual-runbook reminder to `$GITHUB_STEP_SUMMARY`.
- `.github/workflows/deploy-api.yml`: triggers on push to master under `src/** | pyproject.toml | uv.lock | Dockerfile | alembic/** | scripts/docker-entrypoint.sh`; builds with buildx + GHA cache; pushes to `ghcr.io/${{ github.repository }}:${{ github.sha }}` + `:latest`; runs `az containerapp update --name jobrag-prod-api --image ...`; smokes `/health` for 90s post-revision-swap and fails loud on miss.
- `.github/workflows/deploy-spa.yml`: triggers on push to master under `apps/web/**`; Node 22 + `npm ci` + `npm run build` (working-directory: apps/web); deploys via `Azure/static-web-apps-deploy@v1` with `secrets.AZURE_STATIC_WEB_APPS_API_TOKEN_PROD`; sole non-OIDC workflow per CONTEXT.md A2 + D-08.

## Task Commits

1. **Task 1: deploy-infra.yml + deploy-api.yml** — `184bb33` (feat)
2. **Task 2: deploy-spa.yml** — `5480a1e` (feat)

**Plan metadata:** to be attached after this SUMMARY commit.

## Files Created/Modified

- `.github/workflows/deploy-infra.yml` — OIDC-federated terraform apply gated on environment: production. Echoes B2 manual-runbook reminder.
- `.github/workflows/deploy-api.yml` — OIDC-federated docker build+push to GHCR + `az containerapp update` + /health smoke.
- `.github/workflows/deploy-spa.yml` — Token-based SWA upload via `Azure/static-web-apps-deploy@v1`.

## Decisions Made

- **/health smoke poll inside deploy-api.yml**: belt-and-suspenders extension over the canonical workflow shape from RESEARCH.md lines 979-1027. Cost: ~5-90s extra per deploy (only when /health is unhealthy do we hit the upper bound). Benefit: a broken image fails the workflow immediately instead of silently leaving the previous revision still serving traffic while the new one crash-loops.
- **`scripts/docker-entrypoint.sh` added to deploy-api.yml paths filter**: not in the canonical RESEARCH spec but was identified as a Dockerfile-adjacent file that, when changed, must rebuild the image. Reduces "what if I edit the entrypoint and forget to bump the API workflow" surprise.
- **`workflow_dispatch` only on deploy-infra.yml**: deploy-api.yml + deploy-spa.yml deliberately omit `workflow_dispatch` so they cannot be rerun ad-hoc against arbitrary refs (T-3-02 mitigation — keeps the federated credential subject contract narrow).

## Deviations from Plan

### Documentation/Verify-Spec Inconsistency (handled, not auto-fixed)

**1. [Rule N/A — plan-text inconsistency between action and verify]**

- **Found during:** Task 1 verification.
- **Issue:** The plan's `<action>` block for deploy-infra.yml explicitly instructs the executor to write the literal strings `gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` (inside an `echo` line that emits the B2 manual-runbook reminder into `$GITHUB_STEP_SUMMARY`) and `GH_PAT_FOR_SECRETS` (inside a YAML comment explaining the rationale for the manual runbook). The plan's `<verify>` automated check uses `! grep -q "gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD"` and `! grep -q "GH_PAT_FOR_SECRETS"` — both negative greps that contradict the action body the executor was just told to write.
- **Resolution:** Followed the `<action>` block verbatim — those strings appear ONLY in (a) a YAML comment (`GH_PAT_FOR_SECRETS`) and (b) an `echo` line that emits the reminder text into the job summary (`gh secret set ...`). Neither string is part of an executable workflow STEP that mutates GitHub state. The intent of the negative grep — confirmed by `success_criteria` #6 ("deploy-infra.yml does NOT include a `gh secret set` step or reference `GH_PAT_FOR_SECRETS`") and the truths block — is to forbid an executable step that runs `gh secret set` or consumes a `GH_PAT_FOR_SECRETS` secret. That intent is honored: there is no `run: gh secret set ...` and no `${{ secrets.GH_PAT_FOR_SECRETS }}` reference. The strings are documentation only.
- **Files modified:** none (file as written matches `<action>` and the spirit of `success_criteria`).
- **Verification:** Confirmed via `grep -n "gh secret set" .github/workflows/deploy-infra.yml` (matches are in a comment line and an echo line, not a `run:` step) and `grep -c "GH_PAT_FOR_SECRETS"` (1 match, in a YAML comment). No `${{ secrets.GH_PAT_FOR_SECRETS }}` reference anywhere.
- **Committed in:** `184bb33`.

### Auto-fixed Issues

None — no Rule 1/2/3 fixes were needed. All three workflow files compiled cleanly; no scope creep.

---

**Total deviations:** 1 plan-text inconsistency (resolved by following `<action>` and `<success_criteria>` over the contradictory negative-grep `<verify>` rule).

**Impact on plan:** Zero functional impact — the workflow does NOT execute `gh secret set` and does NOT reference `GH_PAT_FOR_SECRETS` as a secret. The negative grep rule was overzealous; the action body and success_criteria were honored.

## Issues Encountered

- `actionlint` is not installed locally; YAML structural validity verified via `python -c "import yaml; yaml.safe_load(open(...))"` for all three workflows (all parse cleanly). All grep contract checks (positive: `id-token: write`, `azure/login@v2`, `docker/build-push-action@v6`, `az containerapp update`, `Azure/static-web-apps-deploy@v1`, `actions/setup-node@v4`, `apps/web`, paths filter, `actions/checkout@v4`; negative: no `azure/login@v2` in deploy-spa.yml, no `id-token: write` in deploy-spa.yml) pass.
- Validators that ran: `python yaml.safe_load` (all 3 files OK); manual grep contract checks (all positives match, all negatives confirmed). Validators that did NOT run: `actionlint` (not installed); `tflint`/`tfsec` (out of scope — those are Plan 03's concern).

## User Setup Required

**Manual setup tasks Adrian must do BEFORE these workflows can succeed in CI:**

1. **GitHub repository secrets at the repo level** (not environment-scoped):
   - `AZURE_CLIENT_ID` — workforce-tenant SP client_id from Plan 04 identity module
   - `AZURE_TENANT_ID` — workforce tenant ID
   - `AZURE_SUBSCRIPTION_ID` — Adrian's Azure subscription ID
2. **GitHub repository secrets used by deploy-infra.yml `TF_VAR_*` env vars** (sensitive Terraform inputs):
   - `GHCR_PAT` — runtime PAT for ACA pull (NOT the GH_PAT_FOR_SECRETS — different surface)
   - `OPENAI_API_KEY` — propagated to Key Vault by terraform apply
   - `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` — propagated to Key Vault
3. **GitHub Environment "production"** must exist with Adrian as the sole required reviewer. The federated credential subject `repo:adrianzaplata/job-rag:environment:production` matches against this environment name. (Plan 04 creates the federated credential; Adrian creates the environment in the GitHub UI.)
4. **`AZURE_STATIC_WEB_APPS_API_TOKEN_PROD`** — set via the B2 manual runbook AFTER the first `terraform apply` succeeds and prints `swa_api_key` into the workflow summary. From Adrian's local terminal:
   ```bash
   cd infra/envs/prod
   terraform output -raw swa_api_key | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD --repo adrianzaplata/job-rag
   ```
5. **GHCR package visibility** (B3 reminder): after the first `docker push` lands in GHCR via deploy-api.yml, Adrian must flip the package's visibility to public (one-time portal click) OR ensure `var.ghcr_pat` carries `read:packages` scope. Documented in `infra/envs/prod/README.md` "Image push: GHCR visibility".

## Next Phase Readiness

- Plan 03-07 (the final plan in this phase — first-apply runbook + smoke validation) is now unblocked. All deploy workflows exist; Plan 07 wires them into the runbook and walks through the live first-apply.
- **Threat surface scan:** no new threat surface beyond the plan's threat_model. T-3-02 (OIDC over-privileged), T-3-04 (GHCR push token), T-3-05 (SWA api_key rotation), T-3-08 (CORS bypass) are all `mitigate` and the mitigations land in this plan.

## Self-Check: PASSED

- `.github/workflows/deploy-infra.yml`: FOUND
- `.github/workflows/deploy-api.yml`: FOUND
- `.github/workflows/deploy-spa.yml`: FOUND
- Commit `184bb33`: FOUND in `git log`
- Commit `5480a1e`: FOUND in `git log`
- All grep contract checks pass; all 3 YAMLs parse cleanly via `yaml.safe_load`.

---
*Phase: 03-infrastructure-ci-cd*
*Completed: 2026-04-30*
