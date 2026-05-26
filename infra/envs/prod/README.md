# Prod environment

> Active production environment for the job-rag stack. Provisions ACA + Postgres B1ms with pgvector + SWA Free + KV with 5 secrets + LAW with daily quota + €10/mo budget alert. Two-pass apply per DEPL-12 to resolve the SWA-origin ↔ ALLOWED_ORIGINS cycle.

---

## Prerequisites

- `infra/bootstrap/` has already been applied (per `infra/bootstrap/README.md`).
- `backend.tf` placeholder values have been replaced with real bootstrap outputs (Step 3 of bootstrap runbook).
- `terraform.tfvars.local` (gitignored) provides the only TF-managed secret: `ghcr_pat` (or use `TF_VAR_ghcr_pat`). `openai_api_key` and `langfuse_*` are NOT TF variables — they are seeded out-of-band into Key Vault after pass 1 (see "Out-of-band secret seeding" below).
- Adrian is signed in via `az login` to the subscription that owns `jobrag-tfstate-rg`.

## Apply command convention (Phase 06.1 D-05/D-06)

**Every `terraform plan` / `apply` / `destroy` against this directory MUST pass BOTH var files:**

```bash
terraform <subcommand> -var-file=prod.tfvars -var-file=prod.tfvars.local
```

Or use the canonical wrapper (recommended — fails loudly if `prod.tfvars.local` is missing):

```bash
bash scripts/tf-apply-prod.sh <subcommand>          # from repo root
bash scripts/tf-apply-prod.sh plan
bash scripts/tf-apply-prod.sh apply
bash scripts/tf-apply-prod.sh apply -auto-approve
bash scripts/tf-apply-prod.sh plan -detailed-exitcode   # Phase 06.1 D-08 verification
```

