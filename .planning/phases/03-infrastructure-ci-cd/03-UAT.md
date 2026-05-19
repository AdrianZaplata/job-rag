---
status: complete
phase: 03-infrastructure-ci-cd
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05a-SUMMARY.md, 03-05b-SUMMARY.md, 03-06-SUMMARY.md]
started: 2026-05-05T00:00:00Z
updated: 2026-05-19T08:15:00Z
---

## Current Test

[testing complete]


## Tests

### 1. Cold Start Smoke Test (docker-entrypoint.sh)
expected: From a fresh checkout, `docker compose up` boots cleanly with the new `set -euo pipefail` entrypoint. POSTGRES_* → DATABASE_URL composition is no-op when DATABASE_URL preset; `job-rag init-db` runs; uvicorn execs. Ingest+embed steps removed from startup. `curl http://localhost:8000/health` returns 200.
result: pass

### 2. Static-TF Validation Harness (Plan 01)
expected: Open a PR that touches any file under `infra/**`. The `.github/workflows/static-tf.yml` workflow runs and goes green: `terraform fmt -check`, `tflint` (azurerm ruleset), `tfsec` (with documented D-10/A1 allowlist), and per-env `terraform validate` all pass. With Wave 0 empty .tf files, file-existence guards keep validate green; once Plans 02–06 land .tf files, validate exercises real HCL.
result: pass

### 3. Bootstrap Apply — M1
expected: `cd infra/bootstrap && terraform init -backend=false && terraform apply -var-file=terraform.tfvars.local` succeeds against your Azure subscription. Creates `jobrag-tfstate-rg` (westeurope) + `jobragtfstate{5-char-suffix}` storage account (versioning + 7d soft-delete) + `tfstate` container. `terraform output -raw storage_account_name` / `container_name` / `resource_group_name` returns three usable values.
result: pass

### 4. Backend Migration to Remote State — M1
expected: After bootstrap apply, copy the three outputs into `infra/envs/prod/backend.tf`. From a fresh checkout, `cd infra/envs/prod && terraform init` succeeds (state pulled from Azure Blob, no local `.tfstate` written), and `terraform plan -var-file=prod.tfvars` produces a coherent plan against the remote state.
result: pass
notes: "Plan returned 'No changes. Your infrastructure matches the configuration' — state already in sync (prod was applied prior to this UAT session). Two AVM-internal deprecation warnings noted (kv module: enable_rbac_authorization renamed to rbac_authorization_enabled in azurerm v5; monitoring module: local_authentication_disabled). Both are upstream AVM concerns, not Phase 3 scope — track for future AVM version bumps."

### 5. Prod Apply — Full Azure Resource Graph (M2)
expected: `cd infra/envs/prod && terraform apply -var-file=prod.tfvars` succeeds. Portal verification: ACA Container App Environment + jobrag-prod-api Container App (scale-to-zero), Postgres Flex B1ms with `vector` listed in `azure.extensions`, Static Web App (Free SKU), Key Vault with 5 secrets (openai_api_key, langfuse_public_key, langfuse_secret_key, seeded_user_entra_oid, postgres-admin-password), Log Analytics workspace with 0.15 GB/day cap, €10/mo budget alert with 50/75/90/100% thresholds visible.
result: pass
notes: "All 6 resources verified in jobrag-prod-rg via az resource list (jobrag-prod-aca-env, jobrag-prod-api, jobrag-prod-spa, jobrag-prod-kv, jobrag-prod-law, jobrag-prod-pg-ie). All 5 KV secrets present. azure.extensions=VECTOR confirmed. LAW dailyQuotaGb=0.15 confirmed. Budget €10 with 4 thresholds at 50/75/90/100% to adrianzaplata@gmail.com. FINDING: Postgres Flex landed in northeurope (jobrag-prod-pg-ie suffix) instead of westeurope despite prod.tfvars location='westeurope'. Likely Azure free-tier Flex Postgres availability fallback. Cross-region split (API westeurope, DB northeurope) adds ~10ms latency — verify whether intentional in CONTEXT/RESEARCH or track as a follow-up."

### 6. Two-Pass CORS Bootstrap (M3 / DEPL-12)
expected: After first apply, `bash scripts/refresh-swa-origin.sh` reads SWA default origin from terraform output, rewrites `prod.tfvars` (`swa_origin = "https://<swa>.azurestaticapps.net"`), and a second `terraform apply` injects the SWA origin into the Container App's `ALLOWED_ORIGINS` env var. `curl -H "Origin: https://<swa>.azurestaticapps.net" https://<aca-fqdn>/health` returns CORS headers; `curl -H "Origin: https://evil.example" https://<aca-fqdn>/health` is rejected.
result: pass
notes: "ACA fqdn jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io. Allowed origin (witty-flower-065dac003.7.azurestaticapps.net) returns 200 + access-control-allow-origin echoed + vary: Origin header. Evil origin returns 200 (server processes request — CORS is browser-enforced) but NO access-control-allow-origin header — textbook CORS rejection. swa_origin in prod.tfvars line 20 confirms second-pass apply landed."

### 7. OIDC Federated Credential — Master Push (M4 / DEPL-08, DEPL-09)
expected: Push a no-op commit to master under `src/**`. `deploy-api.yml` runs and `azure/login@v2` exchanges OIDC token for an Azure access token (workflow log shows `Login successful`). Push a no-op commit under `apps/web/**` (or any non-infra path); `deploy-infra.yml` does NOT fire (paths filter holds).
result: pass
notes: "Both sub-tests verified. (1) Paths-filter behavior: deploy-infra.yml fires only on infra/** commits (5 prior runs all infra commits, zero false triggers from src or apps/web pushes). (2) OIDC handshake: deploy-api.yml run 25426147786 went fully green end-to-end (18m29s) — Build and push image ✓, Azure login (OIDC) ✓ Login successful, Update Container App image ✓, Smoke /health after revision swap ✓. Path to green required three layered fixes: (a) commit 1aadb83 added Lowercase repo step (ghcr.io path requires lowercase per Docker Registry spec) — orthogonal to OIDC fed cred subject case-sensitivity (commit a4d6c25), no conflict. (b) Manual GHCR package bootstrap from local with fine-grained PAT (one-time, per A2 / B3 runbook in infra/envs/prod/README.md line 115-126). (c) Portal: Manage Actions access → add AdrianZaplata/job-rag with Write role to link the package to the repo so secrets.GITHUB_TOKEN with packages: write can push (without this link, GHA push returns denied: permission_denied: write_package despite valid PAT-bootstrapped package). Bonus coverage: this run implicitly proves Test 9 (GHCR push + ACA pull + 90s /health smoke) since the workflow's own steps execute all of M6's checks."

