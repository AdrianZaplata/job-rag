---
phase: 06-chat
plan: 02
subsystem: backend
tags: [chat, backend, openapi, contract-change, post, agent-stream, snapshot-regen]
dependency_graph:
  requires:
    - "Phase 1 Plan 04 (api/sse.py — AgentEvent discriminated union, to_sse helper, ErrorEvent reasons)"
    - "Phase 1 Plan 05 (lifespan + active_streams + shutdown_event)"
    - "Phase 1 Plan 06 (original GET /agent/stream handler with responses=, asyncio.timeout, ping_message_factory, defensive headers)"
    - "Phase 6 Plan 01 (DebugAgentStream {query} body pre-aligned)"
  provides:
    - "POST /agent/stream endpoint accepting AgentQuery body (Pydantic-validated)"
    - "openapi.snapshot.json describing POST /agent/stream + AgentQuery component schema"
    - "frontend/src/api/types.ts with operations[agent_stream_agent_stream_post].requestBody AgentQuery shape"
  affects:
    - "Plan 06-03 (streamAgent helper consumes the POST contract; types.ts feeds the codegen-typed body)"
    - "Plan 06-04 (Chat surface end-to-end POST flow)"
    - "DebugAgentStream.tsx (Plan 06-01 Task 3 already body-key-aligned; works against POST without further changes)"
tech-stack:
  added: []  # No new dependencies — pure contract change on existing FastAPI + Pydantic stack
  patterns:
    - "3-line surgical decorator/signature/body diff (verbatim with no other handler internals touched — exactly 6 git diff lines in routes.py)"
    - "AgentQuery sibling-reuse: same Pydantic body model already in use by POST /agent (line 340), now also POST /agent/stream"
    - "In-process app.openapi() snapshot capture (Plan 04-01 + Plan 05-03 D-04 pattern) — no uvicorn boot, no port binding"
    - "json.dumps(indent=2) WITHOUT sort_keys=True to match Phase 5's committed snapshot format and minimize spurious key-order diff"
    - "Test call-site swap (GET+params -> POST+json) preserving all downstream assertions (response.text body parse, status_code checks, heartbeat/timeout/shutdown drain) unchanged"
key-files:
  modified:
    - src/job_rag/api/routes.py
    - tests/test_api.py
    - frontend/openapi.snapshot.json
    - frontend/src/api/types.ts
  created: []  # No new files this plan
  unchanged:
    - tests/test_sse_contract.py  # verified method-agnostic; zero edits needed
decisions:
  - "Single-line client.post collapse over multi-line: line 186 of test_api.py fits in 89 chars (under ruff's 100-char limit), so the natural single-line form matches the project convention (line 158 sibling /agent POST single-line) AND makes the success-criterion grep `client.post(\"/agent/stream\"` match cleanly without regex acrobatics. Pattern: prefer single-line over multi-line for any client.X(...) call that fits the line-length budget."
  - "json.dumps WITHOUT sort_keys=True: Phase 5 Plan 05-03 (commit 5cd6d7e) committed the canonical snapshot format using `json.dumps(app.openapi(), indent=2) + '\\n'` (no sort_keys). Plan 06-02 deliberately matched this format despite the PLAN.md spec listing `sort_keys=True` — switching to sorted keys would have created a 1885-line whole-file reformat diff (vs. the actual 145-line semantic diff). Preserving Phase 5's format keeps the diff focused on the actual contract change."
  - "Combined RED+GREEN in a single Task 1 commit: the test mutations and routes.py method-flip are tightly coupled by the contract change — splitting them across two commits would leave master in a broken state mid-cycle. Per TDD execution flow note, when test changes are part of the contract (not standalone failing-test artifacts), a single commit is correct. Verified RED phase locally (got 405 against old GET) before applying the GREEN routes.py mutation."
metrics:
  duration: "~7 minutes (executor wall-clock; 4 files modified across 3 commits)"
  completed_date: "2026-05-23"
  tasks: 2
  files_changed: 4
  commits: 3  # Task 1 feat + Task 2 feat + style cleanup
requirements: [CHAT-01]
---

# Phase 6 Plan 2: Backend GET → POST /agent/stream Method Flip Summary

**One-liner:** 3-line surgical backend contract change flipping `/agent/stream` from `GET ?q=...` to `POST {query: string}` body using the existing `AgentQuery` Pydantic model, paired with 2 test call-site updates, snapshot regen, and types.ts codegen — all co-landed in a single plan to close Pitfall G (snapshot drift between backend method-flip and frontend codegen).

