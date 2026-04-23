# Project Research Summary

**Project:** job-rag web app milestone
**Domain:** Personal job-market intelligence SPA + streaming AI chat on existing FastAPI / LangGraph / pgvector backend, Azure free tier
**Researched:** 2026-04-23
**Confidence:** HIGH (all four domains verified against primary sources)

---

## Headline Findings (skim here first)

- **Use Entra External ID, not B2C and not a workforce tenant.** Azure AD B2C hit end-of-sale on 2025-05-01. Wrong tenant type forces a rewrite before v2.
- **RAGAS is at 0.4.3, not 0.2.** Three breaking API changes separate the lines. Bump the dev-dep to >=0.4,<0.5 as a dedicated PR before eval work begins.
- **GHCR is free; ACR Basic is ~5 EUR/mo.** Use GitHub Container Registry for guaranteed-free egress from GitHub Actions.
- **Reject PyMuPDF (fitz) on AGPL grounds.** A network-deployed derivative must be open-sourced under AGPL. Use pypdf (BSD-3-Clause) instead.
- **Tool-call chips are the number-one portfolio signal.** Every competitor hides agent scaffolding. tool_start/tool_end chips are unique, screen-recordable in 30 seconds, and the single feature interviewers will ask about.

---

## Key Findings

### Recommended Stack

The frontend is Vite 8 + React 19.2 with Tailwind v4 (@tailwindcss/vite plugin, not PostCSS), shadcn/ui stable CLI (no canary since March 2026), and @tanstack/react-query for server state -- not Redux/Zustand. Authentication uses @azure/msal-react 5.3.1 with auth-code + PKCE. On the backend, fastapi-azure-auth (intility, v5+) handles JWT validation against the Entra External ID JWKS endpoint. Resume parsing uses pypdf 6.10 (BSD-3-Clause) and python-docx 1.2 (MIT).

Infrastructure is Terraform >= 1.9 with azurerm ~> 4.69 and azuread ~> 3.x as **separate providers** -- a workforce-tenant provider cannot manage the CIAM External ID tenant. Images go to GHCR. The eval harness is RAGAS 0.4.3 with its convert_to_ragas_messages LangGraph integration.

**Core technologies (new additions only; existing backend stack is frozen):**

| Technology | Version | Purpose |
|------------|---------|---------|
| Vite | 8.0.x | SPA bundler (Node 20.19+/22.12+ required) |
| React | 19.2.x | UI library |
| Tailwind CSS | 4.2.x | Utility CSS via @tailwindcss/vite |
| shadcn/ui | CLI @latest | Component primitives, stable for Vite+TW4+React19 |
| @azure/msal-react | 5.3.1 | Auth hooks; peer requires @azure/msal-browser ^5.8 |
| @tanstack/react-query | 5.x | Dashboard + chat server state |
| fastapi-azure-auth | 5.x | FastAPI JWT validation for Entra External ID |
| pypdf | 6.10.x | PDF text extraction (BSD-3-Clause, pure Python) |
| python-docx | 1.2.x | DOCX extraction (MIT) |
| ragas | 0.4.3 | RAG + agent evaluation (bump from 0.2) |
| azurerm provider | ~> 4.69 | Azure resource primitives |
| azuread provider | ~> 3.x | Entra app registrations (separate provider, separate tenant) |
| GHCR | free | Container registry (replaces ACR Basic, saves ~60 EUR/yr) |

**Do not use:** Azure AD B2C, PyMuPDF/fitz (AGPL), npx shadcn@canary, EventSource for authenticated SSE, azurerm v3, MSAL 1.x, Next.js, Tailwind v3.

### Feature Scope Confirmed

All Active requirements items are P1. Source-line evidence in skill extraction and URL-synced filter state are P2 (ship in v1 if time allows).

**Table stakes -- missing any makes the product look half-built:**
- Streaming chat with incremental token render
- Top-N skills widget with must-have / nice-to-have split
- Salary bands p25/p50/p75 with N-postings-had-salary footnote
- Country / seniority / remote filter bar
- CV-vs-market aggregate match score
- Resume upload (PDF + DOCX) with reviewable extracted-skills panel (tick/untick/edit)
- Login wall (Entra ID)
- Loading skeletons and graceful SSE error rendering

