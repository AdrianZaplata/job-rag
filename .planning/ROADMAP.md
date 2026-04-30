# Roadmap: job-rag web-app milestone

**Created:** 2026-04-23
**Granularity:** standard (5-8 phases, 3-5 plans each)
**Parallelization:** true
**Model profile:** quality

## Milestone Goal

Ship a deployed, Entra-gated Vite+React SPA on Azure free tier that delivers:
- A dashboard (top skills, salary bands, CV-vs-market match score) over Adrian's curated AI-Engineer corpus
- A streaming chat page with inline tool-call chips over the existing LangGraph agent
- A resume-upload + reviewable-extraction flow that keeps the profile fresh
- A RAGAS-on-CI eval gate and Langfuse production tracing

Plus all the backend hedges (user_id, career_id, IngestionSource Protocol, Alembic, pre-loaded reranker, CORS, JWT) that keep the single-user v1 structurally platform-ready.

## Phases

- [x] **Phase 1: Backend Prep** - Close the seven web-UI blockers and land the multi-tenant data-model hedges (verified 2026-04-27, 5/5 must-haves)
- [x] **Phase 2: Corpus Cleanup** - Amortize one PROMPT_VERSION bump + full re-extraction across SkillCategory + structured Location
 (completed 2026-04-28)
- [ ] **Phase 3: Infrastructure & CI/CD** - Provision the entire Azure stack (Entra, ACA, Postgres, SWA, KV, LAW) via Terraform + three OIDC-federated GitHub Actions workflows
- [ ] **Phase 4: Frontend Shell + Auth** - Wire MSAL-backed auth end-to-end so every subsequent page has a real user context
- [ ] **Phase 5: Dashboard** - Ship the three analytical widgets and shared filter bar for the first demoable, shareable surface
- [ ] **Phase 6: Chat** - Ship the number-one portfolio-signal feature: streaming tokens with inline tool-call chips
- [ ] **Phase 7: Profile & Resume Upload** - Close the personal-data loop so CV-vs-market scores stay fresh without CLI edits
- [ ] **Phase 8: Eval & Documentation** - Close the MLOps loop with a CI-gated RAGAS harness and publish the web-app deploy story

## Phase Details

### Phase 1: Backend Prep
**Goal**: Phase 1 ships a refactored backend when all seven web-UI blockers are closed, Alembic owns the schema, and every user-scoped table carries a JWT-injected `user_id`.
**Depends on**: Nothing (first phase)
**Parallel-eligible with**: Phase 2 (no shared dependencies)
**Requirements**: BACK-01, BACK-02, BACK-03, BACK-04, BACK-05, BACK-06, BACK-07, BACK-08, BACK-09, BACK-10
**Success Criteria** (what must be TRUE):
  1. A browser-origin SPA on `http://localhost:5173` can POST to the local API without CORS rejection, and the OpenAPI doc at `/docs` shows `AgentEvent` as a typed SSE event model (BACK-01, BACK-02)
  2. The first chat against a freshly-started container streams its first token in <2s — no 2-5s reranker cold-start, no event-loop stalls (BACK-03, BACK-04)
  3. `/agent/stream` emits a `heartbeat` event every 15s during active reasoning, and an in-flight agent call cancels with a `{"event": "error", "data": {"reason": "agent_timeout"}}` SSE frame at the 60s mark (BACK-05, BACK-06)
  4. `alembic upgrade head` is the only schema-creation path; running it against a fresh Postgres instance creates every table including `user_profile`, with `user_id UUID NOT NULL` (no DEFAULT) on every user-scoped table and `career_id TEXT NOT NULL DEFAULT 'ai_engineer'` on `job_posting_db` (BACK-07, BACK-08, BACK-09)
  5. The existing `job-rag ingest data/postings/` CLI call still works end-to-end, but now routes through `MarkdownFileSource` implementing the `IngestionSource` Protocol (BACK-10)
