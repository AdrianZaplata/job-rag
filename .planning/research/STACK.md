# Stack Research

**Domain:** Vite + React SPA + FastAPI + Azure Container Apps + Azure DB for PostgreSQL + Entra ID External Identities + Terraform (Azure free tier)
**Researched:** 2026-04-23
**Overall Confidence:** HIGH
**Scope:** NEW elements added by this milestone only. The backend stack (FastAPI, LangGraph, SQLAlchemy async, Instructor, Langfuse, pgvector, OpenAI, Typer, FastMCP) is frozen and not re-researched — see `.planning/codebase/STACK.md`.

---

## 1 · Frontend SPA

### Recommended

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Vite | 8.0.x | Dev server + production bundler | v8 is the current stable line (v8.0.9 at time of research). v7 is maintenance-only; v6 is security-patch-only. v8 requires Node 20.19+ or 22.12+. Confidence: HIGH — verified on vite.dev. |
| React | 19.2.x | UI library | 19.2 is the current stable (released Oct 2025). Brings `Activity` component, `useEffectEvent`, partial pre-rendering. MSAL React v5.3.x already declares `^19.2.1` in peer deps. Confidence: HIGH. |
| TypeScript | 5.x (latest 5.9+) | Static types | Vite 8 template ships with TS 5.x; no reason to pin below latest. Use `strict: true` and `"moduleResolution": "bundler"`. |
| Tailwind CSS | 4.2.x | Utility-first CSS | v4 is the current line, ships the `@tailwindcss/vite` plugin instead of a PostCSS pipeline. Single `@import "tailwindcss"` replaces the old `@tailwind base/components/utilities` triple. Confidence: HIGH — verified on tailwindcss.com. |
| `@tailwindcss/vite` | latest | Tailwind v4 Vite integration | Replaces the PostCSS-based setup used in Tailwind v3. |
| shadcn/ui | CLI `@latest` (no canary) | Component library (copy-paste primitives) | Stable CLI now supports Vite + Tailwind v4 + React 19 as first-class (CLI v4, March 2026). Canary is no longer required. New projects default to `new-york` style and `data-slot` attributes. Confidence: HIGH — verified on ui.shadcn.com. |
| Radix UI primitives | latest | Unstyled a11y primitives | Pulled in transitively by shadcn/ui; no direct dependency management usually needed. |
| lucide-react | latest | Icon set | shadcn/ui default icon library. Tree-shakeable SVGs. |
| class-variance-authority | latest | Variant-driven class composition | shadcn/ui uses `cva` for component variants. |
| clsx + tailwind-merge | latest | `cn()` utility | The shadcn/ui-generated `lib/utils.ts` helper. |
| `@azure/msal-react` | 5.3.1 (Apr 21 2026) | Auth UI components + hooks for React | Official Microsoft library. Versions 5.1.0+ added React 18 support; 5.2.0 extended peer range; 5.3.x is current. Peer deps: `@azure/msal-browser ^5.8.0`, `react ^16.8.0 \|\| ^17 \|\| ^18 \|\| ^19.2.1`. Confidence: HIGH — verified on GitHub CHANGELOG. |
| `@azure/msal-browser` | 5.8.x | Underlying MSAL.js browser client | Bumped alongside msal-react. Uses PKCE auth code flow by default (the only SPA-sane flow). |
| `@tanstack/react-query` | 5.x | Server-state cache / fetcher | Preferred over `useEffect` + `fetch` (React 19 explicitly discourages `useEffect` data fetching). Handles loading/error/stale/refetch semantics for the dashboard and chat flows. |
| Vitest | 3.x | Unit + component tests | Native Vite test runner; faster than Jest; same transform pipeline. |
| React Testing Library | latest | Component behaviour assertions | Pair with Vitest. Renders components with user-centric queries. |

### Dev tooling

| Tool | Purpose |
|------|---------|
| ESLint + `typescript-eslint` v8 | Lint TS + React. Use flat config (`eslint.config.js`). |
| Prettier | Format. Not strictly required (Biome is an alternative) but aligns with most dev stacks. |
| TypeScript path aliases | Configure `@/*` → `src/*` in both `tsconfig.json` and `vite.config.ts` (`resolve.alias`). |

### Installation

```bash
# 1. Scaffold Vite + React + TS
npm create vite@latest apps/web -- --template react-ts

# 2. Tailwind v4
cd apps/web
npm install tailwindcss @tailwindcss/vite

# 3. shadcn/ui (stable @latest — no canary needed)
npx shadcn@latest init -t vite

# 4. Add first components
npx shadcn@latest add button card input dialog skeleton

# 5. Auth
npm install @azure/msal-react @azure/msal-browser

# 6. Data fetching + icons (shadcn pulls lucide-react but pin it explicitly)
npm install @tanstack/react-query lucide-react

# 7. Dev deps
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event \
  eslint typescript-eslint prettier
```

### Anti-choices