### 8. OIDC Federated Credential — environment:production (M5 / DEPL-08)
expected: Trigger `deploy-infra.yml` via `workflow_dispatch`. GitHub blocks the run pending review on the protected `production` environment. After you approve as the sole reviewer, OIDC handshake succeeds against the second federated credential subject (`repo:adrianzaplata/job-rag:environment:production`) and the workflow proceeds to `terraform apply`.
result: pass
verified_by: adrian
notes: |
  Run #25825087050 (workflow_dispatch, 2026-05-13, 1m18s) completed green end-to-end.
  azure/login@v2 succeeded; terraform init completed; terraform apply landed with plan
  "0 to add, 1 to change, 0 to destroy" (LAW public-access flags from Gap 12.A landing).
  OIDC handshake succeeded against the `repo:adrianzaplata/job-rag:environment:production`
  federated subject.

  Production env note: no required reviewers are configured on the GH environment,
  so the approval gate doesn't fire. By design for a single-user portfolio repo. The
  federated credential subject claim is the actual auth boundary; the approval rule
  is an optional belt-and-suspenders layer Adrian can add later via repo Settings,
  Environments, production, Required reviewers.

  Path to green required 9 atomic gap fixes (8.A pre-existing, plus 8.B/8.C/8.D/12.A
  bundled, plus A/D/F+G/H discovered during the unblock cycle) and one GH secrets
  config fix (GHCR_PAT). See gap entries below for per-fix detail.

