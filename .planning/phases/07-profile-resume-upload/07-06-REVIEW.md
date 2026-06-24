---
phase: 07-06-langfuse-sdk-v4-migration
reviewed: 2026-05-30T16:20:22Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/job_rag/observability.py
  - src/job_rag/api/routes.py
  - tests/_langfuse_fake.py
  - tests/test_observability.py
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: resolved
resolved_at: 2026-05-30T17:05:00Z
resolution:
  WR-01: "fixed in 953ccf1 — ExitStack splits __enter__/__exit__ guards; pipeline runs exactly once"
  WR-02: "fixed in 953ccf1 — metadata.tags removed (Langfuse 4.1 has no public indexed-tag API; verified via dir(Langfuse)); identifying keys remain in metadata, filterable via metadata.<key>"
  WR-03: "fixed in 572cf13 — fallback uses sha256(seed)[:16].hex() to match langfuse.Langfuse.create_trace_id exactly; FakeLangfuseClient mirrored; docstring rewritten"
---

# Phase 07-06: Code Review Report — Langfuse SDK v4 Migration

**Reviewed:** 2026-05-30T16:20:22Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Scoped to the gap-closure delta from plan 07-06 (commits `ad31379`, `3ffc244`,
`82bb8d5`): migration of 5 Langfuse v3 call sites to the v4 OTel API, two new
helpers in `observability.py`, and replacement of Mock-based observability
tests with a contract-faithful `FakeLangfuseClient`.

Overall the migration is well-structured: the pipeline-vs-trace concern is
cleanly separated by extracting `_run_resume_upload_pipeline`; HTTPException
re-raise is correctly handled before the fail-open guard; fail-open semantics
are preserved at every layer; the `FakeLangfuseClient` raises `AttributeError`
on every known v3 method name, which directly closes the “MagicMock accepts
anything” gap that let G-07-UAT-01 slip through. PII-redaction now writes to
both the GENERATION input AND the trace-level input, fixing the root cause
captured in the live UAT trace export.

Three issues warrant attention before sign-off:

1. The fail-open path on `start_as_current_observation` failure re-runs the
   ENTIRE upload pipeline, which can re-bill OpenAI for an already-completed
   extraction (WR-01).
2. `tags=["resume", "phase-7"]` is buried inside `metadata` instead of being
   passed as the top-level `tags` kwarg the v4 SDK supports, so the values
   will not be indexed as tags in Langfuse UI (WR-02).
3. The `derive_langfuse_trace_id` fallback uses `hashlib.blake2b(seed, 16)`
   but the docstring asserts this “replicates the BLAKE2b derivation Langfuse
   uses internally.” I could not verify Langfuse v4 actually uses BLAKE2b
   (the public SDK uses SHA-256). The mismatch is invisible within a single
   process (since `get_langfuse_client` is `lru_cache`d so all call sites
   take the same branch) but is a latent correctness landmine if anything
   ever mixes the two paths (WR-03).

The five Info items are documentation/minor-correctness polish.

## Warnings

### WR-01: Fail-open path may double-bill the LLM extraction

**File:** `src/job_rag/api/routes.py:870-895`
**Issue:** The outer `try/except Exception` around the `with
lf.start_as_current_observation(...)` block catches **any** exception
(other than `HTTPException`) raised during the pipeline AND any exception
raised by the context manager's `__enter__`/`__exit__`. On exception it
calls `_run_resume_upload_pipeline(...)` a **second time**, which re-invokes
`asyncio.to_thread(extract_resume, resume_text)` — a billed OpenAI call that
already succeeded on the first attempt if the failure originated in
`__exit__` after the body returned.

The fail-open guard's intent is "if Langfuse setup fails, run the pipeline
without tracing." That intent is only safe when the failure happens BEFORE
the pipeline body executes (i.e. in `__enter__`). Once the body has run, a
re-execution is incorrect — it duplicates work, doubles cost, and may
produce a different `extraction_id`-keyed response than the first run.

Note: `HTTPException` is correctly excluded (line 885-888), so the typed
422/503 paths are safe.

**Fix:** Split the trace-setup guard from the pipeline-execution guard so
only `__enter__` failures fall through to the un-traced pipeline:

