# Phase 3: Infrastructure & CI/CD - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 ships a fully provisioned Azure stack when:

1. `terraform apply` against `infra/envs/prod/` (run twice to resolve the CORS cycle) creates an Entra External tenant (manually bootstrapped + imported), an ACA Container App (min_replicas=0, max_replicas=1, terminationGracePeriodSeconds=120), a Postgres Flex B1ms with `vector` allowlisted + `jobrag` database created, an SWA Free SKU origin, a Key Vault with managed-identity-backed secret refs, a Log Analytics workspace with a 0.15 GB/day cap on ConsoleLogs only, and a €10/mo subscription budget alert.
2. State lives in an Azure Blob backend created by a separate one-shot `infra/bootstrap/` Terraform run (local state, runbook'd, never committed).
3. `infra/envs/{dev,prod}/` directories share a `infra/modules/*` library; AVM modules used selectively (KV, LAW, Postgres Flex); raw `azurerm` for ACA + SWA; `azuread` for app registrations + federated credentials.
4. `deploy-infra.yml`, `deploy-api.yml`, `deploy-spa.yml` each authenticate via OIDC federated credential (one per trigger shape: master push for api/spa, environment:production for infra), use resource-group-scoped Contributor (never subscription), and `paths` filters keep the workflows independent.
5. The two-pass CORS bootstrap is documented and works — first apply discovers the SWA default origin, second apply injects it into the Container App's `ALLOWED_ORIGINS` env var.
6. A hello-world container image pushed to GHCR (not ACR Basic) and referenced by the Container App is reachable at the ACA FQDN over HTTPS.
7. Dev environment is scaffolded (`infra/envs/dev/` exists with full *.tf + dev.tfvars + separate state key) but **not applied** in v1 — apply path is documented for future staging needs.

Out of scope here (later phases): MSAL React integration + JWT validation in FastAPI body (Phase 4), Dashboard widgets (Phase 5), Chat UI (Phase 6), Resume upload + profile CRUD (Phase 7), RAGAS-on-CI + Langfuse production wiring + docs (Phase 8). Phase-2 follow-up to triage 10 persistent extraction failures stays a standalone Phase-2-rev plan.

</domain>

<decisions>
## Implementation Decisions

### A. Terraform layout & bootstrap

- **D-01:** Repo structure follows REQUIREMENTS DEPL-02 verbatim — `infra/envs/{dev,prod}/` directories each call shared `infra/modules/{network,database,compute,identity,monitoring,kv}`. Each env has a separate state file in the same Azure Blob backend (different `key=`). PITFALLS §14 alignment: directories over workspaces because dev/prod drift is expected (different SKUs, possibly different auth tier later). **Documented deviation from PROJECT.md "Terraform workspaces" Key Decision** — log in PROJECT.md Key Decisions table at phase close ("Terraform envs/dirs over workspaces; PITFALLS §14 + DEPL-02 spec").
- **D-02:** Bootstrap chicken-and-egg (PITFALLS §13) handled by a dedicated `infra/bootstrap/` directory: creates the state-storage RG + storage account (versioning + 7d soft-delete) + state container. **LOCAL state, .gitignored.** One-time run via README runbook; outputs (`storage_account_name`, `container_name`, `resource_group_name`) copied as static literals into `infra/envs/{dev,prod}/backend.tf`. Bootstrap directory remains in repo for reproducibility but its `terraform.tfstate` is never committed.
- **D-03:** Selective AVM adoption per DEPL-02 ("where available"):
  - Use AVM: `avm/res/key-vault/vault`, `avm/res/operational-insights/workspace`, `avm/res/db-for-postgresql/flexible-server`.
  - Skip AVM (use raw azurerm): Container App + Container App Environment (AVM module still maturing as of Apr 2026; raw `azurerm_container_app` is well-trodden), Static Web App (one-resource module = no abstraction value), `azuread` resources (no AVM coverage).
  - Per-resource decision documented in `infra/modules/{kind}/README.md`.
- **D-04:** Dev environment is **scaffold-only, never applied in v1**. `infra/envs/dev/` exists with full *.tf + `dev.tfvars` + `backend.tf` pointing at a separate state key; `terraform plan` works as a sanity-check; `apply` is documented-but-deferred. Cost stays at strict €0 (PROJECT.md budget). Provisioning dev only happens when staging actually becomes useful (post-v1).

### B. Entra External ID + OIDC trust

- **D-05:** External tenant provisioned **manually via Entra admin center (one-time, ~5min, free SKU)**, then `terraform import` brings it under state in `infra/bootstrap/identity.tf`. Reason: `azuread ~> 3.x` has no first-class tenant-creation resource as of Apr 2026 (closes STATE.md open question "Phase 3: Which Terraform resource type creates an Entra External ID tenant?"). All subsequent app registrations + federated credentials are pure TF (azuread provider). Documented runbook in `infra/bootstrap/README.md` covers portal click-path with version note (PITFALLS §1: External ID admin UX is changing).
- **D-06:** **One External tenant for both dev + prod**. SPA app registration carries multiple `single_page_application.redirect_uris` (prod SWA origin + `http://localhost:5173/` for local dev); API app registration exposes one `api://<api-app-id>/access_as_user` scope to both audiences. Free SKU on the single tenant (50k MAU); fits scaffold-only-dev (D-04) — one tenant means no dev-side tenant provisioning at all. Aligns with single-user-platform-ready scope.
- **D-07:** SPA app registration uses `single_page_application { redirect_uris = [...] }` block (NOT `web` platform — PITFALLS §2: PKCE green-checkmark requires this). API app registration uses Web API with no redirect URI; identifier URI = `api://<api-client-id>`. SPA registration adds delegated `access_as_user` permission against API registration with admin consent.
- **D-08:** Federated credential design: **two explicit per-trigger credentials** on the GitHub Actions service principal:
  1. Subject `repo:<owner>/<repo>:ref:refs/heads/master` for `deploy-api.yml` + `deploy-spa.yml` (push-to-master triggers).
  2. Subject `repo:<owner>/<repo>:environment:production` for `deploy-infra.yml` (manual approval gate via GH protected environment named `production`).
  Both RG-scoped Contributor, never subscription. **No PR-trigger credential** — PRs run only `terraform fmt -check` + `terraform validate` (no real-Azure plan); avoids rogue-PR token exfiltration risk. Skip claims-matching (PITFALLS §7: "easy to widen accidentally").
- **D-09:** **SEEDED_USER_ENTRA_OID propagation deferred to Phase 4**: Phase 3 lays the KV slot (empty secret named `seeded-user-entra-oid` with placeholder value) and ACA env wiring. Phase 4 plays out: Adrian completes first MSAL login → reads his real `oid` from the JWT → writes to KV → Phase-1's `00NN_adopt_entra_oid.py` migration (planned in Phase 1 D-09) reads from env at runtime and updates the seed row. Phase 3 outputs `swa_default_origin` + `api_app_client_id` + `tenant_subdomain` + KV name as TF outputs that Phase 4 consumes via tfvars/env.

### C. Postgres networking & secrets

- **D-10:** **Public access + firewall allowlist** for Postgres Flex Server. `public_network_access_enabled = true`, `require_secure_transport = on` (default). Firewall rules: (a) the static outbound IP exposed by `data "azurerm_container_app_environment"` for the prod env, (b) Adrian's home IP (variable in tfvars, regenerated as needed). **Skip private endpoint** — would force the ACA env into workload-profile + VNet integration tier, breaking the €0/mo budget (private endpoint ~€130/mo). Defer to v2 paid tier. Skip "Allow Azure services" toggle (defeats firewall purpose).
- **D-11:** **Random password (32-char alphanumeric) + Key Vault secret** for Postgres admin. `random_password` resource generates the value; constraint: alphanumeric only (avoids URL-encoding pain — Phase 1 STATE.md lessons: dev DB password with `&%!$` already caused alembic ConfigParser ConfigInterpolation issues). Stored as `azurerm_key_vault_secret` named `postgres-admin-password`. Container App pulls via managed identity + KV reference (D-13). Skip Entra-auth-on-Postgres for v1 — would rewrite Phase 1's password-URL-based SQLAlchemy engine config + break local Docker-Compose dev story; revisit in v2 platform-era.
- **D-12:** **Terraform creates the `jobrag` database; Alembic creates the `vector` extension.** Concrete sequencing:
  1. TF: `azure.extensions = "VECTOR"` server parameter (the per-server allowlist).
  2. TF: `azurerm_postgresql_flexible_server_database "jobrag"` explicitly creates the target DB.
  3. Container App startup → `init_db()` → `alembic upgrade head` → migration 0001 (Phase 1, already shipped) runs `CREATE EXTENSION IF NOT EXISTS vector` against the `jobrag` DB.
  Honors Phase 1 D-03 (extension creation lives in 0001 migration) + D-04 (init_db wraps alembic). Closes PITFALLS §9 (extension is per-database). Skip the `cyrilgdn/postgresql` provider — would split schema authority between TF and Alembic and require firewall punch-through for the GHA runner IP during apply.
- **D-13:** **Managed identity + KV references** for all Container App secret consumption. ACA system-assigned managed identity granted `Get` on Key Vault secrets via **RBAC** (modern, audit-friendly — `azurerm_role_assignment` of `Key Vault Secrets User` role); skip legacy access policies. Container App `secrets` block uses `key_vault_secret_id` references (NOT TF data-source literal injection — that flows the secret value through TF state). `template.container.env` references each secret by `secret_name`. KV stores: `openai-api-key`, `postgres-admin-password`, `langfuse-public-key`, `langfuse-secret-key`, `seeded-user-entra-oid` (placeholder for Phase 4). Secrets resolve at container start, rotate on revision swap.

### D. Integration model & guardrails

- **D-14:** **Direct CORS** for the SPA↔API path. SPA calls the ACA hostname directly; CORSMiddleware (Phase 1 D-26) allows the SWA origin. **DEPL-12 two-pass bootstrap** handles the cycle: first `terraform apply` discovers the SWA default origin via `data "azurerm_static_web_app"`, copies it into a tfvar, second apply injects it into the Container App's `ALLOWED_ORIGINS` env var. PITFALLS §10 alignment: single pattern, not mix. **Critical reason to reject SWA linked-API**: its proxy has ≈30–45s response timeout — would kill the `/agent/stream` SSE flow well before Phase 1's 60s app-level timeout. Phase 1 already wired CORS; reuse.
- **D-15:** **`terminationGracePeriodSeconds = 120`** on `azurerm_container_app.template` (Phase 1 D-17 carry-forward; PITFALLS §5). Allows 60s agent timeout (Phase 1 D-25) + 30s shutdown drain (Phase 1 D-17) + 30s buffer. Belt-and-suspenders on top of app-level drain; Envoy 240s ingress cap stays the hard outer ceiling.
- **D-16:** **Log Analytics: 0.15 GB/day daily quota + ConsoleLogs only.** Daily cap ≈4.5 GB/mo, leaves 5 GB/mo alert (DEPL-10) at ≈90% threshold. Diagnostic settings enable `ContainerAppConsoleLogs_CL` only (stdout — structlog JSON); skip `ContainerAppSystemLogs_CL` by default (revision-swap noise; can re-enable for one-off cold-start debugging via portal). Aligns PITFALLS §17 + DEPL-10 simultaneously.
- **D-17:** **No pre-warm cron in Phase 3.** Cold-start mitigation lives in Phase 6 (Chat) as distinct `connecting` → `warming` → `streaming` UI states (PITFALLS §4). Backend already preloads reranker in lifespan (Phase 1 D-27). Rationale: usage is ad-hoc demo + interview moments, not 9–5 traffic; waking ACA on a cron during arbitrary hours wastes free-tier budget on no real users. Reconsider only if portfolio demos become regular. Skip min_replicas=1 — blows the 180k vCPU-sec free grant by ~10x (≈€15–20/mo).
- **D-18:** **Budget alert: €10/month** at thresholds **50%, 75%, 90%, 100%** on the subscription scope. Triggers email to Adrian's address. Aligns DEPL-11 (single threshold) but with multiple notify points so a runaway resource gets caught at €5 not €10.

### Claude's Discretion

- Resource naming convention — recommended: `jobrag-{env}-{kind}` (e.g., `jobrag-prod-aca-env`, `jobrag-prod-pg`); module-level `locals.tf` builds names from env + project prefix.
- Tag policy — recommended: every resource carries `{ project = "job-rag", env = var.env, managed_by = "terraform" }`; module-level `locals.tags`.
- Provider version pin granularity — recommended `~> 4.69` on `azurerm` (keeps minor bumps automatic, blocks 5.x), `~> 3.0` on `azuread`, `~> 3.6` on `random` (per STACK.md).
- Postgres storage size + autogrow — recommended: 32 GB initial (free-tier max), `auto_grow_enabled = true` so the DB doesn't fail the first burst beyond 32 GB; cost beyond free tier is ~€0.10/GB/mo (still cheap).
- Postgres backup retention — recommended: 7 days (free-tier default; longer counts against storage allowance).
- Firewall rule for Adrian's home IP — variable in tfvars; regenerate via `tofu fmt` whenever ISP rotates the dynamic IP. Document refresh runbook.
- ACA `revision_mode` — recommended: `single` (default; simplest blue-green via traffic-split-on-deploy). Skip `multiple` (manual traffic shifting) for v1.
- KV soft-delete + purge protection — `soft_delete_retention_days = 7` (default), `purge_protection_enabled = true` (one-way switch; pick deliberately for prod). Recommended: enable purge protection in prod, disable in dev scaffold for easier teardown.
- KV access model — RBAC over access policies (D-13 implies; explicit decision: `enable_rbac_authorization = true`).
- Choice of GHA `actions/checkout@v4` vs `@v5` — recommended latest stable.
- LAW retention — 30 days (default; longer needs paid tier).
- `azure.extensions` value — `"VECTOR"` only in v1; can append `"PG_TRGM"` if Phase 5 fuzzy search ever needs it (deferred).
- Static Web Apps SKU region — recommended `westeurope` (Berlin proximity); Free SKU is multi-region anyway.
- Deploy-infra.yml protected environment auto-approve setting — Adrian as the sole required reviewer.

### Folded Todos

None — `gsd-tools todo match-phase 3` returned `todo_count: 0`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing Phase 3.**

### Phase scope and requirements
- `.planning/REQUIREMENTS.md` §DEPL-01 through §DEPL-12 — the 12 v1 requirements Phase 3 owns
- `.planning/ROADMAP.md` §Phase 3 — goal + 5 success criteria with concrete must-be-TRUE checks
- `.planning/PROJECT.md` §Constraints — Azure-only, Terraform-only, €0/mo budget, IaC scope
- `.planning/PROJECT.md` §Key Decisions — Azure free tier, GHCR over ACR, Entra External ID, Terraform workspaces (DEVIATION: Phase 3 uses envs/dirs per D-01 — log update)

### Prior phase decisions (carried forward — do NOT re-litigate)
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-03 — pgvector extension lives in 0001 migration (Phase 3 D-12 builds on this)
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-04 — `init_db()` wraps `alembic upgrade head`; Phase 3 ACA startup runs this against the TF-created `jobrag` database
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-08, §D-09, §D-10 — `SEEDED_USER_ID` Python constant + Phase 4 swap-in migration plan; Phase 3 D-09 lays the KV slot for Phase 4 to consume
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-17 — app-level shutdown drain (30s budget); Phase 3 D-15 adds the Terraform-side `terminationGracePeriodSeconds=120` belt-and-suspenders
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-25 — agent timeout 60s (bounds Phase 3 D-15 grace period)
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-26 — CORSMiddleware env-driven; Phase 3 D-14 + DEPL-12 two-pass injects the SWA origin
- `.planning/phases/01-backend-prep/01-CONTEXT.md` §D-29 — async pool `pool_size=3, max_overflow=2`, Alembic NullPool; Phase 3 must NOT change these (B1ms ≤35-effective-conn budget)
- `.planning/phases/02-corpus-cleanup/02-CONTEXT.md` §D-17 — lifespan startup prompt-version drift query; Phase 3 must preserve the structured warning output during ACA cold-start

### Pitfalls research (HIGH confidence, critical for this phase)
- `.planning/research/PITFALLS.md` §1 — wrong tenant type (External vs workforce/B2C); Phase 3 D-05 alignment
- `.planning/research/PITFALLS.md` §2 — SPA registered as Web vs SPA platform; Phase 3 D-07 alignment (`single_page_application` block)
- `.planning/research/PITFALLS.md` §3 — Envoy 240s SSE cap; Phase 3 D-15 grace period stays under
- `.planning/research/PITFALLS.md` §4 — scale-to-zero cold start; Phase 3 D-17 defers UX mitigation to Phase 6
- `.planning/research/PITFALLS.md` §5 — SIGTERM during revision swap drops SSE; Phase 3 D-15 = 120s grace period
- `.planning/research/PITFALLS.md` §7 — OIDC subject claim mismatch; Phase 3 D-08 = per-trigger explicit creds
- `.planning/research/PITFALLS.md` §8 — B1ms connection exhaustion; respected via Phase 1 D-29 pool sizing
- `.planning/research/PITFALLS.md` §9 — pgvector per-database; Phase 3 D-12 = TF creates DB, Alembic creates extension
- `.planning/research/PITFALLS.md` §10 — SWA linked-API CORS confusion; Phase 3 D-14 = direct CORS only
- `.planning/research/PITFALLS.md` §13 — Terraform bootstrap chicken-and-egg; Phase 3 D-02 = dedicated `bootstrap/` with local state
- `.planning/research/PITFALLS.md` §14 — workspace confusion; Phase 3 D-01 = envs/dirs over workspaces
- `.planning/research/PITFALLS.md` §17 — free-tier cost surprises; Phase 3 D-16 (LAW caps) + D-18 (budget alerts)
- `.planning/research/PITFALLS.md` §"Looks Done But Isn't Checklist" — verifiers: JWT `iss` ciamlogin.com, SSE streams in prod EventStream tab, `\dx` shows vector in `jobrag` DB, OIDC works for actual trigger, LAW daily_quota_gb non-default, CORS rejects unknown origins

### Stack research (HIGH confidence)
- `.planning/research/STACK.md` §2 — Azure services: ACA Consumption, B1ms Postgres + pgvector, SWA Free, KV Standard, GHCR over ACR
- `.planning/research/STACK.md` §3 — Entra External ID: External tenant via Terraform `azurerm_*` + `azuread_*`, MSAL authority `*.ciamlogin.com/v2.0`, two app regs (SPA + API)
- `.planning/research/STACK.md` §4 — Terraform: 1.9+, `azurerm ~> 4.69`, `azuread ~> 3.x`, remote state in Azure Storage, workspace pattern (Phase 3 D-01 deviates to envs/dirs)
- `.planning/research/STACK.md` §5 — GHA OIDC: `azure/login@v2` with `id-token: write`, federated credential per trigger, RG-scoped Contributor
- `.planning/research/STACK.md` "Stack Patterns by Variant" — single-user-past-v1 path noted

### Codebase audit (Phase 3 must not break)
- `.planning/codebase/ARCHITECTURE.md` — three-tier layering (Ingestion / Retrieval+Matching / Intelligence/Tools); Phase 3 is platform-plane only, doesn't touch tiers
- `.planning/codebase/STACK.md` — backend frozen (Python 3.12, FastAPI, LangGraph 1.1.x, SQLAlchemy 2.x async, Instructor); Phase 3 adds Azure platform on top, no backend stack changes
- `.planning/codebase/CONCERNS.md` §"Async/sync session dualism in ingest endpoint" — still deferred (Phase 1+2 carry-forward); Phase 3 doesn't close it
- `src/job_rag/db/engine.py` — both `engine` (sync, psycopg2) and `async_engine` (asyncpg) consume `DATABASE_URL` / `ASYNC_DATABASE_URL`; Phase 3 must inject both env vars from KV/managed identity
- `src/job_rag/api/app.py` — lifespan currently expects `ALLOWED_ORIGINS` env var (Phase 1 D-26); Phase 3 DEPL-12 second-apply injects the SWA origin
- `Dockerfile` — multi-stage CPU-only PyTorch build; Phase 3 builds + pushes this to GHCR
- `docker-compose.yml` — local-dev only; Phase 3 doesn't change this surface
- `.github/workflows/ci.yml` — Phase 1 added postgres service + alembic upgrade smoke + grep guard; Phase 3 adds three NEW workflows (`deploy-infra.yml`, `deploy-api.yml`, `deploy-spa.yml`) but does NOT touch ci.yml

### Stack/topology baselines for Phase 4 hand-off
- TF outputs Phase 4 will consume: `swa_default_origin`, `api_app_client_id`, `spa_app_client_id`, `tenant_subdomain`, `tenant_id`, `kv_name`, `aca_fqdn`, `seeded_user_entra_oid_secret_name` (placeholder)
- Phase 4 receives these via either (a) `terraform output -json` written to a generated tfvars file, or (b) GHA Actions secrets exported during `deploy-infra.yml`
- MSAL authority URL Phase 4 will compute: `https://${tenant_subdomain}.ciamlogin.com/${tenant_id}/v2.0`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 1 CORSMiddleware wiring** (`src/job_rag/api/app.py` lines after lifespan setup) — env-var driven via `settings.allowed_origins`; Phase 3 DEPL-12 two-pass injects SWA origin into this list, no code change.
- **Phase 1 settings model** (`src/job_rag/config.py`) — `allowed_origins: list[str]` already accepts CSV; ACA env var injection just sets the value.
- **`init_db()` Alembic wrapper** (Phase 1 D-04) — runs at Container App startup; Phase 3's TF-created `jobrag` DB receives Alembic-driven `CREATE EXTENSION vector` from migration 0001 automatically.
- **Phase 1 lifespan shutdown drain** (`api/app.py`, D-17) — 30s budget; pairs with Phase 3 D-15 `terminationGracePeriodSeconds=120` for clean revision swaps.
- **Existing CI workflow** (`.github/workflows/ci.yml`) — runs ruff/pyright/pytest + postgres service + alembic smoke + grep guard. Phase 3 adds three NEW deploy workflows alongside; ci.yml unchanged.
- **Multi-stage Dockerfile** — already optimized for CPU-only torch; ready to push to GHCR without modification.

### Established Patterns
- **structlog `get_logger(__name__)`** — pattern for any new infra-scripts/runbook helpers Phase 3 ships (none anticipated, but consistent if needed).
- **uv for Python deps** — Phase 3's GHA workflows use `astral-sh/setup-uv@v5` to match dev toolchain (STACK.md §5).
- **Pinning provider versions** — Phase 1 pinned alembic to 1.18.4; Phase 3 pins `azurerm ~> 4.69`, `azuread ~> 3.x`, `random ~> 3.6` per STACK.md.
- **Per-statement commit + log+continue pattern** (Phase 2 D-16) — not relevant to Phase 3 (platform plane, no batch ops).

### Integration Points
- **`Dockerfile`** — Phase 3's `deploy-api.yml` builds + pushes to GHCR; tag pattern `ghcr.io/<owner>/job-rag:${{ github.sha }}` + `:latest`.
- **`apps/web/dist/`** — Phase 4 produces this via `npm run build`; Phase 3's `deploy-spa.yml` consumes it via `azure/static-web-apps-deploy@v1`. Phase 3 doesn't ship the SPA itself, just the workflow + SWA resource.
- **GitHub repository settings** — Phase 3 adds protected environment `production` with required reviewer = Adrian; secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` populated from bootstrap outputs; secret `AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` from SWA deployment token.
- **Adrian's Azure subscription** — bootstrap requires Owner-level access on the subscription for first run; subsequent operations run under the github-actions service principal at RG-scope.
- **Phase 1's `init_db()` startup** — runs Alembic against the `ASYNC_DATABASE_URL` injected from KV via managed identity at ACA startup; Phase 3's TF-created `jobrag` DB must be reachable + the managed identity must have the password secret available before the container starts (TF dependency ordering: KV secret + access role assignment created BEFORE Container App resource).

</code_context>

<specifics>
## Specific Ideas

- Adrian continues the Phase 1 (17/17 Recommended) and Phase 2 (16/16 Recommended) pattern: 16/16 Recommended in Phase 3. Downstream agents should keep presenting concrete recommendations + rationale + counterfactuals; bare alternatives waste a turn.
- The PROJECT.md "Terraform workspaces" Key Decision row is now superseded by Phase 3 D-01 (envs/dirs). Update PROJECT.md Key Decisions table at phase close to reflect: "Terraform envs/dirs over workspaces — PITFALLS §14 + DEPL-02 spec; dev/prod drift expected."
- The STATE.md open question "Phase 3: Which Terraform resource type creates an Entra External ID tenant?" is now closed (Phase 3 D-05): no first-class resource exists in azuread ~> 3.x; manual portal bootstrap + `terraform import` is the documented path.
- The STATE.md open question "Phase 3: Is the SWA deployment token the only non-OIDC secret?" is now answered (Phase 3 D-08 + DEPL-09 alignment): yes — every other Azure auth uses OIDC federated credentials. Document the SWA token as the sole long-lived secret in `infra/envs/prod/README.md` with rotation cadence (180-day Microsoft default).
- The two-pass CORS bootstrap (DEPL-12) is concrete: first apply leaves `ALLOWED_ORIGINS = ["http://localhost:5173"]` (placeholder), terraform outputs the SWA default origin, second apply uses `var.swa_origin` injected from a script (`scripts/refresh-swa-origin.sh`) that reads `terraform output` and re-applies. Document the two-pass step in `infra/envs/prod/README.md`.
- Phase 4 must carry forward: the placeholder KV secret `seeded-user-entra-oid` (D-09) → fill it after first MSAL login → run the existing Phase 1 D-09 migration plan (`00NN_adopt_entra_oid.py`).
- **Reusable-tool framing** (per `~/.claude/projects/.../memory/feedback_reusable_tools.md` from Phase 2): if Phase 3 generates any one-shot operational scripts (e.g., `scripts/refresh-swa-origin.sh`, `scripts/firewall-update-home-ip.sh`), the planner should consider whether to fold them as first-class CLI subcommands with idempotent selection, OR keep them as throwaway scripts. Probably keep as `scripts/` for genuinely one-shot infra glue (low reuse expected).

</specifics>

<deferred>
## Deferred Ideas

- **Private endpoint + VNet integration** for Postgres (D-10 trade-off). Cost ~€130/mo; defer to v2 paid tier.
- **Entra-auth-on-Postgres** (passwordless, managed identity) (D-11 trade-off). Defer to v2 platform-era when local Docker-Compose dev story rewrite is acceptable.
- **PR-trigger OIDC credential** for `terraform plan` on PRs (D-08). Useful when infra changes get reviewed often; marginal for single-engineer repo. Add when a second contributor appears.
- **Pre-warm cron for cold-start** (D-17). Reconsider if portfolio demos become regular (e.g., weekly interview cycle); GHA cron is cheap (~32k vCPU-sec/mo) but unwarranted for ad-hoc usage.
- **Claims-matching-expression OIDC credential** (D-08). Add when a third or fourth trigger shape appears (currently 2: master push + environment:production).
- **Separate dev tenant** for Entra (D-06). Defer to v2 if multi-user testing reveals one-tenant-multi-redirect contention.
- **`min_replicas=1`** for permanent warm-pool. Blows €0 budget by ~€15–20/mo. Defer until paid tier is acceptable.
- **`PG_TRGM` extension** in `azure.extensions` allowlist (Claude's Discretion). Add if Phase 5 fuzzy search needs it; not required for v1.
- **AVM module for ACA** when the official module matures. Currently `avm/res/app/container-app` is in progress; revisit at Phase 3 v1 closeout.
- **Azure Monitor availability test** for `/health` endpoint. Free tier includes 5 tests; useful proactive monitoring. Defer to Phase 8 (observability + docs polish) unless cold-start hits become a real complaint.
- **AVM-only refactor** (D-03 trade-off). If AVM modules mature across the board by Phase 8, consider a v2 plan to migrate raw azurerm → AVM uniformly for the portfolio talking point.
- **Backup retention beyond 7 days** (Claude's Discretion). Free tier covers 7d; longer counts against storage. Bump if compliance requirements emerge.
- **ContainerAppSystemLogs_CL ingestion** (D-16 trade-off). Re-enable for one-off cold-start / revision-swap forensics; not default-on due to ingest budget.
- **Cost-diff PR check** (e.g., `infracost`). Useful but scope creep for v1; revisit if infra changes get frequent.
- **Phase-2 follow-up triage plan** for the 10 persistent extraction failures. Stays as standalone Phase-2-rev work; does NOT fold into Phase 3.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 3` returned `todo_count: 0`.

</deferred>

---

*Phase: 03-infrastructure-ci-cd*
*Context gathered: 2026-04-29*
