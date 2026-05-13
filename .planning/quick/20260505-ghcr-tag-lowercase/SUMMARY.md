---
slug: ghcr-tag-lowercase
quick_id: 260505-lbp
date: 2026-05-05
status: incomplete
---

# Summary — GHCR tag lowercase fix

## What landed

**Commit `1aadb83` on `master`**: `fix(ci): lowercase GHCR repo path in deploy-api`

`.github/workflows/deploy-api.yml` now has a `Lowercase repo` step that exposes `steps.repo.outputs.lc` (lowercased `${{ github.repository }}`). Both the docker tags block and the `az containerapp update --image` line consume the lowercased value. A comment block above the new step documents the orthogonality with the Entra federated credential subject case-sensitivity work in commit `a4d6c25` so a future reader does not accidentally lowercase the OIDC subject.

## Sweep results

| Workflow | GHCR refs | Action |
|---|---|---|
| `.github/workflows/deploy-api.yml` | 3 (lines 50, 51, 67) | Fixed |
| `.github/workflows/bootstrap-corpus.yml` | 0 | No change — uses `az containerapp exec` against running container, no image build |
| `.github/workflows/deploy-spa.yml` | 0 | No change — uses Azure SWA token, no GHCR involvement |

## Verification — partial

Run `25379076835` on master after the push:

- `Lowercase repo` step ✓ (new step, ran successfully)
- `Build and push image` ✗ — but failure mode CHANGED:
  - **Before** (3 prior runs): `ERROR: failed to build: invalid tag "ghcr.io/AdrianZaplata/job-rag:<sha>": repository name must be lowercase` (rejected by docker buildx before any GHCR network call)
  - **After** (1aadb83): buildx accepts the tag and proceeds to push; GHCR returns `403 Forbidden` on the blob HEAD request to `https://ghcr.io/v2/adrianzaplata/job-rag/blobs/sha256:b5f3...`

The lowercase fix is therefore **confirmed working**. The original blocker (Test 7 sub-test) is resolved; a separate, downstream blocker has surfaced.

## New blocker — out of scope (paused per sweep policy)

The 403 push failure matches the workflow's own B3 / A2 comment block (lines 30-33 of `deploy-api.yml`) and the runbook `infra/envs/prod/README.md` § "Image push: GHCR visibility (B3)" (line 91). The GHCR package `adrianzaplata/job-rag` either does not yet exist or lacks the repo linkage required for `secrets.GITHUB_TOKEN` + `permissions: packages: write` to write to it from GHA.

Per the `feedback_ci_fix_sweep` PAUSE conditions:
- The fix lives **outside `.github/workflows/`** (GHCR portal action + manual `docker push` from local).
- It touches design decision **A2** (GHCR visibility — public per portfolio recommendation).

User action required:
1. Run the manual fallback from `infra/envs/prod/README.md` lines 115-126:
   ```bash
   docker build -t ghcr.io/adrianzaplata/job-rag:bootstrap .
   echo "$GHCR_PAT" | docker login ghcr.io -u adrianzaplata --password-stdin
   docker push ghcr.io/adrianzaplata/job-rag:bootstrap
   ```
2. Set the package visibility to Public per A2 (portal: package settings → Change visibility → Public).
3. Re-trigger `deploy-api.yml` on master (any no-op commit under `src/**` or trivial `.github/workflows/deploy-api.yml` edit). Expected: build and push step succeeds, `azure/login@v2` reports `Login successful` (this is the still-missing Test 7 verification), `az containerapp update` swaps the revision, `/health` poll passes within 90s.

## UAT.md status

- Test 7: **NOT** promoted to pass (instruction was conditional on deploy-api going fully green; it didn't). Reported / severity fields retained but reported text rewritten to reflect the new failure mode and explicitly call out commit 1aadb83 as the partial fix.
- Summary: passed unchanged at 6, issues unchanged at 1, pending unchanged at 11.
- Gaps: same single gap entry (Test 7), but reason / artifacts / missing now describe the B3 GHCR-package-permission state instead of the resolved uppercase-tag bug.

## What is NOT done (explicit)

- Test 7 not promoted to pass.
- OIDC handshake on master push not yet verified end-to-end (the run never reaches `azure/login@v2`).
- ACA revision not yet updated with the new image SHA (build/push didn't complete).
- `/health` smoke poll not yet exercised.