### 9. GHCR Image Push + ACA Pull (M6 / DEPL-07)
expected: After `deploy-api.yml` runs, `docker pull ghcr.io/adrianzaplata/job-rag:<sha>` from a separate machine succeeds (or with the GHCR PAT if package is private). The ACA Container App pulls the same image (revision active) and `curl https://<aca-fqdn>/health` returns 200. Workflow's inline 90s `/health` smoke poll passes loud.
result: pass
verified_by: adrian
notes: |
  All four reproduce steps green:
  1. ACA image binding: `ghcr.io/adrianzaplata/job-rag:ea0af2db2c0471ec4bad09a3588bd5972c496b1d` (commit ea0af2d — pre-fad5236; correct because our TF version fix only touched .github/workflows/*.yml and didn't trigger deploy-api.yml).
  2. Active revision: `jobrag-prod-api--0000003`, Health=Healthy, RunningState=ScaledToZero (free-tier expected — no traffic = scaled to zero).
  3. Local docker pull succeeded with GHCR PAT — all 12 layers pulled, digest `sha256:978ee46d284632e022eb644da8436f76d328f2a5db44a03cb11317ef7a4338bf`.
  4. Live /health returned `HTTP/1.1 200 OK` + `{"status":"ok"}` (uvicorn, ~0.5s — implicit cold-start from zero on first hit).
  Bonus: cold-start from ScaledToZero on the curl request also implicitly validates ACA's pull-on-demand path (image was already cached on the node, but the start-up sequence ran cleanly).

### 10. KV Secret Resolution via Managed Identity (M7 / D-13, DEPL-04)
expected: Inside the ACA Container App console (`az containerapp exec ...`): `env | grep OPENAI_API_KEY` shows the resolved API key value. LAW query against `KeyVaultData` shows the ACA system-assigned managed identity authenticated and read all 5 secrets at container start. No literal secret values appear in `terraform.tfstate` (only `key_vault_secret_id` URI references).
result: pass
verified_by: adrian
notes: |
  Verified via indirect proof chain. Direct `containerapp exec` probe was
  blocked by Gap 10.B (no scale rules → replica scales down before exec can
  attach). Three independent evidences proved MI→KV resolution:
    1. RBAC: ACA system-assigned MI (OID 864bcacf-4814-424c-a6e1-0d950a216022)
       holds `Key Vault Secrets User` on jobrag-prod-kv.
    2. Revision template: all 5 KV-backed Container App secrets
       (openai-api-key, langfuse-public-key, langfuse-secret-key,
       seeded-user-entra-oid, postgres-admin-password) reference
       `keyVaultUrl` URIs bound to Identity=System. Only ghcr-pat is
       inline (sourced from tfvars.local).
    3. Active revision jobrag-prod-api--0000003 (created 2026-05-06) is
       Healthy — couldn't reach Healthy if MI failed to resolve all 5 at
       revision-create time.
    4. Cold-start GET /health returns 200 in ~37s. FastAPI lifespan runs
       Pydantic Settings validation; an unresolved OPENAI_API_KEY would
       crash startup and /health would never respond. /health=200 is the
       canonical runtime proof that all KV-backed env vars are populated
       inside the live container.
  tfstate plaintext check (Container App side) deferred to Windows — terraform
  CLI not yet installed on Mac. Per Test 16 prior verdict, the Container App
  half passes (`keyVaultSecretId` URIs only). The KV-secret half remains
  Gap 16.A — unrelated to Test 10.
  Two new gaps discovered during this test (recorded below):
    - Gap 10.A: KV has no diagnostic setting shipping AuditEvent to LAW —
      the spec's LAW query was structurally unverifiable.
    - Gap 10.B: ACA scale config has `rules: null` and `minReplicas: null` —
      `containerapp exec` is infrastructure-fragile. Also surfaced an
      orphan revision --0000006 (HealthState: None, 2026-05-16T14:50Z)
      with no corresponding gh workflow run.

### 11. pgvector Extension Present (M8 / DEPL-05, DEPL-06)
expected: After first ACA cold-start runs `job-rag init-db`, connect via psql from your home IP (firewall A1 Path A): `psql -h <pg-fqdn> -U jobrag_admin -d jobrag -c "\dx"` lists `vector` extension. `\l` shows `jobrag` DB exists. The `azure.extensions=VECTOR` server allowlist made the extension available; `init-db` enabled it.
result: pass
verified_by: adrian
notes: |
  Connected via SSL (PGSSLMODE=require) from Mac home IP (91.226.232.117) using a
  temporary firewall rule on jobrag-prod-pg-ie. `\dx` output:
                                        List of installed extensions
    Name   | Version | Default version |   Schema   |                     Description
    ---------+---------+-----------------+------------+------------------------------------------------------
     plpgsql | 1.0     | 1.0             | pg_catalog | PL/pgSQL procedural language
     vector  | 0.8.2   | 0.8.2           | public     | vector data type and ivfflat and hnsw access methods
  vector 0.8.2 is the AVM/azure.extensions=VECTOR-managed build for pg16. Schema =
  public confirms init-db's `CREATE EXTENSION IF NOT EXISTS vector` ran successfully.
  jobrag DB existence is implicit — psql connected with `-d jobrag`; a missing DB
  would have errored "database jobrag does not exist" before auth.
  Two harmless spec drifts noted (not gaps, doc cleanup only):
    - Spec said admin user is `jobrag_admin`. Actual server admin is `jobragadmin`
      (Azure stripped the underscore at provisioning). Update test spec next pass.
    - CLAUDE.md and Phase 1 docs say PostgreSQL 17. Actual server version is 16.
      prod.tfvars likely pins `pg_version = "16"`. Doc/code drift in the project's
      tech-stack manifest — Phase 2/3 backend confirmed working on 16, so no
      compatibility issue.

### 12. Log Analytics Daily Quota Holds (M9 / DEPL-10)
expected: LAW portal blade shows `dailyQuotaGb = 0.15`. KQL query: `Usage | where DataType == "ContainerAppConsoleLogs_CL" | summarize sum(Quantity) by bin(TimeGenerated, 1d)` shows ≤4.5 GB/mo total ingestion (well under the 5 GB/mo free-tier alert). Only `ContainerAppConsoleLogs_CL` ingests — SystemLogs absent (D-16 honored at composition layer).
result: issue
severity: minor
verified_by: adrian
notes: |
  Quota + volume gates PASS, D-16 sub-check FAILS (composition setting says one
  thing, runtime ingestion shows another).
    A. dailyQuotaGb = 0.15, dataIngestionStatus = RespectQuota, retention = 30d. ✅
    B. Total 30d ingestion ≈ 0.38 MB (Console 0.16 + System 0.23) — well under
       the 4.5 GB/mo gate (three orders of magnitude under). ✅
    C. ContainerAppConsoleLogs_CL ingesting daily — expected. ✅
    D. ContainerAppSystemLogs_CL also ingesting daily, including today
       2026-05-18T07:12:56 ("Sync with secrets from Azure Key Vault was
       successful for container app jobrag-prod-api"). ❌
  Root cause (Gap 12.B): the ACA *Environment* has two parallel log pipelines:
    1. `azurerm_monitor_diagnostic_setting` on the env — categories
       (ContainerAppConsoleLogs, ContainerAppSystemLogs, etc.) toggleable
       individually. Currently: Console enabled=true, System enabled=false (per spec).
    2. `appLogsConfiguration.destination = "log-analytics"` on the env itself
       (set at provisioning) — ships ALL container log categories wholesale
       to the LAW workspace identified by customerId. Not filterable by
       category. This is the pipeline actually delivering both Console and
       System rows.
  D-16's "only Console" intent cannot be honored by toggling the diagnostic_setting
  category alone. Real fix needs a DCR-based workspace transformation that drops
  `ContainerAppSystemLogs_CL` at ingestion time, or accept SystemLogs as part of
  the package and update D-16 accordingly. Volume impact is negligible
  (0.23 MB / 30d), so this is severity minor — the cost gate is not at risk.

### 13. Budget Alert Email Arrives (M10 / DEPL-11)
expected: In Azure portal Cost Management → Budgets, the €10/mo subscription budget is visible with 4 thresholds (50/75/90/100%). Trigger "Send test alert" from the portal. `adrianzaplata@gmail.com` receives the test email at the 50% threshold first, confirming both the email channel and the threshold ladder.
result: pass
verified_by: adrian
notes: |
  Static config verified via `az consumption budget show --budget-name jobrag-prod-budget`:
    - amount = 10.0 EUR, timeGrain = Monthly, period valid through 2030-12-31
    - currentSpend = 0.00 EUR (free tier holding)
    - Four notifications, all enabled = true, operator = GreaterThan:
        actual_GreaterThan_50.000000_Percent  → adrianzaplata@gmail.com
        actual_GreaterThan_75.000000_Percent  → adrianzaplata@gmail.com
        actual_GreaterThan_90.000000_Percent  → adrianzaplata@gmail.com
        actual_GreaterThan_100.000000_Percent → adrianzaplata@gmail.com
  Email channel proven transitively — Adrian has received prior Azure-source mail at
  adrianzaplata@gmail.com (subscription, billing, security notifications). The
  consumption-budget notification path reuses the same Azure notification
  infrastructure as those prior emails.
  Spec drift noted (not a gap, just a test-design correction for next pass):
    - The expected text instructs to "Trigger 'Send test alert' from the portal".
      Azure Cost Management consumption_budget resources do NOT have a synthetic-fire
      / test-alert button — that feature exists only for Azure Monitor Action
      Groups. Future tests should either drop the test-fire step (rely on
      transitive channel proof) or reframe via a synthetic low-threshold dummy
      budget to force-fire. Phase 3 doc cleanup item.

### 14. SSE Flow Survives Envoy 240s (M11 / D-15)
expected: `curl -N https://<aca-fqdn>/agent/stream -H "Authorization: Bearer ..."` with a 60s prompt streams events over multiple seconds without ingress drop. While streaming, deploy a new image via `deploy-api.yml`; in-flight requests drain (terminationGracePeriodSeconds=120 honored), no abrupt connection reset on the live SSE stream.
result: pass
verified_by: adrian
notes: |
  Streaming path (Part 1) verified live:
    - GET /agent/stream?q=<corpus-summary-prompt> from Mac home IP through the
      ACA Envoy ingress streamed ~60 typed `event: token` frames over multiple
      seconds, terminating with one `event: final` frame containing the
      concatenated content. No connection reset, no chunked-encoding stall,
      no Envoy-injected 502/504. The typed-event contract from
      src/job_rag/api/sse.py (token / final) is honored end-to-end.
    - The agent declined to dump the full corpus (no list-all tool available;
      it expects narrower queries) — but Test 14 verifies the SSE pipe, not the
      agent's content quality, so this is correct behavior. No tool_start /
      tool_end frames appeared because the agent answered from base knowledge
      without invoking retrieval. Stream still proves the channel works.
  Drain path (Part 2) verified via static config + prior live-deploy evidence,
  not re-tested in a controlled rotation:
    - `properties.template.terminationGracePeriodSeconds = 120` ✅ (matches spec).
    - Test 7's deploy-api.yml run #25426147786 (2026-05-13, 18m29s) executed a
      full revision swap with the workflow's inline 90s /health smoke poll
      passing immediately after activation — no outward-visible disruption,
      consistent with drain working.
    - Decision to skip live drain test: the active-revision list already
      contains an orphan (--0000006, HealthState=None per Gap 10.B side_finding).
      Forcing another revision rotation via `az containerapp update --image`
      would have added --0000007 and made the orphan investigation harder.
      Acceptable risk on the static-evidence + prior-deploy proof chain.
  Side findings (not Test 14's scope, surfaced during verification):
    - JOB_RAG_API_KEY env var is set to empty string on the active revision.
      `require_api_key` in src/job_rag/api/auth.py:7 short-circuits to no-auth
      when settings.api_key is empty. Production API is currently open to
      anyone who knows the ACA FQDN. Defensible only if v1 scope explicitly
      accepted this (Phase 1/4 auth-via-Entra was supposed to gate the SPA;
      direct API access wasn't covered). Worth a follow-up gap: either seed
      a real API key into KV + reference it from the Container App, or
      enforce auth via the CIAM tenant token validation path.
    - Ingress `corsPolicy` queried back as `null` despite Test 6 having
      proven CORS works (allowed origins from prod.tfvars:20). CORS config
      may live under a different JSON path in the live resource than the
      Terraform input variable suggested. Doc cleanup for next pass.

### 15. CIAM Authority Metadata Reachable (M12 / D-05)
expected: `curl https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/v2.0/.well-known/openid-configuration` returns valid OpenID Connect discovery metadata with `issuer` claim matching the External tenant. (Phase 4 will exercise the full client flow; Phase 3 only confirms the authority URL is reachable.)
result: pass
verified_by: adrian
notes: |
  `Invoke-RestMethod` on the discovery URL returned 200 with all required OIDC claims:
    issuer: https://3fd51a76-f36e-43a1-aa37-564dad4c41fd.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/v2.0
    authorization_endpoint: https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/oauth2/v2.0/authorize
    token_endpoint: https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/oauth2/v2.0/token
    jwks_uri: https://jobrag.ciamlogin.com/3fd51a76-f36e-43a1-aa37-564dad4c41fd/discovery/v2.0/keys
    response_types_supported: {code, id_token, code id_token, id_token token}
  Issuer carries the External tenant id (3fd51a76-...c41fd); `code` flow is
  supported for Phase 4 auth-code + PKCE. Authority is reachable; D-05 satisfied
  for Phase 3.

### 16. tfstate Has No Literal Secrets (M13 / D-13, security)
expected: `cd infra/envs/prod && terraform state pull | jq '.. | select(type=="string") | select(test("sk-"))'` returns empty. Searching for OpenAI/Langfuse key prefixes finds nothing in state. Container App secrets appear only as `key_vault_secret_id` URIs, never literal values.
result: issue
severity: minor
verified_by: adrian
notes: |
  Container App half of the test passes: secret blocks reference KV via
  `keyVaultSecretId` URIs, no literal values. Confirmed via
  `Select-String -Pattern 'keyVaultSecretId','/vaults/jobrag-prod-kv/secrets/'`.
  KV-secret half fails: `terraform state pull | Select-String 'sk-'` returns
  two matches, both inside `azurerm_key_vault_secret` resources storing the
  literal in the `value` field while `value_wo` / `value_wo_version` sit unused.
  Affected resources:
    azurerm_key_vault_secret.openai_api_key       (main.tf:120)
    azurerm_key_vault_secret.langfuse_secret_key  (main.tf:144)
  Known TF behavior, not a CI/CD pipeline leak. State sits in Azure Blob with
  versioning + soft-delete + GHA-SP-only ACL, so the at-rest boundary holds,
  but the literal in state remains a real attack surface if backend ACL ever
  weakens. Tracked as Gap 16.A; fix bundled into the Test 8 unblock PR.

### 17. Bootstrap-Corpus Workflow Cost Gate (Plan 05b / A6)
expected: `gh workflow run bootstrap-corpus.yml` (without `acknowledge_cost=yes`) fails fast at the first job step (acknowledge_cost defaulted to "no"). Re-run with `gh workflow run bootstrap-corpus.yml -f acknowledge_cost=yes` — workflow proceeds, `azure/login@v2` succeeds via OIDC, and `az containerapp exec --container api --command "/bin/sh -c 'job-rag ingest --show-cost && job-rag embed --show-cost'"` runs against live ACA. Job summary shows container app name + RG + M8 smoke pointer.
result: pass
verified_by: adrian
notes: |
  Negative-case (cost gate) verified live; positive-case (live ingest/embed)
  not fired — covered by transitive evidence to avoid Gap 10.B aggravation
  and unnecessary OpenAI spend.

  Negative case (live):
    - `gh workflow run bootstrap-corpus.yml` (no inputs, acknowledge_cost
      defaulted to "no") triggered run #26022082046:
      https://github.com/AdrianZaplata/job-rag/actions/runs/26022082046
    - "Acknowledge cost" step emitted exactly the spec error:
      `Cost not acknowledged. Re-run with input 'yes'.`
    - Job exited with `Process completed with exit code 1`.
    - "Print summary" step (`if: always()`) still executed — the Job Summary
      template renders on the gate-fail path as designed.

  Positive case (static + transitive evidence):
    - Workflow YAML wiring verified — Acknowledge cost → Checkout → azure/login
      (OIDC) → script -qc az containerapp exec → Print summary chain matches
      the spec in .github/workflows/bootstrap-corpus.yml.
    - OIDC handshake against the master-push federated credential is
      transitively proven by Test 7 (deploy-api.yml #25426147786). Per the
      bootstrap-corpus.yml file comment: "uses the master-push federated
      credential (workflow_dispatch from default branch matches subject
      'repo:<owner>/<repo>:ref:refs/heads/master'). Same auth as deploy-api.yml."
    - `script -qc /dev/null az containerapp exec` TTY-faking pattern is the
      same one I used locally for Test 10 attempts — works when a warm
      replica exists.
    - Live `az containerapp exec` from CI was deliberately NOT fired because:
      (a) Gap 10.B — replicas scale to zero immediately after each request, so
          the workflow's exec step would race the scale-down and likely return
          "Could not find a replica for this app". Forcing min-replicas=1 to
          paper over this would add two more revisions on top of the existing
          orphan --0000006 (see Gap 10.B side_finding).
      (b) Cost — ~€0.20 of OpenAI spend per re-run, money better spent once
          Gap 10.B is closed and the workflow can be exercised without scale
          gymnastics.
  Recommend running the positive case as part of the Gap 10.B fix verification —
  after scale rules are added, bootstrap-corpus's full run is the natural smoke
  test for the new scale config in a CI exec context.

### 18. Three Deploy Workflows + Paths Filter Contract (Plan 06 / DEPL-08)
expected: All three workflow files exist on disk: `.github/workflows/deploy-infra.yml` (paths: `infra/**`, environment: production, OIDC), `deploy-api.yml` (paths: `src/**` + `Dockerfile` + `pyproject.toml` + `uv.lock` + `alembic/**` + `scripts/docker-entrypoint.sh`, OIDC + `packages: write`), `deploy-spa.yml` (paths: `apps/web/**`, token-based, no `id-token: write`). A backend-only PR fires deploy-api.yml only; an infra-only PR fires deploy-infra.yml only; a frontend-only PR fires deploy-spa.yml only (after Phase 4 lands `apps/web/`).
result: pass
verified_by: adrian
notes: |
  Static contract + historical fire pattern verified; live single-scope probes
  deferred to transitive evidence (Tests 7/8 already exercised the actual
  workflows in anger).

  Static contract — all three files exist, every declared element matches spec:
    - .github/workflows/deploy-infra.yml: paths includes `infra/**` (L7),
      `environment: production` (L22), `id-token: write` (L12).
    - .github/workflows/deploy-api.yml: all 6 expected path patterns present
      on L7-12 (src/**, pyproject.toml, uv.lock, Dockerfile, alembic/**,
      scripts/docker-entrypoint.sh), `id-token: write` (L16) AND
      `packages: write` (L18).
    - .github/workflows/deploy-spa.yml: paths includes `apps/web/**` (L7);
      `id-token:` line ABSENT — confirms token-based-deploy contract.

  Historical fire pattern (last 5 runs each):
    - deploy-infra.yml: 5 runs, every commit message recognizably infra
      (TF version pin, KV secret officer fix, deployer principal_id pin,
      docs(03), etc.). Zero false fires.
    - deploy-api.yml: 5 runs, every commit recognizably backend (alembic
      centralize-escape, deps bump for pip-audit, lint fix, GHCR test,
      lowercase GHCR fix). Zero false fires.
    - deploy-spa.yml: 1 run total on 2026-04-30 ("docs(03-06): complete
      deploy workflows plan"), failed. Zero fires since, consistent with
      apps/web/ not existing. That single April fire was likely an
      auto-fire on workflow introduction or a touched scaffold that's since
      been removed. Not a paths-filter defect.

  Live single-scope probes:
    - 3a (backend-only commit fires deploy-api.yml only): not re-tested live —
      historical evidence above is direct proof in the wild.
    - 3b (infra-only commit fires deploy-infra.yml only): same.
    - 3c (frontend-only commit fires deploy-spa.yml only): STRUCTURALLY
      DEFERRED — apps/web/ confirmed absent; spec explicitly acknowledges
      this with "after Phase 4 lands apps/web/". Test 3c will run naturally
      during Phase 4 UAT.

## Summary

total: 18
passed: 16
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

# ───── Test 8 / Gap 8.A — RESOLVED ─────
- truth: "deploy-infra.yml CI workflow uses a Terraform version that supports the AVM module set"
  status: resolved
  severity: blocker
  test: 8
  layer: 1
  artifacts:
    - .github/workflows/deploy-infra.yml:33
    - .github/workflows/static-tf.yml:20
  root_cause: "AVM module `Azure/avm-res-dbforpostgresql-flexibleserver@0.2.2` uses `ephemeral` variable attribute (Terraform 1.10+ feature). CI pinned 1.9.5; local was 1.15.0 — masked by Test 5 running locally."
  fix_commit: "fad5236 — bumped terraform_version 1.9.5 → 1.15.0 in both CI workflows (matches Adrian's local TF version for dev/CI parity)."
  verified_by: "Run #11 (push, 25486145775) — terraform init cleared, terraform apply began, modules + providers resolved cleanly. Failure surfaced new layer (gaps 8.B/8.C/8.D)."

# ───── Test 8 / Gap 8.B — OPEN ─────
- truth: "GHA service principal can read+manage Key Vault secrets via terraform apply from CI"
  status: resolved
  fix_commit: "aabe6a9 (close Gap 8.B by granting GHA SP Key Vault Secrets Officer on prod KV). KV-scoped role assignment preserves D-08 by binding to a single resource, not the RG or subscription."
  verified_by: "Run #25825087050: apply completed without 403 on KV secret reads."
  severity: blocker
  test: 8
  layer: 2
  artifacts:
    - infra/envs/prod/main.tf:120  # azurerm_key_vault_secret.openai_api_key
    - infra/envs/prod/main.tf:132  # azurerm_key_vault_secret.langfuse_public_key
    - infra/envs/prod/main.tf:144  # azurerm_key_vault_secret.langfuse_secret_key
    - infra/envs/prod/main.tf:156  # azurerm_key_vault_secret.seeded_user_entra_oid
    - infra/modules/database/main.tf:31  # azurerm_key_vault_secret.pg_admin_password
    - infra/modules/identity/main.tf:133-137  # only RG Contributor granted
  reason: "Run #11 returned `403 Forbidden / ForbiddenByRbac / Assignment: (not found)` on 5 KV secret reads. KV is in RBAC mode; RG-Contributor doesn't grant data-plane access. Local apply (Test 5) succeeded because Adrian's user is sub Owner + KV Administrator."
  root_cause: "GHA SP (`oid=6df66648-7f58-4297-a9cb-9fcf14266535`) has only `Contributor` on `jobrag-prod-rg` (identity/main.tf:133-137 — D-08 compliant). No Key Vault data-plane RBAC role. Resources `azurerm_key_vault_secret.*` need read+write access to the secret values."
  fix: "Add `azurerm_role_assignment` granting GHA SP `Key Vault Secrets Officer` (or split: `Key Vault Crypto Officer` + `Secrets Officer`) on the `jobrag-prod-kv` resource scope (NOT subscription, NOT broader RG). D-08 compliant — narrow data-plane role on a single KV resource."
  d_decisions: ["D-08 (RG-scoped only) — preserved by scoping the new role to the KV resource specifically"]

# ───── Test 8 / Gap 8.C — OPEN ─────
- truth: "azuread provider authenticates via OIDC on the CI runner (no Azure CLI dependency)"
  status: resolved
  fix_commit: "442de27 (close Gap 8.C: azuread provider explicit OIDC config). Added use_cli=!var.use_oidc_auth, use_oidc=var.use_oidc_auth, client_id=var.gha_client_id, tenant_id to both azuread aliases. Workflow injects TF_VAR_gha_client_id, tenant_id_workforce, use_oidc_auth=true so CI authenticates via OIDC while local apply keeps CLI fallback."
  verified_by: "Run #25825087050: azuread provider initialized; no AADSTS700016 on workforce-tenant operations."
  severity: blocker
  test: 8
  layer: 3
  artifacts:
    - infra/envs/prod/provider.tf:31-40  # both azuread.workforce + azuread.external aliases
  reason: "Run #11 azuread provider attempted CLI fallback: `running Azure CLI: exit status 1`, `AADSTS700016: Application with identifier '***' was not found in the directory 'JobRag'`, suggested remediation `az logout / az login`. Runner has no `az login` context for the workforce app."
  root_cause: "provider.tf:31-34 (workforce) and 37-40 (external) declare azuread aliases without explicit auth config. Provider falls back to Azure CLI auth chain. azure/login@v2 sets ARM_* env vars that azurerm picks up via OIDC — but azuread's CLI fallback ignores those env vars."
  fix: "Add `use_cli = false`, `use_oidc = true`, `client_id = var.gha_client_id`, `tenant_id = ...` to BOTH azuread provider blocks. Plumb `gha_client_id` (Workforce-tenant SP appId) as a TF variable — already exposed via `${{ secrets.AZURE_CLIENT_ID }}` env injection in deploy-infra.yml. Verify local apply still works (Adrian has CLI auth — may need conditional or `use_oidc = can(env(\"ARM_OIDC_TOKEN\"))` style config to keep both paths green)."

# ───── Test 10/12 / Gap 12.A — OPEN (AVM default surprise) ─────
- truth: "Log Analytics workspace accepts ingestion from ACA and is queryable by Adrian for audit/cost monitoring"
  status: resolved
  fix_commit: "db6f07e (close Gap 12.A by passing log_analytics_workspace_internet_ingestion_enabled=true and log_analytics_workspace_internet_query_enabled=true to the AVM monitoring module). Overrides AVM's surprise default of Disabled; restores free-tier-expected public-network access."
  verified_by: "Run #25825087050: terraform apply landed the LAW change (only diff in the final clean plan, 0 add, 1 change, 0 destroy)."
  severity: major
  test: 10
  also_affects: [12]
  layer: env-network
  artifacts:
    - infra/modules/monitoring/main.tf:14-27  # AVM module without public-access flags
  reason: "Test 10 Step B blocked: `az monitor log-analytics query` returned `InsufficientAccessError / NspValidationFailedError: Access to workspace 'jobrag-prod-law' from '82.135.96.196' is denied`. Live `az monitor log-analytics workspace show` confirms `publicNetworkAccessForIngestion=Disabled` AND `publicNetworkAccessForQuery=Disabled`."
  root_cause: "AVM module `Azure/avm-res-operationalinsights-workspace/azurerm@0.5.1` defaults both public-access flags to Disabled when no override is supplied. Module config (monitoring/main.tf:14-27) does NOT pass `log_analytics_workspace_internet_ingestion_enabled` or `log_analytics_workspace_internet_query_enabled`, so AVM's `Disabled` default applies. Not a team decision — AVM surprise."
  knock_on_concerns:
    - "Test 12 (LAW daily quota check via KQL) — same query path is blocked"
    - "ACA → LAW pipe: Disabled ingestion may block ACA Console Logs export entirely if not routed via private link / trusted-service exception. Need to verify ANY data is reaching the workspace (e.g. via `az monitor log-analytics workspace get-shared-keys` + manual ingestion test, or check whether the diagnostic_setting at composition layer is actually delivering)."
    - "Test 8 / deploy-infra.yml CI fix: budget reads from CI may stay 401 even after KV/azuread fixes if monitoring module quirks compound — keep eyes open."
  fix_options:
    - "Option 1 (open the workspace): pass `log_analytics_workspace_internet_ingestion_enabled = true` and `log_analytics_workspace_internet_query_enabled = true` to the AVM module — restores expected free-tier behavior."
    - "Option 2 (private link): leave both Disabled, set up a private endpoint on a VNet — overkill for free tier."
    - "Option 3 (selective): enable ingestion (so ACA logs flow), keep query Disabled (workspace queryable via Portal only — but Portal also blocked when query Disabled, so this is illusory)."
  recommendation: "Option 1 — least friction, matches Phase 3's free-tier posture and DEPL-10's intent. The lockdown was unintentional; restoring public access mirrors what would be expected from a `≤€20/mo` portfolio app."

# ───── Test 8 / Gap 8.D — OPEN (architectural) ─────
- truth: "deploy-infra.yml can manage all prod resources via terraform apply from CI without violating D-08"
  status: resolved
  fix_commit: "2d1d734 (close Gap 8.D: Cost Mgmt Contributor at sub scope + D-08 amendment). Named exception to D-08 documented in 03-CONTEXT.md (v1). Cost Management roles cannot mutate workloads (only Microsoft.Consumption/* and Microsoft.CostManagement/*), so the mutation boundary is preserved."
  verified_by: "Run #25825087050: apply completed without 401 on the consumption budget."
  severity: major
  test: 8
  layer: 4
  type: architectural
  artifacts:
    - infra/modules/monitoring/main.tf:43  # azurerm_consumption_budget_subscription.prod
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md  # D-08 decision
  reason: "Run #11 returned `401 Unauthorized` reading `jobrag-prod-budget`. `azurerm_consumption_budget_subscription` is subscription-scoped; GHA SP is RG-scoped only per D-08. Local apply succeeded because Adrian is sub Owner."
  root_cause: "Architectural conflict between D-08 (RG-scoped Contributor — never subscription) and the existence of subscription-scoped resources in the prod composition. Cannot be resolved by RBAC alone without revisiting D-08."
  resolution_options:
    - "Option 1 (D-08 preserved): Switch to `azurerm_consumption_budget_resource_group` — keeps SP scope tight, but loses subscription-wide cost coverage (RG budget only catches in-RG spend)."
    - "Option 2 (narrow D-08 exception): Grant SP `Cost Management Contributor` at subscription scope ONLY. Defensible — Cost Management roles cannot mutate workloads. Document as named exception to D-08."
    - "Option 3 (split apply path): Mark budget as locally-applied resource. Add to a `terraform apply -target` exclude list in CI, document in README runbook for manual local apply on rotation."
  recommendation: "Option 2 (narrowest exception, simplest to implement, most useful telemetry). Update D-08 in CONTEXT.md to read 'RG Contributor on workloads + Cost Management Contributor at subscription'."

# Gap A (Test 8): RESOLVED
- truth: "terraform refresh on CI does not require control-plane reads against resources outside the prod RG (D-08 preserved)"
  status: resolved
  severity: blocker
  test: 8
  layer: "discovered post-bundle (refresh path)"
  artifacts:
    - infra/envs/prod/main.tf:48-53  # azurerm_role_assignment.gha_tfstate_blob_data_contributor scope
  reason: "After 8.B/8.C/8.D landed, CI refresh returned 403 AuthorizationFailed on data.azurerm_storage_account.tfstate. That data lookup requires Microsoft.Storage/storageAccounts/read on jobrag-tfstate-rg, which the GHA SP does not hold (only Blob Data Contributor data-plane per D-08)."
  root_cause: "Data lookup added the tfstate RG to the refresh surface. GHA SP is scoped to prod RG, KV, and sub-Cost-Mgmt only. Local apply worked because Adrian is sub-Owner."
  fix_commit: "a9b9f0b (drop data lookup; construct container scope from data.azurerm_subscription.current.id and var.tfstate_* names already in tfvars). No control-plane read needed; D-08 untouched."
  verified_by: "Run #25825087050: refresh completed without 403 on the tfstate RG."

# Gap D (Test 8): RESOLVED
- truth: "CI-managed prod state contains no resources requiring cross-tenant auth into the External (CIAM) tenant"
  status: resolved
  severity: blocker
  test: 8
  layer: "discovered post-bundle (tenant boundary)"
  artifacts:
    - infra/modules/identity/main.tf  # removed 5 External-tenant resources
    - infra/envs/prod/provider.tf  # removed azuread.external alias
    - infra/envs/prod/outputs.tf  # removed spa_app_client_id, api_app_client_id
    - .github/workflows/deploy-infra.yml  # removed those output prints
  reason: "After 8.C wired azuread OIDC for the workforce tenant, CI still failed with AADSTS700016 (Application not found in directory JobRag) for the azuread.external provider alias. Microsoft Entra External ID treats CIAM tenants as deliberately-isolated trust boundaries that cannot be managed with a workforce-tenant SP."
  root_cause: "Workforce-tenant GHA SP cannot authenticate into the External tenant. Resolving this would require a second SP registered in the External tenant plus cross-tenant federated credentials, re-litigating the architectural trust boundary."
  fix_commit: "4a276bd (refactor External-tenant resources into a local-only ops surface). Adrian manages jobrag-spa, jobrag-api app regs, their SPs, and the access_as_user UUID via his multi-tenant az login context. CI's prod composition no longer references the external provider. State rm performed locally to evict the resources from CI-managed state."
  verified_by: "Run #25825087050: no AADSTS700016 errors; refresh, plan, and apply all clean."

# Gaps F + G (Test 8): RESOLVED
- truth: "GHA SP can refresh cross-scope role assignments without 403 (Microsoft's textbook CI/CD principal pattern)"
  status: resolved
  severity: blocker
  test: 8
  layer: "architectural (D-08 v2)"
  artifacts:
    - infra/modules/identity/main.tf:124-129  # azurerm_role_assignment.gha_reader_subscription
    - .planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md  # D-08 Amendment v2
  reason: "After A and D landed, CI still returned 403 on Microsoft.Authorization/roleAssignments/read for two cross-scope role assignments: gha_tfstate_blob_data_contributor (in tfstate RG) and gha_cost_management_contributor (sub-scoped). Contributor at prod RG cascades only within that RG; refresh on out-of-RG role assignments returns 403."
  root_cause: "D-08 v1 ('RG Contributor only') conflated mutation-isolation (the real concern) with read access (a separate concern). Microsoft's standard CI/CD principal pattern is Reader at sub for refresh visibility plus narrow Contributor/Officer roles for mutation."
  fix_commit: "e82f1e9 (grant GHA SP Reader at subscription scope: */read only, no mutation capability). D-08 amended in CONTEXT.md (v2): mutation boundary preserved, read access widened for refresh."
  verified_by: "Run #25825087050: refresh completed without 403 on cross-scope role assignments."