## Tasks Executed (2/2)

### Task 1: Backend method flip + test call-site update — commits `7208a01` + `d166450`

**`src/job_rag/api/routes.py` (3-line surgical diff, exactly as planned):**

```diff
@@ -361,7 +361,7 @@ except Exception:  # pragma: no cover - defensive fallback
     _AGENT_EVENT_JSON_SCHEMA = {}


-@router.get(
+@router.post(
     "/agent/stream",
     dependencies=[Depends(require_api_key), Depends(agent_limit)],
     responses={
@@ -380,7 +380,7 @@ except Exception:  # pragma: no cover - defensive fallback
         }
     },
 )
-async def agent_stream(request: Request, q: str) -> EventSourceResponse:
+async def agent_stream(request: Request, payload: AgentQuery) -> EventSourceResponse:
     """Stream agent execution as SSE: typed events + heartbeat + 60s timeout + drain.

     The handler wraps the Plan 04 ``stream_agent`` async iterator in
@@ -414,7 +414,7 @@ async def agent_stream(request: Request, q: str) -> EventSourceResponse:
         try:
             try:
                 async with asyncio.timeout(settings.agent_timeout_seconds):
-                    async for event in stream_agent(q):
+                    async for event in stream_agent(payload.query):
                         yield to_sse(event)
             except TimeoutError:
                 # Python 3.11+: asyncio.TimeoutError aliased to builtin TimeoutError
```

Diff stat: exactly **3 lines changed** (3 removed + 3 added = 6 diff lines).

**Preserved verbatim (NOT touched by this plan):**
- `responses={200: {"content": {"text/event-stream": {"schema": _AGENT_EVENT_JSON_SCHEMA}}}}` block
- `typed_event_generator` inner function
- `current_task = asyncio.current_task() / app.state.active_streams.add()`
- `asyncio.timeout(settings.agent_timeout_seconds)` wrap
- All 3 exception branches: `TimeoutError`, `asyncio.CancelledError`, generic `Exception` (all 3 emit typed `ErrorEvent` via `_sanitize` per D-19 / T-06-01)
- `finally: app.state.active_streams.discard(current_task)`
- `EventSourceResponse(..., ping=settings.heartbeat_interval_seconds, ping_message_factory=_heartbeat_factory, shutdown_event=app.state.shutdown_event, shutdown_grace_period=30.0)`
- `headers={"X-Accel-Buffering": "no", "Content-Encoding": "identity"}` (D-18 / Pitfall 6)
- All docstrings and comments

**`tests/test_api.py` (2 call sites swapped + 1 style cleanup):**

```diff
@@ TestAgentEndpoint.test_agent_stream_emits_sse_events (line 186) @@
-                    response = await client.get("/agent/stream", params={"q": "test"})
+                    response = await client.post("/agent/stream", json={"query": "test"})

@@ TestAgentStream._stream_bytes (line 366) @@
                 async with client.stream(
-                    "GET", "/agent/stream?q=test"
+                    "POST", "/agent/stream", json={"query": "test"}
                 ) as resp:
```

The `_stream_bytes` helper is used by 5 downstream tests (heartbeat, timeout, shutdown drain, sanitized error frame, etc.) — all 5 ride through the swap unchanged since they assert on response body shape (SSE frame bytes), not transport method.

**`tests/test_sse_contract.py`:** verified method-agnostic via grep — zero edits needed. The `TestOpenAPISchema.test_openapi_includes_agent_event` test inspects `app.openapi()['components']['schemas']` and is independent of the HTTP method on the route. (Bonus: this test now ACTIVATES — the prior Wave 0 skip-guard tripped because Plan 06's `responses=` annotation hadn't shipped yet; now that it has, the test runs live and asserts the 6 `*Event` schemas appear.)

### Task 2: Snapshot regen + types.ts codegen — commit `14bf177`

**`frontend/openapi.snapshot.json`** regenerated via in-process Python capture:

```bash
uv run python -c "
import json; from pathlib import Path
from job_rag.api.app import app
Path('frontend/openapi.snapshot.json').write_text(
    json.dumps(app.openapi(), indent=2) + '\n'
)
"
```

Pre/post key list at `paths['/agent/stream']`:

