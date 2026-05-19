---
phase: quick
plan: 260519-ids
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/deploy-api.yml
autonomous: true
requirements:
  - GAP-10C
  - D-15
gap_closure: true

must_haves:
  truths:
    - "deploy-api.yml smoke step discovers the NEW revision name (latest by createdTime) after `az containerapp update`"
    - "Smoke step probes the per-revision FQDN (e.g. jobrag-prod-api--0000007.gentlebay-...) — NOT the canonical app FQDN — so it cannot be fooled by ACA traffic-weight fallback to a prior Healthy revision"
    - "Smoke step polls `properties.runningState` on the new revision and treats `ActivationFailed` / `Failed` as fatal (exit 1)"
    - "Workflow log loudly echoes the resolved revision name AND the image tag (github.sha) being probed, so any future incident can be cross-referenced from the run log alone"
    - "Total wait budget is between 120s and 180s (inclusive) — longer than the pre-fix 90s because revision state transitions can outlast first-byte /health latency"
    - "Any of {runningState fatal, /health never 200 within budget} causes the job to exit 1, restoring D-15 (deploy.yml smoke must prove the new revision serves)"
  artifacts:
    - path: ".github/workflows/deploy-api.yml"
      provides: "Revised 'Smoke /health after revision swap' step that proves the new revision is the one serving traffic"
      contains: "az containerapp revision list"
      contains_2: "az containerapp revision show"
      contains_3: "properties.runningState"
      contains_4: "properties.fqdn"
  key_links:
    - from: ".github/workflows/deploy-api.yml (Update Container App image step)"
      to: ".github/workflows/deploy-api.yml (Smoke step)"
      via: "shell — `az containerapp revision list ... sort_by(@, &properties.createdTime)[-1].name` resolves NEW_REVISION after update"
      pattern: "sort_by.*createdTime.*-1.*name"
    - from: ".github/workflows/deploy-api.yml (Smoke step revision lookup)"
      to: "ACA per-revision FQDN endpoint"
      via: "curl against `https://${NEW_REVISION_FQDN}/health`"
      pattern: "curl.*NEW_REVISION_FQDN.*/health"
    - from: ".github/workflows/deploy-api.yml (Smoke step state poll)"
      to: "ACA controller revision state"
      via: "`az containerapp revision show --query properties.runningState` polled in loop"
      pattern: "runningState"
---

<objective>
Close UAT Gap 10.C: deploy-api.yml's post-deploy smoke check currently polls the canonical app FQDN and is silently fooled when a new revision fails activation (ACA falls back to the last Healthy revision). This plan replaces the smoke step with Option A (revision-specific FQDN poll) + Option C (revision runningState poll) so the workflow can distinguish "new revision is alive" from "any revision is alive". Restores D-15.