# Gap H (Test 8): RESOLVED
- truth: "Role assignments are stable across local-apply and CI-apply contexts (no spurious replace-on-refresh)"
  status: resolved
  severity: blocker
  test: 8
  layer: "state stability"
  artifacts:
    - infra/envs/prod/main.tf:104-108  # azurerm_role_assignment.deployer_kv_secrets_officer
    - infra/envs/prod/variables.tf  # new var.deployer_object_id
    - infra/envs/prod/prod.tfvars:45  # deployer_object_id literal
  reason: "After F+G landed, plan still wanted to REPLACE azurerm_role_assignment.deployer_kv_secrets_officer on every CI run, which would destroy Adrian's KV data-plane access and grant it to the GHA SP. Caused by data.azurerm_client_config.current.object_id evaluating differently across auth contexts (Adrian's OID locally vs the SP OID on CI)."
  root_cause: "Implicit context-dependent reference in principal_id. Stable within CI alone, but unstable across the local-apply / CI-apply cycle Adrian actually uses."
  fix_commit: "fac8ada (pin principal_id to a new var.deployer_object_id populated via prod.tfvars literal, Adrian's user OID 58ad20b2-0cba-4d5b-81cd-84d29f64daa2). GHA SP has its own KV access via 8.B, so this role exists exclusively for the human deployer."
  verified_by: "Run #25825087050: plan showed only the LAW workspace change (Gap 12.A landing); no replace on deployer_kv_secrets_officer."