| Avoid | Why | Use instead |
|-------|-----|-------------|
| Next.js | Constraints list bans it explicitly. The educational goal demands the frontend cannot silently colocate backend logic; Next.js API routes would blur the split. | Vite SPA + separate FastAPI. |
| Create React App | Deprecated by the React team in early 2025; no v19 support; Webpack is slower than Vite. | Vite. |
| Tailwind CSS v3 | v4 is the current line; v3 uses PostCSS config + `@tailwind` triple-import that shadcn/ui's new primitives no longer emit. Starting a new project on v3 buys legacy docs. | Tailwind v4 via `@tailwindcss/vite`. |
| `npx shadcn@canary` | Stable was sufficient as of March 2026 (CLI v4 release). Canary is now only needed for features that haven't shipped. | `npx shadcn@latest`. |
| MSAL 1.x / `msal` package | Deprecated — that's the pre-v2 package. | `@azure/msal-react` + `@azure/msal-browser` (both v5). |
| Redux / Zustand for server state | Chat + dashboard state is mostly server state, not shared client state. Mis-modeling server state in a client-state store is the classic React over-engineering tax. | React Query for server state; `useState`/`useReducer` for local UI state. |
| Implicit flow / hybrid flow for SPAs | Deprecated by OAuth 2.1 and by MSAL itself. | PKCE (auth code with PKCE) — the MSAL default. Don't override it. |
| MUI / Chakra / AntD | Not aligned with the Linear-dense aesthetic decision. Heavy runtimes; overrides fight Tailwind. | shadcn/ui + Tailwind. |

---

## 2 · Azure Services (free-tier-first)

### Recommended services

| Service | Tier | Purpose | Why |
|---------|------|---------|-----|
| Azure Container Apps (Consumption) | Scale-to-zero | Host FastAPI | Monthly free grant per subscription: **180,000 vCPU-seconds + 360,000 GiB-seconds + 2 million requests**. With `min_replicas = 0` this is effectively free for a single-user app. Confidence: HIGH — verified on azure.microsoft.com/pricing/details/container-apps. |
| Azure Static Web Apps (Free) | Free | Host the Vite build output + global CDN | Free SKU includes 100 GB bandwidth/mo, 0.5 GB app storage, free managed TLS, free custom domain, built-in GitHub Actions deploy. Confidence: HIGH — verified on learn.microsoft.com/azure/static-web-apps/plans. |
| Azure Database for PostgreSQL Flexible Server | Burstable `B_Standard_B1ms` | Primary datastore | Azure Free account covers **750 hours/month of B1ms + 32 GB storage for 12 months** — enough for continuous operation. B1ms has 1 vCPU, 2 GiB RAM. pgvector is generally available (0.7.0+ on the allowlist). Confidence: HIGH — verified on learn.microsoft.com/azure/postgresql. |
| Azure Key Vault | Standard | Store `OPENAI_API_KEY`, DB password, Langfuse keys | ~€0.03/10k operations; trivial cost for a single-user app. Inject into Container Apps via `secrets` + `env.secretRef`, not literals. |
| Azure Container Registry (Basic) **or** GitHub Container Registry (ghcr.io) | Basic / free | Host API image | See Recommendation below. |
| Log Analytics Workspace | PAYG | Sink for Container Apps logs | First 5 GB/mo ingestion free. Required by Container Apps Environment. |

### Container Registry recommendation

**Recommendation: GitHub Container Registry (ghcr.io).**

| Factor | ACR Basic | GHCR |
|--------|-----------|------|
| Monthly cost at zero usage | ~$5 (no free tier) | $0 (public) / $0 (private while pulled from GH Actions) |
| Pulls via GitHub Actions | Standard image pull | Guaranteed free egress |
| IAM integration with Azure | Native via managed identity | Requires Container Apps registry credential (PAT or GH Actions OIDC → short-lived token) |
| Learning signal for portfolio | "Used ACR" | "Used GHCR, saved ~€60/yr" |

ACR's only meaningful wins are private-registry replication and managed-identity-based image pull for Container Apps. At this project's scope, neither justifies €5/mo. Choose GHCR unless the constraint explicitly requires ACR as an Azure-native artefact for the portfolio story.

### Frontend hosting decision — SWA vs Container Apps

**Use Static Web Apps for the SPA, Container Apps for the API.** The SPA is a pure static bundle (Vite output in `dist/`); shipping it through Container Apps would waste the scale-to-zero budget on static-file serving. SWA's built-in CDN, free TLS, and `staticwebapp.config.json` navigation fallback (for the React Router 404 → `index.html`) are exactly what a SPA needs.

### Anti-choices

