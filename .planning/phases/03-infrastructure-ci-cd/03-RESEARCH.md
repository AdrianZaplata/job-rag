# Phase 3: Infrastructure & CI/CD — Research

**Researched:** 2026-04-29
**Domain:** Terraform IaC + Azure Container Apps + Postgres Flex + Entra External ID + Static Web Apps + Key Vault + Log Analytics + GitHub Actions OIDC
**Confidence:** HIGH on all major surfaces (Context7-equivalent: official Microsoft Learn + Terraform Registry + AVM module repos verified live April 2026); MEDIUM on a single architectural finding flagged below that requires user confirmation before locking the plan.

---

## Summary

Phase 3 provisions the entire production stack with Terraform: an Entra External tenant (manually bootstrapped, then `terraform import`-ed), an Azure Container Apps environment + Container App on the Consumption plan, a Postgres Flexible Server B1ms with `vector` extension allowlisted and a `jobrag` database created, a Static Web App on the Free SKU, a Key Vault with RBAC + managed-identity secret references, a Log Analytics workspace with a 0.15 GB/day cap, a €10/month subscription budget, and three OIDC-federated GitHub Actions workflows. The entire surface is documented and version-pinned; AVM modules are used for KV / Postgres / LAW (per CONTEXT.md D-03), raw `azurerm` for Container Apps + SWA, raw `azuread` for the app registrations + federated credentials.

The most important new finding from this research is **architectural — not a recommendation change, but a load-bearing assumption to verify with the user before plans lock**. CONTEXT.md D-10 specifies firewalling the Postgres Flexible Server to "the static outbound IP exposed by `data \"azurerm_container_app_environment\"` for the prod env." Microsoft's official guidance (cross-referenced in two sources, including a Microsoft-owned Q&A) is that **Consumption-only Container Apps environments do NOT guarantee a static outbound IP** — `static_ip_address` is documented as "may change over time" for Consumption tier. A static outbound IP is only guaranteed by Workload Profiles + NAT Gateway, which costs ~€30+/mo and breaks the €0/mo budget. Three resolution paths exist (Path A "Allow-Azure-services" 0.0.0.0 firewall rule + strong DB password + TLS-only + non-default port; Path B revisit budget for NAT Gateway; Path C take the documented risk and add a manual refresh runbook). My recommendation is **Path A** — see §"Common Pitfalls → Pitfall: ACA Consumption outbound IP is not static" for full reasoning. Plan-time decision only; does not block research.

**Primary recommendation:** Adopt the locked CONTEXT.md decisions verbatim; verify the ACA outbound IP assumption with Adrian (Path A is the cheapest viable path that preserves the firewall-allowlist intent of D-10) before plan-locking; pin AVM modules at versions verified below; structure the Terraform tree in eight `.tf` files per env directory matching CONTEXT.md D-01.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### A. Terraform layout & bootstrap

- **D-01:** Repo structure follows REQUIREMENTS DEPL-02 verbatim — `infra/envs/{dev,prod}/` directories each call shared `infra/modules/{network,database,compute,identity,monitoring,kv}`. Each env has a separate state file in the same Azure Blob backend (different `key=`). PITFALLS §14 alignment: directories over workspaces because dev/prod drift is expected (different SKUs, possibly different auth tier later). **Documented deviation from PROJECT.md "Terraform workspaces" Key Decision** — log in PROJECT.md Key Decisions table at phase close ("Terraform envs/dirs over workspaces; PITFALLS §14 + DEPL-02 spec").
- **D-02:** Bootstrap chicken-and-egg (PITFALLS §13) handled by a dedicated `infra/bootstrap/` directory: creates the state-storage RG + storage account (versioning + 7d soft-delete) + state container. **LOCAL state, .gitignored.** One-time run via README runbook; outputs (`storage_account_name`, `container_name`, `resource_group_name`) copied as static literals into `infra/envs/{dev,prod}/backend.tf`. Bootstrap directory remains in repo for reproducibility but its `terraform.tfstate` is never committed.
- **D-03:** Selective AVM adoption per DEPL-02 ("where available"):
  - Use AVM: `avm/res/key-vault/vault`, `avm/res/operational-insights/workspace`, `avm/res/db-for-postgresql/flexible-server`.
  - Skip AVM (use raw azurerm): Container App + Container App Environment (AVM module still maturing as of Apr 2026; raw `azurerm_container_app` is well-trodden), Static Web App (one-resource module = no abstraction value), `azuread` resources (no AVM coverage).
  - Per-resource decision documented in `infra/modules/{kind}/README.md`.
- **D-04:** Dev environment is **scaffold-only, never applied in v1**. `infra/envs/dev/` exists with full *.tf + `dev.tfvars` + `backend.tf` pointing at a separate state key; `terraform plan` works as a sanity-check; `apply` is documented-but-deferred. Cost stays at strict €0 (PROJECT.md budget). Provisioning dev only happens when staging actually becomes useful (post-v1).

#### B. Entra External ID + OIDC trust

- **D-05:** External tenant provisioned **manually via Entra admin center (one-time, ~5min, free SKU)**, then `terraform import` brings it under state in `infra/bootstrap/identity.tf`. Reason: `azuread ~> 3.x` has no first-class tenant-creation resource as of Apr 2026 (closes STATE.md open question "Phase 3: Which Terraform resource type creates an Entra External ID tenant?"). All subsequent app registrations + federated credentials are pure TF (azuread provider). Documented runbook in `infra/bootstrap/README.md` covers portal click-path with version note (PITFALLS §1: External ID admin UX is changing).
- **D-06:** **One External tenant for both dev + prod**. SPA app registration carries multiple `single_page_application.redirect_uris` (prod SWA origin + `http://localhost:5173/` for local dev); API app registration exposes one `api://<api-app-id>/access_as_user` scope to both audiences. Free SKU on the single tenant (50k MAU); fits scaffold-only-dev (D-04) — one tenant means no dev-side tenant provisioning at all. Aligns with single-user-platform-ready scope.
- **D-07:** SPA app registration uses `single_page_application { redirect_uris = [...] }` block (NOT `web` platform — PITFALLS §2: PKCE green-checkmark requires this). API app registration uses Web API with no redirect URI; identifier URI = `api://<api-client-id>`. SPA registration adds delegated `access_as_user` permission against API registration with admin consent.
- **D-08:** Federated credential design: **two explicit per-trigger credentials** on the GitHub Actions service principal:
  1. Subject `repo:<owner>/<repo>:ref:refs/heads/master` for `deploy-api.yml` + `deploy-spa.yml` (push-to-master triggers).
  2. Subject `repo:<owner>/<repo>:environment:production` for `deploy-infra.yml` (manual approval gate via GH protected environment named `production`).
  Both RG-scoped Contributor, never subscription. **No PR-trigger credential** — PRs run only `terraform fmt -check` + `terraform validate` (no real-Azure plan); avoids rogue-PR token exfiltration risk. Skip claims-matching (PITFALLS §7: "easy to widen accidentally").
- **D-09:** **SEEDED_USER_ENTRA_OID propagation deferred to Phase 4**: Phase 3 lays the KV slot (empty secret named `seeded-user-entra-oid` with placeholder value) and ACA env wiring. Phase 4 plays out: Adrian completes first MSAL login → reads his real `oid` from the JWT → writes to KV → Phase-1's `00NN_adopt_entra_oid.py` migration (planned in Phase 1 D-09) reads from env at runtime and updates the seed row. Phase 3 outputs `swa_default_origin` + `api_app_client_id` + `tenant_subdomain` + KV name as TF outputs that Phase 4 consumes via tfvars/env.

#### C. Postgres networking & secrets

- **D-10:** **Public access + firewall allowlist** for Postgres Flex Server. `public_network_access_enabled = true`, `require_secure_transport = on` (default). Firewall rules: (a) the static outbound IP exposed by `data "azurerm_container_app_environment"` for the prod env, (b) Adrian's home IP (variable in tfvars, regenerated as needed). **Skip private endpoint** — would force the ACA env into workload-profile + VNet integration tier, breaking the €0/mo budget (private endpoint ~€130/mo). Defer to v2 paid tier. Skip "Allow Azure services" toggle (defeats firewall purpose). **⚠️ Research finding: see §Common Pitfalls. Microsoft documents that ACA Consumption-tier outbound IP is NOT guaranteed static; this assumption needs Adrian's confirmation at plan-time.**
- **D-11:** **Random password (32-char alphanumeric) + Key Vault secret** for Postgres admin. `random_password` resource generates the value; constraint: alphanumeric only (avoids URL-encoding pain — Phase 1 STATE.md lessons: dev DB password with `&%!$` already caused alembic ConfigParser ConfigInterpolation issues). Stored as `azurerm_key_vault_secret` named `postgres-admin-password`. Container App pulls via managed identity + KV reference (D-13). Skip Entra-auth-on-Postgres for v1 — would rewrite Phase 1's password-URL-based SQLAlchemy engine config + break local Docker-Compose dev story; revisit in v2 platform-era.
- **D-12:** **Terraform creates the `jobrag` database; Alembic creates the `vector` extension.** Concrete sequencing:
  1. TF: `azure.extensions = "VECTOR"` server parameter (the per-server allowlist).
  2. TF: `azurerm_postgresql_flexible_server_database "jobrag"` explicitly creates the target DB.
  3. Container App startup → `init_db()` → `alembic upgrade head` → migration 0001 (Phase 1, already shipped) runs `CREATE EXTENSION IF NOT EXISTS vector` against the `jobrag` DB.
  Honors Phase 1 D-03 (extension creation lives in 0001 migration) + D-04 (init_db wraps alembic). Closes PITFALLS §9 (extension is per-database). Skip the `cyrilgdn/postgresql` provider — would split schema authority between TF and Alembic and require firewall punch-through for the GHA runner IP during apply.
- **D-13:** **Managed identity + KV references** for all Container App secret consumption. ACA system-assigned managed identity granted `Get` on Key Vault secrets via **RBAC** (modern, audit-friendly — `azurerm_role_assignment` of `Key Vault Secrets User` role); skip legacy access policies. Container App `secrets` block uses `key_vault_secret_id` references (NOT TF data-source literal injection — that flows the secret value through TF state). `template.container.env` references each secret by `secret_name`. KV stores: `openai-api-key`, `postgres-admin-password`, `langfuse-public-key`, `langfuse-secret-key`, `seeded-user-entra-oid` (placeholder for Phase 4). Secrets resolve at container start, rotate on revision swap.

#### D. Integration model & guardrails

- **D-14:** **Direct CORS** for the SPA↔API path. SPA calls the ACA hostname directly; CORSMiddleware (Phase 1 D-26) allows the SWA origin. **DEPL-12 two-pass bootstrap** handles the cycle: first `terraform apply` discovers the SWA default origin via `data "azurerm_static_web_app"`, copies it into a tfvar, second apply injects it into the Container App's `ALLOWED_ORIGINS` env var. PITFALLS §10 alignment: single pattern, not mix. **Critical reason to reject SWA linked-API**: its proxy has ≈30–45s response timeout — would kill the `/agent/stream` SSE flow well before Phase 1's 60s app-level timeout. Phase 1 already wired CORS; reuse.
- **D-15:** **`terminationGracePeriodSeconds = 120`** on `azurerm_container_app.template` (Phase 1 D-17 carry-forward; PITFALLS §5). Allows 60s agent timeout (Phase 1 D-25) + 30s shutdown drain (Phase 1 D-17) + 30s buffer. Belt-and-suspenders on top of app-level drain; Envoy 240s ingress cap stays the hard outer ceiling.
- **D-16:** **Log Analytics: 0.15 GB/day daily quota + ConsoleLogs only.** Daily cap ≈4.5 GB/mo, leaves 5 GB/mo alert (DEPL-10) at ≈90% threshold. Diagnostic settings enable `ContainerAppConsoleLogs_CL` only (stdout — structlog JSON); skip `ContainerAppSystemLogs_CL` by default (revision-swap noise; can re-enable for one-off cold-start debugging via portal). Aligns PITFALLS §17 + DEPL-10 simultaneously.
- **D-17:** **No pre-warm cron in Phase 3.** Cold-start mitigation lives in Phase 6 (Chat) as distinct `connecting` → `warming` → `streaming` UI states (PITFALLS §4). Backend already preloads reranker in lifespan (Phase 1 D-27). Rationale: usage is ad-hoc demo + interview moments, not 9–5 traffic; waking ACA on a cron during arbitrary hours wastes free-tier budget on no real users. Reconsider only if portfolio demos become regular. Skip min_replicas=1 — blows the 180k vCPU-sec free grant by ~10x (≈€15–20/mo).
- **D-18:** **Budget alert: €10/month** at thresholds **50%, 75%, 90%, 100%** on the subscription scope. Triggers email to Adrian's address. Aligns DEPL-11 (single threshold) but with multiple notify points so a runaway resource gets caught at €5 not €10.

### Claude's Discretion

