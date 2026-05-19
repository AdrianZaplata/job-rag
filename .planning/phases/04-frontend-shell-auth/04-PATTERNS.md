# Phase 4: Frontend Shell + Auth - Pattern Map

**Mapped:** 2026-05-19
**Mapper commit:** 00128ec7b3f38ea10480562b440b83264790e2b8
**Files analyzed:** 60 (6 backend touch points + 38 greenfield frontend files + 9 infra/external files + 2 CI/CD files + 5 doc/correction files)
**Analogs found:** 12 exact / 14 shape-match / 34 greenfield (RESEARCH skeleton)
**Inputs read:** 04-CONTEXT.md (full), 04-UI-SPEC.md (full), 04-RESEARCH.md (headers + §Code Examples 1676-2264 + §Pitfalls index)

---

## File Classification

### Backend (6 files — modify/new)

| File (new/modified) | Role | Data Flow | Closest analog in repo | Match Quality |
|---------------------|------|-----------|------------------------|---------------|
| `src/job_rag/api/auth.py` (REWRITE body) | middleware (FastAPI dependency) | request-response | itself @ HEAD (Phase 1 D-10 skeleton) | exact (self-replace) |
| `src/job_rag/config.py` (4 NEW fields) | config | n/a | itself @ HEAD — `seeded_user_id` + `allowed_origins` field patterns | exact |
| `alembic/versions/0005_adopt_entra_oid.py` (NEW) | migration | batch (DDL) | `alembic/versions/0004_corpus_cleanup.py` + `0002_add_user_profile.py` (idempotent UPDATE with bindparams) | role-match |
| `pyproject.toml` (1 dep add) | config | n/a | existing `[project.dependencies]` block | exact |
| `tests/test_auth.py` (EXTEND) | test | request-response | itself @ HEAD (`TestGetCurrentUserId` skeleton; `pytest.skip` on ImportError lifted) | exact (self-extend) |
| `tests/test_alembic.py` (EXTEND with 0005 smoke) | test | batch | `test_alembic.py::test_0004_upgrade_smoke` / `test_0004_downgrade_smoke` | exact |

### Frontend (38 files — all NEW, greenfield directory `frontend/`)

| File | Role | Data Flow | Closest analog in repo | Match Quality |
|------|------|-----------|------------------------|---------------|
| `frontend/package.json` | config | n/a | none — see RESEARCH §Code Examples lines 2232-2264 (script block) | GREENFIELD |
| `frontend/vite.config.ts` | config | n/a | none — see RESEARCH §`vite.config.ts` lines 929-969 | GREENFIELD |
| `frontend/tsconfig.json` | config | n/a | none — see RESEARCH lines 970-986 | GREENFIELD |
| `frontend/eslint.config.js` | config | n/a | none — see CONTEXT.md §Claude's Discretion + STACK.md §1 (typescript-eslint v8 flat) | GREENFIELD |
| `frontend/index.html` | view (root) | n/a | none — see RESEARCH §Pitfall 10 line 786-810 (inline FOUC-prevention theme script) | GREENFIELD |
| `frontend/src/main.tsx` | entry point | request-response (bootstrap) | none — see RESEARCH §`frontend/src/main.tsx` lines 1028-1084 (D-05 literal AUTH-07 race fix) | GREENFIELD |
| `frontend/src/App.tsx` | component (routes) | request-response | none — see UI-SPEC §6 Route Table + RESEARCH §Pattern 1 lines 463-528 | GREENFIELD |
| `frontend/src/app.css` | config (Tailwind tokens) | n/a | none — see RESEARCH §Tailwind init lines 907-928 + UI-SPEC §4 Color | GREENFIELD |
| `frontend/src/auth/msal.ts` | service (singleton) | request-response | none — see RESEARCH §`frontend/src/auth/msal.ts` lines 987-1027 | GREENFIELD |
| `frontend/src/auth/AuthGate.tsx` | component (guard) | request-response | none — see RESEARCH §`frontend/src/components/AuthGate.tsx` lines 1107-1143; UI-SPEC §5 + §16 | GREENFIELD |
| `frontend/src/api/authedFetch.ts` | service (interceptor) | request-response | none — see RESEARCH §`frontend/src/api/authedFetch.ts` lines 1144-1215 (D-11/D-13) | GREENFIELD |
| `frontend/src/api/readSSEStream.ts` | service (streaming) | streaming | shape-match: `src/job_rag/api/sse.py` Phase 1 `to_sse()` event contract — TS consumer mirrors backend event shape. See RESEARCH §`readSSEStream.ts` lines 1216-1318 | GREENFIELD (shape from backend) |
| `frontend/src/api/health.ts` | service (typed endpoint) | request-response | none — see RESEARCH §D-15 service-module template + CONTEXT.md D-15 | GREENFIELD |
| `frontend/src/api/jobs.ts` | service (typed endpoint) | request-response | none — see RESEARCH §D-15 + Phase 5 forward-compatibility note | GREENFIELD |
| `frontend/src/api/profile.ts` | service (typed endpoint) | request-response | none — see RESEARCH §D-15 + Phase 7 forward-compatibility note | GREENFIELD |
| `frontend/src/api/agent.ts` | service (streaming caller) | streaming | none — see RESEARCH §D-15 + composes with readSSEStream.ts | GREENFIELD |
| `frontend/src/api/types.ts` | generated config | n/a | none — output of `openapi-typescript`; checked-in per D-14 | GREENFIELD (codegen output) |
| `frontend/src/components/AppShell.tsx` | component (layout) | n/a | none — see RESEARCH §`AppShell.tsx` lines 1437-1496 + UI-SPEC §7 (top-nav anatomy) | GREENFIELD |
| `frontend/src/components/ThemeToggle.tsx` | component | event-driven (DOM) | none — see RESEARCH §`ThemeToggle.tsx` lines 1396-1436 + UI-SPEC §14 motion rules | GREENFIELD |
| `frontend/src/components/ErrorBoundary.tsx` | component (boundary) | event-driven | none — see RESEARCH §`ErrorBoundary.tsx` lines 1497-1538 + UI-SPEC §9 | GREENFIELD |
| `frontend/src/components/ErrorBoundaryFallback.tsx` | component (view) | n/a | none — extracted from RESEARCH §ErrorBoundary lines 1497-1538 (presentational sibling) | GREENFIELD |
| `frontend/src/components/RouteSkeleton.tsx` | component (loading) | n/a | none — see RESEARCH §`RouteSkeleton.tsx` lines 1585-1606 + UI-SPEC §11 | GREENFIELD |
| `frontend/src/components/EmptyState.tsx` | component (typed primitive) | n/a | none — see RESEARCH §`EmptyState.tsx` lines 1539-1584 + UI-SPEC §10 typed contract | GREENFIELD |
| `frontend/src/components/PhasePlaceholder.tsx` | component (composition) | n/a | none — see RESEARCH §`PhasePlaceholder.tsx` lines 1539-1584 + UI-SPEC §10 instantiations table | GREENFIELD |
| `frontend/src/routes/AccessDenied.tsx` | component (route) | n/a | none — see RESEARCH §`AccessDenied.tsx` lines 1319-1395 + UI-SPEC §8 + §13 copywriting | GREENFIELD |
| `frontend/src/routes/NotFound.tsx` | component (route) | n/a | none — see UI-SPEC §10 NotFound EmptyState instantiation | GREENFIELD |
| `frontend/src/routes/Dashboard.tsx` | component (route placeholder) | n/a | none — see UI-SPEC §10 PhasePlaceholder Dashboard row | GREENFIELD |
| `frontend/src/routes/Chat.tsx` | component (route placeholder) | n/a | none — see UI-SPEC §10 PhasePlaceholder Chat row | GREENFIELD |
| `frontend/src/routes/Profile.tsx` | component (route placeholder) | n/a | none — see UI-SPEC §10 PhasePlaceholder Profile row | GREENFIELD |
| `frontend/src/routes/DebugAgentStream.tsx` | component (route) | streaming | none — see RESEARCH §`DebugAgentStream.tsx` lines 1607-1675 + UI-SPEC §12 | GREENFIELD |
| `frontend/src/lib/queryClient.ts` | config (TanStack defaults) | n/a | none — see RESEARCH §`queryClient.ts` lines 1085-1106 + CONTEXT.md §Claude's Discretion "QueryClient defaults" | GREENFIELD |
| `frontend/src/lib/decodeOidFromJwt.ts` | utility | transform | none — see RESEARCH §AccessDenied lines 1319-1395 (inline helper extraction) | GREENFIELD |
| `frontend/src/test/setup.ts` | test config | n/a | none — see RESEARCH §`frontend/src/test/setup.ts` lines 2250-2263 | GREENFIELD |
| `frontend/src/test/*.test.tsx` (5 MVP tests) | test | varies | shape-match: `tests/test_auth.py::TestGetCurrentUserId` (skip-on-missing pattern) — Vitest equivalent is `vi.skip()`. See RESEARCH §State of the Art lines 2264-2286 | GREENFIELD (shape from backend test discipline) |
| `frontend/.env.local` (gitignored template) | config | n/a | none — see RESEARCH §`frontend/.env.production/.local` lines 2110-2130 | GREENFIELD |
| `frontend/.env.production` (committed) | config | n/a | none — see RESEARCH §`frontend/.env.production` lines 2110-2130 | GREENFIELD |
| `frontend/.gitignore` | config | n/a | shape-match: `infra/bootstrap/.gitignore` (terraform.tfstate pattern); for Node: `node_modules`, `dist`, `.env.local` | role-match |
| `frontend/README.md` | docs | n/a | shape-match: `infra/bootstrap/README.md` Prerequisites/Steps runbook structure | shape-match |
| `frontend/openapi.snapshot.json` | drift-guard reference | n/a | none — drift-guard artefact per CI workflow (RESEARCH lines 2222-2230) | GREENFIELD |

