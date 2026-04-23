# job-rag

## What This Is

A private web app that productizes the existing job-rag backend (Python 3.12 / FastAPI / LangGraph / PostgreSQL+pgvector) into a usable tool for Adrian's AI-Engineer job hunt in the Berlin / German / remote market. Two surfaces on top of the current RAG/agent stack: a **Dashboard** for browsing the corpus at a glance (top skills, salary bands, country-filtered views, CV-vs-market match score) and a **Chat** page that streams the existing LangGraph ReAct agent. Deployed to Azure on free tier. Single-user in v1 but structurally platform-ready so it can evolve into a multi-user career-investigation product without a rewrite.

## Core Value

Make Adrian's job-market corpus actually useful for his job hunt — browse it, question it, measure his CV against it — while simultaneously fulfilling as a portfolio artifact that maps to concrete cloud / MLOps / SQL skill gaps on real AI-Engineer job ads.

## Requirements

### Validated

<!-- Inferred from existing code. These capabilities already work. -->

- ✓ Parse markdown job postings and extract structured `JobPosting` / `JobRequirement` data via Instructor + GPT-4o-mini — existing
- ✓ Store postings in PostgreSQL with pgvector embeddings for semantic search — existing
- ✓ Semantic search with cross-encoder reranking (top-20 → top-5) — existing
- ✓ Profile-to-posting skill matching with must-have / nice-to-have weighting — existing
- ✓ Aggregate skill-gap analysis across filtered postings — existing
- ✓ LangGraph ReAct agent with `search_jobs` / `match_profile` / `analyze_gaps` tools — existing
- ✓ REST API (FastAPI) with SSE streaming for agent (`/agent/stream`) — existing
- ✓ Typer CLI for ingest / embed / serve / agent / mcp — existing
- ✓ FastMCP stdio server exposing 4 tools to Claude Code — existing
- ✓ Optional Langfuse observability (fail-open when keys missing) — existing
- ✓ Optional Bearer-token API auth via `JOB_RAG_API_KEY` — existing
- ✓ In-process per-IP rate limiting — existing
- ✓ Containerised via multi-stage Dockerfile with CPU-only PyTorch — existing
- ✓ docker-compose dev stack (pgvector/pg17 + API container) — existing

### Active

<!-- New scope for this milestone. Hypotheses until shipped. -->

#### Backend prep (pre-frontend)

- [ ] CORS middleware configured via env-var origin allowlist (dev: localhost; prod: SWA origin)
- [ ] Pydantic models documenting the `/agent/stream` SSE event contract (`token` / `tool_start` / `tool_end` / `final`) and exposed in OpenAPI
- [ ] Cross-encoder reranker preloaded in FastAPI lifespan (eliminates cold-start latency on first chat)
- [ ] Reranker invocation wrapped in `asyncio.to_thread()` to stop blocking the event loop
- [ ] Agent request timeout (`asyncio.wait_for`, 60s default) with graceful SSE error event
- [ ] `user_id` UUID column added to all user-scoped tables (conversations, profile rows) with default = Adrian's UUID in v1
- [ ] `career_id` column added to `job_posting_db` with default `"ai_engineer"`
- [ ] `IngestionSource` Protocol defined; existing markdown reader reimplemented as one implementation

#### Skill and location cleanup (one-time re-extraction)

- [ ] `PROMPT_VERSION` bumped; extraction prompt tightened to reject soft-skill noise (communication, problem-solving, analytical thinking)
- [ ] `SkillCategory` enum added to `JobRequirement` (hard / soft / domain) so dashboard can filter
- [ ] Structured `Location` Pydantic schema added (country ISO code, city, region, remote_allowed)
- [ ] Full corpus re-extracted against bumped `PROMPT_VERSION` (~108 postings, one-time cost)

#### Profile + resume upload

- [ ] `UserProfile` DB model replaces `data/profile.json` (skills list, target roles, preferred locations, min salary)
- [ ] API endpoint accepts PDF or DOCX upload, extracts text, calls Instructor to parse into `UserSkillProfile`
- [ ] Resume-extraction prompt produces a reviewable diff vs. current profile
- [ ] Frontend shows extracted skills in a review panel — tick / untick / edit before saving
- [ ] Confirmed skills persist to the `user_profile` row

#### Dashboard (static snapshot)

- [ ] Analytical SQL endpoint: top-N skills with must-have vs nice-to-have breakdown, filterable by country / seniority / remote
- [ ] Analytical SQL endpoint: salary bands (p25 / p50 / p75) filterable by country / seniority / remote
- [ ] Analytical SQL endpoint: CV-vs-market match score (aggregate of per-posting match scores across the filtered set)
- [ ] Dashboard React page renders all three widgets with a shared filter bar (country dropdown: Poland / Germany / EU / Worldwide; seniority; remote toggle)
- [ ] "Top skills" widget supports "show more" drill into a full ranked list

#### Chat

