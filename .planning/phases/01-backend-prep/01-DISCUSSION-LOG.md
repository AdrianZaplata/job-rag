# Phase 1: Backend Prep - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 01-backend-prep
**Areas discussed:** Alembic baseline strategy, user_id seeding mechanism, SSE contract shape, IngestionSource Protocol shape

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic baseline strategy | How to adopt Alembic on top of existing init_db() | ✓ |
| user_id seeding mechanism | Where Adrian's UUID comes from pre-Entra | ✓ |
| SSE contract shape (heartbeat + error + draining) | Shape of new /agent/stream events | ✓ |
| IngestionSource Protocol shape | Interface contract + RawPosting fields | ✓ |

**User's choice:** all four.

---

## Alembic baseline strategy

### Baseline approach

| Option | Description | Selected |
|--------|-------------|----------|
| Autogen + stamp existing dev DB (Recommended) | `alembic revision --autogenerate` then `alembic stamp head` the existing local DB; preserves 108-posting corpus | ✓ |
| Hand-write the baseline migration | Manual `0001_baseline.py` with every CREATE TABLE; 2–3× the work | |
| Drop dev DB + re-ingest 108 postings | Cleanest state but burns ~€0.20 + ~20 min | |
| Hybrid: autogen baseline + empty upgrade() | Generate file but leave upgrade() empty; Phase 2 becomes first real migration | |

**User's choice:** Autogen + stamp existing dev DB (Recommended).

### Alembic engine

| Option | Description | Selected |
|--------|-------------|----------|
| Sync engine + NullPool (Recommended) | psycopg2 via DATABASE_URL, no pool, matches Pitfall 8 | ✓ |
| Async engine with asyncpg | Marginally more complex env.py; buys nothing for offline script | |
| Both — try async first, fall back to sync | Overengineering for v1 | |

**User's choice:** Sync engine + NullPool (Recommended).

### pgvector extension location

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic migration 0001 (Recommended) | Version-controlled; idempotent on fresh Azure DB; matches Pitfall 9 | ✓ |
| Keep init_db() as canonical path | Conflicts with Pitfall 9 | |
| Both — migration + init_db() IF NOT EXISTS | Defense in depth but splits mental model | |

**User's choice:** Alembic migration 0001 (Recommended).

### init_db() CLI after Alembic takes over

| Option | Description | Selected |
|--------|-------------|----------|
| Replace with `alembic upgrade head` wrapper (Recommended) | Keeps CLI name, zero muscle memory lost, Alembic becomes single source of truth | ✓ |
| Delete `init_db()` and the CLI command | Breaks every existing doc/script | |
| Keep both as parallel paths | Divergence risk per CONCERNS.md | |

**User's choice:** Replace with `alembic upgrade head` wrapper (Recommended).

### Migration filename convention

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential integers `NNNN_*.py` (Recommended) | Human-readable order, matches Pitfall 9 example | ✓ |
| Alembic default short UUIDs | Collision-proof but unreadable | |
| Date-prefixed `YYYY_MM_DD_*.py` | Verbose; git already provides timestamps | |

**User's choice:** Sequential integers (Recommended).

---

## user_id seeding mechanism

### UUID source

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded constant in a Python module (Recommended) | `SEEDED_USER_ID = UUID(...)` once; visible in git, reproducible | ✓ |
| Env var `SEEDED_USER_ID` read by migration | Env vars in migrations is an antipattern | |
| Generate at first boot, persist in DB | Opaque, different across fresh clones | |
| Use Adrian's future Entra OID placeholder | Circular dependency on Phase 4 | |

**User's choice:** Hardcoded constant in a Python module (Recommended).

### Users table model

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `users` table with FK from user-scoped tables (Recommended) | Normalized; matches Pitfall 18 "FK from day 1 so orphaned rows fail loudly" | ✓ |
| user_profile IS the users table | Couples identity to profile; awkward for future tables | |
| Bare UUID column, no FK, no users table | Orphan rows possible; painful retrofit later | |

**User's choice:** Dedicated `users` table with FK from user-scoped tables (Recommended).

### Auth resolution before Phase 4

| Option | Description | Selected |
|--------|-------------|----------|
| Dev-mode `get_current_user_id()` returns SEEDED_USER_ID (Recommended) | Single dependency; Phase 4 is a one-file body swap | ✓ |
| Feature flag `AUTH_MODE=dev\|entra` | Extra surface area; YAGNI for single-user | |
| Accept `X-User-Id` header in dev | Forgeable identity in production; security footgun | |

**User's choice:** Dev-mode `get_current_user_id()` returns SEEDED_USER_ID (Recommended).

### user_id scope in Phase 1

| Option | Description | Selected |
|--------|-------------|----------|
| Only `user_profile` (Recommended) | Shared-corpus tables stay shared; matches single-user-platform-ready scope | ✓ |
| Also add user_id to job_postings ("my postings" path) | Premature; conflicts with project scope | |
| Leave user_profile for Phase 7 | Conflicts with Phase 1 success criterion #4 | |

**User's choice:** Only `user_profile` (Recommended).

---

## SSE contract shape

### Heartbeat framing