**Differentiators -- interview landing features:**
- **Tool-call chips (tool_start / tool_end)** -- VERY HIGH signal. Every competitor hides agent scaffolding. Collapsed chips expandable to show args + result.
- **CV-vs-corpus score against all filtered postings** (not a single JD like Teal/Jobscan) -- intellectually honest.
- **SkillCategory enum + structured Location as a pair** -- single PROMPT_VERSION bump, one-time re-extraction. Soft skills hidden by default; otherwise LLM-extracted soft-skill noise tops the dashboard.
- **Reviewable resume extraction** -- consumer version of what enterprise parsers (Affinda) give recruiters; the most direct inspectable AI demo.

**Defer to v2+:** interactive drill-down dashboard, conversation history, multi-user sign-up, ESCO/O*NET taxonomy, automated ingestion, browser extension.

### Architecture Spine

Seven concrete topology decisions that cannot be reversed without significant rework:

1. **Direct SPA to ACA with CORS allowlist** (not SWA linked backend). SWA Standard plan costs ~9 EUR/mo. allow_credentials=False; OPTIONS in allowed methods.

2. **Two-pass Terraform apply** breaks the SWA-URL to CORS-allowlist cycle. Pass 1 creates the SWA; Pass 2 sets its hostname on the Container App. Document as the bootstrap sequence.

3. **Envoy 240s request timeout + 15s SSE heartbeats.** ACA Consumption ingress cap is hard and non-configurable. App-level timeout stays under 180s (60s Active requirement). Heartbeats in stream.py.

4. **fetch + ReadableStream instead of EventSource** for authenticated SSE. EventSource cannot send Authorization headers; JWT in query param leaks to server logs and browser history.

5. **fastapi-azure-auth for JWT validation.** Replaces require_api_key; JOB_RAG_API_KEY becomes dev-only behind AUTH_MODE=dev-bearer. Single-user guard checks the JWT oid claim.

6. **Alembic adoption in the same PR as the user_id + career_id migration.** All service function signatures gain user_id: UUID at once. user_id carries NO DEFAULT in the DB; inject from JWT.

7. **IngestionSource Protocol** (not base class). MarkdownFileSource is the v1 implementation. Must land before the resume-upload feature.

**Component responsibilities:**

| Component | Owns |
|-----------|------|
| Vite+React SPA (SWA) | UI state, MSAL token cache, SSE decoding, filter bars |
| FastAPI container (ACA) | JWT validation, CORS, SSE, reranker lifespan, route handlers |
| LangGraph agent | Tool orchestration (search_jobs, match_profile, analyze_gaps) |
| Postgres Flex B1ms + pgvector | Durable state: postings, chunks, user_profile, embeddings |
| Entra External ID tenant | JWT issuance, SPA + API app registrations |
| GitHub Actions (OIDC) | Build, test, deploy -- no long-lived secrets |
| Azure Key Vault | OPENAI_API_KEY, DB password, Langfuse keys |

### Top Pitfalls the Roadmap Must Address

1. **Wrong Entra tenant type** (workforce instead of CIAM) -- auth rewrite before v2. MSAL authority: https://<tenant>.ciamlogin.com/. **Phase: infra.**
2. **SPA app registration set to Web platform, not SPA** -- silent refresh fails after ~1 hour. Use single_page_application { redirect_uris } in Terraform. **Phase: infra.**
3. **MSAL initialization race** -- protected route flashes login on hard refresh. Call initialize() and handleRedirectPromise() in main.tsx BEFORE createRoot().render(). **Phase: frontend-shell.**
4. **SSE gzip buffering** -- full response arrives at once on Azure. Return X-Accel-Buffering: no and Content-Encoding: identity. Never add GZipMiddleware. **Phase: backend-prep.**
5. **pgvector not in the right database** -- azure.extensions is an allowlist, not an install. CREATE EXTENSION vector must be an Alembic migration against the jobrag database. **Phase: backend-prep + terraform-iac.**
6. **PostgreSQL B1ms connection exhaustion** -- ~35 usable connections. pool_size=3, max_overflow=2; NullPool for scripts. **Phase: backend-prep.**
7. **OIDC subject claim mismatch** (AADSTS70021) -- one federated credential per trigger shape. **Phase: ci-cd.**
8. **user_id DEFAULT collision** -- NO DEFAULT in DB column; inject from JWT application-side. **Phase: backend-prep.**

---

## Implications for Roadmap

### Recommended Phase Ordering

**Phase 1 -- Backend Prep** (pure refactor; no new surfaces)
Goal: close all seven codebase blockers so any frontend round-trip is meaningful.
Delivers: CORS middleware, Pydantic SSE event schema + heartbeats + 60s timeout, reranker preloaded in lifespan + asyncio.to_thread, Alembic with user_id + career_id migration (NO DEFAULT), user_profile table replacing data/profile.json, IngestionSource Protocol, pool_size=3 max_overflow=2.