- Resource naming convention — recommended: `jobrag-{env}-{kind}` (e.g., `jobrag-prod-aca-env`, `jobrag-prod-pg`); module-level `locals.tf` builds names from env + project prefix.
- Tag policy — recommended: every resource carries `{ project = "job-rag", env = var.env, managed_by = "terraform" }`; module-level `locals.tags`.
- Provider version pin granularity — recommended `~> 4.69` on `azurerm` (keeps minor bumps automatic, blocks 5.x), `~> 3.0` on `azuread`, `~> 3.6` on `random` (per STACK.md).
- Postgres storage size + autogrow — recommended: 32 GB initial (free-tier max), `auto_grow_enabled = true`.
- Postgres backup retention — 7 days (free-tier default).
- Firewall rule for Adrian's home IP — variable in tfvars; document refresh runbook.
- ACA `revision_mode` — `single` (default; simplest blue-green via traffic-split-on-deploy).
- KV soft-delete + purge protection — `soft_delete_retention_days = 7`, `purge_protection_enabled = true` in prod.
- KV access model — RBAC over access policies (D-13 implies; explicit decision: `enable_rbac_authorization = true` / `legacy_access_policies_enabled = false`).
- Choice of GHA `actions/checkout` — recommended latest stable.
- LAW retention — 30 days (default; longer needs paid tier).
- `azure.extensions` value — `"VECTOR"` only in v1; can append `"PG_TRGM"` later if Phase 5 fuzzy search needs it.
- Static Web Apps SKU region — `westeurope` (Berlin proximity); Free SKU is multi-region anyway.
- Deploy-infra.yml protected environment auto-approve setting — Adrian as the sole required reviewer.

### Deferred Ideas (OUT OF SCOPE)

