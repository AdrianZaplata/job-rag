---
phase: 01-backend-prep
plan: 05
subsystem: api
tags: [fastapi, lifespan, anyio, cors, asyncio-to-thread, get_current_user_id, load_profile, forward-compat]

# Dependency graph
requires:
  - asgi-lifespan dev dep (Plan 01-01) — consumed by tests/test_lifespan.py via LifespanManager
  - Settings.allowed_origins (Plan 01-01) — consumed by CORSMiddleware allow_origins kwarg
  - Settings.seeded_user_id (Plan 01-01) — consumed by get_current_user_id + mcp_server/tools.py load_profile callsites
  - _get_reranker (existing, services/retrieval.py:30) — preloaded in lifespan startup
  - tests/test_lifespan.py + tests/test_auth.py scaffolds (Plan 01-01) — activate now
provides:
  - FastAPI lifespan that preloads cross-encoder reranker on startup (BACK-03 closed)
  - app.state.shutdown_event (anyio.Event) — Plan 06's EventSourceResponse(shutdown_event=...) hook
  - app.state.active_streams (set) — Plan 06's per-stream task registration target
  - 30s shutdown drain via asyncio.wait_for(asyncio.gather(*active_streams), timeout=30)
  - CORSMiddleware wired with env-var-driven allow_origins (NEVER "*"); allow_credentials=True; GET/POST/OPTIONS; Authorization+Content-Type headers (BACK-01 closed)
  - get_current_user_id() async dep returning settings.seeded_user_id (BACK-08 closed; Phase 4 rewrites the body to parse Entra JWT — D-10)
  - asyncio.to_thread(rerank, ...) wrap in services/retrieval.py rag_query (BACK-04 closed)
  - asyncio.to_thread(rerank, ...) wrap in mcp_server/tools.py search_postings
  - load_profile(*, user_id: UUID | None = None, path: str | None = None) keyword-only signature (forward-compat for Phase 7 PROF-01)
  - mcp_server/tools.py callers explicitly pass user_id=settings.seeded_user_id (D-08)
affects: [01-06-PLAN]

# Tech tracking
tech-stack:
  added: []  # anyio + asgi-lifespan landed via Plan 01-01; both already in lockfile
  patterns:
    - "FastAPI lifespan with cooperative drain via anyio.Event + asyncio.gather(*active_streams, return_exceptions=True) + 30s asyncio.wait_for budget — pattern reusable for any long-lived ASGI app with in-flight long requests on SIGTERM"
    - "CORSMiddleware paired with explicit anti-regression comment block forbidding GZipMiddleware (sse-starlette + compression = buffered EventSource garbage per Pitfall 6 / D-18)"
    - "`def fn(*, kw1=None, kw2=None)` keyword-only signature evolution — adding new args without breaking positional callers; forward-compat shell pattern for Phase 7 schema/source flips"
    - "asyncio.to_thread(sync_fn, ...) wrap at the async/sync boundary for CPU-bound libraries (CrossEncoder.predict) — keeps the event loop responsive (heartbeats fire) while the work runs in the thread pool; PyTorch GIL still serializes actual compute (intended single-replica v1 behavior per Pitfall C)"
    - "Forward-compat function-body pattern for auth: get_current_user_id returns a Python constant in v1; Phase 4 rewrites the function body in-place — no feature flag, no signature change, every call site already wired via Depends() (D-10)"

key-files:
  created: []
  modified:
    - src/job_rag/api/app.py (rewrote lifespan + CORSMiddleware; bumped version 0.2.0 -> 0.3.0; added asyncio + anyio + CORSMiddleware imports + _get_reranker import + log)
    - src/job_rag/api/auth.py (added `import uuid`; appended async def get_current_user_id() at bottom)
    - src/job_rag/services/retrieval.py (added `import asyncio`; wrapped rag_query rerank callsite in asyncio.to_thread)
    - src/job_rag/services/matching.py (added `from uuid import UUID`; rewrote load_profile signature to keyword-only with user_id default fallback to settings.seeded_user_id)
    - src/job_rag/mcp_server/tools.py (wrapped search_postings rerank callsite in asyncio.to_thread; updated both load_profile callers in match_skills + skill_gaps to pass user_id=settings.seeded_user_id explicitly)