**Phase 2 -- Corpus Cleanup** (one-time re-extraction; can overlap Phase 1)
Goal: pay the re-extraction cost once for both SkillCategory and structured Location.
Delivers: SkillCategory enum on JobRequirement, structured Location schema, bumped PROMPT_VERSION, re-extracted corpus (~108 postings).

**Phase 3 -- Infrastructure** (Terraform + Entra provisioning)
Goal: provision all Azure resources so MSAL can complete a real round-trip.
Delivers: Terraform workspace layout (dev + prod), bootstrap state backend, Entra External ID tenant + SPA + API app registrations, full Azure stack (RG + Log Analytics + Key Vault + Postgres Flex B1ms + pgvector + ACA env + Container App + SWA), Adrian user row seeded with real entra_oid, GHCR as registry.

**Phase 4 -- CI/CD** (GitHub Actions + OIDC; can overlap Phase 3)
Goal: automate deploy so frontend work can iterate without manual pushes.
Delivers: Two OIDC-federated service principals, workflow-tf.yml + workflow-api.yml + workflow-spa.yml, SWA deployment token as the only non-OIDC secret, budget alerts.

**Phase 5 -- Frontend Shell + Auth**
Goal: wire auth end-to-end so every subsequent feature has a real user context.
Delivers: Vite 8 + React 19.2 + TypeScript, Tailwind v4, shadcn/ui, Linear-dense theme, top-nav, MsalProvider initialized before createRoot, InteractionStatus gating, sessionStorage token cache, fastapi-azure-auth on FastAPI side, only_seeded_user dependency, one protected round-trip verified.

**Phase 6 -- Dashboard**
Goal: deliver the first demoable, shareable output.
Delivers: Three analytical SQL endpoints (top-N skills; salary p25/p50/p75; CV-vs-market match score), shared filter bar with URL state sync, show-more drill, loading skeletons, empty states, soft skills hidden by default.
Requires: Phases 1 + 2 + 5.

**Phase 7 -- Chat**
Goal: ship the number-one portfolio-signal feature alongside basic streaming.
Delivers: fetch + ReadableStream SSE reader, token-by-token rendering, tool_start chips (collapsed), tool_end chips (expanded), distinct connecting/warming/streaming/thinking states, event:error and event:final handled. Single-turn, clear-on-refresh.

**Phase 8 -- Profile + Resume Upload**
Goal: complete the personal-data loop so CV-vs-market scores stay current.
Delivers: Resume upload endpoint (pypdf 6.10 + python-docx 1.2), Instructor extraction, reviewable panel, 500-char min threshold, 5 MB size cap, 20-skill max validator.

**Phase 9 -- MLOps / Eval Loop** (terminal)
Goal: close the MLOps story with a CI gate that catches regressions before merge.
Delivers: ragas==0.4.3 pinned, ~20-query eval set, eval/baselines/ragas_v0.4.3.json committed, CI gate with 5pp threshold and wider band for LLM-as-judge variance, Langfuse wired.

### Phase Ordering Rationale

- Phases 1 and 2 are parallel (no shared dependencies).
- Phase 3 must complete before Phase 5 (MSAL needs real tenant/client IDs).
- Phase 4 can overlap Phase 3 (federated credentials are in the same Terraform apply).
- Phases 6 and 7 can run in parallel once Phase 5 is done.
- Phase 8 is gated on Phases 1 and 5.
- Phase 9 is terminal.

### Research Flags

**Standard patterns -- no additional research needed:**
- Phase 1 (Backend Prep): all changes in the existing codebase; patterns in ARCHITECTURE.md.
- Phase 2 (Corpus Cleanup): Instructor pattern already in use.
- Phase 4 (CI/CD): OIDC federation is well-documented.
- Phase 6 (Dashboard): analytical SQL + React Query is well-documented.
- Phase 7 (Chat): SSE + ReadableStream is stable (MDN).