### Infra (9 files — NEW `infra/external/` dir + 2 prod edits + 1 script)

| File (new/modified) | Role | Data Flow | Closest analog in repo | Match Quality |
|---------------------|------|-----------|------------------------|---------------|
| `infra/external/main.tf` (NEW) | config (IaC) | batch | `infra/bootstrap/main.tf` + `infra/bootstrap/identity.tf` (azuread.external aliased provider + local-state-only pattern); RESEARCH §`infra/external/main.tf` lines 1895-2001 | exact (shape mirror) |
| `infra/external/variables.tf` (NEW) | config | n/a | `infra/bootstrap/identity.tf` lines 11-20 (tenant_id_external + tenant_subdomain var shape); RESEARCH lines 2027-2045 | exact |
| `infra/external/outputs.tf` (NEW) | config | n/a | `infra/bootstrap/outputs.tf` (output { description + value } shape); RESEARCH lines 2003-2025 | exact |
| `infra/external/provider.tf` (NEW) | config | n/a | `infra/bootstrap/main.tf` lines 21-28 (provider azuread block) + `infra/bootstrap/identity.tf` lines 22-25 (azuread.external alias) | exact |
| `infra/external/terraform.tfvars` (template) | config | n/a | `infra/bootstrap/terraform.tfvars.local` (heredoc-from-README template pattern) | exact |
| `infra/external/.gitignore` (NEW) | config | n/a | `infra/bootstrap/.gitignore` (terraform.tfstate, *.tfvars.local) | exact |
| `infra/external/README.md` (NEW) | docs | n/a | `infra/bootstrap/README.md` (Prerequisites → Step 1/2/3 → Knowingly-accepted trade-offs); RESEARCH lines 2047-2108 | exact |
| `infra/envs/prod/main.tf` (EDIT env block) | config (IaC) | n/a | itself @ HEAD lines 186-209 (existing `module "compute" { kv_secret_uris = {...} }` + `seeded_user_id` arg); existing `azurerm_key_vault_secret "seeded_user_entra_oid"` lines 177-184 | exact (in-place extension) |
| `infra/envs/prod/variables.tf` (EDIT — add 2 tfvars) | config | n/a | itself @ HEAD lines 68-78 (existing `seeded_user_entra_oid` + `seeded_user_id` var shape) | exact (in-place extension) |
| `infra/envs/prod/prod.tfvars.local` (NEW, gitignored) | config | n/a | `infra/bootstrap/terraform.tfvars.local` (manually-pasted outputs pattern) | exact |
| `scripts/refresh-external-outputs.sh` (NEW) | utility (one-shot bash) | batch | `scripts/refresh-swa-origin.sh` (terraform output → sed rewrite → terraform apply pattern) | exact |

### CI/CD (2 files)