**Cost delta**: €0/mo (pure refactor, no Azure provisioning)
**Plans**: 6 plans
Plans:
- [x] 01-01-PLAN.md — Wave 0 foundation: alembic/asgi-lifespan deps, 4 new Settings fields, conftest fixtures, 6 new test files, docker-compose ALLOWED_ORIGINS wire (BACK-01/05/06/08 setup)
- [x] 01-02-PLAN.md — Alembic adoption: baseline autogenerate + user/profile/career_id migrations, init_db wraps `alembic upgrade head`, UserDB/UserProfileDB ORM classes (BACK-07/08/09)
- [x] 01-03-PLAN.md — IngestionSource Protocol + RawPosting + MarkdownFileSource + ingest_from_source async consumer; sync ingest_file rewrap preserves CLI contract (BACK-10)
- [x] 01-04-PLAN.md — SSE event contract: six-model Pydantic discriminated union in api/sse.py + agent/stream.py rewired to yield Pydantic events (BACK-02)
- [x] 01-05-PLAN.md — FastAPI lifespan (reranker preload + shutdown event + 30s drain) + CORS middleware + get_current_user_id dep + asyncio.to_thread rerank wrap + load_profile user_id kwarg (BACK-01/03/04/08)
- [x] 01-06-PLAN.md — Route handler rewrite: agent_stream with heartbeat + 60s timeout + sanitized errors + shutdown drain; /match /gaps /ingest user_id injection; CI postgres service + alembic smoke + grep guard (BACK-05/06)

### Phase 2: Corpus Cleanup
**Goal**: Phase 2 ships a re-extracted 108-posting corpus when every `JobRequirement` carries a `SkillCategory` and every `JobPosting` carries a structured `Location` against a single bumped `PROMPT_VERSION`.
**Depends on**: Phase 1 (Alembic + `IngestionSource` Protocol needed to migrate the new `Location` column and re-ingest cleanly)
**Parallel-eligible with**: Phase 3 (different surfaces; re-extraction runs against the local DB while Terraform spins up Azure)
**Requirements**: CORP-01, CORP-02, CORP-03, CORP-04
**Success Criteria** (what must be TRUE):
  1. `PROMPT_VERSION` in `src/job_rag/extraction/prompt.py` is bumped to the next version, and the tightened prompt explicitly rejects soft-skill noise — a sanity run against 5 postings with heavy soft-skill content returns zero `soft` skills where the old prompt would have extracted "communication", "teamwork", etc. (CORP-01)
  2. Every row in `job_requirement_db` has a non-null `skill_category` column populated with `hard`, `soft`, or `domain`; `SELECT skill_category, COUNT(*) FROM job_requirement_db GROUP BY skill_category` returns a sensible distribution (CORP-02)
  3. Every row in `job_posting_db` has its free-text `location` migrated to the structured `Location` schema — `country_code` ISO-3166 on every row, `remote_allowed` boolean, optional `city`/`region` (CORP-03)
  4. Running `job-rag list --stats` against the re-extracted corpus shows 108 postings with the new `prompt_version` string and no remaining postings from the prior version (CORP-04)
**Cost delta**: ~€0.20 one-time (re-extraction of ~108 postings via GPT-4o-mini)
**Plans**: 4 plans
Plans:
- [x] 02-01-PLAN.md — Pydantic + ORM schema evolution: rename SkillCategory→SkillType, add new SkillCategory(hard/soft/domain), Location submodel, derive_skill_category, db/models.py columns + indexes, conftest sample_posting fixture refresh (CORP-02/CORP-03)
- [x] 02-02-PLAN.md — extraction prompt rewrite: PROMPT_VERSION 1.1→2.0, REJECTED_SOFT_SKILLS tuple, str.format()-built SYSTEM_PROMPT with Location examples + borderline + spoken-language carve-outs, TestPromptStructure / TestRejectionRules tests (CORP-01)
- [x] 02-03-PLAN.md — Alembic 0004 migration (BLOCKING upgrade head) + reextract_stale service + call-site sweeps (ingestion/embedding/retrieval/mcp_server) + reextract CLI + list --stats + lifespan drift warning + tests (CORP-01..04)
- [x] 02-04-PLAN.md — corpus refresh execution: pg_dump backup, dry-run baseline, run reextract against 108 postings, validate 4 SQL sanity checks, capture results in 02-04-SUMMARY.md (CORP-01..04 closure)

