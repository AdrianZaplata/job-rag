# Phase 1: Backend Prep - Research

**Researched:** 2026-04-24
**Domain:** FastAPI 0.135.x lifespan + sse-starlette typed SSE + Alembic 1.18.x baseline against SQLAlchemy 2.x + pgvector + Python `Protocol` for ingestion sources
**Confidence:** HIGH (all critical claims either VERIFIED via library source / official docs, or CITED from PITFALLS.md / ARCHITECTURE.md / STACK.md which are themselves HIGH-confidence)

---

## Summary

Phase 1 is a refactor against an inherited Python 3.12 / FastAPI 0.135.3 / SQLAlchemy 2.x async / LangGraph 1.1.6 / pgvector backend. All ten requirements (BACK-01..BACK-10) and all twenty-nine locked decisions (D-01..D-29 in CONTEXT.md) point to a single coherent slice of work split across four concerns: Alembic schema ownership, typed SSE event contract with heartbeat + timeout + drain, reranker preload + async wrapping, and an `IngestionSource` Protocol with `MarkdownFileSource` as the v1 implementation.

The key research findings that the planner needs **beyond what's already locked in CONTEXT.md**:

1. **`sse-starlette` already has every primitive D-15..D-19 require** — `ping_message_factory` for typed `event: heartbeat`, `shutdown_event` + `shutdown_grace_period` for cooperative drain, automatic `X-Accel-Buffering: no` header, and an explicit `NotImplementedError` if any layer tries to gzip-compress the stream. We do **not** need to roll this from scratch. [VERIFIED: sse_starlette/sse.py source]
2. **FastAPI 0.135.x ships native `fastapi.sse.EventSourceResponse`** with Rust-side serialization — but we should **stay on `sse-starlette`** because the native one lacks `shutdown_event` and only emits `:ping` comments (not typed events). Switching would re-introduce work D-15/D-17 already lock in. [VERIFIED: FastAPI commit 22381558]
3. **Alembic + pgvector autogenerate has a one-line gotcha**: in `env.py`, before `context.configure()`, run `connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector` or autogenerate emits "did not recognize type 'vector'" warnings. [VERIFIED: alembic discussion #1324]
4. **`asyncio.wait_for(agent.astream_events(...))` is safe for a flat `create_react_agent`** (parent graph + tool nodes), which is what we use. The known LangGraph cancellation bug (#5682) is for *nested subgraphs* invoked via `ainvoke` from inside a node — we don't have those. [VERIFIED: langgraph issue #5682]
5. **`CrossEncoder.predict()` is thread-safe for inference under PyTorch's "read-only model state" rule**, but performance does not improve under thread contention because PyTorch holds the GIL during forward passes and CrossEncoder serializes its tokenizer. `asyncio.to_thread()` (D-28) prevents event-loop blocking — that's its job — but does **not** speed up concurrent reranking. Adrian's v1 (single user, single replica) never hits contention. [VERIFIED: pytorch.org/discuss; sentence-transformers issue #857]
6. **`runtime_checkable` Protocol with `async def __aiter__`** requires the implementation method to be a real async generator (yields), not just `async def` returning an iterator — mypy/pyright issue #5385. The implementation pattern is to make `__aiter__` itself `async def` with `yield` in the body, not return a separate iterator object.

**Primary recommendation:** Plan four task waves: (Wave A) Alembic adoption + baseline + user/career migrations, (Wave B) SSE contract + heartbeat + timeout + drain + reranker preload + async wrapping, (Wave C) IngestionSource Protocol + MarkdownFileSource + ingest_from_source, (Wave D) CORS + config + CI grep guard + test infra. Waves A and C are independent and parallel-safe; Wave B is independent of A but touches the FastAPI app; Wave D depends on A finishing for the CI alembic-upgrade-head smoke step.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

The following are locked from `01-CONTEXT.md`. Research these — never alternatives.

#### Alembic adoption
- **D-01**: Baseline via `alembic revision --autogenerate -m 'baseline'` against a fresh Postgres, commit the generated `0001_baseline.py`, then `alembic stamp head` the existing local dev DB. Adrian's 108-posting corpus is preserved through the transition.
- **D-02**: Alembic uses the **sync** engine (psycopg2 via `DATABASE_URL`) with `NullPool`. Async engine is not used for migrations.
- **D-03**: `CREATE EXTENSION IF NOT EXISTS vector` moves into `0001_baseline.py`. `init_db()` loses its extension-creation responsibility.
- **D-04**: `job-rag init-db` CLI command kept by name but internally wraps `alembic upgrade head`. `Base.metadata.create_all()` is removed from the canonical schema path. Docker-entrypoint and docs keep working without change.
- **D-05**: Migration filenames follow `NNNN_<slug>.py` sequential integers (e.g., `0001_baseline.py`, `0002_add_user_profile.py`).

#### User model and `user_id`
- **D-06**: Add `users` table in Phase 1: `users (id UUID PK, entra_oid TEXT UNIQUE NULL, email TEXT NULL, created_at TIMESTAMPTZ DEFAULT now())`. `entra_oid` is nullable in v1.
- **D-07**: Add `user_profile` table in Phase 1 with `user_id UUID NOT NULL FK users(id)` plus the fields from existing `UserSkillProfile` Pydantic model. **No DB DEFAULT on `user_id`.** Data migration from `data/profile.json` is deferred to Phase 7 (PROF-01).
- **D-08**: Adrian's UUID is a **hardcoded Python constant** `SEEDED_USER_ID: UUID` (generate once, commit literal). Baseline migration inserts his `users` row with this ID.
- **D-09**: Phase 4 swap-in: dedicated migration `00NN_adopt_entra_oid.py` runs `UPDATE users SET id = <real-oid>, entra_oid = <real-oid> WHERE id = SEEDED_USER_ID` and drops the constant. Carry forward to Phase 4 planner.
- **D-10**: Single FastAPI dependency `get_current_user_id() -> UUID`. Phase 1 body returns `SEEDED_USER_ID` directly; Phase 4 rewrites to parse Entra JWT `sub`/`oid`. No feature flag.
- **D-11**: `user_id` added in Phase 1 **only to `user_profile`**. Shared-corpus tables (`job_postings`, `job_requirements`, `job_chunks`) stay shared.
- **D-12**: CI grep guard: test or workflow step that greps Alembic migrations for `DEFAULT.*uuid` on any `user_id` column and fails the build if matched.

#### `career_id` column
- **D-13**: `career_id TEXT NOT NULL DEFAULT 'ai_engineer'` added to `job_posting_db` in `0003_add_career_id.py` (after baseline + user tables). Index optional (Claude's discretion — see below; recommend skipping).

#### SSE event contract
- **D-14**: Six event types on `/agent/stream`: `token`, `tool_start`, `tool_end`, `heartbeat`, `error`, `final`. Documented via Pydantic v2 discriminated union on `type` field, appearing in OpenAPI for `openapi-typescript`.
- **D-15**: **Heartbeat** is a typed event: `event: heartbeat\ndata: {"ts": "<ISO-8601>"}`. Emitted every 15s during active reasoning.
- **D-16**: **Timeout** uses `event: error` with `{"reason": "agent_timeout", "message": "..."}` followed by natural stream close.
- **D-17**: Shutdown draining **included in Phase 1**. Lifespan shutdown tracks active stream task set, emits `event: error` with `{"reason": "shutdown"}` to each, and `await asyncio.gather(*active, return_exceptions=True)` with a 30s budget.
- **D-18**: `X-Accel-Buffering: no` header + `Content-Encoding: identity` on the SSE response. **No `GZipMiddleware` anywhere in the app.**
- **D-19**: Error reasons: typed literal `agent_timeout | shutdown | llm_error | internal`. Stack traces **never** leak — sanitize to short human-readable string.

#### `IngestionSource` Protocol
- **D-20**: Protocol shape: `async def __aiter__(self) -> AsyncIterator[RawPosting]`.
- **D-21**: `RawPosting` dataclass: `raw_text: str`, `source_url: str`, `source_id: str | None`, `fetched_at: datetime`. `source_id` maps to `linkedin_job_id` for LinkedIn case.
- **D-22**: `content_hash` computed by ingestion service (not by Protocol implementation) using existing `hashlib.sha256(raw_text.encode()).hexdigest()` pattern.
- **D-23**: Protocol + `RawPosting` + `MarkdownFileSource` all land in `src/job_rag/services/ingestion.py`. No new package.
- **D-24**: `async def ingest_from_source(async_session, source) -> IngestResult` is the new primary consumer. Sync `ingest_file` rewrapped to construct `MarkdownFileSource` and call async under the hood.

#### Operational tuning
- **D-25**: `asyncio.wait_for(agent.astream_events(...), timeout=60.0)` at handler level. On timeout, emit `event: error` with `{"reason": "agent_timeout"}`. Configurable via `AGENT_TIMEOUT_SECONDS`.
- **D-26**: `CORSMiddleware` with `allow_origins=settings.allowed_origins` (env-var driven, comma-split from `ALLOWED_ORIGINS`), `allow_credentials=True`, `allow_methods=["GET","POST"]`, `allow_headers=["Authorization","Content-Type"]`. Default in dev `["http://localhost:5173"]`. **Never `*`**.
- **D-27**: Preload reranker in FastAPI lifespan startup: `_get_reranker()` called once. Blocks startup ~2-3s.
- **D-28**: All `rerank()` call sites wrapped in `asyncio.to_thread(rerank, ...)` from async code (`rag_query` in retrieval.py; MCP tools in mcp_server/tools.py). Sync `rerank()` body unchanged.
- **D-29**: Async engine `pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=300`. Alembic uses `NullPool`.

### Claude's Discretion

- `SEEDED_USER_ID` specific UUID — generate via `uuid.uuid4()`, commit literal. Recommend: pick one with a distinctive prefix that's easy to spot in logs (e.g., starts with `00000000-0000-0000-0000-`).
- Whether `career_id` gets an index — **recommend NO**. Every row is `'ai_engineer'` in v1; index adds nothing and disk overhead.
- Exact Pydantic field names per SSE event type — keep symmetric with current event shapes in `src/job_rag/agent/stream.py`. **Wire shape MUST be byte-identical to today's** (token has `content`, tool_start has `name`/`args`, tool_end has `name`/`output`, final has `content`).
- Shutdown drain budget — chose 30s. Acceptable 15-60s.
- Heartbeat payload — `{"ts": "<ISO-8601>"}` is locked. Optional `active_tool: str | None` is Claude's call (recommend: skip in v1, add later if observability needs it).
- Whether to wrap reranker tokenizer specifically vs whole `rerank()` — **the latter is simpler and captures all CPU work**. Recommend: wrap the whole call.
- Test coverage for BACK-05 / BACK-06 — prefer integration tests that run the stream with patched slow-agent and observe emitted frames. Do not unit-test the asyncio scheduler.

### Deferred Ideas (OUT OF SCOPE for Phase 1)

Do not plan tasks for any of these. They have explicit later homes.

- **Full async-ingest pipeline refactor** — closing CONCERNS.md "Async/sync session dualism" for `/ingest` and CLI. The Protocol + async consumer in Phase 1 is the foundation; migrating callers is incremental. → Phase 2 or v2 tech-debt phase.
- **Prompt-injection sanitization on all LLM inputs** — extraction sanitizes; RAG + agent send raw posting content. → Post-Phase 8 security pass.
- **Rate-limiter moved to Redis / `X-Forwarded-For` support** — in-process per-IP fine for ACA single-replica v1. → Post-v1.
- **`/health` endpoint OpenAI connectivity check** — flagged but not a web-UI blocker. → Phase 8 docs hardening or separate observability plan.
- **Upload `raw_text` size cap at DB layer** — column unbounded today. → If/when adversarial input becomes a concern.
- **Terraform `terminationGracePeriodSeconds = 120`** — Phase 3 concern.
- **Liveness indicator UI from heartbeat** — Phase 6 (Chat) decision.
- **Cross-process model sharing for reranker** — ACA single-worker in v1, irrelevant.
- **Alembic autogeneration diff gate in CI** — nice-to-have. → Phase 8 CI hardening.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BACK-01 | CORS middleware via env-var origin allowlist (dev: localhost:5173; prod: SWA origin) | §"Standard Stack" → `CORSMiddleware`; §"Code Examples" → CORS config snippet; §"Common Pitfalls" → Pitfall: CORS preflight + `OPTIONS`. |
| BACK-02 | Pydantic models document `/agent/stream` SSE event contract; appear in OpenAPI | §"Architecture Patterns" → Pattern 1 typed discriminated union; §"Code Examples" → `AgentEvent` union; §"Common Pitfalls" → Pitfall: discriminated unions render but don't gain TS narrowing without explicit literals. |
| BACK-03 | Cross-encoder reranker preloaded in FastAPI lifespan | §"Architecture Patterns" → Pattern 2 lifespan with reranker preload + active-task set; §"Code Examples" → lifespan snippet. |
| BACK-04 | Reranker invocation wraps CPU-bound work in `asyncio.to_thread()` | §"Standard Stack" → CrossEncoder thread-safety analysis; §"Code Examples" → `await asyncio.to_thread(rerank, ...)`; §"Don't Hand-Roll" → don't build a custom thread pool. |
| BACK-05 | `/agent/stream` emits heartbeat every 15s | §"Standard Stack" → `sse-starlette.ping_message_factory`; §"Code Examples" → typed `event: heartbeat` factory. |
| BACK-06 | Agent endpoints enforce 60s timeout via `asyncio.wait_for`; emits graceful SSE error event | §"Architecture Patterns" → Pattern 3 timeout-wrapped astream_events; §"Code Examples" → `asyncio.wait_for` + `try/except TimeoutError` + `event: error`. |
| BACK-07 | Alembic adopted; initial revision baselines current schema | §"Standard Stack" → Alembic 1.18.x; §"Architecture Patterns" → Pattern 4 baseline-via-autogenerate-then-stamp; §"Common Pitfalls" → Pitfall: pgvector custom type in `env.py`. |
| BACK-08 | `user_id UUID NOT NULL` on `user_profile`; no DEFAULT in DDL; app-injected from JWT `sub` | §"Architecture Patterns" → Pattern 5 user_id without DB DEFAULT; §"Code Examples" → migration ops; §"Don't Hand-Roll" → CI grep guard pattern. |
| BACK-09 | `career_id TEXT NOT NULL DEFAULT 'ai_engineer'` on `job_posting_db` | §"Code Examples" → `0003_add_career_id.py` migration. |
| BACK-10 | `IngestionSource` Protocol with `RawPosting` dataclass; markdown reader is one impl | §"Architecture Patterns" → Pattern 6 async Protocol with structural typing; §"Code Examples" → Protocol + MarkdownFileSource; §"Common Pitfalls" → Pitfall: `runtime_checkable` is shape-only. |

---

## Architectural Responsibility Map

Phase 1 is pure backend; no browser/CDN tier work. Mapping anchors which existing module owns each capability so the planner doesn't assign work to the wrong layer.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CORS allowlist | API / app composition (`api/app.py`) | — | FastAPI middleware sits at app construction, not in routes. |
| SSE event schema | API / Pydantic (`api/sse.py` new) | Agent (`agent/stream.py`) | Schema lives in api/ for OpenAPI exposure; the generator yields *instances* of those models in agent/. Schema is the wire contract. |
| Heartbeat emission | API (sse-starlette `ping_message_factory`) | — | sse-starlette owns the ping cadence — we just supply the factory. Don't put the timer in agent code. |
| Timeout wrapping | API / route handler (`api/routes.py`) | — | `asyncio.wait_for` belongs at the route boundary, where we own the response and can emit a clean error event. Putting it inside `stream_agent` would fragment error handling. |
| Shutdown drain | API / lifespan (`api/app.py`) + sse-starlette `shutdown_event` | API / route (`api/routes.py`) tracks active set | Lifespan owns the lifecycle; routes register/unregister stream tasks in the active set. |
| Reranker preload | API / lifespan (`api/app.py`) | Services (`services/retrieval.py`) keeps `_get_reranker()` | Preload is a lifespan concern; the cache lives in the service module. |
| Reranker async wrapping | Services callers (`services/retrieval.py`, `mcp_server/tools.py`) | — | Callsites — not the sync `rerank()` body — own the async boundary. |
| Alembic env / migrations | DB (`db/`) + new `alembic/` directory at repo root | — | Migrations are db schema; `alembic/env.py` imports `Base` from `db.engine`. |
| `init_db` CLI wrapper | CLI (`cli.py`) → `db/engine.py` `init_db()` rewritten | — | Public surface unchanged; internal implementation calls `alembic upgrade head` via subprocess or programmatic API. |
| `users` + `user_profile` ORM | DB (`db/models.py`) | Pydantic (`models.py`) for response/request validation | ORM is durable schema; Pydantic is wire shape. They evolve together. |
| `get_current_user_id()` dep | API (`api/auth.py` extension or new `api/deps.py` slot) | — | FastAPI dependency. Phase 1 returns SEEDED_USER_ID; Phase 4 rewrites body. |
| `IngestionSource` Protocol | Services (`services/ingestion.py`) | — | Per D-23, no new package. Lives alongside existing `ingest_file`. |
| `MarkdownFileSource` impl | Services (`services/ingestion.py`) | — | Same module per D-23. |
| `ingest_from_source` consumer | Services (`services/ingestion.py`) | API (`api/routes.py`) and CLI (`cli.py`) call it via thin adapters | Service is the canonical async path. |

---

## Standard Stack

### New dependencies to add

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `alembic` | `>=1.18.0,<1.19.0` | Schema migrations | Latest 1.18.4 (released Feb 10 2026) targets SQLAlchemy 2.x. STACK.md confirms 1.18.x as the pin. Single-contributor repos benefit from sequential numeric filenames over UUID-style. [VERIFIED: pypi.org/project/alembic 2026-02-10] |

That's it for new backend deps. Everything else (FastAPI 0.135.3, sse-starlette, sentence-transformers, sqlalchemy 2.x, pgvector) is already in `pyproject.toml`.

### Versions verified in registry

```
$ npm view ... # not applicable, Python project
# Verified via PyPI WebFetch:
alembic 1.18.4  -- released 2026-02-10  -- pin >=1.18,<1.19
sse-starlette 3.3.4  -- released 2026-03-29  -- already installed; pin to current minor or stay loose
fastapi 0.135.3 -> 0.136.1 currently latest -- already installed; do NOT bump in this phase
```

### Stack components actively used (already installed)

| Library | Version (current) | Purpose | Phase 1 Role |
|---------|-------------------|---------|--------------|
| FastAPI | 0.135.3 | HTTP / SSE / OpenAPI | Lifespan extended, CORS middleware added, route handlers wrap `wait_for` |
| sse-starlette | 3.x (whichever pulled in) | SSE response with built-in `ping`, `shutdown_event`, `X-Accel-Buffering: no` | **Stay on this — do NOT migrate to fastapi.sse**, see decision rationale below |
| SQLAlchemy[asyncio] | 2.x with `Mapped[]` | ORM + async engine | Add `UserDB`, `UserProfileDB`, `career_id` col; pool sized per D-29 |
| psycopg2-binary | current | Sync driver for CLI + Alembic | Alembic uses sync per D-02 |
| asyncpg | 0.31.0 | Async driver for FastAPI | Pool config per D-29 |
| pgvector (Python) | current | Vector type in ORM | Schema unchanged in Phase 1 baseline; needs `ischema_names` registration in `alembic/env.py` |
| sentence-transformers | current | CrossEncoder reranker | Preloaded in lifespan per D-27 |
| structlog | current | All logging | Used in new modules |
| pydantic | 2.x | Discriminated unions for SSE events | New `AgentEvent` union model |
| pydantic-settings | current | Config loading | New settings: `allowed_origins`, `seeded_user_id`, `agent_timeout_seconds`, `heartbeat_interval_seconds` |

### Decision: Stay on sse-starlette, do NOT migrate to native `fastapi.sse.EventSourceResponse`

FastAPI 0.135.0+ ships a native `fastapi.sse.EventSourceResponse` with Rust-side Pydantic serialization and automatic 15s keep-alive [VERIFIED: FastAPI commit 22381558446c5d1ac376680a6581dd63b3a04119]. Tempting to migrate. **Do not.**

| Capability D-15..D-19 require | sse-starlette 3.3.4 | fastapi.sse.EventSourceResponse |
|---|---|---|
| Typed `event: heartbeat` (not `:ping` comment) | YES — `ping_message_factory: Callable[[], ServerSentEvent]` lets us inject any event | NO — emits comment-only `:ping` |
| Cooperative shutdown drain | YES — `shutdown_event: anyio.Event` + `shutdown_grace_period: float` parameters | NO — only client-disconnect handling |
| `X-Accel-Buffering: no` default | YES (verified in source) | YES |
| Compression blocked | YES — explicit `NotImplementedError` if anything tries | YES (skips middleware) |
| Custom headers | YES — constructor `headers` parameter | partial |
| Pydantic event model serialization | manual `.model_dump_json()` per yield | Rust-side automatic |
| OpenAPI schema documenting events | manual schema injection (not auto) | automatic from return type annotation |

The Rust-side serialization perf win is real but **doesn't matter** at single-user / single-replica scale. The two locked decisions D-15 (typed heartbeat) and D-17 (cooperative drain) require sse-starlette's `ping_message_factory` and `shutdown_event` parameters that the native FastAPI SSE simply does not have. Migration would re-introduce work the locks already eliminate. Stay on sse-starlette.

### Alternatives considered and rejected

| Instead of | Could use | Why rejected |
|------------|-----------|--------------|
| `alembic` | `yoyo-migrations` | Yoyo has no native SQLAlchemy autogenerate. We need autogenerate to baseline against the existing `Mapped[]` schema (D-01). |
| `sse-starlette` | `fastapi.sse.EventSourceResponse` (native) | Lacks `shutdown_event` + typed `ping_message_factory`. See above. |
| `runtime_checkable` Protocol | abstract base class `IngestionSource(ABC)` | ABC requires inheritance; PROJECT/Stack already established Protocol pattern (FastMCP tools). D-20 explicitly chose Protocol. |
| `asyncio.to_thread` for reranker | `concurrent.futures.ThreadPoolExecutor` direct | `to_thread` is the Python 3.9+ idiom; uses the default executor; one less moving part. D-28 locks `asyncio.to_thread`. |
| Pydantic discriminated union for SSE events | TypedDict with `Literal` | TypedDict has weaker OpenAPI integration. Pydantic v2 discriminated unions render the OpenAPI `discriminator` attribute correctly per Pydantic docs. [CITED: pydantic.dev/docs/validation] |

### Installation

```bash
# Add Alembic to pyproject.toml
uv add 'alembic>=1.18,<1.19'

# Initialize the alembic directory once
uv run alembic init alembic
```

After the `alembic init`, modify `alembic/env.py` (see Code Examples §"Alembic env.py for pgvector") and `alembic/script.py.mako` (add `import pgvector`).

### Version verification

[VERIFIED: pypi.org/project/alembic page fetched 2026-04-24] Alembic 1.18.4 released 2026-02-10. Compatible with SQLAlchemy 2.x.

[VERIFIED: pypi.org/project/sse-starlette page fetched 2026-04-24] sse-starlette 3.3.4 released 2026-03-29. Python ≥3.10. Already in deps.

[VERIFIED: github.com/fastapi/fastapi commit 22381558 fetched 2026-04-24] Native `fastapi.sse.EventSourceResponse` shipped in 0.135.0+; current 0.135.3 already includes it. We choose not to use it (rationale above).

---

## Architecture Patterns

### System Architecture Diagram (Phase 1 scope only)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       FastAPI app (uvicorn process)                          │
│                                                                              │
│  ┌──────────── lifespan ────────────┐    ┌─────────── middleware ─────────┐  │
│  │ startup:                         │    │ CORSMiddleware                 │  │
│  │   1. _get_reranker() preload     │    │   allow_origins from env       │  │
│  │   2. create app_shutdown event   │    │   never "*"                    │  │
│  │      (anyio.Event)               │    │   methods: GET, POST, OPTIONS  │  │
│  │   3. attach to app.state         │    │   headers: Authorization,...   │  │
│  │ shutdown:                        │    └────────────┬───────────────────┘  │
│  │   1. set app_shutdown            │                 │                      │
│  │   2. await asyncio.gather(       │                 ▼                      │
│  │      *active_streams, return_    │    ┌─────── /agent/stream ──────────┐  │
│  │      exceptions=True), 30s timeout)   │  request →                     │  │
│  │   3. await async_engine.dispose()│    │    register task in            │  │
│  └──────────────────────────────────┘    │    app.state.active_streams    │  │
│                                          │  ↓                             │  │
│  ┌─────── app.state ──────────────┐      │  EventSourceResponse(          │  │
│  │ active_streams: set[Task]      │◄─────│    typed_event_generator(),    │  │
│  │ shutdown_event: anyio.Event    │◄─────│    ping_message_factory=       │  │
│  └────────────────────────────────┘      │      heartbeat_factory,        │  │
│                                          │    shutdown_event=             │  │
│                                          │      app.state.shutdown_event, │  │
│                                          │    shutdown_grace_period=30.0, │  │
│                                          │    headers={                   │  │
│                                          │      "X-Accel-Buffering":"no", │  │
│                                          │      "Content-Encoding":       │  │
│                                          │        "identity"})            │  │
│                                          │                                │  │
│                                          │  typed_event_generator():      │  │
│                                          │    try:                        │  │
│                                          │      async for ev in           │  │
│                                          │        asyncio.wait_for(       │  │
│                                          │          stream_agent(q),      │  │
│                                          │          timeout=60.0):        │  │
│                                          │        yield ev.to_sse()       │  │
│                                          │    except TimeoutError:        │  │
│                                          │      yield ErrorEvent(reason=  │  │
│                                          │        "agent_timeout").to_sse │  │
│                                          │    except CancelledError:      │  │
│                                          │      yield ErrorEvent(reason=  │  │
│                                          │        "shutdown").to_sse      │  │
│                                          │      raise                     │  │
│                                          │    except Exception as e:      │  │
│                                          │      yield ErrorEvent(reason=  │  │
│                                          │        "internal", message=    │  │
│                                          │        sanitize(str(e))).to_sse│  │
│                                          │    finally:                    │  │
│                                          │      unregister from active    │  │
│                                          └────────────────────────────────┘  │
│                                                                              │
│  ┌─── /search, /match, /gaps, /agent (non-SSE) ────────────────────────┐     │
│  │  Existing handlers, now use:                                        │     │
│  │    user_id: UUID = Depends(get_current_user_id)                     │     │
│  │    (returns SEEDED_USER_ID in v1; Phase 4 swaps to JWT)             │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌─── /ingest ────────────────────────────────────────────────────────┐      │
│  │  await ingest_from_source(async_session,                          │      │
│  │      MarkdownFileSource(tmp_path))                                 │      │
│  └────────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │ asyncpg (pool: 3+2, pre_ping, recycle 300s)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PostgreSQL 17 + pgvector                                                   │
│  Schema managed exclusively by `alembic upgrade head`                       │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌──────────────────┐   │
│  │ 0001_baseline.py    │   │ 0002_add_user_      │   │ 0003_add_        │   │
│  │  - CREATE EXT vector│   │   profile.py        │   │   career_id.py   │   │
│  │  - job_postings     │   │  - users (id UUID,  │   │  - ALTER         │   │
│  │  - job_requirements │   │    entra_oid,email) │   │    job_postings  │   │
│  │  - job_chunks       │   │  - user_profile     │   │    ADD COLUMN    │   │
│  │  (autogenerated)    │   │    (user_id UUID    │   │    career_id TEXT│   │
│  │                     │   │    NOT NULL FK,     │   │    NOT NULL      │   │
│  │                     │   │    NO DEFAULT)      │   │    DEFAULT       │   │
│  │                     │   │  - INSERT seed user │   │    'ai_engineer' │   │
│  └─────────────────────┘   └─────────────────────┘   └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

         ┌───── parallel CLI path (no FastAPI) ─────┐
         │                                          │
         │  job-rag init-db                         │
         │    → subprocess: alembic upgrade head    │
         │                                          │
         │  job-rag ingest <dir>                    │
         │    → ingest_directory(sync_session, dir) │
         │      └─ for each file:                   │
         │          asyncio.run(                    │
         │            ingest_from_source(           │
         │              async_session,              │
         │              MarkdownFileSource(file)))  │
         └──────────────────────────────────────────┘
```

A reader can trace the primary use case: SPA hits `/agent/stream?q=...` → CORS check → handler registers task in app.state → wraps `stream_agent(q)` in `asyncio.wait_for(..., 60.0)` → the typed event generator yields Pydantic events serialized to SSE frames → sse-starlette layers heartbeat pings every 15s and watches for shutdown_event → on timeout, error event + close → on shutdown, error event + grace 30s → finally branch unregisters.

### Recommended Project Structure

```
src/job_rag/
├── api/
│   ├── app.py            # MODIFIED: lifespan adds reranker preload + shutdown_event + active_streams set
│   ├── routes.py         # MODIFIED: agent_stream wraps in wait_for; uses get_current_user_id
│   ├── auth.py           # ADDED: get_current_user_id() dep returning SEEDED_USER_ID in v1
│   ├── deps.py           # unchanged in Phase 1
│   └── sse.py            # NEW: AgentEvent discriminated union + per-event Pydantic models + helper to_sse()
├── agent/
│   └── stream.py         # MODIFIED: yields AgentEvent instances (not dicts); same wire shape; adds error event types
├── db/
│   ├── engine.py         # MODIFIED: pool sizing per D-29; init_db() now wraps `alembic upgrade head`
│   └── models.py         # MODIFIED: add UserDB, UserProfileDB; add career_id col to JobPostingDB
├── services/
│   ├── ingestion.py      # MODIFIED: add IngestionSource Protocol, RawPosting, MarkdownFileSource, ingest_from_source
│   ├── retrieval.py      # MODIFIED: rerank() body unchanged; rag_query awaits asyncio.to_thread(rerank, ...)
│   └── matching.py       # MODIFIED: load_profile(user_id) signature; body still reads data/profile.json in v1
├── mcp_server/
│   └── tools.py          # MODIFIED: rerank call sites wrapped in asyncio.to_thread
└── config.py             # MODIFIED: add allowed_origins, seeded_user_id, agent_timeout_seconds, heartbeat_interval_seconds

alembic/                  # NEW directory at repo root
├── env.py                # ischema_names['vector'] = pgvector.sqlalchemy.Vector before context.configure
├── script.py.mako        # add `import pgvector` to template
├── README
└── versions/
    ├── 0001_baseline.py          # autogenerated; CREATE EXT vector; create_table * 3
    ├── 0002_add_user_profile.py  # users + user_profile tables; INSERT seed
    └── 0003_add_career_id.py     # ALTER job_postings ADD COLUMN

alembic.ini               # NEW: connection URL via env var, no PII

tests/
├── test_api.py           # EXTEND: CORS preflight, agent_stream heartbeat, agent_stream timeout, agent_stream error sanitization
├── test_alembic.py       # NEW: in-process pytest that spins up a fresh DB, runs `alembic upgrade head`, asserts schema; greps versions/ for DEFAULT.*uuid
├── test_sse_contract.py  # NEW: AgentEvent serialization/parsing roundtrip; OpenAPI schema includes discriminator
├── test_ingestion.py     # NEW: IngestionSource Protocol structural typing; MarkdownFileSource yields RawPosting; ingest_from_source roundtrip
└── test_lifespan.py      # NEW: reranker preloaded; shutdown drain emits error events
```

### Pattern 1: Pydantic v2 Discriminated Union for SSE Events

**What:** A union of typed event models keyed on `type` field, rendering correctly in OpenAPI for downstream `openapi-typescript` consumption.

**When to use:** Any SSE endpoint with multiple distinct event shapes that the client needs to discriminate.

**Example:**

```python
# src/job_rag/api/sse.py
from datetime import datetime
from typing import Annotated, Literal, Union
import json
from pydantic import BaseModel, Field

# --- per-event payload models ---

class TokenEvent(BaseModel):
    type: Literal["token"]
    content: str  # MUST stay 'content' to match current wire shape (see CONTEXT D)

class ToolStartEvent(BaseModel):
    type: Literal["tool_start"]
    name: str
    args: dict | None = None

class ToolEndEvent(BaseModel):
    type: Literal["tool_end"]
    name: str
    output: str

class HeartbeatEvent(BaseModel):
    type: Literal["heartbeat"]
    ts: str  # ISO-8601, generated at emit time

class ErrorEvent(BaseModel):
    type: Literal["error"]
    reason: Literal["agent_timeout", "shutdown", "llm_error", "internal"]
    message: str  # sanitized human-readable; never a stack trace

class FinalEvent(BaseModel):
    type: Literal["final"]
    content: str

# --- discriminated union (the wire contract) ---

AgentEvent = Annotated[
    Union[TokenEvent, ToolStartEvent, ToolEndEvent, HeartbeatEvent, ErrorEvent, FinalEvent],
    Field(discriminator="type"),
]

# --- helper to convert to sse-starlette event payload ---

def to_sse(event: BaseModel) -> dict[str, str]:
    """Convert a Pydantic event to the dict shape sse-starlette expects."""
    return {
        "event": event.type,  # type: ignore[attr-defined]
        "data": event.model_dump_json(),  # JSON without surrounding quotes
    }
```

Source: pattern verified against [Pydantic v2 unions docs](https://pydantic.dev/docs/validation/latest/concepts/unions/).

**Wire-shape compatibility note:** the current `agent/stream.py` yields dicts like `{"type": "token", "content": "..."}`. The new Pydantic models reproduce this shape *exactly* — `model_dump_json()` on `TokenEvent(type="token", content="x")` produces `{"type":"token","content":"x"}`. Frontend clients parsing the existing wire format see no change.

**OpenAPI exposure:** Use a placeholder route or a dedicated schemas endpoint to make the union show up in the spec. FastAPI doesn't introspect SSE generators for response schema by default. One pattern:

```python
# Dummy endpoint solely for schema export — never called.
@router.get("/agent/stream/schema", include_in_schema=True, response_model=AgentEvent)
async def _agent_event_schema() -> AgentEvent:  # pragma: no cover
    raise NotImplementedError("schema-only endpoint")
```

Or — cleaner — add `AgentEvent` to a `responses={...}` dict on the actual `/agent/stream` route via `responses={200: {"content": {"text/event-stream": {"schema": AgentEvent.model_json_schema()}}}}`.

### Pattern 2: FastAPI Lifespan with Reranker Preload + Active-Stream Set + Cooperative Shutdown

**What:** Combine startup-time preloading, a tracked active-stream set, and a shared `anyio.Event` for graceful drain.

**When to use:** Any long-lived FastAPI app with both expensive startup work AND in-flight long requests that need clean termination.

**Example:**

```python
# src/job_rag/api/app.py
import asyncio
import anyio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_rag.api.routes import router
from job_rag.config import settings
from job_rag.db.engine import async_engine
from job_rag.logging import get_logger
from job_rag.services.retrieval import _get_reranker

log = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # --- startup ---
    log.info("lifespan_startup_begin")
    # 1. Preload the cross-encoder model (~80MB, blocks ~2-3s) [D-27]
    _get_reranker()
    log.info("reranker_preloaded")

    # 2. Create the app-wide shutdown event passed to every SSE response
    app.state.shutdown_event = anyio.Event()

    # 3. Track all active SSE handler tasks for drain
    app.state.active_streams = set()

    log.info("lifespan_startup_complete")
    yield

    # --- shutdown [D-17] ---
    log.info("lifespan_shutdown_begin", active_streams=len(app.state.active_streams))
    # 1. Signal every in-flight stream to wrap up
    app.state.shutdown_event.set()

    # 2. Wait up to 30s for them to drain
    if app.state.active_streams:
        try:
            await asyncio.wait_for(
                asyncio.gather(*app.state.active_streams, return_exceptions=True),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            log.warning("shutdown_drain_timeout", remaining=len(app.state.active_streams))

    # 3. Tear down DB
    await async_engine.dispose()
    log.info("lifespan_shutdown_complete")


app = FastAPI(title="Job RAG API", lifespan=lifespan, version="0.3.0")

# CORS [D-26]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # OPTIONS for preflight; never miss this
    allow_headers=["Authorization", "Content-Type"],
)

# CRITICAL: do NOT add GZipMiddleware [D-18, Pitfall 6]

app.include_router(router)
```

Source: pattern combines [FastAPI lifespan docs](https://fastapi.tiangolo.com/advanced/events/) + sse-starlette's `shutdown_event` mechanism (verified against `sse_starlette/sse.py` source).

**Note on `anyio.Event` vs `asyncio.Event`:** sse-starlette uses anyio for portability across asyncio and trio. The `shutdown_event` parameter expects an `anyio.Event`. They are interchangeable in pure-asyncio code via `anyio.from_thread.run` etc., but for our needs `anyio.Event()` works directly.

### Pattern 3: Timeout-wrapped `astream_events` with sanitized error event

**What:** Wrap the agent stream in `asyncio.wait_for`, catch `TimeoutError`, and emit a typed error event before the stream closes.

**When to use:** Any LangGraph `astream_events()` invocation that needs an enforced wall-clock bound.

**Example:**

```python
# src/job_rag/api/routes.py (excerpt)
import asyncio
from datetime import datetime, timezone
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from fastapi import APIRouter, Request

from job_rag.agent.stream import stream_agent  # MODIFIED to yield AgentEvent
from job_rag.api.sse import (
    AgentEvent, ErrorEvent, HeartbeatEvent, to_sse,
)
from job_rag.config import settings


def _heartbeat_factory() -> ServerSentEvent:
    """Custom ping factory: emits a typed event: heartbeat with ISO-8601 ts. [D-15]"""
    ev = HeartbeatEvent(type="heartbeat", ts=datetime.now(timezone.utc).isoformat())
    return ServerSentEvent(event="heartbeat", data=ev.model_dump_json())


def _sanitize(exc: BaseException) -> str:
    """Sanitize an exception for SSE error message — no stack traces. [D-19]"""
    # Bound length, strip newlines, never include the exception class
    return str(exc).strip().replace("\n", " ")[:200] or "internal error"


@router.get("/agent/stream", dependencies=[Depends(require_api_key), Depends(agent_limit)])
async def agent_stream(request: Request, q: str) -> EventSourceResponse:
    """Stream agent execution as SSE with heartbeat, 60s timeout, graceful drain."""
    app = request.app

    async def typed_event_generator():
        # The app needs to register THIS task so shutdown can wait on it.
        # We register self in the run-coroutine, but FastAPI doesn't expose
        # the task directly — workaround: use asyncio.current_task() inside the gen.
        current_task = asyncio.current_task()
        if current_task is not None:
            app.state.active_streams.add(current_task)
        try:
            try:
                # asyncio.wait_for cancels the inner generator on timeout. [D-25]
                async with asyncio.timeout(settings.agent_timeout_seconds):
                    async for event in stream_agent(q):
                        yield to_sse(event)
            except asyncio.TimeoutError:
                err = ErrorEvent(
                    type="error",
                    reason="agent_timeout",
                    message=f"Agent exceeded {settings.agent_timeout_seconds}s timeout",
                )
                yield to_sse(err)
            except asyncio.CancelledError:
                # Triggered by sse-starlette's shutdown_event drain or client disconnect.
                err = ErrorEvent(
                    type="error",
                    reason="shutdown",
                    message="Server is shutting down — please retry shortly",
                )
                yield to_sse(err)
                raise  # re-raise so the task actually completes
            except Exception as e:
                err = ErrorEvent(
                    type="error",
                    reason="internal",
                    message=_sanitize(e),
                )
                yield to_sse(err)
        finally:
            if current_task is not None:
                app.state.active_streams.discard(current_task)

    return EventSourceResponse(
        typed_event_generator(),
        ping=settings.heartbeat_interval_seconds,        # default 15
        ping_message_factory=_heartbeat_factory,         # typed heartbeat [D-15]
        shutdown_event=app.state.shutdown_event,          # cooperative drain [D-17]
        shutdown_grace_period=30.0,                       # [D-17]
        headers={
            "X-Accel-Buffering": "no",                    # [D-18]
            "Content-Encoding": "identity",               # [D-18]
        },
    )
```

Source: combination of [sse-starlette source](https://github.com/sysid/sse-starlette/blob/main/sse_starlette/sse.py) and [FastAPI lifespan + Request docs](https://fastapi.tiangolo.com/advanced/events/).

**Note on `asyncio.timeout` vs `asyncio.wait_for`:** D-25 says `asyncio.wait_for(agent.astream_events(...), timeout=60.0)`. `asyncio.timeout()` (3.11+) is the modern context-manager equivalent and works inside async generators where `wait_for` is awkward to apply to an `async for` loop. Both produce `asyncio.TimeoutError`. Either is acceptable; the example uses `async with asyncio.timeout(...)` because it composes more cleanly with the generator. The planner can choose; the wire effect (timeout → error event → close) is identical.

### Pattern 4: Alembic baseline-via-autogenerate-then-stamp

**What:** Bring an existing live database (built historically by `Base.metadata.create_all()`) under Alembic management without re-creating it.

**When to use:** Any migration to Alembic from any other schema-management approach.

**Example workflow:**

```bash
# 1. Initialize alembic at repo root
uv run alembic init alembic

# 2. Edit alembic/env.py per Pattern 7 (pgvector ischema_names hack + import Base)

# 3. Spin up a FRESH ephemeral postgres (NOT the dev DB)
docker run --rm -d --name pg-baseline -p 5433:5432 -e POSTGRES_PASSWORD=baseline pgvector/pgvector:pg17

# 4. Point alembic at the fresh DB and autogenerate
DATABASE_URL=postgresql://postgres:baseline@localhost:5433/postgres \
  uv run alembic revision --autogenerate -m "baseline"

# 5. Inspect the generated 0001_<slug>.py — should contain CREATE EXTENSION + 3 create_table.
#    Hand-edit to ensure CREATE EXTENSION runs FIRST in upgrade(), and rename file to 0001_baseline.py.

# 6. Tear down the ephemeral DB
docker stop pg-baseline

# 7. Stamp the existing dev DB so alembic knows it's already at that revision
DATABASE_URL=$DEV_DATABASE_URL \
  uv run alembic stamp head

# 8. Now write the next migrations on top:
uv run alembic revision -m "add_user_profile"   # hand-write 0002 (no autogenerate — defining new tables)
uv run alembic revision -m "add_career_id"      # hand-write 0003

# 9. From here on, init_db wraps `alembic upgrade head`
```

Source: assembled from [alembic autogenerate docs](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) and [alembic discussion #1324](https://github.com/sqlalchemy/alembic/discussions/1324).

**Caveat verified by Alembic docs:** Autogenerate cannot detect:
- Changes to `server_default` values
- Changes to constraint names without explicit `name=` arguments
- Postgres operator classes on indexes
- Custom column type changes (need `__repr__` or `render_item` hook)

For Phase 1 these are not blockers — we run autogenerate exactly once for the baseline, and then write all subsequent migrations by hand.

### Pattern 5: `user_id` migration without DDL DEFAULT

**What:** Adding a `user_id UUID NOT NULL` column to a table that already has data, without using a DDL DEFAULT (per D-08, D-12, Pitfall 18).

**When to use:** Any user-scoping migration. In Phase 1 this matters specifically for the future Phase 4 swap; in Phase 1 itself, `user_id` is only added to the *new* `user_profile` table, where there are no pre-existing rows to backfill.

**Example:**

```python
# alembic/versions/0002_add_user_profile.py
"""add user_profile and users tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-24 ...
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Constant must match src/job_rag/auth.py SEEDED_USER_ID exactly
SEEDED_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")  # placeholder

revision = "0002"
down_revision = "0001"

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),  # NO server_default!
        sa.Column("entra_oid", sa.Text, unique=True, nullable=True),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "user_profile",
        # NOT NULL, NO DEFAULT — that's the critical decision [D-07]
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True, nullable=False),
        sa.Column("skills_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("target_roles_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("preferred_locations_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("min_salary_eur", sa.Integer, nullable=True),
        sa.Column("remote_preference", sa.Text, nullable=False, server_default="unknown"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    # Insert Adrian's seed user [D-08]
    op.execute(sa.text("""
        INSERT INTO users (id, email)
        VALUES (:user_id, :email)
        ON CONFLICT (id) DO NOTHING
    """).bindparams(user_id=SEEDED_USER_ID, email="adrianzaplata@gmail.com"))


def downgrade() -> None:
    op.drop_table("user_profile")
    op.drop_table("users")
```

**Note:** `user_profile.skills_json` etc. use `Text` columns containing JSON in v1. Phase 7 (PROF-01) will introduce typed columns or JSONB. Phase 1's job is to land the table; the v1 path still reads `data/profile.json` (D-07).

### Pattern 6: `runtime_checkable` Async Protocol with Dataclass Yield

**What:** Define a structural-typing contract for "an async iterable of `RawPosting`" without requiring inheritance.

**When to use:** Any plug-in point where you want duck-typed implementations the codebase can extend without import gymnastics. PROJECT/Stack already established Protocol pattern via FastMCP tools.

**Example:**

```python
# src/job_rag/services/ingestion.py (new section)
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable
import asyncio


@dataclass(frozen=True, slots=True)
class RawPosting:
    """A raw posting emitted by an IngestionSource. No DB or extraction concerns. [D-21]"""
    raw_text: str
    source_url: str
    source_id: str | None  # e.g. linkedin_job_id, or None for bare markdown
    fetched_at: datetime


@runtime_checkable
class IngestionSource(Protocol):
    """An async-iterable source of RawPosting objects. [D-20]"""

    def __aiter__(self) -> AsyncIterator[RawPosting]:
        """Return an async iterator. Implementations are typically async generators."""
        ...


class MarkdownFileSource:
    """v1 implementation: yields one RawPosting per markdown file in a directory.
    
    File reads happen in a thread to avoid blocking the event loop. [D-20]
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    async def __aiter__(self) -> AsyncIterator[RawPosting]:
        if self.path.is_file():
            files = [self.path]
        else:
            files = sorted(self.path.glob("*.md"))

        for f in files:
            # Path.read_text is sync I/O — push to a thread to keep the loop free
            text = await asyncio.to_thread(f.read_text, encoding="utf-8")
            # Detect linkedin_job_id from raw text (existing helper)
            from job_rag.extraction.extractor import extract_linkedin_id
            source_id = None
            for line in text.splitlines():
                if "linkedin.com/jobs/view/" in line:
                    source_id = extract_linkedin_id(line)
                    break
            yield RawPosting(
                raw_text=text,
                source_url=f"file://{f.absolute()}",
                source_id=source_id,
                fetched_at=datetime.now(timezone.utc),
            )


# --- new primary consumer [D-24] ---

@dataclass
class IngestResult:
    total: int
    ingested: int
    skipped: int
    errors: int
    error_details: list[tuple[str, str]]
    total_cost_usd: float


async def ingest_from_source(
    async_session: "AsyncSession",  # forward ref to avoid extra import
    source: IngestionSource,
) -> IngestResult:
    """Run a source end-to-end: extract, dedupe, embed, store."""
    # ... body composes existing _content_hash, _posting_exists, _store_posting,
    #     embed_and_store_posting, but in async style.
    #     Compute content_hash here — NOT in the Protocol [D-22].
    ...
```

**Critical caveat verified against [mypy issue #5385](https://github.com/python/mypy/issues/5385):** When defining `__aiter__` in a Protocol, you must use `def __aiter__(self) -> AsyncIterator[...]` (sync-def returning an AsyncIterator), NOT `async def __aiter__`. The standard async-iterator protocol expects `__aiter__` to be a *regular* method that returns the async iterator object. The `async def __aiter__` form is allowed by Python but type checkers including pyright disagree on whether it satisfies the Protocol.

**Resolution for this codebase:** in the Protocol, declare `def __aiter__(self) -> AsyncIterator[RawPosting]: ...`. In the implementation (`MarkdownFileSource`), `async def __aiter__` works because async-generator-functions return async iterators when called. Pyright in basic mode (this project's setting) accepts both shapes for the implementation.

If pyright complains, the simpler workaround is to put the loop in a separate `async def _iter()` method and have `__aiter__` just `return self._iter()`.

### Anti-Patterns to Avoid

- **`allow_origins=["*"]` with `allow_credentials=True`** — CORS spec rejects this combination silently. Browsers refuse credentialed requests. [D-26 explicitly forbids `*` regardless.]
- **Missing `OPTIONS` in `allow_methods`** — preflight requests 405 even though the route handler is GET/POST.
- **Adding `GZipMiddleware` to FastAPI** — sse-starlette will raise `NotImplementedError("Compression is not supported for SSE streams.")`, but if a downstream proxy does it, the SPA sees buffered junk (Pitfall 6). [D-18 forbids GZip middleware.]
- **Calling `_get_reranker()` from inside an async route** — that's the lazy-load pattern we're killing. After D-27, any callsite seeing the reranker not preloaded should treat it as a bug.
- **Calling `rerank()` directly from async code** — blocks the event loop, blocks the heartbeat task, breaks D-15 cadence. Always `await asyncio.to_thread(rerank, ...)`. [D-28]
- **Putting `asyncio.wait_for` *inside* `stream_agent`** — fragments error handling. Wrap at the route handler boundary so error events stay in the SSE generator's `try/except` block.
- **`server_default=sa.text("'00000000-...'::uuid")` on `user_id`** — exactly what Pitfall 18 + D-08 forbid. CI must grep for this. [D-12]
- **Letting the Protocol's `IngestionSource` know about ORM or extraction** — the Protocol's job is to emit raw text + identifiers. Any DB or LLM code in a source implementation breaks the abstraction. [D-22 explicitly says content_hash is NOT in the Protocol.]
- **Calling `Base.metadata.create_all()` anywhere except tests** — D-04 makes Alembic the only schema path. Leaving `create_all()` in production code masks Alembic-vs-models drift.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE keep-alive heartbeat | A separate `asyncio.create_task(periodic_yield())` interleaved with the main generator | `EventSourceResponse(ping=15, ping_message_factory=...)` | sse-starlette already does this with correct cadence and cancellation cleanup. Hand-rolling means re-debugging interleaving with the main yields. |
| SSE shutdown drain | `app.state.signal = asyncio.Event()` + `if signal.is_set(): break` checks scattered through your generator | `EventSourceResponse(shutdown_event=..., shutdown_grace_period=30.0)` | sse-starlette injects the cancellation cleanly per-connection and respects the grace period. Hand-rolled code misses race conditions. |
| Concurrency limiter for reranker | A `Semaphore(1)` around the call | `await asyncio.to_thread(rerank, ...)` | Single-replica v1 has no contention. PyTorch holds the GIL during forward pass, so a semaphore would just duplicate that effect with extra book-keeping. |
| SSE event schema in OpenAPI | Hand-written JSON Schema dict in `responses={200: {...}}` | Pydantic v2 discriminated union via `Annotated[Union[...], Field(discriminator="type")]` | Pydantic emits the OpenAPI `discriminator` attribute correctly. `openapi-typescript` consumes it. |
| Schema migrations | Custom `init_db()` that runs DDL strings on app boot | Alembic 1.18.x | Versioned, reversible, autogeneratable, idempotent. Best practice and unambiguously locked by D-01..D-05. |
| Async iteration over IO sources | A `while True: result = await fetch_next()` loop with manual stop signaling | `async def __aiter__(self) -> AsyncIterator[...]` returning an async generator | Native Python async-generator protocol. `async for x in source:` works out of the box, supports clean cancellation via `aclose()`. |
| User-id injection | A header parser middleware that reads `X-User-Id` | A FastAPI dependency `get_current_user_id() -> UUID` returning `SEEDED_USER_ID` in v1 | Headers are client-controlled trust surface; dependencies are server-controlled. Phase 4 swap is one function body change. |
| CI grep guard for DEFAULT uuid | A custom Python script | A pytest test that opens `alembic/versions/*.py` and asserts no match for `r"DEFAULT.*uuid|DEFAULT.*UUID"` on lines containing `user_id` | Lives next to the test suite, runs in CI without any new workflow plumbing, fails fast with a clear assertion. |
| Sanitization of error messages | An `except Exception as e: yield {"data": str(e)}` | An explicit `_sanitize(exc)` helper that bounds length + strips newlines + drops the exception class | Stack traces leak DB schema, env vars, file paths, and (D-19) SHOULD NOT reach the client. |
| pgvector ischema reflection | A `MigrationContext` subclass override | One line in `env.py`: `connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector` | Single-line workaround verified against alembic discussion #1324. |

**Key insight:** Almost every "should I build this?" question in Phase 1 has a one-parameter answer in `sse-starlette` or `alembic`. The hand-rolled paths exist online but are several times more code and reproduce known bugs. Adrian's constraint set ("educational goal: clean separation, no logic in the wrong place") is best served by composing the right libraries, not writing infrastructure.

---

## Common Pitfalls

### Pitfall A: pgvector type not recognized by Alembic autogenerate
**What goes wrong:** First `alembic revision --autogenerate -m baseline` emits `INFO  [alembic.runtime.migration] Did not recognize type 'vector' of column ...`. The generated migration has `sa.Column("embedding", sa.NullType(), ...)` — wrong, will fail to apply.
**Why it happens:** SQLAlchemy doesn't know how to reflect the pgvector custom type unless the dialect's `ischema_names` is told about it.
**How to avoid:** In `alembic/env.py`, before `context.configure()` in `do_run_migrations`, register the type:
```python
import pgvector.sqlalchemy
def do_run_migrations(connection):
    connection.dialect.ischema_names["vector"] = pgvector.sqlalchemy.Vector
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
```
Also add `import pgvector` to `alembic/script.py.mako` so generated migrations have the import. [VERIFIED: alembic discussion #1324]
**Warning signs:** generated migrations contain `sa.NullType()` for the embedding column.

### Pitfall B: `asyncio.wait_for` cancellation doesn't clean up nested LangGraph subgraphs
**What goes wrong:** A `asyncio.wait_for(agent.astream_events(...), 60.0)` timeout cancels the parent graph but a subgraph invoked via `subgraph.ainvoke(...)` from inside a tool keeps running. (LangGraph issue #5682, still open.)
**Why it happens:** Cancellation propagation through `ainvoke` boundaries has a known gap in LangGraph 0.x and 1.x.
**How to avoid:** **Not relevant to Phase 1**. Our `create_react_agent(model, tools=AGENT_TOOLS, prompt=...)` is a **flat** agent — tools are LangChain `@tool` functions, not nested graphs. The bug only fires when graphs invoke other graphs. Flag for the planner: if Phase 6 (Chat) ever introduces subgraphs, revisit this.
**Warning signs:** server logs show "tool execution continuing after timeout" or LangSmith traces show two parallel runs after a cancellation event. [VERIFIED: langgraph issue #5682]

### Pitfall C: CrossEncoder concurrent `predict()` doesn't speed up
**What goes wrong:** Engineer wraps `rerank` in `asyncio.to_thread`, then runs 4 concurrent searches expecting parallelism. They observe ~4x latency, not ~1x. Frustration. They reach for a process pool.
**Why it happens:** PyTorch holds the GIL for the duration of CPU-bound forward passes. CrossEncoder's tokenizer is similarly serialized. Multiple threads contend, they don't parallelize.
**How to avoid:** Don't expect speedup — `to_thread` is for **event-loop release**, not parallelism. The async event loop stays responsive (heartbeats keep firing, other requests proceed) but the rerank itself is still serialized. For Phase 1 (single user, single replica), this is exactly what we need. [VERIFIED: pytorch.org/discuss; sentence-transformers issue #857]
**Warning signs:** none in v1 — the single-user load won't expose contention. Document as a known constraint for the v1.x scaling phase.

### Pitfall D: sse-starlette default `ping_message_factory` emits comment, not event
**What goes wrong:** Frontend developer adds `eventSource.addEventListener("heartbeat", ...)` expecting the default ping to fire it. Nothing happens. The `:ping ...` line is consumed silently.
**Why it happens:** sse-starlette's default ping is a *comment* (`:`-prefixed line per SSE spec) that the EventSource API does not deliver to listeners. To fire a typed `event: heartbeat`, you must pass a custom `ping_message_factory`.
**How to avoid:** Always pass `ping_message_factory=_heartbeat_factory` returning `ServerSentEvent(event="heartbeat", data=...)`. [VERIFIED: sse_starlette/sse.py source]
**Warning signs:** SPA console: no heartbeat events; DevTools EventStream tab shows `:ping...` comment lines but no `event: heartbeat` frames.

### Pitfall E: Pydantic discriminated union in OpenAPI doesn't auto-narrow TypeScript types
**What goes wrong:** `openapi-typescript` generates a TypeScript union but does not emit a discriminated union — frontend has to write its own type narrowing.
**Why it happens:** OpenAPI `discriminator` is a metadata hint, not a strict type narrowing. Most TS codegens (openapi-ts, openapi-typescript, openapi-fetch) treat unions as flat unions unless a Zod plugin is layered on. [hey-api/openapi-ts issue #3270]
**How to avoid:** Document at the SPA level (Phase 6 concern) that the SSE event union requires a manual narrowing step like:
```ts
function isToken(e: AgentEvent): e is TokenEvent { return e.type === "token"; }
```
Phase 1's job is correct OpenAPI emission. The TS narrowing problem is Phase 6's; flag for that planner. [CITED: hey-api/openapi-ts issue #3270]
**Warning signs:** Phase 6 PR has lots of `if (e.type === "token") { ... } else if (...)` ladders without TS-level type narrowing.

### Pitfall F: `runtime_checkable` Protocol's `isinstance()` only checks attribute presence
**What goes wrong:** `isinstance(my_source, IngestionSource)` returns `True` for any object that happens to have an `__aiter__` attribute, even if the signature is wrong (e.g., yields `dict` instead of `RawPosting`).
**Why it happens:** PEP 544 / `typing.runtime_checkable` was deliberately limited to attribute presence — checking signatures or generic parameters at runtime is not feasible.
**How to avoid:** Treat `runtime_checkable` as a sanity check, not a contract enforcer. Use static type checking (pyright basic mode, already on) for the real verification. Don't rely on `isinstance(source, IngestionSource)` for security boundaries. [VERIFIED: typing.python.org/protocols]
**Warning signs:** Tests pass `isinstance` but yield wrong-shaped objects; pyright catches it but only if you actually run pyright in CI (we do).

### Pitfall G: FastAPI `lifespan` `app.state` not propagated to dependencies before startup
**What goes wrong:** A dependency that reads `request.app.state.shutdown_event` raises `AttributeError` for the first request that arrives during the brief window before `yield` in lifespan.
**Why it happens:** FastAPI doesn't open the listener socket until after the lifespan's startup phase completes — but if your test uses `TestClient` with `with TestClient(app) as client:`, that context manager runs lifespan startup before any request. So in production it's safe; in tests it's safe IF you use the context manager. The bug fires only if you instantiate `TestClient(app)` without `with` (don't).
**How to avoid:** Always use `with TestClient(app) as client:` in tests. For ASGITransport-based tests (the project's existing pattern), `LifespanManager` from `asgi-lifespan` is needed:
```python
from asgi_lifespan import LifespanManager
async with LifespanManager(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ...
```
[CITED: FastAPI lifespan docs] Add `asgi-lifespan` to dev deps if it's not already pulled in transitively.
**Warning signs:** test errors like `AttributeError: 'State' object has no attribute 'shutdown_event'`.

### Pitfall H: `init_db` subprocess vs programmatic Alembic
**What goes wrong:** `init_db()` calls `subprocess.run(["alembic", "upgrade", "head"])`. In Docker, the working directory is `/app` but `alembic.ini` lives next to the source — subprocess can't find it without `cwd=` or absolute config path. Or — `alembic` binary not on PATH inside the runtime container.
**Why it happens:** Docker multi-stage build copies `.venv` but not `pyproject.toml` and not the `alembic.ini`. The shell-form `alembic` command resolves via PATH which may differ.
**How to avoid:** Use Alembic's programmatic API:
```python
from alembic import command
from alembic.config import Config

def init_db() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
```
Then ensure `alembic.ini` and `alembic/` directory are COPIED in the Dockerfile alongside `src/`.
**Warning signs:** `init_db` logs `FileNotFoundError: [Errno 2] No such file or directory: 'alembic'` or alembic logs `Cant find alembic.ini`.

### Pitfall I: Pool sizing doesn't include CLI / migration concurrent connections
**What goes wrong:** API has `pool_size=3, max_overflow=2` (5 max). A long-running `job-rag embed` CLI is also connected. A new deploy triggers `alembic upgrade head` while the API is still processing requests. Postgres caps out at 35 effective connections (per Pitfall 8). Things bork.
**Why it happens:** D-29 sized the API pool but Alembic uses NullPool (D-02) which opens *transient* connections — fine. But the CLI uses `SessionLocal` (sync, no NullPool) — that can hold connections persistently.
**How to avoid:** Document in the migration runbook: don't run CLI commands and `alembic upgrade head` simultaneously against the same DB. Phase 3 (deploy) will enforce ordering (Container App can't start until migrations finish). For Phase 1 local dev, this is not a concern.
**Warning signs:** `FATAL: sorry, too many clients already` during overlapping CLI + API + alembic activity.

---

## Runtime State Inventory

Phase 1 is a code/schema refactor with **one** runtime-state concern: existing data.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | Adrian's existing 108 postings + their embeddings + their chunks already live in the dev Postgres; the schema baseline must NOT drop or re-create these tables. | `alembic stamp head` after `0001_baseline.py` is committed (D-01). The baseline migration is for fresh installs only; existing dev DB is told "you're already at HEAD" without re-running DDL. |
| **Live service config** | None — this is a local + (later) Azure project; Phase 1 ships before Azure exists. No external services have v1 state baked in. | None. |
| **OS-registered state** | None — no Task Scheduler / launchd / systemd entries reference job-rag. | None — verified by inspection of repo (no `.service` files, no launchd plists, no scheduled-task scripts). |
| **Secrets and env vars** | Adding new env vars: `ALLOWED_ORIGINS`, `SEEDED_USER_ID` (committed literal, not env), `AGENT_TIMEOUT_SECONDS`, `HEARTBEAT_INTERVAL_SECONDS`. Existing `JOB_RAG_API_KEY`, `OPENAI_API_KEY`, `DATABASE_URL`, `ASYNC_DATABASE_URL` unchanged. | Update `.env.example` with the new vars (CONTEXT.md only adds `ALLOWED_ORIGINS` to docker-compose.yml; the others have safe defaults in `config.py`). Document that `SEEDED_USER_ID` is NOT an env var — it's a Python constant. |
| **Build artifacts / installed packages** | `pyproject.toml` and `uv.lock` need `alembic` added; Docker image rebuild required. | `uv add 'alembic>=1.18,<1.19'` then commit `pyproject.toml` + `uv.lock`. Dockerfile may need `alembic.ini` and `alembic/` directory in COPY. |

---

## Code Examples

Verified patterns from official sources. All snippets are illustrative — not drop-in. The planner should adapt.

### CORS middleware [D-26, BACK-01]

```python
# src/job_rag/api/app.py (excerpt)
from fastapi.middleware.cors import CORSMiddleware
from job_rag.config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,   # list[str] from env, comma-split
    allow_credentials=True,                    # required for Authorization header credentialed requests
    allow_methods=["GET", "POST", "OPTIONS"], # OPTIONS preflight; never miss it
    allow_headers=["Authorization", "Content-Type"],
)
```

### Config additions [D-25, D-26, D-27]

```python
# src/job_rag/config.py additions
import uuid
from pydantic import Field, field_validator

class Settings(BaseSettings):
    # ... existing fields ...

    allowed_origins: list[str] = Field(default=["http://localhost:5173"])
    seeded_user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    agent_timeout_seconds: int = 60
    heartbeat_interval_seconds: int = 15

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v
```

Source: [Pydantic Settings field_validator](https://docs.pydantic.dev/latest/usage/validators/).

### Alembic env.py for pgvector [Pitfall A, BACK-07]

```python
# alembic/env.py (key excerpts)
from logging.config import fileConfig
from sqlalchemy import pool, engine_from_config
from alembic import context
import pgvector.sqlalchemy  # CRITICAL — register the vector type

from job_rag.db.engine import Base
from job_rag.db import models as _models  # noqa: F401  -- side-effect import for table registration

target_metadata = Base.metadata


def run_migrations_online() -> None:
    config = context.config
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])  # never commit URL
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # [D-02]
    )

    with connectable.connect() as connection:
        # CRITICAL: tell the dialect about pgvector before context configures
        connection.dialect.ischema_names["vector"] = pgvector.sqlalchemy.Vector
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

Source: [alembic discussion #1324](https://github.com/sqlalchemy/alembic/discussions/1324).

### init_db wraps alembic [D-04]

```python
# src/job_rag/db/engine.py (init_db replacement)
from alembic import command
from alembic.config import Config
from pathlib import Path

def init_db() -> None:
    """Run all pending Alembic migrations to bring the DB up to head."""
    cfg = Config(str(Path(__file__).parent.parent.parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
```

Source: [Alembic Operations Reference](https://alembic.sqlalchemy.org/en/latest/api/commands.html).

### `get_current_user_id` dependency [D-10]

```python
# src/job_rag/api/auth.py additions
import uuid
from fastapi import Depends
from job_rag.config import settings

async def get_current_user_id() -> uuid.UUID:
    """v1: return Adrian's seeded UUID. Phase 4: parse Entra JWT sub/oid."""
    return settings.seeded_user_id
```

### CI grep guard [D-12]

```python
# tests/test_alembic.py (excerpt)
import re
from pathlib import Path

DEFAULT_UUID_PATTERN = re.compile(
    r"DEFAULT.*['\"]?[0-9a-f-]{36}['\"]?.*::?uuid|"  # DEFAULT '...' :: uuid
    r"server_default\s*=.*[Uu][Uu][Ii][Dd]",         # server_default=... uuid
    re.IGNORECASE,
)

def test_no_default_uuid_on_user_id_columns():
    """CI guard: no Alembic migration may add a DDL DEFAULT to a user_id column.
    
    Pitfall 18: silent multi-user collision.
    Decision D-08, D-12.
    """
    versions_dir = Path(__file__).parent.parent / "alembic" / "versions"
    bad_files: list[tuple[Path, int, str]] = []
    for migration in versions_dir.glob("*.py"):
        for lineno, line in enumerate(migration.read_text().splitlines(), 1):
            if "user_id" in line and DEFAULT_UUID_PATTERN.search(line):
                bad_files.append((migration, lineno, line.strip()))
    assert not bad_files, (
        "Migrations adding DEFAULT to user_id columns:\n"
        + "\n".join(f"  {p.name}:{n}: {line}" for p, n, line in bad_files)
    )
```

Plus a workflow step (recommended belt-and-suspenders):

```yaml
# .github/workflows/ci.yml addition (after existing test step)
      - name: Guard against DEFAULT on user_id columns
        run: |
          if grep -rn -E "user_id.*server_default|user_id.*DEFAULT.*uuid" alembic/versions/ ; then
            echo "::error::Migration adds DEFAULT to user_id column — see decision D-08 / Pitfall 18"
            exit 1
          fi

      - name: Smoke-test alembic upgrade head
        run: |
          export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test
          uv run alembic upgrade head
        services:
          postgres:
            image: pgvector/pgvector:pg17
            env:
              POSTGRES_PASSWORD: postgres
            ports:
              - 5432:5432
            options: >-
              --health-cmd "pg_isready -U postgres"
              --health-interval 5s
              --health-timeout 5s
              --health-retries 5
```

### `ingest_from_source` consumer [D-22, D-24, BACK-10]

```python
# src/job_rag/services/ingestion.py (new function)
async def ingest_from_source(
    async_session: AsyncSession,
    source: IngestionSource,
) -> IngestResult:
    """Run a source through dedupe+extract+embed+store, returning a summary."""
    ingested = skipped = errors = 0
    error_details: list[tuple[str, str]] = []
    total_cost = 0.0

    async for raw in source:
        # content_hash computed by SERVICE per D-22, not by the source
        c_hash = hashlib.sha256(raw.raw_text.encode()).hexdigest()

        if await _posting_exists_async(async_session, c_hash, raw.source_id):
            skipped += 1
            log.info("skipped_duplicate", source_url=raw.source_url, source_id=raw.source_id)
            continue

        try:
            # extract_posting is sync + LLM; push to thread to keep loop free
            posting, usage = await asyncio.to_thread(extract_posting, raw.raw_text)
            posting.raw_text = raw.raw_text

            db_posting = await _store_posting_async(async_session, posting, c_hash, raw.source_id)
            await _embed_and_store_async(async_session, db_posting)
            await async_session.commit()

            ingested += 1
            total_cost += usage["cost_usd"]
        except IntegrityError:
            await async_session.rollback()
            skipped += 1
        except Exception as e:
            await async_session.rollback()
            errors += 1
            error_details.append((raw.source_url, str(e)))
            log.error("ingest_error", source_url=raw.source_url, error=str(e))

    return IngestResult(
        total=ingested + skipped + errors,
        ingested=ingested, skipped=skipped, errors=errors,
        error_details=error_details, total_cost_usd=total_cost,
    )
```

### Sync `ingest_file` rewrap [D-24]

```python
# src/job_rag/services/ingestion.py (rewrite)
def ingest_file(session: Session, file_path: Path) -> tuple[bool, str, str | None]:
    """Sync entry point — preserved for CLI and existing /ingest endpoint.
    
    Internally constructs MarkdownFileSource and runs the async pipeline.
    """
    async def _run():
        async with AsyncSessionLocal() as async_session:
            result = await ingest_from_source(
                async_session,
                MarkdownFileSource(file_path),
            )
            return result

    result = asyncio.run(_run())
    if result.ingested:
        return True, f"ingested (${result.total_cost_usd:.4f})", None
    if result.skipped:
        return False, "duplicate", None
    if result.errors:
        return False, f"error: {result.error_details[0][1]}", None
    return False, "no_content", None
```

**Caveat:** the `posting_id` return value is dropped by this signature change (was `tuple[bool, str, str | None]` with id in the third slot). Callers in `/ingest` route use it for embedding. Solution: have `ingest_from_source` return the IDs in `IngestResult` and surface them. Planner should preserve callsite contracts.

### Reranker async wrapping [D-28, BACK-04]

```python
# src/job_rag/services/retrieval.py (rag_query change)
async def rag_query(...) -> dict[str, Any]:
    # ... retrieve unchanged ...

    # 2. Rerank — push CPU-bound work off the event loop [D-28]
    reranked = await asyncio.to_thread(
        rerank, query, results, top_k=top_k_rerank
    )

    # ... rest unchanged ...
```

```python
# src/job_rag/mcp_server/tools.py (similar change wherever rerank is called)
reranked = await asyncio.to_thread(rerank, query, results, top_k=5)
```

The sync `rerank()` body (`reranker.predict(pairs)` etc.) is **unchanged**. Only the callsites change.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Base.metadata.create_all()` for schema | `alembic upgrade head` for schema | Phase 1 (D-04) | Migrations are versioned, reversible, autogeneratable, idempotent across fresh + existing DBs |
| Lazy reranker init on first request | Preload in lifespan startup | Phase 1 (D-27) | First chat doesn't pay 2-3s cold-start; ACA cold-start absorbs it instead |
| Reranker called sync from async route | `await asyncio.to_thread(rerank, ...)` | Phase 1 (D-28) | Event loop stays responsive; heartbeat cadence preserved |
| Untyped SSE event dicts | Pydantic v2 discriminated union | Phase 1 (D-14) | OpenAPI spec documents events; `openapi-typescript` can generate TS types |
| Hand-rolled SSE keep-alive (none — would have to add manually) | sse-starlette `ping_message_factory` | Phase 1 (D-15) | 15s heartbeat is one parameter; emits typed event clients can listen for |
| `EventSource(url + "?token=...")` for auth (theoretical) | `fetch + ReadableStream` with `Authorization: Bearer` header | Phase 6 client (referenced in PROJECT.md research) | Tokens stay in headers, not URLs / logs |
| `data/profile.json` as canonical profile | `user_profile` DB row, indexed by `user_id` | Phase 7 (PROF-01) — **NOT Phase 1** | Phase 1 lays the schema; Phase 7 migrates the read path |

**Deprecated/outdated as of Phase 1 completion:**

- `init_db()`'s `Base.metadata.create_all()` call — deleted entirely (the function still exists, but its body is `command.upgrade(cfg, "head")`).
- `_get_reranker()` lazy init pattern — `_get_reranker()` itself stays (it's the singleton accessor) but no async path should be the FIRST caller.
- Direct `rerank(...)` calls from async code — flagged as bug by reviewers after Phase 1.
- `EventSource` (browser API) for `/agent/stream` — Phase 6 will use `fetch + ReadableStream` to attach `Authorization` header. Phase 1 doesn't ship a frontend, but the SSE response shape is what enables this.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The current dev Postgres has been built historically by `Base.metadata.create_all()` and not by some other mechanism (e.g. manual DDL). | Pattern 4 (Alembic baseline) | Low. If a column was added manually, autogenerate against fresh-DB will miss it; baseline migration won't recreate it; `alembic stamp head` against the dev DB will mark it correctly so that's fine. The risk is only that future schema-comparisons (e.g., `alembic check`) will flag the discrepancy. Mitigation: do a manual `\d+` audit before stamping. |
| A2 | `pyright` in basic mode accepts both `def __aiter__(self) -> AsyncIterator[...]` (Protocol) and `async def __aiter__(self) -> AsyncIterator[...]` (impl) shapes. | Pattern 6 | Low. If pyright complains, restructure the impl as `def __aiter__(self) -> AsyncIterator[RawPosting]: return self._iter()` with `async def _iter(self)` separately. Validated by reading the existing codebase (basic mode + Mapped[] usage suggests it's permissive). |
| A3 | The `/ingest` endpoint's caller (a single CLI script or a curl-from-frontend) expects the existing `tuple[bool, str, str | None]` signature on `ingest_file` — so D-24's rewrap must preserve it. | Pattern 6 / sync rewrap | Medium. If the frontend (Phase 7?) decides to pass through the posting_id for follow-up embedding, the slot must stay populated. Solution: thread the id through `IngestResult` and return it in slot 3 of the tuple. |
| A4 | `sse-starlette`'s `shutdown_event` mechanism, when set, propagates cleanly to all connected clients without losing in-flight bytes. | Pattern 2 / D-17 | Medium. Verified against source code but no production-scale test data on hand. Mitigation: explicit integration test (see Validation Architecture §Wave 0 gaps). |
| A5 | `asyncio.timeout(...)` (3.11+) is preferred over `asyncio.wait_for(...)` for wrapping an `async for` loop, but BOTH produce `asyncio.TimeoutError` and BOTH satisfy D-25. | Pattern 3 | Low. The choice is purely stylistic. The handler test should assert TimeoutError is raised regardless of which form is used. |
| A6 | The existing wire shape (`{"type": "token", "content": "..."}` etc.) is what the to-be-built frontend (Phase 6) expects. | Pattern 1 | Low. Verified by reading current `agent/stream.py`; the new Pydantic models reproduce it exactly. If Phase 6 wants a different shape (e.g. nested `data` field), that's a Phase 6 decision that doesn't block Phase 1. |
| A7 | Adrian's email `adrianzaplata@gmail.com` (extracted from this session's MEMORY.md) is what should populate the seeded `users.email` row. | Pattern 5 / migration 0002 | Low. If wrong, an `UPDATE users SET email=...` runs in <1s. Confirmed via this session's userEmail context. |
| A8 | The existing test suite uses `httpx.ASGITransport(app=app)` in unit tests without a `LifespanManager`, which means today's tests would NOT exercise the new lifespan startup. | Pitfall G | Medium. The planner should add `asgi-lifespan` to dev deps and update the test pattern, OR use `with TestClient(app) as client:`. Tests that assert `app.state.shutdown_event` exists are needed. |
| A9 | The `0001_baseline.py` migration runs `CREATE EXTENSION IF NOT EXISTS vector` BEFORE the `create_table` operations on tables that use `Vector`. | Pattern 4 / D-03 | Medium. Autogenerate may emit them in the wrong order. Hand-edit the generated migration to ensure extension creation runs first (`op.execute("CREATE EXTENSION IF NOT EXISTS vector")` as the first op in `upgrade()`). |

---

## Open Questions

1. **Should the heartbeat interval be configurable independently from the sse-starlette `ping=` parameter?**
   - What we know: D-15 locks 15s; settings has `heartbeat_interval_seconds: int = 15`.
   - What's unclear: whether to expose a separate setting or just use the existing one as-is.
   - Recommendation: single setting, pass to `EventSourceResponse(ping=settings.heartbeat_interval_seconds, ...)`.

2. **For the CI alembic-upgrade-head smoke test, do we add a postgres service container to GHA, or use SQLite for a dialect-portable check?**
   - What we know: pgvector requires Postgres. SQLite can't run the migration.
   - Recommendation: add the postgres service. It's a 5-line YAML addition. Sample shown in §Code Examples.

3. **`asgi-lifespan` for tests — is it already pulled in transitively, or do we need to add it?**
   - What we know: existing tests use `ASGITransport` without `LifespanManager` and they pass — but they also don't depend on `app.state` being populated.
   - Recommendation: add `asgi-lifespan` to dev deps explicitly so tests for the lifespan can run reliably. `uv add --dev asgi-lifespan`.

4. **Should `0001_baseline.py` include the `INSERT INTO users` for SEEDED_USER_ID, or should that go in `0002_add_user_profile.py`?**
   - What we know: D-08 says baseline-baseline migration inserts the row. But the baseline migration is autogenerated from the *existing* schema, which has no `users` table.
   - Recommendation: `users` table is *new* in Phase 1 — it goes in `0002_add_user_profile.py`. The seed `INSERT` goes there too. The "baseline-baseline" wording in D-08 should be read as "the migration that creates the users table" — i.e., 0002.

5. **Where does `SEEDED_USER_ID` constant live: `auth.py`, `config.py`, or its own module?**
   - What we know: D-08 says "hardcoded Python constant". D-09 says Phase 4 "drops the constant" — implying a single named import to find-and-remove.
   - Recommendation: `src/job_rag/config.py` as `Settings.seeded_user_id: UUID = UUID("...")` so it's discoverable alongside other config and importable as `settings.seeded_user_id`. Alembic migration imports it directly: `from job_rag.config import settings; SEED = settings.seeded_user_id`.

---

## Environment Availability

Phase 1 is local-only refactor work; no Azure / external services in scope. External dev dependencies are tools needed to develop and test, not runtime services.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All code, tests | (assumed yes — repo specifies 3.12) | 3.12.x | — |
| uv | Dependency mgmt | (assumed yes — uv.lock present) | latest | pip + venv |
| Docker | docker-compose dev stack | (assumed yes — docker-compose.yml present) | latest | None — local dev requires it |
| docker-compose | dev DB orchestration | (assumed yes) | latest | docker run pgvector/pgvector:pg17 manually |
| pgvector/pgvector:pg17 image | Local Postgres + vector | (assumed yes — pulled by docker-compose) | pg17 | Postgres 17 with manual `CREATE EXTENSION vector` if pgvector image missing |
| Postgres 17 service | Tests, dev DB | locally via docker-compose | 17 | None — pgvector requires it |

**Missing dependencies with no fallback:** none expected.

**Missing dependencies with fallback:** none expected.

**Note for the planner:** Phase 1's only new dev-time tool is the `alembic` CLI, which `uv add alembic` provides. Tests and CI need access to a Postgres + pgvector instance, which the repo already requires; no new infra dependency.

---

## Validation Architecture

**Nyquist validation IS enabled** for this project (`workflow.nyquist_validation: true` in `.planning/config.json`). This section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest -m "not eval" -x --tb=short` |
| Full suite command | `uv run pytest -m "not eval"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| BACK-01 | CORS middleware accepts `http://localhost:5173` | unit / integration | `pytest tests/test_api.py::TestCORS::test_preflight_localhost_5173 -x` | ❌ Wave 0 |
| BACK-01 | CORS middleware rejects unknown origins | unit | `pytest tests/test_api.py::TestCORS::test_preflight_unknown_rejected -x` | ❌ Wave 0 |
| BACK-01 | CORS does NOT use `*` even when env var unset (defensive) | unit | `pytest tests/test_api.py::TestCORS::test_no_wildcard_origin -x` | ❌ Wave 0 |
| BACK-02 | OpenAPI spec exposes `AgentEvent` discriminated union | unit | `pytest tests/test_sse_contract.py::test_openapi_includes_agent_event -x` | ❌ Wave 0 |
| BACK-02 | Each event type's wire shape matches today's | unit | `pytest tests/test_sse_contract.py::test_token_event_wire_shape -x` (and similar for tool_start, tool_end, final, heartbeat, error) | ❌ Wave 0 |
| BACK-03 | Reranker is preloaded by lifespan startup | integration | `pytest tests/test_lifespan.py::test_reranker_preloaded -x` | ❌ Wave 0 |
| BACK-03 | First `/agent/stream` call doesn't trigger CrossEncoder load | integration | `pytest tests/test_lifespan.py::test_first_request_no_cold_start -x` | ❌ Wave 0 |
| BACK-04 | `rag_query` calls reranker via `asyncio.to_thread` | unit (mock-based) | `pytest tests/test_retrieval.py::test_rerank_uses_to_thread -x` | ❌ Wave 0 |
| BACK-04 | Event loop is not blocked during reranking | integration | `pytest tests/test_retrieval.py::test_event_loop_responsive_during_rerank -x` (concurrent timer + rerank) | ❌ Wave 0 |
| BACK-05 | `/agent/stream` emits `event: heartbeat` ~every 15s | integration | `pytest tests/test_api.py::TestAgentStream::test_heartbeat_emitted -x` (uses fake-slow-agent fixture) | ❌ Wave 0 |
| BACK-05 | Heartbeat payload is `{"ts": "<ISO-8601>"}` | unit | `pytest tests/test_sse_contract.py::test_heartbeat_payload_shape -x` | ❌ Wave 0 |
| BACK-06 | `/agent/stream` enforces `agent_timeout_seconds` (default 60s) | integration | `pytest tests/test_api.py::TestAgentStream::test_timeout_emits_error -x` (uses fake-hanging-agent + `settings.agent_timeout_seconds=2`) | ❌ Wave 0 |
| BACK-06 | Timeout emits `event: error` with `reason="agent_timeout"` then closes stream | integration | (same test) | ❌ Wave 0 |
| BACK-06 | Internal exceptions emit sanitized error event (no stack traces) | unit | `pytest tests/test_api.py::TestAgentStream::test_internal_exception_sanitized -x` | ❌ Wave 0 |
| BACK-07 | `alembic upgrade head` against fresh DB creates all tables | integration | `pytest tests/test_alembic.py::test_upgrade_head_creates_schema -x` (requires postgres service in CI) | ❌ Wave 0 |
| BACK-07 | `alembic upgrade head` is idempotent | integration | `pytest tests/test_alembic.py::test_upgrade_head_twice_is_noop -x` | ❌ Wave 0 |
| BACK-07 | `init-db` CLI delegates to alembic | unit | `pytest tests/test_cli.py::test_init_db_runs_alembic -x` (mock alembic.command.upgrade) | ❌ Wave 0 |
| BACK-08 | `user_profile.user_id` has NO DDL DEFAULT | unit | `pytest tests/test_alembic.py::test_no_default_uuid_on_user_id_columns -x` | ❌ Wave 0 |
| BACK-08 | `users` table seeded with `SEEDED_USER_ID` | integration | `pytest tests/test_alembic.py::test_seed_user_inserted -x` | ❌ Wave 0 |
| BACK-08 | `get_current_user_id()` returns `SEEDED_USER_ID` in v1 | unit | `pytest tests/test_auth.py::test_get_current_user_id_v1 -x` | ❌ Wave 0 |
| BACK-09 | `job_postings.career_id` has DDL DEFAULT `'ai_engineer'` | integration | `pytest tests/test_alembic.py::test_career_id_default_ai_engineer -x` | ❌ Wave 0 |
| BACK-09 | Existing postings get `'ai_engineer'` after migration | integration | `pytest tests/test_alembic.py::test_career_id_backfilled -x` | ❌ Wave 0 |
| BACK-10 | `MarkdownFileSource` yields one `RawPosting` per .md file | unit | `pytest tests/test_ingestion.py::test_markdown_file_source_yields -x` | ❌ Wave 0 |
| BACK-10 | `MarkdownFileSource` satisfies `IngestionSource` Protocol | unit | `pytest tests/test_ingestion.py::test_markdown_file_source_is_ingestion_source -x` (`isinstance` check) | ❌ Wave 0 |
| BACK-10 | `ingest_from_source` end-to-end: extracts, embeds, stores | integration | `pytest tests/test_ingestion.py::test_ingest_from_source_roundtrip -x` (requires DB or extensive mocking) | ❌ Wave 0 |
| BACK-10 | Sync `ingest_file` still works (CLI compatibility) | integration | `pytest tests/test_ingestion.py::test_ingest_file_sync_compat -x` | (existing test extended) |
| BACK-10 | `job-rag ingest data/postings/` end-to-end | smoke (manual) | `make smoke-ingest` or doc'd manual step | manual-only |

**Manual-only justification:** the full `job-rag ingest data/postings/` end-to-end smoke test requires real OpenAI API calls (extraction + embeddings) + a live DB. Cost and non-determinism make it inappropriate for CI. Manual test runs at phase-completion gate.

### Anti-regression / Cross-cutting tests

These don't map to a single requirement but verify Phase 1's overall correctness:

| Behavior | Test | Type |
|---|---|---|
| No `GZipMiddleware` is added to the app | `pytest tests/test_api.py::test_no_gzip_middleware -x` | unit (introspect `app.user_middleware`) |
| `Content-Encoding: identity` header on SSE response | `pytest tests/test_api.py::TestAgentStream::test_content_encoding_identity -x` | integration |
| `X-Accel-Buffering: no` header on SSE response | `pytest tests/test_api.py::TestAgentStream::test_x_accel_buffering -x` | integration |
| Existing tests still pass (regression) | `pytest -m "not eval"` | full suite |
| `alembic check` shows no drift after baseline + 0002 + 0003 | manual / CI | optional CI step |

### Sampling Rate

- **Per task commit:** `uv run pytest -m "not eval" -x --tb=short` (~30s for unit + mocked integration; postgres-requiring tests skipped if DB not available)
- **Per wave merge:** `uv run pytest -m "not eval"` plus `uv run alembic upgrade head` against a fresh DB
- **Phase gate:** Full suite green + manual `job-rag ingest data/postings/` smoke + `docker-compose up` → first chat streams

### Wave 0 Gaps

The existing test suite covers extraction, matching, retrieval, models, and basic API endpoints (health, search), but Phase 1's new behavior is entirely new test territory. Wave 0 must create:

- [ ] `tests/test_alembic.py` — migration smoke + grep guard for DEFAULT.uuid
- [ ] `tests/test_sse_contract.py` — Pydantic event union + OpenAPI schema test
- [ ] `tests/test_lifespan.py` — reranker preloaded; shutdown drain emits error events
- [ ] `tests/test_ingestion.py` — Protocol satisfaction + MarkdownFileSource + ingest_from_source roundtrip
- [ ] `tests/test_auth.py` — `get_current_user_id` returns SEEDED_USER_ID
- [ ] `tests/test_cli.py` — `init-db` delegates to alembic command
- [ ] Extend `tests/test_api.py` — TestCORS class, TestAgentStream extensions for heartbeat/timeout/sanitization/headers
- [ ] Extend `tests/test_retrieval.py` — `rerank` uses `asyncio.to_thread`; event loop responsiveness during rerank
- [ ] Extend `tests/conftest.py` — fixture for fake-slow-agent (yields tokens with sleep) and fake-hanging-agent (never yields)
- [ ] Add `asgi-lifespan` to dev deps (`uv add --dev asgi-lifespan`) for lifespan-aware ASGITransport tests
- [ ] Framework install: `uv add 'alembic>=1.18,<1.19'` — only new runtime/dev dep
- [ ] `.github/workflows/ci.yml` extension: postgres service container + `alembic upgrade head` step + grep guard step

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md is largely a static codebase descriptor (it lists the existing tech stack, conventions, and architecture). The actionable constraints relevant to Phase 1:

- **Python version:** 3.12 (pyproject.toml `requires-python = ">=3.12"`). Match in CI and Dockerfile.
- **Line length:** 100 chars (ruff). New files must comply.
- **Type hints:** required on all public functions; `dict[str, Any]` for loose returns; `|` for unions.
- **Imports:** absolute only (no `from . import`, no path aliases).
- **Async/sync split:** services layer is async; CLI is sync; new code follows.
- **Naming:** `snake_case` modules, `PascalCase` classes, `_private` for module state, `DB` suffix for ORM models.
- **Logging:** `structlog` via `get_logger(__name__)`, structured kwargs (`log.info("event_name", key=value)`).
- **GSD workflow:** start work via GSD commands. Phase 1 is the first phase; planner enters via `/gsd-plan-phase`.
- **Tech stack frozen:** Python 3.12, FastAPI, LangGraph 1.1.x, PostgreSQL 17 + pgvector, SQLAlchemy 2.x async, Instructor, OpenAI SDK. No new backend frameworks.

These are project-wide; the planner verifies new code follows them.

---

## Sources

### Primary (HIGH confidence)

- [Pydantic v2 Unions docs](https://pydantic.dev/docs/validation/latest/concepts/unions/) — discriminated union pattern with `Annotated[Union[...], Field(discriminator=...)]`
- [Alembic autogenerate documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) — known limitations (Enum, custom types, server_default)
- [Alembic discussion #1324: pgvector autogenerate](https://github.com/sqlalchemy/alembic/discussions/1324) — `ischema_names` workaround in env.py
- [sse-starlette source: sse_starlette/sse.py](https://github.com/sysid/sse-starlette/blob/main/sse_starlette/sse.py) — exact constructor signature: `ping`, `ping_message_factory`, `shutdown_event`, `shutdown_grace_period`, default headers (`X-Accel-Buffering: no`, `Cache-Control: no-store`, `Connection: keep-alive`), `NotImplementedError` for compression
- [sse-starlette README + DeepWiki](https://github.com/sysid/sse-starlette) — cooperative shutdown pattern with `anyio.Event`
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/) — async context-manager pattern, app.state for shared resources
- [FastAPI server-sent events tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/) — native `fastapi.sse.EventSourceResponse` (0.135+) — used as comparison; not adopted in this phase
- [FastAPI commit 22381558: Add support for SSE](https://github.com/fastapi/fastapi/commit/22381558446c5d1ac376680a6581dd63b3a04119) — confirmed native EventSourceResponse lacks `shutdown_event` and only emits `:ping` comments
- [PyPI: Alembic 1.18.4](https://pypi.org/project/alembic/) — released 2026-02-10, SQLAlchemy 2.x compatible
- [PyPI: sse-starlette 3.3.4](https://pypi.org/project/sse-starlette/) — released 2026-03-29, Python ≥3.10
- [PyTorch forums: Is inference thread-safe?](https://discuss.pytorch.org/t/is-inference-thread-safe/88583) — read-only forward pass is safe; performance does not improve under contention
- [LangGraph issue #5682: Subgraph cancellation](https://github.com/langchain-ai/langgraph/issues/5682) — cancellation bug ONLY affects nested subgraphs (irrelevant to flat ReAct agent)
- [LangGraph streaming docs](https://docs.langchain.com/oss/python/langgraph/streaming) — `astream_events`, version="v2"
- [Python typing Protocols](https://typing.python.org/en/latest/reference/protocols.html) — `runtime_checkable` only checks attribute presence, not signatures
- [PEP 525: Asynchronous Generators](https://peps.python.org/pep-0525/) — `__aiter__` / `__anext__` semantics

### Secondary (MEDIUM confidence)

- [sentence-transformers issue #857](https://github.com/UKPLab/sentence-transformers/issues/857) — concurrent encode does not parallelize on CPU
- [hey-api/openapi-ts issue #3270](https://github.com/hey-api/openapi-ts/issues/3270) — TS codegen does not auto-narrow OpenAPI discriminator unions; explicit type guards needed in SPA

### Tertiary (LOW confidence — flagged for validation)

- None for Phase 1. All claims either VERIFIED via library source code / official docs, or CITED from PITFALLS.md / ARCHITECTURE.md / STACK.md (themselves HIGH-confidence).

### Internal references (HIGH-confidence, derived from in-repo audit)

- `.planning/phases/01-backend-prep/01-CONTEXT.md` — 29 locked decisions D-01..D-29
- `.planning/REQUIREMENTS.md` BACK-01..BACK-10 — phase scope
- `.planning/ROADMAP.md` Phase 1 — goal + 5 success criteria
- `.planning/research/PITFALLS.md` Pitfalls 3, 5, 6, 8, 9, 18 — directly drive Phase 1 decisions
- `.planning/research/ARCHITECTURE.md` §3, §7, §8 — SSE through ACA, user_id model, IngestionSource Protocol
- `.planning/research/STACK.md` — Alembic 1.18.x version pin, sse-starlette confirmation
- `.planning/codebase/CONCERNS.md` web-UI blockers 1-7 — Phase 1's scope
- `.planning/codebase/STRUCTURE.md` — package layout
- `.planning/codebase/CONVENTIONS.md` — coding style
- `.planning/codebase/TESTING.md` — pytest-asyncio + ASGITransport patterns
- Current source files: `src/job_rag/api/app.py`, `src/job_rag/api/routes.py`, `src/job_rag/agent/stream.py`, `src/job_rag/db/engine.py`, `src/job_rag/db/models.py`, `src/job_rag/services/ingestion.py`, `src/job_rag/services/retrieval.py`, `src/job_rag/services/matching.py`, `src/job_rag/config.py`, `src/job_rag/agent/graph.py`, `src/job_rag/cli.py`, `docker-compose.yml`, `Dockerfile`, `pyproject.toml`, `.github/workflows/ci.yml`

---

## Metadata

**Confidence breakdown:**
- Standard stack (Alembic 1.18.x; sse-starlette 3.3.4; existing FastAPI/SQLAlchemy/pgvector unchanged): **HIGH** — all versions verified on PyPI 2026-04-24; SSE library API verified directly from source code.
- Architecture (lifespan + shutdown_event + active task set + reranker preload + asyncio.to_thread + asyncio.timeout): **HIGH** — every component documented in linked sources; pattern combination is canonical (FastAPI lifespan + sse-starlette cooperative shutdown).
- Pitfalls (pgvector ischema, asyncio.wait_for cancellation, CrossEncoder threading, init_db subprocess): **HIGH** — all verified against issue trackers and source code.
- Validation architecture (test inventory, Wave 0 gaps): **HIGH** — direct mapping from BACK-01..BACK-10 to specific test files; test framework already in place.
- Code examples: **HIGH** — assembled from verified library APIs; not unproven snippets.

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (estimate — sse-starlette and Alembic are stable; unlikely to introduce breaking changes in 30 days; FastAPI 0.x line moves faster but the SSE features used are 0.135+ stable)