| Avoid | Why | Use instead |
|-------|-----|-------------|
| Azure App Service (Linux, B1) | ~€13/mo minimum; no scale-to-zero; no free grant. | Container Apps (Consumption) with `min_replicas = 0`. |
| Azure Kubernetes Service (AKS) | Explicitly out of scope in PROJECT.md. ~€75/mo for the control plane on the default offering. | Container Apps. |
| Azure Cosmos DB for PostgreSQL | Higher cost; overkill for 108 postings + one user; no Burstable SKU. | Flexible Server B1ms. |
| Cosmos DB (core / Mongo / Gremlin) | Different API; loses Postgres + pgvector; loses existing SQLAlchemy models. | Postgres Flexible Server. |
| Azure Functions for the API | Stateless Functions force rewriting the LangGraph agent lifespan; cold starts worse than Container Apps; no persistent cross-encoder reloading. | Container Apps. |
| Storage Account static website + Front Door | Cheaper per-GB but no integrated auth, no free managed TLS on the custom domain, and no CI artefact handoff. | Static Web Apps (Free). |
| Azure AD B2C | **End of sale May 1 2025**; P2 is being retired March 15 2026 (auto-downgraded to P1); full deprecation by May 2030. Microsoft's own FAQ redirects new CIAM workloads to Entra External ID. | Entra External ID. |
| Azure SQL Database Free | Single-DB free tier (~100k vCore-sec/mo) exists, but you lose PostgreSQL and pgvector and have to rewrite the entire data layer. | Postgres Flexible Server B1ms. |

---

## 3 · Identity — Entra ID External Identities

### Recommended

| Component | Configuration | Why |
|-----------|---------------|-----|
| Entra External Tenant (not workforce) | New "external" tenant configuration via Entra admin center / Terraform | External tenant = the new CIAM tenant type that replaces B2C. Workforce tenant is for employees; external is for customers. Microsoft's own FAQ: "Azure AD B2C … continue supporting until at least May 2030" but "End of Sale: May 1 2025" and "Entra External ID is our next-generation CIAM platform." Confidence: HIGH — verified on learn.microsoft.com/entra/external-id/customers/faq-customers. |
| SPA app registration | Platform: **Single-page application**, Redirect URI = `https://<swa-hostname>/`, Implicit grant **off**, PKCE on (default). | Registers the Vite SPA as a public client. PKCE + auth code is the only sanctioned SPA flow. |
| API app registration | Platform: Web API (no redirect URI). Exposes **one scope** — e.g. `access_as_user`. Application ID URI = `api://<guid>`. | Separates "who the user is" (tokens minted for the SPA's client ID) from "what they can access" (tokens audienced to the API's app ID). |
| API permission on SPA registration | Delegated `access_as_user` scope against the API registration, admin-consented. | Lets the SPA acquire an access token with the API as audience. |
| API token validation | Validate `iss`, `aud`, `exp`, signature via `PyJWT` + `jwks_client` against the tenant's JWKS endpoint. | FastAPI middleware reads `Authorization: Bearer <access_token>`, validates, extracts `oid` (stable user GUID) → maps to `user_id` column. |
| User seeding | Adrian's Entra `oid` is the only row in `user_profile`. | Matches the constraint "single user in v1, structurally multi-user." |

### Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `@azure/msal-react` | 5.3.1 | React hooks + `MsalProvider` + `AuthenticatedTemplate` / `UnauthenticatedTemplate`. |
| `@azure/msal-browser` | 5.8.x | Underlying PublicClientApplication. |
| `PyJWT[crypto]` | 2.9+ | RS256 JWT signature validation (Python). |
| `jwcrypto` or `authlib` | optional | Alternative JWT libs if PyJWT limits surface; PyJWT + `cryptography` is sufficient. |

### Flow (one diagram)

```
User → SPA (Vite build hosted on SWA)
     → MSAL loginRedirect → Entra External tenant authority
       (https://<tenant>.ciamlogin.com/<tenant>.onmicrosoft.com/)
     → user signs in (email / social IdP)
     → tenant returns ID token + auth code
     → MSAL exchanges code + PKCE verifier for access token
       (audience = api://<api-app-id>, scope = access_as_user)
     → SPA calls FastAPI with `Authorization: Bearer <access_token>`
     → FastAPI validates signature against tenant JWKS, extracts `oid`
     → Application logic proceeds under user_id = oid
```

### Anti-choices

| Avoid | Why | Use instead |
|-------|-----|-------------|
| Azure AD B2C | End of sale May 1 2025; P2 retirement March 15 2026; active migration guidance to External ID. Building new B2C tenants in 2026 is building to a five-year sunset on day one. | Entra External ID (external tenant). |
| Workforce tenant with guest invites | Wrong model for end-user sign-up; invite flow breaks self-service; licensing weird. | External tenant. |
| Confidential-client (client secret) for the SPA | SPA can't store secrets — that's the whole point of "public client." Anyone who views the bundle reads the secret. | Public client + PKCE. |
| Implicit grant / hybrid grant | Deprecated by OAuth 2.1; MSAL has not defaulted to implicit since v2. | Auth code + PKCE (MSAL default). |
| Rolling your own JWT validation from `jwt.decode(token, verify=False)` | Timing-independent; trivially spoofable. | `PyJWT` with `options={"verify_signature": True}` + JWKS client with kid-based key lookup. |
| Custom policies (XML) | External ID deliberately replaces B2C custom policies with simpler "user flows" and server-side extensions. Writing custom policies now is writing legacy. | Default user flows; custom authentication extensions only if needed later. |
| Native authentication for this v1 | Useful for mobile apps with pixel-perfect auth UI; overkill for a web SPA with one user. | Browser redirect flow via MSAL. |