### Phase 3: Infrastructure & CI/CD
**Goal**: Phase 3 ships a fully provisioned Azure stack when `terraform apply` (run twice to resolve the CORS cycle) produces a working Entra External tenant, an ACA container, a B1ms Postgres with pgvector, an SWA origin, Key Vault-backed secrets, and three OIDC-federated GitHub Actions workflows can deploy infra / API / SPA independently.
**Depends on**: Phase 1 (Alembic migrations must exist before Postgres pgvector provisioning can smoke-test against them) and Phase 2 (if Phase 2 has landed, the re-extracted corpus is what gets seeded)
**Parallel-eligible with**: Phase 2 (separate concern)
**Requirements**: DEPL-01, DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06, DEPL-07, DEPL-08, DEPL-09, DEPL-10, DEPL-11, DEPL-12
**Success Criteria** (what must be TRUE):
  1. `terraform apply` in `infra/envs/prod/` creates the complete Azure resource graph — ACA environment + Container App (min_replicas=0, max_replicas=1), Postgres Flex B1ms with `vector` in `azure.extensions`, SWA Free SKU, Key Vault with `OPENAI_API_KEY` / DB-password / Langfuse keys, Log Analytics with 5 GB/mo cap, €10/mo subscription budget alert (DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06, DEPL-10, DEPL-11)
  2. Terraform state lives in an Azure Blob backend with state-locking; a second `terraform apply` from a clean clone succeeds without local `.tfstate` (DEPL-01)
  3. The two-pass CORS bootstrap is documented and works — first apply discovers the SWA default origin, second apply injects it into the Container App's `ALLOWED_ORIGINS` (DEPL-12)
  4. `deploy-infra.yml`, `deploy-api.yml`, `deploy-spa.yml` each authenticate via OIDC federated credential (no long-lived secrets except the SWA deployment token), use resource-group-scoped Contributor (never subscription-scoped), and their `paths` filters mean a frontend-only PR doesn't fire the infra workflow (DEPL-08, DEPL-09)
  5. A hello-world container image pushed to GHCR (not ACR Basic) and referenced by the Container App is reachable at the ACA FQDN over HTTPS (DEPL-07)
**Cost delta**: ~€0/mo target (Azure free tier + B1ms free-12-months + SWA Free + LAW 5 GB free); €10/mo budget alert as the hard ceiling
**Plans**: 8 plans (split per W4: Plan 05 → 05a + 05b)
Plans:
- [ ] 03-01-PLAN.md — Wave 0 validation scaffolding: tflint.hcl + tfsec config + runbook skeletons + scripts/refresh-swa-origin.sh + .github/workflows/static-tf.yml + .gitignore TF block (DEPL-01/02/12 setup)
- [ ] 03-02-PLAN.md — Bootstrap module: infra/bootstrap/ with state-storage RG + storage + container + External tenant import path; documents portal click-path for D-05 manual tenant creation (DEPL-01)
- [ ] 03-03-PLAN.md — Shared modules A: network (ACA env), kv (AVM 0.10.2 + RBAC + role_assignments), monitoring (AVM LAW 0.5.1 + budget €10/mo with 50/75/90/100% thresholds via data.azurerm_subscription per W1; diagnostic_setting moved to composition layer per W7) (DEPL-02/03/06/10/11)
- [ ] 03-04-PLAN.md — Shared modules B: database (AVM Postgres 0.2.2 + B1ms + VECTOR allowlist + jobrag DB + 32-char random_password + A1 Path A firewall), compute (raw azurerm_container_app + scale-to-zero + termination_grace_period_seconds=120 + lifecycle.ignore_changes for image+revision_suffix per B5 + ingress[0].fqdn output per W5 + 5 KV secret refs + GHCR registry), identity (3 azuread_applications + 2 federated credentials with lower() subjects + RG-scoped Contributor + B1 empty-string redirect_uris fix) (DEPL-02/03/04/06/07/08/09)
- [ ] 03-05a-PLAN.md — Prod env composition: envs/prod composes all 6 modules + adds raw SWA + 4 KV secrets + role assignments + W7 composition-layer diagnostic_setting + locals.allowed_origins_csv for DEPL-12 two-pass + 11-output Phase 4 hand-off bundle (+ swa_api_key alias for B2); fills prod README with W2 ordered runbook + B2 manual SWA-token-sync + B3 GHCR visibility (DEPL-01/02/04/05/06/12)
- [ ] 03-05b-PLAN.md — Dev scaffold + entrypoint update + bootstrap-corpus workflow: envs/dev mirrors prod as scaffold-only per D-04; scripts/docker-entrypoint.sh runs ONLY init-db + uvicorn per B4 (corpus ingest/embed REMOVED); .github/workflows/bootstrap-corpus.yml ships as workflow_dispatch-only one-shot per A6 (DEPL-01/02)
- [ ] 03-06-PLAN.md — GHA deploy workflows: deploy-infra.yml (OIDC + environment:production gate + B2 manual SWA-token-sync runbook reminder via summary, NO `gh secret set` step), deploy-api.yml (OIDC + docker/build-push-action@v6 to GHCR + az containerapp update + B3 visibility comment), deploy-spa.yml (sole non-OIDC, uses AZURE_STATIC_WEB_APPS_API_TOKEN_PROD) (DEPL-07/08/09)
- [ ] 03-07-PLAN.md — Live-Azure smoke runbook: M1–M13 from VALIDATION.md against applied prod stack; produces 03-SMOKE.md with evidence covering all 12 DEPL-* requirements + 8 T-3-* threat verifications; autonomous: false because verification requires real Azure resources