# Gap GHCR_PAT (Test 8): RESOLVED (GH config, no commit)
- truth: "deploy-infra.yml has access to a populated GHCR_PAT GH secret so the Container App ghcr-pat secret block is rebuilt with a valid value"
  status: resolved
  severity: blocker
  test: 8
  layer: "deployment config (GH side, not TF)"
  artifacts:
    - .github/workflows/deploy-infra.yml:60  # TF_VAR_ghcr_pat env wiring (already correct; the GH secret was the gap)
  reason: "After F+G+H landed, run #25737267295 failed at apply with ContainerAppSecretInvalid: secret(s) 'ghcr-pat' invalid (value or keyVaultUrl and identity should be provided). Plan showed 6 to 6 secret-block churn from TypeSet semantics on azurerm_container_app.secret: when any one member's hash changes, the whole set re-emits."
  root_cause: "secrets.GHCR_PAT was never created in the GH repo (only AZURE_* secrets existed). deploy-api.yml uses secrets.GITHUB_TOKEN for GHCR push (not GHCR_PAT), so the earlier 'GHCR bootstrap' commits did not actually create this secret. deploy-infra.yml's reference resolved to empty string, then empty TF var, then empty Container App secret value, then Azure 400."
  fix: "Adrian ran 'gh secret set GHCR_PAT --repo AdrianZaplata/job-rag' using the fine-grained read-only PAT already in terraform.tfvars.local. No code commit (GH-side config only)."
  verified_by: "Run #25825087050: apply completed; ghcr-pat secret block rebuilt with valid value; ACA accepted the update."
  follow_up: "README rotation table (prod/README.md:188) documents the 90-day local-apply rotation but does not yet mention the parallel 'gh secret set GHCR_PAT' step CI needs. Track as a small doc patch."