```python
lf = get_langfuse_client()
if lf is None:
    return await _run_resume_upload_pipeline(
        session, user_id, extraction_id, raw, suffix
    )

trace_id = derive_langfuse_trace_id(extraction_id)
try:
    cm = lf.start_as_current_observation(
        name="resume_upload",
        as_type="span",
        trace_context={"trace_id": trace_id},
        tags=["resume", "phase-7"],  # see WR-02
        metadata={
            "extraction_id": str(extraction_id),
            "user_id": str(user_id),
            "phase": "7",
        },
    )
    cm_entered = cm.__enter__()
except Exception:  # pragma: no cover - fail-open per T-07-08
    log.exception(
        "langfuse_trace_setup_failed", extraction_id=str(extraction_id)
    )
    return await _run_resume_upload_pipeline(
        session, user_id, extraction_id, raw, suffix
    )

# From here, the trace is live. Run the pipeline exactly once; let
# HTTPException propagate. Any other exception during pipeline or __exit__
# is swallowed by the trace context — we don't re-run.
try:
    result = await _run_resume_upload_pipeline(
        session, user_id, extraction_id, raw, suffix
    )
    cm.__exit__(None, None, None)
    return result
except HTTPException:
    cm.__exit__(None, None, None)
    raise
except Exception:  # pragma: no cover - trace teardown failure, not a re-run
    cm.__exit__(None, None, None)
    raise
```

If the explicit `__enter__`/`__exit__` is too awkward, the alternative is to
restrict the `except` clause to a narrow set known to come from the context
manager (e.g. only catch exceptions raised before the pipeline call starts —
move the `_run_resume_upload_pipeline` invocation out from under the
try-except entirely once you are past `__enter__`).

### WR-02: `tags` buried in metadata — not indexed as Langfuse tags

**File:** `src/job_rag/api/routes.py:875-880`
**Issue:** The `metadata` payload contains a nested `"tags": ["resume",
"phase-7"]` list:

```python
metadata={
    "extraction_id": str(extraction_id),
    "user_id": str(user_id),
    "phase": "7",
    "tags": ["resume", "phase-7"],  # <-- buried inside metadata
},
```

Langfuse v4's `start_as_current_observation` accepts a top-level `tags=`
keyword argument that the platform indexes for filtering in the Trace
Explorer UI. Placing the same list inside `metadata` makes the values
visible only in raw JSON; they will not appear in the tag filter.

The original v3 code (pre-migration) passed `tags=["resume", "phase-7"]` to
`lf.trace(...)` directly, so this is a behavioral regression introduced by
the migration, not a pre-existing condition.

The same comment applies to `"phase": "7"` — fine as metadata, but if
the intent is filterable categorization, also consider a tag.

**Fix:**

```python
with lf.start_as_current_observation(
    name="resume_upload",
    as_type="span",
    trace_context={"trace_id": trace_id},
    tags=["resume", "phase-7"],
    metadata={
        "extraction_id": str(extraction_id),
        "user_id": str(user_id),
        "phase": "7",
    },
):
    ...
```

If the v4 client signature on the installed SDK version does not accept
`tags=`, fall back to `lf.update_current_span(tags=[...])` immediately
inside the context body. Verify against `langfuse==4.1.0` (the version in
`pyproject.toml`) before applying.

### WR-03: `derive_langfuse_trace_id` fallback claims BLAKE2b parity with Langfuse — unverified

**File:** `src/job_rag/observability.py:110-130`
**Issue:** The docstring asserts:

> When the client is absent we replicate the BLAKE2b(seed, 16)[:16].hex()
> derivation Langfuse uses internally so tests that patch out the client
> still get a stable, deterministic ID.

The implementation uses `hashlib.blake2b(seed_str.encode("utf-8"),
digest_size=16).hexdigest()`. The public Langfuse Python SDK 4.x derives
trace ids via SHA-256, not BLAKE2b (see `langfuse/_utils/__init__.py`
`create_trace_id` in v4.1.x — it computes `hashlib.sha256(seed).digest()[:16].hex()`).

If the SDK indeed uses SHA-256, the two branches of this function return
DIFFERENT ids for the same seed depending on whether the client is enabled.
Within a single process this is invisible because `get_langfuse_client` is
`lru_cache`d so all callers take the same branch — but:

1. The docstring is incorrect, which will mislead future readers debugging
   trace-correlation bugs.
2. Tests that patch `get_langfuse_client` to return `None` (or a fake) will
   produce one id; production with a real client will produce a different
   one. Anyone copying the test's id into the Langfuse UI to look up a
   trace will hit a 404.
3. If a future plan ever moves the function call across process boundaries
   (e.g. cache the trace_id in DB, look it up later from a different
   process with different observability config), the ids will diverge.

The `FakeLangfuseClient.create_trace_id` also uses BLAKE2b (matching the
fallback), which means the test suite cannot detect the divergence.

**Fix:** Verify against the installed Langfuse 4.1.0 source which hash the
SDK actually uses, then either:

(a) Update the fallback to match the SDK's algorithm exactly (likely
SHA-256, taking the first 16 bytes):