### Phase 4: Frontend Shell + Auth
**Goal**: Phase 4 ships a logged-in-end-to-end SPA when the Vite+React shell loads from SWA, Entra login completes a real round-trip, and the FastAPI `/health` endpoint returns 200 only when called with a valid Entra-issued Bearer JWT — with Adrian's `oid` as the single permitted user.
**Depends on**: Phase 3 (needs real Entra tenant IDs, API app client ID, SWA origin for the MSAL redirect URI, and the Container App to validate JWTs against)
**Parallel-eligible with**: Nothing (blocks Phases 5, 6, 7)
**Requirements**: SHEL-01, SHEL-02, SHEL-03, SHEL-04, SHEL-05, SHEL-06, AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
  1. Navigating to the SWA URL presents a Linear-dense top-nav with Dashboard / Chat / sign-out; hitting a protected route when signed-out redirects to the Entra External ID (`*.ciamlogin.com`) authority and returns the user to the app post-login (SHEL-01, SHEL-02, SHEL-04, AUTH-01, AUTH-02, AUTH-04)
  2. A hard-refresh while already logged in does NOT flash the login page — `initialize()` + `handleRedirectPromise()` resolve before `createRoot().render()` so MSAL state is settled on first paint (AUTH-07)
  3. Every API call from the SPA attaches `Authorization: Bearer <jwt>` via the TanStack-Query-wrapped API client; every FastAPI route requires that JWT and rejects unsigned / wrong-audience / expired tokens via `fastapi-azure-auth` (SHEL-05, AUTH-03, AUTH-05)
  4. An Entra token minted for any `oid` other than Adrian's seeded `SEEDED_USER_ENTRA_OID` is rejected with a 403 before any business logic runs; Adrian's token reaches the endpoint with `user_id` resolved application-side (AUTH-06)
  5. Every page under the shell renders distinct loading skeletons / empty states / error boundaries — there is no blank-screen-during-fetch state and no unhandled error can propagate past the root `<ErrorBoundary>` (SHEL-03, SHEL-06)
**Cost delta**: €0/mo (runtime only; Entra External ID free up to 50k MAU)
**Plans**: TBD
**UI hint**: yes

