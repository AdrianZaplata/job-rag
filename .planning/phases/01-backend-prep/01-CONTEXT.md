# Phase 1: Backend Prep - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 ships a refactored backend (no Azure provisioning, no frontend, no Entra) when:

1. The seven web-UI blockers are closed (CORS, SSE contract, preloaded reranker, async reranker call, 15s heartbeat, 60s timeout, typed agent errors).
2. Alembic owns the schema as the single source of truth.
3. A `users` + `user_profile` data model carries `user_id UUID NOT NULL` (no DB DEFAULT) ready for Phase 4's Entra `oid`.
4. `career_id TEXT NOT NULL DEFAULT 'ai_engineer'` is on `job_posting_db`.
5. `IngestionSource` Protocol exists with `MarkdownFileSource` as its v1 implementation; `job-rag ingest data/postings/` still works.

Out of scope here (later phases): Azure infra (Phase 3), Entra tenant + MSAL + JWT validation (Phase 4), Location/SkillCategory/re-extraction (Phase 2), resume upload endpoint + profile CRUD (Phase 7), RAGAS (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Alembic adoption

- **D-01:** Baseline via `alembic revision --autogenerate -m 'baseline'` against a fresh Postgres, commit the generated `0001_baseline.py`, then `alembic stamp head` the existing local dev DB. Adrian's 108-posting corpus is preserved through the transition; all schema evolves through Alembic from here on.
- **D-02:** Alembic uses the **sync** engine (psycopg2 via `DATABASE_URL`) with `NullPool`. Matches PITFALLS.md Pitfall 8 ("NullPool for short-lived scripts") and keeps migration scripts simple. Async engine is not used for migrations.
- **D-03:** `CREATE EXTENSION IF NOT EXISTS vector` moves into `0001_baseline.py`. It is the canonical path; `init_db()` loses its extension-creation responsibility.
- **D-04:** `job-rag init-db` CLI command is kept by name but internally wraps `alembic upgrade head`. `Base.metadata.create_all()` is removed from the canonical schema path. Docker-entrypoint and docs keep working without change.
- **D-05:** Migration filenames follow `NNNN_<slug>.py` sequential integers (e.g., `0001_baseline.py`, `0002_add_user_profile.py`). Single-contributor repo; ordering must be grep-readable.

### User model and `user_id`

- **D-06:** Add a dedicated `users` table in Phase 1: `users (id UUID PK, entra_oid TEXT UNIQUE NULL, email TEXT NULL, created_at TIMESTAMPTZ DEFAULT now())`. `entra_oid` is nullable in v1 (populated in Phase 4 when Entra issues the real `oid`).
- **D-07:** Add `user_profile` table in Phase 1 with `user_id UUID NOT NULL FK users(id)` plus the fields from the existing `UserSkillProfile` Pydantic model. No DB DEFAULT on `user_id` anywhere. The table is created now; data migration from `data/profile.json` is deferred to Phase 7 (PROF-01) as scoped.
- **D-08:** Adrian's UUID is a **hardcoded Python constant** `SEEDED_USER_ID: UUID` (generate once locally, commit the exact value). The baseline-baseline migration inserts his `users` row with this ID. No env-var indirection; no random-at-first-boot.
- **D-09:** Phase 4 swap-in plan for the real Entra `oid`: a dedicated migration (`00NN_adopt_entra_oid.py`) runs `UPDATE users SET id = <adrian-real-oid>, entra_oid = <adrian-real-oid> WHERE id = SEEDED_USER_ID` with the UUID cascading through FKs, then drops the `SEEDED_USER_ID` constant in the same PR. Planner for Phase 4 carries this action item.
- **D-10:** App-side user resolution: single FastAPI dependency `get_current_user_id() -> UUID`. In Phase 1 the body returns `SEEDED_USER_ID` directly; in Phase 4 the body is rewritten to parse the Entra JWT `sub` / `oid` claim. No feature flag — Phase 4 is a one-file change.
- **D-11:** `user_id` is added in Phase 1 **only to `user_profile`**. Shared-corpus tables (`job_postings`, `job_requirements`, `job_chunks`) stay shared — no `user_id` column. This matches single-user-platform-ready scope; "my postings" is not a v1 concept.
- **D-12:** CI grep guard: add a test or CI step that greps Alembic migrations for `DEFAULT.*uuid` on any `user_id` column and fails the build if matched. Prevents Pitfall 18 regression.

### `career_id` column

- **D-13:** `career_id TEXT NOT NULL DEFAULT 'ai_engineer'` added to `job_posting_db` in `0003_add_career_id.py` (after baseline + user tables). Unlike `user_id`, this column keeps a DDL DEFAULT — every corpus posting is an AI-Engineer posting in v1, and future career expansion will be explicit. Claude's Discretion on whether it's index-worthy (no immediate query needs it filtered).

### SSE event contract

- **D-14:** Event types on `/agent/stream`: `token`, `tool_start`, `tool_end`, `heartbeat`, `error`, `final`. Six total. Documented via Pydantic v2 discriminated union on the `type` field (`AgentEvent = Annotated[Union[...], Field(discriminator="type")]`), appearing in OpenAPI so `openapi-typescript` can generate frontend types.
- **D-15:** **Heartbeat** is a typed event: `event: heartbeat\ndata: {"ts": "<ISO-8601>"}`. Emitted every 15s during active reasoning. Visible to `EventSource`/`fetch`+`ReadableStream` clients; Phase 6 can choose whether to surface it as a liveness indicator or silently consume it.
- **D-16:** **Timeout** uses a new `event: error` with `{"reason": "agent_timeout", "message": "..."}` followed by natural stream close. BACK-06 literally says "graceful SSE error event" — this is that event.
- **D-17:** Shutdown draining is **included in Phase 1**. Lifespan shutdown tracks the active stream task set, emits `event: error` with `{"reason": "shutdown", "message": "..."}` to each, and `await asyncio.gather(*active, return_exceptions=True)` with a 30s budget. Phase 3's `terminationGracePeriodSeconds=120` (noted for that phase) is belt-and-suspenders on top. This closes Pitfall 5.
- **D-18:** `X-Accel-Buffering: no` header + `Content-Encoding: identity` defensive headers on the SSE response. No `GZipMiddleware` anywhere in the app (Pitfall 6).
- **D-19:** Error reasons on the `error` event are a typed literal: `agent_timeout | shutdown | llm_error | internal`. Frontend can branch on reason for retry vs. fatal. Stack traces **never** leak into error messages — sanitize to a short human-readable string (see CONCERNS.md "SSE response reveals stack trace on error").

### `IngestionSource` Protocol

- **D-20:** Protocol shape: `async def __aiter__(self) -> AsyncIterator[RawPosting]`. Async by default; sync-wrapping lives inside each source (e.g., `MarkdownFileSource` uses `asyncio.to_thread()` around file reads).
- **D-21:** `RawPosting` dataclass fields: `raw_text: str`, `source_url: str`, `source_id: str | None`, `fetched_at: datetime`. `source_id` maps to `linkedin_job_id` for the LinkedIn case; is None for bare markdown. No extracted/structured fields here — extraction stays a downstream concern.
- **D-22:** `content_hash` is computed by the ingestion service (not by the Protocol implementation) using the existing `hashlib.sha256(raw_text.encode()).hexdigest()` pattern. Future caching optimizations can add an optional `content_hash: str | None` override on `RawPosting`; not v1.
- **D-23:** Location: Protocol + `RawPosting` + `MarkdownFileSource` class all land in `src/job_rag/services/ingestion.py` alongside the existing `ingest_file`. No new package. Splitting to `src/job_rag/ingestion/` is deferred to when source #2 arrives.
- **D-24:** Wire pattern: introduce `async def ingest_from_source(async_session, source) -> IngestResult` as the new primary consumer. `ingest_file(session, path)` is rewritten to: construct a `MarkdownFileSource(path)`, call `asyncio.run(ingest_from_source(...))` under an async session (or dispatch to an async-session shim), and keep its existing sync `Session` signature so the CLI and `/ingest` endpoint keep working unchanged. Full async-ingest pipeline refactor (closing CONCERNS.md "Async/sync session dualism") is **deferred** — flagged below.

### Request timeout (BACK-06)

- **D-25:** Agent timeout: `asyncio.wait_for(agent.astream_events(...), timeout=60.0)` at the `/agent/stream` handler level. On timeout, emit `event: error` with `{"reason": "agent_timeout"}`, then close stream cleanly. 60s is app-level; must stay strictly below Container Apps' 240s Envoy cap and below Terraform's 120s grace period (Pitfall 3). Value is configurable via `AGENT_TIMEOUT_SECONDS` setting, default 60.

### CORS (BACK-01)

- **D-26:** `CORSMiddleware` configured with `allow_origins=settings.allowed_origins` (list, env-var driven, comma-split from `ALLOWED_ORIGINS`), `allow_credentials=True`, `allow_methods=["GET","POST"]`, `allow_headers=["Authorization","Content-Type"]`. Default in dev is `["http://localhost:5173"]` (Vite default); Phase 3 injects the SWA origin (DEPL-12 two-pass). **Never `*`**. No wildcard fallback.

### Reranker preload + threading (BACK-03, BACK-04)

- **D-27:** Preload in FastAPI lifespan startup: `_get_reranker()` called once (triggers the `CrossEncoder(settings.reranker_model)` load). Blocks startup for ~2–3s — acceptable; ACA cold-start already absorbs this (Pitfall 4).
- **D-28:** All `rerank()` call sites wrapped in `asyncio.to_thread(rerank, ...)` where invoked from async code (`rag_query` in `retrieval.py`; MCP tools in `mcp_server/tools.py`). The sync `rerank()` function body itself is unchanged.

### SQLAlchemy connection pool sizing

- **D-29:** Async engine config: `pool_size=3, max_overflow=2` per worker, `pool_pre_ping=True`, `pool_recycle=300` (5 min). Matches Pitfall 8 for B1ms. Alembic uses `NullPool` (see D-02). Local Docker-Compose Postgres 17 isn't connection-limited like B1ms, but using the same pool config locally surfaces connection-pressure bugs before they hit prod.

### Claude's Discretion

- `SEEDED_USER_ID` specific UUID value — generate via `uuid.uuid4()` locally, commit the literal, prefer one with a distinctive prefix that's easy to spot in logs (e.g., starts with `00000000-0000-0000-0000-` is fine; a random value is also fine; no semantic meaning needed).
- Whether `career_id` gets an index (likely not — every row is `'ai_engineer'` in v1 so the index adds nothing).
- Exact Pydantic field names inside each SSE event type (e.g., `content` vs `text` for token events) — keep symmetric with current event shapes in `src/job_rag/agent/stream.py` where possible.
- Shutdown drain budget (chose 30s) — acceptable range is 15–60s; prefer 30.
- Heartbeat payload — `{"ts": "<ISO-8601>"}` is the decision, but adding optional fields like `active_tool: str | None` is Claude's call if useful for observability.
- Whether to also wire `asyncio.to_thread()` around the reranker's tokenizer path specifically, or just the whole `rerank()` call — the latter is simpler and captures all CPU-bound work.
- Test coverage strategy for BACK-05 (heartbeat) and BACK-06 (timeout): prefer integration tests that actually run the stream with a patched slow-agent and observe emitted frames; don't unit-test the asyncio scheduler itself.

### Folded Todos

None — STATE.md shows no pending todos relevant to Phase 1.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing Phase 1.**

### Phase scope and requirements
- `.planning/REQUIREMENTS.md` §BACK-01 through §BACK-10 — the 10 v1 requirements Phase 1 owns
- `.planning/ROADMAP.md` §Phase 1 (Backend Prep) — goal + success criteria (5 concrete must-be-TRUE checks)
- `.planning/PROJECT.md` §Key Decisions — platform-ready hedges and the Entra-External-ID/Azure/Terraform frame

### Pitfalls research (HIGH-confidence, critical for this phase)
- `.planning/research/PITFALLS.md` §Pitfall 3 — 240s Envoy timeout (bounds BACK-06's 60s agent timeout)
- `.planning/research/PITFALLS.md` §Pitfall 5 — SIGTERM during revision swap drops SSE (drives D-17 draining)
- `.planning/research/PITFALLS.md` §Pitfall 6 — EventSource + gzip = buffered garbage (drives D-18 headers)
- `.planning/research/PITFALLS.md` §Pitfall 8 — B1ms Postgres connection exhaustion (drives D-02 NullPool + D-29 pool sizing)
- `.planning/research/PITFALLS.md` §Pitfall 9 — pgvector per-database (drives D-03 extension in migration)
- `.planning/research/PITFALLS.md` §Pitfall 18 — `user_id` DEFAULT collision (drives D-07/D-08/D-10/D-12)
- `.planning/research/PITFALLS.md` §"Looks Done But Isn't Checklist" — Phase 1 verifiers: JWT sanity, SSE streams real events, `\dx` shows vector, `user_id` has no DEFAULT

### Codebase audit (what exists, what breaks)
- `.planning/codebase/CONCERNS.md` §"Critical Blockers for Web UI" — 1-7 all close in Phase 1
- `.planning/codebase/CONCERNS.md` §"No CORS configuration" — BACK-01 target
- `.planning/codebase/CONCERNS.md` §"Streaming contract is undocumented" — BACK-02 target
- `.planning/codebase/CONCERNS.md` §"Reranker model loaded lazily" + §"Reranking runs synchronously" — BACK-03/04 targets
- `.planning/codebase/CONCERNS.md` §"Long-running agent queries are not time-bounded" — BACK-06 target
- `.planning/codebase/CONCERNS.md` §"No multi-tenancy or user isolation" + §"Profile is hardcoded file" — BACK-08 / Phase 7 setup
- `.planning/codebase/CONCERNS.md` §"Async/sync session dualism in ingest endpoint" — flagged deferred, not closed in Phase 1 (see Deferred Ideas)
- `.planning/codebase/STRUCTURE.md` — package layout for `src/job_rag/api/`, `db/`, `services/`
- `.planning/codebase/CONVENTIONS.md` — naming (snake_case), type hints required, structured logging via `structlog`
- `.planning/codebase/TESTING.md` — test layout + pytest-asyncio patterns for async endpoints

### Current backend state (files Phase 1 will touch)
- `src/job_rag/api/app.py` — lifespan for CORS middleware, reranker preload, shutdown draining hooks
- `src/job_rag/api/routes.py` §agent_stream (lines 132-147) — SSE handler → adds heartbeat, timeout, error events
- `src/job_rag/agent/stream.py` — event generator → adds heartbeat emission, error-event shape
- `src/job_rag/db/engine.py` §`init_db()` — gets replaced by `alembic upgrade head` wrapper
- `src/job_rag/db/models.py` — add `UserDB`, `UserProfileDB`; add `career_id` column to `JobPostingDB`
- `src/job_rag/services/ingestion.py` — add `IngestionSource` Protocol, `RawPosting`, `MarkdownFileSource`, `ingest_from_source`
- `src/job_rag/services/retrieval.py` §`rerank` call sites — wrap in `asyncio.to_thread()`
- `src/job_rag/services/matching.py` §`load_profile()` — currently reads `data/profile.json`; keep reading it in Phase 1 but take `user_id` parameter for forward compatibility (Phase 7 flips the source to DB)
- `src/job_rag/config.py` — new settings: `allowed_origins: list[str]`, `seeded_user_id: UUID`, `agent_timeout_seconds: int`, `heartbeat_interval_seconds: int`

### Stack / architecture baselines
- `.planning/research/STACK.md` — Alembic + fastapi-azure-auth + pypdf version pins (fastapi-azure-auth and pypdf are Phase 4/7, Alembic is Phase 1)
- `.planning/research/ARCHITECTURE.md` — target topology (Phase 1 must not break the existing three-tier layering: Ingestion → Retrieval+Matching → Intelligence/Tools)
- `.planning/codebase/ARCHITECTURE.md` — how current abstractions compose (Protocol pattern already used for MCP tools)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FastAPI lifespan pattern** (`src/job_rag/api/app.py` lines 10-13) — already uses `@asynccontextmanager`; extend it for reranker preload + shutdown draining without new scaffolding.
- **Dual engine pattern** (`src/job_rag/db/engine.py`) — sync `SessionLocal` and async `AsyncSessionLocal` coexist; `ingest_from_source` consumes async, existing `ingest_file` callers keep sync.
- **structlog logger** (`src/job_rag/logging.py`) — `get_logger(__name__)` pattern everywhere; use for all Phase 1 observability.
- **Pydantic Settings** (`src/job_rag/config.py`) — env-var + `.env` loading already wired; add new settings here.
- **Tenacity retry decorator** (seen in `src/job_rag/extraction/extractor.py`) — template for any new transient-failure retries, if needed (likely not in Phase 1).
- **FastMCP Protocol-style pattern** (`src/job_rag/mcp_server/tools.py`) — proof that Protocols fit this codebase cleanly; `IngestionSource` follows similar shape.

### Established Patterns
- **Absolute imports** from `job_rag.services.*` — no relative imports, no path aliases.
- **Type hints on all signatures**; `dict[str, Any]` for loose returns, Pydantic models for structured ones.
- **Event schema today** (`src/job_rag/agent/stream.py`) — `{"type": "token", "content": "..."}` etc. Phase 1's Pydantic models must preserve this wire shape so no frontend regression; just add two new types.
- **SQLAlchemy 2.x Mapped[] syntax** (`src/job_rag/db/models.py`) — `mapped_column(..., nullable=False)`, `Mapped[uuid.UUID]`. New `UserDB` / `UserProfileDB` follow this exactly.
- **Prompt injection guard** (`src/job_rag/extraction/extractor.py` `_sanitize_delimiters`) — reminder that LLM inputs can be adversarial; not directly Phase 1 scope but the SSE error-message sanitization (D-19) is the analogue.

### Integration Points
- `docker-compose.yml` — envs passed through; need to add `ALLOWED_ORIGINS` and verify Postgres is pgvector/pg17 image (it is; no change).
- `docker-entrypoint` script calls `job-rag init-db` on startup — after D-04 this is still the entry point, now wrapping Alembic.
- `.github/workflows/ci.yml` — currently runs ruff + pyright + pytest + pip-audit; add `alembic upgrade head` smoke step and the `grep DEFAULT uuid` guard (D-12).
- `/health` endpoint — currently checks DB only; Phase 1 extends (optionally) to also report reranker-ready status.
- Existing `JOB_RAG_API_KEY` Bearer auth stays in Phase 1; Phase 4 layers Entra JWT validation on top. Phase 1 **does not remove** the bearer auth — the `get_current_user_id()` dependency is orthogonal.

</code_context>

<specifics>
## Specific Ideas

- Adrian consistently selected the Recommended option across all 17 sub-decisions, signalling trust in the recommendations once the tradeoffs were explicit. Downstream agents should continue to present recommendations with rationale, not bare alternatives.
- The seeded-UUID-to-Entra-oid migration (D-09) is a specific, testable artifact Phase 4's planner must carry forward. Do not silently drop the `SEEDED_USER_ID` constant without the migration.
- The CI `grep DEFAULT uuid` guard (D-12) is a concrete mechanism, not just a code-review habit. Implement it as a small pytest or a workflow step.
- SSE contract should be documented in a human-readable way too — `docs/topology.md` or README mention in Phase 8 (DOCS-03) will consume the Pydantic models for its spec section. Plant a hook so Phase 8 doesn't have to reverse-engineer.

</specifics>

<deferred>
## Deferred Ideas

- **Full async-ingest pipeline refactor.** Closing CONCERNS.md "Async/sync session dualism" for `/ingest` and the CLI is explicit non-scope for Phase 1 (D-24 compromise). Candidate for a standalone plan in Phase 2 or a v2 tech-debt phase. The Protocol + async consumer in Phase 1 is the foundation; migrating callers can happen incrementally.
- **Prompt-injection sanitization applied to all LLM inputs.** Today only extraction sanitizes; RAG + agent send raw posting content to the LLM (CONCERNS.md §"Prompt injection mitigation only in extraction"). Not in Phase 1 scope — safer posture but out of band for BACK-01..10. Candidate for a security-hardening pass after Phase 8.
- **Rate-limiter moved to Redis / `X-Forwarded-For` support.** In-process per-IP limiter is fine for ACA single-replica v1. Deferred to when horizontal scaling actually arrives (post-v1).
- **`/health` endpoint checks OpenAI connectivity.** CONCERNS.md flagged this; valuable but not a web-UI blocker. Candidate for Phase 8 documentation hardening or a separate observability plan.
- **Uploading raw_text size cap at DB layer.** Text column is unbounded today; bump this if/when real attacker input becomes a concern. Not Phase 1.
- **Terraform `terminationGracePeriodSeconds = 120`.** D-17 handles the app-level drain. The Terraform resource-level value is a Phase 3 concern — planner for Phase 3 must carry this. (STATE.md Open Question resolved: app-level drain in Phase 1, Terraform grace period in Phase 3.)
- **Liveness indicator UI from heartbeat events.** Phase 6 (Chat) decision. Phase 1 only exposes the event; Phase 6 chooses whether to render anything.
- **Cross-process model sharing for the reranker.** CONCERNS.md flagged multi-worker memory duplication; ACA runs single-worker in v1 (scale-to-zero + max-replicas=1), so irrelevant. Revisit only if horizontal scaling arrives.
- **Alembic autogeneration diff gate in CI.** A check like "if `alembic upgrade head && alembic check` shows drift, fail" is a nice-to-have. Candidate for Phase 8 CI hardening.

</deferred>

---

*Phase: 01-backend-prep*
*Context gathered: 2026-04-24*
