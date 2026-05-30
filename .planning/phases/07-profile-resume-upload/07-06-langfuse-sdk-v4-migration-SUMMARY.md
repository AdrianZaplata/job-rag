---
phase: 07-profile-resume-upload
plan: 06
subsystem: observability
tags: [observability, langfuse, otel, pii-redaction, gap-closure, sdk-migration]
gap_closure: true
closes_gaps: [G-07-UAT-01]
requirements: [PROF-06]
dependency_graph:
  requires: [07-04]
  provides:
    - "Langfuse v4-compliant trace contract on POST /profile/upload + PATCH /profile"
    - "derive_langfuse_trace_id(seed) — deterministic 32-hex trace_id from extraction_id"
    - "redact_current_generation_input(client, char_count) — PII redaction helper"
    - "tests/_langfuse_fake.py::FakeLangfuseClient — contract-faithful v4 fake with v3 method-name regression guard"
  affects: ["src/job_rag/api/routes.py", "src/job_rag/observability.py", "tests/test_observability.py"]
tech_stack:
  added: []
  patterns:
    - "Langfuse 4.x OTel-based start_as_current_observation context manager"
    - "Deterministic trace correlation via create_trace_id(seed=str(uuid))"
    - "Two-layer PII redaction: update_current_generation + set_current_trace_io"
    - "Contract-faithful test fake (not Mock) with explicit v3 AttributeError guards"
key_files:
  created:
    - tests/_langfuse_fake.py
  modified:
    - src/job_rag/observability.py
    - src/job_rag/api/routes.py
    - tests/test_observability.py
    - .planning/phases/07-profile-resume-upload/deferred-items.md
decisions:
  - "Use start_as_current_observation as a context manager (not start_observation + manual .end()) so OTel context propagation auto-parents child spans + the langfuse.openai auto-GENERATION."
  - "Refactor upload_resume body into _run_resume_upload_pipeline helper so the fail-open branch (no Langfuse keys) can reuse the same code path."
  - "Two-layer redaction (generation + trace) instead of just generation — the captured trace-c744bb2d...json export showed PII at the trace.input level even with generation-level redaction applied."
  - "Build FakeLangfuseClient as a real Python class (not MagicMock) so v3 method names raise AttributeError. Closes the why-tests-passed gap that let G-07-UAT-01 ship."
metrics:
  duration: ~14m
  tasks: 3
  files: 4
  completed_date: 2026-05-30
---

# Phase 7 Plan 06: Langfuse SDK v4 Migration Summary

**One-liner:** Closed G-07-UAT-01 by porting the 5 broken Langfuse SDK 3.x call sites in `routes.py` to the installed Langfuse 4.1.0 OpenTelemetry-based API, restoring the PROF-06 trace correlation + PII redaction contract; replaced Mock-based tests with a contract-faithful `FakeLangfuseClient` that catches v3-method-name regressions at CI time.

## Context