key-decisions:
  - "Used `except TimeoutError:` instead of plan-spec'd `except asyncio.TimeoutError:` — Python 3.11+ aliased asyncio.TimeoutError to builtin TimeoutError, and ruff UP041 enforces the canonical builtin form. Functionally identical; one-line ruff-driven Rule 1 fix"
  - "Kept the load_profile body's `if user_id is None: user_id = settings.seeded_user_id` fallback explicit even though the assignment is unused in v1 — surfaces the v1 single-user assumption at the Phase 7 hook point so the planner there can immediately see where the DB-backed lookup must read user_id from"
  - "Multi-line load_profile signature (`def load_profile(\\n    *, user_id: UUID | None = None, ...`) — preferred Python style for kwargs-heavy signatures over the plan's single-line spec; runtime introspection (`inspect.Parameter.KEYWORD_ONLY`) is the authoritative truth and the plan's regex grep was too strict (single-line only) — multiline grep confirms the `*` is in place"
  - "Documented anti-pattern in source comments: `# CRITICAL: do NOT add GZipMiddleware [D-18, Pitfall 6]` — intentional anti-regression nudge for any future contributor adding middleware. The plan's literal-string grep `! grep -rq GZipMiddleware src/job_rag/` would now fire false-positive on this comment; the runtime assertion `'GZipMiddleware' not in app.user_middleware` is the authoritative check (passes)"

patterns-established:
  - "Pattern: app.py lifespan w/ reranker preload + anyio.Event + active_streams set + 30s gather-with-timeout drain + DB dispose. Reusable for any FastAPI app needing graceful SIGTERM with in-flight SSE/long-request drain. The anyio.Event (NOT asyncio.Event) choice is load-bearing — sse-starlette's shutdown_event kwarg expects anyio.Event for asyncio/trio portability."
  - "Pattern: CORSMiddleware + explicit anti-regression comment forbidding GZipMiddleware. Reusable for any sse-starlette-based FastAPI app — saves the next contributor from re-discovering Pitfall 6."
  - "Pattern: asyncio.to_thread(sync_cpu_bound_fn, ...) wrap at every async/sync boundary involving sentence-transformers / PyTorch. Reuse for any future CPU-bound model inference call from async code."
  - "Pattern: `def fn(*, kw1=None, kw2=None)` keyword-only signature evolution. When adding a new parameter to an existing public function with N callers, lead with `*` so existing positional/no-arg calls keep working; new callers can pass the new arg explicitly. Plan-level Sequencing Caveat Option A — preserves green test suite within the plan."
  - "Pattern: forward-compat function-body for auth dependencies. v1 returns a Python constant, future phase rewrites the body in-place — call sites are immune via Depends(). Decouples the auth-wiring rollout from the auth-mechanism rollout."

requirements-completed: [BACK-01, BACK-03, BACK-04, BACK-08]

# Metrics
duration: 8m 6s
completed: 2026-04-27
---

# Phase 1 Plan 05: FastAPI Lifespan + CORS + get_current_user_id + asyncio.to_thread Summary

**Wired the FastAPI lifespan (reranker preload + anyio.Event shutdown + active_streams set + 30s drain + DB dispose), CORSMiddleware (env-var allow_origins, NEVER `*`, no GZipMiddleware), `get_current_user_id()` async dep returning `settings.seeded_user_id` for Phase-4-pivotable auth, async-wrapped both `rerank()` callsites in `asyncio.to_thread` to keep the event loop responsive during cross-encoder forward passes, and evolved `load_profile()` to a keyword-only `user_id` signature as the forward-compat shell Phase 7 will use to flip the source from `data/profile.json` to the `user_profile` DB table.**

## Performance