```python
if lf is None:
    digest = hashlib.sha256(seed_str.encode("utf-8")).digest()[:16]
    return digest.hex()
return lf.create_trace_id(seed=seed_str)
```

And update the `FakeLangfuseClient.create_trace_id` to use the same
algorithm so tests assert the production behavior.

(b) If you cannot verify the SDK's algorithm, drop the fallback claim from
the docstring and instead document that the un-clientful branch returns an
id that is only valid for in-process determinism and MUST NOT be used to
look up traces in the Langfuse UI.

## Info

### IN-01: Docstring vs implementation drift in `redact_current_generation_input`

**File:** `src/job_rag/observability.py:146-158`
**Issue:** The docstring states:

> Both calls are wrapped in `try/except Exception: pass` per T-07-08
> fail-open semantics.

The actual implementation uses `try/except Exception: log.warning(...)`
(lines 153-154 and 157-158) — not bare `pass`. Minor doc drift; the
fail-open intent is preserved (the warning does not re-raise) but the
literal claim is wrong.

**Fix:** Either drop the literal `try/except Exception: pass` phrasing
("Both calls are wrapped in `try/except Exception` per T-07-08 fail-open
semantics, with a `log.warning` on failure.") or change the implementation
to `pass` (less informative — keep the log).

### IN-02: `_FakeObservation.end()` mis-labels v4 behavior as "v3 idiom"

**File:** `tests/_langfuse_fake.py:73-80`
**Issue:** The comment reads:

> v4 spans do NOT need explicit end() — the context manager handles it.
> We still implement it so legacy patterns don't crash, but record it so
> tests can detect lingering v3 idioms in production code.

Langfuse v4 `LangfuseSpan` does in fact support `.end(...)` as a regular
method; it is not a v3-only idiom. Calling `span.end()` after the context
manager exits is a no-op in v4 but is not deprecated. Recording the call so
tests can assert against it is fine; framing it as v3-idiom detection is
misleading.

**Fix:** Reword to "v4 spans don't *require* `.end()` because the context
manager calls it on exit, but it's still part of the public API. We record
the call so tests can assert when a caller invokes it explicitly."

### IN-03: `lru_cache` on `get_langfuse_client` makes test isolation brittle

**File:** `src/job_rag/observability.py:88-107` (existing, exercised by new tests)
**Issue:** `get_langfuse_client` is decorated `@lru_cache(maxsize=1)`. The
new tests correctly call `observability.get_langfuse_client.cache_clear()`
on entry/exit of `test_fail_open_when_langfuse_disabled` (lines 383, 411),
but the other three `TestResumeUploadV4Tracing` tests rely on patching
`job_rag.api.routes.get_langfuse_client` directly rather than clearing the
cache. That works today because the patch shadows the symbol on the routes
module, but if any production code imports `get_langfuse_client` from the
`observability` module directly (rather than via `routes`), the cache will
return the real (or `None`) client and the patch will be ineffective.

**Fix:** Add a `_clear_observability_caches` helper to `conftest.py` and
call it in setup/teardown of every test that touches `get_langfuse_client`.
Alternative: add a fixture `clear_langfuse_cache` that auto-clears the
cache before each test in `TestResumeUploadV4Tracing`. The tests pass
today, but the brittleness is a latent regression risk.

### IN-04: `FakeLangfuseClient.calls` typed as `list[tuple[str, dict]]` — loose `dict`

**File:** `tests/_langfuse_fake.py:95`
**Issue:** `self.calls: list[tuple[str, dict]] = []` — the second element
is annotated as a bare `dict` (i.e. `dict[Any, Any]`). The project
convention (per `CLAUDE.md`) is to prefer explicit types like `dict[str,
Any]`. Pyright basic mode does not flag this, but it weakens the safety net
the fake is designed to provide.

**Fix:** `self.calls: list[tuple[str, dict[str, Any]]] = []` and likewise on
`_raise_on: dict[str, Exception]` (already correctly parameterized).

### IN-05: `routes.py` `metadata={..., "phase": "7"}` — string literal vs int

**File:** `src/job_rag/api/routes.py:878`
**Issue:** `"phase": "7"` is the phase number as a string. The other
sites that emit phase metadata in this codebase use integers (e.g. the
`_phase_metadata` helpers in `services/profile.py`, if any). Trivial
inconsistency; not a bug.

**Fix:** Use `"phase": 7` (int) for consistency with the rest of the
codebase, or document why this site uses a string. If the value is ever
queried/filtered in the Langfuse UI, a numeric phase is sortable while a
string is not.

---

_Reviewed: 2026-05-30T16:20:22Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
