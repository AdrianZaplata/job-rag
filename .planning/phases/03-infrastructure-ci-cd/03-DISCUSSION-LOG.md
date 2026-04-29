# Phase 3: Infrastructure & CI/CD - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 03-infrastructure-ci-cd
**Areas discussed:** TF layout & bootstrap, Entra External ID + OIDC, Postgres net + secrets, Integration & guardrails

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| TF layout & bootstrap | Repo structure, bootstrap chicken-and-egg, AVM use, dev env scope | ✓ |
| Entra External ID + OIDC | Tenant provisioning, federated credential design, app reg pattern, seeded oid propagation | ✓ |
| Postgres net + secrets | Network mode, admin auth, pgvector pathway, KV consumption | ✓ |
| Integration & guardrails | SPA↔API integration, grace period, LAW caps, pre-warm | ✓ |

**User selected:** all four areas (consistent with Phase 1 + Phase 2 pattern).

---

## TF layout & bootstrap

### Q1: Reconcile PROJECT.md "Terraform workspaces" vs REQUIREMENTS DEPL-02 "infra/envs/{dev,prod}+modules/*" — which structure for the repo?

| Option | Description | Selected |
|--------|-------------|----------|
| envs/ dirs + modules/ (Recommended) | infra/envs/{dev,prod} each call infra/modules/*; separate state files in same Azure Blob backend (different keys); aligns DEPL-02 verbatim; PITFALLS §14 favors dirs over workspaces; PROJECT.md "workspaces" gets a documented deviation | ✓ |
| Workspaces (PROJECT.md literal) | Single infra/ directory; `terraform workspace select dev|prod` switches state; honors PROJECT.md but contradicts DEPL-02; PITFALLS §14 flags real risks | |
| Hybrid: workspaces inside envs/ | envs/{dev,prod} dirs but each uses workspaces internally; over-engineered for single-user project | |

**User's choice:** envs/ dirs + modules/ (Recommended)
**Notes:** Documented deviation from PROJECT.md to be logged at phase close.

### Q2: How to handle the Terraform chicken-and-egg (PITFALLS §13 — state storage account + RG must exist before backend init)?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated bootstrap/ state (Recommended) | infra/bootstrap/ creates state-storage RG + storage account + container; LOCAL state, .gitignored; outputs copied into envs/{dev,prod}/backend.tf as static literals; runbook'd | ✓ |
| az CLI script + import | scripts/bootstrap-state.sh provisions state storage; main code uses azurerm backend; loses TF declarative trail | |
| State in envs/ + terraform import | envs/prod/state.tf manages own backing storage; mind-bending; PITFALLS §13 explicitly warns | |

**User's choice:** Dedicated bootstrap/ state (Recommended)
**Notes:** Bootstrap dir remains in repo for reproducibility; terraform.tfstate never committed.

### Q3: DEPL-02 says "Azure Verified Modules used where available" — how aggressively should we adopt AVM?

| Option | Description | Selected |
|--------|-------------|----------|
| Selective AVM (Recommended) | AVM for KV, LAW, Postgres Flex; raw azurerm for ACA (AVM still maturing) + SWA (no value) + azuread (no AVM); per-resource decision documented | ✓ |
| AVM for everything available | Maximum DEPL-02 alignment + portfolio talking point; risk of abstraction layer + lag behind azurerm | |
| Raw azurerm only | Maximum control; deviates from DEPL-02; loses AVM-best-practices talking point | |

**User's choice:** Selective AVM (Recommended)

### Q4: PROJECT.md says "dev scaffolded, prod primary" — should the dev environment actually be deployed in Phase 3, or stay as un-applied scaffolding?

| Option | Description | Selected |
|--------|-------------|----------|
| Scaffold-only, never apply in v1 (Recommended) | infra/envs/dev/ exists with full *.tf + dev.tfvars; `plan` works as sanity-check; `apply` documented-but-deferred; €0 cost preserved | ✓ |
| Apply dev alongside prod | Both fully provisioned; doubles cost surface; eats free-tier hours | |
| Dev is just "prod-but-named-differently" | Single env; saves ~30min; loses dev/prod separation portfolio signal; PROJECT.md rejects | |

**User's choice:** Scaffold-only, never apply in v1 (Recommended)

---

## Entra External ID + OIDC

### Q5: How is the External ID tenant itself provisioned? STATE.md open question — azuread ~> 3.x has no first-class tenant resource as of Apr 2026.

| Option | Description | Selected |
|--------|-------------|----------|
| Manual portal + import (Recommended) | Adrian creates tenant once via Entra admin center; bootstrap/ runs `terraform import`; subsequent app regs + federated creds are pure TF; runbook documented | ✓ |
| Try `azurerm_resource_group_template_deployment` | ARM-template-via-Terraform escape hatch; brittle to Microsoft API drift; violates "Terraform only" in spirit | |
| Skip TF for tenant entirely; portal-only | Tenant lives outside Terraform; equivalent in practice to import-then-manage but loses the import step | |

**User's choice:** Manual portal + import (Recommended)
**Notes:** Closes STATE.md open question; runbook in `infra/bootstrap/README.md`.

### Q6: One External tenant for both dev + prod, or separate tenants per env?

| Option | Description | Selected |
|--------|-------------|----------|
| Single tenant, multi-redirect (Recommended) | One External ID tenant; SPA app reg has multiple redirect URIs (prod SWA + localhost:5173); fits scaffold-only-dev | ✓ |
| Separate dev + prod tenants | Cleanest blast-radius isolation; doubles app-reg + federated-cred maintenance; over-engineered | |

**User's choice:** Single tenant, multi-redirect (Recommended)

### Q7: Federated credential design for the deploy workflows (PITFALLS §7)?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-trigger explicit creds (Recommended) | Two credentials: (1) repo:OWNER/REPO:ref:refs/heads/master for deploy-api/spa, (2) repo:OWNER/REPO:environment:production for deploy-infra; no PR-trigger cred; both RG-scoped Contributor | ✓ |
| Add PR plan credential | Third credential for PR-triggered terraform plan; broader trust surface; marginal for single-engineer | |
| Claims-matching expression | Single wildcard credential; PITFALLS §7 warns "easy to widen accidentally" | |

**User's choice:** Per-trigger explicit creds (Recommended)

### Q8: How does Adrian's real Entra `oid` reach the DB seed (replacing the Phase-1 placeholder SEEDED_USER_ID)?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase-4 migration consumes TF output (Recommended) | Phase 3 lays empty KV slot + ACA env wiring; Phase 4 fills it post-first-login + runs Phase-1 D-09 migration | ✓ |
| Hardcode oid in tfvars after first login | Adrian edits prod.tfvars after first login, re-applies; oid lives in git history (low risk) | |
| Skip in Phase 3 — entirely Phase-4 concern | Cleanest Phase-3 boundary; loses chance to land KV slot + env wiring while in TF land | |

**User's choice:** Phase-4 migration consumes TF output (Recommended)
**Notes:** Phase 3 D-09 lays placeholder secret + env wiring; Phase 4 carries fill + migration.

---

## Postgres net + secrets

### Q9: Postgres B1ms network model — how does the Container App reach the database?

| Option | Description | Selected |
|--------|-------------|----------|
| Public + firewall allowlist (Recommended) | public_network_access_enabled=true; firewall rules for ACA outbound IP + Adrian's home IP; SSL/TLS required; €0 cost | ✓ |
| Private endpoint + VNet on ACA | Zero public exposure; portfolio talking point; ~€130/mo BREAKS €0 budget | |
| Public + firewall + Microsoft services bypass | Blanket-allows ALL Azure tenants; defeats firewall purpose | |

**User's choice:** Public + firewall allowlist (Recommended)
**Notes:** Private endpoint deferred to v2 paid tier.

### Q10: Postgres admin authentication — random password in Key Vault, or Entra auth (passwordless)?

| Option | Description | Selected |
|--------|-------------|----------|
| Random password + KV (Recommended) | random_password (alphanumeric only — avoids URL-encoding pain from Phase 1 lessons); azurerm_key_vault_secret; Container App pulls via managed identity | ✓ |
| Entra auth on Postgres + managed identity | Passwordless; strongest portfolio signal; rewrites Phase 1 SQLAlchemy engine + breaks local Docker-Compose dev | |
| Hardcoded password in tfvars | Skip KV; loses managed-identity portfolio signal | |

**User's choice:** Random password + KV (Recommended)
**Notes:** Entra-auth-on-Postgres deferred to v2 platform-era.

### Q11: How does the `jobrag` database + pgvector extension get created in Azure (PITFALLS §9)?

| Option | Description | Selected |
|--------|-------------|----------|
| TF creates DB; Alembic creates extension (Recommended) | TF: azure.extensions=VECTOR + azurerm_postgresql_flexible_server_database; Alembic 0001 (Phase 1) creates extension on startup; honors Phase 1 D-03/D-04 | ✓ |
| TF creates DB + extension (cyrilgdn/postgresql) | Single TF source of truth; needs DB connection during apply; conflicts with Alembic | |
| Manual psql runbook | Loses idempotency; fails DEPL-04 SC fresh-clone smoke test | |

**User's choice:** TF creates DB; Alembic creates extension (Recommended)

### Q12: How does the Container App consume Key Vault secrets at runtime?

| Option | Description | Selected |
|--------|-------------|----------|
| Managed identity + KV references (Recommended) | System-assigned MI; RBAC via Key Vault Secrets User role; Container App secrets block uses key_vault_secret_id; zero literal secret values in TF state | ✓ |
| KV data source → ACA env literals | Secret values flow through TF state; no runtime rotation; anti-pattern | |
| Hybrid: literals for OPENAI/Langfuse, MI for DB | Edge value; unified model is simpler | |

**User's choice:** Managed identity + KV references (Recommended)

---

## Integration & guardrails

### Q13: Frontend↔API integration model — keep Phase-1's direct CORS path or layer SWA linked-API on top?

| Option | Description | Selected |
|--------|-------------|----------|
| Direct CORS (Recommended) | SPA calls ACA hostname directly; CORSMiddleware (Phase 1 D-26) allows SWA origin; DEPL-12 two-pass bootstrap; PITFALLS §10 single-pattern alignment; SWA linked-API ≈30–45s timeout would KILL SSE | ✓ |
| Linked-API for everything | Eliminates CORS entirely; BREAKS SSE due to proxy timeout | |
| Hybrid: linked-API for analytics, direct for /agent/stream | Two URL patterns; marginal benefit; real complexity cost | |

**User's choice:** Direct CORS (Recommended)
**Notes:** Critical reason: SWA linked-API proxy timeout (~30–45s) shorter than agent's 60s app-level timeout.

### Q14: terminationGracePeriodSeconds on the Container App template (Phase 1 D-17 carry-forward; PITFALLS §5)?

| Option | Description | Selected |
|--------|-------------|----------|
| 120s (Recommended) | Matches PITFALLS §5; allows 60s agent timeout + 30s shutdown drain + 30s buffer; honors Phase 1 STATE.md resolved Open Question | ✓ |
| 60s (matches agent timeout) | Tighter; no buffer; brittle to future agent timeout extension | |
| 240s (matches Envoy cap) | Maximum sane; blocks deploys for up to 4min; over-engineers | |

**User's choice:** 120s (Recommended)

### Q15: Log Analytics daily quota + which log categories (DEPL-10 says 5GB/mo alert; PITFALLS §17 says 0.1GB/day hard cap)?

| Option | Description | Selected |
|--------|-------------|----------|
| 0.15GB/day cap + ConsoleLogs only (Recommended) | ≈4.5GB/mo cap; 5GB/mo alert at ≈90% threshold; ContainerAppConsoleLogs_CL only; aligns PITFALLS §17 + DEPL-10 | ✓ |
| 0.1GB/day + ConsoleLogs only (PITFALLS literal) | ≈3GB/mo; tighter; higher chance of hitting daily ceiling | |
| 0.15GB/day + Console + System logs | Both categories; ~2x ingest; better forensics | |

**User's choice:** 0.15GB/day cap + ConsoleLogs only (Recommended)

### Q16: Cold-start mitigation — add a pre-warm cron in Phase 3 or defer to frontend UX (Phase 6)?

| Option | Description | Selected |
|--------|-------------|----------|
| Defer; frontend handles UX (Recommended) | No cron in Phase 3; UX states in Phase 6; backend already preloads reranker (Phase 1 D-27); usage is ad-hoc demo, not 9–5 | ✓ |
| GH Actions cron pings /health every 10min business-hours | ~32k vCPU-sec/mo; still wastes free-tier on no real users; brittle to DST | |
| minReplicas=1 always | Zero cold-start; ≈€15–20/mo BREAKS €0 budget | |

**User's choice:** Defer; frontend handles UX (Recommended)

---

## Continuation prompt

After all four areas resolved, asked: "We've discussed [areas] (16 decisions captured). Which gray areas remain unclear?"

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context | Write CONTEXT.md + DISCUSSION-LOG.md, commit, route to /gsd-plan-phase 3 | ✓ |
| Explore more gray areas | Open candidates: naming/tag policy, GH protected-environment approval gate detail, dev tenant separation contingency, Phase-2 follow-up scope | |

**User's choice:** I'm ready for context

---

## Claude's Discretion

Items deferred to planner/executor decision (documented in CONTEXT.md §"Claude's Discretion"):
- Resource naming convention (recommended `jobrag-{env}-{kind}`)
- Tag policy (recommended `project/env/managed_by`)
- Provider version pin granularity (recommended `~> 4.69` azurerm, `~> 3.0` azuread)
- Postgres storage size + autogrow (recommended 32GB + auto_grow_enabled)
- Postgres backup retention (recommended 7d)
- Firewall rule for Adrian's home IP (variable in tfvars + refresh runbook)
- ACA `revision_mode` (recommended `single`)
- KV soft-delete + purge protection settings
- KV access model (RBAC over access policies — implied by D-13)
- GHA action version pins (latest stable)
- LAW retention (30d default)
- `azure.extensions` value (`VECTOR` only in v1)
- SWA region (recommended `westeurope`)
- Protected-environment auto-approve setting (Adrian as sole reviewer)

## Deferred Ideas

Documented in CONTEXT.md §"Deferred Ideas" — 14 items including: private endpoint + VNet, Entra-auth-on-Postgres, PR-trigger OIDC cred, pre-warm cron, claims-matching expression, separate dev tenant, min_replicas=1, PG_TRGM extension, AVM-for-ACA upgrade, Azure Monitor availability test, AVM-only refactor, longer backup retention, ContainerAppSystemLogs_CL ingestion, infracost PR check, Phase-2 follow-up triage plan.