- [ ] Chat React page consumes `/agent/stream` via native `EventSource` or `fetch` + SSE reader
- [ ] Token events render into the assistant bubble incrementally
- [ ] `tool_start` events show a collapsed "→ calling search_jobs" chip with args
- [ ] `tool_end` events expand the chip with a preview of the output
- [ ] Single-turn only in v1 (no conversation history); clear-on-refresh

#### Frontend shell

- [ ] Vite + React + TypeScript project scaffolded
- [ ] Tailwind + shadcn/ui installed and themed to Linear-style dense aesthetic (grayscale + one accent, small type, dense info)
- [ ] App shell with top-nav (Dashboard / Chat) and Entra-ID login wall
- [ ] API client uses the MSAL-issued access token as Bearer

#### Auth (Entra ID External Identities)

- [ ] Entra ID tenant provisioned via Terraform
- [ ] SPA registered as a public client; API registered as a resource with one scope
- [ ] MSAL React integrated in the frontend; protected routes redirect to login
- [ ] FastAPI validates the Entra JWT on every request (issuer, audience, signature)
- [ ] Adrian's UUID seeded as the only user

#### Deploy (Azure free tier, Terraform)

- [ ] Terraform workspaces configured (`dev` scaffolded, `prod` primary)
- [ ] Azure Container Apps environment provisioned (API container, scale-to-zero configured)
- [ ] Azure DB for PostgreSQL Flexible Server B1ms (Burstable) provisioned with `pgvector` extension
- [ ] Azure Static Web Apps provisioned for the Vite build output
- [ ] Azure Key Vault stores `OPENAI_API_KEY`, DB password, Langfuse keys
- [ ] Azure Container Registry (Basic) or GitHub Container Registry hosts images
- [ ] GitHub Actions workflow deploys via OIDC federated credential (no long-lived secrets)
- [ ] Log Analytics workspace captures Container Apps logs
- [ ] Cost guardrails: DB has a "stop" workflow the user can trigger manually; Container Apps min-replicas = 0

#### MLOps / eval loop

- [ ] Langfuse keys wired into cloud deployment; tracing active
- [ ] Curated eval set of ~20 queries covering search / match / gaps flows
- [ ] RAGAS evaluation harness runs the set against a live dev environment
- [ ] GitHub Actions CI job runs the eval set on every PR; fails the build on regression beyond threshold
- [ ] Eval results surfaced in Langfuse

#### Documentation

- [ ] README updated with the web-app section (deploy URL, screenshots, architecture diagram)
- [ ] `ARCHITECTURE.md` supplemented with the frontend / deploy topology

### Out of Scope

- **Kubernetes / AKS** — deliberately skipped; separate future project if needed. Azure free tier doesn't cover AKS and the docker-compose → AKS learning curve deserves its own repo.
- **AWS** — picked one cloud (Azure) for the portfolio story. Adding AWS would dilute depth.
- **Multi-user sign-up / tenancy UX** — schema is platform-ready (`user_id` everywhere), but no registration, no row-level security enforcement, no org model in v1.
- **Career-investigation platform features** — portfolio project generator, learning resource recommender, progress tracking over time. Valid v2 pivot if demand is validated.
- **Automated job-posting ingestion** — no scrapers, no LinkedIn/Indeed API, no scheduled refresh. Adrian continues curating postings via the CLI. `IngestionSource` Protocol exists for future plug-ins.
- **Interactive drill-down dashboard** — static snapshot only. Clickable charts, skill co-occurrence graphs, time-series trends are v2.
- **Conversation history / branching chat** — single-turn, clear-on-refresh. Chat-history schema + sidebar is v2.
- **TensorFlow / classical ML / GCP** — listed in skill gaps but don't fit a RAG/agent app; chasing them here would be theatre.
- **Full MLOps loop** — drift detection, prompt-version regression alerts, model A/B harness. Too much for v1; RAGAS on CI is the minimum viable loop.
- **Custom skill taxonomy (O*NET / ESCO)** — soft-skill cleanup via `SkillCategory` enum is enough for v1. Canonical taxonomy is a platform-era feature.
- **Billing / payments / plan tiers** — platform-era. Single user pays their own OpenAI bill.

## Context

### Existing codebase

The backend is a three-tier system (Ingestion → Retrieval + Matching → Intelligence/Tools), with a shared async tool layer reused by CLI, REST, agent, and MCP entry points. Dual SQLAlchemy engines (sync for CLI, async for API). 108 job postings currently ingested, mostly AI-Engineer roles. Docker-compose runs the stack locally. Full codebase map in `.planning/codebase/`.

### Skill-gap data (as of 2026-04-15, 108 postings)