| Before (committed)        | After (regenerated)        |
| ------------------------- | -------------------------- |
| `['get']`                 | `['post']`                 |
| `parameters: [{ name: 'q', in: 'query', required: true }]` | `requestBody: { $ref: '#/components/schemas/AgentQuery' }` |
| `operationId: agent_stream_agent_stream_get` | `operationId: agent_stream_agent_stream_post` |

`components.schemas.AgentQuery` already existed (referenced by the sibling POST `/agent` endpoint since Phase 1 Plan 06 / commit 0e4b596). No new schemas added; the `/agent/stream` POST now references the existing `AgentQuery` shape.

**`frontend/src/api/types.ts`** codegen via `npm run codegen:snapshot`:

```diff
-    agent_stream_agent_stream_get: {
+    agent_stream_agent_stream_post: {
         parameters: {
-            query: {
-                q: string;
-            };
+            query?: never;
             header?: never;
             path?: never;
             cookie?: never;
         };
-        requestBody?: never;
+        requestBody: {
+            content: {
+                "application/json": components["schemas"]["AgentQuery"];
+            };
+        };
```

Path-level:
- `paths["/agent/stream"].get` removed (compiles to `get?: never`)
- `paths["/agent/stream"].post: operations["agent_stream_agent_stream_post"]`

Total `types.ts` diff: 18 lines changed (compact; only the `/agent/stream` path and its `operations` entry differ).

## Verification Evidence

### Per-task automated verifies

**Task 1:**
- `git diff src/job_rag/api/routes.py | grep '^[-+]' | grep -vE '^(---|\+\+\+)' | wc -l` → **6** (exactly 3 removed + 3 added)
- `grep -c '@router.post(' src/job_rag/api/routes.py` → **3** (was 2; +1 from `/agent/stream`)
- `grep -c '@router.get(' src/job_rag/api/routes.py` → **7** (was 8; -1 from `/agent/stream`)
- `grep -c '"/agent/stream"' src/job_rag/api/routes.py` → **1** (only one decorator, only one method)
- `grep -c 'payload: AgentQuery' src/job_rag/api/routes.py` → **2** (both `/agent` and `/agent/stream` use the same Pydantic body)
- `grep -c 'stream_agent(payload.query)' src/job_rag/api/routes.py` → **1**
- `grep -c 'stream_agent(q)' src/job_rag/api/routes.py` → **0** (old reference gone)
- `grep -c 'X-Accel-Buffering' src/job_rag/api/routes.py` → **3** (defensive header preserved across 3 comment + code occurrences)
- `grep -c 'Content-Encoding' src/job_rag/api/routes.py` → **3** (defensive header preserved)
- `grep -c 'client.get("/agent/stream"' tests/test_api.py` → **0** (✓)
- `grep -c '"GET", "/agent/stream' tests/test_api.py` → **0** (✓)
- `grep -c 'client.post("/agent/stream"' tests/test_api.py` → **1** (✓ — after style cleanup, single-line form)
- `grep -c '"POST", "/agent/stream"' tests/test_api.py` → **1** (✓)
- `uv run pytest tests/test_api.py::TestAgentEndpoint tests/test_api.py::TestAgentStream tests/test_sse_contract.py -x` → **16 passed**
- `uv run pytest --ignore=tests/test_alembic.py` → **233 passed, 8 skipped** (Wave 0 stubs)

**Task 2:**
- `python3 -c "import json; spec=json.load(open('frontend/openapi.snapshot.json')); print(list(spec['paths']['/agent/stream'].keys()))"` → **`['post']`** (no `'get'`)
- `python3 -c "...; print('AgentQuery' in spec['components']['schemas'])"` → **True**
- `grep -c 'AgentQuery' frontend/src/api/types.ts` → **4** (codegen wired the body schema in 4 locations: path operations entry, requestBody content type, components alias, operationId metadata)
- `cd frontend && npm run typecheck` → **exit 0**
- `cd frontend && npm run lint` → **exit 0**
- `cd frontend && npm test -- --run` → **17 test files passed, 55 tests passed** (Plan 01 skip-guarded scaffolds for `useChatStream`/`ToolChip`/`ChatComposer`/`ChatTranscript` stay skip-clean — target chat-feature modules ship in Plans 03/04)
- `cd frontend && npm run build` → **built in 185ms, no errors**
- `cd frontend && cp src/api/types.ts /tmp/check.ts && npm run codegen:snapshot && diff -q /tmp/check.ts src/api/types.ts` → **types.ts IDEMPOTENT** (no diff)
- Back-to-back `app.openapi()` capture → **snapshot IDEMPOTENT** (no diff)