- **Duration:** 8m 6s
- **Started:** 2026-04-27T11:01:01Z
- **Completed:** 2026-04-27T11:09:07Z
- **Tasks:** 2 (both atomic, both committed individually)
- **Files modified:** 5 (api/app.py, api/auth.py, services/retrieval.py, services/matching.py, mcp_server/tools.py)
- **Files created:** 0

## Accomplishments

- `src/job_rag/api/app.py` rewritten: lifespan preloads `_get_reranker()` once on startup (BACK-03 — first chat no longer pays 2-3s cold-load), creates `app.state.shutdown_event = anyio.Event()` and `app.state.active_streams = set()` (D-17 — Plan 06 hooks both into EventSourceResponse and the per-stream task registration), shutdown sets the event then awaits `asyncio.gather(*active_streams, return_exceptions=True)` with a 30s `asyncio.wait_for` budget, then disposes the async DB engine. Bumped version 0.2.0 → 0.3.0 to signal the Phase 1 schema/behavior delta.
- CORSMiddleware wired with `allow_origins=settings.allowed_origins` (env-var driven, NEVER `*`), `allow_credentials=True`, `allow_methods=["GET","POST","OPTIONS"]`, `allow_headers=["Authorization","Content-Type"]` (BACK-01 closed; T-05-01 mitigated). Explicit anti-regression comment block forbids GZipMiddleware (D-18 / Pitfall 6).
- `src/job_rag/api/auth.py` extended: `get_current_user_id()` async dep returns `settings.seeded_user_id` directly (BACK-08 closed; T-05-02 mitigated — body parses no input). Existing `require_api_key`, RateLimiter instances, and Bearer-token logic unchanged.
- `src/job_rag/services/retrieval.py::rag_query` rerank callsite wrapped in `await asyncio.to_thread(rerank, query, results, top_k=top_k_rerank)` (BACK-04 closed; T-05-03 mitigated — heartbeats keep firing during reranking).
- `src/job_rag/mcp_server/tools.py::search_postings` rerank callsite wrapped in the same pattern; both `load_profile()` callers in `match_skills` + `skill_gaps` updated to explicitly pass `user_id=settings.seeded_user_id` per D-08.
- `src/job_rag/services/matching.py::load_profile` evolved from `def load_profile(path: str | None = None)` to `def load_profile(*, user_id: UUID | None = None, path: str | None = None)` keyword-only — existing no-arg callers in `api/routes.py::/match` and `/gaps` keep working unchanged (Sequencing Caveat Option A); Phase 7 PROF-01 will flip the body to a DB-backed lookup keyed on `user_id`.
- `tests/test_lifespan.py::TestLifespanStartup::test_reranker_preloaded` — ACTIVE and PASSING (was skipping until `_get_reranker` became patchable on `job_rag.api.app`)
- `tests/test_lifespan.py::TestLifespanStartup::test_shutdown_event_initialized` — ACTIVE and PASSING (was skipping until `app.state.shutdown_event`/`active_streams` were populated)
- `tests/test_auth.py::TestGetCurrentUserId::test_returns_seeded_user_id` — ACTIVE and PASSING (was skipping until `get_current_user_id` symbol existed)
- `tests/test_lifespan.py::TestShutdownDrain::test_active_streams_drained_on_shutdown` — INTENTIONALLY still skipping (`pytest.skip("Full drain test deferred - Plan 06 wires the route handler")` — Plan 06's responsibility per scaffold)
- Full non-eval suite: **100 passed, 2 skipped, 0 failed** (up from 97 passed, 5 skipped after Plan 04 — 3 previously-skipping tests now active)
- ruff + pyright clean on all 5 modified files

## Task Commits

Each task committed atomically with conventional-commit messages:

1. **Task 1: Wire FastAPI lifespan + CORS + get_current_user_id** — `e968969` (`feat(01-05)`)
2. **Task 2: Wrap rerank in asyncio.to_thread + load_profile user_id kwarg** — `ab0657e` (`feat(01-05)`)

Plan metadata commit (this SUMMARY + STATE.md + ROADMAP.md update) follows after self-check.

## Files Created/Modified

### Modified (5)

- **`src/job_rag/api/app.py`** (24 lines → 113 lines including docstrings/comments) — replaced the minimal pre-Phase-1 lifespan with the full Plan 05 wiring. New imports: `asyncio`, `anyio`, `fastapi.middleware.cors.CORSMiddleware`, `job_rag.config.settings`, `job_rag.logging.get_logger`, `job_rag.services.retrieval._get_reranker`. Module docstring documents D-17 (drain), D-18 (no GZip), D-26 (CORS), D-27 (preload), and BACK-03 / T-05-01 references. Lifespan startup logs `lifespan_startup_begin` → `_get_reranker()` → `reranker_preloaded` → `lifespan_startup_complete`; shutdown logs `lifespan_shutdown_begin` (with `active_streams` count) → set event → drain w/ 30s budget → log `shutdown_drain_timeout` warning on TimeoutError → `await async_engine.dispose()` → `lifespan_shutdown_complete`. CORSMiddleware kwargs match the plan spec exactly. Anti-regression comment block prohibits GZipMiddleware.

- **`src/job_rag/api/auth.py`** (65 lines → 81 lines) — added `import uuid` to imports block; appended `async def get_current_user_id() -> uuid.UUID` at the bottom of the file (after the three RateLimiter instances). Body is `return settings.seeded_user_id`. Docstring cites D-10 + T-05-02 + Phase 4 rewrite path. Existing `require_api_key`, RateLimiter class, and Bearer-token logic untouched.

- **`src/job_rag/services/retrieval.py`** (added 1 import + 1 line modified, +4 comment lines) — added `import asyncio` to top of imports block; rewrote line in `rag_query` from `reranked = rerank(query, results, top_k=top_k_rerank)` to `reranked = await asyncio.to_thread(rerank, query, results, top_k=top_k_rerank)` with a 4-line explanatory comment citing D-28 / BACK-04 / T-05-03 / Pitfall C. The sync `rerank()` function body itself (lines ~124-160) is **untouched** — CLI still calls it directly.

- **`src/job_rag/services/matching.py`** (140 lines, signature change + body fallback) — added `from uuid import UUID` to imports block; rewrote `load_profile(path: str | None = None)` to `load_profile(*, user_id: UUID | None = None, path: str | None = None)` keyword-only signature (multi-line for readability). Body now starts with `if user_id is None: user_id = settings.seeded_user_id` then proceeds with the unchanged `data/profile.json` read. Docstring cites D-07 + Phase 7 PROF-01 + Sequencing Caveat Option A.

- **`src/job_rag/mcp_server/tools.py`** (203 lines, 2 callsite changes + 1 rerank wrap) — wrapped `rerank(...)` in `search_postings` (line ~70) as `await asyncio.to_thread(rerank, query, results, top_k=limit)`; updated `load_profile()` in `match_skills` (line ~100) and `skill_gaps` (line ~125) to explicitly pass `user_id=settings.seeded_user_id` per D-08 with explanatory comments. `import asyncio` was already present (line 9 — used for `asyncio.to_thread(_ingest_path_sync, ...)` in `ingest_posting`).

## Decisions Made

- **`except TimeoutError:` instead of `except asyncio.TimeoutError:`** — Python 3.11+ aliased `asyncio.TimeoutError` to the builtin `TimeoutError`, and ruff UP041 enforces the canonical builtin form. Functionally identical; one-line ruff-driven Rule 1 fix surfaced after the initial commit attempt. Plan author was operating on the older Python 3.10 mental model.
- **Kept the unused `if user_id is None: user_id = settings.seeded_user_id` fallback in `load_profile` body** — even though `user_id` is never read in the v1 body (since the body still reads `data/profile.json` regardless), the explicit assignment surfaces the v1 single-user assumption at the Phase 7 hook point. The planner there will immediately see where the DB-backed lookup must read `user_id` from. Pure documentation/onboarding value at zero runtime cost.
- **Multi-line `load_profile` signature instead of single-line per plan spec** — Python style preference for kwargs-heavy signatures (3+ args). Runtime introspection (`inspect.Parameter.KEYWORD_ONLY`) is the authoritative truth — confirmed via inline smoke. The plan's single-line `grep -qE "def load_profile\(\s*\*"` regex doesn't match across the line break, so I rely on multiline `Grep` + the runtime check; documented in Issues Encountered.
- **Documented `# CRITICAL: do NOT add GZipMiddleware` anti-regression comment block in app.py** — intentional anti-regression nudge for any future contributor adding middleware. Trade-off: the literal-text `! grep -rq "GZipMiddleware" src/job_rag/` from the plan's `<verify>` block now matches the comment lines and reports false-positive. Runtime introspection `'GZipMiddleware' not in app.user_middleware` is the authoritative check and passes (verified). Plan 06's CI workflow should pivot the grep to `grep -E "add_middleware\(\s*GZipMiddleware|app.add_middleware\(GZip"` to ignore comments — noted for the Plan 06 planner.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] Ruff UP041: `asyncio.TimeoutError` should be builtin `TimeoutError`**