| File (modified) | Role | Data Flow | Closest analog in repo | Match Quality |
|-----------------|------|-----------|------------------------|---------------|
| `.github/workflows/ci.yml` (ADD `frontend-ci` job) | config (workflow) | batch | itself @ HEAD `lint-and-test` job (pgvector service + setup-* + step structure); RESEARCH lines 2149-2230 | exact (sibling-job extension) |
| `.github/workflows/deploy-spa.yml` (EXTEND build env) | config (workflow) | batch | itself @ HEAD (Build step) — needs path fix `apps/web` → `frontend` AND VITE_* env block per RESEARCH lines 2131-2148 | exact (in-place extension) |

### Documentation corrections (2 small touch-ups)

| File (modified) | Role | Data Flow | Closest analog | Match Quality |
|-----------------|------|-----------|----------------|---------------|
| `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` (D-07 amendment) | docs | n/a | itself — change `SingleTenantAzureAuthorizationCodeBearer` → `B2CMultiTenantAuthorizationCodeBearer` per RESEARCH Open Question Q1 | exact (text edit) |
| `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` (Q3 stray `apps/web/` correction) | docs | n/a | itself — line 187 stray reference correction | exact (text edit) |

---

## Pattern Assignments

### `src/job_rag/api/auth.py` (REWRITE function body + add module-level instance)

**Analog:** itself @ HEAD (Phase 1 D-10 left this function as a deliberate one-line skeleton precisely so Phase 4 could swap the body without touching call-sites).

**Current state — body to replace** (`src/job_rag/api/auth.py` lines 68-80):
```python
async def get_current_user_id() -> uuid.UUID:
    """Resolve the current user's UUID.

    v1 (Phase 1): returns ``settings.seeded_user_id`` directly — single-user
    deployment, no JWT validation. T-05-02 mitigation: the body parses no
    input, so there is no injection surface.

    Phase 4 (AUTH-06) rewrites this body to parse the Entra JWT ``sub`` /
    ``oid`` claim. No feature flag is needed — Phase 4 is a one-function-body
    change since every consumer of this dependency has already been wired
    via ``Depends(get_current_user_id)``. [D-10]
    """
    return settings.seeded_user_id
```

**Imports pattern to preserve** (`src/job_rag/api/auth.py` lines 1-13) — append `Depends`, `B2CMultiTenantAuthorizationCodeBearer`, `User`, `get_logger`:
```python
import hmac
import time
import uuid
from collections import defaultdict

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from job_rag.config import settings

_bearer = HTTPBearer(auto_error=False)
```

**Excerpt to mirror (canonical rewrite):** RESEARCH.md lines 1676-1794 — full file rewrite skeleton with `B2CMultiTenantAuthorizationCodeBearer` (NOT `SingleTenant…` as CONTEXT D-07 mis-named — see Q1 amendment). Critical excerpt (lines 1711-1724):
```python
# Module-level azure_scheme instance — instantiated ONCE at import time.
azure_scheme = B2CMultiTenantAuthorizationCodeBearer(
    app_client_id=settings.backend_audience.removeprefix("api://"),
    openid_config_url=(
        f"https://{settings.entra_tenant_subdomain}.ciamlogin.com/"
        f"{settings.entra_tenant_id}/v2.0/.well-known/openid-configuration"
    ),
    scopes={
        f"{settings.backend_audience}/access_as_user": "access_as_user",
    },
    validate_iss=True,
)
```

**Preserve as-is:** `_bearer`, `require_api_key`, `RateLimiter`, `standard_limit`/`agent_limit`/`ingest_limit` (lines 13-65).

---

### `src/job_rag/config.py` (4 NEW Pydantic Settings fields)

**Analog:** itself @ HEAD — extends the existing `Settings` class.

**Field pattern to mirror** — minimal `str = ""` defaults match `api_key`/`langfuse_*` shape (`src/job_rag/config.py` lines 18-29):
```python
openai_api_key: str = ""
openai_model: str = "gpt-4o-mini"
...
langfuse_public_key: str = ""
langfuse_secret_key: str = ""
langfuse_host: str = "https://cloud.langfuse.com"
agent_model: str = "gpt-4o-mini"
api_key: str = Field(default="", validation_alias="JOB_RAG_API_KEY")
```

**Excerpt to insert (per RESEARCH lines 1798-1813):**
```python
entra_tenant_id: str = ""
entra_tenant_subdomain: str = ""
backend_audience: str = ""
seeded_user_entra_oid: str = ""
```

