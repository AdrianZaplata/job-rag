---
phase: quick
plan: 260519-ids
subsystem: ci-cd / deploy-api
tags: [ci, github-actions, azure-container-apps, smoke-check, uat-gap-closure, d-15]
requires: []
provides:
  - "deploy-api.yml smoke step that pins to NEW revision via per-revision FQDN + runningState poll"
  - "Restored D-15 invariant: deploy.yml smoke must prove the new revision serves traffic"
affects:
  - .github/workflows/deploy-api.yml
tech_added: []
patterns:
  - "ACA revision pinning via `az containerapp revision list ... sort_by(@, &properties.createdTime)[-1].name`"
  - "Dual-signal smoke gate: HTTP 200 on per-revision FQDN AND properties.runningState='Running'"
  - "Terminal-state early-exit: ActivationFailed / Failed = exit 1 immediately (no polling burn)"
  - "Forensic logging: echo NEW_REVISION + image tag (github.sha) BEFORE polling"
key_files:
  modified:
    - .github/workflows/deploy-api.yml
decisions:
  - "150s budget (30 iter x 5s) chosen over 120s or 180s — sits cleanly in the required 120-180s window, gives ~60s headroom over the pre-fix 90s while remaining bounded enough to fail fast on a stuck revision"
  - "latestRevisionName as fallback (with loud WARN) — defensive only; revision-list lookup should always succeed but the fallback covers a transient ARM read miss without silent failure"
  - "Both HTTP 200 AND runningState=Running required for success — single-signal would re-introduce the failure mode (revision can serve /health 200 briefly during Processing → ActivationFailed transition)"
metrics:
  duration: "1m 35s"
  tasks: 2
  files_modified: 1
  commits: 1
  completed_date: "2026-05-19"
gap_closure: true
requirements:
  - GAP-10C
  - D-15
---

# Quick Task 260519-ids: deploy-api.yml smoke check — pin to new revision Summary

**One-liner:** Replaced deploy-api.yml smoke step with revision-pinned probe (per-revision FQDN + `properties.runningState` poll) so ACA traffic-weight fallback can no longer fake a green deploy when the new revision ActivationFailed; restores D-15.

## What changed

A single workflow step in `.github/workflows/deploy-api.yml` was rewritten end-to-end. No other workflow step, no app code, no Dockerfile, no Terraform — strictly the `Smoke /health after revision swap` step (lines 78-94 of the old file).

### Step name change
- **Before:** `Smoke /health after revision swap`
- **After:**  `Smoke new revision (per-revision FQDN + runningState)`

### Logic change

| Aspect              | Before                                                                                       | After                                                                                              |
| ------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Target FQDN         | Canonical app FQDN (`properties.configuration.ingress.fqdn`)                                  | Per-revision FQDN (`az containerapp revision show ... properties.fqdn`)                            |
| Revision resolution | None (queried app-level FQDN)                                                                 | `az containerapp revision list ... sort_by(@, &properties.createdTime)[-1].name` + fallback to `properties.latestRevisionName` with loud WARN |
| Health signal       | HTTP 200 on `/health`                                                                         | HTTP 200 on `/health` AND `properties.runningState == 'Running'`                                   |
| Terminal failure    | None — polled until budget exhausted                                                          | `ActivationFailed` or `Failed` → exit 1 immediately (no further polling)                           |
| Total budget        | 90s (18 iter x 5s)                                                                            | 150s (30 iter x 5s)                                                                                |
| Shell safety        | None                                                                                          | `set -euo pipefail` at top of run block                                                            |
| Log forensics       | Only printed elapsed seconds on success                                                       | Echoes resolved NEW_REVISION + REV_FQDN + image tag (`github.sha`) BEFORE polling; per-iteration runningState; final fatal includes last state |

### Diff summary

```
.github/workflows/deploy-api.yml | 92 ++++++++++++++++++++++++++++++++++++----
1 file changed, 83 insertions(+), 9 deletions(-)
```

All 92 lines of change confined to the single smoke step. `git diff` against any other step in the workflow shows zero modifications.

### Diff (old → new smoke step)

**Removed (lines 78-94 of old file):**
```yaml
      - name: Smoke /health after revision swap
        run: |
          # Wait up to 90s for the new revision to be active and reachable.
          ACA_FQDN="$(az containerapp show \
            --name jobrag-prod-api \
            --resource-group jobrag-prod-rg \
            --query properties.configuration.ingress.fqdn -o tsv)"

          for i in {1..18}; do
            if curl -fs --max-time 5 "https://${ACA_FQDN}/health" >/dev/null; then
              echo "Health check passed after $((i*5))s"
              exit 0
            fi
            sleep 5
          done
          echo "Health check did not pass after 90s — revision may be unhealthy"
          exit 1
```