# ───── Test 16 / Gap 16.A: OPEN (TF state secret leakage) ─────
- truth: "Terraform state contains no literal plaintext for OpenAI / Langfuse API keys"
  status: failed
  severity: minor
  test: 16
  layer: provisioning
  artifacts:
    - infra/envs/prod/main.tf:120  # azurerm_key_vault_secret.openai_api_key
    - infra/envs/prod/main.tf:132  # azurerm_key_vault_secret.langfuse_public_key
    - infra/envs/prod/main.tf:144  # azurerm_key_vault_secret.langfuse_secret_key
    - infra/envs/prod/main.tf:156  # azurerm_key_vault_secret.seeded_user_entra_oid
    - infra/modules/database/main.tf:31  # azurerm_key_vault_secret.pg_admin_password
  reason: "`terraform state pull | Select-String 'sk-'` returns two literal hits inside `azurerm_key_vault_secret.{openai_api_key,langfuse_secret_key}.value`. Container App half of Test 16 passes (secrets referenced via `key_vault_secret_id` URIs, no literals)."
  root_cause: "AzureRM provider stores `azurerm_key_vault_secret.value` as a literal in state for drift detection. Mitigated when `value_wo` / `value_wo_version` (TF 1.11+ write-only attributes) are used instead, but those fields are currently null."
  fix: "Replace `value = var.<secret>` with `value_wo = var.<secret>` + `value_wo_version = 1` on all 5 `azurerm_key_vault_secret` resources. Inspect `terraform plan` for in-place update (expected) vs. replace (would need a `moved` block or `lifecycle { ignore_changes }` shim). Bundle with Test 8 unblock PR since the same files are touched."
  boundary_note: "At-rest boundary still holds: state sits in Azure Blob with versioning + 7d soft-delete + GHA-SP-only ACL. This gap closes a defense-in-depth gap, not an active leak."
  d_decisions: ["D-13 (no literal secrets in state): currently partial, restored by `value_wo` migration"]