**May benefit from deeper research during planning:**
- Phase 3 (Infra): azuread Terraform resource for creating an External ID tenant may require azapi or a manual portal step. Confirm before starting.
- Phase 9 (Eval): RAGAS 0.4 convert_to_ragas_messages needs a smoke test against actual LangGraph output before the CI harness is finalized.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified on official docs and PyPI. All key surprises primary-source verified. |
| Features | HIGH | Competitor landscape well-researched. Portfolio-signal calibration against industry patterns. |
| Architecture | HIGH | Azure official docs confirm all topology decisions. |
| Pitfalls | HIGH / MEDIUM (2) | Entra/ACA/MSAL/OIDC/SSE pitfalls primary-source verified. RAGAS threshold and B1ms connection numbers are MEDIUM. |

**Overall confidence: HIGH**

### Gaps to Address During Implementation

- **B1ms connection budget**: verify SHOW max_connections on the provisioned server; adjust pool sizing if headroom differs from ~15.
- **RAGAS 0.4 harness smoke test**: smoke-test convert_to_ragas_messages against a live LangGraph run; re-baseline required after the 0.2 to 0.4 bump.
- **Entra External ID Terraform resource**: confirm which resource creates an External (CIAM) tenant; document manual bootstrap if not in azuread ~> 3.x.
- **SWA OIDC deploy status**: confirm GA vs. preview at Phase 4 planning time; use the deployment token if still preview.

---

## Aggregated Open Questions by Phase

| Phase | Question |
|-------|----------|
| Phase 1 | Should terminationGracePeriodSeconds=120 live in the Terraform Container App resource or in the ACA YAML config? |
| Phase 2 | Does the PROMPT_VERSION bump require invalidating existing embeddings, or only re-extraction of text fields? |
| Phase 3 | Which Terraform resource type creates an Entra External ID tenant? Document manual bootstrap if none exists. |
| Phase 3 | Is the SWA deployment token the only non-OIDC secret? Document explicitly in infra README. |
| Phase 5 | Should the Vite dev proxy point to local Docker Compose API or to the dev ACA deployment? |
| Phase 7 | Is event:heartbeat silently consumed, or should it drive a visible liveness indicator on the assistant bubble? |
| Phase 8 | Should source-line evidence be attempted in v1 or deferred to v1.x? FEATURES.md marks it P2. |
| Phase 9 | Eval cost per PR is ~0.02 EUR (~240 GPT-4o-mini calls). At what PR frequency does this become material? |

---

## Sources (aggregated)

### Primary -- HIGH confidence

- Vite Releases (vite.dev/releases) -- v8.0.9 current stable
- Tailwind CSS v4 Vite integration (tailwindcss.com/docs/installation/using-vite)
- shadcn/ui Tailwind v4 (ui.shadcn.com/docs/tailwind-v4)
- @azure/msal-react CHANGELOG (github.com/AzureAD/microsoft-authentication-library-for-js)
- Entra External ID FAQ (learn.microsoft.com/en-us/entra/external-id/customers/faq-customers)
- Azure Container Apps pricing (azure.microsoft.com/en-us/pricing/details/container-apps/)
- Azure Static Web Apps plans (learn.microsoft.com/en-us/azure/static-web-apps/plans)
- terraform-provider-azurerm releases (github.com/hashicorp/terraform-provider-azurerm/releases)
- RAGAS releases (github.com/explodinggradients/ragas/releases)
- pypdf on PyPI (pypi.org/project/pypdf/) -- 6.10.2, BSD-3-Clause
- PyMuPDF AGPL discussion (github.com/pymupdf/PyMuPDF/discussions/971)
- python-docx on PyPI (pypi.org/project/python-docx/) -- 1.2.0, MIT
- ACA ingress overview (learn.microsoft.com/en-us/azure/container-apps/ingress-overview)
- fastapi-azure-auth GitHub (github.com/intility/fastapi-azure-auth)
- Authenticate to Azure from GitHub Actions by OIDC (learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- MSAL race condition issue #6893 (github.com/AzureAD/microsoft-authentication-library-for-js/issues/6893)
- ACA graceful termination (azureossd.github.io/2024/05/27/Graceful-termination-on-Container-Apps/)
- Postgres Flexible Server limits (learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-limits)
- RAGAS v0.4 migration guide (docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/)
- SSE -- MDN (developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

### Secondary -- MEDIUM confidence

- shadcn/ui March 2026 Update -- CLI v4 (medium.com/@nakranirakesh)
- Azure Federated Credentials claims matching expressions (josh-ops.com)
- PDF extractor benchmarks 2026 (unstract.com/blog/evaluating-python-pdf-to-text-libraries/)
- Evaluating non-deterministic RAG results (medium.com/@parserdigital)

---

*Research completed: 2026-04-23*
*Ready for roadmap: yes*
