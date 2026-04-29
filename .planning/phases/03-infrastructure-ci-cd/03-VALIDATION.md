---
phase: 3
slug: infrastructure-ci-cd
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Source:** `03-RESEARCH.md` §Validation Architecture (13-item Requirements→Test Map). Phase 3 is platform-plane work — validation is largely **runbook-driven live Azure smoke** (cost: free; CI: not feasible without paid Azure-on-CI infra). Static checks (`terraform fmt`, `terraform validate`, `tflint`) DO run in CI.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (static)** | Terraform 1.9+ + tflint + tfsec; existing pytest for backend regression |
| **Config file** | `infra/.tflint.hcl` (Wave 0 creates); `pyproject.toml` for pytest already in place |
| **Quick run command** | `cd infra/envs/prod && terraform fmt -check && terraform validate` |
| **Full suite command** | `cd infra/envs/prod && terraform plan -var-file=prod.tfvars -out=plan.tfplan && tflint && tfsec . && cd ../../.. && uv run pytest tests/` |
| **Estimated runtime** | static suite ~30s; live Azure validation ~10–15min (runbook, not CI) |

---

## Sampling Rate

- **After every task commit:** `terraform fmt -check && terraform validate` for any modified TF directory; `uv run pytest tests/test_<related_module>.py` if backend code touched
- **After every plan wave:** Full static suite (`fmt -check`, `validate`, `tflint`, `tfsec`)
- **Before `/gsd-verify-work`:** All static checks green + the runbook-driven live-Azure smoke checklist (see Manual-Only Verifications below) executed once on a clean clone
- **Max feedback latency:** 30s (static checks); live Azure runbook is one-time per phase close

---

## Per-Task Verification Map

> Filled in by the planner after plan files are generated. Each task's `<automated>` block must reference one of the categories below or declare a Wave 0 dependency.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _planner-fills_ | _01_ | _1_ | _DEPL-XX_ | _T-3-XX_ | _expected_ | _static / live-smoke / unit_ | _command_ | _W0_ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Automation tiers (planner uses these):**

1. **Static (`terraform fmt -check`, `terraform validate`, `tflint`, `tfsec`)** — runs in CI on PR; covers DEPL-01, DEPL-02 syntactic correctness, all linter-detectable security misconfigs.
2. **Plan-time (`terraform plan -detailed-exitcode`)** — runs in CI on `deploy-infra.yml` PR; ensures plan is empty for no-op changes (drift detection).
3. **Live-smoke (runbook)** — runs once per phase close + on-demand: provisions actual Azure resources, verifies reachability, JWT issuer, pgvector extension presence, OIDC token claims, CORS rejections, SSE flow over public ACA URL.
4. **Backend regression (`uv run pytest tests/`)** — Phase 1+2 test suite must stay green; Phase 3 doesn't touch backend code but the API container build is verified by smoke-running migrations.

---

## Wave 0 Requirements

- [ ] `infra/.tflint.hcl` — tflint config (azurerm ruleset, deep-check enabled where supported)
- [ ] `infra/.tfsec/config.yml` — tfsec config (allowlist for documented €0-budget trade-offs: e.g., `public_network_access_enabled = true` on Postgres per D-10)
- [ ] `infra/envs/prod/README.md` skeleton — runbook stub (filled by execution tasks)
- [ ] `infra/bootstrap/README.md` skeleton — bootstrap runbook stub
- [ ] `infra/scripts/refresh-swa-origin.sh` skeleton — two-pass CORS helper (filled by execution tasks)
- [ ] `.github/workflows/_static-tf.yml` (or fold into existing `ci.yml`) — `terraform fmt -check && terraform validate && tflint && tfsec` on PRs touching `infra/**`
- [ ] No new pytest fixtures needed — Phase 3 doesn't add backend test files

---

## Manual-Only Verifications (Live Azure Smoke Runbook)

> Source: `03-RESEARCH.md` §Validation Architecture + PITFALLS.md "Looks Done But Isn't Checklist". Run once on a clean clone of the repo at phase-close; document evidence in `.planning/phases/03-infrastructure-ci-cd/03-SMOKE.md` (created by the verify wave).