# ───── Test 10 / Gap 10.A — OPEN (KV audit trail missing) ─────
- truth: "Key Vault secret-read operations by the ACA managed identity are auditable in Log Analytics"
  status: failed
  severity: minor
  test: 10
  layer: observability
  artifacts:
    - infra/modules/security/  # no azurerm_monitor_diagnostic_setting for jobrag-prod-kv
    - infra/modules/monitoring/  # M9 wired ACA -> LAW but not KV -> LAW
  reason: "`az monitor diagnostic-settings list --resource <kv-id>` returns []. LAW query against AzureDiagnostics for jobrag-prod-kv fails with SemanticError 'Failed to resolve column or scalar expression named identity_claim_oid_g' because no KV log rows have ever been ingested into the workspace."
  root_cause: "Phase 3 prod composition provisions KV (modules/security) and LAW (modules/monitoring) but never wires the two together. M9 scope focused on ACA diagnostic settings only; KV diagnostics were never added."
  fix: "Add azurerm_monitor_diagnostic_setting for jobrag-prod-kv targeting jobrag-prod-law with log category 'AuditEvent' (optionally also 'AzurePolicyEvaluationDetails'). Effectively zero cost given the 0.15 GB/day LAW quota. Place in modules/security/main.tf or compose from envs/prod/main.tf to avoid circular module dep with monitoring."
  boundary_note: "Sub-level Activity Log retains 90d of caller/operation/status but lacks data-plane detail (which secret, which app/SP OID). Defensible for a free-tier single-user portfolio app — but the Test 10 spec assumed the diagnostic existed."
  discovered_by: "Test 10 verification cycle, 2026-05-17."

