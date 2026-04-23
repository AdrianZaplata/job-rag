# Pitfalls Research

**Domain:** Vite+React SPA + FastAPI + LangGraph + Entra External ID + Azure Container Apps + Terraform
**Researched:** 2026-04-23
**Confidence:** HIGH for Entra/ACA/SSE/MSAL/OIDC (primary-source verified); MEDIUM for RAGAS-0.4 semantics and Flex-Server B1ms live numbers; LOW on phase-assignment of a few forward-looking items that depend on exact roadmap shape

**Scope note:** This document covers the NEW pitfalls introduced by this milestone's additions only. Existing backend concerns are already tracked in `.planning/codebase/CONCERNS.md` and in the Active requirements; they are not re-flagged here.

## Critical Pitfalls

### Pitfall 1: Wrong Entra tenant type — workforce tenant used for external customers

**What goes wrong:**
Developer creates a single app registration in their existing workforce tenant (or the personal Azure subscription's default directory) and wires MSAL against `login.microsoftonline.com/<tenant>`. Works for Adrian-as-owner but will never cleanly onboard a second user without a schema and auth rewrite.

**Why it happens:**
Every first-page tutorial assumes a workforce tenant. The "External ID" tenant type is a separate resource, uses a separate authority host (`<tenant>.ciamlogin.com`), and has different user-flow semantics. Azure AD B2C — which most older tutorials cover — stopped accepting new customers on 2025-05-01 and is not the same product.

**How to avoid:**
- Provision a dedicated **External tenant** (not workforce) via Terraform (`azurerm_*` + `azuread_*` providers targeting the external-tenant subscription) before any app registrations.
- MSAL authority MUST be `https://<tenant-name>.ciamlogin.com/<tenant-id>/v2.0` — not `login.microsoftonline.com`.
- Issuer-validation on the FastAPI side must accept the ciamlogin issuer; copy it from `/.well-known/openid-configuration` rather than hard-coding.
- Register TWO apps: the SPA (public client, no secret) and the API (exposes `api://<api-client-id>/access_as_user` scope).

**Warning signs:**
- JWT `iss` claim starts with `https://login.microsoftonline.com/` instead of `https://<tenant>.ciamlogin.com/`.
- `AADSTS50011` "redirect URI mismatch" even though the URI looks right — usually means you're hitting the wrong tenant.
- User self-sign-up option is missing from the portal blade (external tenants expose it; workforce tenants don't).

**Phase to address:** auth-prep (before frontend shell integrates MSAL).
**Confidence:** HIGH.

---

### Pitfall 2: SPA redirect URI registered as "Web" instead of "SPA" — silent-refresh fails

**What goes wrong:**
App registration created with the default `Web` platform. MSAL login works (because the initial redirect is fine), but `acquireTokenSilent` returns `invalid_grant` or quietly 404s. Users appear logged-in but every API call fails after the first hour.

**Why it happens:**
Web platforms expect a client secret and the auth-code flow without PKCE. SPAs must use the auth-code flow **with PKCE** and CORS-enabled token endpoints. The portal shows a green checkmark "Your Redirect URI is eligible for the Authorization Code Flow with PKCE" only when the platform is set to SPA.

**How to avoid:**
- In Terraform: `azuread_application.spa.public_client.redirect_uris` is the wrong block; use `single_page_application { redirect_uris = [...] }`.
- Verify post-apply in the portal: Authentication blade should show redirect URIs under the "Single-page application" heading with the green PKCE checkmark.
- MSAL config: use `@azure/msal-browser` v3+ with `PublicClientApplication`, never `ConfidentialClientApplication`.

**Warning signs:**
- `AADSTS9002326` "Cross-origin token redemption is permitted only for the 'Single-Page Application' client-type".
- First login works but token refresh fails after ~1 hour.
- Network tab shows `/oauth2/v2.0/token` blocked by CORS.

**Phase to address:** auth-prep / terraform-iac (the Terraform block for the app registration).
**Confidence:** HIGH.

---

### Pitfall 3: Azure Container Apps default 240s request cap kills long SSE streams

**What goes wrong:**
Envoy ingress in Container Apps has a hard default request timeout of **240 seconds**. Any SSE connection still open at 4:01 is cancelled mid-stream. For short `/agent/stream` turns this rarely fires, but a retrieval + rerank + multi-tool LangGraph run over a slow OpenAI response can breach it.

**Why it happens:**
Container Apps' "Standard" ingress tier was tuned for request/response, not streaming. The timeout applies to the whole request duration, not idle time. Documentation on this is scattered: the limit is mentioned in GitHub issue #597 and a community post about Premium Ingress, not in the main pricing/limits page.

**How to avoid:**
- Enforce an **application-level timeout shorter than 240s** (the 60s `asyncio.wait_for` in the Active requirements is good — keep it ≤ 180s maximum if you ever extend it).
- Emit a final `event: final` with an "aborted" reason before the timeout fires, so the client gets a clean EOF rather than a connection error.
- If longer streams are ever needed: upgrade the environment to **Premium Ingress** and set `az containerapp env update --request-idle-timeout` (max 1 hour) — but this costs extra and is not in the free tier.
- Send SSE keep-alive comments (`: ping\n\n`) every 15–20s during idle LLM response segments so intermediate proxies don't treat the stream as dead.

**Warning signs:**
- Connections drop at ~240s with no server-side log (Envoy cancels silently from the app's perspective).
- Client `EventSource` fires `onerror` and auto-reconnects roughly every 4 minutes under load.
- Azure Log Analytics `ContainerAppSystemLogs_CL` shows `request_timeout` entries.

**Phase to address:** backend-prep (timeout + keep-alive) and deploy (ingress config).
**Confidence:** HIGH.

---

### Pitfall 4: Scale-to-zero + SSE = client sees cold-start latency as a hang on the first chat

**What goes wrong:**
Min-replicas is 0 (required for free tier). First chat of the day: Container Apps pulls the image (~1.5 GB with torch), boots uvicorn, loads the reranker (~80 MB cross-encoder) into RAM, runs DB migrations, connects to pgvector. Observed cold-starts are 5–10s for the platform alone; with PyTorch + reranker preload, expect **15–25s** before the first SSE byte flows. The browser EventSource has no visual feedback during this window.

**Why it happens:**
ACA cold-start combines image pull + container start + user app init. The reranker preload (already in the Active requirements via FastAPI lifespan) is correct but pushes the critical path further. On a B1ms-scale environment (1 vCPU / 2 GB) the HuggingFace tokenizer + torch import alone is 2–4 seconds.

**How to avoid:**
- The frontend must show a dedicated "warming up" state on first chat — NOT a spinner that looks identical to "thinking". Distinguish `connecting` → `streaming` visually.
- Keep the image lean: do not bundle dev dependencies; consider splitting the reranker into a separate image or lazy-loading it on non-chat routes.
- Optionally, in production, set `minReplicas = 1` on a low-cost workload profile during business hours via a scheduled job (separate cost-vs-UX decision).
- Pre-warm via a keepalive ping from GitHub Actions cron or Azure Monitor availability test during expected-use windows.

**Warning signs:**
- First `/agent/stream` of the day shows no bytes for >10 seconds; subsequent streams are instant.
- `ContainerAppSystemLogs_CL` shows a `ReplicaReady` event matching the first chat timestamp.
- Client-side, `EventSource.readyState` stays at `0 (CONNECTING)` for 10+ seconds.

**Phase to address:** backend-prep (preload) and frontend (UX) and deploy (min-replica decision).
**Confidence:** HIGH.

---

### Pitfall 5: Azure Container Apps SIGTERM during revision swap drops in-flight SSE connections

**What goes wrong:**
Deploy via `terraform apply` creates a new revision. The old revision is deactivated; ACA sends SIGTERM to the old pod. Default `terminationGracePeriodSeconds` is **30 seconds**. Any chat stream still running past 30s is killed with SIGKILL mid-message. Client sees a half-formed response.

**Why it happens:**
`terminationGracePeriodSeconds` is optional and defaults to 30s if unset. For streaming workloads this is often too short. Additionally, uvicorn and FastAPI do not drain in-flight SSE by default — on SIGTERM they stop accepting new requests but the existing generator is killed unless the lifespan/shutdown hook awaits them.

**How to avoid:**
- Set `template.terminationGracePeriodSeconds = 120` in the Container App Terraform resource (allows the 60s agent timeout + buffer).
- Implement shutdown draining in FastAPI: on lifespan shutdown, track active SSE generators (a set of tasks) and `await asyncio.gather(*tasks, return_exceptions=True)` before returning. Add a `Retry-After: 2` header hint if you emit an "aborted" event.
- In the client, handle `EventSource.onerror` by showing "Reconnecting…" and re-issuing the last user turn automatically (this is a single-turn app, so context is trivial to preserve).
- Prefer zero-downtime deploys: use `traffic { latest_revision = true, weight = 100 }` with a warmup period so the new revision is fully ready before the old one drains.

**Warning signs:**
- Chat responses truncate mid-sentence exactly when a deploy runs.
- `kubectl`-style events in `ContainerAppSystemLogs_CL`: `Killing` before `Stopped`.
- Users report "it worked fine, then suddenly it stopped responding" shortly after a push.

**Phase to address:** backend-prep (draining) and terraform-iac (grace period).
**Confidence:** HIGH.

---

### Pitfall 6: EventSource + gzip compression = buffered garbage, no incremental tokens

**What goes wrong:**
Some reverse proxy or middleware (sometimes FastAPI's `GZipMiddleware`, sometimes the ingress, sometimes a corporate network's TLS-inspection proxy) applies gzip to the SSE response. Browsers do not stream gzipped responses event-by-event — they buffer. The user sees no tokens stream; the entire response arrives at once when the connection closes.

**Why it happens:**
SSE is HTTP chunked transfer encoding; gzip is applied over chunks, and some decoders wait for a full decompressible window. FastAPI's `StreamingResponse` is fine, but any wrapping middleware that sets `Content-Encoding: gzip` breaks it.

**How to avoid:**
- Explicitly disable compression for the SSE route: return `Content-Encoding: identity` or add `X-Accel-Buffering: no` header.
- Do NOT add `GZipMiddleware` to the FastAPI app, OR configure it to skip `/agent/stream`. Azure Container Apps' Envoy does not gzip by default, but this is still worth a defensive header.
- Test through the deployed URL (not just localhost) — compression behaviour is where dev and prod diverge most.
- Verify client-side: in DevTools, the response should have `Content-Type: text/event-stream` and NO `Content-Encoding` header.

**Warning signs:**
- Full response appears at once after a long pause.
- `DevTools → Network → EventStream` tab is empty but `Response` tab has the whole payload.
- Works on localhost, fails on Azure.

**Phase to address:** backend-prep (headers) and deploy (smoke test).
**Confidence:** HIGH.

---

### Pitfall 7: GitHub Actions OIDC subject claim mismatch — `AADSTS70021` / `AADSTS700213`

**What goes wrong:**
Federated credential configured for `repo:AdrianZaplata/job-rag:ref:refs/heads/master`, but the workflow runs on a `workflow_dispatch` trigger, or uses an environment, or a tag push. Subject claim from GitHub is `repo:AdrianZaplata/job-rag:environment:production` or `repo:AdrianZaplata/job-rag:ref:refs/tags/v1.0` — doesn't match. Deployment fails with `AADSTS70021: No matching federated identity record found for presented assertion`.

**Why it happens:**
Subject claims are exact-string-matched (case-sensitive). Wildcards are not supported by traditional federated credentials — only by the newer "Claims matching expression" feature (still preview in early 2026). Four common subject formats for GitHub Actions:
- `repo:owner/repo:ref:refs/heads/<branch>` — branch push
- `repo:owner/repo:ref:refs/tags/<tag>` — tag push
- `repo:owner/repo:pull_request` — PR (no branch name!)
- `repo:owner/repo:environment:<env>` — environment protection

**How to avoid:**
- Decide the trigger shape BEFORE configuring the credential. For this project: push to master + manual dispatch from protected environment `production`.
- Register at least two credentials: one for `ref:refs/heads/master`, one for `environment:production`. Never try one credential for both.
- Use `environment:` scoped secrets in GitHub — not repository secrets — so a merged rogue PR can't steal the OIDC token.
- Minimum permission: `Contributor` on the resource group, NOT subscription. Or better, a custom role with only `containerApps/write`, `containerApps/revisions/*/write`.
- Add `AADSTS70021` to a known-errors.md runbook with the exact subject strings.

**Warning signs:**
- First deploy after a workflow change fails; log shows the attempted subject string (copy it into the federated credential).
- `AADSTS700213` specifically indicates subject claim case mismatch — GitHub repo names ARE lowercase in the claim even if the display is mixed-case.

**Phase to address:** deploy / ci-cd (before first production deploy).
**Confidence:** HIGH.

---

### Pitfall 8: Azure DB for PostgreSQL Flexible Server B1ms connection exhaustion

**What goes wrong:**
B1ms tier has `max_connections = 50`, of which **~15 are reserved** by Azure for replication and monitoring. Application effectively has ~35 connections. SQLAlchemy async default pool is 5 + 10 overflow per worker. Two workers + a background eval job + a `pg_dump` backup = instant exhaustion. Error: `FATAL: sorry, too many clients already`.

**Why it happens:**
B1ms is a burstable / hobby tier and intentionally cheap. PgBouncer built-in pooling is **not available** on Burstable tiers. Most SQLAlchemy tutorials assume 100+ connections.

**How to avoid:**
- Cap SQLAlchemy pool: `pool_size=3, max_overflow=2` per worker. With `minReplicas=0, maxReplicas=2`, worst-case is 2 * 5 = 10 connections + eval job + migrations.
- Use NullPool for short-lived scripts (Alembic migrations, CLI, eval job) — they shouldn't hold pooled connections.
- Run external PgBouncer as a sidecar if scaling beyond one replica — do not rely on the built-in one that the docs mention for General Purpose tiers.
- Document the connection budget in `.env.example` and in the deploy phase task.

**Warning signs:**
- `sqlalchemy.exc.OperationalError: FATAL: sorry, too many clients already` in logs, usually during deploys (new replica + old replica overlap).
- pg metric `active_connections` graph shows spikes to ~35 followed by errors.
- Dashboard loads slowly or fails when the eval job is running.

**Phase to address:** backend-prep (pool sizing) and deploy (capacity verification).
**Confidence:** MEDIUM (exact B1ms numbers verified; concrete pool sizes depend on eventual worker count).

---

### Pitfall 9: pgvector extension not enabled in the right database

**What goes wrong:**
Terraform creates the Flexible Server and lists `VECTOR` in `azurerm_postgresql_flexible_server_configuration.azure_extensions`. Application runs `CREATE EXTENSION vector` in `init_db()` against database `postgres` (the default). Operator later creates the real `jobrag` database — the extension is **per-database** and has to be re-enabled there. First vector query: `ERROR: type "vector" does not exist`.

**Why it happens:**
`azure.extensions` server parameter is a server-level **allowlist** — it makes extensions available but does not install them. `CREATE EXTENSION` is per-database. Cross-database extension installation is a common blind spot.

**How to avoid:**
- Terraform order: create server → set `azure.extensions = "VECTOR"` → create the target database → run `CREATE EXTENSION IF NOT EXISTS vector` AS part of Alembic migrations (not just `init_db()` on startup).
- Use Alembic migration version `0001_enable_pgvector.py` so the extension creation is version-controlled, not an implicit side-effect of app boot.
- Smoke test in CI: `SELECT vector_dims(ARRAY[1,2,3]::vector)` before any embedding calls.

**Warning signs:**
- App starts cleanly but first `/search` call returns `type "vector" does not exist`.
- `\dx` in psql against the target DB shows nothing; `\l+` shows multiple databases.

**Phase to address:** terraform-iac (allowlist) and backend-prep (Alembic migration).
**Confidence:** HIGH.

---

### Pitfall 10: Static Web Apps "linked API" misunderstanding — CORS problem re-emerges

**What goes wrong:**
Team chooses the SWA "Bring Your Own Backend" linked-API feature assuming it eliminates CORS. It does — but only while requests are proxied via `/api/*` on the SWA domain. Someone bypasses that for performance by calling the Container Apps URL directly from the SPA. CORS rejection immediately; the fix (adding ACA URL to FastAPI's CORS allowlist) then accidentally opens the API to the open internet.

**Why it happens:**
The linked-API model works by SWA acting as a reverse proxy. It strips the cross-origin problem because the browser sees the same origin. Dev and prod have different authority boundaries, and the mental model that "SWA is just CDN + auth" is incomplete.

**How to avoid:**
- Commit to the `/api/*` routing convention everywhere in the frontend. The API client base URL is `/api` in production, `http://localhost:8000` in dev. Never use the direct ACA hostname from the SPA.
- FastAPI CORS allowlist: dev origin (`http://localhost:5173`) and SWA production hostname only. Never `*`. Never the ACA hostname.
- Static Web Apps `staticwebapp.config.json` maps `/api/*` to the linked backend; put this in the repo, not just portal config.
- For the Vite dev server, configure a proxy (`vite.config.ts` → `server.proxy`) so the dev experience matches prod routing.

**Warning signs:**
- `Access-Control-Allow-Origin` errors in the browser after a deploy.
- Working dev chat, broken prod chat (or vice versa).
- The API is callable from `curl` with no Origin header but 403/CORS-blocked from the browser.

**Phase to address:** frontend-shell (API client config) and deploy (SWA config).
**Confidence:** HIGH.

---

### Pitfall 11: MSAL React + Vite initialization race — "user null" on first render

**What goes wrong:**
`MsalProvider` is rendered, but `useIsAuthenticated()` returns `false` on the very first render even for an already-logged-in user. The protected route redirects to login immediately, the redirect brings them back, and they see a flash of the login page every hard refresh. Worse: the API client tries to call `acquireTokenSilent` before MSAL finishes `handleRedirectPromise`, throwing `uninitialized_public_client_application`.

**Why it happens:**
Two race conditions are documented in MSAL issues #6785, #6893, and #7561:
1. `MsalProvider` runs `handleRedirectPromise` asynchronously; first render fires before it resolves.
2. MSAL v4's cache uses encrypted storage with async decryption; on slow devices (or CI), claims access beats decryption completion.
Vite's SPA-only model means there's no server-side hydration to mask the flicker.

**How to avoid:**
- Wrap protected routes in an `AuthenticationTemplate` (from `@azure/msal-react`) rather than a custom `if (!isAuthenticated) redirect()` — the template handles the initialization state correctly.
- Initialize MSAL EAGERLY before React renders: `await msalInstance.initialize()` and `await msalInstance.handleRedirectPromise()` in `main.tsx` before `ReactDOM.createRoot(...).render()`. Do NOT call these inside `useEffect`.
- Use `InteractionStatus` from `useMsal()` to gate UI: `if (inProgress !== InteractionStatus.None) return <Loading />`.
- Dedicated `redirect.html` page (not the main app shell) for the redirect URI, so re-rendering the whole app during callback is impossible.

**Warning signs:**
- Flash of login page after hard refresh while already logged in.
- `BrowserAuthError: uninitialized_public_client_application` in console.
- `BrowserAuthError: monitor_window_timeout` — iframe silent refresh timed out.

**Phase to address:** frontend-shell (MSAL integration).
**Confidence:** HIGH.

---

### Pitfall 12: Silent refresh via hidden iframe — blocked by third-party cookie policies

**What goes wrong:**
MSAL's default silent-token renewal uses a hidden iframe navigating to `<tenant>.ciamlogin.com`. Chrome's phased third-party cookie deprecation (rolling out through 2025–2026), Safari ITP (already active), Firefox ETP, and Brave all block third-party cookies by default. The iframe refresh silently fails; user gets logged out after ~1 hour without explanation.

**Why it happens:**
The `.ciamlogin.com` iframe is a different registrable domain from your SPA. Without SameSite=None cookies delivered cross-site, the iframe can't access the session. Refresh tokens in session storage work, but older tutorials still prefer the iframe pattern.

**How to avoid:**
- Configure MSAL with `cacheLocation: "sessionStorage"` (or `localStorage` — weigh security) AND enable the **refresh token flow** via `@azure/msal-browser` v3+: refresh tokens are stored in the SPA and do not need the iframe.
- Set `PublicClientApplication.options.cache.temporaryCacheLocation = "sessionStorage"` explicitly.
- Test in Safari and Chrome with third-party cookies blocked during development — not just default Chrome.
- Catch `BrowserAuthError: monitor_window_timeout` and `silent_sso_error` and fall back to `acquireTokenRedirect` with a "Please sign in again" message.

**Warning signs:**
- Users get logged out exactly every ~60 min matching the access-token lifetime.
- DevTools → Application → Frames shows a persistent iframe to `ciamlogin.com`.
- Safari users report it works briefly and then fails; Chrome users unaffected (differential browser behaviour = cookie policy issue).

**Phase to address:** frontend-shell (MSAL config).
**Confidence:** HIGH.

---

### Pitfall 13: Terraform state bootstrap chicken-and-egg for Entra tenant

**What goes wrong:**
`main.tf` declares an Azure blob-storage backend AND an Entra tenant + app registrations. First `terraform init` needs the backend storage account to exist; `terraform apply` wants to create the Entra tenant before the app registrations that depend on it. Manual bootstrapping is required but not documented; team member #2 runs `init` cold and hits an unrecoverable error.

**Why it happens:**
Remote state backends must exist before init. Entra tenants themselves are subscription-level resources created via a different API than the app registrations. Circular dependency or ordering issues between `azurerm` and `azuread` providers are common.

**How to avoid:**
- Split Terraform into **two states**:
  1. `bootstrap/` — creates the storage account for state, the resource group, and the External ID tenant. Local-state only. Run once, checked-in `.tfstate` NOT committed; outputs are copied to `main/`'s `terraform.tfvars`.
  2. `main/` — everything else, with remote state on the storage account from bootstrap.
- Document bootstrap as a one-time README section with exact CLI steps.
- Use `terraform import` for pre-existing resources rather than destroying-and-recreating.
- Pin provider versions: `azurerm = "~> 4.x"`, `azuread = "~> 3.x"`. Provider major-version bumps have introduced breaking changes on `single_page_application`, etc.

**Warning signs:**
- `Error: error loading state: storage account not found` on a fresh clone.
- `terraform plan` wants to destroy and recreate the tenant (state drift between bootstrap and main).
- Provider upgrade triggers schema migrations that fail on Burstable-tier Postgres (not all attributes supported).

**Phase to address:** terraform-iac (very first task of the phase).
**Confidence:** HIGH.

---

### Pitfall 14: Terraform workspace confusion — `dev` state applied to `prod` resources

**What goes wrong:**
Team adopts workspaces (`terraform workspace new dev`, `prod`). Someone runs `terraform apply` without checking the active workspace. Resources intended for dev land in prod (or a prod secret rotation wipes dev). Workspace name is an implicit global that doesn't appear in any commit.

**Why it happens:**
`terraform workspace` state is per-CLI-machine in `.terraform/environment`. No prompt on apply. Not visible in the plan output unless you explicitly reference `terraform.workspace` in variable values.

**How to avoid:**
- Use workspace-aware naming in every resource: `name = "job-rag-${terraform.workspace}"`.
- Wrap Terraform with a Makefile or script: `make apply-dev` / `make apply-prod` that forces the workspace switch AND adds a confirmation prompt.
- In CI, the GitHub Actions job explicitly runs `terraform workspace select prod` before plan/apply. Never `default` workspace.
- Add a `validate.sh` that fails if `terraform.workspace == "default"` in any non-bootstrap code.
- Prefer separate **directories** (`environments/dev/`, `environments/prod/`) over workspaces if the differences grow beyond a few variables — workspaces hide environment-specific drift inside a single config.

**Warning signs:**
- Resource counts in `terraform plan` wildly different between runs on the same branch.
- `default` workspace accidentally contains prod resources.
- Drift detected in one workspace but not the other — plan/apply from a teammate's machine shows changes you don't expect.

**Phase to address:** terraform-iac.
**Confidence:** HIGH.

---

### Pitfall 15: LLM resume extraction — scanned PDFs and DOCX noise silently produce wrong skills

**What goes wrong:**
User uploads a scanned PDF (photograph of a printed resume) or a DOCX with heavy formatting. `pypdf` / `pdfplumber` extract very little text or OCR-garbled text. Instructor-backed extraction returns a plausible-looking but fabricated `UserSkillProfile` — hallucinated skills the user never had.

**Why it happens:**
- Scanned PDFs need OCR; text-based PDF extractors silently return empty strings or image captions.
- DOCX bullet characters often come through as glyphs, tab characters, or get split across paragraphs.
- LLMs are optimistic: when given garbage input, they synthesize plausible output rather than refusing.
- Encoding issues (Windows-1252 vs UTF-8) in older DOCX produce mojibake the LLM hallucinates around.

**How to avoid:**
- Extract text with a library that detects scan vs native (e.g., `pdfplumber` then fallback to `pytesseract` if `len(text) < threshold`) OR explicitly reject scanned PDFs with a clear error.
- Require a minimum extracted character count (e.g., 500 chars) before invoking the LLM. Below that, return "We couldn't read your resume — please upload a text-based PDF or paste text directly."
- For DOCX: use `python-docx` and `mammoth` to extract both plain text AND HTML; give both to the LLM so bullet structure is preserved.
- Instructor with `max_retries=2` and a validator that rejects >20 skills (likely hallucination) or any skill with length >60 chars.
- **The existing "show extracted skills for review" UX is the single most important defence** — it's already in the Active requirements. Do not skip it as "we'll add it later".
- Log extracted-text length and final skill count to Langfuse for every extraction; alert if ratio seems off.

**Warning signs:**
- Extracted skill list contains skills not on the original resume (user reports "where did this come from?").
- Extracted text length < 500 chars.
- Identical skill sets returned for different resumes (LLM falling back to a memorized template).

**Phase to address:** resume-upload-feature (non-negotiable before shipping the endpoint).
**Confidence:** HIGH.

---

### Pitfall 16: RAGAS in CI — non-determinism triggers false-positive regressions

**What goes wrong:**
RAGAS metrics use an LLM as a judge. Judge calls are non-deterministic even at `temperature=0` (OpenAI still has floating-point non-determinism for scoring tasks). A PR that improves retrieval scores 0.82 on one run, 0.76 on the next. CI threshold at 0.80 fails arbitrarily. Team starts ignoring the CI result; the gate becomes theatre.

**Why it happens:**
LLM-as-judge has stochastic variance (~±0.03–0.05 absolute per metric). Running on 20 queries = ~0.01–0.02 variance on the aggregate. RAGAS 0.2 and 0.4 also shifted metric definitions — `answer_relevancy` in 0.2 is not identical to the post-0.4 equivalent; bumping the library version looks like a regression.

**How to avoid:**
- Pin the RAGAS version exactly in `pyproject.toml`. Do not use `^0.2` — use `==0.2.15` or similar.
- Use a wider threshold (e.g., median-of-3 runs vs a 5-pp drop from the last known-good baseline), not an absolute pass/fail.
- Run RAGAS with `temperature=0` and seed where possible.
- Store the baseline in the repo (`eval/baselines/ragas_v0.2.15.json`) and compare against it, not against a thresh-of-the-month.
- Budget: 20 queries × ~3 LLM calls per metric × 4 metrics ≈ 240 API calls per PR. At GPT-4o-mini rates this is cheap (~€0.02/run) but visible at 100 PRs/month.
- When library version changes: re-baseline deliberately as a single PR titled `chore(eval): rebaseline for RAGAS 0.X`.

**Warning signs:**
- CI red on one commit, green on re-run (no code change).
- Metric scores drift slowly over time with no corresponding code change — actually a model-version shift from the judge LLM.
- 0.2 → 0.3/0.4 upgrade attempt shows massive score deltas.

**Phase to address:** eval / ci-cd.
**Confidence:** MEDIUM (general LLM-as-judge non-determinism HIGH; RAGAS-specific version-migration semantics MEDIUM).

---

### Pitfall 17: Free-tier cost surprises — Log Analytics, Container Registry, egress

**What goes wrong:**
Everything is "free" until it isn't. Diagnostic settings enabled by default send every log line to Log Analytics. Monthly ingest exceeds 5 GB around week 3, billed at ~$2.30/GB. Container Registry Basic tier is ~€4/month (not free). Egress bandwidth first 100 GB/month is free, but pulling a 1.5 GB Docker image on every CI run + every deploy can eat it.

**Why it happens:**
The "free" label applies to the SKU, not unlimited usage. Log Analytics ingestion quota is per-workspace and silently exceeds on any production workload. No warning until the bill arrives (typically 45+ days after the month starts).

**How to avoid:**
- **Log Analytics:** turn off verbose diagnostic categories. In Terraform, only enable `ContainerAppConsoleLogs_CL` (app logs), skip `ContainerAppSystemLogs_CL` for routine use. Set a daily ingestion cap on the workspace: `daily_quota_gb = 0.1`.
- **Container Registry:** use GitHub Container Registry (`ghcr.io`) instead — free for public repos, and for private repos the bandwidth out to Azure is free (both sides). ACR Basic is the recommended-by-MS option but not the cheapest.
- **Egress:** use ACR's geo-replication only if truly needed (it's not for single-region apps). Deploy images to the same region as Container Apps to avoid cross-region egress.
- **Year-1 vs always-free:** track which resources are only free for 12 months (most compute) vs always free (some services with monthly allowances). Set a calendar reminder at month 10.
- **Credit expiry:** the €200 credit expires after 30 days. Don't rely on it masking real costs during the build-out.

**Warning signs:**
- First monthly invoice has a non-zero "Log Analytics" line.
- ACR storage > 5 GB (images piling up with no retention).
- Egress line item > 0 — something is pulling or pushing data outside the region.

**Phase to address:** deploy / cost-guardrails (must be a first-class checklist item, not a retro afterthought).
**Confidence:** HIGH.

---

### Pitfall 18: `user_id` default collision when multi-user mode enables

**What goes wrong:**
Schema adds `user_id UUID DEFAULT '<adrian-uuid>'`. Looks fine in v1. Six months later, multi-user enabled; someone forgets to remove the default. New user signs up, their rows silently get Adrian's `user_id` because the code path forgot to pass `user_id` through. Data commingling, invisible for months.

**Why it happens:**
SQL defaults are persistent. Application-layer defaults drift from DB-layer defaults. `DEFAULT gen_random_uuid()` is safer but wasn't used because v1 wanted a known UUID for Adrian's data.

**How to avoid:**
- DB column: `user_id UUID NOT NULL` — **no DEFAULT**. Inject the UUID application-side from the JWT `sub` claim.
- For v1 seeding, run an idempotent migration that sets Adrian's `user_id` on existing rows; don't rely on defaults.
- Foreign-key `user_id` to a `users(id)` table from day 1 so orphaned rows fail loudly.
- Add a CI check: `grep "DEFAULT.*uuid" alembic/versions/` should return zero results.
- Soft delete: add `deleted_at TIMESTAMPTZ` + partial unique indexes that exclude deleted rows. Hard-delete-on-cascade is fine for now; soft-delete is a platform-era feature but the column can be added cheaply.

**Warning signs:**
- Second user sees Adrian's conversation history.
- Row counts in analytical queries don't match expectations after multi-user enablement.
- `gen_random_uuid()` absent from migration files — extension `pgcrypto` not enabled.

**Phase to address:** backend-prep (schema design — the `user_id` migration is already in Active but must be DEFAULT-free).
**Confidence:** HIGH.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-code Adrian's UUID as a DB default | Faster v1 seeding | Multi-user rollout collides with existing rows; silent data commingling | Never — use app-level injection + migration instead |
| `CORS: "*"` on FastAPI | Works in dev and prod instantly | API is openly callable by any site; token theft surface expands | Localhost dev only — must be env-gated |
| Skip Alembic, rely on `init_db()` | No migration tooling to learn | `pgvector` enablement drifts between dev/prod DBs; schema changes break fresh clones | Never on a DB with persistent state |
| `temperature=0` treated as "deterministic" in RAGAS | Simple CI threshold | False regressions, ignored CI gate | OK if threshold accounts for ±0.05 variance |
| Store refresh tokens in localStorage | MSAL default works in all browsers | XSS attacker exfiltrates tokens | Session-storage instead; accept re-login on tab close |
| `minReplicas=1` to dodge cold-start | Perfect UX | ~€15-30/mo on free-tier-only project, breaks the budget constraint | Only when business hours are tight and you can schedule it |
| Global HuggingFace cache in Dockerfile | Cheap CI builds | First pod after image-cache-miss re-downloads 500 MB | Mount persistent volume in ACA (but free tier doesn't give you that cheaply) |
| One big Terraform state for everything | One `apply` deploys everything | Plan times balloon; blast radius = entire infra | Split into bootstrap/ and main/ from day 1 |
| No SSE keep-alive | Simpler code | Proxies kill idle streams | Never on SSE through any proxy |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Entra External ID | Using `login.microsoftonline.com` authority | Use `<tenant>.ciamlogin.com` authority; validate issuer against well-known config |
| MSAL React | Calling `handleRedirectPromise` in useEffect | Call BEFORE React render in `main.tsx`; gate UI on `inProgress === None` |
| SSE through Envoy (ACA) | Assuming 240s timeout is enough | Enforce app-level timeout < 240s; send keep-alive pings every 15s |
| Static Web Apps linked API | Mixing direct ACA calls and /api/* routing | Commit to `/api/*` everywhere in the SPA; never call the ACA hostname directly |
| pgvector | Enabling allowlist but not `CREATE EXTENSION` | Alembic migration creates the extension per-database |
| Alembic on Burstable Postgres | Running with SQLAlchemy pool | Use NullPool for migration scripts |
| GitHub Actions OIDC | Single federated credential for all triggers | One credential per trigger shape (branch push, environment, tag) |
| Terraform azuread provider | Not pinning major version | Pin `~> 3.x` — minor versions break `single_page_application` blocks |
| OpenAI via Instructor | No validation on extracted skill count | Max 20 skills, max 60 chars per skill, reject empty-text inputs |
| RAGAS 0.2 → 0.4 | Upgrade in same PR as code changes | Rebaseline as a dedicated PR so deltas are attributable |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Reranker loaded per worker | 4 × 80MB = 320MB wasted | Single-worker ACA replica; preload in lifespan | Any multi-worker deploy |
| B1ms CPU burst depletion | Slow queries during reranking; throttled DB | Keep reranker on API side only; use `asyncio.to_thread` | Burst credits run out under sustained load |
| Cold start on every first request | 15–25s hang | Pre-warm ping; `minReplicas=1` during business hours | Always on scale-to-zero |
| Connection pool > 35 on B1ms | `too many clients` errors during deploys | SQLAlchemy `pool_size=3, max_overflow=2`; NullPool for scripts | >1 replica + eval job concurrent |
| Embedding API called per-posting | Slow bulk ingest, 100× API calls | Batch to 500-2048 per call (already flagged in CONCERNS) | >50 postings at once |
| EventSource 6-connection browser cap | Multiple chat tabs refuse to stream | Close unused streams; migrate to HTTP/2 (ACA supports it) | 7+ tabs open to same origin |
| SSE gzip buffering | No streaming, response dumps at end | `X-Accel-Buffering: no`; no GZipMiddleware | Any proxy doing compression |
| Log Analytics ingestion | Silent monthly bill | Daily quota cap; disable system-log category | Week 3 of any month |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| FastAPI JWT validation skips `iss` or `aud` claims | Token from a different tenant or app accepted | Validate `iss`, `aud`, signature, and `exp` with JWKS cached from the well-known config |
| Refresh tokens in localStorage | XSS exfiltrates persistent credential | Use sessionStorage; accept re-login on tab close |
| Long-lived Azure SP secrets in GitHub secrets | Credential rotation friction; leaked if repo cloned | OIDC federated credentials only — zero long-lived secrets |
| Terraform state committed to repo | DB passwords in git history | Remote state only; pre-commit hook blocks `.tfstate` |
| CORS allowlist with `*` or regex | Any site can call API with user's token | Exact origin match; reject mismatches |
| `user_id` not filtered in queries | Data leak when multi-user enables | Parameterized filter in every query; audit with `grep "SELECT.*FROM.*WHERE"` |
| Resume upload not size-capped | Memory exhaustion on large PDFs | `max_upload_size=5MB` at FastAPI level; reject before reading body |
| Prompt injection via uploaded resume | LLM follows instructions in uploaded text | Treat resume as data not instructions; `_sanitize_delimiters` equivalent on resume text |
| Entra scope over-granted | SPA asks for `.default` and gets more than it needs | Request only `api://<api-id>/access_as_user` |
| SSE response reveals stack trace on error | Leaks env variables, DB schema | Catch all exceptions in the stream; emit sanitized `event: error` |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Single "loading" state for cold-start and streaming | Users think chat is broken on first use of the day | Distinct `connecting` / `warming` / `streaming` / `thinking` states |
| Silent token refresh failure | User kicked to login mid-conversation with no warning | Catch `monitor_window_timeout`, show "Session expiring — re-authenticate" banner |
| Resume upload shows "Done" on LLM response | User trusts hallucinated skills | Always show extracted skills in a reviewable panel; require explicit tick-to-save |
| Dashboard load times spike on eval days | User thinks dashboard is broken | Decouple eval from web DB OR run eval against a snapshot |
| Truncated SSE response due to revision swap | User sees half an answer, reloads and re-runs | Implement draining; emit `event: aborted` with a retry hint |
| CORS error surfaces as generic "network error" | User thinks app is offline | Explicit error boundary that detects CORS vs timeout vs auth |
| Mid-stream error as silent stop | User waits for more tokens that never come | Always terminate with `event: final` or `event: error`, never just close the stream |

## "Looks Done But Isn't" Checklist

- [ ] **Entra ID login works:** verify by reading the JWT — check `iss` starts with `ciamlogin.com`, `aud` is your API's client ID, not the SPA's.
- [ ] **SSE streams tokens:** test from deployed URL in Chrome AND Safari AND Firefox; view the `EventStream` tab, not just the response.
- [ ] **Cold start handled:** delete all ACA replicas (or wait for scale-to-zero), then hit the chat. First response should show a distinct "warming up" state.
- [ ] **Revision deploy doesn't drop streams:** start a long chat, trigger `terraform apply` with an inconsequential change, verify the stream completes or shows a clean abort+retry.
- [ ] **Silent refresh works across browsers:** log in, wait 65 minutes, try to call the API without clicking anything. Token refresh should succeed silently in Chrome, Safari, Firefox.
- [ ] **pgvector enabled in the right DB:** `psql ... -d jobrag -c "\dx"` lists `vector`. Not `postgres` database.
- [ ] **OIDC federated credential works for the actual trigger you use:** deploy from the exact trigger shape (branch push + environment) that CI uses. Not just `workflow_dispatch` from the terminal.
- [ ] **Log Analytics quota set:** `daily_quota_gb` is a non-default value, verified in the portal.
- [ ] **user_id has no DEFAULT:** `\d+ conversations` shows `user_id uuid NOT NULL` with no `DEFAULT` clause.
- [ ] **Resume extraction shows diff, not just save:** uploading the same resume twice shows the review panel both times.
- [ ] **RAGAS baseline committed:** there's a JSON file in the repo with the last known-good metric values, referenced by version.
- [ ] **CORS rejects unknown origins:** `curl -H "Origin: https://evil.example.com" ...` gets 403 or missing ACAO header.
- [ ] **Graceful shutdown verified:** `docker stop` (or `az containerapp revision deactivate`) completes in <30s and no stream errors in client logs.
- [ ] **Cost alerts configured:** budget alert at 50% / 75% / 90% of €0 threshold (yes, for a "free" project).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong tenant type used (workforce for customers) | HIGH | Provision a new External tenant; re-register apps; migrate users (none in v1 — Adrian re-registers). Update MSAL authority + FastAPI issuer. |
| Hardcoded `user_id` DEFAULT discovered in prod | MEDIUM | Migration: `ALTER COLUMN user_id DROP DEFAULT`; audit WHERE user_id = adrian-uuid for rows that shouldn't be his. |
| pgvector not enabled in prod DB | LOW | Run Alembic migration; restart app. Downtime <1 min. |
| Terraform state corrupted | MEDIUM | Restore from Azure Blob soft-delete (enabled by default, 7-day retention). If lost: `terraform import` every resource. |
| OIDC credential mismatched | LOW | Edit federated credential in portal with the exact subject from the failed workflow log. |
| SSE streams truncating on deploy | LOW | Set `terminationGracePeriodSeconds = 120` in Terraform; re-apply. |
| Resume extraction hallucinating | MEDIUM | Fall back to "paste text" UI; add stricter min-char threshold; add validator on skill count. |
| Log Analytics bill > budget | LOW | Set daily quota cap; purge old logs (`workspace_purge` API); disable verbose categories. |
| RAGAS CI false-positives | LOW | Widen threshold to `abs(delta) > 0.1` from baseline; run 3x median. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Wrong Entra tenant type | auth-prep (Terraform design) | JWT `iss` inspection in a smoke test |
| 2. Redirect URI type | auth-prep + terraform-iac | Portal green-checkmark; MSAL login round-trip |
| 3. 240s SSE timeout | backend-prep + deploy | Test stream at 230s keep-alive; Log Analytics for `request_timeout` |
| 4. Cold-start UX | backend-prep + frontend-shell | First-chat-of-day manual test |
| 5. Revision-swap drops SSE | backend-prep + terraform-iac | Deploy mid-stream, verify clean abort event |
| 6. SSE + gzip buffering | backend-prep + deploy | DevTools EventStream tab in production |
| 7. OIDC subject mismatch | deploy / ci-cd | First prod deploy from the real trigger |
| 8. Postgres connection exhaustion | backend-prep + deploy | Load test with 2 replicas + eval job |
| 9. pgvector per-database | terraform-iac + backend-prep | `\dx` against the target DB post-deploy |
| 10. SWA linked API CORS confusion | frontend-shell + deploy | Only hit `/api/*`; CORS allowlist review |
| 11. MSAL initialization race | frontend-shell | Hard-refresh while logged in shows no login flash |
| 12. Silent refresh in Safari | frontend-shell | Wait 65 min in Safari, then API call succeeds |
| 13. Terraform bootstrap chicken-and-egg | terraform-iac (task 1) | Fresh-clone dry run |
| 14. Terraform workspace confusion | terraform-iac + ci-cd | CI workflow always selects workspace explicitly |
| 15. Resume LLM hallucination | resume-upload feature | Review-panel UX is mandatory, not optional |
| 16. RAGAS CI non-determinism | eval / ci-cd | Baseline file committed; widened threshold |
| 17. Free-tier cost surprises | deploy / cost-guardrails | Budget alerts + Log Analytics daily quota |
| 18. `user_id` DEFAULT collision | backend-prep | Migration review; `grep DEFAULT` check in CI |

## Sources

**Entra External ID / MSAL / OIDC:**
- [External Tenant Overview — Microsoft Entra External ID](https://learn.microsoft.com/en-us/entra/external-id/customers/overview-customers-ciam) — HIGH
- [Microsoft identity platform and OAuth 2.0 authorization code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow) — HIGH
- [Avoid page reloads (MSAL.js)](https://learn.microsoft.com/en-us/entra/identity-platform/msal-js-avoid-page-reloads) — HIGH
- [MSAL race condition Issue #6893](https://github.com/AzureAD/microsoft-authentication-library-for-js/issues/6893) — HIGH
- [MSAL cache initialization race Issue #7561](https://github.com/AzureAD/microsoft-authentication-library-for-js/issues/7561) — HIGH
- [Common MSAL JS errors](https://learn.microsoft.com/en-us/entra/msal/javascript/browser/errors) — HIGH
- [MSAL token lifetimes doc](https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/token-lifetimes.md) — HIGH

**Azure Container Apps:**
- [Ingress Timeout Configurable? Issue #597](https://github.com/microsoft/azure-container-apps/issues/597) — HIGH
- [Premium Ingress Timeout Q&A](https://learn.microsoft.com/en-us/answers/questions/2284383/how-to-enable-premium-ingress-for-azure-container) — HIGH
- [Graceful termination on Container Apps](https://azureossd.github.io/2024/05/27/Graceful-termination-on-Container-Apps/) — HIGH
- [ACA terminationGracePeriodSeconds Q&A](https://learn.microsoft.com/en-us/answers/questions/5609700/azure-container-app-to-configure-terminationgracep) — HIGH
- [Reducing cold-start time on Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/cold-start) — HIGH
- [Scaling in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/scale-app) — HIGH
- [Application lifecycle management in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/application-lifecycle-management) — HIGH

**GitHub Actions OIDC:**
- [Authenticate to Azure from GitHub Actions by OpenID Connect](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect) — HIGH
- [Flexible federated identity credentials discussion #172176](https://github.com/orgs/community/discussions/172176) — HIGH
- [Azure Federated Credentials: Claims Matching Expressions](https://josh-ops.com/posts/azure-federated-credential-claims-matching-expressions/) — MEDIUM

**Azure Static Web Apps:**
- [Configure Azure Static Web Apps](https://learn.microsoft.com/en-us/azure/static-web-apps/configuration) — HIGH
- [Azure Static Web Apps Introduces API Backend Options](https://www.infoq.com/news/2022/07/azure-swa-backend-apis/) — MEDIUM
- [CORS on API portion of Azure Static Web Apps Issue #108](https://github.com/Azure/static-web-apps/issues/108) — MEDIUM

**Terraform:**
- [Backend Type: azurerm](https://developer.hashicorp.com/terraform/language/backend/azurerm) — HIGH
- [Store Terraform state in Azure Storage](https://learn.microsoft.com/en-us/azure/developer/terraform/store-state-in-azure-storage) — HIGH
- [Terraform State Management in Azure (2025)](https://blog.l-w.tech/posts/2025-02-26-tf-backend-bite-you.html) — MEDIUM

**Azure PostgreSQL Flexible Server:**
- [Limits in Azure Database for PostgreSQL flexible server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-limits) — HIGH
- [Postgres flexible server max_connections Q&A](https://learn.microsoft.com/en-us/answers/questions/770985/postgres-flexible-server-max-connections-parameter) — HIGH
- [Azure PostgreSQL connection pool exhausted Q&A](https://learn.microsoft.com/en-us/answers/questions/1464087/azure-postgresql-flexible-server-connection-pool-e) — HIGH
- [pgvector on Azure PostgreSQL Flexible Server](https://github.com/MicrosoftDocs/azure-databases-docs/blob/main/articles/postgresql/flexible-server/how-to-use-pgvector.md) — HIGH

**SSE / EventSource:**
- [Using server-sent events — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — HIGH
- [Server-Sent Events — High Performance Browser Networking](https://hpbn.co/server-sent-events-sse/) — HIGH
- [WHATWG Server-sent events spec](https://html.spec.whatwg.org/multipage/server-sent-events.html) — HIGH
- [Server-sent events and Application Gateway for Containers](https://learn.microsoft.com/en-us/azure/application-gateway/for-containers/server-sent-events) — HIGH

**LLM resume extraction:**
- [Parsing Resumes with LLMs — Datumo](https://www.datumo.io/blog/parsing-resumes-with-llms-a-guide-to-structuring-cvs-for-hr-automation) — MEDIUM
- [Extracting Data from PDFs — Unstract](https://unstract.com/blog/pdf-hell-and-practical-rag-applications/) — MEDIUM

**RAGAS:**
- [Ragas metrics overview](https://docs.ragas.io/en/stable/concepts/metrics/overview/) — HIGH
- [Ragas v0.3 → v0.4 migration](https://docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/) — HIGH
- [Evaluating Non-Deterministic Results From RAG Systems](https://medium.com/@parserdigital/evaluating-non-deterministic-results-from-rag-systems-0e3adaeddfd3) — MEDIUM

**Azure cost / free tier:**
- [Busting Azure Free Tier Myths](https://www.cloudoptimo.com/blog/busting-azure-free-tier-myths-avoid-the-hidden-costs/) — MEDIUM
- [Azure Container Registry pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/) — HIGH
- [Azure Egress Cost Guide](https://cloudcostkit.com/guides/azure-bandwidth-egress-costs/) — MEDIUM

---
*Pitfalls research for: Vite+React SPA + FastAPI + LangGraph + Entra External ID + Azure Container Apps + Terraform*
*Researched: 2026-04-23*