### Flagged risk

**The External ID admin UX is new and still changing.** Some portal paths moved between Entra ID blade and dedicated External ID blade during 2025–2026. When wiring Terraform, prefer referring to resource types directly rather than copy-pasting portal click-paths from older tutorials. See `PITFALLS.md` for concrete mitigations.

---

## 4 · Infrastructure as Code — Terraform

### Recommended

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Terraform CLI | 1.9+ (stable) | IaC runner | OpenTofu is a viable fork, but Terraform CLI has broader tutorial coverage and the `azurerm` provider is developed against it. |
| `hashicorp/azurerm` provider | **~> 4.69** (latest as of Apr 16 2026) | Azure resource primitives | v4 line is current; v4 introduced provider-defined functions and a rewrite of many resources. v3 is in maintenance. Container App resources have been in `azurerm` since v3.43; no `azapi` dependency needed for standard workloads. Confidence: HIGH — verified on github.com/hashicorp/terraform-provider-azurerm/releases. |
| `hashicorp/azuread` provider | ~> 3.x | App registrations, service principals, federated credentials | Distinct provider for Entra ID; `azurerm` does not cover app registrations. |
| `hashicorp/random` | ~> 3.x | Random password / suffix generation | Seeds DB passwords before handing them to Key Vault. |
| `hashicorp/null` | ~> 3.x | Occasional glue | e.g. for `local-exec` bootstrapping of pgvector extension (or use `postgresql` provider). |
| (optional) `cyrilgdn/postgresql` provider | ~> 1.25 | `CREATE EXTENSION vector` over the admin connection | Alternative to shelling out via `az postgres flexible-server execute`. Pick one; don't use both. |

### Workspace pattern

PROJECT.md locks "Terraform workspaces (dev + prod) from day 1." Concrete layout:

```
infra/
├── backend.tf            # remote state in Azure Storage (not local)
├── provider.tf           # azurerm + azuread, feature flags, subscription_id
├── variables.tf          # tfvars-backed inputs per workspace
├── locals.tf             # naming convention, tags
├── network.tf            # Container Apps Environment, VNet if needed
├── database.tf           # Postgres Flexible Server, pgvector allowlist
├── compute.tf            # Container App, env vars, secrets from Key Vault
├── identity.tf           # Entra app registrations, federated credentials, scopes
├── kv.tf                 # Key Vault + secret resources
├── swa.tf                # Static Web App + deployment token
├── monitoring.tf         # Log Analytics workspace, diagnostic settings
├── dev.tfvars
└── prod.tfvars
```

Remote state in Azure Storage (blob + state lock container), not local — prevents state loss and enables CI drift detection.

### Terraform workflow