**Anti-pattern:** Do NOT add `validation_alias` on these (env var name = uppercased field name; Pydantic Settings handles it). Do NOT add `Annotated[..., NoDecode]` (only `allowed_origins` needs that — it's CSV-decoded). Do NOT add a `model_validator` here.

---

### `alembic/versions/0005_adopt_entra_oid.py` (NEW migration)

**Analog (header/structure):** `alembic/versions/0004_corpus_cleanup.py` lines 1-44 — module docstring style ("HAND-WRITTEN", pitfall notes, D-decision refs) + revision identifiers block.

**Analog (idempotent UPDATE with bindparams):** `alembic/versions/0002_add_user_profile.py` lines 87-96 — `op.execute(sa.text("...").bindparams(...))` pattern with `:placeholder` syntax that avoids SQL injection (RESEARCH §Pitfall 14):
```python
op.execute(
    sa.text(
        "INSERT INTO users (id, email) VALUES (:user_id, :email) "
        "ON CONFLICT (id) DO NOTHING"
    ).bindparams(
        user_id=SEEDED_USER_ID,
        email="adrianzaplata@gmail.com",
    )
)
```

**Analog (column-add + index creation):** `alembic/versions/0004_corpus_cleanup.py` lines 68-72 + 94-105 — nullable=True column followed by `op.create_index(..., unique=True, ...)`.

**Analog (SEEDED_USER_ID single source of truth):** `0002_add_user_profile.py` lines 22-25 — `SEEDED_USER_ID = settings.seeded_user_id` pinned constant. **NOTE:** 0005 must NOT do `from job_rag.config import settings` because migration runs before app import order is fully wired in some entrypoints; instead use the literal `SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"` (RESEARCH line 1853) — DEVIATION justified there.

**Excerpt to mirror (full skeleton):** RESEARCH.md lines 1816-1893 — copy verbatim; in particular the `os.environ.get("SEEDED_USER_ENTRA_OID", "").strip()` + `if oid:` guard (lines 1868-1875) and the partial unique index (lines 1880-1886) `postgresql_where=sa.text("entra_oid IS NOT NULL")`.

**revision/down_revision pattern** (`0004_corpus_cleanup.py` lines 41-44):
```python
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```
For 0005 → `revision = "0005"`, `down_revision = "0004"`.

**Verified head:** `ls /Users/adrian/Developer/job-rag/alembic/versions/` → 0001, 0002, 0003, 0004 (no later). Head is 0004; 0005 chains cleanly.

---

### `pyproject.toml` (1 dep add)

**Analog:** itself @ HEAD `[project.dependencies]` block — add `"fastapi-azure-auth>=5.2,<6.0"` to the array. RESEARCH.md §Core (backend additions) line ~195 names the version bound. Bumps `uv.lock` via `uv add fastapi-azure-auth`.

**Pattern reminder:** Use `uv add fastapi-azure-auth` (not manual edit) — Phase 1 D-04 / CLAUDE.md "Configuration" pattern uses uv as the source of truth for the lockfile.

---

### `tests/test_auth.py` (EXTEND with TestEntraJwtValidation + TestOidGuard)

**Analog:** itself @ HEAD `TestGetCurrentUserId` (lines 13-34) — `@pytest.mark.asyncio` class + `pytest.skip` on missing-import pattern.

**Skip-on-missing pattern to mirror** (lines 26-31):
```python
try:
    auth = importlib.import_module("job_rag.api.auth")
except ImportError as e:
    pytest.skip(f"job_rag.api.auth not yet added (Plan 05): {e}")
if not hasattr(auth, "get_current_user_id"):
    pytest.skip("get_current_user_id not yet added (Plan 05)")
```

**New test classes — pattern (use existing test_auth.py shape):**
- `TestEntraJwtValidation` — mock `User` claims, assert 403 raised when oid empty / mismatch. Use `pytest.MonkeyPatch` for `settings.seeded_user_entra_oid` overrides.
- `TestOidGuard` — happy-path: when `oid == settings.seeded_user_entra_oid`, returns `settings.seeded_user_id`.

**Critical:** the assertion `result == settings.seeded_user_id` from line 33 holds across the rewrite because the dependency contract is "returns UUID" — preserve this assertion in the happy-path test.

---

### `tests/test_alembic.py` (EXTEND with 0005 smoke tests)

**Analog:** itself @ HEAD `test_0004_upgrade_smoke` (lines 67-147) + `test_0004_downgrade_smoke` (lines 150-194).

**Excerpt to mirror — Postgres-reachable guard** (lines 52-64):
```python
def _postgres_reachable() -> bool:
    try:
        from sqlalchemy import create_engine, text
        from job_rag.config import settings
        eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False
```

**Excerpt to mirror — alembic command harness** (lines 76-99):
```python
from alembic.config import Config
from sqlalchemy import create_engine, text
from alembic import command
from job_rag.config import settings

cfg = Config("alembic.ini")
from job_rag.db.engine import configure_alembic_url
configure_alembic_url(cfg, settings.database_url)

command.downgrade(cfg, "0004")  # roll back to one-before
# … snapshot row counts …
command.upgrade(cfg, "0005")
# … assert column/index presence …
```

**New assertions for 0005:**
- `entra_oid` column exists on `user_db` table (information_schema check).
- `ix_user_db_entra_oid_unique` index exists (pg_indexes check).
- Idempotent: a second `command.upgrade(cfg, "head")` is a no-op.
- Env-driven UPDATE: with `SEEDED_USER_ENTRA_OID=test-oid` in env, the seed row's `entra_oid` = `'test-oid'`; with env empty, the column stays NULL.
- Re-test no-default-uuid guard (already covered by `test_no_default_uuid_on_user_id_columns` at lines 33-49) — no new test needed; the scanner runs against 0005 automatically.

---

### `frontend/src/main.tsx` (NEW — D-05 AUTH-07 race fix)

**Analog:** none in repo (greenfield SPA).

**Excerpt to mirror:** RESEARCH.md lines 1028-1084 — `await msalInstance.initialize(); await msalInstance.handleRedirectPromise();` literally precedes `ReactDOM.createRoot(rootEl).render(<App/>)` — no wrapping component, no React.use(). UI-SPEC §16 "Loading-State Policy" enforces: blank during the await window (50-150ms), AuthGate renders RouteSkeleton if MSAL is still mid-init.

**Provider nesting order** (CONTEXT §Claude's Discretion, immutable):
```
<MsalProvider> → <QueryClientProvider> → <BrowserRouter> → <ErrorBoundary> → <App/>
```

---

### `frontend/src/auth/msal.ts` (NEW — singleton)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 987-1027 (PublicClientApplication + `knownAuthorities: ["{tenant_subdomain}.ciamlogin.com"]` + `cacheLocation: 'sessionStorage'` per D-06).

**Critical:** `knownAuthorities` MUST be set — without it MSAL refuses non-microsoftonline.com authorities (RESEARCH §Pitfall 1).

---

### `frontend/src/auth/AuthGate.tsx` (NEW — D-18 protected-route boundary)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1107-1143 — `useIsAuthenticated()` + `useMsal().inProgress` check; if unauth → `msalInstance.loginRedirect({scopes: [API_SCOPE]})`; if in-progress → `<RouteSkeleton/>`; else → `<Outlet/>`.

**UI-SPEC §16 contract:** NEVER render a login form as first visible UI. The loginRedirect is the only path to auth UI.

---

### `frontend/src/api/authedFetch.ts` (NEW — D-11/D-13)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1144-1215 — native fetch wrapper with `acquireTokenSilent` → Bearer header → 401-retry-after-refresh → `InteractionRequiredAuthError` ⇒ `acquireTokenRedirect`. Signature: `authedFetch(input: RequestInfo, init?: RequestInit) → Promise<Response>` (~30-50 LOC).

**Composition note:** TanStack Query passes `signal` via queryFn arg; service modules thread `init.signal` through.

---

### `frontend/src/api/readSSEStream.ts` (NEW — D-16)

**Analog (event shape):** `src/job_rag/api/sse.py` Phase 1 `AgentEvent` discriminated union — the SPA-side consumer reads the same tagged union via openapi-typescript codegen. **Same event names**, modulo TS deserialization.

**Excerpt to mirror:** RESEARCH.md lines 1216-1318 — `async function*` over `response.body.getReader()` + `TextDecoder("utf-8")` + split-on-`\n\n` SSE frame boundary. Yields typed `AgentEvent` (from `src/api/types.ts` codegen).

**Pitfall:** RESEARCH §Pitfall 5 — must buffer partial chunks; do NOT JSON.parse mid-frame.

---

### `frontend/src/api/{health,jobs,profile,agent}.ts` (D-15 typed service modules)

**Analog:** none in repo. Pattern: each module exports typed async functions `(params, signal) → Promise<T>` that call `authedFetch` and cast against `openapi-typescript` `paths` type. CONTEXT.md D-15 names the signature shape; RESEARCH §State of the Art (lines 2264+) shows the canonical TanStack Query queryFn composition.

---

### `frontend/src/components/AppShell.tsx` (NEW — D-18 layout)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1437-1496 (component skeleton) + UI-SPEC §7 (the canonical anatomy ASCII diagram + spacing tokens + `<nav aria-label="Primary">` + Tab order + Toaster placement).

**Sign-out:** `msalInstance.logoutRedirect({postLogoutRedirectUri: SWA_origin})` per D-12. NOT an `<a href>`.

---

### `frontend/src/components/ThemeToggle.tsx` (NEW — D-20)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1396-1436 — localStorage `'theme'` read/write + `window.matchMedia('(prefers-color-scheme: dark)')` fallback + `document.documentElement.classList.toggle('dark')` mutation.

**UI-SPEC §14 motion contract:** 150ms cross-fade Sun↔Moon icon swap.

**Pitfall 10 coordination:** `index.html` must contain an inline `<script>` in `<head>` that sets `class="dark"` on `<html>` BEFORE React mounts (prevents FOUC). The ThemeToggle just keeps state in sync after first paint.

---

### `frontend/src/components/ErrorBoundary.tsx` + `ErrorBoundaryFallback.tsx` (NEW — D-19a)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1497-1538 — uses `react-error-boundary` library; fallback is a Card with `Back to dashboard` (default variant) + `Reload page` (outline variant) + `<details>Technical details</details>` collapsible. UI-SPEC §9 spells the layout + copywriting; UI-SPEC §15 mandates `role="alert"` on heading.

---

### `frontend/src/components/RouteSkeleton.tsx` (NEW — D-19b)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1585-1606 + UI-SPEC §11 (Skeleton h-6 w-1/3 + h-4 w-full + h-4 w-2/3 + h-9 w-32 rectangles in `max-w-md mx-auto mt-24 p-8` container — matching EmptyState dimensions to prevent layout shift).

---

### `frontend/src/components/EmptyState.tsx` + `PhasePlaceholder.tsx` (NEW — D-19d)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1539-1584 — typed `EmptyStateProps` (icon, heading, body, cta?) per UI-SPEC §10 typed contract.

**Copywriting (UI-SPEC §10 + §13):** exact body strings per route — `The dashboard widgets land in Phase 5. Check the roadmap for progress.`, `The streaming chat surface lands in Phase 6.`, `Resume upload and profile editing land in Phase 7.`. Phase 4 ships THREE PhasePlaceholder instantiations (Dashboard/Chat/Profile) + one NotFound EmptyState.

---

### `frontend/src/routes/AccessDenied.tsx` (NEW — D-09)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1319-1395 + UI-SPEC §8 (ASCII diagram + Card + `<pre><code>` mono OID + Copy ID button + Administrator runbook 3-step code block).

**Empty-OID fallback contract (UI-SPEC §8):** if `msalInstance.getActiveAccount()?.idTokenClaims?.oid` is undefined, render `<EmptyState heading="Sign in first" cta={{label: "Sign in", onClick: loginRedirect}}/>` — do NOT show empty `<pre>` block.

**ARIA (UI-SPEC §15):** `<div role="region" aria-label="Your account ID">` wraps the `<pre>`.

**Copy success/failure toasts:** `Copied to clipboard` / `Couldn't copy — please select and copy manually` (UI-SPEC §13 exact wording).

---

### `frontend/src/routes/DebugAgentStream.tsx` (NEW — D-16 dev-only)

**Analog:** none. Excerpt to mirror: RESEARCH.md lines 1607-1675 + UI-SPEC §12 (Input + Send query Button + scrollable `<pre max-h-96 overflow-y-auto bg-muted p-4 font-mono text-xs>` event log + connecting/end-of-stream/error separator copy).

**Gate:** route only mounts if `import.meta.env.DEV || import.meta.env.VITE_DEBUG_PAGES === 'true'` — falls through to `*` NotFound otherwise. Done in `App.tsx` route table (UI-SPEC §6).

---

### `infra/external/main.tf` (NEW)

**Analog (local-state-only + provider aliasing):** `infra/bootstrap/main.tf` lines 1-19 (terraform block + `# NO backend block — bootstrap intentionally uses LOCAL state`) + `infra/bootstrap/identity.tf` lines 22-25 (`provider "azuread" { alias = "external"; tenant_id = var.tenant_id_external }`).

**Excerpt to mirror — local-state declaration** (`infra/bootstrap/main.tf` lines 1-19):
```hcl
terraform {
  required_version = ">= 1.9"
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # NO backend block — bootstrap intentionally uses LOCAL state (D-02).
  # Local terraform.tfstate is gitignored via Plan 01's .gitignore additions.
}
```

**Excerpt to mirror — azuread external-tenant provider** (`infra/bootstrap/identity.tf` lines 22-25):
```hcl
provider "azuread" {
  alias     = "external"
  tenant_id = var.tenant_id_external
}
```

**App-reg resource skeletons:** RESEARCH.md lines 1923-2000 — `azuread_application "api"` (with `requested_access_token_version = 2` + `oauth2_permission_scope`) + `azuread_application_identifier_uri` (separate resource to break the client_id chicken-and-egg) + `azuread_application "spa"` (with `single_page_application { redirect_uris = [...] }`) + `azuread_service_principal_delegated_permission_grant` for admin consent.

**Critical (RESEARCH §Pitfall 2):** `single_page_application` block, NOT `web` block. Wrong type = AADSTS9002326 "Cross-origin token redemption is permitted only for the 'Single-Page Application' client-type."

---

### `infra/external/outputs.tf` (NEW)

**Analog:** `infra/bootstrap/outputs.tf` — `output { description; value }` shape. Excerpt to mirror (lines 1-19):
```hcl
output "storage_account_name" {
  description = "Copy this value into infra/envs/{prod,dev}/backend.tf as the storage_account_name literal."
  value       = azurerm_storage_account.tfstate.name
}
```

**Phase 4 outputs (per RESEARCH lines 2003-2025):** `spa_client_id`, `api_client_id`, `api_audience_uri`, `api_scope_name`. Each output's `description` MUST tell the next operator where to paste the value (mirrors bootstrap pattern).

---

### `infra/external/provider.tf` (NEW)

**Analog:** combination of `infra/bootstrap/main.tf` lines 21-28 (provider block) + `infra/bootstrap/identity.tf` lines 22-25 (alias). Phase 4 deviation: only `azuread.external` provider, NO `azurerm` (this dir manages NO Azure resources — Gap D constraint).

---

### `infra/external/README.md` (NEW)

**Analog:** `infra/bootstrap/README.md` (full file). Sections to mirror in order: Prerequisites → Step 1/2/3 → Knowingly-accepted security trade-offs → When to re-apply. RESEARCH lines 2047-2108 has the exact section structure.

---

### `infra/envs/prod/main.tf` (EDIT — extend `module "compute"` env block)

**Analog:** itself @ HEAD — the existing `module "compute" { kv_secret_uris = {...} }` block at lines 188-209.

**Excerpt to extend (lines 203-209):**
```hcl
kv_secret_uris = {
  "openai-api-key"          = azurerm_key_vault_secret.openai_api_key.versionless_id
  "postgres-admin-password" = module.database.admin_password_secret_uri
  "langfuse-public-key"     = azurerm_key_vault_secret.langfuse_public_key.versionless_id
  "langfuse-secret-key"     = azurerm_key_vault_secret.langfuse_secret_key.versionless_id
  "seeded-user-entra-oid"   = azurerm_key_vault_secret.seeded_user_entra_oid.versionless_id  # Phase 3 placeholder; Phase 4 fills with secretRef wiring in compute module
}
```

**Phase 4 additions (plain ACA env vars per D-04):** the compute module must accept 3 new variables `backend_audience`, `entra_tenant_id`, `entra_tenant_subdomain` and wire them into the `template.container.env` block. The existing `seeded-user-entra-oid` KV secretRef is already wired — Phase 4 just ensures the new SEEDED_USER_ENTRA_OID env name points at it.

**Pattern (KV-vs-plain env distinction per Phase 3 D-13):** public-by-design ID strings = `env { name = "X"; value = var.x }`; genuine secrets = `env { name = "X"; secret_ref = "kv-secret-name" }`.

---

### `infra/envs/prod/variables.tf` (EDIT — add 2 tfvars)

**Analog:** itself @ HEAD lines 68-78 — `seeded_user_entra_oid` + `seeded_user_id` block shape.

**Excerpt to mirror (lines 68-73):**
```hcl
variable "seeded_user_entra_oid" {
  type        = string
  description = "Adrian's Entra oid placeholder per D-09. Empty on first Phase 3 apply; Phase 4 fills after first MSAL login."
  default     = "00000000-0000-0000-0000-000000000000"
  sensitive   = true
}
```

**New tfvars to add (sourced from `infra/external/` outputs):** `api_audience` (string, no default, description names `infra/external/` as source) + `entra_tenant_subdomain` (already exists at line 14 — verify no duplicate before adding).

---

### `infra/envs/prod/prod.tfvars.local` (NEW, gitignored)

**Analog:** `infra/bootstrap/terraform.tfvars.local` (manually-pasted outputs heredoc). README §Step 1 pattern.

---

### `scripts/refresh-external-outputs.sh` (NEW)

**Analog:** `scripts/refresh-swa-origin.sh` (full file, 35 lines).

**Excerpt to mirror (lines 13-32):**
```bash
set -euo pipefail
cd "$(dirname "$0")/../infra/envs/prod"

SWA_HOST="$(terraform output -raw swa_default_origin)"
if [ -z "$SWA_HOST" ]; then
  echo "FATAL: terraform output swa_default_origin returned empty" >&2
  exit 1
fi
SWA_ORIGIN="https://${SWA_HOST}"

if grep -q '^swa_origin' prod.tfvars; then
  sed -i.bak "s|^swa_origin.*|swa_origin = \"$SWA_ORIGIN\"|" prod.tfvars
  rm -f prod.tfvars.bak
else
  echo "swa_origin = \"$SWA_ORIGIN\"" >> prod.tfvars
fi

terraform apply -var-file=prod.tfvars -auto-approve
```

**Phase 4 deviation:** the new script `cd`s to `infra/external/` first, reads `spa_client_id` / `api_client_id` / `api_audience_uri` outputs, then writes them into `infra/envs/prod/prod.tfvars.local` (NOT `prod.tfvars`, since these are gitignored-via-`.local`). Optionally also writes them into `frontend/.env.production`. The terraform-output-then-sed pattern is the load-bearing reusable piece.

---

### `.github/workflows/ci.yml` (ADD `frontend-ci` job)

**Analog:** itself @ HEAD `lint-and-test` job (lines 10-65). Phase 4 adds a SIBLING job; runs in parallel.

**Excerpt to mirror — postgres service block (CI lines 12-24):**
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: test
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U postgres"
      --health-interval 5s
      --health-timeout 5s
      --health-retries 5
```

**Excerpt to mirror — Python setup (lines 26-37):**
```yaml
- uses: actions/checkout@v4
- name: Install uv
  uses: astral-sh/setup-uv@v4
  with:
    enable-cache: true
- name: Set up Python
  run: uv python install 3.12
- name: Install dependencies
  run: uv sync --frozen
```

**Phase 4 swap — Node toolchain (RESEARCH lines 2172-2194):**
```yaml
- name: Setup Node
  uses: actions/setup-node@v4
  with:
    node-version: '22'
    cache: 'npm'
    cache-dependency-path: frontend/package-lock.json

- name: Install frontend dependencies
  run: npm ci
  working-directory: frontend

- name: Typecheck
  run: npm run typecheck
  working-directory: frontend
- name: Lint
  run: npm run lint
  working-directory: frontend
- name: Vitest
  run: npm run test -- --run
  working-directory: frontend
```

**Codegen drift-check step (RESEARCH lines 2195-2230):** bring up FastAPI on port 8000, poll `/openapi.json`, run `npm run codegen`, `git diff --exit-code src/api/types.ts` — fail on drift. The postgres service block (mirrored above) is required for the FastAPI startup; that's why the new job needs it too.

---

### `.github/workflows/deploy-spa.yml` (EDIT — fix path + add VITE_* env)

**Analog:** itself @ HEAD (full file, 52 lines).

**Edit 1 — path corrections (3 occurrences of `apps/web/`):**
- Line 7 (`paths:`) → `frontend/**`
- Line 30 (`cache-dependency-path:`) → `frontend/package-lock.json`
- Line 34 (`working-directory:`) → `frontend`
- Line 49 (`app_location:`) → `frontend/dist`

**Edit 2 — Build step env block (RESEARCH lines 2131-2148):**
```yaml
- name: Build
  run: npm run build
  working-directory: frontend
  env:
    VITE_TENANT_SUBDOMAIN: ${{ secrets.VITE_TENANT_SUBDOMAIN }}
    VITE_TENANT_ID: ${{ secrets.VITE_TENANT_ID }}
    VITE_SPA_CLIENT_ID: ${{ secrets.VITE_SPA_CLIENT_ID }}
    VITE_API_AUDIENCE: ${{ secrets.VITE_API_AUDIENCE }}
    VITE_API_BASE_URL: ${{ secrets.VITE_API_BASE_URL }}
```

**GitHub repo secrets to add (out-of-band, after `infra/external/` apply):** the 5 `VITE_*` names above, set via `gh secret set`.

---

### `.planning/phases/04-frontend-shell-auth/04-CONTEXT.md` (D-07 amendment)

**Edit (RESEARCH Open Question Q1):** D-07 line 38 — change `SingleTenantAzureAuthorizationCodeBearer` → `B2CMultiTenantAuthorizationCodeBearer`. Rationale: SingleTenant class hard-codes the `login.microsoftonline.com` discovery URL (workforce); CIAM External Identities tokens are issued from `*.ciamlogin.com` and require the override-able `openid_config_url` constructor arg that only the B2C class accepts. Add a one-line note: "Class corrected per RESEARCH Q1 — see RESEARCH.md lines 2303-2308."

---

### `.planning/phases/03-infrastructure-ci-cd/03-CONTEXT.md` (Q3 `apps/web/` correction)

**Edit:** locate the stray `apps/web/` reference (line 187 per CONTEXT.md `<specifics>`) — annotate with: "Superseded by Phase 4 D-01: project location is `frontend/`."

---

## Shared Patterns

### Backend authentication (FastAPI Depends rewrite)

**Source:** `src/job_rag/api/auth.py` (existing pattern, line 68-80 is the function being rewritten)
**Apply to:** `src/job_rag/api/auth.py` ONLY — every consumer is wired via `Depends(get_current_user_id)` and does NOT change.

Pattern (Phase 1 D-10 function-body rewrite): pre-wire `Depends()` in early phase, swap body in later phase. The consumer-side decorator pattern is canonical in FastAPI; see `src/job_rag/api/routes.py` for the `Depends(get_current_user_id)` call-sites that Phase 4 doesn't touch.

### Structured logging

**Source:** `src/job_rag/api/auth.py` should mirror module-top pattern from `src/job_rag/observability.py` / `src/job_rag/services/*.py`:
```python
from job_rag.logging import get_logger
log = get_logger(__name__)
```
**Apply to:** `src/job_rag/api/auth.py` (new rejected-oid warning per D-08).

Warning shape (CONTEXT line 50): `log.warning("user_not_allowlisted", rejected_oid=oid)` — keyword-args, snake_case event name, NO PII leaking in detail string returned to user.

### Pydantic Settings field additions

**Source:** `src/job_rag/config.py` lines 18-29 (langfuse_*/openai_* pattern: bare `field_name: str = ""` for env-var-derived strings).
**Apply to:** `src/job_rag/config.py` — all 4 new fields use this exact shape. NO `validation_alias`, NO `NoDecode`, NO model_validator.

### Alembic migration safety

**Source:** `alembic/versions/0002_add_user_profile.py` lines 87-96 (`sa.text("...").bindparams(...)` — parameterized SQL, no string interpolation) + `0004_corpus_cleanup.py` lines 7-33 (head-comment pitfall documentation).
**Apply to:** `alembic/versions/0005_adopt_entra_oid.py` — RESEARCH §Pitfall 14 explicitly warns against string-interpolating `oid` into raw SQL; use `bindparams(oid=...)`.

### Terraform local-state isolation

**Source:** `infra/bootstrap/main.tf` lines 1-19 (terraform block with `# NO backend block` comment) + `infra/bootstrap/identity.tf` (azuread.external provider alias) + `infra/bootstrap/README.md` (Prerequisites → Steps → Trade-offs structure).
**Apply to:** `infra/external/main.tf` + `infra/external/provider.tf` + `infra/external/README.md`. Same operational shape (local apply, gitignored state, manual output-paste downstream).

### Test skip-on-missing-dep

**Source:** `tests/test_auth.py` lines 26-31 (`pytest.skip(f"... not yet added (Plan 05): {e}")` for ImportError handling).
**Apply to:** any test that depends on a frontend tool not yet installed or a backend symbol added later in the same plan-wave. The Vitest equivalent is `vi.skipIf(...)`.

### Postgres-reachability gate in alembic smoke tests

**Source:** `tests/test_alembic.py` lines 52-64 (`_postgres_reachable()` helper).
**Apply to:** new `test_0005_upgrade_smoke` + `test_0005_downgrade_smoke` — wrap each with `if not _postgres_reachable(): pytest.skip(...)` so CI without docker-compose still passes.

### Terraform-output-driven script

**Source:** `scripts/refresh-swa-origin.sh` lines 13-34 (`set -euo pipefail` + `cd "$(dirname "$0")/../..."` + `terraform output -raw X` + non-empty guard + `sed -i.bak` + `terraform apply -auto-approve`).
**Apply to:** `scripts/refresh-external-outputs.sh` — same idiom, different output names, different downstream file target.

### CI job-sibling extension

**Source:** `.github/workflows/ci.yml` lines 9-65 (single `lint-and-test` job). Phase 3 / earlier phases extended jobs by adding steps; Phase 4 adds a SIBLING job (`frontend-ci`) under the same `jobs:` key — runs in parallel. The pgvector service block is duplicated (not extracted to a reusable workflow — over-engineering for two jobs).

---

## No Analog Found (GREENFIELD — use RESEARCH skeletons)

The following files have NO in-repo analog because they are part of the new `frontend/` SPA. Planner must reference RESEARCH.md §Code Examples line ranges as the canonical skeleton.

| File | RESEARCH skeleton location |
|------|----------------------------|
| `frontend/package.json` | RESEARCH lines 2232-2264 |
| `frontend/vite.config.ts` | RESEARCH lines 929-969 |
| `frontend/tsconfig.json` | RESEARCH lines 970-986 |
| `frontend/eslint.config.js` | CONTEXT §Claude's Discretion (typescript-eslint v8 flat) + STACK §1 |
| `frontend/index.html` | RESEARCH §Pitfall 10 lines 786-810 (inline FOUC theme script) |
| `frontend/src/main.tsx` | RESEARCH lines 1028-1084 (D-05 race fix) |
| `frontend/src/App.tsx` | UI-SPEC §6 Route Table + RESEARCH §Pattern 1 lines 463-528 |
| `frontend/src/app.css` | RESEARCH lines 907-928 + UI-SPEC §4 Color |
| `frontend/src/auth/msal.ts` | RESEARCH lines 987-1027 |
| `frontend/src/auth/AuthGate.tsx` | RESEARCH lines 1107-1143 + UI-SPEC §5 |
| `frontend/src/api/authedFetch.ts` | RESEARCH lines 1144-1215 |
| `frontend/src/api/readSSEStream.ts` | RESEARCH lines 1216-1318 (+ event shape from `src/job_rag/api/sse.py`) |
| `frontend/src/api/{health,jobs,profile,agent}.ts` | RESEARCH §D-15 service-module template (no skeleton; pattern is "typed async fn per endpoint, signal threaded through, codegen-cast") |
| `frontend/src/api/types.ts` | codegen output — `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts` |
| `frontend/src/components/AppShell.tsx` | RESEARCH lines 1437-1496 + UI-SPEC §7 |
| `frontend/src/components/ThemeToggle.tsx` | RESEARCH lines 1396-1436 |
| `frontend/src/components/ErrorBoundary.tsx` + `Fallback.tsx` | RESEARCH lines 1497-1538 + UI-SPEC §9 |
| `frontend/src/components/RouteSkeleton.tsx` | RESEARCH lines 1585-1606 + UI-SPEC §11 |
| `frontend/src/components/EmptyState.tsx` + `PhasePlaceholder.tsx` | RESEARCH lines 1539-1584 + UI-SPEC §10 |
| `frontend/src/routes/AccessDenied.tsx` | RESEARCH lines 1319-1395 + UI-SPEC §8 |
| `frontend/src/routes/NotFound.tsx` | UI-SPEC §10 NotFound EmptyState instantiation |
| `frontend/src/routes/{Dashboard,Chat,Profile}.tsx` | UI-SPEC §10 PhasePlaceholder rows |
| `frontend/src/routes/DebugAgentStream.tsx` | RESEARCH lines 1607-1675 + UI-SPEC §12 |
| `frontend/src/lib/queryClient.ts` | RESEARCH lines 1085-1106 |
| `frontend/src/lib/decodeOidFromJwt.ts` | inline in RESEARCH §AccessDenied lines 1319-1395 |
| `frontend/src/test/setup.ts` | RESEARCH lines 2250-2263 |
| `frontend/src/test/*.test.tsx` (5 MVP) | RESEARCH §State of the Art lines 2264-2286 (no canonical skeleton — shape from `tests/test_auth.py` skip-on-missing discipline) |
| `frontend/.env.production` + `.env.local` | RESEARCH lines 2110-2130 |
| `frontend/.gitignore` | standard Node + Vite + IDE patterns; no in-repo analog (`.gitignore` files are role-canonical, not project-canonical) |
| `frontend/README.md` | shape-match `infra/bootstrap/README.md` (Prerequisites/Steps/Trade-offs) — content is bespoke to npm/Vite |
| `frontend/openapi.snapshot.json` | CI drift-guard artefact — RESEARCH lines 2222-2230 |

---

## Metadata

**Analog search scope:**
- `src/job_rag/api/*` (auth.py, app.py, routes.py, sse.py)
- `src/job_rag/config.py`
- `alembic/versions/*.py` (0001-0004)
- `tests/test_auth.py`, `tests/test_alembic.py`
- `infra/bootstrap/*` (main.tf, identity.tf, outputs.tf, README.md)
- `infra/envs/prod/*` (main.tf, variables.tf, locals.tf, provider.tf, backend.tf)
- `infra/modules/{identity,compute,kv,database}/` (skimmed — module-call patterns)
- `scripts/refresh-swa-origin.sh`
- `.github/workflows/{ci,deploy-spa,deploy-api}.yml`
- Phase 4 inputs: `04-CONTEXT.md`, `04-RESEARCH.md` (full headers + Code Examples §1676-2264), `04-UI-SPEC.md`

**Files scanned:** ~45 backend/infra files read (full or excerpt) + 60 phase-4 input pages = ~3500 lines of reference material.

**Pattern extraction date:** 2026-05-19

**Key invariants confirmed:**
- Alembic head is 0004 (`ls alembic/versions/` → 0001-0004, no later). 0005 chains cleanly.
- `infra/envs/prod/main.tf` already contains the `seeded-user-entra-oid` KV secret resource (lines 177-184) and the `kv_secret_uris` map entry (line 208) — Phase 4 only adds compute-module env-var wiring, not the KV resource.
- `tests/test_auth.py` is currently a tiny skeleton (35 lines, single class) — Phase 4 extends it; no rewrites.
- `.github/workflows/deploy-spa.yml` currently references `apps/web/` (stale path from Phase 3 STACK.md) — Phase 4 corrects to `frontend/`.
- `src/job_rag/api/auth.py::get_current_user_id` body is the literal 1-line return — Phase 1 D-10 prepared it for Phase 4 to swap without call-site churn.
- CONTEXT.md D-07 names `SingleTenantAzureAuthorizationCodeBearer` but RESEARCH.md Q1 confirms this class hard-codes the workforce discovery URL — Phase 4 must use `B2CMultiTenantAuthorizationCodeBearer` instead.