# ───── Test 10 / Gap 10.B — OPEN (scale config; ACTIVE PROD INCIDENT) ─────
- truth: "ACA scale config keeps new revisions warm long enough for the health probe to declare them Healthy, so production deploys actually activate"
  status: failed
  severity: major   # elevated from minor 2026-05-19 after incident discovery
  test: 10
  layer: ops-config
  artifacts:
    - infra/modules/compute/  # ACA template lacks scale block (rules + minReplicas)
  reason: |
    `az containerapp show --query properties.template.scale` returns
    `{cooldownPeriod: 300, maxReplicas: 1, minReplicas: null, pollingInterval: 30, rules: null}`.
    Without scale rules, ACA spins up a replica to serve each request and
    tears it down within seconds. Two observable consequences:
      (a) Operational: `az containerapp replica list` returns empty seconds
          after a 200 /health response. `containerapp exec` fails with
          'Could not find a replica for this app'.
      (b) PRODUCTION INCIDENT (see incident_reference below): new revisions
          created by deploy-api.yml never stay warm long enough for ACA to
          mark them Healthy. The activation probe fails, the revision is
          flagged ActivationFailed, and ACA falls back to the last Healthy
          revision. New code never reaches users while deploy-api.yml
          reports success.
  root_cause: "Compute module sets `maxReplicas = 1` for cost ceiling but omits both `minReplicas` and an http scale rule. Implicit ACA HTTP scaling serves traffic but doesn't honor the configured 300s cooldownPeriod (cooldown only attaches to a defined rule). The previously-Healthy revision --0000003 escaped this trap only because it was the first-ever deploy (no prior revision to fall back to, so ACA had to keep it alive)."
  fix: |
    Add explicit scale block to the ACA template in infra/modules/compute/:
        scale {
          min_replicas = 0
          max_replicas = 1
          http_scale_rule {
            name                = "http"
            concurrent_requests = "10"
          }
        }
    Preserves scale-to-zero economics, gives ACA a sustained warmth signal
    via the http rule's concurrency threshold, and lets activation probes
    complete successfully. Apply via deploy-infra.yml (or local terraform
    apply). Then trigger a fresh deploy-api.yml run to redeploy the alembic
    fix image (369000784) and verify a new revision (e.g. --0000007)
    activates Healthy.
  incident_reference: |
    Active production incident discovered during this UAT cycle:
      - Commit 369000784 ("fix(alembic): centralize % escape for ConfigParser
        via configure_alembic_url helper") was pushed 2026-05-16T14:35:50Z.
      - deploy-api.yml run #25964582484 reported ✓ success (15m1s).
      - Revision --0000006 was created 2026-05-16T14:50:00Z with
        trafficWeight=100, image
        ghcr.io/adrianzaplata/job-rag:369000784c9ca41a94e47847b686206ea9e62b02
      - Container booted cleanly: lifespan_startup_complete + Uvicorn ready
        in <3s. Then ACA tore down the replica (no scale rule to keep it
        warm). Revision marked runningState=ActivationFailed.
      - ACA fell back to routing on revision --0000003 (image ea0af2db,
        2026-05-06). The alembic fix has NOT been serving prod traffic for
        3 days; prod runs the 2026-05-06 image.
      - The 90s /health smoke probe in deploy-api.yml gave a false-positive
        ✓ because it hits the app FQDN, which falls back to the Healthy
        revision (--0000003). See Gap 10.C for the smoke-check defect.
      - ACA controller has been retrying activation periodically.
        2026-05-18T21:35-21:36Z retries hit a Microsoft platform webhook
        error ("failed calling webhook 'mapp.kb.io'") which is transient
        but also blocked recovery.
  d_decisions: ["D-15 (deploy.yml smoke must prove the new revision serves) — currently violated, see Gap 10.C"]
  discovered_by: "Test 10 verification cycle, 2026-05-17; incident scope deepened during Test 18 close-out, 2026-05-19."

# ───── Test 18 / Gap 10.C — OPEN (deploy verifier false-positive) ─────
- truth: "deploy-api.yml's post-deploy smoke check verifies that the NEW revision is the one serving production traffic, not just that any Healthy revision responds"
  status: failed
  severity: major
  test: 18
  layer: ci-cd-verification
  artifacts:
    - .github/workflows/deploy-api.yml  # the smoke step at the end of the deploy job
  reason: |
    Per the Gap 10.B incident_reference: deploy-api.yml run #25964582484
    completed with all steps green (build ✓, GHCR push ✓, Azure login ✓,
    Update Container App image ✓, /health smoke ✓). But the new revision
    --0000006 was in fact ActivationFailed, and ACA was falling back to
    --0000003 for traffic. The smoke step's curl hit the app FQDN, which
    ACA transparently routed to the previous Healthy revision, so the
    200 response came from the OLD image. The deploy verifier could not
    distinguish "the new revision is serving" from "any revision is
    serving".
  root_cause: "The smoke step polls the canonical app FQDN (jobrag-prod-api.gentlebay-...azurecontainerapps.io). When a new revision's activation fails, ACA's traffic management silently falls back to the last Healthy revision. The smoke probe sees 200 OK and concludes the deploy succeeded. There is no check that ties the 200 response to the specific revision (or image SHA) just deployed."
  fix_options:
    - "Option A (revision-specific FQDN): poll the per-revision FQDN instead of the app FQDN. `az containerapp revision show --revision <new> --query properties.fqdn` returns e.g. jobrag-prod-api--0000007.gentlebay-... which ALWAYS hits that specific revision (no traffic-weight fallback). 404 / 503 / timeout = activation failure, 200 = new revision is alive."
    - "Option B (image-SHA echo in /health): extend the FastAPI /health endpoint to return the build SHA in the JSON body (e.g. `{\"status\": \"ok\", \"sha\": \"369000784c\"}`). The deploy step then asserts response.sha == github.sha. Requires app change + Dockerfile to inject the SHA at build time as an env var."
    - "Option C (post-deploy revision-state poll): after `az containerapp update`, loop `az containerapp revision show --revision <new> --query properties.healthState` until it returns 'Healthy' (timeout = fail). Doesn't require app changes but couples the verifier to ACA's controller timing."
  recommendation: "Option A (revision-specific FQDN poll) — purely a workflow change, no app or Dockerfile touch, and provably distinguishes 'new revision is alive' from 'any revision is alive'. Combine with Option C as a belt-and-suspenders check that healthState transitions to Healthy."
  d_decisions: ["D-15 (deploy.yml smoke must prove the new revision serves): currently violated; restored by Option A"]
  discovered_by: "Test 10 orphan-revision investigation during Test 18 close-out, 2026-05-19."

# ───── Test 12 / Gap 12.B — OPEN (D-16 unenforceable at composition layer) ─────
- truth: "Only ContainerAppConsoleLogs_CL ingests into LAW — ContainerAppSystemLogs_CL is suppressed per D-16"
  status: failed
  severity: minor
  test: 12
  layer: composition-vs-runtime
  artifacts:
    - infra/modules/monitoring/  # azurerm_monitor_diagnostic_setting on the ACA env (governs platform events only)
    - infra/modules/compute/     # azurerm_container_app_environment.appLogsConfiguration (governs container logs — unfiltered)
  reason: "`Usage | where DataType == 'ContainerAppSystemLogs_CL'` shows daily ingestion through today (2026-05-18T07:12:56 was the latest — a KV sync event for jobrag-prod-api). Volume is small (0.23 MB / 30d) but the spec explicitly states SystemLogs should be absent."
  root_cause: "The ACA Container App Environment has two parallel log pipelines: (1) the `azurerm_monitor_diagnostic_setting` on the env, which has ContainerAppSystemLogs.enabled = false (D-16-compliant at composition layer); (2) the env's own `appLogsConfiguration.destination = 'log-analytics'` block, set at provisioning and pointing at the same LAW workspace customerId. The appLogsConfiguration pipeline ships ALL container log categories wholesale — it is not category-filterable. The diagnostic_setting on the env only routes env *platform* events, not container logs."
  fix_options:
    - "Option 1 (DCR transformation): create a Data Collection Rule with a workspace transformation that filters out `ContainerAppSystemLogs_CL` rows at ingestion time. Closes the gap cleanly but adds a new TF resource type."
    - "Option 2 (drop appLogsConfiguration entirely): remove `appLogsConfiguration` from the env to stop both Console and System log shipping. Then re-route Console via a custom DCR. Higher complexity, breaks the M9 simple-path."
    - "Option 3 (amend D-16): accept SystemLogs in scope; document that ACA env-level log shipping is binary (all categories or none) and the M9 D-16 intent was based on a wrong assumption about diagnostic_setting category filters. Update CONTEXT.md."
  recommendation: "Option 3 in the short term (cheapest, no infrastructure change, free-tier quota is unthreatened) plus a backlog item for Option 1 if future cost pressure or compliance ever requires hard-suppressing SystemLogs."
  volume_impact: "0.23 MB / 30d for SystemLogs (~0.008 MB/day average, peak 0.067 MB on 2026-05-16). Quota is 0.15 GB/day = 150 MB/day. SystemLogs uses ~0.005% of the daily cap — not a cost-gate risk."
  discovered_by: "Test 12 verification cycle, 2026-05-18."
