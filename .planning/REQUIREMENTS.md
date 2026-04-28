# Requirements: job-rag web app

**Defined:** 2026-04-23
**Core Value:** Make Adrian's job-market corpus actually usable for his Berlin AI-Engineer job hunt — browse it, question it, measure his CV against it — while doubling as a portfolio artifact that maps to concrete Azure / MLOps / SQL gap-fill items on real job ads.

## v1 Requirements

Requirements for the initial release. Each maps to a single roadmap phase; the traceability table at the bottom is filled in by the roadmapper.

### Backend prep (BACK)

Close the seven blockers surfaced in the codebase audit and add the platform-ready hedges.

- [x] **BACK-01**: CORS middleware configured via env-var origin allowlist (dev: localhost:5173; prod: Azure Static Web Apps origin)
- [x] **BACK-02**: Pydantic models document the `/agent/stream` SSE event contract (`token` / `tool_start` / `tool_end` / `final`) and appear in OpenAPI
- [x] **BACK-03**: Cross-encoder reranker is preloaded in the FastAPI lifespan (no 2–5 s cold-start on first chat)
- [x] **BACK-04**: Reranker invocation wraps CPU-bound work in `asyncio.to_thread()` so the event loop is never blocked
- [x] **BACK-05**: `/agent/stream` emits a heartbeat event every 15 seconds to keep the Azure Container Apps Envoy idle timer from closing the stream
- [x] **BACK-06**: Agent endpoints enforce a 60 s timeout via `asyncio.wait_for`; timeout emits a graceful SSE error event instead of hanging
- [x] **BACK-07**: Alembic adopted for schema migrations; initial revision baselines the current schema
- [x] **BACK-08**: `user_id` UUID NOT NULL column added to all user-scoped tables via Alembic; seed row uses Adrian's UUID in v1 (no `DEFAULT` in DDL — value is app-layer injected from the JWT `sub`)
- [x] **BACK-09**: `career_id` TEXT NOT NULL column added to `job_posting_db`, default `"ai_engineer"`
- [x] **BACK-10**: `IngestionSource` Protocol defined with a `RawPosting` dataclass contract; the existing markdown-file reader is refactored as one `MarkdownFileSource` implementation

### Corpus cleanup — one-time re-extraction (CORP)

All four ship as a single pair to amortize the re-extraction cost.

- [x] **CORP-01**: Extraction prompt tightened to reject soft-skill noise (communication, problem-solving, analytical thinking, time management, teamwork, and similar)
- [x] **CORP-02**: `SkillCategory` enum added to `JobRequirement` (hard / soft / domain); extraction tags every requirement
- [x] **CORP-03**: Structured `Location` Pydantic schema added (country ISO-3166 code, city, region, remote_allowed boolean) replacing free-text `location` on `job_posting_db`
- [ ] **CORP-04**: `PROMPT_VERSION` bumped; full corpus (~108 postings) re-extracted against the new prompt and stored with the new `Location` schema

### Profile and resume upload (PROF)

- [ ] **PROF-01**: `UserProfile` DB model (skills list, target roles, preferred locations, min salary) added via Alembic; Adrian's profile seeded from the current `data/profile.json`; `data/profile.json` is removed from the canonical read path
- [ ] **PROF-02**: API endpoint accepts a PDF or DOCX upload (`multipart/form-data`, max 2 MB; `pypdf` 6.x for PDF text, `python-docx` 1.x for DOCX)
- [ ] **PROF-03**: Uploaded resume text is passed through Instructor + GPT-4o-mini with a pinned prompt version; returns a `UserSkillProfile` structured per the existing Pydantic schema
- [ ] **PROF-04**: API returns a reviewable diff of extracted skills vs the current profile (added / removed / unchanged) so the UI can show a side-by-side view
- [ ] **PROF-05**: Frontend review panel shows the extracted skills as tick/untick chips; user can edit skill names before saving
- [ ] **PROF-06**: Confirmed skills persist to the `user_profile` row via a PATCH endpoint; Langfuse traces the full extract → review → save flow

### Dashboard — static snapshot (DASH)

