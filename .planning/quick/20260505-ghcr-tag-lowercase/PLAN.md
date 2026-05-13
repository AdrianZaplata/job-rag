---
slug: ghcr-tag-lowercase
quick_id: 260505-lbp
date: 2026-05-05
status: in-progress
---

# Lowercase GHCR repo path in deploy-api workflow

## Problem

`.github/workflows/deploy-api.yml` builds and pushes `ghcr.io/${{ github.repository }}:<sha>` directly. With `github.repository = "AdrianZaplata/job-rag"`, the resulting tag has an uppercase path component, which GHCR rejects:

```
ERROR: failed to build: invalid tag "ghcr.io/AdrianZaplata/job-rag:<sha>": repository name must be lowercase
```

Last 3 master pushes failed at the docker build step before `azure/login@v2` ran, so Test 7's OIDC sub-test is unverifiable until this clears.

## Constraint — DO NOT TOUCH

OIDC / Entra federated credential subject case (Aug 2024 AADSTS7002138 tightening) was stabilized in commit a4d6c25:
- `infra/modules/identity/main.tf` no longer `lower()`s the subject — keep as-is
- `infra/envs/prod/prod.tfvars` `github_owner = "AdrianZaplata"` — keep as-is
- Any AZURE_* OIDC secret reference — keep as-is

The Docker tag lowercase requirement is **orthogonal** to the OIDC subject case requirement. JWT subject `repo:AdrianZaplata/job-rag:...` is matched against the registered fed cred subject (uppercase `AdrianZaplata`); the docker tag value is unrelated to that handshake.

## Fix

1. Add a "Lowercase repo" step at the top of deploy-api.yml that exposes a `steps.repo.outputs.lc` value:
   ```yaml
   - name: Lowercase repo
     id: repo
     run: echo "lc=$(echo '${{ github.repository }}' | tr '[:upper:]' '[:lower:]')" >> "$GITHUB_OUTPUT"
   ```
2. Replace `${{ github.repository }}` with `${{ steps.repo.outputs.lc }}` in:
   - `tags:` block (lines ~50-51)
   - `az containerapp update --image` line (~67)
3. Sweep sibling workflows for any `ghcr.io/${{ github.repository }}` constructions:
   - `bootstrap-corpus.yml` — no GHCR refs (uses `az containerapp exec` against running container)
   - `deploy-spa.yml` — no GHCR refs (uses Azure SWA token)
   - Only `deploy-api.yml` needs the change.

## Branch strategy

Working branch is `test/static-tf-smoke` (8 commits ahead of master). User instruction says "Commit on master directly". Approach:
1. Stash unstaged UAT.md changes (Test 7 issue findings already drafted)
2. Switch to master
3. Apply fix, commit `fix(ci): lowercase GHCR repo path in deploy-api`
4. Push master, `gh run watch`
5. After green, return to `test/static-tf-smoke`, pop stash, update UAT.md (Test 7 issue → pass + summary + gaps), commit `docs(quick-260505-lbp): GHCR fix landed; Test 7 OIDC handshake verified`

## Expected outcome

- GHCR build/push succeeds (lowercase tag accepted)
- `azure/login@v2` reports "Login successful" (OIDC handshake confirmed)
- `az containerapp update` succeeds
- `/health` smoke poll passes within 90s

## Sweep policy (per memory: feedback_ci_fix_sweep)

Other static/workflow findings: fix mechanically with atomic commits per finding. PAUSE on:
- Findings that change documented design decisions (D-XX, A-X)
- Any change to OIDC/Entra/fed-cred surface (just stabilized — case-sensitive)
- Anything outside `.github/workflows/`

Pre-existing `lint-and-test` ruff failures: out of scope.
