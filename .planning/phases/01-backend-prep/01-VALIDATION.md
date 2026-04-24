---
phase: 1
slug: backend-prep
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Concrete test catalogue with 29 BACK-* mappings lives in `01-RESEARCH.md § Validation Architecture`; this file is the execution contract that plan tasks bind to.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3+ with pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest -m "not eval" -x --tb=short` |
| **Full suite command** | `uv run pytest -m "not eval"` |
| **Estimated runtime** | ~30s quick (unit + mocked integration); ~90s full with postgres-service tests |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -m "not eval" -x --tb=short`
- **After every plan wave:** Run `uv run pytest -m "not eval"` plus `uv run alembic upgrade head` against a fresh DB
- **Before `/gsd-verify-work`:** Full suite green + manual `job-rag ingest data/postings/` smoke + `docker-compose up` → first chat streams
- **Max feedback latency:** 30 seconds (quick run)

---

## Per-Task Verification Map

*Populated by gsd-planner during plan generation. Each task's `<automated>` block lands here with its requirement, test type, and status. Research § Validation Architecture holds the 29 test specs planner uses as source.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _pending planner assignment_ | | | | | | | | | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

New test files Phase 1 must create before any other wave starts (inferred from 01-RESEARCH.md § Validation Architecture → Wave 0 Gaps):

- [ ] `tests/test_alembic.py` — migration smoke + grep guard for `DEFAULT.*uuid` on user_id columns + seed user + career_id default/backfill
- [ ] `tests/test_sse_contract.py` — Pydantic v2 discriminated union + OpenAPI schema test + per-event wire-shape tests (token, tool_start, tool_end, heartbeat, error, final)
- [ ] `tests/test_lifespan.py` — reranker preloaded on startup + shutdown drain emits `event: error` with `reason="shutdown"` to active streams
- [ ] `tests/test_ingestion.py` — `MarkdownFileSource` yields one `RawPosting` per .md + `isinstance` Protocol satisfaction + `ingest_from_source` end-to-end + sync `ingest_file` compat
- [ ] `tests/test_auth.py` — `get_current_user_id()` returns `SEEDED_USER_ID` in v1
- [ ] `tests/test_cli.py` — `init-db` delegates to `alembic.command.upgrade` (mock-based)
- [ ] `tests/test_api.py` — Wave 0 does NOT extend this file. The `TestCORS` class and `TestAgentStream` extensions (heartbeat emission, timeout/sanitization, `Content-Encoding: identity`, `X-Accel-Buffering: no`, no-GZipMiddleware guard, internal-exception sanitization) depend on production symbols (`_sanitize`, `_heartbeat_factory`, `app.state.shutdown_event`, `app.state.active_streams`) that only exist after Plan 06. These tests land atomically alongside Plan 06's route rewrite (Plan 06 Task 3 — test wiring). Plan 01 deliberately does not scaffold skeletons here because every CORS/Stream test is integration-level and needs the final route handlers to assert against.
- [ ] `tests/test_retrieval.py` — extend with `rerank` via `asyncio.to_thread` + event-loop responsiveness during reranking
- [ ] `tests/conftest.py` — fixtures `fake_slow_agent` (yields tokens with sleep) and `fake_hanging_agent` (never yields)
- [ ] Dev dep: `uv add --dev asgi-lifespan` for lifespan-aware ASGITransport tests
- [ ] Runtime dep: `uv add 'alembic>=1.18,<1.19'`
- [ ] `.github/workflows/ci.yml` — add Postgres service container, `alembic upgrade head` smoke step, and grep guard step

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full `job-rag ingest data/postings/` smoke | BACK-10 | Requires real OpenAI API calls (extraction + embeddings) + live DB; cost and non-determinism make it inappropriate for CI | Phase-completion gate: run `docker-compose up -d postgres && uv run job-rag init-db && uv run job-rag ingest data/postings/`; verify 108 postings stored; `\dx` in psql shows `vector` extension |
| `docker-compose up` → first chat streams (<2s first token) | BACK-03, BACK-04 | End-to-end cold-start timing requires a freshly-started container; not a unit/integration concern | Phase-completion gate: `docker-compose up`; open `http://localhost:8000/docs`; run an agent call and measure first-token latency |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter after planner binds all task IDs

**Approval:** pending