```bash
terraform init
terraform workspace new dev     # one-time
terraform workspace new prod    # one-time

# day-to-day
terraform workspace select dev
terraform plan  -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

`terraform.workspace` flows into `locals.tf` to build resource names (e.g. `jobrag-api-${terraform.workspace}`) so dev + prod cohabit one subscription cleanly.

### Anti-choices

| Avoid | Why | Use instead |
|-------|-----|-------------|
| Bicep / ARM templates | PROJECT.md constraint: Terraform only. Portfolio value of Terraform > Bicep for the non-Azure-only market. | Terraform. |
| Azure CLI / PowerShell scripts for provisioning | No drift detection; no state; no plan output. | Terraform. |
| Local state file | Lost on laptop loss; no concurrency control; leaks secrets in `terraform.tfstate`. | Remote state in Azure Storage with state lock. |
| `azapi` provider for standard resources | Needed only for preview features not yet in `azurerm`. Everything this milestone touches is in `azurerm` v4. | `azurerm` v4. |
| `azurerm` v2 or v3 | v4 is current; v3 is maintenance-only; migration costs grow the longer you wait. | `~> 4` constraint with regular bumps. |
| One monolithic `main.tf` | Unreadable, terrible diffs, impossible code review. | Split by concern (network, database, compute, identity, etc.). |
| Per-environment branches in git | Promotion becomes merge conflicts. | Workspaces + tfvars files; single branch. |
| Terraform modules published to a public registry for this one project | Over-engineering for a single-repo deployment. | Inline resources in `infra/`. |

---

## 5 · CI/CD — GitHub Actions + OIDC federation

### Recommended

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| GitHub Actions workflows | N/A | CI + CD orchestration | Native GitHub, free for public repos, 2000 free minutes/mo on private. |
| `azure/login@v2` | v2 | Azure auth step | OIDC mode: no client secret, short-lived token issued per job. |
| Entra App registration for CI | — | Trust boundary | One app registration with **federated identity credentials** scoped per GitHub ref (e.g. one for `refs/heads/master`, one for `environment:prod`). |
| Role assignments | `Contributor` on the resource group + `AcrPush` (if ACR) or no role for GHCR | RBAC | Never `Owner` at subscription. Scope the role to the specific resource group. |
| `azure/static-web-apps-deploy@v1` | v1 | SPA deploy | Uses the SWA deployment token — short-lived, issued per deploy. |
| `docker/login-action@v3` + `docker/build-push-action@v6` | latest | API image build/push | Push to GHCR by default; ACR only if chosen above. |
| `hashicorp/setup-terraform@v3` | v3 | Terraform CLI on runners | |
| `actions/setup-python@v5` | v5 | Python for eval job | |
| `astral-sh/setup-uv@v5` | v5 | uv for the Python project | Matches the dev toolchain (uv is the package manager in `pyproject.toml`). |

### Workflow shape

- **`ci.yml`** (on PR): ruff, pyright, pytest (unit), npm `lint`+`test`+`build`, terraform `fmt -check` + `validate`, RAGAS eval vs a dev env (see §6).
- **`deploy-infra.yml`** (on push to `master`, `workflow_dispatch`): OIDC login → `terraform apply -auto-approve -var-file=prod.tfvars` behind a protected environment with manual approval.
- **`deploy-api.yml`** (on push to `master`, `paths: src/**`): OIDC login → build image → push to GHCR → `az containerapp update --image ...`.
- **`deploy-spa.yml`** (on push to `master`, `paths: apps/web/**`): `npm ci`, `npm run build`, `azure/static-web-apps-deploy` with the SWA token from GH secrets.

### OIDC setup recipe

```hcl
resource "azuread_application" "github_actions" {
  display_name = "jobrag-gha"
}

resource "azuread_service_principal" "github_actions" {
  client_id = azuread_application.github_actions.client_id
}

resource "azuread_application_federated_identity_credential" "master" {
  application_id = azuread_application.github_actions.id
  display_name   = "gha-master"
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:<owner>/<repo>:ref:refs/heads/master"
  audiences      = ["api://AzureADTokenExchange"]
}

resource "azurerm_role_assignment" "rg_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github_actions.object_id
}
```

Workflow side:

```yaml
permissions:
  id-token: write    # required for OIDC
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: prod   # protected environment with approval
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

### Anti-choices

| Avoid | Why | Use instead |
|-------|-----|-------------|
| Service principal with long-lived client secret | Rotations are manual, leaks sit in GitHub secrets forever, violates "no long-lived secrets" constraint. | OIDC federated credential. |
| `azure/login` without `id-token: write` | Login will fall back to secret-based auth or fail silently. | Always declare `permissions: id-token: write`. |
| Subscription-scoped role assignment | Blast radius: any resource in the subscription. | Resource-group-scoped `Contributor`. |
| One federated credential per branch with wildcard subjects | Easy to widen accidentally; better to use Azure's newer "flexible federated identity credentials" (pattern-based claims matching) if many branches are needed — but for one master + one env that's unnecessary. | Explicit per-branch / per-environment credentials. |
| Deploying infra, API, and SPA from one workflow | Any failure blocks all three; slow feedback. | Three separate workflows, filtered by `paths`. |
| GitHub Environments without approval gate on `prod` | Any merge to master auto-applies Terraform to prod. | Protected `prod` environment with required reviewers (Adrian). |

---

## 6 · RAG Evaluation — RAGAS

### Recommended

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| `ragas` | **0.4.3** (Jan 13 2026) | RAG + agent evaluation metrics | The PROJECT.md frontmatter mentions 0.2.0+ in existing dev deps, but **the current line is 0.4.x**. Upgrade to 0.4.3. Confidence: HIGH — verified on pypi.org/project/ragas and github.com/explodinggradients/ragas/releases. |
| `ragas.integrations.langgraph` | bundled | Convert LangGraph message lists → RAGAS format | `convert_to_ragas_messages` utility is critical — our agent outputs LangChain `BaseMessage`s, not plain dicts. |
| `datasets` (HuggingFace) | latest | RAGAS's native `EvaluationDataset` container | Standard dep of `ragas`. |
| `langfuse` | 4.1.0 (existing) | Surface eval results | RAGAS scores posted as trace scores via the existing Langfuse client; viewable in the same dashboard as production traces. |

### Metrics to use (from RAGAS 0.4)

For the curated eval set of ~20 queries covering search / match / gaps flows (per Active requirements):

| Metric | What it measures | When it fires |
|--------|------------------|---------------|
| **Faithfulness** | Answer is grounded in retrieved context (no hallucinations) | Every RAG answer |
| **Answer Relevancy** | Answer addresses the user's question | Every RAG answer |
| **Context Precision** | Retrieved chunks that are actually used | Retrieval quality |
| **Context Recall** | Retrieved chunks vs. ground-truth needed chunks | Retrieval completeness (requires references) |
| **ToolCallF1** (agent) | Agent calls the right tools with the right args | ReAct agent flows |
| **AgentGoalAccuracy** | Agent actually achieves the user goal | Multi-step agent runs |
| **TopicAdherence** | Agent stays on the job-market domain | Guardrails |

### API breaking change flags

Between 0.2, 0.3, and 0.4:

- **0.3 → 0.4**: migration to `instructor.from_provider` for universal provider support; many metrics moved to a new `BasePrompt` architecture. Old `Metric.score()` patterns may need updating.
- **0.2 → 0.3**: evaluator LLM wrapping changed; `evaluate(dataset, metrics, llm, embeddings)` signature is the stable form.
- **0.1 → 0.2**: entire API rewrite; anything from an "old" blog post is untrustworthy.

If the existing `pyproject.toml` pins `ragas>=0.2.0,<0.3`, plan a deliberate bump to `ragas>=0.4,<0.5` and re-test the evaluation harness — don't let pip-audit surprise-upgrade it mid-milestone.

### CI integration pattern

- Run the eval set on a **dev Azure environment** seeded with a fixed subset of postings (reproducibility).
- Store baseline scores in `eval/baseline.json` under git.
- Fail the build if any metric drops below `baseline - threshold` (start at 0.05 = 5 points).
- Post per-run scores to Langfuse with the PR SHA as a tag.

### Anti-choices

| Avoid | Why | Use instead |
|-------|-----|-------------|
| RAGAS 0.1.x / 0.2.x in a new project | Three major breaking changes since; tutorials on the internet will mostly lie to you. | 0.4.x. |
| DeepEval | Viable alternative but re-learning curve; RAGAS is already in the dev deps and has the LangGraph integration. | Stay on RAGAS. |
| Hand-rolled metrics from scratch | Reinventing faithfulness/grounding scoring is a full side-project. | RAGAS built-ins. |
| Running eval on production traffic | Expensive; pollutes Langfuse production traces; non-deterministic. | A pinned eval set against a dev deployment. |
| RAGAS + Langfuse + a third eval tool | Three dashboards, three truths, zero clarity. | RAGAS for metrics, Langfuse for trace storage + display. |

---

## 7 · Resume Parsing (PDF + DOCX)

### Recommended

| Library | Version | Purpose | License | Why |
|---------|---------|---------|---------|-----|
| `pypdf` | **6.10.2** (Apr 15 2026) | PDF text extraction | BSD-3-Clause | Pure-Python — no C or GPL dependency to audit. Fastest of the pure-Python options in the 2026 benchmarks (0.024s/doc). Active maintenance; replaces the deprecated `PyPDF2`. Handles structured resumes well enough once combined with Instructor for semantic parsing (we don't rely on layout). Confidence: HIGH — verified on pypi.org/project/pypdf. |
| `python-docx` | **1.2.0** (Jun 2025) | DOCX text + paragraph extraction | MIT | The canonical DOCX library; still actively maintained. Preserves paragraph structure which helps Instructor segment education vs experience. Confidence: HIGH — verified on pypi.org/project/python-docx. |

### Pattern

```python
# resume_reader.py
from pathlib import Path

def extract_text(file_path: Path) -> str:
    if file_path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if file_path.suffix.lower() == ".docx":
        from docx import Document
        doc = Document(str(file_path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError(f"Unsupported file type: {file_path.suffix}")
```

Hand the raw text to the existing Instructor pipeline with a `UserSkillProfile` schema. The extraction quality comes from the LLM + schema, not from PDF layout preservation.

### Anti-choices

| Avoid | Why | Use instead |
|-------|-----|-------------|
| **PyMuPDF / `fitz`** | **AGPL-3.0**. Licensing a closed-source portfolio project under AGPL forces open-sourcing any network-deployed derivative — Adrian's API is network-deployed. Commercial license is per-year paid. Even if benchmarks are slightly better, the license viral risk is not worth it. | `pypdf`. |
| `PyPDF2` | Last release Dec 2022; merged back into `pypdf`; deprecated. | `pypdf` (lowercase). |
| `pdfplumber` | MIT-licensed and good for tables, but slower than `pypdf` (0.10s vs 0.024s) and overkill for resumes — resumes are paragraph-oriented text, not tables. Extra C dependency (`pdfminer.six`) compared to pure-Python `pypdf`. | `pypdf`. Reach for `pdfplumber` only if a resume is table-heavy. |
| `pdfminer.six` directly | Lower-level; pypdf wraps the same patterns with a friendlier API. | `pypdf`. |
| `docx2txt` | Simpler but drops paragraph boundaries → loses section structure → worse Instructor extraction. Unmaintained. | `python-docx`. |
| OCR (`pytesseract`, `paddleocr`) in v1 | Most resumes are text-based PDFs. OCR adds system dependencies (Tesseract binary in the Docker image), increases cold-start time, and adds failure modes. | Skip until a real scanned-resume reaches us. |
| `unstructured` | Heavy dep tree (pulls in NLP models, OCR, etc.); overkill for single-file uploads and conflicts with the CPU-only PyTorch optimization the backend already does. | `pypdf` + `python-docx`. |

### Installation

```toml
# pyproject.toml additions
dependencies = [
  # ... existing deps ...
  "pypdf>=6.10,<7",
  "python-docx>=1.2,<2",
]
```

---

## Version Compatibility Matrix

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| Vite | ^8.0 | Node 20.19+ or 22.12+ | v8 dropped Node 18 support. |
| React | ^19.2.1 | MSAL React ^5.3 | MSAL peer range explicitly bumps to 19.2.1. |
| `@azure/msal-react` | ^5.3 | `@azure/msal-browser` ^5.8 | Bump both together. |
| Tailwind CSS | ^4.2 | `@tailwindcss/vite` latest, shadcn/ui CLI v4 | Don't mix v3 and v4 tooling. |
| shadcn/ui | CLI `@latest` | Tailwind v4 + React 19 | Stable; no canary. |
| `azurerm` Terraform provider | ~> 4.69 | Terraform CLI 1.9+ | Uses provider-defined functions introduced in v4.0. |
| `azuread` Terraform provider | ~> 3.x | `azurerm` ~> 4 | Distinct provider. |
| `ragas` | 0.4.3 | LangGraph 1.1.x (existing), OpenAI SDK 2.x (existing) | 0.4 requires re-testing the eval harness vs 0.2/0.3 API. |
| `pypdf` | ^6.10 | Python 3.9–3.14 | BSD-3-Clause, pure Python. |
| `python-docx` | ^1.2 | Python 3.9+ | MIT. |
| Azure Container Apps | Consumption plan | `min_replicas=0` required for free-tier semantics | Paid-only workload profile SKUs also exist; don't use them. |
| Azure DB Postgres | Flexible Server B1ms | pgvector 0.7.0+ (on allowlist) | Must add `vector` to `azure.extensions` server parameter before `CREATE EXTENSION`. |

---

## Installation — Consolidated

### Backend (Python 3.12, uv)

```bash
# Additions to pyproject.toml dependencies
uv add pypdf python-docx 'ragas>=0.4,<0.5' 'PyJWT[crypto]>=2.9'

# Keep existing optional/dev group for ragas already present
uv sync --all-extras
```

### Frontend (Node 22, npm)

```bash
# In apps/web/
npm create vite@latest . -- --template react-ts
npm install tailwindcss @tailwindcss/vite
npx shadcn@latest init -t vite
npx shadcn@latest add button card input dialog skeleton tabs table select
npm install @azure/msal-react @azure/msal-browser @tanstack/react-query lucide-react
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event \
  eslint typescript-eslint prettier
```

### Infra (Terraform)

```hcl
terraform {
  required_version = ">= 1.9"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.69" }
    azuread = { source = "hashicorp/azuread", version = "~> 3.0" }
    random  = { source = "hashicorp/random",  version = "~> 3.6" }
  }

  backend "azurerm" {
    resource_group_name  = "jobrag-tfstate"
    storage_account_name = "jobragtfstate"
    container_name       = "tfstate"
    key                  = "jobrag.tfstate"
  }
}

provider "azurerm" {
  features {}
}
```

---

## Stack Patterns by Variant

**If the project stays single-user past v1:**
- Skip Entra External ID; use a workforce tenant with Adrian as the only member. Same MSAL wiring.
- Skip RAGAS CI gate on every PR; run it weekly.
- Skip Terraform workspaces; one environment is fine.

**If the project grows to multi-user (platform pivot):**
- Entra External ID scales to 50k MAU free; no change needed.
- Add pgvector IVFFlat indexes (currently likely using flat search at 108 rows).
- Add row-level security or per-query `WHERE user_id = :current_user` audits.
- Bump Postgres tier from B1ms → B2s when query volume grows; pgvector extension carries over.

**If Langfuse self-hosting becomes a constraint:**
- Swap `LANGFUSE_HOST` to a self-hosted instance; no code change required.
- RAGAS can post scores to any Langfuse-compatible endpoint via the same `langfuse` client.

---

## Confidence Assessment

| Element | Confidence | Notes |
|---------|------------|-------|
| Frontend SPA stack | HIGH | Vite 8, React 19.2, Tailwind v4, shadcn/ui stable — all verified on official docs and npm. |
| Azure services | HIGH | Free-tier allowances verified on azure.microsoft.com/pricing. |
| Entra External ID | HIGH | Microsoft's own FAQ page confirms B2C deprecation and positions External ID as the successor. |
| Terraform | HIGH | v4.69 of `azurerm` verified on GitHub releases page, released Apr 16 2026. |
| GitHub Actions + OIDC | HIGH | Official Microsoft + GitHub docs confirm the pattern. |
| RAGAS | HIGH | 0.4.3 verified on PyPI and GitHub releases. API change notes from 0.2 → 0.4 flagged clearly. |
| Resume parsing | HIGH | Versions, licenses, and pure-Python status verified on PyPI. AGPL risk of PyMuPDF verified in vendor docs. |

---

## Sources

### Official docs (HIGH confidence)

- [Vite Releases](https://vite.dev/releases) — v8.0.9 current stable, Node 20.19+/22.12+ required
- [Tailwind CSS — Using Vite](https://tailwindcss.com/docs/installation/using-vite) — v4.2, `@tailwindcss/vite` plugin
- [shadcn/ui — Tailwind v4](https://ui.shadcn.com/docs/tailwind-v4) — stable CLI, no canary required
- [shadcn/ui — Vite installation](https://ui.shadcn.com/docs/installation/vite) — `npx shadcn@latest init -t vite`
- [React 19.2 release blog](https://react.dev/blog/2025/10/01/react-19-2) — Oct 2025 stable
- [@azure/msal-react CHANGELOG](https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-react/CHANGELOG.md) — 5.3.1 on Apr 21 2026
- [@azure/msal-react package.json](https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-react/package.json) — peer deps
- [Entra External ID FAQ](https://learn.microsoft.com/en-us/entra/external-id/customers/faq-customers) — B2C deprecation, External ID positioning, pricing
- [Microsoft's B2C to External ID migration](https://learn.microsoft.com/en-us/entra/external-id/customers/plan-your-migration-from-b2c-to-external-id)
- [Azure Container Apps pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/) — 180k vCPU-s + 360k GiB-s + 2M requests free grant
- [Azure Static Web Apps plans](https://learn.microsoft.com/en-us/azure/static-web-apps/plans) — Free SKU limits
- [Azure PostgreSQL Free account](https://github.com/MicrosoftDocs/azure-databases-docs/blob/main/articles/postgresql/flexible-server/how-to-deploy-on-azure-free-account.md) — 750 hr/mo B1ms + 32 GB for 12 months
- [Azure Container Apps + azurerm](https://techcommunity.microsoft.com/blog/fasttrackforazureblog/can-i-create-an-azure-container-apps-in-terraform-yes-you-can/3570694)
- [terraform-provider-azurerm releases](https://github.com/hashicorp/terraform-provider-azurerm/releases) — v4.69.0 on Apr 16 2026
- [Configuring OIDC in Azure — GitHub Docs](https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure)
- [Authenticate to Azure from GitHub Actions by OpenID Connect](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Enable pgvector in Azure Database for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-use-pgvector)
- [RAGAS releases on GitHub](https://github.com/explodinggradients/ragas/releases) — 0.4.3 on Jan 13 2026
- [RAGAS LangGraph integration](https://docs.ragas.io/en/v0.2.6/howtos/integrations/_langgraph_agent_evaluation/)
- [pypdf on PyPI](https://pypi.org/project/pypdf/) — 6.10.2 on Apr 15 2026, BSD-3-Clause, pure Python
- [pdfplumber on PyPI](https://pypi.org/project/pdfplumber/) — 0.11.9, MIT
- [python-docx on PyPI](https://pypi.org/project/python-docx/) — 1.2.0, MIT
- [PyMuPDF license discussion](https://github.com/pymupdf/PyMuPDF/discussions/971) — AGPL-3.0 / commercial

### Secondary / confirmatory (MEDIUM confidence)

- [React SPA + MSAL + Entra External ID (Microsoft sample)](https://learn.microsoft.com/en-us/samples/azure-samples/ms-identity-ciam-javascript-tutorial/ms-identity-ciam-javascript-tutorial-1-call-api-react/)
- [Tutorial: Prepare a React SPA for authentication (Entra External ID)](https://learn.microsoft.com/en-us/entra/external-id/customers/tutorial-single-page-app-react-sign-in-configure-authentication)
- [Version 4.0 of the Azure Provider — upgrade guide](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/guides/4.0-overview)
- [GitHub Container Registry pricing discussion](https://github.com/orgs/community/discussions/183054)
- [Shadcn/ui March 2026 Update — CLI v4](https://medium.com/@nakranirakesh/shadcn-ui-march-2026-update-cli-v4-ai-agent-skills-and-design-system-presets-d30cf200b0e9)
- [PDF extractor benchmarks 2026](https://unstract.com/blog/evaluating-python-pdf-to-text-libraries/)

---

*Stack research for: Vite + React SPA + Azure Container Apps + Postgres pgvector + Entra External ID + Terraform (free-tier-first)*
*Researched: 2026-04-23*