| # | Behavior | Requirement | Why Manual | Test Instructions |
|---|----------|-------------|------------|-------------------|
| M1 | Bootstrap remote state from a clean clone | DEPL-01 | Requires Azure portal + first-run RBAC | `cd infra/bootstrap && terraform init && terraform apply`, copy outputs into `infra/envs/prod/backend.tf`, then from a fresh checkout `cd infra/envs/prod && terraform init && terraform plan` should succeed without `.tfstate` |
| M2 | `terraform apply` creates the full Azure resource graph | DEPL-02..DEPL-07, DEPL-10, DEPL-11 | Real Azure provisioning, not feasible in CI | First apply: `cd infra/envs/prod && terraform apply -var-file=prod.tfvars` — verify in portal: ACA env + Container App, Postgres B1ms with `vector` in `azure.extensions`, SWA Free, KV with 5 secrets, LAW with 0.15 GB/day cap, €10/mo budget alert with 50/75/90/100% thresholds |
| M3 | Two-pass CORS bootstrap | DEPL-12 | Cross-resource cycle requires apply + script + apply | Run `scripts/refresh-swa-origin.sh`, observe second apply injects SWA default origin into Container App `ALLOWED_ORIGINS`; verify with `curl -H "Origin: https://<swa-default>" <aca-fqdn>/health` returns CORS headers, and `curl -H "Origin: https://evil.example" <aca-fqdn>/health` is rejected |
| M4 | OIDC federated credential — master push trigger | DEPL-08, DEPL-09 | Requires real GitHub Actions runner | Push a no-op commit to master with API path; verify `deploy-api.yml` runs and `azure/login@v2` exchanges the OIDC token for an Azure access token (check workflow log for `Login successful`); push a frontend-only no-op commit; verify `deploy-infra.yml` does NOT fire (paths filter) |
| M5 | OIDC federated credential — environment:production trigger | DEPL-08 | Requires GH protected environment | Trigger `deploy-infra.yml` via `workflow_dispatch` with environment: production; verify GitHub blocks until Adrian approves; after approval, OIDC exchange succeeds against the second federated credential subject |
| M6 | GHCR image push + ACA pull over HTTPS | DEPL-07 | Requires real GHCR registry + ACA pull | After `deploy-api.yml` runs, `docker pull ghcr.io/<owner>/job-rag:<sha>` from a separate machine succeeds; ACA Container App pulls the same image and `curl https://<aca-fqdn>/health` returns 200 |
| M7 | KV secret resolution via managed identity | D-13, DEPL-04 | Requires running Container App | Inside ACA console: `env \| grep OPENAI_API_KEY` shows resolved value; KV access logs (LAW query: `KeyVaultData` table) show the ACA system-assigned MI authenticated and read each of the 5 secrets at container start |
| M8 | pgvector extension exists in `jobrag` DB | DEPL-05, DEPL-06 | Requires DB connection through firewall | After first ACA cold-start (Alembic migration runs), connect via psql from Adrian's home IP: `psql -h <pg-fqdn> -U jobrag_admin -d jobrag -c "\dx"` — `vector` listed; `\l` shows `jobrag` DB exists; per-DB extension visibility confirmed |
| M9 | Log Analytics daily quota cap holds | DEPL-10 | Requires real ingest over time | LAW portal: verify `dailyQuotaGb = 0.15`; KQL: `Usage \| where DataType == "ContainerAppConsoleLogs_CL" \| summarize sum(Quantity) by bin(TimeGenerated, 1d)` shows ≤4.5 GB/mo; system logs absent unless explicitly enabled |
| M10 | Budget alert email arrives | DEPL-11 | Requires real cost accumulation OR portal-side test | Portal: simulate alert via "Send test alert" button on the budget alert; Adrian's email receives at the 50% threshold first, confirming the email channel and threshold ladder |
| M11 | SSE flow survives Envoy 240s cap during streaming | D-15, PITFALLS §3 | Requires real ACA traffic | `curl -N https://<aca-fqdn>/agent/stream -H "Authorization: Bearer ..."` and a 60s prompt — observe events stream over multiple seconds without ingress drop; revision swap during stream (deploy a new image) — verify in-flight requests drain (terminationGracePeriodSeconds=120 honors) |
| M12 | JWT iss claim matches ciamlogin.com (Phase 4 hand-off prep) | D-05 | Requires Phase 4 client + first MSAL login | Phase 4 owns the client; for Phase 3, runbook validates only that the External tenant subdomain is reachable at `https://<tenant-subdomain>.ciamlogin.com/.well-known/openid-configuration` and returns valid metadata |
| M13 | tfstate does not contain the OPENAI_API_KEY value | D-13, security | TF state read | `terraform state pull \| jq '.. \| select(type=="string") \| select(test("sk-"))'` returns empty; KV references should appear as `key_vault_secret_id` URIs, never literal values |

---

## Validation Sign-Off

- [ ] All planner-generated tasks have `<automated>` verify or Wave 0 dependencies (planner adds these in step 8)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (static-suite covers most)
- [ ] Wave 0 covers all MISSING references (`tflint.hcl`, `tfsec/config.yml`, runbook skeletons)
- [ ] No watch-mode flags (`terraform fmt -check`, not `-recursive` watch)
- [ ] Feedback latency < 30s for static suite
- [ ] Live-smoke runbook (M1–M13) executed once at phase close, evidence in `03-SMOKE.md`
- [ ] `nyquist_compliant: true` set in frontmatter after planner fills the per-task map

**Approval:** pending