### Phase 5: Dashboard
**Goal**: Phase 5 ships the first shareable surface when the Dashboard page renders three analytical widgets (top skills, salary bands, CV-vs-market score) under a shared filter bar, with state round-tripping through URL search params.
**Depends on**: Phases 1 (user_id + career_id in queries), 2 (structured Location + SkillCategory enable the filter + clean skills), 4 (auth'd API client)
**Parallel-eligible with**: Phase 6 (independent features)
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06
**Success Criteria** (what must be TRUE):
  1. Visiting `/dashboard?country=DE&seniority=senior&remote=true` renders the dashboard with the country dropdown, seniority select, and remote toggle pre-set to those values, and changing any filter updates the URL in place (DASH-04, DASH-06)
  2. The top-skills widget shows the top 8-10 hard skills (soft skills hidden by default via `SkillCategory` filter) with a must-have / nice-to-have split; clicking "show more" expands to the full ranked list (DASH-01, DASH-05)
  3. The salary-bands widget shows p25 / p50 / p75 computed server-side via `percentile_cont`, with a footnote "N of M postings had salary data" so the sample size is visible (DASH-02)
  4. The CV-vs-market widget shows an aggregate match score (mean of per-posting scores across the filtered set) plus the top 3 missing must-have skills, updating as filters change (DASH-03)
  5. Flipping the country filter between Poland / Germany / EU / Worldwide produces genuinely different numbers on all three widgets (proves the filter actually flows through to SQL, not just the URL) (DASH-01, DASH-02, DASH-03, DASH-04)
**Cost delta**: €0/mo (runtime only; analytical queries against existing B1ms)
**Plans**: TBD
**UI hint**: yes

### Phase 6: Chat
**Goal**: Phase 6 ships the number-one portfolio-signal surface when the Chat page streams tokens incrementally via `fetch`+`ReadableStream`, renders `tool_start`/`tool_end` events as collapsed/expanded chips with args + output previews, and cleans up on refresh.
**Depends on**: Phases 1 (typed SSE event contract + heartbeat + timeout), 4 (auth'd API client — EventSource can't attach Bearer headers, so `fetch` is mandatory)
**Parallel-eligible with**: Phase 5 (independent features)
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06
**Success Criteria** (what must be TRUE):
  1. A chat query streams tokens into the assistant bubble smoothly (no "full message dumped at once" behaviour) — DevTools EventStream tab shows discrete `event: token` frames arriving, not a single buffered response (CHAT-01, CHAT-02)
  2. When the agent calls `search_jobs`, a collapsed chip appears in the transcript showing "calling search_jobs" + a JSON preview of args; when the tool returns, the chip expands with an output preview (truncated at ~200 chars with an "expand" affordance) (CHAT-03, CHAT-04)
  3. The `final` event marks the assistant bubble complete and re-enables the composer; attempting to submit during streaming is blocked (CHAT-05)
  4. Refreshing the page clears the transcript entirely — no history reloaded, no localStorage residue (CHAT-06)
  5. A screen recording of one chat turn (question → tool_start chip → tool_end chip → streamed synthesis → final) renders in <30 seconds and is demoable as-is
**Cost delta**: €0/mo (runtime only; per-query OpenAI cost charged to Adrian's key)
**Plans**: TBD
**UI hint**: yes

### Phase 7: Profile & Resume Upload
**Goal**: Phase 7 ships the personal-data loop when Adrian can upload a PDF or DOCX resume, see an Instructor-extracted skill diff vs his current profile in a reviewable panel, and tick/edit/save confirmed skills back to `user_profile` — with the full extract→review→save trace visible in Langfuse.
**Depends on**: Phases 1 (`UserProfile` DB model + Langfuse backend wiring), 4 (auth'd shell for the upload UI)
**Parallel-eligible with**: Phases 5, 6 (independent feature)
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04, PROF-05, PROF-06
**Success Criteria** (what must be TRUE):
  1. `data/profile.json` is no longer the read path for matching — `load_profile(session, user_id)` hits the `user_profile` table, and Adrian's existing profile data is the seeded row (PROF-01)
  2. Uploading a 1.5 MB resume PDF via the UI (or `multipart/form-data` curl against `POST /profile/upload`) succeeds; uploading a >2 MB file is rejected with a 413 before the body is fully read; DOCX is accepted alongside PDF (PROF-02)
  3. The upload response shows a reviewable diff — extracted skills split into `added` / `removed` / `unchanged` buckets — and the UI renders this as tick/untick chips with inline edit for skill names (PROF-03, PROF-04, PROF-05)
  4. Ticking a subset of extracted skills and hitting "save" PATCHes the `user_profile` row; the next CV-vs-market dashboard load reflects the new skills (PROF-06)
  5. Langfuse dashboard shows a single trace per upload spanning: text extraction → Instructor call → diff computation → (on save) PATCH — so the full pipeline is auditable in one place (PROF-06)
**Cost delta**: ~€0.005 per upload (GPT-4o-mini extraction) — dozens per month at most
**Plans**: TBD
**UI hint**: yes

### Phase 8: Eval & Documentation
**Goal**: Phase 8 ships the MLOps close-out and the portfolio artefact when RAGAS 0.4.3 runs on every PR that changes backend code, fails the build on metric regression, Langfuse is capturing production traces, and the README + ARCHITECTURE.md document the deployed stack so a reader can understand (and reproduce) the project without the `.planning/` tree.
**Depends on**: All prior phases (needs the deployed stack to trace; needs the agent + dashboard endpoints stable to baseline)
**Parallel-eligible with**: Nothing (terminal phase)
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07, DOCS-01, DOCS-02, DOCS-03
**Success Criteria** (what must be TRUE):
  1. RAGAS is pinned to `>=0.4,<0.5` in `pyproject.toml` dev deps and all import-sites are updated for the 0.3 → 0.4 breaking API (`convert_to_ragas_messages`, new metric class locations); the existing RAGAS code does not import anything that existed only in 0.2 (EVAL-01)
  2. `tests/eval/dataset.json` contains ~20 curated queries covering search / match / gaps flows; `python tests/eval/run_eval.py` against a live dev ACA instance produces per-metric scores for Faithfulness, Answer Relevancy, Context Precision, Context Recall, ToolCallF1, AgentGoalAccuracy, TopicAdherence (EVAL-02, EVAL-03, EVAL-04)
  3. `tests/eval/baseline.json` is committed with per-metric thresholds (wider for LLM-as-judge metrics to absorb non-determinism); the CI job fails on a single PR if any metric drops below its threshold — demonstrated by intentionally regressing retrieval then reverting (EVAL-05, EVAL-06)
  4. Langfuse keys flow from Key Vault → Container App env → `src/job_rag/observability.py`; a production chat turn shows a corresponding trace in the Langfuse dashboard within 30 seconds (EVAL-07)
  5. The README "Web app" section links to the deployed URL, shows 2-3 screenshots (dashboard + chat), includes an updated architecture diagram covering the Azure topology (SPA → SWA → ACA → Postgres + Entra + KV), and the SSE streaming contract (event schema, `fetch`+`ReadableStream` pattern, heartbeat semantics, timeout behaviour) is documented (DOCS-01, DOCS-02, DOCS-03)
**Cost delta**: ~€0.02 per PR eval run (~240 GPT-4o-mini calls per run); negligible at expected PR cadence
**Plans**: TBD

## Phase Ordering Notes

- **Parallelization**: Phase 2 can overlap Phase 1 (different surfaces); Phase 3 can overlap Phase 2 once Phase 1 has landed Alembic. Phases 5, 6, 7 can all run in parallel after Phase 4 completes.
- **Hard gate**: Phase 4 is the only single-threaded gate — it blocks Phases 5, 6, 7. Getting through it fast unlocks maximum parallelism.
- **EVAL-01 (RAGAS 0.2→0.4.3 upgrade)**: The library bump must land as the FIRST action of Phase 8, before any EVAL-02..07 code is written. Writing the harness against 0.2 then upgrading would waste a full plan's worth of work. This is enforced at the plan level.
- **DEPL-12 (two-pass CORS deploy)**: Folded into Phase 3 as a documented bootstrap step. Call-out preserved in the phase success criteria.
- **DOCS pattern**: All DOCS requirements ride in Phase 8's final doc pass — not sprinkled across feature phases. This keeps the docs coherent, single-pass, and authored against the actually-shipped system rather than in-flight guesses.

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Prep | 6/6 | ✓ Complete | 2026-04-27 |
| 2. Corpus Cleanup | 4/4 | Complete   | 2026-04-28 |
| 3. Infrastructure & CI/CD | 0/8 | Not started | - |
| 4. Frontend Shell + Auth | 0/? | Not started | - |
| 5. Dashboard | 0/? | Not started | - |
| 6. Chat | 0/? | Not started | - |
| 7. Profile & Resume Upload | 0/? | Not started | - |
| 8. Eval & Documentation | 0/? | Not started | - |

---
*Roadmap created: 2026-04-23*
*Granularity: standard*
*Coverage: 67/67 v1 requirements mapped*