| Option | Description | Selected |
|--------|-------------|----------|
| Typed event: `event: heartbeat` + `data: {"ts": "..."}` (Recommended) | Visible in EventStream tab; discoverable in OpenAPI; self-documenting | ✓ |
| SSE comment `: ping\n\n` | Invisible to EventSource/onmessage; undiscoverable in OpenAPI | |
| Both — comment + typed heartbeat | Overengineering for v1 | |

**User's choice:** Typed event (Recommended).

### Timeout + shutdown event shape

| Option | Description | Selected |
|--------|-------------|----------|
| New `event: error` with structured reason (Recommended) | Distinct type; BACK-06 literally says "SSE error event"; branch-able by reason | ✓ |
| Reuse `event: final` with `{"aborted": true, ...}` | Conflates success and failure | |
| HTTP-level error (abort stream with 500) | Won't reach client mid-stream | |

**User's choice:** New `event: error` type with structured reason (Recommended).

### Shutdown draining scope

| Option | Description | Selected |
|--------|-------------|----------|
| Include minimal draining in Phase 1 (Recommended) | Track active tasks, emit error-shutdown, gather with 30s budget; closes Pitfall 5 | ✓ |
| Defer draining to Phase 3 | Leaves Pitfall-5 truncation window open on deploys | |
| Do both — app-level drain + Terraform grace period | Belt and suspenders | |

**User's choice:** Include minimal draining in Phase 1 (Recommended).

**Note:** Phase 3 still gets `terminationGracePeriodSeconds=120` as belt-and-suspenders. Tracked in Deferred.

### Pydantic model shape

| Option | Description | Selected |
|--------|-------------|----------|
| Discriminated union on `type` field (Recommended) | Cleanly documented in OpenAPI; openapi-typescript gives frontend types | ✓ |
| Separate endpoints per event type | Not applicable for SSE | |
| Untyped `dict[str, Any]` | Defeats BACK-02 purpose | |

**User's choice:** Discriminated union (Recommended).

---

## IngestionSource Protocol shape

### Interface I/O

| Option | Description | Selected |
|--------|-------------|----------|
| Async iterator (`async def __aiter__`) returning `RawPosting` (Recommended) | Natural fit for future HTTP-bound scrapers; sync file reads wrap in asyncio.to_thread | ✓ |
| Sync iterator, async wrapper at call site | Scrapers pay the async-in-thread-pool tax forever | |
| Callable: `def fetch() -> list[RawPosting]` | Buffers everything in memory; iterator streams | |

**User's choice:** Async iterator (Recommended).

### RawPosting fields

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: `raw_text`, `source_url`, `source_id` (Recommended) | Extraction + hashing downstream; Protocol free of extraction concerns | ✓ |
| Include pre-extracted metadata (title, company, etc.) | Creates branch in pipeline | |
| Include `fetched_at: datetime` | (Folded into Recommended — acknowledged and added) | |

**User's choice:** Minimal fields (Recommended). `fetched_at` added per the option's inline note.

### content_hash location

| Option | Description | Selected |
|--------|-------------|----------|
| Ingestion service computes hash from `raw_text` (Recommended) | Sources stay minimal; algorithm in one place | ✓ |
| Source computes hash, passes it in RawPosting | Premature caching optimization | |
| Both — service hashes, source can override | Acceptable but deferred | |

**User's choice:** Ingestion service computes hash (Recommended).

### Module location

| Option | Description | Selected |
|--------|-------------|----------|
| `src/job_rag/services/ingestion.py` next to `ingest_file` (Recommended) | Co-located with consumer; ~80 lines in existing file | ✓ |
| New module `src/job_rag/ingestion/` package | Overbuilding for 1 source | |
| New module `src/job_rag/services/sources.py` | 2-file dance for v1 | |

**User's choice:** `src/job_rag/services/ingestion.py` (Recommended).

### Async Protocol + sync pipeline bridging

| Option | Description | Selected |
|--------|-------------|----------|
| Thin async consumer; existing sync callers use `asyncio.run()` (Recommended) | Minimal churn, CLI unchanged, defers full refactor | ✓ |
| Full async-ingest refactor now | Bigger change; adds scope beyond BACK-10 | |
| Defer — ship Protocol only, pipeline untouched | Fails success criterion #5 | |
| Ready for context — trust Claude's call | (not needed — Recommended selected directly) | |

**User's choice:** Thin async consumer (Recommended).

---

## Claude's Discretion

Captured in CONTEXT.md `<decisions>` §"Claude's Discretion":
- Specific UUID value for `SEEDED_USER_ID`
- Whether `career_id` gets an index
- Exact Pydantic field names inside SSE event types (keeping symmetry with current shape)
- Shutdown drain budget exact value (chose 30s within 15–60s range)
- Optional heartbeat payload fields
- `asyncio.to_thread` scope inside the reranker
- Test-coverage strategy for heartbeat/timeout

## Deferred Ideas

Captured in CONTEXT.md `<deferred>`:
- Full async-ingest pipeline refactor (foundations land in Phase 1, full cutover later)
- Prompt-injection sanitization for RAG/agent paths
- Redis rate limiter + `X-Forwarded-For`
- `/health` extended OpenAI connectivity check
- raw_text DB-layer size cap
- Terraform `terminationGracePeriodSeconds=120` (Phase 3)
- Heartbeat-driven liveness indicator UI (Phase 6 call)
- Cross-process reranker sharing (irrelevant while single-worker)
- Alembic autogen drift gate in CI (Phase 8 candidate)