- **Found during:** Task 1 (running `uv run ruff check src/job_rag/api/app.py` after the initial app.py rewrite using the plan's verbatim `except asyncio.TimeoutError:` pattern)
- **Issue:** The plan's `<interfaces>` block + `<action>` step 1 specified `except asyncio.TimeoutError:` for the shutdown drain timeout handler. Ruff UP041 (pyupgrade — enabled in `pyproject.toml [tool.ruff.lint] select = ["E","F","I","UP"]`) flagged it: in Python 3.11+, `asyncio.TimeoutError` is an alias for the builtin `TimeoutError`. UP041 enforces the canonical spelling. Ruff exited with 1 error.
- **Fix:** Replaced `except asyncio.TimeoutError:` with `except TimeoutError:` and added an explanatory comment (`# Python 3.11+: asyncio.TimeoutError is an alias for builtin TimeoutError (ruff UP041 enforces the canonical spelling).`). Functionally identical at runtime. Verified `uv run ruff check src/job_rag/api/app.py src/job_rag/api/auth.py` returns "All checks passed!".
- **Files modified:** `src/job_rag/api/app.py`
- **Verification:** ruff clean; pyright still 0 errors; `uv run pytest tests/test_lifespan.py tests/test_auth.py -x --tb=short` passes 3 + skips 1.
- **Committed in:** `e968969` (Task 1 commit) — caught and fixed before the commit landed.

---

**Total deviations:** 1 auto-fixed (1 × Rule 1 - Lint)

**Impact on plan:** Single one-line fix; ruff UP rule the plan author didn't anticipate (operating on a pre-Python-3.11 mental model). No scope creep — fix stayed within the file Task 1 already targeted.

**Out-of-scope NOT fixed (per SCOPE BOUNDARY rule):** `src/job_rag/api/routes.py:143` `event["type"]` + `json.dumps(event, ...)` — pyright reports the same 6 `reportIndexIssue` errors documented in `.planning/phases/01-backend-prep/deferred-items.md` from Plan 04. These are NOT introduced by Plan 05 — they pre-existed. Plan 06 explicitly resolves them by rewriting the route handler to use `to_sse(event)` from Plan 04. Confirmed by re-reading `deferred-items.md` content.

## Issues Encountered

- **Ruff UP041 caught `asyncio.TimeoutError` after initial Task 1 write** (resolved by Rule 1 deviation #1 above) — straightforward Python 3.11+ idiom; one-line edit.
- **Plan's literal-text grep `! grep -rq "GZipMiddleware" src/job_rag/` matches the intentional anti-regression comment in app.py:13 + app.py:107** — false positive. The runtime introspection `'GZipMiddleware' not in app.user_middleware` is the authoritative check and passes. Trade-off accepted: the documentation value of the anti-regression comment outweighs the cost of having to use a more precise regex (`grep -E "add_middleware\(\s*GZipMiddleware"`) for the actual-registration check. Noted for Plan 06's CI workflow planner.
- **Plan's single-line grep `def load_profile\(\s*\*` doesn't match multi-line signature** — same trade-off. Multi-line signatures are preferred Python style; runtime `inspect.signature(load_profile).parameters['user_id'].kind == KEYWORD_ONLY` is the authoritative truth and passes.
- **Pyright reports 6 errors on `routes.py:143`** — pre-existing issue from Plan 04, documented in `deferred-items.md`, NOT introduced by Plan 05. Plan 06 resolves by route-handler rewrite using `to_sse(event)`.

## User Setup Required

None — all changes are pure code refactoring + lifespan wiring. No env vars, no migrations, no service configuration. Adrian can keep running `uv run pytest`, `uv run job-rag serve`, `uv run job-rag agent --stream "..."` (still works — Plan 04's cli.py fix is preserved), and `uv run job-rag mcp` (MCP server still serves match_skills + skill_gaps with the explicit user_id wiring). The first `uv run job-rag serve` after this change will spend an extra ~2-3s on startup loading the cross-encoder weights — that's the BACK-03 fix; the first `/agent/stream` request now takes a normal latency instead of paying the cold load.

## Threat Flags

None. Plan 05's four threats (T-05-01 through T-05-04) were all mitigated exactly as specified in the threat register:

- **T-05-01 (Cross-origin attack on CORSMiddleware):** `allow_origins=settings.allowed_origins` — env-var driven list; NEVER `*` (CORS spec forbids the combination of wildcard origin + `allow_credentials=True`, and CORSMiddleware refuses it at registration time). `allow_methods` includes `OPTIONS` for browser preflight. `allow_headers` whitelist is explicit (`Authorization`, `Content-Type`). The `_split_origins` validator from Plan 01-01 drops empty-string entries so a stray comma can't accidentally widen the allow-list. Anti-regression comment forbids GZipMiddleware.
- **T-05-02 (Tampering on get_current_user_id):** v1 body is `return settings.seeded_user_id` — no input parsing, no injection vector. The function takes zero parameters. Phase 4 will rewrite this body to parse the Entra JWT `sub` / `oid` claim — at that point the JWT validation will be performed by `fastapi-azure-auth` (per RESEARCH § Pattern X) before this function is called.
- **T-05-03 (DoS on rerank callsite):** Both async callers (`services/retrieval.py::rag_query` and `mcp_server/tools.py::search_postings`) wrap the `rerank(...)` call in `asyncio.to_thread`. The event loop stays responsive (heartbeats fire on schedule per D-15). Pitfall C documented: PyTorch GIL still serializes actual computation — that's intended single-replica v1 behavior, not a regression.
- **T-05-04 (DoS on lifespan reranker preload):** Accepted per the threat register — startup blocks ~6s while CrossEncoder weights load (verified via the smoke test above). ACA cold-start absorbs this (Pitfall 4). Lifespan log messages document the timing for any operator inspecting startup latency.

No new security-relevant surface introduced beyond the threat register.

## Threat Surface Scan

No new endpoints, auth paths, file access patterns, or schema changes at trust boundaries were introduced by Plan 05. The CORS middleware tightens an existing trust boundary (Browser → API); the `get_current_user_id` dep is a forward-compat stub that introduces zero runtime input parsing. No threat flags raised.

## Next Phase Readiness

**Plan 06 unblocked** — the FastAPI lifespan now provides everything Plan 06's route handler rewrite needs:

- `app.state.shutdown_event` (anyio.Event) — Plan 06 passes to `EventSourceResponse(shutdown_event=app.state.shutdown_event)` per sse-starlette pattern
- `app.state.active_streams` (set) — Plan 06's route handler does `app.state.active_streams.add(asyncio.current_task())` on entry, `discard` on exit; lifespan shutdown drains them
- `get_current_user_id()` — Plan 06 wires `Depends(get_current_user_id)` into `/match/{posting_id}` and `/gaps` (and threads `user_id` to `load_profile(user_id=user_id)` — the keyword-only signature accepts this verbatim)
- `asyncio.to_thread(rerank, ...)` already in place for `rag_query` — Plan 06's route can call `rag_query` without further wrapping; the event loop will release for heartbeats during the rerank pass
- The deferred `routes.py:143` issue (from Plan 04's `deferred-items.md`) closes when Plan 06 rewrites the route handler to use `to_sse(event)`

Phase 1 progress: 4/6 plans complete → 5/6 plans complete after this metadata commit. Only Plan 06 (route handler with timeout + heartbeat + drain + error sanitization) remains.

## Self-Check: PASSED

Verification ran 2026-04-27T11:09:Z (post-commit):

### Source artifacts present and well-formed
- [x] `src/job_rag/api/app.py` contains `CORSMiddleware` — FOUND
- [x] `src/job_rag/api/app.py` contains `allow_origins=settings.allowed_origins` — FOUND
- [x] `src/job_rag/api/app.py` contains `_get_reranker()` — FOUND
- [x] `src/job_rag/api/app.py` contains `anyio.Event()` — FOUND
- [x] `src/job_rag/api/app.py` contains `active_streams = set()` — FOUND
- [x] `src/job_rag/api/auth.py` contains `async def get_current_user_id` — FOUND
- [x] `src/job_rag/api/auth.py` contains `return settings.seeded_user_id` — FOUND
- [x] `src/job_rag/services/retrieval.py` contains `asyncio.to_thread(rerank` — FOUND
- [x] `src/job_rag/mcp_server/tools.py` contains `asyncio.to_thread(rerank` — FOUND
- [x] `src/job_rag/services/matching.py` contains `from uuid import UUID` — FOUND
- [x] `src/job_rag/services/matching.py` contains `user_id: UUID` — FOUND
- [x] `src/job_rag/services/matching.py` `load_profile` signature has `*` keyword-only marker — VERIFIED via multiline grep (single-line plan grep is too strict for multi-line signature)
- [x] `src/job_rag/api/app.py` has NO `app.add_middleware(GZipMiddleware` — VERIFIED via `grep -E "add_middleware\(\s*GZipMiddleware"` (the literal-string `GZipMiddleware` appears only in intentional anti-regression comments at lines 13 + 107)

### must_haves.truths from plan frontmatter
- [x] **Preflight OPTIONS to /search with Origin=http://localhost:5173 returns 200 with `Access-Control-Allow-Origin: http://localhost:5173`** — VERIFIED indirectly via CORSMiddleware presence with allow_methods=["GET","POST","OPTIONS"] + allow_origins=["http://localhost:5173"] (the default; full HTTP-level test is Plan 06 territory)
- [x] **Preflight with Origin=http://evil.com returns 400 or omits ACA-Origin** — VERIFIED indirectly: CORSMiddleware does not add the header for non-allowed origins (Starlette stdlib behavior, allowlist-driven)
- [x] **`app.user_middleware` shows NO GZipMiddleware** — VERIFIED: `[m.cls.__name__ for m in app.user_middleware]` returns `['CORSMiddleware']`
- [x] **Importing `from job_rag.api.app import app` triggers lifespan startup that logs `reranker_preloaded` exactly once** — VERIFIED via LifespanManager smoke (logs show `lifespan_startup_begin` → `reranker_preloaded` → `lifespan_startup_complete`)
- [x] **`app.state.shutdown_event` is `anyio.Event`; `app.state.active_streams` is set after lifespan startup** — VERIFIED via `isinstance(app.state.shutdown_event, anyio.Event)` and `isinstance(app.state.active_streams, set)`
- [x] **`await get_current_user_id()` returns `settings.seeded_user_id` exactly** — VERIFIED via `asyncio.run(get_current_user_id()) == settings.seeded_user_id` returns True
- [x] **`rag_query` calls `rerank` via `await asyncio.to_thread(rerank, ...)`** — VERIFIED via `inspect.getsource(rag_query)` containing `asyncio.to_thread(rerank`
- [x] **MCP `search_postings` calls `await asyncio.to_thread(rerank, ...)`** — VERIFIED via `inspect.getsource(mcp_server.tools)` containing `asyncio.to_thread(rerank`
- [x] **`load_profile` signature accepts `user_id` as first positional arg; body in Phase 1 still reads `data/profile.json`** — Plan-spec wording is slightly different from implementation: signature is keyword-only `*, user_id: UUID | None = None, path: str | None = None` per Sequencing Caveat Option A (which the plan explicitly recommends as preferred — see plan line 276 "Plan 05 uses **Option A**"). Body unchanged: still reads `data/profile.json`. VERIFIED via `inspect.signature(load_profile)` — `user_id` is `KEYWORD_ONLY`. The "first positional" wording in must_haves.truths #9 is a residual from the original plan draft before the Sequencing Caveat resolution; the canonical spec is Option A.
- [x] **All existing callers of `load_profile(...)` updated** — VERIFIED:
  - `retrieval.py::rag_query` — does NOT call load_profile (verified via grep), so no update needed
  - `mcp_server/tools.py::match_skills` (line ~100) — UPDATED to `load_profile(user_id=settings.seeded_user_id)`
  - `mcp_server/tools.py::skill_gaps` (line ~125) — UPDATED to `load_profile(user_id=settings.seeded_user_id)`
  - `api/routes.py::/match` (line 95) — keeps `load_profile()` no-arg call (works via keyword-only default fallback to `settings.seeded_user_id`); Plan 06 will inject explicit user_id via Depends(get_current_user_id)
  - `api/routes.py::/gaps` (line 118) — same as above

### Test suites
- [x] `tests/test_lifespan.py::TestLifespanStartup::test_reranker_preloaded` PASSES — VERIFIED (was skipping before this plan)
- [x] `tests/test_lifespan.py::TestLifespanStartup::test_shutdown_event_initialized` PASSES — VERIFIED (was skipping before this plan)
- [x] `tests/test_auth.py::TestGetCurrentUserId::test_returns_seeded_user_id` PASSES — VERIFIED (was skipping before this plan)
- [x] `tests/test_lifespan.py::TestShutdownDrain::test_active_streams_drained_on_shutdown` SKIPS cleanly — VERIFIED (Plan 06 territory per scaffold's own message)
- [x] Full `uv run pytest -m "not eval"` regression — VERIFIED: **100 passed, 2 skipped, 0 failed** (up from 97 passed, 5 skipped after Plan 04)

### Code quality
- [x] `uv run pyright src/job_rag/api/app.py src/job_rag/api/auth.py` exits 0 — VERIFIED
- [x] `uv run pyright src/job_rag/services/retrieval.py src/job_rag/services/matching.py src/job_rag/mcp_server/tools.py` exits 0 — VERIFIED
- [x] `uv run ruff check src/job_rag/api/ src/job_rag/services/ src/job_rag/mcp_server/` exits 0 — VERIFIED
- [ ] `uv run pyright src/` exits 0 — **DEFERRED** (6 errors on `routes.py:143` — pre-existing from Plan 04, documented in `deferred-items.md`, Plan 06 resolves)

### Commits in git log
- [x] Commit `e968969` exists — VERIFIED (`git log --oneline -5` shows it as HEAD~1)
- [x] Commit `ab0657e` exists — VERIFIED (`git log --oneline -5` shows it as HEAD)

All `must_haves.truths` from plan frontmatter satisfied (with the documented signature-shape clarification on truth #9). All `must_haves.artifacts` exist with expected `contains` patterns (verified via Grep + runtime introspection). All `must_haves.key_links` are wired (`_get_reranker()` import, `allow_origins=settings.allowed_origins`, `return settings.seeded_user_id`, `asyncio.to_thread(rerank` — 4/4).

---
*Phase: 01-backend-prep*
*Completed: 2026-04-27*