**Added (new step):**
```yaml
      - name: Smoke new revision (per-revision FQDN + runningState)
        run: |
          set -euo pipefail
          # UAT Gap 10.C fix (incident: run #25964582484, 2026-05-16): the previous
          # smoke step polled the canonical app FQDN, which ACA silently routes to the
          # last Healthy revision if the new one ActivationFailed. That shipped a
          # false-positive green while prod kept serving a 10-day-old image.
          #
          # This step pins both probes to the NEW revision:
          #   (A) curl the per-revision FQDN (e.g. jobrag-prod-api--0000007.gentlebay-...)
          #   (B) poll properties.runningState; ActivationFailed/Failed = terminal exit 1
          # Both signals must be green (HTTP 200 + runningState=Running) to succeed.
          # Total budget: 150s (30 iterations x 5s) — fits the 120-180s window.

          # 1) Resolve the NEW revision name (latest by createdTime). Fall back to
          #    the legacy latestRevisionName query if the list lookup returns empty,
          #    and loudly warn so the fallback path is visible in workflow logs.
          NEW_REVISION="$(az containerapp revision list \
            --name jobrag-prod-api \
            --resource-group jobrag-prod-rg \
            --query "[?properties.createdTime != null] | sort_by(@, &properties.createdTime)[-1].name" \
            -o tsv)"
          if [ -z "$NEW_REVISION" ]; then
            echo "WARN: revision-list lookup failed, using latestRevisionName fallback"
            NEW_REVISION="$(az containerapp show \
              --name jobrag-prod-api \
              --resource-group jobrag-prod-rg \
              --query properties.latestRevisionName -o tsv)"
          fi
          if [ -z "$NEW_REVISION" ]; then
            echo "FATAL: could not resolve new revision name from either lookup"
            exit 1
          fi

          # 2) Resolve the per-revision FQDN. Empty = fatal (can't probe what we
          #    can't address).
          REV_FQDN="$(az containerapp revision show \
            --name jobrag-prod-api \
            --resource-group jobrag-prod-rg \
            --revision "$NEW_REVISION" \
            --query properties.fqdn -o tsv)"
          if [ -z "$REV_FQDN" ]; then
            echo "FATAL: per-revision FQDN is empty for revision $NEW_REVISION"
            exit 1
          fi

          # 3) Echo forensic anchors BEFORE polling — any future incident triage
          #    starts from these two lines in the run log.
          IMAGE_TAG="ghcr.io/${{ steps.repo.outputs.lc }}:${{ github.sha }}"
          echo "Smoke target revision: $NEW_REVISION"
          echo "Smoke target FQDN:     $REV_FQDN"
          echo "Smoke target image:    $IMAGE_TAG"

          # 4) Poll loop: 30 iterations x 5s = 150s total budget.
          STATE=""
          for i in $(seq 1 30); do
            STATE="$(az containerapp revision show \
              --name jobrag-prod-api \
              --resource-group jobrag-prod-rg \
              --revision "$NEW_REVISION" \
              --query properties.runningState -o tsv)"

            # 4a) Terminal failure states — stop immediately, don't burn budget.
            if [ "$STATE" = "ActivationFailed" ] || [ "$STATE" = "Failed" ]; then
              echo "FATAL: revision $NEW_REVISION entered terminal state '$STATE'"
              echo "       image: $IMAGE_TAG"
              echo "       elapsed: $((i*5))s"
              exit 1
            fi

            # 4b) Health probe against per-revision FQDN. Both HTTP 200 AND
            #     runningState=Running must hold before we declare success.
            if curl -fs --max-time 5 "https://${REV_FQDN}/health" >/dev/null; then
              if [ "$STATE" = "Running" ]; then
                echo "Smoke passed after $((i*5))s — revision $NEW_REVISION is Running and serving /health 200"
                exit 0
              fi
              echo "Iteration $i: /health 200 but runningState='$STATE' — continuing to poll"
            else
              echo "Iteration $i: /health not yet ready, runningState='$STATE'"
            fi

            sleep 5
          done

          # 5) Budget exhausted — fail loudly with the last observed state.
          echo "FATAL: smoke check did not pass after 150s"
          echo "       revision: $NEW_REVISION"
          echo "       image:    $IMAGE_TAG"
          echo "       last observed runningState: '$STATE'"
          exit 1
```

## must_haves.truths — encoding map

All 6 plan truths are encoded in the new step:

| # | Truth                                                                                                                       | Encoded by                                                                              |
| - | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1 | Smoke discovers NEW revision (latest by createdTime) after `az containerapp update`                                          | Block (1): `az containerapp revision list ... sort_by(@, &properties.createdTime)[-1].name` |
| 2 | Probes per-revision FQDN, not canonical app FQDN                                                                             | Block (2) sets `REV_FQDN` from `revision show ... --query properties.fqdn`; curl in (4b) targets `https://${REV_FQDN}/health` |
| 3 | Polls `properties.runningState`; `ActivationFailed` / `Failed` are fatal (exit 1)                                            | Block (4a): early exit on terminal states                                                |
| 4 | Workflow log loudly echoes NEW revision + image tag (github.sha) before polling                                              | Block (3): three echo lines                                                              |
| 5 | Total wait budget between 120s and 180s                                                                                      | Block (4): `seq 1 30` x `sleep 5` = 150s                                                 |
| 6 | Either {runningState fatal, /health never 200 in budget} causes exit 1, restoring D-15                                       | Block (4a) handles the first; Block (5) handles the second                               |

