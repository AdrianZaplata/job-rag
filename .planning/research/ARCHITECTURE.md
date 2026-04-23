# Architecture Research: Web-App + Azure Milestone

**Domain:** Single-user SaaS platform (structurally multi-user), Python/FastAPI backend + React SPA frontend, deployed on Azure free tier
**Researched:** 2026-04-23
**Confidence:** HIGH (Azure docs, official SDKs, Context7-equivalent sources verified)
**Scope:** Cross-cutting architecture introduced by this milestone only. Existing three-tier backend (Ingestion → Retrieval → Intelligence) is out of scope for re-architecture per `milestone_context`.

---

## 1. Topology at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                BROWSER                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Vite+React SPA (static bundle)                                       │  │
│  │  ├── MSAL React (auth-code + PKCE, token cache in sessionStorage)     │  │
│  │  ├── API client (adds "Authorization: Bearer <access_token>")         │  │
│  │  └── EventSource / fetch-ReadableStream for /agent/stream             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└───────────────┬─────────────────────────────────────────┬───────────────────┘
                │ (1) HTTPS static assets                 │ (3) HTTPS JSON/SSE
                │                                         │     Authorization: Bearer
                ▼                                         ▼
┌───────────────────────────────┐          ┌───────────────────────────────────┐
│ Azure Static Web Apps (Free)  │          │ Azure Container Apps (Consumption)│
│  ┌─────────────────────────┐  │          │  Envoy ingress                    │
│  │ vite build /dist        │  │          │   ├── Timeout: 240s default       │
│  │ ├─ index.html           │  │          │   ├── Idle timeout: cfg (premium) │
│  │ ├─ assets/*.js          │  │          │   └── HTTP/2 + chunked xfer       │
│  │ └─ staticwebapp.config  │  │          │  ┌─────────────────────────────┐  │
│  │    (routes fallback)    │  │          │  │ FastAPI container           │  │
│  └─────────────────────────┘  │          │  │  ├── CORS allowlist mw      │  │
│  Custom domain (optional v2)  │          │  │  ├── fastapi-azure-auth JWT │  │
│                               │          │  │  ├── /agent/stream (SSE)    │  │
│                               │          │  │  ├── Reranker pre-loaded    │  │
│                               │          │  │  │   in lifespan            │  │
│                               │          │  │  └── LangGraph agent        │  │
│                               │          │  └─────────────────────────────┘  │
└─────────────┬─────────────────┘          └──────────────┬────────────────────┘
              │                                           │
              │  (2) OIDC auth-code + PKCE                │  (4) asyncpg over SSL
              ▼                                           ▼
┌───────────────────────────────┐          ┌───────────────────────────────────┐
│  Microsoft Entra External ID  │          │  Azure DB for PostgreSQL          │
│  (CIAM tenant, separate from  │          │  Flexible Server B1ms (Burstable) │
│  the Azure subscription       │          │   + pgvector extension            │
│  workforce tenant)            │          │   + private endpoint (v2) / FW    │
│  ├─ SPA app reg (public)      │          │     rule allowing ACA subnet (v1) │
│  └─ API app reg (resource)    │          └───────────────────────────────────┘
│     └── scope api://<id>/Access.All                             ▲
└───────────────────────────────┘                                 │
                                          ┌───────────────────────┴───────────┐
                                          │  Azure Key Vault                  │
                                          │  ├─ OPENAI_API_KEY                │
                                          │  ├─ POSTGRES_PASSWORD             │
                                          │  ├─ LANGFUSE_SECRET_KEY           │
                                          │  └─ accessed via Container App    │
                                          │     managed identity + Key Vault  │
                                          │     reference syntax in secrets   │
                                          └───────────────────────────────────┘

Build & deploy plane (out-of-band):

  GitHub Actions ──OIDC federated credential──► Azure AD Workforce tenant ──► ARM control plane
     │                                                                              │
     ├─ workflow-api.yml  (docker build → ACR push → containerapp update)           │
     ├─ workflow-spa.yml  (vite build → azure/static-web-apps-deploy@v1)            │
     └─ workflow-tf.yml   (terraform plan/apply with remote state in blob storage)  │
                                                                                    ▼
                                                            Log Analytics workspace
                                                            (ACA logs, SWA not-supported-yet)
```

The diagram shows the **free-tier v1 topology** (direct SPA → ACA origin with CORS). The Static Web Apps "linked backend" feature is a known alternative — see §2 for why it is **not** adopted in v1.

---

## 2. Concern A — SPA ↔ API Topology on Azure

### Decision: direct origin with CORS allowlist in v1. Linked-backend pattern deferred.

Azure Static Web Apps supports a **linked backend** feature where requests to `/api/*` on the SWA origin are proxied to a linked Container App. Under that model, CORS is eliminated (same origin), and a hidden identity provider named `Azure Static Web Apps (Linked)` locks the Container App so it only accepts proxied traffic. **But:**

| Constraint | v1 impact |
|---|---|
| Linked backend requires **SWA Standard plan** (~€9/mo) | Violates €0/mo year-1 budget constraint |
| A Container App can be linked to **only one** SWA | Locks out dev/prod SWA sharing one ACA |
| Pull-request environments don't support the linked backend | Breaks preview-env workflow we may want later |
| Adds a proxy hop — ingress idle-timeout stacks on top of ACA's | Extra SSE failure mode to debug |

**v1 path (recommended):**
- SWA on **Free tier** hosts the Vite build. Vite's `base: '/'` + SPA router fallback via `staticwebapp.config.json` `"navigationFallback": { "rewrite": "/index.html" }`.
- The SPA reads `VITE_API_BASE_URL` at build time → points at the Container App FQDN (`https://job-rag-api.<random>.<region>.azurecontainerapps.io`).
- FastAPI gains `CORSMiddleware` with an **env-var allowlist**:
  - Dev: `http://localhost:5173` (Vite default)
  - Prod: SWA URL (after first deploy) + optional custom domain
  - Credentials: `allow_credentials=False` (we use Bearer tokens, not cookies) — simpler CORS preflight.
  - Allowed headers: `Authorization, Content-Type`
  - Allowed methods: `GET, POST, OPTIONS`

**Custom domain path (v2, optional):** point `app.job-rag.dev` at SWA, `api.job-rag.dev` at ACA. Still two origins → CORS still required. Only way to collapse origins for free is to proxy through SWA, which requires Standard plan.

### Build-order implications
- SWA default origin is only known **after** the SWA is provisioned (random hash subdomain). Terraform outputs the SWA URL → the CI workflow that deploys the API reads that output → sets `ALLOWED_ORIGINS` env var on the Container App. This introduces a **one-way Terraform dependency**: SWA must be created before the Container App env vars are finalized.
- First-deploy workaround: ship the Container App with `ALLOWED_ORIGINS="*"` as a temporary constant, `terraform apply` the SWA, then a second `terraform apply` wires the SWA URL into the Container App's secrets/env. Document this two-step bootstrap in README.

### Component boundary
- **FastAPI never calls SWA.** Data flow is browser-initiated only. SWA is a CDN; the API is the origin of state.
- **Auth tokens cross the boundary, not cookies.** Bearer-Auth header + JWT → no cookie CSRF class of problems, no SameSite gymnastics.

---

## 3. Concern B — SSE Through Container Apps Ingress

### Decision: keep SSE on `/agent/stream`, add heartbeats, preload the reranker, set a 60s agent timeout, pin `minReplicas≥1` during active hours.

**What the Envoy ingress does to streaming:**
- **HTTP/1.1 chunked transfer and HTTP/2 streams both pass through** with no enforced response buffering (unlike Azure Application Gateway, which buffers by default). Envoy proxies bytes as they arrive.
- **Request timeout** defaults to **240 seconds**. Any single SSE response that does not close within 240s is killed by the ingress. A typical agent reasoning loop is 5–30s, so 240s is comfortable — but we must guarantee the server side closes cleanly within that window or sends `final` event early.
- **Idle timeout** applies to gaps between bytes. On the Consumption plan, idle timeout is fixed; on the Premium ingress it's configurable via `az containerapp env update --request-idle-timeout`. Since we're free tier → Consumption → **cannot extend idle timeout**. Must send heartbeats.
- **Scale-to-zero (minReplicas=0) + SSE** is a UX trap. First chat after idle = 3–8s cold-start before any token appears. Browser fetch/EventSource readers don't show "thinking" — they just hang.

### Server-side SSE contract (documented in Pydantic, v1)

Add the following event schema in `src/job_rag/api/routes.py` and publish it in the OpenAPI spec:

```python
class AgentEvent(BaseModel):
    event: Literal["token", "tool_start", "tool_end", "final", "error", "heartbeat"]
    data: dict  # shape depends on event; enumerated via AgentEventData union

# Heartbeat: every 15s while agent is working, emit
#   event: heartbeat
#   data: {"ts": "2026-04-23T12:34:56Z"}
# — keeps Envoy idle timer reset, keeps browser Connection alive, gives SPA a liveness signal.
```

Additions to the existing `/agent/stream` handler:

1. **Wrap the agent call in `asyncio.wait_for(..., timeout=60)`.** On `TimeoutError`, emit `event: error` with reason `"agent_timeout"` then close. Do not let ingress time out the connection unannounced.
2. **Heartbeat generator.** Spawn a task that yields `event: heartbeat` every 15s. Cancel it when the agent produces `final`.
3. **Preload reranker in `app.py` lifespan.**
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       from job_rag.services.retrieval import _get_reranker
       _get_reranker()  # warm the cross-encoder (~80 MB) during startup
       yield
   ```
   This turns the 2–5s cold-start penalty into a one-time startup cost, paid during container provisioning rather than during the user's first chat.
4. **Wrap reranker in `asyncio.to_thread`** wherever it's called in async context. Reranker is CPU-bound PyTorch; blocking the event loop kills heartbeat timing and stalls the SSE stream.

### Scale-to-zero policy

| Hours | Strategy | Rationale |
|---|---|---|
| v1 day-1 | `minReplicas=0, maxReplicas=1` | Free-tier budget, chat UX degrades on first hit but is tolerable for single-user demo |
| v1 day-N | HTTP scale rule + optional "wake" via scheduled GitHub Action hitting `/health` at 08:00 CET | Mitigates cold-start without paying for an always-on replica |
| Portfolio-demo mode | Temporarily `minReplicas=1` 24h before a recruiter call | Pays €≤2 for the day, eliminates all cold starts |

### Component boundary
- SSE is an **application-protocol concern**, not an infrastructure one. The only Azure knob is idle timeout (which we can't change on free tier) — everything else belongs in FastAPI.
- Heartbeat logic lives in `src/job_rag/agent/stream.py` (wrap existing `stream_agent()`), not in route handlers.

### Build-order implications
- Reranker-preload and heartbeats can land **before** any frontend work — pure backend refactor. They block nothing downstream except they remove frontend pain.
- The Pydantic event contract must land **before** the frontend writes the SSE reader so both sides share a typed schema. Generate TypeScript types from OpenAPI via `openapi-typescript` in the SPA build.

---

## 4. Concern C — Auth: Entra External ID → SPA → FastAPI

### Decision: Entra **External ID** (CIAM, not B2C-classic), MSAL React in SPA, `fastapi-azure-auth` validating JWT on FastAPI. Single-user enforcement lives in a FastAPI dependency, not in Entra policy.

### Which Entra flavour

Microsoft now has three:
1. **Entra ID Workforce** — company employees; same tenant as the Azure subscription.
2. **Entra External ID** (GA, the successor to "External Identities") — customer-facing CIAM, separate tenant.
3. **Azure AD B2C (classic)** — legacy CIAM, still supported but in maintenance mode; new projects should use External ID.

Adrian's portfolio is a customer-facing product, so **External ID** is correct. It lives in a **separate Entra tenant** from the Azure subscription's workforce tenant. Same Azure bill, different identity directory. This is critical for the Terraform split (§6).

### Flow (browser's POV)

1. SPA loads, MSAL bootstraps from `msalConfig`:
   ```ts
   {
     clientId: SPA_APP_CLIENT_ID,                      // SPA app registration
     authority: "https://<ciam-tenant>.ciamlogin.com/", // External ID endpoint
     redirectUri: window.location.origin,
     cache: { cacheLocation: "sessionStorage" },        // tighter than localStorage
   }
   ```
2. Protected route triggers `loginRedirect()` — browser goes to `/oauth2/v2.0/authorize` with `code_challenge` (PKCE), scope `api://<API_APP_CLIENT_ID>/Access.All openid profile`.
3. User authenticates; Entra redirects back to SPA with auth code.
4. MSAL exchanges code + PKCE verifier for access token + ID token (no secret — SPA is a public client).
5. SPA stores token in memory / sessionStorage. On API call, `acquireTokenSilent({ scopes: ["api://<API_APP_CLIENT_ID>/Access.All"] })` + `Authorization: Bearer <access_token>`.

### Flow (FastAPI's POV)

`fastapi-azure-auth` (intility, mature, supports External ID as of 5.x):

```python
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer

azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    app_client_id=settings.API_APP_CLIENT_ID,            # this API's audience
    tenant_id=settings.CIAM_TENANT_ID,
    scopes={f"api://{settings.API_APP_CLIENT_ID}/Access.All": "Access the API"},
)

@router.get("/search", dependencies=[Security(azure_scheme)])
async def search(...): ...
```

What this gives us:
- **JWKS fetched from the tenant's OIDC metadata endpoint and cached** (default TTL matches Microsoft's key rotation cadence — typically 24h).
- **Signature verification** against the cached JWKS.
- **Audience (aud) check** against `api://<API_APP_CLIENT_ID>`.
- **Issuer (iss) check** against `https://<ciam-tenant>.ciamlogin.com/<tenant-id>/v2.0`.
- **Exp, nbf, iat** checks.
- **User object injection** via `request.state.user` → has `claims`, `oid` (Entra object ID — stable per user), `sub`, and scope.

### Single-user enforcement (the "passphrase-like" guard)

The Active requirements say "Adrian's UUID seeded as the only user". This is **application-level** enforcement, not directory-level:

```python
async def only_seeded_user(
    user: Annotated[User, Depends(azure_scheme)],
) -> User:
    if user.claims["oid"] != settings.SEEDED_USER_ENTRA_OID:
        raise HTTPException(403, "Not authorized")
    return user
```

- `SEEDED_USER_ENTRA_OID` is Adrian's Entra object ID (stable, opaque UUID issued by Entra when the user is created).
- Map this to `user_id` (the internal UUID used in DB columns — §7) via a lookup table or a direct `user_id == SEEDED_USER_ENTRA_OID` convention.
- When v2 opens to more users: drop the `only_seeded_user` dependency, add an auto-provisioning step that creates a DB user row on first JWT seen with an unknown `oid`.

### Token delivery on SSE

`EventSource` **cannot send custom headers**. Options:
- **A. Use `fetch` + `ReadableStream` instead of `EventSource`** — supports `Authorization` header natively. Standard pattern for SSE in authenticated SPAs. **Recommended.**
- **B. Pass token as query param** (`/agent/stream?token=...`) — works with `EventSource` but tokens end up in server logs. **Rejected.**
- **C. Use WebSocket** — WS upgrade can include headers; but SSE is already working on the backend, no need to switch protocols.

### Component boundary
- **SPA knows nothing about internal `user_id`** — it only holds the Entra access token. Backend derives `user_id` from the JWT's `oid` claim.
- **FastAPI never calls Entra directly** — it only validates tokens against cached JWKS. No Graph API calls in v1.
- **`fastapi_azure_auth` replaces the existing `require_api_key` middleware** entirely. The `JOB_RAG_API_KEY` env var becomes a dev-only escape hatch (gated by a settings flag like `AUTH_MODE=dev-bearer`).

### Build-order implications
1. **Entra tenant + both app registrations must exist** before any SPA auth code can be tested (even locally — MSAL needs a real `tenantId` + `clientId`).
2. **API app registration must expose its scope** (`Access.All`) before the SPA app registration can be granted permission to it. Terraform order: resource → client → admin consent.
3. **JWKS endpoint must be reachable from the Container App.** ACA outbound to internet is allowed by default on Consumption; no extra rule needed. Document as an assumption.

---

## 5. Concern D — Terraform Module Layout

### Decision: one root module, one state, per-environment workspaces (`dev`, `prod`), AVM-based child modules.

Splitting into many tiny root modules (one per resource) is overkill for a single-user portfolio project and multiplies state files to manage. Splitting into many workspaces is the explicit `Key Decisions` choice. Stay flat.

### Repository layout

```
infra/
├── envs/
│   ├── prod/
│   │   ├── main.tf              # calls ../../modules/*
│   │   ├── variables.tf
│   │   ├── outputs.tf           # SWA URL, ACA FQDN, DB host (for CI injection)
│   │   ├── terraform.tfvars     # encrypted or templated from CI secret
│   │   └── backend.tf           # azurerm backend pinned to prod state blob
│   └── dev/                     # same shape; smaller SKUs
├── modules/
│   ├── foundation/              # rg, log analytics, vnet (v2)
│   ├── platform/                # acr, key vault, managed identity
│   ├── data/                    # postgres flex server, firewall rules, pgvector ext
│   ├── compute/                 # aca environment + aca container app
│   ├── frontend/                # static web app (free tier)
│   └── identity/                # external id tenant ref + spa app reg + api app reg
└── README.md                    # bootstrap sequence
```

**Why one root per env** (not workspaces): `azurerm` backend in blob storage is per-state-file. Separate envs → separate state files → simpler blast-radius reasoning. The `Key Decisions` line "Terraform workspaces (dev + prod) from day 1" is compatible with this — Terraform CLI workspaces map to state-key prefixes within the same blob container, which is what we'll use.

### Resource dependency graph (build order)

```
(1) Resource Group                          ← prerequisite for everything
      │
      ├─(2) Log Analytics Workspace          ← ACA env needs diagnostic settings target
      │
      ├─(3) Key Vault                        ← holds secrets before Container App references them
      │     └─ Access policy for CI SP       ← GitHub Actions OIDC SP
      │     └─ Access policy for ACA-MI      ← (wired in step 6 once MI exists)
      │
      ├─(4) Azure Container Registry (Basic) ← holds image before Container App can pull
      │
      ├─(5) Postgres Flex B1ms               ← independent of compute; takes ~10 min to provision
      │     ├─ pgvector extension            ← via `azurerm_postgresql_flexible_server_configuration`
      │     └─ Firewall rule                 ← allow ACA env outbound IP (or "AllowAllAzureServices")
      │
      ├─(6) ACA Environment                  ← depends on LAW (2)
      │     └─ Container App                 ← depends on ACR (4) + KV (3) + Postgres (5)
      │         ├─ system-assigned MI        ← output: principal_id → back to KV access policy (3)
      │         ├─ secret refs → KV          ← `keyVaultUrl` syntax in ACA secret
      │         └─ env: ALLOWED_ORIGINS      ← late-bind after SWA (7) exists
      │
      ├─(7) Static Web App (Free)            ← independent; no config depends on SPA existing
      │     └─ output: default_host_name     ← feeds back into ACA env var (6)
      │
      └─(8) Entra External ID app regs       ← lives in separate provider alias (different tenant)
            ├─ API app registration          ← exposes scope
            └─ SPA app registration          ← consumes scope, has redirect_uri = SWA URL (7)
```

**The cycle: Container App → ALLOWED_ORIGINS → SWA → Container App.** Break it with a two-pass apply:
- Pass 1: `terraform apply -target=module.frontend` — creates SWA, writes URL to state.
- Pass 2: `terraform apply` (full) — now `module.compute` can read `module.frontend.default_host_name` from state.

Or use a `null_resource` + `local-exec` that runs `az containerapp update --set-env-vars ALLOWED_ORIGINS=...` after the SWA is live. Less clean but a one-shot.

### Remote state

```hcl
# envs/prod/backend.tf
terraform {
  backend "azurerm" {
    resource_group_name  = "job-rag-tfstate-rg"    # created out-of-band, once, manually
    storage_account_name = "jobragtfstate<suffix>"
    container_name       = "tfstate"
    key                  = "prod.terraform.tfstate"
    use_oidc             = true                    # GitHub Actions auth to state blob
  }
}
```

Bootstrap: create the state RG + storage account manually via `az` CLI once, then `terraform init` from that point forward. This is the standard Azure Terraform pattern — there's no chicken-and-egg way to provision your own state backend with Terraform.

### AVM (Azure Verified Modules) — recommended child modules

Microsoft publishes official-verified modules on registry.terraform.io:
- `Azure/avm-res-app-containerapp/azurerm` — Container App with identity, ingress, secrets
- `Azure/avm-res-web-staticsite/azurerm` — Static Web App
- `Azure/avm-res-dbforpostgresql-flexibleserver/azurerm` — Postgres Flex
- `Azure/avm-res-keyvault-vault/azurerm` — Key Vault with RBAC
- `Azure/avm-res-operationalinsights-workspace/azurerm` — Log Analytics

Using AVM modules gives us: tested module inputs, encoded resource naming conventions, and provider-version pinning. Beats hand-writing `azurerm_container_app` blocks. Not a hard requirement — hand-rolled is fine for this scope — but recommended as a portfolio signal.

### Component boundary
- **Terraform owns everything that must survive a git-clone-and-redeploy.** Images and secrets do not.
- **Secrets never in `.tfvars`.** Bootstrap-time secrets (OpenAI key, DB admin password) are set manually via `az keyvault secret set` or injected through GitHub Actions repo secrets → Terraform variables at apply time.
- **The Entra directory is a foreign domain.** Separate provider alias (`provider "azuread" { alias = "ciam", tenant_id = var.ciam_tenant_id }`), separate access rights. Workforce-tenant-scoped SP cannot manage the External ID tenant by default — a separate SP in the CIAM tenant is needed, **or** delegate to a human operator for that bootstrap.

---

## 6. Concern E — GitHub Actions → Azure OIDC Federation

### Decision: two OIDC-federated service principals (infra SP, app SP), three workflows (tf, api, spa), no long-lived secrets.

### Federated credential model

GitHub → Azure OIDC replaces the old `AZURE_CREDENTIALS` JSON secret. The flow:
1. GitHub Actions job requests an OIDC token from GitHub's issuer (`token.actions.githubusercontent.com`).
2. Job calls `azure/login@v2` with `client-id`, `tenant-id`, `subscription-id` — **no secret**.
3. Azure's federated credential on the app registration matches the OIDC token's subject claim (`repo:AdrianZaplata/job-rag:ref:refs/heads/master` or `repo:AdrianZaplata/job-rag:environment:prod`) against the configured federation pattern.
4. Match → Azure issues an access token for the workflow to use.

### Service principal split

| SP | Role assignments | Used by |
|---|---|---|
| `sp-job-rag-tf` | `Contributor` on the subscription; Key Vault admin scoped to the KV resource | `workflow-tf.yml` (plan + apply) |
| `sp-job-rag-app` | `acrpush` on ACR; `Container App Contributor` on the specific ACA resource; `Azure Static Web Apps Contributor` on the specific SWA | `workflow-api.yml` + `workflow-spa.yml` |

Two SPs so that day-to-day deploys don't have Terraform-level blast radius. The infra SP can do anything, the app SP can only push images and update configs.

### Workflow composition

```
workflow-tf.yml        ← manual dispatch or PR on infra/**
  jobs:
    plan:
      - azure/login@v2 (OIDC, sp-job-rag-tf)
      - terraform plan
      - Post plan output to PR comment
    apply (on merge, environment: prod):
      - azure/login@v2 (OIDC, sp-job-rag-tf)
      - terraform apply -auto-approve
      - Export: ACA_NAME, ACR_NAME, SWA_NAME as job outputs

workflow-api.yml       ← on push to master (or tag) if src/** or Dockerfile changed
  jobs:
    test:
      - run pytest + ragas (existing)
    build:
      needs: test
      - azure/login@v2 (OIDC, sp-job-rag-app)
      - az acr login --name <ACR_NAME>
      - docker build + push <ACR_NAME>.azurecr.io/job-rag:${{ github.sha }}
    deploy:
      needs: build
      - az containerapp update --name <ACA_NAME> \
          --image <ACR_NAME>.azurecr.io/job-rag:${{ github.sha }}
      - Poll /health endpoint until 200

workflow-spa.yml       ← on push to master if frontend/** changed
  jobs:
    build:
      - cd frontend && pnpm install && pnpm build
    deploy:
      - Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.SWA_DEPLOYMENT_TOKEN }}
          app_location: "frontend"
          output_location: "dist"
```

**Gotcha:** `Azure/static-web-apps-deploy@v1` still uses a **deployment token** (fetched from the SWA resource once, stored as a GitHub Actions secret). OIDC for SWA deploy is in preview but not universally GA as of 2026. Accept the single secret for SWA deployment — it's scoped only to that SWA, not the subscription.

### Component boundary
- **Workflows are deliberately orthogonal.** SPA deploy can run without API deploy and vice versa. The only shared dependency is that both deploy against infra provisioned by `workflow-tf.yml`.
- **No workflow writes to Terraform state.** Only `workflow-tf.yml` holds the state lock.

### Build-order implications
- **Federated credentials on the app registration must exist before the first workflow run** — one-shot `az ad app federated-credential create` or Terraform `azuread_application_federated_identity_credential`.
- The CIAM tenant's SP federation is a separate registration in the CIAM tenant — do **not** try to authenticate to the External ID tenant using the workforce-tenant SP.

---

## 7. Concern F — `user_id` + `career_id` Data Model Hedge

### Decision: add Alembic to the project, migrate in one revision that adds `user_id UUID NOT NULL DEFAULT <adrian-uuid>` and `career_id TEXT NOT NULL DEFAULT 'ai_engineer'` to all user-scoped tables. Plus a new `user_profile` table replacing `data/profile.json`.

### Schema changes (revision `0001_multi_user_hedge`)

```python
# alembic/versions/0001_multi_user_hedge.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"  # Adrian

def upgrade() -> None:
    # Ensure uuid generation is available
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # 1. New user_profile table (replaces data/profile.json)
    op.create_table(
        "user_profile",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entra_oid", sa.String(length=64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(length=200)),
        sa.Column("skills", sa.JSON, nullable=False),               # preserves existing JSON shape
        sa.Column("target_roles", sa.JSON),
        sa.Column("preferred_locations", sa.JSON),
        sa.Column("min_salary_eur", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Seed Adrian's row BEFORE adding FKs
    op.execute(f"""
        INSERT INTO user_profile (user_id, entra_oid, display_name, skills)
        VALUES ('{SEED_USER_ID}', 'SEED_REPLACE_ME_POST_DEPLOY', 'Adrian', '{{"items": []}}'::json)
    """)

    # 2. Add user_id + career_id to job_posting_db, default to Adrian / ai_engineer
    op.add_column(
        "job_posting_db",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            server_default=sa.text(f"'{SEED_USER_ID}'::uuid"),
            nullable=False,
        ),
    )
    op.add_column(
        "job_posting_db",
        sa.Column(
            "career_id",
            sa.String(length=64),
            server_default="ai_engineer",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_job_posting_user",
        "job_posting_db", "user_profile",
        ["user_id"], ["user_id"],
    )
    op.create_index("ix_job_posting_user_career", "job_posting_db", ["user_id", "career_id"])

    # 3. Ditto for chunks (inherited from posting but explicit for future RLS)
    op.add_column("job_chunk_db", sa.Column("user_id", UUID, server_default=sa.text(f"'{SEED_USER_ID}'::uuid"), nullable=False))

def downgrade() -> None:
    op.drop_index("ix_job_posting_user_career", table_name="job_posting_db")
    op.drop_constraint("fk_job_posting_user", "job_posting_db", type_="foreignkey")
    op.drop_column("job_posting_db", "career_id")
    op.drop_column("job_posting_db", "user_id")
    op.drop_column("job_chunk_db", "user_id")
    op.drop_table("user_profile")
```

### Why Alembic now (not raw DDL)

- The existing `CONCERNS.md` already flags "no alembic" as a fragile area. Adopting it here pays down that debt in the same PR that touches the schema.
- **Idempotent on CI.** RAGAS + CI workflow will need to spin up a fresh DB regularly. `alembic upgrade head` is deterministic; a hand-rolled `init-db` + DDL script is not.
- **Forward-compatible.** Every future schema change (adding columns, renaming, indices on analytics queries) plugs into the same pipeline.

### Query surface change

All service functions currently read without a user filter. New contract:

```python
# Before
async def search_postings(session, query, *, limit=20) -> list[...]: ...

# After
async def search_postings(
    session, query, *, user_id: UUID, career_id: str = "ai_engineer", limit=20,
) -> list[...]:
    ...
    stmt = select(JobPostingDB).where(
        JobPostingDB.user_id == user_id,
        JobPostingDB.career_id == career_id,
        ...
    )
```

`user_id` is resolved in the auth dependency (`Depends(only_seeded_user)` → returns internal `User`) and threaded through to every service call. `career_id` defaults, is readable from a query param on dashboard endpoints.

### Component boundary
- **Schema migration is the single source of truth for the data shape.** The Pydantic `UserSkillProfile` model and the SQLAlchemy `UserProfile` ORM model must evolve together.
- **`load_profile()` from `src/job_rag/services/matching.py` is replaced, not deleted** — becomes a thin wrapper `async def load_profile(session, user_id) -> UserSkillProfile` that queries the new table. Keeps downstream callers stable.

### Build-order implications
- **Alembic + migration must ship before any Entra wiring.** The "seed Adrian" step depends on knowing Adrian's Entra `oid`, which isn't available until Entra is provisioned. Sequence:
  1. Add Alembic. Migrate with a placeholder `entra_oid` ("SEED_REPLACE_ME_POST_DEPLOY").
  2. Provision Entra External ID tenant + app regs. Adrian signs in once to generate his OID.
  3. Run a one-shot script to `UPDATE user_profile SET entra_oid = '<real-oid>' WHERE user_id = '<seed-uuid>'`.
- **All service-function signature changes must land together**, not piecemeal. A partial migration where `/search` filters by `user_id` but `/gaps` doesn't creates a silent correctness bug.

---

## 8. Concern G — `IngestionSource` Protocol

### Decision: a typed Protocol in `src/job_rag/services/ingestion.py`, one v1 implementation (`MarkdownFileSource`), CLI and API endpoint both go through it.

### Protocol shape

```python
# src/job_rag/services/ingestion.py
from typing import Protocol, AsyncIterator
from dataclasses import dataclass

@dataclass(frozen=True)
class RawPosting:
    """What an ingestion source emits. No DB dependency, no extraction logic."""
    content: str                 # raw markdown / text
    source_identifier: str       # filename, URL, API id — for dedup logging
    source_type: str             # "markdown_file" | "linkedin_url" | "api"
    metadata: dict[str, str]     # opaque; source-specific (e.g., file_mtime)

class IngestionSource(Protocol):
    """Protocol any ingestion source implements. Async iterator = streamable."""
    async def iter_postings(self) -> AsyncIterator[RawPosting]: ...

class MarkdownFileSource:
    """v1 implementation. Reads a directory of markdown files."""
    def __init__(self, path: Path): self.path = path

    async def iter_postings(self) -> AsyncIterator[RawPosting]:
        for md_file in self.path.glob("*.md"):
            yield RawPosting(
                content=md_file.read_text(encoding="utf-8"),
                source_identifier=md_file.name,
                source_type="markdown_file",
                metadata={"mtime": str(md_file.stat().st_mtime)},
            )
```

### The ingestion pipeline becomes

```python
async def ingest_from_source(
    session: AsyncSession,
    source: IngestionSource,
    *,
    user_id: UUID,
    career_id: str = "ai_engineer",
) -> IngestReport:
    async for raw in source.iter_postings():
        # existing dedup + extract + store logic, unchanged
        # plus user_id / career_id passed into _store_posting()
```

### Why a Protocol (not a base class)

- **No inheritance chain.** Future sources (scrapers, APIs) don't need to import a base class — they just shape-match the Protocol.
- **Testable.** `mock_source = [RawPosting(...), RawPosting(...)]` works via duck typing; no mock classes.
- **CLI stays sync-simple** — `ingest_directory(path)` becomes `run_sync(ingest_from_source(sess, MarkdownFileSource(path), user_id=...))`.

### Component boundary
- **Source does not know about extraction.** It emits raw text and a stable identifier. All extraction, embedding, and storage is downstream.
- **API and CLI converge.** The existing async/sync-mixing in `/ingest` endpoint (CONCERNS.md #1) is resolved by having both entry points call the async `ingest_from_source` — CLI wraps with `asyncio.run`, API awaits directly.
- **New sources are a plug-in point.** LinkedIn scraper, Greenhouse API, scheduled-refresh worker — each is a new class implementing the Protocol, added under `src/job_rag/services/sources/`.

### Build-order implications
- **Can ship independently of the frontend.** Pure backend refactor that preserves the existing `data/postings/` UX.
- **Must land before the resume-upload feature** — that feature introduces a second source type (PDF/DOCX user upload extracting into `UserProfile` not `JobPosting`, but the same Protocol shape applies if we extend `RawPosting` with a `kind: Literal["posting", "profile"]`).

---

## Component Responsibilities Table

| Component | Owns | Talks to (outbound) | Listens on (inbound) |
|-----------|------|---------------------|----------------------|
| **Vite+React SPA** | UI state, MSAL token cache, SSE decoding, filter bars | Container App FQDN (HTTPS+JWT), Entra authority | Browser window / user |
| **MSAL React** | Auth-code + PKCE flow, silent token refresh | Entra authorize/token endpoints | SPA code |
| **Azure Static Web Apps (Free)** | Static asset CDN, SPA fallback routing | — | Browser HTTPS |
| **Azure Container Apps Env** | Envoy ingress, Log Analytics diagnostic sink | Log Analytics, ACR (image pull), Key Vault (secret refs), Postgres | SPA HTTPS on 443 |
| **FastAPI container** | API routes, JWT validation, CORS, SSE, reranker lifespan | Postgres (asyncpg), OpenAI, Langfuse (optional), Entra JWKS | ACA ingress on 8000 |
| **LangGraph agent** | Tool orchestration, ReAct loop | Services layer (search, match, gaps) | FastAPI route handler |
| **Services (retrieval/matching/ingestion)** | Business logic, pure async fns, user-scoped queries | Postgres, OpenAI, CrossEncoder | Tools + API routes |
| **Postgres Flex B1ms + pgvector** | Durable state: postings, chunks, user_profile, embeddings | — | ACA env outbound (asyncpg) |
| **Azure Key Vault** | Secret material | — | ACA managed identity |
| **Azure Container Registry** | Docker image storage | — | GitHub Actions push, ACA pull |
| **Entra External ID tenant** | Identity, JWT issuance, app registrations | — | SPA (authorize), FastAPI (JWKS fetch) |
| **GitHub Actions** | Build, test, deploy orchestration | Azure ARM via OIDC, ACR, SWA deploy endpoint | git push / manual dispatch |
| **Log Analytics workspace** | Log storage, KQL queryable | — | ACA env diagnostic pipe |

---

## Data Flow: User Asks a Question in Chat

```
[User types query, hits enter]
        │
        ▼
[SPA] acquireTokenSilent({ scopes: [api://.../Access.All] })  ──► [Entra] returns JWT
        │
        ▼
[SPA] fetch("/agent/stream", { headers: { Authorization: "Bearer <jwt>" } })
        │
        ▼
[Envoy ingress]  validates 240s timeout, passes through
        │
        ▼
[FastAPI middleware]
    ├─ CORSMiddleware: origin matches allowlist? ✓
    └─ fastapi_azure_auth: verify JWT vs cached JWKS ✓
    └─ only_seeded_user: oid == SEED? ✓ → user_id resolved
        │
        ▼
[Route handler /agent/stream]
    ├─ Start heartbeat task (yields every 15s)
    ├─ asyncio.wait_for(stream_agent(query, user_id=..., career_id=...), 60)
    │       │
    │       ▼
    │   [LangGraph ReAct loop]
    │       └─ calls search_jobs tool
    │           └─ search_postings(session, query, user_id=...)
    │               ├─ OpenAI embedding (one call)
    │               ├─ pgvector top-20 scan, user_id-filtered
    │               └─ asyncio.to_thread(rerank, top-20) → top-5
    │       └─ LLM synthesis; yields tokens as they arrive
    │
    └─ StreamingResponse yields:
           event: tool_start / tool_end (chips in UI)
           event: token (incremental text)
           event: heartbeat (every 15s, silently consumed by SPA)
           event: final (end of stream)
        │
        ▼
[SPA ReadableStream reader]  parses SSE events, updates React state
        │
        ▼
[UI] assistant bubble renders token-by-token; tool chips expand on tool_end
```

Heartbeat invisible to the user but critical to ingress idle-timer and to the SPA's liveness indicator (a subtle "thinking" spinner can key off heartbeat cadence).

---

## Build Order Recommendation (for roadmap phasing)

The seven concerns don't all ship at once. Recommended dependency order for phase structure:

**Phase N — Backend prep (pure refactor, no new surfaces).** Can run fully in parallel with any frontend scaffolding work.
- Add Alembic; run the user_id + career_id migration (§7).
- Define `IngestionSource` Protocol; migrate markdown reader (§8).
- Preload reranker in lifespan; wrap in `asyncio.to_thread` (§3).
- Pydantic SSE event schema + heartbeat + 60s agent timeout (§3).
- CORS middleware with env-allowlist (§2).
- Replace `/data/profile.json` load with DB-backed `user_profile` table fetch.

**Phase N+1 — Infra bootstrap (Terraform + Entra).** Must happen before auth work can be tested end-to-end.
- Bootstrap state backend (manual az step).
- Provision Entra External ID tenant + SPA + API app registrations (§4).
- Provision the RG + LAW + ACR + KV + Postgres Flex + ACA env + ACA + SWA (§5).
- Seed Adrian's user row with real `entra_oid` (one-shot post-deploy).

**Phase N+2 — GitHub Actions OIDC (CI/CD glue).**
- Federated credentials on the app registration (§6).
- `workflow-tf.yml`, `workflow-api.yml`, `workflow-spa.yml`.

**Phase N+3 — SPA shell + auth.** Now Entra + API + infra exist, so MSAL can do a real round-trip.
- Vite+React scaffolding, Tailwind + shadcn.
- MSAL React, login wall, token acquisition.
- FastAPI side: swap `require_api_key` for `fastapi-azure-auth` (§4).
- One protected endpoint working end-to-end (e.g., `/health-authed`).

**Phase N+4 — Dashboard widgets.** Analytical SQL endpoints + filter-bar UI. Independent of chat.

**Phase N+5 — Chat SSE integration.** SPA fetch-reader pattern; SSE event parsing against typed schema generated from OpenAPI.

**Phase N+6 — Profile + resume upload.** Uses the ingestion Protocol from N.

**Phase N+7 — RAGAS eval in CI** and observability wiring. Terminal polish.

Phases N, N+1, N+2 can overlap. Phase N+3 blocks N+4 and N+5 (no auth → no dashboard). Phase N+4 and N+5 are independent and can overlap. Phase N+7 hooks into all and ships last.

---

## Anti-Patterns for This Architecture

### Anti-Pattern 1: letting the SPA hold internal `user_id`
**What people do:** pass the internal UUID into API calls as a header or query param.
**Why wrong:** it becomes a trust boundary the frontend owns. Swap `user_id` in DevTools → access other users.
**Instead:** internal `user_id` is derived from the validated JWT's `oid` claim, backend-only. SPA only knows the Entra token.

### Anti-Pattern 2: using `allow_credentials=True` on CORS plus Bearer tokens
**What people do:** copy-paste a CORS config that sets `allow_credentials=True` without checking.
**Why wrong:** bearer tokens don't need credentials mode; enabling it forces preflight complexity and blocks wildcard origins.
**Instead:** `allow_credentials=False`, specific origin allowlist, `Authorization` in `allow_headers`.

### Anti-Pattern 3: using `EventSource` with a tokenised URL
**What people do:** `new EventSource('/agent/stream?token=' + jwt)` because EventSource can't set headers.
**Why wrong:** tokens leak to server logs, browser history, referer headers.
**Instead:** `fetch('/agent/stream', { headers: { Authorization: ... } })` + manual `ReadableStream` SSE parser.

### Anti-Pattern 4: running the cross-encoder in the async event loop
**What people do:** call `reranker.predict(...)` directly from an async handler because "it's fast enough."
**Why wrong:** it's 100–300ms of blocking CPU work that freezes the heartbeat task and stalls every other in-flight request.
**Instead:** `await asyncio.to_thread(reranker.predict, pairs)`.

### Anti-Pattern 5: mixing workforce and CIAM tenant Terraform providers without aliases
**What people do:** one `azuread` provider with `tenant_id = var.tenant_id` and hope the right tenant is set per resource.
**Why wrong:** silently creates app registrations in the wrong tenant; SPA cannot discover its own clientId; debugging is brutal.
**Instead:** `provider "azuread" { alias = "workforce", ... }` + `provider "azuread" { alias = "ciam", ... }` and every `azuread_application` explicitly selects its provider.

### Anti-Pattern 6: CORS preflight failing in prod because `OPTIONS` isn't in allowed methods
**What people do:** set `allow_methods=["GET", "POST"]` and wonder why every non-GET dashboard call 405s.
**Why wrong:** preflight needs `OPTIONS`; FastAPI's `CORSMiddleware` handles it but only if listed.
**Instead:** `allow_methods=["GET", "POST", "OPTIONS"]` or `allow_methods=["*"]` in prod.

### Anti-Pattern 7: letting Terraform own the Docker image reference
**What people do:** declare the Container App's `image = "acr.../job-rag:v1"` in TF, then change the tag on every deploy and run `terraform apply`.
**Why wrong:** entangles app deploys with infra state; deploys are slow; state drift bugs surface on every push.
**Instead:** Terraform sets an initial placeholder image; `az containerapp update --image` in the deploy workflow drives subsequent deploys. `lifecycle { ignore_changes = [template[0].container[0].image] }` on the TF resource.

---

## Integration Points

### External services crossing the architecture boundary
| Service | Who initiates | Pattern | Failure mode |
|---|---|---|---|
| Entra authorize endpoint | SPA (MSAL) | Browser redirect | User can't sign in — HTTP to SPA still works but protected routes 401 |
| Entra JWKS endpoint | FastAPI | Lazy fetch + cache | Auth fails on startup if reachable; after cache warm, survives Entra outage up to cache TTL |
| OpenAI API | FastAPI (services layer) | openai python SDK, retries via tenacity | Agent fails; existing Langfuse traces capture this |
| Langfuse | FastAPI (observability) | Fail-open wrapper | No impact on user-facing flow |
| Postgres Flex | FastAPI (asyncpg) | Connection pool in `db/engine.py` | API 500 on connection exhaustion; health check catches it |
| Azure Container Registry | GitHub Actions (build) + ACA (pull) | Docker push/pull over HTTPS with MI auth | Deploy fails in CI; running app unaffected |
| Key Vault | ACA (secret reference) | `keyVaultUrl` syntax resolved at container start | Container fails to start; previous revision keeps serving |

### Internal boundaries worth documenting
| Boundary | Contract | Breakage risk |
|---|---|---|
| SPA ↔ FastAPI | OpenAPI JSON + generated TS types | Medium — schema drift if OpenAPI regen missed |
| FastAPI route ↔ services layer | Async function signatures + Pydantic models | Low — all in the same codebase |
| services ↔ DB | SQLAlchemy ORM | Medium — Alembic migrations mandatory |
| FastAPI ↔ Entra | JWT validation (aud, iss, sig) | Low — fastapi-azure-auth handles; CIAM tenant id rotation is rare |
| Ingestion Protocol ↔ sources | `RawPosting` dataclass | Low — sources are independent; Protocol is duck-typed |

---

## Where the Existing Architecture Needs Changes vs Where New Surfaces Sit Alongside

### Changes to existing code (not additions)
| Existing | Change required | File |
|---|---|---|
| `src/job_rag/api/app.py` | Add CORS middleware; add lifespan that preloads reranker | app.py |
| `src/job_rag/api/auth.py` | Replace `require_api_key` with `fastapi-azure-auth` scheme; keep legacy path behind `AUTH_MODE` flag | auth.py |
| `src/job_rag/api/routes.py` | Add JWT dep to every route; add SSE Pydantic event models; add timeout wrapper to `/agent/stream`; thread `user_id` into service calls | routes.py |
| `src/job_rag/services/retrieval.py` | Wrap `rerank()` in `asyncio.to_thread` at call sites; accept `user_id` parameter | retrieval.py |
| `src/job_rag/services/matching.py` | Replace `load_profile()` file read with DB query; accept `user_id` | matching.py |
| `src/job_rag/services/ingestion.py` | Introduce `IngestionSource` Protocol; existing `ingest_directory` becomes `MarkdownFileSource` wrapper; accept `user_id, career_id` | ingestion.py |
| `src/job_rag/db/models.py` | Add `UserProfileDB`; add `user_id`, `career_id` columns to posting/chunk tables | db/models.py |
| `src/job_rag/db/engine.py` | Leave sync engine; init_db replaced by `alembic upgrade head` in CLI and deploy workflow | engine.py |
| `src/job_rag/agent/stream.py` | Add heartbeat generator; structure events as typed Pydantic models | stream.py |
| `src/job_rag/cli.py` | `init-db` command delegates to alembic; `ingest` uses `MarkdownFileSource` explicitly | cli.py |

### New surfaces sitting alongside (no changes to existing files)
- `src/job_rag/auth/` — new package for Entra-aware user-resolution dependency. Keep separate from legacy `api/auth.py`.
- `src/job_rag/api/dashboard.py` — new analytical SQL endpoints (top skills, salary bands, CV-vs-market).
- `src/job_rag/api/profile.py` — new resume-upload + profile CRUD endpoints.
- `alembic/` — new directory at repo root; `alembic/env.py` imports `from job_rag.db.models import Base`.
- `infra/` — new directory (Terraform). Untouched by any application code.
- `.github/workflows/` — three new workflows; existing CI preserved (likely extended to run `alembic upgrade` against a throwaway DB in tests).
- `frontend/` — brand-new directory. Pure addition.

---

## Scaling Considerations (for roadmap sanity, not urgent)

| Scale | Architecture adjustment |
|---|---|
| Current (1 user, ~108 postings) | Works as designed. B1ms Postgres, consumption ACA, SWA Free. |
| 10 users / 10k postings | Still single B1ms. Add pgvector HNSW index (already on roadmap). Bump ACA min-replicas=1 to kill cold starts. |
| 100 users / 100k postings | Add a Redis cache for per-user top-k results (CONCERNS.md #10). Split embedding batching (CONCERNS.md gap). Move reranker to a separate ACA containing just the model. |
| 1000+ users | Private networking + vnet integration. SWA Standard with linked backend. Postgres tier upgrade. Dedicated Langfuse cloud. |

Not a pressing concern for v1 — but the hedge layer (`user_id`, `career_id`, Entra tenancy, Protocol-based ingestion) keeps every one of these future moves cheap.

---

## Sources

Verified with Azure official documentation and established Python libraries:

- [API support in Azure Static Web Apps with Azure Container Apps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/static-web-apps/apis-container-apps) — confirms linked-backend semantics, Standard plan requirement, single-SWA-link constraint
- [Ingress in Azure Container Apps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview) — Envoy ingress architecture, HTTP/2 support
- [Troubleshooting ingress issues on Azure Container Apps — Azure OSSD](https://azureossd.github.io/2023/03/22/Troubleshooting-ingress-issues-on-Azure-Container-Apps/) — confirms 240s request timeout default, streaming behavior
- [How to Enable Premium Ingress for Azure Container Apps & Configure Timeout Settings — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2284383/how-to-enable-premium-ingress-for-azure-container) — premium ingress idle-timeout flag (`--request-idle-timeout`)
- [Scaling in Azure Container Apps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-apps/scale-app) — minReplicas=0 semantics
- [Reducing cold-start time on Azure Container Apps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-apps/cold-start) — cold-start mitigation patterns
- [Authentication flow support in MSAL — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity-platform/msal-authentication-flows) — auth-code + PKCE canonical pattern for SPAs
- [fastapi-azure-auth — intility GitHub + PyPI](https://github.com/intility/fastapi-azure-auth) — mature FastAPI lib for Entra JWT validation (External ID supported 5.x)
- [Authenticate to Azure from GitHub Actions by OpenID Connect — Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect) — OIDC federated credential setup
- [Azure Verified Module: Container App — Terraform Registry](https://registry.terraform.io/modules/Azure/avm-res-app-containerapp/azurerm/latest) — recommended AVM module
- [Azure Verified Module: Static Web App — GitHub](https://github.com/Azure/terraform-azurerm-avm-res-web-staticsite) — recommended AVM module
- [Alembic Operation Reference](https://alembic.sqlalchemy.org/en/latest/ops.html) — `server_default`, UUID migration patterns
- [Server-sent events on Azure — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5573038/issues-with-sse-(server-side-events)-on-azure-app) — SSE heartbeat recommendation (15–30s cadence)

Existing project context:
- `.planning/PROJECT.md` — Active requirements, Key Decisions, Constraints
- `.planning/codebase/ARCHITECTURE.md` — existing backend three-tier model
- `.planning/codebase/CONCERNS.md` — blockers 1–7 for web UI (all addressed above)
- `.planning/codebase/STRUCTURE.md` — where to slot new code
- `.planning/codebase/INTEGRATIONS.md` — existing OpenAI / Postgres / Langfuse integration points

---

*Architecture research for: web-app + Azure milestone on job-rag*
*Researched: 2026-04-23*