- **Private endpoint + VNet integration** for Postgres (D-10 trade-off). Cost ~€130/mo; defer to v2 paid tier.
- **Entra-auth-on-Postgres** (passwordless, managed identity) (D-11 trade-off). Defer to v2 platform-era.
- **PR-trigger OIDC credential** for `terraform plan` on PRs (D-08). Add when a second contributor appears.
- **Pre-warm cron for cold-start** (D-17). Reconsider if portfolio demos become regular.
- **Claims-matching-expression OIDC credential** (D-08). Add when a third or fourth trigger shape appears.
- **Separate dev tenant** for Entra (D-06). Defer to v2 if multi-user testing reveals contention.
- **`min_replicas=1`** for permanent warm-pool. Blows €0 budget by ~€15–20/mo. Defer until paid tier is acceptable.
- **`PG_TRGM` extension** in `azure.extensions` allowlist (Claude's Discretion). Add if Phase 5 fuzzy search needs it.
- **AVM module for ACA** when the official module matures.
- **Azure Monitor availability test** for `/health` endpoint. Defer to Phase 8.
- **AVM-only refactor** (D-03 trade-off). Defer to a Phase 8 portfolio polish pass if all AVM modules mature.
- **Backup retention beyond 7 days** (Claude's Discretion).
- **ContainerAppSystemLogs_CL ingestion** (D-16 trade-off). Re-enable for one-off forensics.
- **Cost-diff PR check** (e.g., `infracost`). Scope creep for v1.
- **NAT Gateway + Workload Profiles** for static outbound IP (research-flagged; see Common Pitfalls). ~€30+/mo defer to paid tier.
- **Phase-2 follow-up triage plan** for the 10 persistent extraction failures. Stays as standalone Phase-2-rev work.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPL-01 | Terraform remote state backend on Azure Blob Storage with state-locking | §Architecture Pattern 1 (Bootstrap split + remote state); CONTEXT.md D-02. Verified: `azurerm` backend type natively supports state locking via blob lease since 2024. |
| DEPL-02 | `infra/envs/{dev,prod}` calling `infra/modules/*`; AVM where available | §Recommended Project Structure; §Architecture Pattern 2 (envs/dirs); CONTEXT.md D-01 + D-03. AVM module versions verified live on Terraform Registry / GitHub. |
| DEPL-03 | ACA env + Container App, min_replicas=0 max_replicas=1 | §Code Examples → "Container App with KV-backed secrets"; CONTEXT.md D-15. Raw `azurerm_container_app` resource shape verified Apr 2026. |
| DEPL-04 | Postgres Flex B1ms + pgvector + pool (3+2) | §Code Examples → "Postgres Flex with vector extension"; pool sizing already shipped Phase 1 D-29 / `db/engine.py`. |
| DEPL-05 | SWA Free SKU for Vite output | §Code Examples → "Static Web App"; api_key output is the only long-lived secret needed (closes STATE.md open question). |
| DEPL-06 | KV stores OPENAI / DB pwd / Langfuse keys; ACA pulls via MI at runtime | §Code Examples → "AVM Key Vault + role assignment"; §Architecture Pattern 4 (KV reference flow). |
| DEPL-07 | GHCR (not ACR Basic) for container images | §Code Examples → "deploy-api.yml" uses `docker/build-push-action@v6` + GHCR login. Saves €4-5/mo + free egress to Azure. |
| DEPL-08 | Three workflows (deploy-infra/api/spa) with `paths` filters | §Code Examples → "Three GHA workflow skeletons"; CONTEXT.md D-08 = two federated creds. |
| DEPL-09 | OIDC fed-cred per trigger; RG-scoped Contributor; SWA token only |  §Code Examples → "azuread_application_federated_identity_credential"; SWA `api_key` output is sensitive=true → GH secret. |
| DEPL-10 | LAW captures logs; 5 GB/mo quota alert | §Code Examples → "AVM LAW + diagnostic setting"; daily quota 0.15 GB ≈ 4.5 GB/mo (90% of 5 GB alert). |
| DEPL-11 | Budget €10/mo, alert 80%/100% (CONTEXT.md D-18 widens to 50/75/90/100) | §Code Examples → "azurerm_consumption_budget_subscription"; multi-threshold pattern verified. |
| DEPL-12 | Two-pass deploy injecting SWA origin into ALLOWED_ORIGINS | §Architecture Pattern 5 (two-pass CORS); §Code Examples → "scripts/refresh-swa-origin.sh". |
</phase_requirements>

---

## Architectural Responsibility Map

> Reasoning step before research-domain investigation: which architectural tier owns each Phase 3 capability?

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| State storage (Blob backend) | Azure Storage (platform) | — | State must outlive any dev workstation; managed by Azure, not the app |
| Identity / app registrations | Entra External tenant | — | Tenant is the auth root; SPA + API regs live there, not in workforce tenant |
| Container hosting | Container Apps environment + Container App | — | Pure backend tier; SPA does NOT run here |
| Static asset hosting | Static Web Apps (CDN/edge) | — | Browser-cacheable assets; never Container Apps (wastes vCPU-s budget on file serving) |
| Database | Postgres Flexible Server | — | Persistence tier; backend-only; no direct browser access |
| Secret storage | Key Vault | — | Platform-managed secrets; ACA pulls via MI, never literals in TF state |
| Log aggregation | Log Analytics workspace | Azure Monitor | Diagnostic settings forward ACA stdout |
| Cost guardrails | Subscription-scoped budget | Action group / email | Subscription is the only billing scope that catches stray RGs |
| Trust to GitHub | Entra app reg + federated credential | RG-scoped role assignment | OIDC = no long-lived secrets; per-trigger subject |
| Build pipeline | GitHub Actions (CI/CD) | GHCR | Image build/push happens on GH runners; Azure pulls from GHCR at deploy |
| CORS allowlist | FastAPI app (already shipped Phase 1) | — | Direct CORS pattern (D-14); no proxy layer modifies this |

This map is the sanity-check the planner uses before assigning tasks. Misassignments to watch: (1) putting the SPA in Container Apps (wrong tier — kills free-tier budget), (2) putting JWT validation in the SPA (wrong tier — must be backend per AUTH-05), (3) firewalling Postgres at the VNet level (wrong tier — would force Workload Profiles).

---

## Standard Stack

### Core (verified live April 2026)

| Library / Module | Version | Purpose | Why Standard |
|------------------|---------|---------|--------------|
| Terraform CLI | ≥ 1.9 | IaC runner | LTS line; `azurerm ~> 4.69` requires 1.9+ for provider-defined functions [VERIFIED: Terraform Registry] |
| `hashicorp/azurerm` | `~> 4.69` | Azure resource primitives | v4 line is current; v5 unreleased as of Apr 2026; `~>` keeps minor bumps but blocks unannounced breaking 5.x [VERIFIED: github.com/hashicorp/terraform-provider-azurerm/releases] |
| `hashicorp/azuread` | `~> 3.0` | Entra app regs + federated credentials | v3 series stable; v3.x has the `single_page_application` block + federated_identity_credential resource needed [CITED: terraform-provider-azuread upgrade-guide-3.0] |
| `hashicorp/random` | `~> 3.6` | Random password / suffix gen | Used for the 32-char alphanumeric Postgres admin password (D-11) [VERIFIED: registry] |
| `Azure/avm-res-keyvault-vault/azurerm` | **`0.10.2`** (Oct 14 2025) | Key Vault | AVM module — RBAC support via `legacy_access_policies_enabled = false`; bundles secret + role-assignment children [VERIFIED: github.com/Azure/terraform-azurerm-avm-res-keyvault-vault releases] |
| `Azure/avm-res-operationalinsights-workspace/azurerm` | **`0.5.1`** (Dec 23 2025) | Log Analytics workspace | AVM module — `log_analytics_workspace_daily_quota_gb` input maps to the daily cap (D-16) [VERIFIED: github.com/Azure/terraform-azurerm-avm-res-operationalinsights-workspace releases] |
| `Azure/avm-res-dbforpostgresql-flexibleserver/azurerm` | **`0.2.2`** (Apr 14 2026) | Postgres Flex Server | AVM module — `server_configuration` map accepts `azure.extensions` parameter; `databases` map creates the `jobrag` DB [VERIFIED: github.com/Azure/terraform-azurerm-avm-res-dbforpostgresql-flexibleserver releases] |

### Supporting (raw `azurerm` resources — AVM not used per CONTEXT.md D-03)

| Resource | Purpose | When to Use |
|----------|---------|-------------|
| `azurerm_resource_group` | Container for all Phase 3 prod resources | Single RG `jobrag-prod-rg`; RG-scoped Contributor RBAC matches CONTEXT.md D-08 |
| `azurerm_container_app_environment` | ACA host environment | Required by every Container App; pairs with the LAW workspace |
| `azurerm_container_app` | The API container itself | Raw — AVM `avm/res/app/container-app` still maturing per D-03 |
| `azurerm_container_app_environment` (data source) | Read static IP after env exists | Used in two-pass apply IF firewall path includes ACA IP (see Pitfall) |
| `azurerm_postgresql_flexible_server_firewall_rule` | Allowlist for Adrian's home IP + (conditionally) ACA outbound | Raw — AVM module handles this via `firewall_rules` map but the user's discretion is to keep it explicit |
| `azurerm_static_web_app` | SWA Free SKU for the Vite SPA | Raw — single-resource module; AVM offers no abstraction value [CITED: registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/static_web_app] |
| `azurerm_static_web_app` (data source) | Read `default_host_name` for second apply | DEPL-12 two-pass: first apply creates SWA; second apply injects origin into ACA env var |
| `azuread_application` | SPA + API + GitHub Actions app regs | Raw — no AVM coverage for `azuread` resources |
| `azuread_service_principal` | Backing SPs for the three app regs | Raw |
| `azuread_application_federated_identity_credential` | OIDC trust GitHub → Azure | Raw — two creds per CONTEXT.md D-08 |
| `azurerm_role_assignment` | RG-scoped Contributor for GHA SP; Key Vault Secrets User for ACA system MI | Raw — three role assignments minimum |
| `azurerm_monitor_diagnostic_setting` | Forward ACA `ContainerAppConsoleLogs_CL` to LAW | Raw — single category enabled (D-16) |
| `azurerm_consumption_budget_subscription` | €10/mo budget + 4-threshold alert | Raw — `notification` block per threshold (D-18) [CITED: registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/consumption_budget_subscription] |
| `random_password` | 32-char alphanumeric Postgres admin pwd | Raw — feeds an `azurerm_key_vault_secret` |
| `azurerm_key_vault_secret` | Five secrets per CONTEXT.md D-13 | Raw — even when KV itself comes from AVM, secrets are added with the raw resource |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AVM Key Vault module | `azurerm_key_vault` directly | Saves ~50 lines of AVM input plumbing, loses the AVM "best practice baseline" portfolio talking point. CONTEXT.md D-03 locked AVM. |
| AVM Postgres module | `azurerm_postgresql_flexible_server` directly | Same trade. AVM bundles `databases` map which exactly matches D-12 sequencing. |
| Workspace Terraform model | (already rejected per D-01) | PITFALLS §14: workspaces hide drift; envs/dirs is the spec. |
| `cyrilgdn/postgresql` provider for `CREATE EXTENSION` | `cyrilgdn/postgresql` | Splits schema authority between TF and Alembic; needs GHA runner IP firewall punch-through. Already rejected by D-12. |
| ACR Basic for image hosting | ACR Basic (~€4-5/mo) | Loses GHCR's free egress to Azure ~€60/yr. Already rejected by DEPL-07 + STACK.md §2. |
| Confidential client (TOKEN secret) for the SPA | (rejected — public client + PKCE only) | PITFALLS §2 — would silently break refresh. |
| Workload Profiles + NAT Gateway for static outbound IP | Workload Profiles env type + `azurerm_nat_gateway` | ~€30+/mo + breaks €0 budget; only consider if D-10 firewall-by-IP becomes mandatory. See §Common Pitfalls. |

**Installation (no Python deps; Terraform-only Phase):**

```bash
# Install Terraform 1.9+ (one-time, machine-local)
brew install terraform   # or: choco install terraform / tfenv install latest

# No npm/uv changes — Phase 3 is pure infra. Phase 4 picks up frontend deps.
```

**Version verification (run before locking plan):**

```bash
# Verify the AVM module versions in this RESEARCH.md are still current
gh api repos/Azure/terraform-azurerm-avm-res-keyvault-vault/releases/latest --jq '.tag_name'
gh api repos/Azure/terraform-azurerm-avm-res-operationalinsights-workspace/releases/latest --jq '.tag_name'
gh api repos/Azure/terraform-azurerm-avm-res-dbforpostgresql-flexibleserver/releases/latest --jq '.tag_name'

# Verify azurerm provider latest minor
gh api repos/hashicorp/terraform-provider-azurerm/releases/latest --jq '.tag_name'
```

If any AVM module has shipped a major version bump (e.g., 0.x → 1.0) since this research, re-read its `examples/` tree before locking — AVM modules under 1.0 are pre-stable and breaking changes between minors are not unheard of.

---

## Architecture Patterns

### System Architecture Diagram

```
                             [ Adrian's browser ]
                                     │
                                     │  HTTPS
                                     ▼
                       [ Static Web App (Free SKU) ]──────────┐
                       │  - Vite/React build (apps/web/dist)  │
                       │  - default_host_name = jobrag-...    │
                       │    azurestaticapps.net                │
                       │  - SWA deployment token (only        │
                       │    long-lived secret in repo)         │
                       └───────────────────────────────────────┘
                                     │
                                     │  fetch() with Bearer JWT
                                     │  (CORS preflight first)
                                     ▼
       ┌─────────────────────────────────────────────────────────────┐
       │ Azure Container Apps environment (Consumption)              │
       │ ─ jobrag-prod-aca-env ──────────────────────────────────────│
       │                                                              │
       │   [ Container App: jobrag-prod-api ]                         │
       │   ─ image: ghcr.io/<owner>/job-rag:<sha> ────────────────────│
       │   ─ ingress: external HTTPS, target_port=8000 ───────────────│
       │   ─ system-assigned MANAGED IDENTITY ────────────────────────│
       │   ─ template:                                                │
       │       min_replicas=0, max_replicas=1                          │
       │       termination_grace_period_seconds=120 (D-15)             │
       │       env vars from `secret_name` references:                 │
       │           - OPENAI_API_KEY → openai-api-key                   │
       │           - DATABASE_URL  (built from KV password + host)     │
       │           - LANGFUSE_PUBLIC_KEY / SECRET_KEY                  │
       │           - SEEDED_USER_ENTRA_OID (placeholder, Phase 4)      │
       │           - ALLOWED_ORIGINS (literal — second apply)          │
       │   ─ ConsoleLogs_CL → diagnostic_setting → LAW workspace       │
       └─────────────────────────────────────────────────────────────┘
              │                                    │
              │  KV reference resolution           │  asyncpg over TLS
              │  via system MI                     │  (require_secure_transport=on)
              ▼                                    ▼
       ┌──────────────────┐               ┌─────────────────────────────┐
       │ Key Vault (RBAC) │               │ Postgres Flex B1ms          │
       │ jobrag-prod-kv   │               │ jobrag-prod-pg              │
       │  ─ openai-api-key│               │  ─ azure.extensions=VECTOR   │
       │  ─ pg-admin-pwd  │               │  ─ public_network_access=on  │
       │  ─ langfuse-pub  │               │  ─ require_secure_transport  │
       │  ─ langfuse-sec  │               │  ─ DB: jobrag (TF-created)   │
       │  ─ seeded-oid    │               │  ─ firewall: home IP +       │
       │  RBAC roles:     │               │    (?ACA outbound IP)        │
       │   ACA system MI: │               │  ─ pool: pool_size=3,        │
       │   "KV Secrets    │               │    max_overflow=2 (Ph1)      │
       │     User"        │               └─────────────────────────────┘
       └──────────────────┘                              ▲
                                                          │ CREATE EXTENSION vector
                                                          │ (Alembic 0001 at startup)
                                                          │
       ┌─────────────────────────────────────────────────────────────┐
       │ Log Analytics workspace (jobrag-prod-law)                    │
       │ ─ daily_quota_gb = 0.15 (D-16) ──────────────────────────────│
       │ ─ retention_in_days = 30 (default) ──────────────────────────│
       │ ─ ContainerAppConsoleLogs_CL only (skip SystemLogs) ─────────│
       └─────────────────────────────────────────────────────────────┘

       ┌─────────────────────────────────────────────────────────────┐
       │ Subscription budget (€10/mo)                                 │
       │ Notifications at 50/75/90/100% → Adrian's email              │
       └─────────────────────────────────────────────────────────────┘

       ─── Identity plane (Entra External tenant) ───────────────────────────
                            ┌──────────────────────────┐
                            │ Entra External tenant    │
                            │ jobrag.ciamlogin.com     │
                            │ (manually bootstrapped,  │
                            │  terraform import)       │
                            ├──────────────────────────┤
                            │ App reg #1: SPA          │
                            │   single_page_application│
                            │     redirect_uris = [    │
                            │       <swa_default>,     │
                            │       http://localhost:  │
                            │         5173/            │
                            │     ]                    │
                            │   delegated permissions: │
                            │     access_as_user       │
                            │ App reg #2: API          │
                            │   identifier_uri =       │
                            │     api://<api-id>       │
                            │   exposed scope:         │
                            │     access_as_user       │
                            │ App reg #3: GitHub       │
                            │   federated creds:       │
                            │     repo:.../master      │
                            │     repo:.../env:prod    │
                            └──────────────────────────┘
                                     │
                                     │ OIDC (api://AzureADTokenExchange)
                                     ▼
                            ┌──────────────────────────┐
                            │ GitHub Actions runners   │
                            │  - deploy-infra.yml      │
                            │     (env:prod approval)  │
                            │  - deploy-api.yml        │
                            │     (push:master, paths) │
                            │  - deploy-spa.yml        │
                            │     (push:master, paths) │
                            └──────────────────────────┘
                                     │
                                     │ az/terraform CLI w/ short-lived token
                                     ▼
                            (Azure subscription, RG-scoped Contributor)
```

### Recommended Project Structure

```
infra/
├── bootstrap/                       # one-time, LOCAL state, .gitignored *.tfstate
│   ├── main.tf                      # storage_account + container for state, RG
│   ├── identity.tf                  # `terraform import` target for the External tenant
│   ├── outputs.tf                   # storage_account_name, container_name, rg_name, tenant_id
│   ├── README.md                    # portal click-path runbook for tenant creation (D-05)
│   └── terraform.tfstate            # gitignored
├── modules/
│   ├── network/                     # ACA env + (deferred) any future VNet integration
│   │   ├── main.tf                  # azurerm_container_app_environment
│   │   ├── variables.tf
│   │   ├── outputs.tf               # env_id, env_static_ip
│   │   └── README.md                # AVM-skipped rationale (D-03)
│   ├── database/
│   │   ├── main.tf                  # AVM postgres-flexible-server invocation
│   │   ├── variables.tf
│   │   ├── outputs.tf               # fqdn, db_name, admin_pwd_secret_id
│   │   └── README.md                # AVM-used rationale (D-03)
│   ├── compute/
│   │   ├── main.tf                  # azurerm_container_app + secret refs + env
│   │   ├── variables.tf
│   │   ├── outputs.tf               # aca_fqdn, aca_principal_id
│   │   └── README.md                # AVM-skipped (D-03)
│   ├── identity/
│   │   ├── main.tf                  # azuread_application × 3, federated creds, role_assignment
│   │   ├── variables.tf
│   │   ├── outputs.tf               # spa_client_id, api_client_id, gha_client_id, tenant_subdomain
│   │   └── README.md                # AVM-skipped, no azuread coverage
│   ├── monitoring/
│   │   ├── main.tf                  # AVM LAW + diagnostic_setting + budget
│   │   ├── variables.tf
│   │   ├── outputs.tf               # workspace_id
│   │   └── README.md                # AVM-used for LAW; budget is raw
│   └── kv/
│       ├── main.tf                  # AVM KV + 5 secrets + role_assignment for ACA MI
│       ├── variables.tf
│       ├── outputs.tf               # kv_id, kv_uri, secret URIs
│       └── README.md                # AVM-used (D-03)
├── envs/
│   ├── dev/                         # SCAFFOLD ONLY — never `terraform apply`d in v1 (D-04)
│   │   ├── backend.tf               # backend "azurerm" with key=dev.tfstate
│   │   ├── provider.tf
│   │   ├── main.tf                  # module calls only; no resources direct
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── dev.tfvars
│   │   └── README.md                # "Apply path is documented but not executed in v1"
│   └── prod/
│       ├── backend.tf               # backend "azurerm" with key=prod.tfstate
│       ├── provider.tf              # azurerm + azuread + random pinned per Discretion
│       ├── main.tf                  # module calls
│       ├── variables.tf
│       ├── outputs.tf               # the Phase 4 hand-off outputs (D-09)
│       ├── prod.tfvars              # var.home_ip + tenant_id literal from bootstrap
│       └── README.md                # two-pass apply runbook (DEPL-12)
└── README.md                        # top-level: bootstrap → prod-apply-pass-1 → swa-origin → prod-apply-pass-2

scripts/
└── refresh-swa-origin.sh            # one-shot DEPL-12 helper
                                       # reads `terraform output -raw swa_default_origin`
                                       # rewrites prod.tfvars var.swa_origin
                                       # re-runs terraform apply

.github/workflows/
├── ci.yml                           # UNCHANGED (Phase 1 owns this)
├── deploy-infra.yml                 # NEW: env:production gate; OIDC; terraform apply
├── deploy-api.yml                   # NEW: paths: src/**; OIDC; build+push GHCR; az containerapp update
└── deploy-spa.yml                   # NEW: paths: apps/web/**; SWA deploy via api_key
```

### Pattern 1: Bootstrap split (state chicken-and-egg)

**What:** A dedicated `infra/bootstrap/` directory creates the storage account that hosts state for `infra/envs/{dev,prod}/`. Bootstrap runs with LOCAL state, .gitignored. Outputs are copied into `backend.tf` literals.
**When to use:** Always, for any TF setup with remote state in the same cloud being provisioned.
**Source:** PITFALLS §13; `learn.microsoft.com/en-us/azure/developer/terraform/store-state-in-azure-storage`.

```hcl
# infra/bootstrap/main.tf — runs ONCE per machine, LOCAL state
terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.69" }
  }
  # NO backend block — uses local state on purpose
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "tfstate" {
  name     = "jobrag-tfstate-rg"
  location = "westeurope"
  tags     = { project = "job-rag", managed_by = "terraform-bootstrap" }
}

resource "azurerm_storage_account" "tfstate" {
  name                     = "jobragtfstate${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  blob_properties {
    versioning_enabled       = true
    delete_retention_policy { days = 7 }   # 7d soft delete (recovery from corrupted state)
  }
  tags = { project = "job-rag", managed_by = "terraform-bootstrap" }
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}

resource "random_string" "suffix" { length = 5; upper = false; special = false }

output "storage_account_name" { value = azurerm_storage_account.tfstate.name }
output "container_name"       { value = azurerm_storage_container.tfstate.name }
output "resource_group_name"  { value = azurerm_resource_group.tfstate.name }
```

After running:

```bash
cd infra/bootstrap && terraform init && terraform apply
# Capture the three outputs and paste them as literals into infra/envs/{dev,prod}/backend.tf
```

### Pattern 2: envs/dirs over workspaces (D-01 spec)

**What:** Each environment is a sibling directory with its own `backend.tf`, tfvars, and a flat `module {}` call to the shared modules. `terraform.workspace` is unused.
**When to use:** Whenever environments will drift on SKU, tier, or auth model — e.g., dev never applied (D-04) means dev tfvars must be free to point at `_NotApplicable_` placeholder values without breaking prod plan.
**Source:** PITFALLS §14; CONTEXT.md D-01.

```hcl
# infra/envs/prod/backend.tf — note: literal values copied from bootstrap output
terraform {
  required_version = ">= 1.9"
  backend "azurerm" {
    resource_group_name  = "jobrag-tfstate-rg"
    storage_account_name = "jobragtfstateXYZAB"   # from bootstrap output
    container_name       = "tfstate"
    key                  = "prod.tfstate"          # different from dev.tfstate
    use_azuread_auth     = true                     # blob auth via the apply-time identity, no SAS
  }
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.69" }
    azuread = { source = "hashicorp/azuread", version = "~> 3.0" }
    random  = { source = "hashicorp/random",  version = "~> 3.6" }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false   # respect purge_protection
    }
  }
}

provider "azuread" {
  tenant_id = var.tenant_id_external   # the External tenant — NOT workforce
}
```

### Pattern 3: Selective AVM adoption (D-03 spec)

**What:** AVM modules used for KV / LAW / Postgres; raw `azurerm` for ACA / SWA; raw `azuread` for app regs. Each module README.md documents the choice.
**When to use:** "Best of both" — AVM modules carry the best-practice baseline (RBAC defaults, soft-delete, network ACL hooks) but the v1 ACA module is still pre-stable and SWA is one resource (no abstraction value).
**Source:** CONTEXT.md D-03; AVM module versions verified live.

```hcl
# infra/modules/kv/main.tf — AVM consumed
module "key_vault" {
  source  = "Azure/avm-res-keyvault-vault/azurerm"
  version = "0.10.2"

  name                = "jobrag-${var.env}-kv"
  location            = var.location
  resource_group_name = var.resource_group_name
  tenant_id           = var.tenant_id

  sku_name                       = "standard"
  legacy_access_policies_enabled = false   # RBAC only (D-13)
  purge_protection_enabled       = var.env == "prod" ? true : false   # D-13 + Discretion
  soft_delete_retention_days     = 7
  public_network_access_enabled  = true   # ACA can't reach private endpoints on Consumption

  role_assignments = {
    aca_system_mi = {
      role_definition_id_or_name = "Key Vault Secrets User"
      principal_id               = var.aca_principal_id
    }
  }

  tags = var.tags
}
```

### Pattern 4: Container App secret reference (D-13 spec)

**What:** Secrets injected as `key_vault_secret_id` URI references; Container App's system MI resolves them at start. The literal value never enters Terraform state.
**When to use:** Every secret. Never use `data "azurerm_key_vault_secret"` and then pipe into env vars — that flows the value through TF state.
**Source:** Microsoft Learn "Manage secrets in Azure Container Apps"; HashiCorp Help Center troubleshooting article.

```hcl
# infra/modules/compute/main.tf — system-assigned MI + KV secret refs
resource "azurerm_container_app" "api" {
  name                         = "jobrag-${var.env}-api"
  container_app_environment_id = var.aca_env_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"   # blue-green via traffic-split-on-deploy

  identity {
    type = "SystemAssigned"   # system-assigned: simpler ownership; D-13
  }

  registry {
    server   = "ghcr.io"
    username = var.ghcr_username                   # github username
    password_secret_name = "ghcr-pat"              # PAT stored in app secret (read-only on package)
  }

  secret {
    name = "ghcr-pat"
    value = var.ghcr_pat   # one literal exception (read-only fine-grained PAT)
  }

  # ── KV-backed secrets ─ system MI must have "Key Vault Secrets User" on the vault ────────
  secret {
    name                = "openai-api-key"
    identity            = "System"          # the literal string "System" for system-assigned
    key_vault_secret_id = var.kv_secret_uris["openai-api-key"]
  }
  secret {
    name                = "postgres-admin-password"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["postgres-admin-password"]
  }
  secret {
    name                = "langfuse-public-key"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["langfuse-public-key"]
  }
  secret {
    name                = "langfuse-secret-key"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["langfuse-secret-key"]
  }
  secret {
    name                = "seeded-user-entra-oid"
    identity            = "System"
    key_vault_secret_id = var.kv_secret_uris["seeded-user-entra-oid"]
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"
    allow_insecure_connections = false   # HTTPS-only
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas                       = 0     # scale-to-zero (DEPL-03)
    max_replicas                       = 1     # single-user
    termination_grace_period_seconds   = 120   # D-15 / Phase 1 D-17 belt-and-suspenders

    container {
      name   = "api"
      image  = "ghcr.io/${var.ghcr_username}/job-rag:${var.image_tag}"
      cpu    = 0.5    # 0.25/0.5/0.75/1.0 vCPU steps in consumption
      memory = "1Gi"

      # ── Secrets routed to env vars by name reference ────────────────────────────────
      env { name = "OPENAI_API_KEY"          ; secret_name = "openai-api-key" }
      env { name = "LANGFUSE_PUBLIC_KEY"     ; secret_name = "langfuse-public-key" }
      env { name = "LANGFUSE_SECRET_KEY"     ; secret_name = "langfuse-secret-key" }
      env { name = "SEEDED_USER_ENTRA_OID"   ; secret_name = "seeded-user-entra-oid" }   # placeholder D-09

      # ── Composed/literal env (DATABASE_URL is built from KV pwd + literal host) ────
      env { name = "POSTGRES_ADMIN_PASSWORD" ; secret_name = "postgres-admin-password" }   # raw value for URL composition at startup
      env { name = "POSTGRES_HOST"           ; value = var.postgres_fqdn }                  # literal — not secret
      env { name = "POSTGRES_DB"             ; value = "jobrag" }
      env { name = "POSTGRES_USER"           ; value = var.postgres_admin_login }
      env { name = "ALLOWED_ORIGINS"         ; value = var.allowed_origins }                # literal — second-apply injects var.swa_origin (DEPL-12)
      env { name = "JOB_RAG_API_KEY"         ; value = "" }                                 # disabled in prod (Entra JWT replaces it Phase 4)

      # docker-entrypoint.sh composes DATABASE_URL/ASYNC_DATABASE_URL inline:
      #   export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_ADMIN_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
    }
  }

  tags = var.tags
}
```

> Naming nit: in `azurerm` v4 the secret block uses `name` + `value` OR `name` + `identity` + `key_vault_secret_id`. Mixing will produce confusing diffs. Pick one shape per secret.

### Pattern 5: Two-pass CORS bootstrap (DEPL-12 spec)

**What:** First `terraform apply` creates the SWA → `terraform output -raw swa_default_origin` returns it. A helper script writes it into `prod.tfvars` as `swa_origin`, then re-applies. Container App's `ALLOWED_ORIGINS` env var now contains the real origin.
**When to use:** Whenever the SWA hostname is needed inside the same TF graph that creates the SWA. Cleaner than `null_resource` + `local-exec` because it stays observable.
**Source:** CONTEXT.md D-14 + DEPL-12; Microsoft sample patterns.

```bash
# scripts/refresh-swa-origin.sh — DEPL-12 second-apply helper
# One-shot infra glue (per CONTEXT.md specifics §4 and the user's reusable-tools memory:
# kept as a standalone script, NOT folded into the main `job-rag` CLI; reuse expected near-zero).
set -euo pipefail
cd "$(dirname "$0")/../infra/envs/prod"

# Read SWA default host name from terraform state (must come from a TF output)
SWA_ORIGIN="https://$(terraform output -raw swa_default_origin)"

# Re-write prod.tfvars in place — sed pattern asserts exactly one prior line
if grep -q '^swa_origin' prod.tfvars; then
  sed -i.bak "s|^swa_origin.*|swa_origin = \"$SWA_ORIGIN\"|" prod.tfvars
else
  echo "swa_origin = \"$SWA_ORIGIN\"" >> prod.tfvars
fi

terraform apply -var-file=prod.tfvars -auto-approve
```

`infra/envs/prod/main.tf` plumbs `var.swa_origin` into the compute module's `var.allowed_origins`:

```hcl
locals {
  allowed_origins_csv = join(",", compact([var.swa_origin, "http://localhost:5173"]))
}

module "compute" {
  source              = "../../modules/compute"
  env                 = "prod"
  allowed_origins     = local.allowed_origins_csv   # consumed by FastAPI CORSMiddleware (Phase 1 D-26)
  # ...
}
```

> The CORSMiddleware in `src/job_rag/api/app.py` already accepts a CSV via `Settings.allowed_origins` (Plan 01-01 NoDecode pattern). Phase 3 only sets the env var.

### Anti-Patterns to Avoid

- **Mixing AVM and raw resources for the SAME concern.** Pick one per concern (D-03 already does this). Don't, e.g., use AVM Postgres for the server but raw `azurerm_postgresql_flexible_server_database` for the DB if the AVM's `databases` map covers it — picks one syntax per concern.
- **Putting secret values into `data "azurerm_key_vault_secret"`.** The value flows through TF state. Use `key_vault_secret_id` URI references in the Container App `secret` block instead.
- **One federated credential for both branch push and environment trigger.** The subjects differ; the credential matches one or the other, not both. PITFALLS §7 — D-08 mandates two creds.
- **Subscription-scoped Contributor for the GHA SP.** Blast radius == whole subscription. RG-scoped only.
- **Using `azurerm_container_app_environment.static_ip_address` as a Postgres firewall rule on Consumption tier.** Documented as not-guaranteed-static — see Pitfall section.
- **Adding `min_replicas = 1`** "to avoid cold start". Blows €0 by ~€15-20/mo. Phase 6 handles this with a UX state, per D-17.
- **Skipping the `purge_protection_enabled = true` on prod KV.** One-way switch — but that's the point: prevents accidental wipe. Dev scaffold can set false for easier teardown.
- **Adding `GZipMiddleware` to FastAPI** to "save bandwidth on SSE." Phase 1 already wired the anti-regression check. ACA's ingress doesn't gzip by default; nothing extra to do at the platform layer.
- **Auto-applying infra without environment approval.** D-08 + DEPL-09 require `environment: production` gate.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Storing `OPENAI_API_KEY` in `.env` files baked into the image | env-baked secret | Key Vault + ACA `key_vault_secret_id` reference | Anyone with image pull access reads the key; rotation is a rebuild. |
| Forwarding ACA logs to a custom HTTP endpoint | Self-built log shipper | `azurerm_monitor_diagnostic_setting` → LAW | Native diagnostic settings handle backpressure, identity, retention, and cost cap (DEPL-10). |
| OAuth/PKCE flow in custom JS | Hand-rolled token exchange | `@azure/msal-react` + `@azure/msal-browser` v5 | PKCE, token cache, refresh, iframe edge cases. PITFALLS §11/§12 enumerate why DIY breaks. |
| GitHub→Azure OIDC trust | Long-lived service principal secret rotation pipeline | `azuread_application_federated_identity_credential` | Short-lived per-job tokens; zero secret rotation; CONTEXT.md D-08. |
| Postgres password generation | Hardcoded "password123" | `random_password` resource | 32-char random, alphanumeric for URL safety (D-11). |
| Container image registry auth from ACA | ACA pulling with subscription-level creds | `registry { server, username, password_secret_name }` block | Pulls with a fine-grained PAT that can be rotated independently of TF state. |
| SWA → API CORS proxying | SWA linked-API feature | Direct CORS from Phase 1 CORSMiddleware | SWA proxy has ~30-45s timeout; kills SSE (D-14, PITFALLS §10). |
| Cost monitoring | Monthly portal-checking | `azurerm_consumption_budget_subscription` with multi-threshold notifications | Email at 50% catches problems while still cheap to fix (D-18). |
| pgvector extension creation | Custom SQL in TF `local-exec` | Alembic migration 0001 (already shipped Phase 1) | Per-database; CI smoke already runs `alembic upgrade head` against postgres service. |
| Resource naming consistency | Per-resource ad-hoc names | `infra/envs/{env}/locals.tf` building names from project + env + kind | Single source of truth; tag policy auto-applies. |
| Diagnostic category discovery | Hand-typed log category names | `data "azurerm_monitor_diagnostic_categories"` | The exact category set per resource type changes; data source is canonical. |

**Key insight:** The whole point of CONTEXT.md D-03's "selective AVM" call is *don't hand-roll the parts the cloud already gave you a reference module for.* AVM modules carry security-baseline defaults (RBAC, soft-delete, public-access toggles, network_acls scaffolding) that take 30-50 lines to replicate correctly. The two cases where hand-rolling wins are (1) ACA Container App because the AVM module is still pre-stable, and (2) SWA because the resource is one line and AVM adds zero value.

---

## Runtime State Inventory

> Phase 3 is partly greenfield (creating Azure resources for the first time) and partly migration-adjacent (Phase 1 already shipped Alembic migrations + dev DB stamped at 0003). Both lenses apply. The state inventory matters because Phase 4 consumes Phase 3 outputs and Phase 1's existing migrations must run cleanly against the TF-created DB.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| **Stored data** | None — Phase 3 creates a brand-new Postgres instance and database. The dev Docker-Compose Postgres has 108 postings ingested + 2121 requirements (Phase 1+2 work) but it stays local; nothing migrates from dev to prod in Phase 3. Phase 4+ will re-ingest into the new prod DB via the existing CLI. | None for Phase 3. Phase 8 may add a snapshot/seed step but it is out of scope here. |
| **Live service config** | None at start of Phase 3 (the Azure subscription is empty). After Phase 3 completes, future tweaks must remain TF-managed: any portal-edited resource will drift on next `apply`. | Document in `infra/envs/prod/README.md`: "ALL resource state lives in Terraform. If you edit in portal for one-off debugging, capture the change in TF before the next apply." |
| **OS-registered state** | None. Phase 3 is cloud-only; no local Windows Task Scheduler / launchd / systemd entries. | None. |
| **Secrets/env vars** | After Phase 3 completes, **5 secrets in KV** (D-13): `openai-api-key`, `postgres-admin-password`, `langfuse-public-key`, `langfuse-secret-key`, `seeded-user-entra-oid`. Plus **3 GitHub secrets** populated from bootstrap/prod outputs: `AZURE_CLIENT_ID` (GHA app reg), `AZURE_TENANT_ID` (External tenant id), `AZURE_SUBSCRIPTION_ID`, `AZURE_STATIC_WEB_APPS_API_TOKEN_PROD` (SWA api_key — sole long-lived secret per D-08). | Phase 4 reads `seeded-user-entra-oid` after first MSAL login (D-09 hand-off). All other secrets are produced and consumed by Phase 3 only. |
| **Build artifacts / installed packages** | Existing Docker image: docker-compose builds `app` from local Dockerfile. Phase 3 starts publishing the same Dockerfile to GHCR. **No stale local artifacts** because the dev story keeps using `docker-compose up` against the local image — prod is a separate code path. | Document in `.github/workflows/deploy-api.yml`: image tag pattern `ghcr.io/<owner>/job-rag:${{ github.sha }}` + `:latest`. ACA picks `:latest` on revision creation; sha tag stays for rollback. |

**Phase-3-internal state inventory addition:** the Phase 3 output bundle Phase 4 consumes is non-trivial — list verbatim in `infra/envs/prod/outputs.tf`:

```hcl
output "swa_default_origin"        { value = azurerm_static_web_app.spa.default_host_name }
output "aca_fqdn"                  { value = azurerm_container_app.api.latest_revision_fqdn }
output "kv_name"                   { value = module.key_vault.name }
output "kv_uri"                    { value = module.key_vault.uri }
output "tenant_subdomain"          { value = var.tenant_subdomain  /* literal, e.g. "jobrag" */ }
output "tenant_id"                 { value = var.tenant_id_external }
output "spa_app_client_id"         { value = azuread_application.spa.client_id }
output "api_app_client_id"         { value = azuread_application.api.client_id }
output "gha_app_client_id"         { value = azuread_application.github_actions.client_id   sensitive = false }
output "swa_deployment_token"      { value = azurerm_static_web_app.spa.api_key             sensitive = true  }
output "seeded_user_entra_oid_secret_name" { value = "seeded-user-entra-oid" }   # so Phase 4 knows where to write
```

Phase 4 ingests these via `terraform output -json > .planning/phases/04-frontend-shell-auth/tf-outputs.json` (gitignored) or via GH Actions secret export from `deploy-infra.yml`.

---

## Common Pitfalls

### Pitfall: ACA Consumption-tier outbound IP is NOT guaranteed static (NEW finding — verify with user)

**What goes wrong:** CONTEXT.md D-10 specifies firewalling Postgres Flex to "the static outbound IP exposed by `data \"azurerm_container_app_environment\"`." That data source's `static_ip_address` attribute exists, but Microsoft's official docs and a Microsoft-owned Q&A explicitly state that **on the Consumption-only environment tier, outbound IPs may change over time** — they are *not guaranteed* to be stable. Workload Profiles + NAT Gateway is the only documented way to guarantee a static outbound IP, and that costs ~€30+/mo.
**Why it happens:** Consumption-tier ACA runs on shared infrastructure where outbound traffic egresses through Azure-managed pools. The IP shows up in `static_ip_address` on the data source because there *is* an IP at any moment, but the underlying Microsoft service can rotate it during platform maintenance, scale events, or pool rebalancing.
**How to avoid:** Three options. Adrian must pick one before plan-locking.

| Path | What it does | Cost | Trade-off |
|------|--------------|------|-----------|
| **A: "Allow Azure services" + strong app-layer auth** (RECOMMENDED) | Set Postgres firewall to `0.0.0.0/0.0.0.0` (Microsoft-documented as "Allow public access from any Azure service"); rely on `require_secure_transport=on` (TLS) + 32-char random password + (optional) `connect_timeout` and `host` validation in asyncpg | €0/mo | Slightly wider firewall surface than D-10 intends — any Azure service in any subscription can attempt connection, but they need the password to actually reach the DB. The TLS + random password + Azure-only restriction is the same model used by Azure DB free-tier reference architectures. |
| **B: NAT Gateway + Workload Profiles** | ACA env upgraded to Workload Profiles tier; NAT Gateway with static public IP; firewall = NAT IP + home IP per D-10 intent | ~€30+/mo (NAT Gateway €15/mo + Workload Profiles consumption-vCPU rates) | Breaks €0 budget; defer to v2 paid tier. |
| **C: Take the documented risk** | Use `data.azurerm_container_app_environment.prod.static_ip_address` as a firewall rule despite the Microsoft warning; add a one-shot `scripts/firewall-update-aca-ip.sh` runbook for when the IP drifts | €0/mo | Will silently break with no warning when Microsoft rotates the IP; debugging time is unbounded. |

**Recommendation: Path A.** Reasoning: (1) The threat model for "Allow Azure services" is "another Azure customer brute-forces the random 32-char alphanumeric password over TLS." Computationally infeasible. (2) Microsoft's own free-tier sample architectures use this exact pattern. (3) Path C imposes silent-failure debugging cost on Adrian whose time-cost is the dominant scarce resource. (4) Path B violates the locked €0 budget constraint and would force a separate decision.

> **Plan-time action:** Add a lightweight discussion checkpoint at plan-locking time to confirm Path A; if confirmed, the locked CONTEXT.md D-10 wording becomes:
> "Public access + firewall: `0.0.0.0/0.0.0.0` 'Allow Azure services' rule + Adrian's home IP. TLS-only (`require_secure_transport=on`) + 32-char random password is the security boundary. Skip per-IP allowlist for ACA because Consumption-tier outbound IP is documented non-stable. Defer NAT Gateway to v2 paid tier."

**Warning signs:** `OperationalError: connection timed out` or `FATAL: no pg_hba.conf entry for host` from the ACA logs after a previously-working deploy, despite zero infra changes — the platform rotated the IP.

[VERIFIED via two sources: Microsoft Q&A "In a consumption only environment, is a Container App's outbound IP static?" (answer: no); GitHub microsoft/azure-container-apps issue #801 (Microsoft response: "Outbound IPs aren't guaranteed and may change over time")]

### Pitfall: AVM Postgres module's `server_configuration` example confused `shared_preload_libraries` with `azure.extensions`

**What goes wrong:** A WebFetch of the AVM Postgres module returned an example using `name = "shared_preload_libraries", config = "vector"`. That is **wrong** for Azure Database for PostgreSQL Flexible Server. Microsoft's allowlist mechanism is the `azure.extensions` server parameter, not `shared_preload_libraries` (which has different semantics — preloads at startup vs. allowlist for `CREATE EXTENSION`).
**Why it happens:** Both parameters look extension-related; on self-hosted Postgres `shared_preload_libraries` is the canonical "load me at startup" knob, but Azure Flexible Server uses `azure.extensions` as a separate allowlist that gates `CREATE EXTENSION`. pgvector does NOT need `shared_preload_libraries` at all.
**How to avoid:** Use `name = "azure.extensions"`, `value = "VECTOR"` (the value is case-insensitive but Microsoft docs use uppercase). For multiple extensions: comma-separated, e.g., `"VECTOR,PG_TRGM"`.
**Source:** Microsoft Learn `learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-allow-extensions` — explicit ARM template example showing `parameters('flexibleServers_name'), '/azure.extensions'`.

```hcl
# CORRECT — what to put in infra/modules/database/main.tf
module "postgres" {
  source  = "Azure/avm-res-dbforpostgresql-flexibleserver/azurerm"
  version = "0.2.2"
  # ...
  server_configuration = {
    extensions_allowlist = {
      name  = "azure.extensions"
      value = "VECTOR"
    }
  }
  databases = {
    jobrag = { name = "jobrag" }
  }
  # ...
}
```

The Alembic migration 0001 (already shipped Phase 1) runs `CREATE EXTENSION IF NOT EXISTS vector` against the `jobrag` database at container startup. The AVM module's `server_configuration` only allowlists; the migration creates.

### Pitfall: `azurerm_container_app_environment` and `azurerm_static_web_app` share a name across regions but Free SKU is multi-region

**What goes wrong:** Naming the SWA `jobrag-prod-spa` works in westeurope, but a future stage 2 SWA created in another region with the same name fails. Free SKU is automatically multi-region for serving; the *name* is per-subscription unique.
**How to avoid:** Use `jobrag-${env}-spa-${random_string.suffix}` if there is any chance of multi-region future, or just commit to one name + one region. CONTEXT.md Discretion locks `westeurope` so this is moot for v1, but document for v2.

### Pitfall: Federated credential subject substring matches but trigger differs

**What goes wrong:** `repo:adrianzaplata/job-rag:ref:refs/heads/master` looks identical to `repo:AdrianZaplata/job-rag:ref:refs/heads/master` but GitHub's claim is lowercase. Azure rejects with `AADSTS700213: subject claim case mismatch.`
**How to avoid:** Always use lowercase repo owner + name in the federated credential subject. PITFALLS §7 already covers this; reinforce in `infra/modules/identity/main.tf` with a `lower(var.github_repo)` defensive normalization.

### Pitfall: SWA `api_key` flows through Terraform state but is the only long-lived secret

**What goes wrong:** SWA does not yet support OIDC GA, so `azure/static-web-apps-deploy@v1` consumes the `api_key` (deployment token). The token is `sensitive = true` in TF state but can leak via `terraform output -raw swa_deployment_token` in CI logs if not handled carefully.
**How to avoid:** In `deploy-infra.yml`, capture the token directly into a GitHub Actions secret rather than letting it flow through stdout: `gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD --body "$(terraform output -raw swa_deployment_token)"` — `gh secret set` reads from stdin and never echoes. Document a 180-day rotation cadence in `infra/envs/prod/README.md` (Microsoft's documented default for SWA tokens; `learn.microsoft.com/en-us/azure/static-web-apps/deployment-token-management`).

### Pitfall: `legacy_access_policies_enabled = false` on a KV that already has policies

**What goes wrong:** AVM module's flag flips behavior atomically; flipping it on an existing KV with prior access policies removes those policies' effect (RBAC takes over). Not destructive but breaks any IAM that was relying on the policies.
**How to avoid:** Phase 3 creates the KV from scratch — set `legacy_access_policies_enabled = false` from the very first apply. Never flip it later.

### Pitfall: ACA `secret { value = ... }` block stores the literal in TF state

**What goes wrong:** The GHCR PAT pattern in Pattern 4 above uses `secret { name = "ghcr-pat", value = var.ghcr_pat }`. That literal lands in `prod.tfstate` (encrypted at rest in the blob, but visible to anyone who can read state).
**How to avoid:** Two options:
1. **Mark `var.ghcr_pat` as `sensitive = true`** so it doesn't echo in plan output; accept that state contains it. Acceptable for a fine-grained read-only PAT scoped to one package.
2. **Store the PAT in KV too** and use `key_vault_secret_id` for the registry secret — but then there's a chicken-and-egg: Container App needs to pull image to start, and pulling needs the registry secret, which needs MI to read KV, which needs Container App to be running. Path 1 is the conventional answer.

### Pitfall: Two-pass apply produces a "no changes" plan on second pass

**What goes wrong:** `scripts/refresh-swa-origin.sh` rewrites `prod.tfvars` to set `swa_origin = "https://jobrag-prod-spa-xxxxxxxx.azurestaticapps.net"`. If the SWA hostname is identical between passes (cached), the second `apply` reports "no changes" and the Container App's env var doesn't update.
**How to avoid:** Make the second-pass run `apply -replace=module.compute.azurerm_container_app.api` only if `terraform plan` reports zero changes. Or use a `null_resource` with `triggers = { swa_origin = var.swa_origin }` so a tfvars update always triggers a Container App revision. Pragmatic answer: the first apply leaves `var.swa_origin` empty → ALLOWED_ORIGINS = `"http://localhost:5173"`; second apply sets it → ALLOWED_ORIGINS = `"https://...,http://localhost:5173"`. Different value → revision swap → real change. Verified by reading the Pattern 5 logic above.

### Pitfall: Existing pitfalls (already covered in PITFALLS.md, repeat here only as planner reminders)

The following are already documented in `.planning/research/PITFALLS.md` and Phase 1 already mitigated them. Phase 3's job is to *not regress* them.

- §1 wrong tenant type → D-05 manually creates External tenant (not workforce / not B2C)
- §2 SPA registered as Web platform → D-07 uses `single_page_application` block
- §3 Envoy 240s SSE cap → D-15 grace period 120s ≤ 240s
- §4 scale-to-zero cold start → D-17 defers UX mitigation to Phase 6
- §5 SIGTERM mid-stream → D-15 + Phase 1 D-17 already shipped 30s app drain
- §7 OIDC subject mismatch → D-08 two explicit creds, no claims-matching
- §8 B1ms connection exhaustion → Phase 1 D-29 pool already shipped (`pool_size=3, max_overflow=2`)
- §9 pgvector per-database → D-12 sequencing (TF allowlists, Alembic creates extension)
- §10 SWA linked-API CORS confusion → D-14 direct CORS, never linked-API
- §13 TF bootstrap chicken-and-egg → D-02 dedicated `bootstrap/`
- §14 workspace confusion → D-01 envs/dirs over workspaces
- §17 free-tier cost surprises → D-16 (LAW 0.15 GB/day) + D-18 (€10/mo budget)

---

## Code Examples

Verified patterns from official sources, ready for the planner to convert into task-level code.

### Postgres Flex with VECTOR allowlist + jobrag database

```hcl
# infra/modules/database/main.tf
resource "random_password" "pg_admin" {
  length           = 32
  special          = false   # alphanumeric only — D-11 + Phase 1 STATE.md lessons (URL-encoding pain)
  upper            = true
  lower            = true
  numeric          = true
}

# Stash the password in KV BEFORE Postgres is created so the secret URI can
# be referenced by the Container App at deploy time. (Strict ordering matters.)
resource "azurerm_key_vault_secret" "pg_admin_password" {
  name         = "postgres-admin-password"
  value        = random_password.pg_admin.result
  key_vault_id = var.key_vault_id

  # Wait for the role assignment that lets the deployer write to KV
  depends_on = [var.kv_admin_role_assignment_id]
}

module "postgres" {
  source  = "Azure/avm-res-dbforpostgresql-flexibleserver/azurerm"
  version = "0.2.2"

  name                = "jobrag-${var.env}-pg"
  location            = var.location
  resource_group_name = var.resource_group_name

  sku_name           = "B_Standard_B1ms"
  storage_mb         = 32768   # 32 GB — free-tier max (Discretion)
  auto_grow_enabled  = true    # Discretion — fail-soft past 32 GB
  server_version     = "16"

  administrator_login    = var.pg_admin_login    # default "jobragadmin"
  administrator_password = random_password.pg_admin.result

  public_network_access_enabled = true   # D-10 — see Pitfall on outbound IP
  backup_retention_days         = 7      # Discretion — free-tier default

  high_availability = null   # B1ms doesn't support HA

  server_configuration = {
    extensions_allowlist = {
      name  = "azure.extensions"
      value = "VECTOR"   # case-insensitive; matches Microsoft docs convention
    }
  }

  databases = {
    jobrag = {
      name = "jobrag"   # D-12: TF creates the DB; Alembic creates the extension
    }
  }

  firewall_rules = merge(
    {
      home = {
        start_ip_address = var.home_ip
        end_ip_address   = var.home_ip
      }
    },
    # Conditional on Path A from outbound-IP pitfall:
    var.use_allow_azure_services ? {
      allow_azure_services = {
        start_ip_address = "0.0.0.0"
        end_ip_address   = "0.0.0.0"   # Microsoft's "Allow Azure services" idiom
      }
    } : {}
  )

  tags = var.tags
}
```

### Three GHA workflows (skeletons)

```yaml
# .github/workflows/deploy-infra.yml
name: Deploy infrastructure
on:
  push:
    branches: [master]
    paths:
      - 'infra/**'
      - '.github/workflows/deploy-infra.yml'
  workflow_dispatch:

permissions:
  id-token: write     # OIDC to Azure — required
  contents: read

jobs:
  apply:
    runs-on: ubuntu-latest
    environment: production    # protected env — Adrian as required reviewer
    defaults:
      run:
        working-directory: infra/envs/prod
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.9.5
      - uses: azure/login@v2
        with:
          client-id:       ${{ secrets.AZURE_CLIENT_ID }}        # GHA app reg client_id (D-08 cred #2)
          tenant-id:       ${{ secrets.AZURE_TENANT_ID }}        # External tenant id
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Terraform Init
        run: terraform init -input=false
      - name: Terraform Apply
        run: terraform apply -input=false -auto-approve -var-file=prod.tfvars
      - name: Capture outputs for downstream workflows
        run: |
          # SWA api_key is the only long-lived secret. Update on every apply
          # so that token rotation propagates to the deploy-spa workflow.
          echo "::add-mask::$(terraform output -raw swa_deployment_token)"
          gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD \
            --body "$(terraform output -raw swa_deployment_token)" \
            --repo ${{ github.repository }}
        env:
          GH_TOKEN: ${{ secrets.GH_PAT_FOR_SECRETS }}    # alternative: use OIDC and `gh auth login --with-token`
```

```yaml
# .github/workflows/deploy-api.yml
name: Deploy API
on:
  push:
    branches: [master]
    paths:
      - 'src/**'
      - 'pyproject.toml'
      - 'uv.lock'
      - 'Dockerfile'
      - 'alembic/**'
      - '.github/workflows/deploy-api.yml'

permissions:
  id-token: write
  contents: read
  packages: write     # GHCR push

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - uses: azure/login@v2
        with:
          client-id:       ${{ secrets.AZURE_CLIENT_ID }}        # D-08 cred #1: master-push subject
          tenant-id:       ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Update Container App image
        run: |
          az containerapp update \
            --name jobrag-prod-api \
            --resource-group jobrag-prod-rg \
            --image ghcr.io/${{ github.repository }}:${{ github.sha }}
```

```yaml
# .github/workflows/deploy-spa.yml
name: Deploy SPA
on:
  push:
    branches: [master]
    paths:
      - 'apps/web/**'
      - '.github/workflows/deploy-spa.yml'

permissions:
  id-token: write
  contents: read

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: apps/web/package-lock.json
      - run: npm ci
        working-directory: apps/web
      - run: npm run build
        working-directory: apps/web
      - uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN_PROD }}
          repo_token: ${{ secrets.GITHUB_TOKEN }}
          action: 'upload'
          app_location: 'apps/web/dist'
          skip_app_build: true
          skip_api_build: true
```

### azuread federated identity credentials (CONTEXT.md D-08)

```hcl
# infra/modules/identity/main.tf — three app registrations
resource "azuread_application" "spa" {
  display_name     = "jobrag-spa"
  sign_in_audience = "AzureADandPersonalMicrosoftAccount"   # adjust per External tenant config

  single_page_application {
    redirect_uris = [
      "${var.swa_origin}/",                # production SWA
      "http://localhost:5173/",            # local dev
    ]
  }

  required_resource_access {
    resource_app_id = azuread_application.api.client_id
    resource_access {
      id   = azuread_application.api.oauth2_permission_scope_ids["access_as_user"]
      type = "Scope"
    }
  }
}

resource "azuread_application" "api" {
  display_name     = "jobrag-api"
  identifier_uris  = ["api://jobrag-api"]   # set BEFORE setting client_id-based identifier; rewrite after first apply

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = "00000000-0000-0000-0000-000000000001"   # generate once, hardcode
      admin_consent_description  = "Allow the SPA to act on behalf of the signed-in user."
      admin_consent_display_name = "Access job-rag API as user"
      enabled                    = true
      type                       = "User"
      user_consent_description   = "Allow the SPA to access job-rag on your behalf."
      user_consent_display_name  = "Access job-rag API"
      value                      = "access_as_user"
    }
  }
}

resource "azuread_application" "github_actions" {
  display_name = "jobrag-gha"
}

resource "azuread_service_principal" "github_actions" {
  client_id = azuread_application.github_actions.client_id
}

resource "azuread_application_federated_identity_credential" "master" {
  application_id = azuread_application.github_actions.id
  display_name   = "gha-master-push"
  description    = "GHA OIDC for master push (deploy-api / deploy-spa)"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${lower(var.github_owner)}/${lower(var.github_repo)}:ref:refs/heads/master"   # case-sensitive lowercase
  audiences      = ["api://AzureADTokenExchange"]
}

resource "azuread_application_federated_identity_credential" "production_env" {
  application_id = azuread_application.github_actions.id
  display_name   = "gha-environment-production"
  description    = "GHA OIDC for environment:production (deploy-infra)"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${lower(var.github_owner)}/${lower(var.github_repo)}:environment:production"
  audiences      = ["api://AzureADTokenExchange"]
}

resource "azurerm_role_assignment" "gha_rg_contributor" {
  scope                = var.resource_group_id   # RG-scoped — never subscription
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}
```

### Static Web App + data source for two-pass apply

```hcl
# infra/envs/prod/main.tf — direct azurerm_static_web_app (raw, per D-03)
resource "azurerm_static_web_app" "spa" {
  name                = "jobrag-prod-spa"
  resource_group_name = azurerm_resource_group.prod.name
  location            = "westeurope"
  sku_tier            = "Free"
  sku_size            = "Free"

  tags = local.tags
}

# After first apply, refresh-swa-origin.sh reads this output:
output "swa_default_origin" { value = azurerm_static_web_app.spa.default_host_name }
output "swa_deployment_token" {
  value     = azurerm_static_web_app.spa.api_key
  sensitive = true
}
```

### Diagnostic setting + LAW (DEPL-10, D-16)

```hcl
# infra/modules/monitoring/main.tf
module "log_analytics" {
  source  = "Azure/avm-res-operationalinsights-workspace/azurerm"
  version = "0.5.1"

  name                = "jobrag-${var.env}-law"
  location            = var.location
  resource_group_name = var.resource_group_name

  log_analytics_workspace_sku            = "PerGB2018"
  log_analytics_workspace_retention_in_days = 30        # Discretion — default
  log_analytics_workspace_daily_quota_gb    = 0.15      # D-16 — ≈4.5 GB/mo, 90% of DEPL-10's 5GB alert
}

resource "azurerm_monitor_diagnostic_setting" "aca" {
  name                       = "jobrag-${var.env}-aca-diag"
  target_resource_id         = var.aca_id    # the Container App resource id
  log_analytics_workspace_id = module.log_analytics.resource_id

  enabled_log {
    category = "ContainerAppConsoleLogs_CL"   # D-16 — stdout / structlog JSON only
  }
  # Note: ContainerAppSystemLogs_CL is intentionally OMITTED (D-16)
}

resource "azurerm_consumption_budget_subscription" "prod" {
  name            = "jobrag-prod-budget"
  subscription_id = var.subscription_id
  amount          = 10               # €10/mo — DEPL-11 + D-18
  time_grain      = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
    end_date   = "2030-12-31T23:59:59Z"   # explicit far-future
  }

  dynamic "notification" {
    for_each = toset([50, 75, 90, 100])     # D-18 — multiple thresholds
    content {
      enabled         = true
      threshold       = notification.value
      operator        = "GreaterThan"
      threshold_type  = "Actual"
      contact_emails  = [var.budget_alert_email]   # adrianzaplata@gmail.com from tfvars
    }
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Azure AD B2C for customer auth | Entra External ID | B2C end-of-sale 2025-05-01; P2 retired 2026-03-15 | Phase 3 must use External tenant + `*.ciamlogin.com` authority; PITFALLS §1 |
| Long-lived service principal client secret | OIDC federated credential | GA on Microsoft side since 2022; mature on GitHub side | Zero long-lived secrets except SWA api_key; D-08 |
| Terraform workspaces for env separation | envs/dirs (separate `.tf` trees) | Industry shift toward avoiding workspaces; PITFALLS §14 | CONTEXT.md D-01 deviates from PROJECT.md original |
| KV access policies | KV RBAC | Microsoft deprecated access policies as default; AVM modules now default to RBAC | `legacy_access_policies_enabled = false`; D-13 |
| `actions/checkout@v3` | `actions/checkout@v4` | v4 GA late 2024; v3 deprecated 2024 | Use v4 in all three workflows |
| ACR for Azure-only image hosting | GHCR for free egress + cost saving | Pricing math; GHCR free-tier coverage of Azure pulls | DEPL-07; saves ~€60/yr |
| `single_page_application` not yet supported in terraform-provider-azuread | `single_page_application { redirect_uris = [...] }` | Added in azuread provider v2.x (2022) | D-07; PITFALLS §2 |
| Postgres extension via `shared_preload_libraries` | `azure.extensions` allowlist | Specific to Azure DB for PostgreSQL Flex | D-12; common confusion (see Pitfall) |

**Deprecated/outdated (do NOT use):**
- `azurerm_static_site` resource — superseded by `azurerm_static_web_app` (the resource was renamed; old name kept as alias but deprecation warnings emitted on plan)
- `actions/setup-uv@v3` and below — `astral-sh/setup-uv@v5` is current (consistent with Phase 1 CI)
- `azure/login@v1` — `@v2` is the canonical OIDC version
- `azurerm` provider 3.x — v3 is in maintenance; v4 has rewritten Container App schema
- `azurerm_postgresql_flexible_server_configuration` for `shared_preload_libraries` to add pgvector — wrong parameter for Azure (use `azure.extensions`)

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ (Python — Phase 1 carry-over for grep/lint guards); `terraform validate` + `terraform fmt -check` (TF — built-in); `ajv` / OpenAPI schema validation deferred (Phase 4) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` (existing); `terraform fmt` operates on `*.tf` files in `infra/` tree; no separate config file |
| Quick run command | `cd infra/envs/prod && terraform fmt -check -recursive ../.. && terraform validate` (offline; no Azure required) |
| Full suite command | `terraform plan -var-file=prod.tfvars` (requires Azure auth + valid backend; consumes a few seconds of `azurerm_*` describes but creates nothing) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPL-01 | TF state lives in Blob backend with locking | smoke | `cd infra/envs/prod && terraform init && terraform state list \| head -1` (succeeds = backend reachable) | ❌ Wave 0 |
| DEPL-02 | envs/dirs structure exists; `infra/modules/*` referenced | structure | `test -f infra/envs/prod/main.tf && test -f infra/modules/kv/main.tf && grep -q '../../modules/kv' infra/envs/prod/main.tf` | ❌ Wave 0 |
| DEPL-03 | ACA env + Container App with correct replica counts | TF schema validation | `terraform validate` confirms blocks; `terraform plan` shows `min_replicas=0, max_replicas=1, termination_grace_period_seconds=120` | ❌ Wave 0 |
| DEPL-04 | Postgres B1ms + VECTOR allowlisted + jobrag DB | unit (TF) + smoke (post-apply) | TF: `terraform plan` shows `azure.extensions = "VECTOR"`. Live: `psql ... -d jobrag -c "\dx"` shows vector after Alembic 0001 | ❌ Wave 0 |
| DEPL-05 | SWA Free SKU created | TF schema | `terraform plan` shows `sku_tier = "Free"` and `sku_size = "Free"` | ❌ Wave 0 |
| DEPL-06 | KV stores 5 secrets; ACA pulls via MI | unit (TF) + smoke (live) | TF: `azurerm_key_vault_secret.*` × 5 in plan. Live: `az containerapp show -n jobrag-prod-api ... --query 'properties.template.containers[0].env' \| jq` shows secret references resolve | ❌ Wave 0 |
| DEPL-07 | Container image in GHCR, pulled successfully | smoke (live) | `curl -I https://<aca-fqdn>/health` returns 200; check first line of `az containerapp logs show` for image pull success | ❌ Wave 0 |
| DEPL-08 | Three workflows with paths filters | structure | `test -f .github/workflows/deploy-{infra,api,spa}.yml && yq '.on.push.paths' < .github/workflows/deploy-api.yml \| grep src` | ❌ Wave 0 |
| DEPL-09 | OIDC fed creds wired; RG-scoped Contributor | TF schema + smoke | `terraform plan` shows two `azuread_application_federated_identity_credential` resources + `azurerm_role_assignment.scope == resource_group_id`. Live: `az role assignment list --assignee <gha-sp-id> --scope <subscription-id>` returns empty (proves NOT subscription-scoped) | ❌ Wave 0 |
| DEPL-10 | LAW captures ConsoleLogs only; daily quota set | TF schema + smoke | `terraform plan` shows `daily_quota_gb = 0.15`, `enabled_log` with `category = "ContainerAppConsoleLogs_CL"` only. Live: portal "Daily cap" non-default | ❌ Wave 0 |
| DEPL-11 | Budget €10/mo with multi-threshold notifications | TF schema | `terraform plan` shows `azurerm_consumption_budget_subscription.prod.amount = 10` and 4 notification blocks at 50/75/90/100 | ❌ Wave 0 |
| DEPL-12 | Two-pass deploy injects ALLOWED_ORIGINS | manual + smoke | First apply: `ALLOWED_ORIGINS=http://localhost:5173`; run `scripts/refresh-swa-origin.sh`; second apply: `ALLOWED_ORIGINS` includes SWA hostname. Live: `curl -H "Origin: https://evil.com" <aca-fqdn>/match` returns 403 (PITFALLS Looks-Done-But-Isn't checklist) | ❌ Wave 0 |
| Cross-cutting | JWT issuer claim — Phase 4 verification | smoke (Phase 4) | Phase 4 owns this; Phase 3 only ensures the App Registration is set up (no live JWT yet because no SPA running) | N/A — Phase 4 |
| Cross-cutting | SSE flow over public ACA URL | smoke (post-apply) | Hello-world image; `curl -N <aca-fqdn>/health` returns 200; full SSE flow validated in Phase 4 (no SPA yet) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `terraform fmt -check` + `terraform validate` (offline, ~5s)
- **Per wave merge:** `terraform plan -var-file=prod.tfvars` against Azure (live read; ~30s; creates nothing)
- **Phase gate:** Full `terraform apply` succeeded on a clean clone; the 13 LIVE smokes from the table above; the 14-item PITFALLS "Looks Done But Isn't" subset that applies to Phase 3 (JWT iss check deferred to Phase 4).

### Wave 0 Gaps

- [ ] `infra/envs/prod/{backend.tf,provider.tf,main.tf,variables.tf,outputs.tf,prod.tfvars,README.md}` — covers DEPL-01/02
- [ ] `infra/envs/dev/{*}` — same files, scaffold only (D-04)
- [ ] `infra/modules/{network,database,compute,identity,monitoring,kv}/{main.tf,variables.tf,outputs.tf,README.md}` — covers DEPL-03/04/05/06/10
- [ ] `infra/bootstrap/{main.tf,identity.tf,outputs.tf,README.md}` + `.gitignore` rule for its tfstate — covers DEPL-01
- [ ] `scripts/refresh-swa-origin.sh` — covers DEPL-12
- [ ] `.github/workflows/deploy-{infra,api,spa}.yml` — covers DEPL-08/09
- [ ] `tests/test_phase3_structure.py` — Python tests verifying TF tree shape, file existence, expected `module ""` calls, lowercase repo owner in fed-cred subjects (catches PITFALLS §7 regression). Lives in repo `tests/` so it runs in existing `pytest` invocation; uses `pathlib` only — no Azure SDK.
- [ ] `infra/.gitignore` — explicit `*.tfstate*`, `.terraform/`, `.terraform.lock.hcl` (or commit lock), `*.tfvars.local` (Adrian's home IP)
- [ ] Framework install: none — Terraform 1.9+ is a one-time machine install; no language-runtime addition.

### Phase 3 testing strategy

Phase 3 has a sharp asymmetry compared to Phase 1+2: most validation requires LIVE Azure resources because the static analyzer can't simulate Azure side-effects. Three honest test categories:

1. **Static (no Azure):** `terraform fmt -check`, `terraform validate`, `pytest tests/test_phase3_structure.py` (file existence, naming, fed-cred subject lowercasing, secret reference structure). Runs in CI on every PR; fast.
2. **Plan (read Azure):** `terraform plan -var-file=prod.tfvars` against the real subscription; reads existing resources; creates nothing. Runs locally + once in `deploy-infra.yml` before apply.
3. **Live (apply Azure):** the 13 smokes above + the PITFALLS-derived "Looks Done But Isn't" checklist subset. Runs once after first prod apply; documented in `infra/envs/prod/README.md` as a post-apply checklist.

CI does NOT run live Azure validation (cost + complexity). Live smokes run manually via `infra/envs/prod/README.md` runbook after each `deploy-infra.yml` run.

---

## Security Domain

### Applicable ASVS Categories

`security_enforcement` is enabled by default (no override in `.planning/config.json`). Phase 3 is platform-plane; Phase 4 will own most app-layer ASVS. The Phase-3-relevant categories:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture, Design, Threat Modeling | yes | This research's STRIDE table below; CONTEXT.md decisions are the threat-model output |
| V2 Authentication | yes (foundation) | Entra External tenant; SPA + API app regs (D-05/06/07); MSAL enforced in Phase 4 |
| V3 Session Management | partial (foundation) | Token lifetime defaults from Entra; refresh-token-with-PKCE via MSAL (Phase 4) |
| V4 Access Control | yes | RG-scoped Contributor for GHA SP; Key Vault RBAC; per-DB password (no shared admin); seeded user `oid` enforced app-side (Phase 4) |
| V5 Validation, Sanitization & Encoding | partial (Phase 1+2 owns) | FastAPI Pydantic input validation already shipped |
| V6 Cryptography | yes | TLS-only Postgres (`require_secure_transport=on`); HTTPS-only ACA ingress; managed-identity-issued tokens vs. long-lived secrets; KV soft-delete + purge-protection |
| V7 Error Handling & Logging | yes | structlog JSON to LAW (D-16); error frames sanitized in `/agent/stream` (Phase 1 already shipped); 30-day retention |
| V8 Data Protection | yes (foundation) | KV at-rest encryption (Azure default); TF state in Blob with versioning + soft-delete (D-02) |
| V9 Communication Security | yes | TLS 1.2+ enforced by default on every Azure managed service; Container Apps Envoy terminates TLS; Postgres requires TLS |
| V10 Malicious Code | partial | `pip-audit` already shipped CI (Phase 1); image scanning at GHCR is GitHub-default |
| V11 Business Logic | N/A Phase 3 | App-layer; Phase 4-7 |
| V12 Files and Resources | partial | Resume upload size limits (Phase 7); not Phase 3 |
| V13 API and Web Service | yes | CORS allowlist exact match (D-14); Bearer JWT enforced Phase 4 |
| V14 Configuration | yes | Terraform-only IaC; env-driven config (Phase 1); secrets in KV not env files; pin every provider version |

### Known Threat Patterns for Azure free-tier + Terraform + Entra External + GHA-OIDC

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| State storage compromise — attacker reads `prod.tfstate` and extracts secret values | I (Information disclosure) | (1) Storage account is private (`container_access_type = "private"`); (2) `use_azuread_auth = true` on backend block — apply-time identity reads state, no SAS; (3) Soft-delete + versioning so corrupted state can be rolled back; (4) Never put literal secret values in TF — use `key_vault_secret_id` references (Pattern 4). |
| GHA token exfiltration via rogue PR | E (Elevation), I | (1) NO PR-trigger federated credential (D-08); (2) Two creds, both subject-bound to `master` or `environment:production`; (3) `paths` filter on workflows so a PR touching docs can't trigger deploy. |
| Subject claim widening via claims-matching expression | E | D-08 explicitly skips claims-matching ("easy to widen accidentally"). Two explicit creds. |
| Credential leak through TF state | I | KV secret URIs (`key_vault_secret_id`) flow through state; their *values* don't. The single exception is the GHCR PAT, which is sensitive=true and scoped read-only to one package. |
| Postgres brute-force over public network | T, E | TLS-only (`require_secure_transport=on`); 32-char alphanumeric random password; firewall allowlist (home IP + Path A "Allow Azure services" with TLS+password as the actual security boundary, see Pitfall). |
| Subscription-wide blast radius if GHA SP compromised | E | RG-scoped Contributor (DEPL-09); never subscription. Even if PAT or OIDC token is leaked, attacker can only modify resources in `jobrag-prod-rg`. |
| Cost exhaustion via runaway workflow | DoS | (1) Budget alerts at 50/75/90/100% (D-18) email Adrian fast; (2) `min_replicas=0` makes runaway compute self-bound to scale-to-zero on idle; (3) LAW daily cap 0.15GB hard ceiling (D-16). |
| Long-lived deploy secret leak (SWA api_key) | I, E | (1) Documented as the *only* long-lived secret (D-08 + DEPL-09); (2) Captured into GH Actions secret via `gh secret set` with `add-mask` to avoid stdout leak; (3) Microsoft default 180-day rotation cadence documented in `infra/envs/prod/README.md`. |
| Image supply-chain (compromised base image) | T | GHCR is GitHub Container Registry; Microsoft and HashiCorp base images. Multi-stage build copies `.venv` only; Phase 1's CI already runs `pip-audit`. Phase 8 may add Trivy; out of scope for Phase 3. |
| ACA cold-start flooding (DoS via repeated wakes) | DoS | `max_replicas=1` caps; `min_replicas=0` gives rapid scale-to-zero on idle. Cost-side capped by budget alert. No CDN/WAF needed for single-user app. |
| Workforce vs External tenant confusion (PITFALLS §1) | various | D-05 hard-locks External tenant; `provider "azuread" { tenant_id = var.tenant_id_external }` makes the tenant explicit. JWT `iss` claim verification in Phase 4. |
| Identity-plane lateral movement (compromised SPA SP cross-uses API) | E | API app reg's `oauth2_permission_scope` is `User`-consent type; the `requested_access_token_version=2` produces v2 tokens with explicit `aud=api://<api-id>`; Phase 4 validates `aud` strictly. |

---

## Environment Availability

| Dependency | Required By | Available (likely) | Version | Fallback |
|------------|------------|--------------------|---------|----------|
| Terraform CLI | All TF work | Probably ✗ | — | Install via `choco install terraform` (Windows) or `brew install terraform` (macOS); Azure DevOps Cloud Shell as last resort |
| Azure CLI (`az`) | bootstrap login + GHA workflow `az containerapp update` | Probably ✗ on dev box | — | `winget install Microsoft.AzureCLI`; required for `az login` during bootstrap and for the deploy-api workflow's `az containerapp update` step |
| GitHub CLI (`gh`) | Setting GH Actions secrets from `deploy-infra.yml` post-apply | Possibly ✓ | — | `winget install GitHub.cli`; alternative: portal-set the secrets manually |
| Azure subscription with Owner | One-time bootstrap (creating the GHA app reg + RG-scoped role assignment) | ✓ (Adrian's personal subscription, per CONTEXT.md `<code_context>`) | — | None — required for first apply. After bootstrap, GHA SP has only Contributor on RG. |
| Active Microsoft Entra workforce tenant (Adrian's existing) | Logging into Azure CLI for bootstrap | ✓ | — | None — but bootstrap creates a SECOND tenant (External) for app users. Two tenants coexist. |
| `pgvector/pgvector:pg17` Docker image | Phase 1 CI smoke; not Phase 3 | ✓ (already in CI per `.github/workflows/ci.yml`) | pg17 | Phase 3 doesn't need this directly |
| Internet egress for image pull from GHCR | ACA at first revision deploy | ✓ (Azure-managed) | — | None |
| Domain/DNS | Custom domain on SWA — DEFERRED | N/A v1 | — | SWA's `*.azurestaticapps.net` default suffices for v1 |

**Missing dependencies with no fallback:** All three CLIs (Terraform, az, gh) need to be installed on Adrian's machine before bootstrap. Plan should have a pre-flight task verifying each `command -v terraform && terraform version` etc. and emitting install-command suggestions if missing.

**Missing dependencies with fallback:** None for Phase 3.

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md is autogenerated and reflects PROJECT.md / STACK.md / ARCHITECTURE.md / CONVENTIONS.md (none of which are Phase-3-specific beyond the constraints already captured). Phase 3 must respect:

- **Azure-only / Terraform-only.** No Bicep, no ARM, no AWS, no AKS. CONTEXT.md D-01..D-18 already encode this.
- **€0/mo target.** Every Phase 3 resource is free-tier or B1ms-free-12-months; budget alert at €10/mo is the safety net (D-18). Path B from the outbound-IP pitfall (NAT Gateway) violates this and is correctly deferred.
- **Single-user-but-multi-user-ready.** Phase 3's identity layer creates ONE External tenant for both dev + prod (D-06), which scales to 50k MAU on free tier — multi-user-ready by construction. The seeded `oid` slot (D-09) preserves the Phase 1 D-08/D-09 pattern.
- **Tech stack frozen.** Phase 3 adds NO Python deps. The Phase 1 backend stack (FastAPI, LangGraph, SQLAlchemy async) is already what gets containerized.
- **Educational frontend/backend separation.** Phase 3's direct CORS (D-14) preserves this — backend logic in FastAPI, never proxied through SWA-as-reverse-proxy.
- **Per CONVENTIONS.md:** structlog `get_logger(__name__)` for any operational scripts; uv as the Python package manager (already shipped); ruff `E,F,I,UP` rules for any Python tests in `tests/test_phase3_*`.
- **GSD workflow enforcement:** Phase 3 work happens via `/gsd-execute-phase`. Direct file edits outside GSD are forbidden.

---

## Assumptions Log

> All claims tagged `[ASSUMED]` in this research. The planner and discuss-phase use this section to identify decisions that need user confirmation before execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Path A (`0.0.0.0` Allow-Azure-services + TLS + 32-char password) is the right resolution to the ACA Consumption outbound-IP non-stability problem" | Common Pitfalls / Outbound-IP | Path B (NAT Gateway) costs €30+/mo and violates €0 budget; Path C will silently fail when Microsoft rotates the IP. Adrian should confirm Path A or override at plan-locking. |
| A2 | "GHCR PAT can stay as a literal `secret { value = ... }` block in TF state given fine-grained read-only scope" | Code Examples / Container App / registry block | If Adrian's threat model says no literal secrets in state at all, Path B is "PAT in KV with chicken-and-egg solved by either pre-creating the Container App without a registry block, then `terraform apply -target=...` to add it, or by using a managed identity for ACR pull (but we're using GHCR not ACR)." Path A simpler; minor footprint risk. |
| A3 | "Setting `legacy_access_policies_enabled = false` from first apply is acceptable; no pre-existing access policies need migration" | Common Pitfalls / KV legacy policies | Phase 3 creates a fresh KV; assumption is true by construction. Stays low-risk. |
| A4 | "180-day SWA token rotation cadence is Microsoft's documented default" | Pitfall / SWA api_key | If shorter, the runbook needs updating; cosmetic. Verified citation: Microsoft Learn "Reset deployment tokens." |
| A5 | "ACA `revision_mode = \"Single\"` is sufficient for blue-green via traffic-split-on-deploy" | Discretion (locked) | Single-replica + scale-to-zero means traffic-shifting is moot for v1; if Phase 6 ever wants real blue-green, revisit. Low-risk for v1. |
| A6 | "Adrian's home IP is dynamic; firewall rule needs occasional refresh runbook" | Discretion | If Adrian's ISP gives a static IP or he uses a fixed VPN egress, runbook is no-op. Low-risk; runbook adds value either way. |
| A7 | "GitHub Actions environment named `production` is supported on Adrian's GH plan (Pro / paid)" | DEPL-09 / D-08 | Public repos always have free protected environments; private repos need paid plan. The job-rag repo is presumed public per the portfolio framing — confirm. |

**If A7 is wrong** (job-rag is private + Adrian on free GH plan), `environment: production` won't gate; deploy-infra.yml runs auto. Mitigation: switch to `workflow_dispatch`-only with a manual review step inside the workflow itself (less ergonomic but works on free private). This affects D-08's second federated credential subject — `repo:.../environment:production` would never fire; replace with a `workflow_dispatch` subject pattern.

---

## Open Questions

1. **ACA Consumption outbound IP — Path A vs Path C?**
   - What we know: Microsoft says outbound IP is not guaranteed static on Consumption tier. Two cited sources confirm.
   - What's unclear: How frequently does it actually rotate in practice for a single ACA env? Some users observe years of stability; Microsoft's stance is "we make no promise."
   - Recommendation: Path A. Confirm with Adrian at plan-locking; if he wants Path C with an explicit risk-acceptance, document it as a CONTEXT.md update.

2. **Is the GitHub repo `adrianzaplata/job-rag` public or private?**
   - What we know: PROJECT.md framing is "portfolio artifact"; Adrian is in active job hunt. Public is the rational portfolio choice.
   - What's unclear: Confirm at plan-time whether the repo is currently public. Affects A7 (free protected environments).
   - Recommendation: Make public if not already (cost: zero; benefit: portfolio + free protected envs).

3. **Two-pass apply — TF-native or script-driven?**
   - What we know: D-14 + DEPL-12 require a second apply that injects SWA origin. Two patterns work: (a) `null_resource` with `triggers = { swa_origin = ... }` + an output that re-reads the SWA host name; (b) the script-driven `scripts/refresh-swa-origin.sh` shown above.
   - What's unclear: Which pattern is more debuggable? Script is more explicit; null_resource is more terraform-native.
   - Recommendation: Script-driven for v1 (matches CONTEXT.md specifics §4). Per the user's reusable-tools memory, the script stays in `scripts/` — genuinely one-shot infra glue, not a CLI subcommand.

4. **Where does the GHA App Registration live — workforce or External tenant?**
   - What we know: D-05 creates the External tenant for app-user identity. The GHA SP (used to deploy Azure resources) needs a tenant too.
   - What's unclear: Should the GHA SP live in the workforce tenant (Adrian's personal subscription's default directory) or the new External tenant?
   - Recommendation: Workforce tenant. Reasons: (1) GHA SP authenticates AGAINST the subscription, which is bound to Adrian's workforce tenant, not the new External one; (2) two tenants for two purposes — External for end-users, workforce for ops/CI — is the standard Microsoft topology; (3) CONTEXT.md `<code_context>` says "Adrian's Azure subscription — bootstrap requires Owner-level access" which means the subscription tenant is Adrian's workforce tenant. Open question worth confirming at plan-time.

5. **AVM Postgres module's `server_configuration` shape — verify exact key names**
   - What we know: AVM v0.2.2 docs show `server_configuration = { extensions_allowlist = { name = "azure.extensions", value = "VECTOR" } }` works (synthesized from the AVM repo's `examples/`).
   - What's unclear: The exact dictionary key shape (`extensions_allowlist` vs `azure_extensions` vs free-form key) — needs a `terraform-docs` read of the v0.2.2 module before planning.
   - Recommendation: Pre-plan task: `cd infra/modules/database && terraform-docs markdown table .` after writing the first draft to confirm the shape compiles. Trivial 1-task spike.

---

## Sources

### Primary (HIGH confidence)

- [Microsoft Learn — Allow extensions in Azure DB for PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-allow-extensions) — exact `azure.extensions` parameter behavior and ARM example
- [Microsoft Learn — Vector search on Azure DB for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector) — pgvector named "vector" in extension allowlist
- [Microsoft Learn — Reset deployment tokens (SWA)](https://learn.microsoft.com/en-us/azure/static-web-apps/deployment-token-management) — token rotation cadence
- [Microsoft Learn — Manage secrets in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets) — `key_vault_secret_id` reference shape
- [Microsoft Learn — Authenticate to Azure from GitHub Actions by OpenID Connect](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect) — GHA OIDC end-to-end
- [Microsoft Learn — Networking in Azure Container Apps environment](https://learn.microsoft.com/en-us/azure/container-apps/networking) — outbound IP non-guarantee on Consumption
- [Microsoft Q&A — In a consumption only environment, is a Container App's outbound IP static?](https://learn.microsoft.com/en-us/answers/questions/2138866/in-a-consumption-only-environment-is-a-container-a) — Microsoft staff answer: "not guaranteed to be static"
- [GitHub — microsoft/azure-container-apps issue #801 (outbound IP limitations)](https://github.com/microsoft/azure-container-apps/issues/801) — Microsoft confirmation: "may change over time"
- [Microsoft Learn — Create an External Tenant (portal)](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-create-external-tenant-portal) — D-05 portal click-path runbook source
- [Microsoft Learn — Entra External ID FAQ](https://learn.microsoft.com/en-us/entra/external-id/customers/faq-customers) — B2C deprecation, External ID positioning
- [Terraform Registry — `azurerm_container_app`](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_app) — Container App resource schema
- [Terraform Registry — `azurerm_static_web_app`](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/static_web_app) — SWA resource shape
- [Terraform Registry — `azurerm_postgresql_flexible_server`](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/postgresql_flexible_server) — server resource
- [Terraform Registry — `azurerm_postgresql_flexible_server_firewall_rule`](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/postgresql_flexible_server_firewall_rule) — firewall rule shape
- [Terraform Registry — `azurerm_consumption_budget_subscription`](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/consumption_budget_subscription) — budget + notifications
- [Terraform Registry — `azurerm_monitor_diagnostic_setting`](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/monitor_diagnostic_setting) — diagnostic categories
- [Terraform Registry — `azuread_application_federated_identity_credential`](https://registry.terraform.io/providers/hashicorp/azuread/latest/docs/resources/application_federated_identity_credential) — fed-cred subject pattern
- [GitHub — Azure/terraform-azurerm-avm-res-keyvault-vault](https://github.com/Azure/terraform-azurerm-avm-res-keyvault-vault) — AVM KV module v0.10.2 (Oct 14 2025)
- [GitHub — Azure/terraform-azurerm-avm-res-operationalinsights-workspace](https://github.com/Azure/terraform-azurerm-avm-res-operationalinsights-workspace) — AVM LAW module v0.5.1 (Dec 23 2025)
- [GitHub — Azure/terraform-azurerm-avm-res-dbforpostgresql-flexibleserver](https://github.com/Azure/terraform-azurerm-avm-res-dbforpostgresql-flexibleserver) — AVM Postgres module v0.2.2 (Apr 14 2026)
- [Terraform AzureRM Provider 4.0 — release blog](https://www.hashicorp.com/en/blog/terraform-azurerm-provider-4-0-adds-provider-defined-functions) — v4 line confirmation
- [Microsoft Learn — Firewall rules — Azure DB for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/security-firewall-rules) — `0.0.0.0` "Allow Azure services" semantics

### Secondary (MEDIUM confidence — verified against an HIGH source)

- [HashiCorp Help Center — Troubleshooting `azurerm` provider issue not able to fetch keyvault secret(s) while deploying container app](https://support.hashicorp.com/hc/en-us/articles/34643944045075-Troubleshooting-azurerm-provider-issue-not-able-to-fetch-keyvault-secret-s-while-deploying-container-app) — confirms `key_vault_secret_id` requires the right URI shape + role assignment
- [Damien Aicheh — Define secrets and environment variables in Azure Container Apps using Terraform](https://damienaicheh.github.io/terraform/azure/azure-container-apps/2023/05/09/azure-container-apps-use-secrets-terraform-en.html) — secret block syntax cross-reference
- [Wayne Goosen — Azure Federated Identity Guide](https://waynegoosen.com/post/azure-federated-identity-credentials-terraform-github-actions-guide/) — federated credential subject patterns
- [Tarun Bhatt — Azure Static Web App: Save Deployment Token to KeyVault](https://medium.com/devops-dudes/azure-static-web-app-save-management-token-to-keyvault-using-terraform-ccf1a344e38e) — `api_key` output shape
- [Mattias Engineer — Azure Federated Credentials for GitHub](https://mattias.engineer/blog/2024/azure-federated-credentials-github/) — flexible federated identity overview
- [Microsoft Q&A — `static_ip_address` set just one outboundAddress in container app](https://learn.microsoft.com/en-us/answers/questions/2125471/set-just-one-outboundadress-in-container-app) — additional confirmation of the outbound-IP non-guarantee on Consumption
- [Cloudoptimo — Busting Azure Free Tier Myths](https://www.cloudoptimo.com/blog/busting-azure-free-tier-myths-avoid-the-hidden-costs/) — context for D-18 budget tightness

### Tertiary (LOW confidence — flagged for live-verification at plan time)

- [oneuptime — How to Create Azure Static Web Apps in Terraform (Feb 2026)](https://oneuptime.com/blog/post/2026-02-23-how-to-create-azure-static-web-apps-in-terraform/view) — useful but not authoritative; cross-checked against registry docs
- [oneuptime — How to Implement Azure Budget Alerts (Feb 2026)](https://oneuptime.com/blog/post/2026-02-16-implement-azure-budget-alerts-cost-management-terraform/view) — cross-checked with registry docs

---

## Metadata

**Confidence breakdown:**
- Standard stack (provider + AVM versions): HIGH — verified live against GitHub releases April 2026
- Architecture (8-domain split, two-pass CORS, OIDC pattern): HIGH — directly maps to CONTEXT.md decisions + verified Microsoft samples
- Container App resource shape (secret/env/identity/registry blocks): HIGH — registry docs + 3 cross-references
- Postgres VECTOR allowlist mechanism: HIGH — Microsoft Learn primary source + AVM module example correction (the AVM example I initially fetched was misleading; corrected via primary Microsoft docs)
- ACA Consumption outbound-IP non-stability: HIGH (the warning) / MEDIUM (the resolution path A recommendation) — Microsoft confirms the warning; the resolution involves a security trade-off that warrants user confirmation
- GitHub Actions OIDC + federated credential subjects: HIGH — Microsoft + GitHub primary docs
- Pitfalls (new — outbound IP, AVM Postgres example): HIGH — multi-source cross-verification
- Common pitfalls (carry-over from PITFALLS.md): HIGH — already vetted in prior research
- Validation Architecture: MEDIUM — most validation is "live Azure smoke" which can't run in CI; documented as a runbook
- Security domain (ASVS mapping): MEDIUM — Phase 4-7 own most app-layer ASVS; Phase 3's coverage is foundation-level

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 days for stable Azure/Terraform surface; AVM module versions especially worth re-checking — pre-1.0 modules can move fast)