## Validation results

Both Task 2 automated checks PASSED:

### Validation 1 — YAML parse + step structure + required tokens
```
$ uv run python -c "<task-2 validation-1 block>"
Steps: ['Checkout', 'GHCR login', 'Setup buildx', 'Lowercase repo', 'Build and push image', 'Azure login (OIDC)', 'Update Container App image', 'Smoke new revision (per-revision FQDN + runningState)']
OK
```

### Validation 2 — bash -n syntax check on extracted run body
```
$ uv run python -c "<extract body>" && bash -n /tmp/smoke_body.sh && echo "shell syntax OK" && rm /tmp/smoke_body.sh
shell syntax OK
```

### Combined automated verify (Task 2 `<automated>`)
```
$ uv run python -c "<task-2 combined>" && bash -n /tmp/smoke_body.sh && rm /tmp/smoke_body.sh && echo PASS
PASS
```

All 10 required tokens present in the smoke step body: `set -euo pipefail`, `az containerapp revision list`, `az containerapp revision show`, `properties.runningState`, `properties.fqdn`, `ActivationFailed`, `NEW_REVISION`, `REV_FQDN`, `sort_by`, `createdTime`.

Old query `properties.configuration.ingress.fqdn` count in file: **0** (fully replaced, not appended).

Note: validations used `uv run python` (project's package manager) because system `python3` does not have PyYAML installed. The validation logic is identical to the plan's `<automated>` block — the only adjustment was `python3` → `uv run python`.

## Commits

| Task | Hash      | Message                                                                |
| ---- | --------- | ---------------------------------------------------------------------- |
| 1    | `07817d8` | `fix(deploy-api): pin smoke check to new revision FQDN + runningState` |
| 2    | (none)    | Validation only — no file changes                                      |

## Deviations from Plan

None. Plan executed exactly as written; the only adjustment was using `uv run python` instead of `python3` for the YAML-parsing validations, which is a tool-availability mechanical substitution and does not change validation semantics.

## End-to-end verification — DEFERRED

Plan explicitly scopes end-to-end validation as out of scope for this quick task. The new smoke step's behavioural correctness (does it actually fail loudly on a fresh `ActivationFailed`? does it actually succeed on a fresh `Running` revision?) cannot be proven without pushing to `master` and burning a real deploy.

**Live proof point:** the next push to `master` that touches any of the deploy-api.yml trigger paths (`src/**`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `alembic/**`, `scripts/docker-entrypoint.sh`, `.github/workflows/deploy-api.yml`) will exercise this path. Two expected observable outcomes:

1. **If the new image activates cleanly** → logs show `Smoke target revision: jobrag-prod-api--00000XX`, `Smoke target FQDN: ...`, `Smoke target image: ghcr.io/adrianzaplata/job-rag:<sha>`, then `Smoke passed after Ns — revision ... is Running and serving /health 200`. Workflow green.
2. **If the new image fails activation** → logs show the same forensic anchors, then `FATAL: revision ... entered terminal state 'ActivationFailed'` and the job exits 1 within ~5-30s of the failure becoming observable (no 150s wait burn). Workflow red — which is the desired behaviour and what was missing pre-fix.

## Cross-references

- **UAT Gap 10.C** (`.planning/phases/03-infrastructure-ci-cd/03-UAT.md`): status flips from `failed` → expected `passed` on the next real deploy that either succeeds cleanly OR fails loudly on the new probe. This commit closes the *code surface* of Gap 10.C; the *behavioural* close requires the next live deploy observation.

- **UAT Gap 10.B** (the still-open alembic-fix image `369000784` that has not actually served prod for 3 days): explicitly OUT OF SCOPE for this quick task per the plan's `<output>` block. Gap 10.B is *blocked by* Gap 10.C being fixed first (you cannot trust a deploy until the smoke check actually distinguishes new-revision health from any-revision health). The next push to master will both (a) prove this fix and (b) — if it activates cleanly — naturally close 10.B by getting the alembic fix into production.

- **D-15 invariant:** restored at the code surface. Deploy.yml smoke now provably distinguishes "new revision is alive" from "any revision is alive" via dual-signal gating (HTTP 200 on per-revision FQDN + `runningState='Running'`).

## Self-Check: PASSED

- File exists: `.github/workflows/deploy-api.yml` (modified)
- Commit exists: `07817d8` — `fix(deploy-api): pin smoke check to new revision FQDN + runningState`
- All 10 required tokens present in smoke step `run:` body
- Old `properties.configuration.ingress.fqdn` query count: 0 (fully replaced)
- YAML parses cleanly
- `bash -n` on extracted run body: 0 (no syntax errors)
- Diff confined to the single smoke step (83 insertions / 9 deletions in one step)