Purpose: A documented production incident (deploy-api.yml run #25964582484, 2026-05-16) shipped a false-positive ✓ while revision --0000006 was ActivationFailed and prod traffic kept hitting the 2026-05-06 image on --0000003. The alembic fix has NOT been serving prod for 3 days. This change makes that failure mode impossible.

Output: A single revised `.github/workflows/deploy-api.yml` with a rewritten "Smoke /health after revision swap" step that fails loudly when the new revision is not the one serving traffic.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/03-infrastructure-ci-cd/03-UAT.md
@.github/workflows/deploy-api.yml

<interfaces>
<!-- Existing shell context the smoke step operates inside. Extracted from current deploy-api.yml. -->

From .github/workflows/deploy-api.yml (current state):

The job already has:
- `${{ steps.repo.outputs.lc }}` — lowercased repo path (e.g. `adrianzaplata/job-rag`)
- `${{ github.sha }}` — full commit SHA being deployed (the new image tag)
- Azure CLI authenticated via OIDC (`azure/login@v2` step ran successfully)
- Resource group: `jobrag-prod-rg`
- Container App name: `jobrag-prod-api`

The current smoke step (lines 78-94) uses:
```yaml
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

This is the entire surface the task replaces. No other workflow steps change.

Azure CLI commands the new step uses (verified syntax):
- `az containerapp revision list --name <app> --resource-group <rg> --query "<jmespath>" -o tsv`
- `az containerapp revision show --name <app> --resource-group <rg> --revision <rev-name> --query <jmespath> -o tsv`

Relevant JMESPath:
- Latest revision name: `"[?properties.createdTime != null] | sort_by(@, &properties.createdTime)[-1].name"`
- Per-revision FQDN: `properties.fqdn`
- Per-revision running state: `properties.runningState` (values: `Running`, `Processing`, `ActivationFailed`, `Failed`, `Degraded`)

Note: `properties.healthState` exists historically but is deprecated; `runningState` is the current authoritative field.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace smoke step with revision-pinned FQDN + runningState poll</name>
  <files>.github/workflows/deploy-api.yml</files>
  <action>
Replace the existing "Smoke /health after revision swap" step (currently lines 78-94 of `.github/workflows/deploy-api.yml`) with a new step that:

1. Resolves the new revision name from `az containerapp revision list` using `sort_by(@, &properties.createdTime)[-1].name`. Capture into `NEW_REVISION` shell var. If the lookup returns empty, fall back to the legacy `az containerapp show ... properties.latestRevisionName` query AND echo a loud `WARN: revision-list lookup failed, using latestRevisionName fallback` to the log (defensive — should never trip but visible if it does).
2. Resolves the per-revision FQDN via `az containerapp revision show --name jobrag-prod-api --resource-group jobrag-prod-rg --revision "$NEW_REVISION" --query properties.fqdn -o tsv`. Capture into `REV_FQDN`. If empty, exit 1 immediately with a clear error.
3. Echoes both `NEW_REVISION` and the deployed image tag (`ghcr.io/${{ steps.repo.outputs.lc }}:${{ github.sha }}`) to the workflow log BEFORE starting the poll — these are the forensic anchors any future incident will need.
4. Enters a poll loop, total budget = **150s** (30 iterations of 5s sleep — sits cleanly within the required 120-180s window). Each iteration:
   a. Query `properties.runningState` via `az containerapp revision show ... --query properties.runningState -o tsv`. If the value is `ActivationFailed` or `Failed`, immediately exit 1 with a fatal error message that includes `NEW_REVISION` and the state. Do NOT keep polling — these states are terminal.
   b. Issue `curl -fs --max-time 5 "https://${REV_FQDN}/health" >/dev/null`. If 200, AND the most-recent runningState read is `Running`, echo success (with elapsed seconds + revision name) and exit 0. If 200 but runningState is still `Processing`, continue polling — we want both signals green.
   c. Sleep 5s.
5. On loop exhaustion, echo a final error including `NEW_REVISION`, the last observed `runningState`, and the elapsed budget, then exit 1.

Implementation notes:
- Use `set -euo pipefail` at the top of the `run:` block so any unexpected az/curl failure surfaces immediately rather than silently flowing past.
- The runningState query is cheap (single ARM read) — running it once per iteration alongside the curl is fine; total = ~30 az calls + ~30 curls over 150s.
- Quote all shell variable expansions (`"$NEW_REVISION"`, `"$REV_FQDN"`, `"$STATE"`) — revision names contain `--` and FQDNs contain dots; unquoted expansion is a footgun under `set -u`.
- Do NOT change any other step (Checkout, GHCR login, buildx, Lowercase repo, Build/push, Azure login, Update Container App image). Scope is the single smoke step only.
- Preserve YAML indentation (steps are 6 spaces, `run: |` body is 10 spaces) — the existing file is mixed-tab-safe; match the surrounding style exactly.
- Step name SHOULD change from "Smoke /health after revision swap" to "Smoke new revision (per-revision FQDN + runningState)" so the workflow log surfaces the new semantics immediately.

D-15 reference: this restores the invariant "deploy.yml smoke must prove the new revision serves" which was violated by the pre-fix step. Per UAT Gap 10.C recommendation, this is Option A + Option C combined as belt-and-suspenders.
  </action>
  <verify>
    <automated>cd /Users/adrian/Developer/job-rag &amp;&amp; python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/deploy-api.yml')); steps=d['jobs']['build-and-deploy']['steps']; smoke=[s for s in steps if 'smoke' in (s.get('name','') or '').lower() or 'health' in (s.get('name','') or '').lower()][-1]; body=smoke['run']; required=['az containerapp revision list','az containerapp revision show','properties.fqdn','properties.runningState','sort_by','createdTime','ActivationFailed','set -euo pipefail','NEW_REVISION','REV_FQDN']; missing=[t for t in required if t not in body]; sys.exit(0 if not missing else (print('MISSING tokens:',missing) or 1))"</automated>
  </verify>
  <done>
- `.github/workflows/deploy-api.yml` parses as valid YAML.
- The smoke step's `run:` body contains all of: `az containerapp revision list`, `az containerapp revision show`, `properties.fqdn`, `properties.runningState`, `sort_by`, `createdTime`, `ActivationFailed`, `set -euo pipefail`, `NEW_REVISION`, `REV_FQDN`.
- The smoke step's `run:` body does NOT contain the old `properties.configuration.ingress.fqdn` query (the canonical-FQDN poll is fully replaced, not appended).
- Total poll budget visible in the body is between 120s and 180s inclusive (e.g. 30 iterations × 5s = 150s).
- The step name is updated to reflect new semantics (mentions "per-revision" and/or "runningState").
- No other workflow step is modified — `git diff .github/workflows/deploy-api.yml` shows changes only inside the smoke step.
  </done>
</task>

<task type="auto">
  <name>Task 2: Local syntax + dry-render validation</name>
  <files>(no file changes — validation only)</files>
  <action>
Run two validations to catch shape errors before this hits a real workflow run:

1. **YAML parse + step structure:**
   ```bash
   python3 -c "
   import yaml
   with open('.github/workflows/deploy-api.yml') as f:
       d = yaml.safe_load(f)
   steps = d['jobs']['build-and-deploy']['steps']
   names = [s.get('name','<unnamed>') for s in steps]
   print('Steps:', names)
   assert any('per-revision' in (n or '').lower() or 'runningstate' in (n or '').lower() for n in names), 'New smoke step name missing'
   smoke = [s for s in steps if 'per-revision' in (s.get('name','') or '').lower() or 'runningstate' in (s.get('name','') or '').lower()][-1]
   assert 'run' in smoke, 'Smoke step has no run block'
   body = smoke['run']
   assert 'set -euo pipefail' in body
   assert 'az containerapp revision list' in body
   assert 'az containerapp revision show' in body
   assert 'properties.runningState' in body
   assert 'properties.fqdn' in body
   assert 'ActivationFailed' in body
   print('OK')
   "
   ```

2. **Shell `bash -n` syntax check on the extracted run body:**
   ```bash
   python3 -c "
   import yaml
   d = yaml.safe_load(open('.github/workflows/deploy-api.yml'))
   steps = d['jobs']['build-and-deploy']['steps']
   smoke = [s for s in steps if 'per-revision' in (s.get('name','') or '').lower() or 'runningstate' in (s.get('name','') or '').lower()][-1]
   open('/tmp/smoke_body.sh','w').write(smoke['run'])
   " && bash -n /tmp/smoke_body.sh && echo "shell syntax OK" && rm /tmp/smoke_body.sh
   ```

Both must succeed before the task is done. Bash `-n` will NOT catch logic errors but WILL catch unbalanced quotes, missing `fi`/`done`, or stray characters — the most common YAML-embedded-shell footguns.

Note: We cannot actually run the workflow end-to-end without pushing to master and burning a real deploy. End-to-end validation is implicit in the NEXT real push (or a deliberate no-op push after this lands) — out of scope for this quick task. Document this expectation in the SUMMARY.
  </action>
  <verify>
    <automated>cd /Users/adrian/Developer/job-rag &amp;&amp; python3 -c "
import yaml
d = yaml.safe_load(open('.github/workflows/deploy-api.yml'))
steps = d['jobs']['build-and-deploy']['steps']
smoke = [s for s in steps if 'per-revision' in (s.get('name','') or '').lower() or 'runningstate' in (s.get('name','') or '').lower()][-1]
body = smoke['run']
for tok in ['set -euo pipefail','az containerapp revision list','az containerapp revision show','properties.runningState','properties.fqdn','ActivationFailed','NEW_REVISION','REV_FQDN','sort_by','createdTime']:
    assert tok in body, f'missing: {tok}'
open('/tmp/smoke_body.sh','w').write(body)
" &amp;&amp; bash -n /tmp/smoke_body.sh &amp;&amp; rm /tmp/smoke_body.sh &amp;&amp; echo PASS</automated>
  </verify>
  <done>
- `python3 yaml.safe_load` on the workflow file succeeds.
- All 10 required tokens present in the smoke step body.
- `bash -n` on the extracted run body returns 0 (no syntax errors).
- Tmp file `/tmp/smoke_body.sh` cleaned up.
  </done>
</task>

</tasks>

<verification>
- YAML parses cleanly via `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-api.yml'))"`.
- All required Azure CLI commands and JMESPath fragments are present in the smoke step body (see Task 2 automated check).
- `bash -n` confirms the shell body has no syntax errors.
- `git diff .github/workflows/deploy-api.yml` shows changes confined to the smoke step — no drift into other steps.
- End-to-end behavioural verification (real failed-activation deploy → workflow exits 1) is OUT OF SCOPE for this quick task and will land naturally on the next real push to master that exercises a fresh revision. The SUMMARY should call this out.
</verification>

<success_criteria>
- All 6 `must_haves.truths` are encoded in the revised workflow step.
- Both tasks' `<automated>` verifications pass.
- D-15 is restored at the code surface (deploy.yml smoke now provably distinguishes "new revision is alive" from "any revision is alive").
- The change is a single-file diff against `.github/workflows/deploy-api.yml`; no other repo file is touched.
</success_criteria>

<output>
After completion, create `.planning/quick/260519-ids-fix-gap-10-c-deploy-api-yml-smoke-check-/260519-ids-SUMMARY.md` capturing:
- The exact diff (before/after) of the smoke step.
- Confirmation of both automated verifications (paste the PASS output).
- Explicit note that end-to-end validation requires a subsequent real master push (or deliberate trivial commit) to exercise the new path; the next deploy-api.yml run is the live proof point.
- Cross-reference to Gap 10.C in `.planning/phases/03-infrastructure-ci-cd/03-UAT.md` (status should flip from `failed` → `passed` once a subsequent real deploy is observed to either succeed cleanly or fail loudly on the new probe).
- Cross-reference to the still-open Gap 10.B incident (the alembic-fix image `369000784` still needs to actually be deployed to prod once this fix is in place — that is OUT OF SCOPE here but blocked by it being resolved first).
</output>