Top must-have gaps in Adrian's corpus: AWS (16%), SQL (16%), Azure (13%), MLOps (12%), TensorFlow (11%), GCP (10%), Kubernetes (9%). Priority clusters: cloud (AWS/Azure/GCP), MLOps stack (MLOps/Kubernetes/MLflow/Airflow), classical ML (SQL/TensorFlow/ML/NLP), data engineering (pipelines/Spark/Databricks). Analysis in `data/skill-gaps.json`; LLM-extraction noise on soft skills acknowledged and addressed by this milestone.

### Target market

Adrian targets Berlin / Germany / remote AI-Engineer roles at €65k+. Germany's enterprise market is Azure-heavy (SAP, Siemens, BMW); startups are mixed AWS/Azure. Azure chosen over AWS for the portfolio artifact to match the target market.

### User profile

Adrian's current skills (from `data/profile.json`): Python, FastAPI, React, Docker, PostgreSQL, LangGraph, TypeScript, prompt engineering, RAG, Langfuse, CI/CD. Missing on the gap list that this project fills: Azure, Terraform, Entra ID, analytical SQL, RAG evaluation.

### Known backend blockers for a web UI (from codebase audit)

1. No CORS middleware
2. User profile is a hardcoded JSON file (no user model, no DB-backed profile)
3. `/agent/stream` SSE contract is undocumented (only in code comments)
4. Cross-encoder reranker loads lazily — 2–5s cold-start on first chat
5. Reranker runs synchronously in async context (blocks event loop)
6. No request timeout on agent endpoints
7. Ingestion mixes async HTTP context with sync ingest pipeline

All seven are explicitly addressed in the Active requirements.

## Constraints

- **Tech stack (frozen)**: Python 3.12, FastAPI, LangGraph 1.1.x, PostgreSQL 17 + pgvector, SQLAlchemy 2.x async, Instructor, OpenAI SDK. The backend stack is inherited; this milestone doesn't introduce new backend frameworks.
- **Frontend stack (chosen)**: Vite + React 18+ + TypeScript, Tailwind CSS, shadcn/ui, MSAL React for Entra ID. Pure SPA — no SSR.
- **Cloud provider (chosen)**: Azure only. No multi-cloud.
- **Budget**: target €0/month on Azure free tier for year 1; ≤ €20/month year 2 (via DB stop + scale-to-zero).
- **IaC**: Terraform only. Bicep / ARM / CLI scripts not used.
- **Single user (structurally multi-user)**: v1 has one user (Adrian) but every table carries `user_id` and every query filters by it.
- **One cloud, one provider per concern**: managed Postgres (Azure DB), managed secrets (Key Vault), managed identity (Entra ID), managed containers (Container Apps), managed static hosting (Static Web Apps), managed CI (GitHub Actions + OIDC). Don't mix in third-party equivalents.
- **Educational goal**: the frontend and backend must remain cleanly separated. Logic that belongs in the backend cannot live in the frontend, and vice versa.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Azure free tier over AWS or local-only | Berlin market is Azure-heavy (13% of ads, enterprise-dominant); free tier covers year 1; direct interview-talking-point for the target market | — Pending |
| Vite + React SPA + Static Web Apps (not Next.js) | Cleanest frontend↔backend separation — impossible to accidentally colocate logic. Matches the educational goal. | — Pending |
| Entra ID External Identities instead of a passphrase | Same build effort as a passphrase login, real Azure identity skill, zero rewrite when v1 becomes multi-user | — Pending |
| `user_id` and `career_id` columns from day 1 | ~10% extra migration scope now, saves a painful refactor if the tool pivots to a career-investigation platform later | — Pending |
| `IngestionSource` Protocol with one v1 implementation | Decouples storage from ingestion source; future scrapers / APIs can be added without touching models or services | — Pending |
| Re-extraction with structured `Location` + `SkillCategory` | Free-text `location` can't support country filters; soft-skill noise pollutes the gap analysis. One `PROMPT_VERSION` bump fixes both. | — Pending |
| PDF/DOCX resume upload with show-and-confirm UX | Reuses the Instructor pattern the backend already knows; "inspectable AI extraction" is a direct portfolio talking point for AI-Engineer interviews | — Pending |
| Static-snapshot dashboard, not interactive explorer | Matches single-user scope; the existing corpus is ~108 postings, not enough to warrant deep exploration. Interactive is a v2 candidate. | — Pending |
| Chat is stream-only, no history | Keeps the surface minimal and matches the snapshot philosophy. Chat-history is a v2 candidate. | — Pending |
| RAGAS + CI gate for agent eval | Langfuse alone catches production issues; RAGAS catches regressions before merge. Minimum viable MLOps loop. | — Pending |
| Skip Kubernetes in this project | Azure free tier doesn't include AKS (~€75/mo); K8s deserves its own repo with a proper scope | — Pending |
| Linear-style dense aesthetic | Matches a data-dense dashboard; faster to execute than Stripe-polish; dark-mode-friendly | — Pending |
| Terraform workspaces (dev + prod) from day 1 | 30 min extra scaffolding, saves hours when a staging env is needed | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-23 after initialization*