- [ ] **DASH-01**: Analytical endpoint returns top-N skills with must-have / nice-to-have split, filterable by country / seniority / remote; server-side SQL aggregation (no Python-side group-by)
- [ ] **DASH-02**: Analytical endpoint returns salary bands (p25 / p50 / p75) filterable by country / seniority / remote; uses PostgreSQL `percentile_cont`
- [ ] **DASH-03**: Analytical endpoint returns CV-vs-market aggregate match score (mean of per-posting scores across the filtered set) plus the top 3 missing must-have skills
- [ ] **DASH-04**: Dashboard React page renders all three widgets under one shared filter bar (country dropdown: Poland / Germany / EU / Worldwide; seniority; remote toggle)
- [ ] **DASH-05**: Top-skills widget exposes a "show more" drill-down that renders the full ranked list
- [ ] **DASH-06**: Dashboard filter state syncs to URL search params (deep links + refresh safe)

### Chat — streaming (CHAT)

- [ ] **CHAT-01**: Chat React page consumes `/agent/stream` via `fetch` + `ReadableStream` (EventSource cannot attach Bearer JWT headers)
- [ ] **CHAT-02**: `token` events render incrementally into the assistant bubble with smooth text append
- [ ] **CHAT-03**: `tool_start` events render as a collapsed chip showing tool name + JSON-preview of args
- [ ] **CHAT-04**: `tool_end` events expand the chip with an output preview (truncated ≥ 200 chars with "expand" affordance)
- [ ] **CHAT-05**: `final` event marks the assistant bubble complete and re-enables the input
- [ ] **CHAT-06**: Single-turn only in v1 — refreshing the page clears the conversation; no history persistence

### Frontend shell and UI baseline (SHEL)

- [ ] **SHEL-01**: Vite + React 19 + TypeScript project scaffolded in `frontend/`
- [ ] **SHEL-02**: Tailwind CSS v4 + shadcn/ui installed and themed to a Linear-style dense aesthetic (grayscale palette + one accent; small type; information-dense layouts)
- [ ] **SHEL-03**: TanStack Query installed; all server state flows through `useQuery`/`useMutation` (no ad-hoc `useEffect` fetching)
- [ ] **SHEL-04**: App shell provides a top-nav with Dashboard / Chat routes, logged-in user indicator, and sign-out
- [ ] **SHEL-05**: API client attaches the MSAL-issued access token as `Authorization: Bearer <jwt>` on every request
- [ ] **SHEL-06**: Error boundary + empty/error/loading states for every page; Suspense fallbacks for async boundaries

### Auth — Entra ID External Identities (AUTH)

- [ ] **AUTH-01**: Entra External ID tenant provisioned via Terraform (external SKU — not B2C legacy, not workforce)
- [ ] **AUTH-02**: SPA app registration created as a public client using PKCE authorization-code flow
- [ ] **AUTH-03**: API app registration created as a resource with a single `access_as_user` scope
- [ ] **AUTH-04**: MSAL React integrated in the frontend; protected routes redirect unauthenticated users to Entra login
- [ ] **AUTH-05**: FastAPI validates the Entra JWT on every protected request via `fastapi-azure-auth` 5.x (issuer, audience, signature, expiry, JWKS caching)
- [ ] **AUTH-06**: Adrian's Entra `oid` is stored in the `user_profile` row; an app-layer guard rejects any other `oid` in v1 (single-user enforcement)
- [ ] **AUTH-07**: MSAL initialization race prevented — `initialize()` and `handleRedirectPromise()` resolved before `ReactDOM.createRoot().render()`

### Deploy — IaC, CI/CD, Azure infra (DEPL)