### Full verification trifecta (final state)

```
Backend gate:
- uv run ruff check src/ tests/ ............... All checks passed!
- uv run pyright src/ ......................... 0 errors, 0 warnings, 0 informations
- uv run pytest tests/test_api.py tests/test_sse_contract.py -x ........... 34 passed

Frontend gate:
- npm run typecheck ........................... exit 0
- npm run lint ................................ exit 0
- npm test -- --run ........................... 17 files, 55 tests passed
- npm run build ............................... built in 185ms

CI drift simulation:
- Back-to-back snapshot capture ............... byte-identical
- Back-to-back codegen ........................ byte-identical
```

## Pitfall G Closure (Snapshot Drift Mitigation)

**Pitfall G** (RESEARCH §"Pitfall G"): Backend method change + snapshot regen + types.ts codegen MUST co-land in a single PR — otherwise the CI drift-check job (Phase 4 D-14) would catch the mismatch mid-merge and fail.

**Closure:** Plan 06-02 atomically lands all three artifacts:
- Task 1 commit `7208a01` ships the backend method flip
- Task 2 commit `14bf177` ships snapshot regen + types.ts codegen in lockstep
- Style cleanup commit `d166450` is a no-op for contract/snapshot/types — pure single-line consolidation in tests

CI drift-check simulation locally: `npm run codegen:snapshot && git diff --exit-code` → **exit 0** (the committed snapshot and types.ts are in equilibrium with the live `app.openapi()`).

## Pitfall E Preservation (Defensive Headers)

**Pitfall E** (RESEARCH §"Pitfall E"): The defensive headers `X-Accel-Buffering: no` + `Content-Encoding: identity` must be preserved verbatim through any handler modification, otherwise reverse-proxy buffering or accidental gzip compression breaks EventSource parsing on the frontend.

**Preserved:**
- `grep -c "X-Accel-Buffering" src/job_rag/api/routes.py` → **3** (1 code occurrence + 2 comment refs at lines 402-403, 467, 471)
- `grep -c "Content-Encoding" src/job_rag/api/routes.py` → **3** (1 code occurrence + 2 comment refs at lines 402-403, 467, 472)