The Phase 7 UAT (Adrian's first live upload via the deployed SWA + ACA stack) revealed that the manual `text_extract`, `diff_compute`, and `profile_save` spans never landed in Langfuse — only the auto-captured `langfuse.openai` GENERATION trace survived. Worse, that GENERATION's `input` field (and the trace root) shipped Adrian's resume verbatim: name, email, phone, LinkedIn, GitHub, and physical address all leaked to Langfuse Cloud.

Root cause: Plan 07-04 was written against Langfuse v3 (`lf.trace(...)` / `trace.span(...).end(...)` / `lf.update_current_observation(...)`) but the installed SDK is v4.1.0, where all 3 method names were removed. The 5 call sites raised `AttributeError`, which the T-07-08 fail-open guards silently caught — so the upload succeeded (correct), but tracing AND PII redaction silently no-op'd (catastrophic for D-32 + D-33).

The Mock-based tests in `test_observability.py` passed because `MagicMock()` accepts any method call, so `mock_lf.trace.return_value = mock_trace` looked like a working spy. The tests never exercised the real Langfuse 4.x contract surface.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add v4 helpers to observability.py + scaffold FakeLangfuseClient | `ad31379` | observability.py, _langfuse_fake.py, test_observability.py |
| 2 | Rewrite 5 broken Langfuse call sites in routes.py to v4 API | `3ffc244` | routes.py, observability.py (E402 hoist), _langfuse_fake.py (ruff autofix) |
| 3 | Replace Mock-based Langfuse tests with FakeLangfuseClient integration tests | `82bb8d5` | test_observability.py, deferred-items.md |

## The 5 v3 → v4 API Migrations

### Site 1: `routes.py:683-694` — Upload handler trace setup

**Before (v3):**
```python
lf = get_langfuse_client()
trace = None
if lf:
    try:
        trace = lf.trace(name="resume_upload", id=str(extraction_id),
                         user_id=str(user_id), tags=["resume", "phase-7"])
    except Exception:
        trace = None
```

**After (v4):**
```python
lf = get_langfuse_client()
if lf is None:
    return await _run_resume_upload_pipeline(session, user_id, extraction_id, raw, suffix)

trace_id = derive_langfuse_trace_id(extraction_id)
try:
    with lf.start_as_current_observation(
        name="resume_upload",
        as_type="span",
        trace_context={"trace_id": trace_id},
        metadata={"extraction_id": str(extraction_id), "user_id": str(user_id),
                  "phase": "7", "tags": ["resume", "phase-7"]},
    ):
        return await _run_resume_upload_pipeline(session, user_id, extraction_id, raw, suffix)
except HTTPException:
    raise
except Exception:
    log.exception("langfuse_trace_setup_failed", extraction_id=str(extraction_id))
    return await _run_resume_upload_pipeline(session, user_id, extraction_id, raw, suffix)
```

Key changes: `lf.trace(id=...)` replaced with `trace_context={"trace_id": derive_langfuse_trace_id(extraction_id)}` — the OTel-based v4 API uses a 32-hex hash of the seed to deterministically derive the trace_id, replacing v3's string-id-based correlation.

### Site 2: `routes.py:753-765` — `text_extract` child span

**Before (v3):**
```python
if trace is not None:
    try:
        trace.span(name="text_extract").end(metadata={...})
    except Exception:
        pass
```

**After (v4):**
```python
if lf:
    try:
        with lf.start_as_current_observation(
            name="text_extract",
            as_type="span",
            metadata={"file_type": file_type, "char_count": len(resume_text),
                      "page_count": page_count, "latency_ms": text_extract_ms},
        ):
            pass
    except Exception:
        pass
```

Key changes: `trace.span(...).end(...)` two-step pattern collapsed into a single `with start_as_current_observation(...) as span: pass` context manager. The span auto-ends on context exit.

### Site 3: `routes.py:802-808` — PII redaction on auto-captured GENERATION

**Before (v3):**
```python
if lf is not None:
    try:
        lf.update_current_observation(
            input={"text": f"[REDACTED — char_count={len(resume_text)}]"}
        )
    except Exception:
        pass
```

**After (v4):**
```python
if lf:
    redact_current_generation_input(lf, char_count=len(resume_text))
```

The new helper in `observability.py` performs TWO redactions (defense in depth):
1. `client.update_current_generation(input=REDACTED)` — overrides the child GENERATION's input field.
2. `client.set_current_trace_io(input=REDACTED)` — overrides the trace-level input (which is what showed PII in the captured `trace-c744bb2d...json` export).

Both calls are independently fail-open per T-07-08.

### Site 4: `routes.py:815-832` — `diff_compute` child span

Same pattern as Site 2. `trace.span(name="diff_compute").end(metadata=...)` replaced with `with lf.start_as_current_observation(name="diff_compute", as_type="span", metadata=...): pass`.

### Site 5: `routes.py:893-901` — PATCH /profile `profile_save` span

**Before (v3):**
```python
if lf is not None and payload.extraction_id is not None:
    try:
        trace = lf.trace(id=str(payload.extraction_id))
        trace.span(name="profile_save").end(metadata={"written_skill_count": len(payload.skills)})
    except Exception:
        pass
```

**After (v4):**
```python
if lf is not None and payload.extraction_id is not None:
    try:
        trace_id = derive_langfuse_trace_id(payload.extraction_id)
        with lf.start_as_current_observation(
            name="profile_save",
            as_type="span",
            trace_context={"trace_id": trace_id},
            metadata={"written_skill_count": len(payload.skills)},
        ):
            pass
    except Exception:
        log.warning("langfuse_profile_save_span_failed",
                    extraction_id=str(payload.extraction_id))
```

Cross-request correlation: re-derives the SAME `trace_id` from the SAME `extraction_id` seed so `profile_save` attaches to the same trace as the original `POST /profile/upload`.

## Diff Size

- `src/job_rag/api/routes.py`: 14,122 chars of diff (290 lines changed) — 5 call sites rewritten + new `_run_resume_upload_pipeline` helper extracted.
- `src/job_rag/observability.py`: 3,089 chars of diff (53 net lines added) — 2 new helpers (`derive_langfuse_trace_id`, `redact_current_generation_input`) + hoisted `hashlib` + `uuid as _uuid` imports to module top.
- `tests/_langfuse_fake.py`: 231 lines (new file) — `FakeLangfuseClient` + `_FakeObservation` + v3-name `AttributeError` guard.
- `tests/test_observability.py`: 481 lines of diff (Mock-based block dropped, 9 new tests across 4 test classes added).

## New Tests in `TestResumeUploadV4Tracing`

| Test | What it proves |
|------|----------------|
| `test_post_upload_records_three_child_observations` | Exact span order `[resume_upload, text_extract, diff_compute]` with `resume_upload.trace_id == derive_langfuse_trace_id(extraction_id)`. Catches any drift in span names, span order, or trace_id derivation. |
| `test_post_then_patch_share_trace_id` | PATCH `/profile` re-derives the same `trace_id` so `profile_save` attaches to the same trace as the original POST. Catches regressions in cross-request correlation. |
| `test_no_resume_pii_in_recorded_payloads` | Flattens every recorded `input`/`output`/`metadata` payload; asserts neither watermark (`"TEST FIXTURE"`, `"synthetic data"`) appears anywhere. Also asserts both `update_current_generation` AND `set_current_trace_io` recorded `[REDACTED — char_count=...]`. Catches D-33 / T-07-07 regressions at either layer. |
| `test_v3_method_calls_would_fail_loudly` | SDK-regression guard. `pytest.raises(AttributeError, match="v3 API removed")` on `fake.trace(...)` and `fake.update_current_observation(...)`. PROVES that if a future PR writes any v3 method name AND the test uses `FakeLangfuseClient`, CI catches it. |
| `test_fail_open_when_langfuse_disabled` | T-07-08 preserved: missing keys → 200 with valid UUID, no traceback. Same intent as the dropped `test_langfuse_fail_open_when_keys_missing` but exercises the new fail-open branch in `upload_resume`. |

Plus 3 helper tests retained from Task 1:
- `TestDeriveLangfuseTraceId::test_deterministic_for_same_seed`
- `TestDeriveLangfuseTraceId::test_different_for_different_seeds`
- `TestRedactCurrentGenerationInput::test_calls_both_update_and_set_trace_io`
- `TestRedactCurrentGenerationInput::test_fail_open_when_client_raises`
- `TestFakeLangfuseClient::test_v3_method_names_raise_attributeerror`
- `TestFakeLangfuseClient::test_records_start_as_current_observation_calls`

## FakeLangfuseClient Design Rationale

The Mock-based tests that shipped in Plan 07-04 looked like spies but accepted any method call without raising — including `lf.trace(...)`, which is gone in v4. So when production code called the v3 API and got `AttributeError` (silently caught by the fail-open guard), the tests still passed because `MagicMock().trace.return_value = MagicMock()` is happy to record a call that doesn't exist on the real class.

`FakeLangfuseClient` is a real Python class that implements EXACTLY the v4 surface (`start_as_current_observation`, `start_observation`, `update_current_span`, `update_current_generation`, `set_current_trace_io`, `create_trace_id`, `get_current_trace_id`, `get_current_observation_id`, `flush`, `auth_check`, `shutdown`) — and includes a `__getattr__` override that raises `AttributeError` with a migration hint for the 3 removed v3 names (`trace`, `update_current_observation`, `span`).

Every recorded call lands in `self.calls: list[tuple[str, dict]]` for assertion-based verification. Two helper methods (`span_names_recorded()`, `all_recorded_inputs()`) provide ergonomic accessors.

**Why this closes the why-tests-passed gap:** the next time a PR accidentally writes a v3 method name (or the SDK drops another v4 method), the FakeLangfuseClient `__getattr__` guard fires `AttributeError` AT TEST TIME — not at runtime where the T-07-08 fail-open guard silently swallows it.

## Verification Results

```bash
# Static checks
grep -rnE "lf\.trace\(|trace\.span\(|update_current_observation\(" src/    # 0 matches
# 4 v4 spans present (semantic multi-line regex):
#   start_as_current_observation(name="resume_upload")
#   start_as_current_observation(name="text_extract")
#   start_as_current_observation(name="diff_compute")
#   start_as_current_observation(name="profile_save")
grep -nE "redact_current_generation_input\(lf" src/job_rag/api/routes.py    # 1 match

# Pyright
uv run pyright src/job_rag/observability.py src/job_rag/api/routes.py \
              tests/_langfuse_fake.py tests/test_observability.py
# → 0 errors, 0 warnings, 0 informations

# Ruff
uv run ruff check src/job_rag/api/routes.py src/job_rag/observability.py \
                 tests/_langfuse_fake.py tests/test_observability.py
# → All checks passed!

# Targeted tests
uv run pytest tests/test_observability.py tests/test_profile.py \
              tests/test_resume_extractor.py
# → 39 passed in 7.29s

# Full backend suite (excluding pre-existing failures per deferred-items.md)
uv run pytest --ignore=tests/test_alembic.py \
              --deselect tests/test_matching.py::test_load_profile_returns_seeded_row
# → 269 passed, 8 skipped, 1 deselected
```

## Deferred Issues

### Pre-existing failure: `test_load_profile_returns_seeded_row`

Documented in `.planning/phases/07-profile-resume-upload/deferred-items.md`. The seeded `user_profile.skills_json` in the live dev DB has drifted from the hardcoded test expectation — Adrian re-ran `POST /profile/upload` + `PATCH /profile` during the UAT that captured G-07-UAT-01, which replaced the migration-seeded skills with LLM-extracted skills from his actual resume.

Verified pre-existing by reverting all 4 files modified by Plan 07-06 to commit `056c3df` and rerunning the test — failure reproduces identically. OUT OF SCOPE per the GSD executor SCOPE BOUNDARY rule. Plan 07-06 did not modify `tests/test_matching.py`, the seed migration, or `load_profile`.

## DeprecationWarning Note

`Langfuse.set_current_trace_io(input=...)` emits a `DeprecationWarning` in v4.1.0 — Langfuse plans to remove trace-level I/O setters in a future major version and recommends `propagate_attributes()` instead. We KNOWINGLY keep the deprecated call because it's the only way to override the TRACE-LEVEL input that `langfuse.openai` writes (the layer where the captured `trace-c744bb2d...json` export showed PII). The `<interfaces>` block of the plan explicitly documents this trade-off. When Langfuse ships a non-deprecated trace-input setter (or a switch on the `langfuse.openai` wrapper to suppress its trace-input write), file a follow-up issue to migrate.

## Adrian's Post-Merge Live-UAT Replay

To close G-07-UAT-01 in `07-VERIFICATION.md`:

1. With `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` set in the ACA env, upload a 1.5 MB PDF via the running SWA UI.
2. Open the Langfuse dashboard; find the most recent trace.
3. Confirm:
   - Trace contains a parent span named `resume_upload` with `metadata.extraction_id` set.
   - 2 explicit child spans (`text_extract`, `diff_compute`).
   - 1 auto-captured GENERATION child (the `langfuse.openai` wrapper's default name).
4. PATCH the profile via the Save button; the same trace gains a `profile_save` child span.
5. Confirm: NEITHER the trace root input NOR the generation child input contains Adrian's name, email, phone, LinkedIn, GitHub, or address. The string `"[REDACTED — char_count=N]"` should appear in their place.

## Self-Check: PASSED

Verified the following exist:

- **Files created:** `tests/_langfuse_fake.py` — FOUND
- **Files modified:** `src/job_rag/observability.py` (53 net lines added), `src/job_rag/api/routes.py` (290 lines changed), `tests/test_observability.py` (Mock block dropped + 9 tests added across 4 classes), `.planning/phases/07-profile-resume-upload/deferred-items.md` (1 section added) — all FOUND
- **Commits:** `ad31379`, `3ffc244`, `82bb8d5` — all in `git log --oneline 056c3df..HEAD`
- **Static checks:** v3 patterns absent, v4 spans present, redact helper invoked — all PASS
- **Tests:** 17 test_observability + 14 test_profile + 8 test_resume_extractor = 39 PASS; full backend 269 PASS excluding 2 documented pre-existing failures
- **Pyright:** 0 errors across all 4 touched files
- **Ruff:** all checks pass