- [ ] **DEPL-01**: Terraform remote state backend configured on Azure Blob Storage with state-locking
- [ ] **DEPL-02**: Terraform structure: `infra/envs/{dev,prod}` calling `infra/modules/*`; Azure Verified Modules used where available
- [ ] **DEPL-03**: Azure Container Apps environment + Container App (API) provisioned; min-replicas = 0 for scale-to-zero; max-replicas = 1 (single-user)
- [ ] **DEPL-04**: Azure DB for PostgreSQL Flexible Server B1ms provisioned with `pgvector` extension; SQLAlchemy pool sized to B1ms limits (`pool_size=3`, `max_overflow=2`)
- [ ] **DEPL-05**: Azure Static Web Apps (Free SKU) provisioned for the Vite build output
- [ ] **DEPL-06**: Azure Key Vault stores `OPENAI_API_KEY`, DB admin password, Langfuse keys; Container App retrieves them via managed identity at runtime
- [ ] **DEPL-07**: Container images built and pushed to GitHub Container Registry (GHCR), not Azure Container Registry Basic (saves ~€60/year)
- [ ] **DEPL-08**: GitHub Actions split into three workflows — `deploy-infra.yml` (Terraform), `deploy-api.yml` (Docker build/push/container-app update), `deploy-spa.yml` (Vite build/SWA deploy) — each with `paths` filters so changes only fire the relevant workflow
- [ ] **DEPL-09**: Each workflow authenticates to Azure via OIDC federated credential; role assignments are resource-group-scoped Contributor (never subscription-scoped); SWA uses a deployment token (OIDC isn't GA for SWA)
- [ ] **DEPL-10**: Log Analytics workspace captures Container Apps + Postgres logs; a 5 GB/month quota alert is configured to prevent surprise bills
- [ ] **DEPL-11**: Azure budget alert set at €10/month on the subscription; triggers email at 80% and 100% of cap
- [ ] **DEPL-12**: Terraform two-pass deploy handled: first apply provisions the SWA to discover its default origin; second apply injects that origin into the Container App's `ALLOWED_ORIGINS` env var

### MLOps and eval loop (EVAL)

- [ ] **EVAL-01**: RAGAS upgraded from 0.2.0 to 0.4.3 in `pyproject.toml` dev deps; import-sites updated for the 0.3 → 0.4 breaking API changes
- [ ] **EVAL-02**: Curated eval set of ~20 queries covering search / match / gaps flows in `tests/eval/dataset.json`, versioned in git
- [ ] **EVAL-03**: RAGAS evaluation harness at `tests/eval/run_eval.py` using `ragas.integrations.langgraph.convert_to_ragas_messages` against the live LangGraph agent
- [ ] **EVAL-04**: Metrics computed per run: Faithfulness, Answer Relevancy, Context Precision, Context Recall, ToolCallF1, AgentGoalAccuracy, TopicAdherence
- [ ] **EVAL-05**: GitHub Actions CI job runs the eval set on every PR that changes backend code; fails the build when a metric drops below its baseline threshold
- [ ] **EVAL-06**: Eval baseline committed at `tests/eval/baseline.json` with per-metric thresholds and documented acceptable variance to absorb LLM non-determinism
- [ ] **EVAL-07**: Langfuse wired into the Azure deployment (env vars sourced from Key Vault); production agent traces flow to the Langfuse dashboard

### Documentation (DOCS)

- [ ] **DOCS-01**: README updated with a web-app section — deploy URL, screenshots, architecture diagram
- [ ] **DOCS-02**: `ARCHITECTURE.md` (or a new `docs/topology.md`) supplemented with the frontend + Azure deploy topology
- [ ] **DOCS-03**: SSE streaming contract documented (event schema, client fetch+ReadableStream pattern, heartbeat behaviour, timeout semantics)

## v2 Requirements

Deferred to a future release. Tracked so they're not forgotten but not in this roadmap.

### Dashboard interactivity

- **DASH2-01**: Clickable charts that cross-filter the dashboard
- **DASH2-02**: Skill co-occurrence view (which skills travel together?)
- **DASH2-03**: Time-series trends (skill demand over time, salary drift)
- **DASH2-04**: Per-posting drill-down pages

### Chat enhancements

- **CHAT2-01**: Conversation history persisted per user
- **CHAT2-02**: Chat branching / forking
- **CHAT2-03**: Export chat as Markdown

### Platform evolution (if validated)

- **PLAT2-01**: Multi-user sign-up and tenancy UX (row-level security enforcement)
- **PLAT2-02**: Career taxonomy (user picks career; posting classifier fills `career_id`)
- **PLAT2-03**: Automated job-posting ingestion sources (scrapers, API, scheduled refresh)
- **PLAT2-04**: Custom skill taxonomy (O*NET or ESCO) with alias resolution
- **PLAT2-05**: Portfolio project idea generator (LLM matched to gaps + career)
- **PLAT2-06**: Learning resource recommender (curated catalog)
- **PLAT2-07**: Progress tracking over time

## Out of Scope

Explicitly excluded from this project. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Kubernetes / AKS | Azure free tier doesn't cover AKS (~€75/mo); K8s deserves its own repo with a proper scope |
| AWS | Picked one cloud (Azure) for portfolio depth; adding AWS would dilute focus |
| GCP / TensorFlow / classical-ML stack | Listed in gaps but doesn't fit a RAG/agent app; would be theatre |
| Full MLOps loop (drift detection, A/B prompt tests, alerting) | Overkill for v1; RAGAS-on-CI is the minimum viable loop |
| Custom skill taxonomy (ESCO / O*NET) with alias resolution | Platform-era feature; SkillCategory enum is enough for v1 |
| Billing, payments, plan tiers | Platform-era feature; v1 is single-user |
| Mobile app / React Native | Web-first; mobile is post-validation |
| Real-time or scheduled corpus refresh | Adrian continues curating via CLI; `IngestionSource` Protocol leaves the door open |

## Traceability

Which phases cover which requirements. Filled in by the roadmapper.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BACK-01 | Phase 1 | Complete |
| BACK-02 | Phase 1 | Complete |
| BACK-03 | Phase 1 | Complete |
| BACK-04 | Phase 1 | Complete |
| BACK-05 | Phase 1 | Complete |
| BACK-06 | Phase 1 | Complete |
| BACK-07 | Phase 1 | Complete |
| BACK-08 | Phase 1 | Complete |
| BACK-09 | Phase 1 | Complete |
| BACK-10 | Phase 1 | Complete |
| CORP-01 | Phase 2 | Complete |
| CORP-02 | Phase 2 | Complete |
| CORP-03 | Phase 2 | Complete |
| CORP-04 | Phase 2 | Pending |
| PROF-01 | Phase 7 | Pending |
| PROF-02 | Phase 7 | Pending |
| PROF-03 | Phase 7 | Pending |
| PROF-04 | Phase 7 | Pending |
| PROF-05 | Phase 7 | Pending |
| PROF-06 | Phase 7 | Pending |
| DASH-01 | Phase 5 | Pending |
| DASH-02 | Phase 5 | Pending |
| DASH-03 | Phase 5 | Pending |
| DASH-04 | Phase 5 | Pending |
| DASH-05 | Phase 5 | Pending |
| DASH-06 | Phase 5 | Pending |
| CHAT-01 | Phase 6 | Pending |
| CHAT-02 | Phase 6 | Pending |
| CHAT-03 | Phase 6 | Pending |
| CHAT-04 | Phase 6 | Pending |
| CHAT-05 | Phase 6 | Pending |
| CHAT-06 | Phase 6 | Pending |
| SHEL-01 | Phase 4 | Pending |
| SHEL-02 | Phase 4 | Pending |
| SHEL-03 | Phase 4 | Pending |
| SHEL-04 | Phase 4 | Pending |
| SHEL-05 | Phase 4 | Pending |
| SHEL-06 | Phase 4 | Pending |
| AUTH-01 | Phase 4 | Pending |
| AUTH-02 | Phase 4 | Pending |
| AUTH-03 | Phase 4 | Pending |
| AUTH-04 | Phase 4 | Pending |
| AUTH-05 | Phase 4 | Pending |
| AUTH-06 | Phase 4 | Pending |
| AUTH-07 | Phase 4 | Pending |
| DEPL-01 | Phase 3 | Pending |
| DEPL-02 | Phase 3 | Pending |
| DEPL-03 | Phase 3 | Pending |
| DEPL-04 | Phase 3 | Pending |
| DEPL-05 | Phase 3 | Pending |
| DEPL-06 | Phase 3 | Pending |
| DEPL-07 | Phase 3 | Pending |
| DEPL-08 | Phase 3 | Pending |
| DEPL-09 | Phase 3 | Pending |
| DEPL-10 | Phase 3 | Pending |
| DEPL-11 | Phase 3 | Pending |
| DEPL-12 | Phase 3 | Pending |
| EVAL-01 | Phase 8 | Pending |
| EVAL-02 | Phase 8 | Pending |
| EVAL-03 | Phase 8 | Pending |
| EVAL-04 | Phase 8 | Pending |
| EVAL-05 | Phase 8 | Pending |
| EVAL-06 | Phase 8 | Pending |
| EVAL-07 | Phase 8 | Pending |
| DOCS-01 | Phase 8 | Pending |
| DOCS-02 | Phase 8 | Pending |
| DOCS-03 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 67 total
- Mapped to phases: 67
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-23*
*Last updated: 2026-04-23 after roadmap creation (Traceability filled)*