The `EventSourceResponse(...)` construction at line 458 retains the exact `headers={"X-Accel-Buffering": "no", "Content-Encoding": "identity"}` block. No middleware was added or removed; the Phase 1 D-18 / Pitfall 6 invariant holds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Single-line `client.post` collapse**
- **Found during:** Task 1 verification — success-criterion grep `client.post("/agent/stream"` returned 0 against the initial multi-line form
- **Issue:** The plan's `<action>` block specified a multi-line client.post form (3 lines: `client.post(`, `"/agent/stream", json={"query": "test"}`, `)`). The success criterion `grep -c 'client.post("/agent/stream"'` doesn't match across line breaks, so the multi-line form would fail the verification gate.
- **Fix:** Collapsed to a single line (89 chars, well under ruff's 100-char budget). Matches the sibling convention at line 158 (`client.post("/agent", json={"query": "test"})`).
- **Files modified:** `tests/test_api.py` (line 186)
- **Commit:** `d166450` (separate style commit, kept distinct from the contract-change commit for clarity)
- **Why Rule 1 not Rule 4:** Pure stylistic correction to satisfy the literal grep gate; preserves test semantics exactly. The plan author had specified the multi-line form likely to be defensive about line length, but the actual line fits the budget.

### Sibling test references discovered beyond the 3 named call sites

**None.** Grep enumeration for `client\.get\("/agent/stream"\|client\.stream\("GET", "/agent/stream` against the entire test directory returned exactly the 2 call sites named in the plan (line 186 + line 366). `test_sse_contract.py` is method-agnostic as predicted (only docstring/comment references; no client calls).

### Pre-existing out-of-scope issues observed

- `tests/test_alembic.py::test_0004_upgrade_smoke` fails with `KeyError: 'DATABASE_URL'` regardless of this plan's changes (verified by stashing the diff and re-running). Confirmed pre-existing; needs `DATABASE_URL` env var set against a live PostgreSQL. **Out of scope** per SCOPE BOUNDARY rule — not caused by this task's changes.
- `.planning/phases/04.1-phase-4-follow-ups-runbook-deviation-cleanup/04.1-VERIFICATION.md` shows pending modifications in the working tree from a prior session. Not part of this plan's scope; deliberately excluded from all 3 commits in this plan.

### Auth gates

None — fully automated. The `/agent/stream` route's existing `dependencies=[Depends(require_api_key), Depends(agent_limit)]` chain is preserved verbatim (D-05); the POST flip does NOT change authentication or rate-limiting surface (T-06-02-02 / T-06-02-06).

## Threat Flags

None — the POST migration does not introduce any new trust boundary, network endpoint, auth path, file access pattern, or schema change at a trust boundary. The endpoint surface is unchanged (`/agent/stream` was already exposed); only the HTTP verb + body shape flip. Per the threat model:

- **T-06-02-01 (snapshot drift):** Closed (Pitfall G closure above)
- **T-06-02-02 (CSRF):** Inherited mitigation from Phase 4 — Bearer JWT in `Authorization` header is CSRF-immune
- **T-06-02-04 (stack trace leak):** Inherited mitigation from Phase 1 — `_sanitize(exc)` preserved on all 3 exception branches
- **T-06-02-07 (heartbeat/timeout regression):** Mitigated — all 3 mechanisms verified live via `TestAgentStream` (heartbeat, timeout, shutdown drain all pass)

## Known Stubs

None — this plan ships production-ready backend contract + verified codegen artifacts. The Plan 01 scaffold tests (`useChatStream`, `ToolChip`, `ChatComposer`, `ChatTranscript`) remain skip-clean as intended; they will activate when Plans 03/04 land their target modules.

## Self-Check: PASSED

### Modified files exist and contain expected changes

```
FOUND: src/job_rag/api/routes.py — 3 lines mutated (@router.post + payload: AgentQuery + stream_agent(payload.query))
FOUND: tests/test_api.py — 2 call sites swapped (line 186 POST + json={"query":...}, line 366 stream POST + json)
FOUND: frontend/openapi.snapshot.json — paths['/agent/stream'] = ['post'], AgentQuery $ref wired
FOUND: frontend/src/api/types.ts — agent_stream_agent_stream_post with requestBody AgentQuery
UNCHANGED: tests/test_sse_contract.py — method-agnostic, no edits needed
```

### Commits exist in git history

```
FOUND: 7208a01 feat(06-02): flip /agent/stream from GET ?q= to POST {query} body
FOUND: 14bf177 feat(06-02): regenerate openapi.snapshot.json + types.ts for POST /agent/stream
FOUND: d166450 style(06-02): collapse multi-line client.post call to single line
```

### Defensive verification artifacts preserved

```
X-Accel-Buffering: 3 occurrences in routes.py (1 code + 2 comments)
Content-Encoding: identity: 3 occurrences in routes.py (1 code + 2 comments)
asyncio.timeout(settings.agent_timeout_seconds): 1 occurrence (timeout wrap intact)
ping_message_factory=_heartbeat_factory: 1 occurrence (typed heartbeat preserved)
shutdown_event=app.state.shutdown_event: 1 occurrence (drain wiring preserved)
```

## Next Plan

**06-03** (frontend `streamAgent` helper + `useChatStream` hook):
- Build `frontend/src/api/streamAgent.ts` — wraps `fetch()` POST + `readSSEStream` against `/agent/stream`
- Build `frontend/src/components/chat/useChatStream.ts` — reducer-driven state machine consuming `streamAgent`
- Plan 01's skip-guarded `useChatStream.test.tsx` auto-activates when the target module + symbol resolve
- This plan's snapshot + types.ts work means `components['schemas']['AgentQuery']` is importable as the typed request body in `streamAgent.ts`

## Self-Check: PASSED

### Created/modified files exist

```
FOUND: src/job_rag/api/routes.py — 3 lines mutated
FOUND: tests/test_api.py — 2 call sites swapped + 1 style cleanup
FOUND: frontend/openapi.snapshot.json — paths['/agent/stream'] = ['post']
FOUND: frontend/src/api/types.ts — agent_stream_agent_stream_post with AgentQuery body
FOUND: .planning/phases/06-chat/06-02-SUMMARY.md (this file)
```

### Commits exist in git history

```
FOUND: 7208a01 feat(06-02): flip /agent/stream from GET ?q= to POST {query} body
FOUND: 14bf177 feat(06-02): regenerate openapi.snapshot.json + types.ts for POST /agent/stream
FOUND: d166450 style(06-02): collapse multi-line client.post call to single line
```
