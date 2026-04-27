# Phase 1 Deferred Items

Items discovered during plan execution that fall OUTSIDE the current plan's
scope. Each item lists the discovering plan, the file/line, and the plan that
should resolve it.

---

## src/job_rag/api/routes.py:143 — `event["type"]` + `json.dumps(event, ...)` against Pydantic AgentEvent instances

**Discovered by:** Plan 01-04 (this rewire — `stream_agent` now yields `AgentEvent` Pydantic instances)

**Status:** Pyright reports 6 `reportIndexIssue` errors (one per AgentEvent variant) at `src/job_rag/api/routes.py:143:26`. The runtime production code path (a real frontend hitting `/agent/stream`) would crash on `event["type"]` because Pydantic models don't define `__getitem__`. The existing test `tests/test_api.py::TestAgentEndpoint::test_agent_stream_emits_sse_events` currently still PASSES because it patches `stream_agent` with a fake generator that yields plain dicts — so the test doesn't catch this regression.

**Plan 01-04 explicitly defers this:** quoting Plan 04 Task 2 action #4: *"If the `tests/test_api.py::TestAgentStream` tests (existing, not in Plan 01 scope) fail because the route handler currently `json.dumps` the yielded dict — that's fine. Those tests will be updated by Plan 06 when the route handler is rewritten."*

**Resolution plan:** Plan 01-06 (route handler rewrite — adds `asyncio.wait_for` 60s timeout per D-25, sse-starlette `ping_message_factory` per D-15, shutdown drain per D-17, typed `error` event emission per D-19). At that point the route handler will:

```python
async for event in stream_agent(q):
    yield to_sse(event)  # uses the Plan 04 helper
```

`to_sse(event)` returns `{"event": event.type, "data": event.model_dump_json()}` — wire-shape byte-identical (modulo whitespace) to the current `json.dumps(event, default=str, ensure_ascii=False)` output.

**Plan 06 will also need to update** `tests/test_api.py::TestAgentEndpoint::test_agent_stream_emits_sse_events` so the fake `stream_agent` generator yields Pydantic `AgentEvent` instances (e.g., `TokenEvent(type="token", content="Hello")`) instead of dicts.

**Until Plan 06 lands:**
- `uv run pyright src/` exits 1 (6 errors on routes.py:143)
- `uv run pytest -m "not eval"` exits 0 (97 passed, 5 skipped — the test_api stream test still passes via the dict-yielding mock)
- The production `/agent/stream` endpoint would crash on the first yielded event (no real frontend exists yet — Phase 6)

**CI impact:** `.github/workflows/ci.yml` runs `uv run pyright src/` and would fail. Two acceptable mitigations until Plan 06:
1. Sequence Plan 06 to land in the same PR or before pushing to GitHub.
2. Add a `# pyright: ignore[reportIndexIssue]` comment on routes.py:143 as a temporary band-aid (NOT done in Plan 04 — it would mask the real fix Plan 06 must perform).

Plan 06 picks option 1.