**Why both files are required:** `prod.tfvars` (committed) carries non-secret, version-controlled
config (image_tag, cpu, memory, ghcr_username, swa_origin). `prod.tfvars.local` (gitignored
per `.gitignore:35`) carries the Phase 4 D-04 auth values (`backend_audience`, `entra_tenant_id`,
`entra_tenant_subdomain`) plus `home_ip` and `api_audience`. Running `terraform apply -var-file=prod.tfvars`
alone leaves the auth values at their `""` defaults in `infra/modules/compute/variables.tf`,
which wipes the ACA container's `BACKEND_AUDIENCE` / `ENTRA_TENANT_*` env vars and silently
breaks Entra auth (Phase 06 UAT Bug #3, `.planning/phases/06-chat/06-UAT-DEBUG-HANDOFF.md`).

### Where each kind of value belongs (file pyramid — Phase 06.1 D-09)

| Tier | File / mechanism | Examples |
|------|------------------|----------|
| Committed, deployment-stable | `prod.tfvars` (this repo) | `image_tag`, `cpu`, `memory`, `ghcr_username`, `swa_origin`, `location`, `tags` |
| Gitignored, Adrian-specific | `prod.tfvars.local` (gitignored) | `home_ip`, `backend_audience`, `entra_tenant_id`, `entra_tenant_subdomain`, `api_audience` |
| `TF_VAR_*` env var (CI/local secret) | `secrets.GHCR_PAT` via workflow | `ghcr_pat` |
| Out-of-band `az keyvault secret set` (never in TF) | Key Vault, post-apply | `OPENAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `SEEDED_USER_ENTRA_OID` on rotation |

### CI vs local: variable-source matrix (Phase 06.1 D-10)

| Variable | Local apply | CI apply (`deploy-infra.yml`) |
|----------|-------------|-------------------------------|
| `home_ip` | `prod.tfvars.local` | `TF_VAR_home_ip` from `secrets.HOME_IP` |
| `ghcr_pat` | `TF_VAR_ghcr_pat` or `prod.tfvars.local` | `TF_VAR_ghcr_pat` from `secrets.GHCR_PAT` |
| `gha_client_id` / `tenant_id_workforce` / `use_oidc_auth` | empty (CLI auth path) | `TF_VAR_*` from `secrets.AZURE_*` |
| `backend_audience` / `entra_tenant_id` / `entra_tenant_subdomain` | `prod.tfvars.local` (sourced from `infra/external/` outputs via `scripts/refresh-external-outputs.sh`) | **Intentionally NOT managed by CI.** Adrian sets them locally; CI applies preserve via `terraform apply`'s no-op-on-equal semantics (set once, present in state). If CI ever wipes them, the next local `bash scripts/tf-apply-prod.sh apply` restores from `prod.tfvars.local`. See `deploy-infra.yml` inline comment block (Phase 06.1 D-10). |

## Ordered runbook (W2 — explicit step ordering)

The two-pass apply is sequenced per the W2 fix to make the "image not deployed yet" expectation explicit:

1. **Bootstrap apply** (one-time, separate directory): `cd infra/bootstrap && terraform apply` — creates state-storage RG. (See `infra/bootstrap/README.md`.)
2. **Prod env pass 1**: `cd infra/envs/prod && terraform init && terraform apply -var-file=prod.tfvars -var-file=prod.tfvars.local` — creates ACA + SWA + KV + Postgres + LAW + budget. **Expected behavior:** the Container App revision will fail to start (image tag `latest` doesn't exist in GHCR yet, AND the openai/langfuse KV secrets are still placeholder strings). This is normal at this stage.
3. **Out-of-band secret seeding** (Option B, one-time + on rotation): `az keyvault secret set ...` for `openai-api-key` / `langfuse-public-key` / `langfuse-secret-key`. (See "Out-of-band secret seeding" below.)
4. **First image push**: either run `deploy-api.yml` manually via `gh workflow run deploy-api.yml --ref master`, OR push from local: `docker push ghcr.io/adrianzaplata/job-rag:latest`. (See "Image push: GHCR visibility" below for the B3 visibility step.)
5. **Prod env pass 2** (CORS injection): `bash ../../../scripts/refresh-swa-origin.sh` — script rewrites `swa_origin` in tfvars and re-applies. The Container App revision now starts cleanly (image exists, real secrets in KV, ALLOWED_ORIGINS now includes the SWA origin).
6. **GitHub secrets sync** (manual, B2): `terraform output -raw swa_api_key | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD --repo adrianzaplata/job-rag`. (See "Phase-close: GitHub secrets sync" below.)
7. **Corpus bootstrap** (one-time, A6): `gh workflow run bootstrap-corpus.yml --ref master`. (See "Corpus bootstrap" below.)
8. **M1–M13 smoke** (Plan 07): execute the live-Azure smoke per `.planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md`.

## First apply (pass 1)

```bash
cd infra/envs/prod

terraform init
terraform plan -var-file=prod.tfvars -var-file=prod.tfvars.local -out=plan-pass-1.tfplan
terraform apply plan-pass-1.tfplan
```

After apply succeeds, the SWA exists and `terraform output -raw swa_default_origin` returns its hostname. The Container App's `ALLOWED_ORIGINS` env var contains only `http://localhost:5173` at this point (per `locals.allowed_origins_csv` with `var.swa_origin = ""`). The Container App revision will fail to start (no image yet) — that's expected; proceed to **out-of-band secret seeding** (next section), then image push.

## Out-of-band secret seeding (Option B — required after pass 1, before image push)

Why: keeps `OPENAI_API_KEY` and `LANGFUSE_*` out of GitHub Actions secrets. TF creates the KV secret resource shells with placeholder value `"managed-out-of-band"` and `lifecycle.ignore_changes = [value]`, so Adrian seeds the real values directly via Azure CLI. Subsequent `terraform apply` runs do NOT overwrite them.

When to run: **once after first apply**, and again on rotation (recommend quarterly for OpenAI, on-demand for Langfuse).

```bash
KV_NAME=$(terraform output -raw kv_name)

az keyvault secret set --vault-name "$KV_NAME" --name openai-api-key      --value "<sk-...>"
az keyvault secret set --vault-name "$KV_NAME" --name langfuse-public-key --value "<pk-...>"
az keyvault secret set --vault-name "$KV_NAME" --name langfuse-secret-key --value "<sk-...>"
```

If Langfuse is disabled (Phase 1 fail-open behavior), set both langfuse keys to empty strings:

```bash
az keyvault secret set --vault-name "$KV_NAME" --name langfuse-public-key --value ""
az keyvault secret set --vault-name "$KV_NAME" --name langfuse-secret-key --value ""
```

After seeding, force a Container App revision restart so the new env var values are picked up (the ACA `secretRef` resolves at revision creation time, not on every request):

```bash
RG=$(terraform output -raw resource_group_name 2>/dev/null || echo "jobrag-prod-rg")
az containerapp revision restart --name jobrag-prod-api --resource-group "$RG" \
  --revision "$(az containerapp revision list --name jobrag-prod-api --resource-group "$RG" --query '[0].name' -o tsv)"
```

Verify (does NOT print the secret — only its `versionless_id`):

```bash
az keyvault secret show --vault-name "$KV_NAME" --name openai-api-key --query 'attributes.updated' -o tsv
```

**Do NOT** put these values in `terraform.tfvars.local` or in any `TF_VAR_*` env var — the variables don't exist anymore in `variables.tf`. The only TF-managed secret is `ghcr_pat` (registry credential, passed via `TF_VAR_ghcr_pat` from the workflow).

## Two-Pass CORS Bootstrap

```bash
bash ../../../scripts/refresh-swa-origin.sh
```

The script:
1. Reads `terraform output -raw swa_default_origin`.
2. Rewrites `prod.tfvars` to set `swa_origin = "https://<swa-default-host>"` (idempotent).
3. Runs `terraform apply -var-file=prod.tfvars -var-file=prod.tfvars.local -auto-approve`.

Result: the Container App's `ALLOWED_ORIGINS` env var becomes `"https://<swa-default-host>,http://localhost:5173"`; the SPA app reg's `redirect_uris` includes both local + prod.

Verify: `curl -H "Origin: https://<swa-default-host>" https://<aca-fqdn>/health` returns 200 with CORS headers; `curl -H "Origin: https://evil.example" https://<aca-fqdn>/health` is rejected.

## Image push: GHCR visibility (B3)

After the first `docker push` (manual or via `deploy-api.yml`), the GHCR package's visibility may default to private. ACA must be able to pull. Two paths:

**Recommended (portfolio repo per A2 — public):**
1. Visit `https://github.com/adrianzaplata/job-rag/pkgs/container/job-rag` → "Package settings" → "Manage Actions access" + "Change visibility" → set to **Public**.
2. ACA can pull anonymously; no PAT scope required at runtime (the registry block in compute module still uses `var.ghcr_pat` for first-pull but reads anonymous if package is public).

**Alternative (private package):**
1. Generate a fine-grained PAT with `read:packages` scope on the `job-rag` package only (90-day expiry max).
2. Update `var.ghcr_pat` in `terraform.tfvars.local` and re-apply.

Reference: [GitHub Docs — Configuring a package's access control and visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

## Image push and ACA revision update

The first apply uses `image_tag = "latest"` (default in prod.tfvars). The actual image push happens via `deploy-api.yml` (Plan 06):

1. Push to `master` with changes under `src/**` / `pyproject.toml` / `uv.lock` / `Dockerfile` / `alembic/**`.
2. `deploy-api.yml` builds + pushes to `ghcr.io/adrianzaplata/job-rag:${{ github.sha }}` + `:latest`.
3. `az containerapp update --image ghcr.io/.../job-rag:${{ github.sha }}` swaps the revision.

**B5 alignment:** the compute module has `lifecycle { ignore_changes = [template[0].container[0].image, template[0].revision_suffix] }` so subsequent `terraform apply` runs do NOT revert the SHA-pinned revision deployed by CI.

Manual fallback (when GHA is broken or image needs a hand-fix):

```bash
docker build -t ghcr.io/adrianzaplata/job-rag:manual .
echo "$GHCR_PAT" | docker login ghcr.io -u adrianzaplata --password-stdin
docker push ghcr.io/adrianzaplata/job-rag:manual

az containerapp update \
  --name jobrag-prod-api \
  --resource-group jobrag-prod-rg \
  --image ghcr.io/adrianzaplata/job-rag:manual
```

## Phase-close: GitHub secrets sync (B2 — manual runbook)

The SWA `api_key` is the sole long-lived secret in the system (A2 + D-08). It must reach `AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` so `deploy-spa.yml` can authenticate. The B2 locked decision: **NO automated `gh secret set` step in `deploy-infra.yml`** (avoids needing a long-lived `GH_PAT_FOR_SECRETS`). Adrian runs the sync manually from a local terminal:

```bash
cd infra/envs/prod
terraform output -raw swa_api_key | gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD --repo adrianzaplata/job-rag
```

**When to run:**
- After the first prod apply.
- On SWA token rotation (~180 days, Microsoft default — `learn.microsoft.com/en-us/azure/static-web-apps/deployment-token-management`).
- Set a calendar reminder for the 180-day cadence.

The `terraform output -raw` reads from local TF state (must run from a clone with backend.tf pointing at the bootstrap state); `gh secret set` reads from stdin and never echoes the value to the terminal. Both ends respect the secret boundary.

## Corpus bootstrap (A6 — one-time)

Per CONTEXT.md A6, the ACA `docker-entrypoint.sh` runs ONLY `job-rag init-db` + `uvicorn`. Corpus ingest + embed are decoupled into `.github/workflows/bootstrap-corpus.yml` (created in Plan 05b). After the first deploy, run once:

```bash
gh workflow run bootstrap-corpus.yml --ref master
```

The workflow uses the same OIDC federated credential as `deploy-api.yml`, then `az containerapp exec` to run `job-rag ingest --show-cost && job-rag embed --show-cost` against the live container.

**When to run:**
- After the first prod apply (one-time corpus seed).
- On `PROMPT_VERSION` bumps that require full re-extraction (rare — Phase 2-rev plans).

The workflow is `workflow_dispatch` only — never auto-runs. Re-running it without a corpus refresh is a safe no-op (ingest skips already-ingested files via content hash dedup).

## Post-apply smoke checklist

Run the M1–M13 smoke runbook documented in `.planning/phases/03-infrastructure-ci-cd/03-VALIDATION.md` lines 70–89. Plan 07 ships the evidence file `03-SMOKE.md`. Highlights:

- **M3** CORS: `curl -H "Origin: https://evil.example" <aca-fqdn>/health` rejected.
- **M7** KV resolution: `az containerapp exec ... -- env | grep OPENAI_API_KEY` shows resolved value.
- **M8** pgvector: `psql -h <pg-fqdn> -U jobragadmin -d jobrag -c "\dx"` shows `vector` extension.
- **M11** SSE survival: `curl -N <aca-fqdn>/agent/stream` streams over multiple seconds; revision swap during stream drains cleanly per `termination_grace_period_seconds=120`.
- **M13** TF state hygiene: `terraform state pull | jq '.. | select(type=="string") | select(test("sk-"))'` returns empty.

## Knowingly-accepted security trade-offs

Per CONTEXT.md Plan-Locking Addendum A1 (Path A) and Plan 04 module READMEs:

| Trade-off | Rationale | Mitigation |
|-----------|-----------|------------|
| Postgres `public_network_access_enabled = true` | Private endpoint costs ~€130/mo; breaks €0 budget. | TLS-only (`require_secure_transport=on`) + 32-char random alphanumeric password in KV. |
| Postgres firewall includes `0.0.0.0` "Allow Azure services" rule | ACA Consumption-tier outbound IP is documented non-stable; per-IP allowlist would silently break. | Same TLS + password boundary; tfsec allowlist documented in `infra/.tfsec/config.yml`. |
| GHCR PAT lives in TF state | Chicken-and-egg: ACA needs to pull image before MI can resolve KV refs. | PAT is fine-grained read-only on the package; `var.ghcr_pat` is `sensitive = true`; rotate per below. (Or set package public per B3 to skip the PAT path entirely.) |
| SWA `api_key` flows through TF state | SWA does not yet support OIDC GA. | `sensitive = true`; rotated per below; only consumed by deploy-spa.yml; B2: synced manually, no `GH_PAT_FOR_SECRETS` in the system. |
| `min_replicas = 0` causes cold-start latency | Free-tier vCPU-sec budget would be blown by `min_replicas = 1` (~€15-20/mo). | Phase 6 ships UX states (`connecting` / `warming` / `streaming`) per CONTEXT.md D-17. |
| `ContainerAppSystemLogs_CL` ingests into LAW alongside Console | ACA env's `appLogsConfiguration.destination = "log-analytics"` is a binary all-or-none pipeline; the `azurerm_monitor_diagnostic_setting` on the env governs only platform events, not container logs. See 03-CONTEXT.md D-16 Amendment (Gap 12.B). | Volume is ~0.005% of the 0.15 GB/day LAW cap (~0.008 MB/day average, peak 0.067 MB). Cost gate remains the daily quota. DCR-based filtering is documented as a Deferred backlog item if compliance ever requires hard-suppression. |
| Auth env vars (`backend_audience`, `entra_tenant_id`, `entra_tenant_subdomain`) sourced from gitignored `prod.tfvars.local` | Values come from `infra/external/` outputs (Adrian's local-only TF). Committing them is harmless (they're public-by-design per Phase 3 D-13) but the per-machine `*.tfvars.local` pattern keeps the file-tier discipline uniform. | Apply command convention (Phase 06.1 D-05/D-06) makes both var files mandatory; `scripts/tf-apply-prod.sh` enforces the policy at the wrapper layer; CI documents the matrix in `deploy-infra.yml` inline comment block (D-10). |

## Token rotation cadence

| Token | Cadence | Procedure |
|-------|---------|-----------|
| KV secret `openai-api-key` (out-of-band, Option B) | Quarterly recommended; immediately on exposure | `az keyvault secret set --vault-name $(terraform output -raw kv_name) --name openai-api-key --value "<new>"` then `az containerapp revision restart ...` so the new revision picks it up |
| KV secret `langfuse-public-key` / `langfuse-secret-key` | When rotated in Langfuse Cloud | Same `az keyvault secret set` pattern as above |
| `var.ghcr_pat` | 90 days (GitHub fine-grained PAT max) | Generate new PAT (`read:packages` on the `job-rag` package). Apply BOTH surfaces in parallel: (1) update `terraform.tfvars.local` and run `terraform apply -var-file=prod.tfvars -var-file=prod.tfvars.local -var ghcr_pat="<new>"` (rotates state + ACA registry secret); (2) `gh secret set GHCR_PAT --repo AdrianZaplata/job-rag` (CI parity, else the next `deploy-infra.yml` run fails with `ContainerAppSecretInvalid: secret(s) 'ghcr-pat' invalid` when `TF_VAR_ghcr_pat` resolves to empty string). |
| Postgres admin password (KV: `postgres-admin-password`) | On-demand only | `terraform taint module.database.random_password.pg_admin && terraform apply` |
| SWA api_key (KV: N/A — direct GH secret) | **180 days** (Microsoft default) | Run the B2 manual sync command above (`terraform output -raw swa_api_key \| gh secret set ...`) from local. NO automated rotation in workflow per B2. |
| GHA SP federated credentials | Never (OIDC = no long-lived secret to rotate) | n/a |

The SWA api_key is the **sole long-lived secret** in the system per A2 + D-08 + RESEARCH.md Pitfall §SWA api_key.

## Home IP refresh

Adrian's home IP rotates with ISP DHCP. Refresh procedure documented in `infra/modules/database/README.md` (sed-based one-liner update of `prod.tfvars`).

## Drift detection

Run `terraform plan -var-file=prod.tfvars -var-file=prod.tfvars.local` periodically. A non-empty plan against an unchanged repo means someone portal-edited a resource, OR the live image diverged from `var.image_tag` (expected per B5 — terraform's view of the image is intentionally stale after first deploy-api.yml run).

---

## Phase 4 close (2026-05-21)

Phase 4 (Frontend Shell + Auth) shipped live verified. SPA at the SWA origin signs in via Entra
External ID, backend validates the JWT via `fastapi-azure-auth`, AUTH-06 oid allowlist gate
enforces single-user. Full post-mortem + verbatim runbook live at
`.planning/phases/04-frontend-shell-auth/04-06-SUMMARY.md` and `04-06-RUNBOOK.md`.

**Unblock fixes captured during the runbook — operators replaying this should apply these up front:**

| Fix | Commit | Where |
|-----|--------|-------|
| SPA app reg needs `requested_access_token_version = 2` (CIAM rejects v1) | `83c936a` | `infra/external/main.tf` |
| `azuread_application_identifier_uri.api` Terraform resource may silently fail — run `az ad app update --identifier-uris api://<api_client_id>` to verify | n/a (manual) | External tenant — Phase 04.1-06 refactor (`infra/external/` split into `azuread_application_registration` + `azuread_application_identifier_uri` + `azuread_application_permission_scope` siblings) makes this STILL the unblock for live silent-fail of `azuread_application_identifier_uri`; `scripts/refresh-external-outputs.sh` now asserts on it and prints the exact command on failure |
| Migration 0005's UPDATE only runs once; subsequent SEEDED_USER_ENTRA_OID rotations need a manual UPDATE via `az containerapp exec` (or refactor into `init_db()` per follow-up) | manual SQL | live DB |
| `frontend/public/staticwebapp.config.json` needed for SPA deep-link routing | `733920f` | `frontend/public/` |
| Plan template typo: actual ACA app name is `jobrag-prod-api` (env-first), NOT `jobrag-api-prod` | n/a (doc) | every `az containerapp` command |

**B2B-guest-vs-customer namespace** — the CIAM user flow only resolves customer-namespace identities. The Entra-portal "Invite external user" flow creates B2B guests that CANNOT sign in via the user flow even though they show up in `az ad user list`. The canonical customer/Member bootstrap step is now documented in `infra/bootstrap/README.md` → "Step 5 — Bootstrap a first-login customer/Member account" (Phase 04.1 fix 4). Run that step BEFORE attempting first sign-in.

**Pre-existing CI failures** inherited from Phase 3 (unrelated to Phase 4): `ci.yml` lint-and-test alembic smoke step has been failing since 2026-05-19; `deploy-infrastructure.yml` is missing `TF_VAR_home_ip` / `TF_VAR_ghcr_pat` in workflow env. Both are Phase 3 follow-ups; documented in 04-06-SUMMARY.md.

**ACA deploy-api.yml smoke check** rejects `runningState=RunningAtMaxScale` as not-`Running` — cosmetic CI failure even though the new revision IS healthy and serving traffic. Verify deploy succeeded via per-revision FQDN smoke (per `aca-deploy-verifier-trap` memory) regardless of the run status. Fix: extend `Running` predicate to accept both states; see follow-up.

**`azuread_application_identifier_uri` Terraform unreliability** — fixed structurally in Phase 04.1-06 (Phase 04.1 fix 5's inline-attribute attempt was rejected by Terraform's resource graph layer as a self-reference; see `.planning/debug/external-identifier-uris-self-ref.md` for the full diagnosis). `infra/external/main.tf` now uses the `azuread_application_registration` + `azuread_application_identifier_uri` + `azuread_application_permission_scope` split (verified against the locked `azuread = 3.8.0` schema via `terraform providers schema -json`). The URI side-resource references the registration's `client_id` (a cross-resource reference, plans cleanly). `requested_access_token_version = 2` is set directly on the registration as a top-level attribute (replaces the old nested `api { requested_access_token_version = 2 }` block from `azuread_application.api`; CIAM rejects v1 tokens — load-bearing). Silent-fail risk on the URI side-resource (state says `Created` while live `identifierUris` stays empty) is mitigated by `scripts/refresh-external-outputs.sh`'s `az ad app show --query identifierUris` assertion — the script exits 2 with an unblock instruction before any downstream file rewrite if the live URI is empty. On the **next** `cd infra/external && terraform apply`, the plan shape is `3 to add, 1 to change, 2 to destroy, 2 to replace` (or `5 add / 1 change / 4 destroy` in newer Terraform that rolls replacements into the add+destroy totals) and the `api_client_id` changes (new app registration = new GUID). `bash scripts/refresh-external-outputs.sh` then propagates the new GUID atomically to `frontend/.env.production`, `infra/envs/prod/prod.tfvars.local`, and (via `gh secret set`) the GitHub repo secret. The literal SHAPE `api://<guid>` is unchanged — `src/job_rag/api/auth.py:72`'s `removeprefix("api://")` contract is preserved. **Admin consent on the SPA→API delegated permission grant MUST be re-granted via portal** (the API SP is a brand-new object after the cascade — previous admin consent does not migrate). See `infra/external/README.md` "State reconciliation" for the full operator playbook.
