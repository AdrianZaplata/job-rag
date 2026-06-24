---
phase: 07-profile-resume-upload
plan: 06
type: execute
wave: 1
depends_on: [04]
files_modified:
  - src/job_rag/observability.py
  - src/job_rag/api/routes.py
  - tests/test_observability.py
  - tests/_langfuse_fake.py
autonomous: true
gap_closure: true
requirements: [PROF-06]
closes_gaps: [G-07-UAT-01]
tags: [observability, langfuse, otel, pii-redaction, gap-closure]

must_haves:
  truths:
    - "A real Langfuse 4.1.0 client receives a parent `resume_upload` span (or trace whose root span is named `resume_upload`) keyed by a deterministic trace_id derived from `extraction_id`."
    - "The auto-captured `langfuse.openai` GENERATION observation is a CHILD of the `resume_upload` parent span in the same trace, NOT a standalone trace."
    - "Three explicit child spans exist under `resume_upload`: `text_extract`, `diff_compute`, and (when PATCH is called with matching extraction_id) `profile_save`."
    - "Raw resume text NEVER appears in any span input, output, or metadata — the GENERATION's `input` field is overwritten with `[REDACTED — char_count=N]` BEFORE the langfuse client flushes the observation, and trace-level input is overwritten via `set_current_trace_io(input=...)` so legacy LLM-as-judge evaluators don't see PII."
    - "When `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are unset, the upload + PATCH endpoints still return 200 and the trace simply never gets created (T-07-08 fail-open preserved)."
    - "If a future PR reintroduces any v3 method name (`lf.trace(...)`, `trace.span(...).end(...)`, `lf.update_current_observation(...)`) on the live SDK, the new integration test in `tests/test_observability.py` fails — the test exercises the real `Langfuse` class surface (via a contract-faithful fake, NOT `MagicMock`)."
  artifacts:
    - path: "src/job_rag/observability.py"
      provides: "Langfuse 4.x client factory + new `redact_current_generation_input(char_count)` helper that wraps `update_current_generation(input=...)` with fail-open semantics + new `derive_langfuse_trace_id(seed)` helper wrapping `create_trace_id(seed=str(extraction_id))`"
      contains: "def derive_langfuse_trace_id(seed:"
      contains_also: "def redact_current_generation_input("
    - path: "src/job_rag/api/routes.py"
      provides: "v4-compliant tracing on POST /profile/upload and PATCH /profile — uses `with lf.start_as_current_observation(...)` context managers; no `.trace()` / `.span().end()` / `.update_current_observation()` calls anywhere in the file"
      contains: "start_as_current_observation"
      forbids_strings: ["lf.trace(", ".update_current_observation(", "trace.span("]
    - path: "tests/_langfuse_fake.py"
      provides: "FakeLangfuseClient implementing the v4 contract surface (start_as_current_observation, start_observation, update_current_span, update_current_generation, set_current_trace_io, create_trace_id, flush, auth_check) that records all calls + raises AttributeError on any v3 method name — used by the new integration tests"
      contains: "class FakeLangfuseClient"
      contains_also: "def start_as_current_observation"
    - path: "tests/test_observability.py"
      provides: "Rewritten Langfuse trace tests using the FakeLangfuseClient: 4-span shape, no-PII (resume bytes never reach span/trace i/o), v3 method-name regression guard, fail-open when keys missing"
      contains: "FakeLangfuseClient"
      forbids_strings: ["mock_lf.trace.return_value", "mock_trace.span.call_args_list"]
  key_links:
    - from: "src/job_rag/api/routes.py POST /profile/upload"
      to: "langfuse.start_as_current_observation(name='resume_upload', trace_context={'trace_id': derived_id}, ...)"
      via: "context manager wrapping all 3 manual spans + the OpenAI call"
      pattern: "start_as_current_observation\\(name=.resume_upload."
    - from: "src/job_rag/api/routes.py POST /profile/upload (after extract_resume returns)"
      to: "lf.update_current_generation(input={'text': f'[REDACTED — char_count={n}]'})"
      via: "called from inside the resume_upload parent context but AFTER the langfuse.openai wrapper has set the generation"
      pattern: "update_current_generation"
    - from: "src/job_rag/api/routes.py PATCH /profile"
      to: "lf.start_as_current_observation(name='profile_save', trace_context={'trace_id': derive_langfuse_trace_id(payload.extraction_id)})"
      via: "re-derives the same trace_id from the same seed so the span attaches to the same trace"
      pattern: "start_as_current_observation\\(name=.profile_save."
    - from: "tests/test_observability.py"
      to: "tests/_langfuse_fake.py::FakeLangfuseClient"
      via: "patch('job_rag.api.routes.get_langfuse_client', return_value=FakeLangfuseClient())"
      pattern: "FakeLangfuseClient"
---

<objective>
Close G-07-UAT-01 by porting the 5 broken Langfuse SDK 3.x call sites in `routes.py` to the installed Langfuse 4.1.0 OpenTelemetry-based API, restoring the PROF-06 success-criterion 5 contract ("single trace per upload spanning text-extract → Instructor → diff → PATCH; raw resume text NEVER in trace.input").

Purpose:
- Make the manual `text_extract`, `diff_compute`, and `profile_save` spans actually render in Langfuse (currently all 5 v3-API calls raise `AttributeError`, are swallowed by the T-07-08 fail-open guard, and silently no-op — only the standalone `langfuse.openai` GENERATION trace survives).
- Restore D-33 PII redaction so resume bytes (name, email, phone, LinkedIn URL, GitHub URL, address) never reach Langfuse — currently they ship verbatim in `trace.input` per the captured `trace-c744bb2d0683a35da965946940e70bab.json` export.
- Replace the Mock-based unit tests that let this regression slip through (`MagicMock().trace.return_value` accepts any method without raising) with a contract-faithful fake that mirrors the real Langfuse 4.x surface and asserts AttributeError on any v3 method name — so the next time the SDK changes, CI fails.

Output:
- One modified `src/job_rag/observability.py` (two small helpers added; the existing `get_langfuse_client()` factory keeps its shape and continues to return a real `Langfuse` instance).
- One modified `src/job_rag/api/routes.py` (5 call sites rewritten; total diff ≈ 60 lines changed in the upload + PATCH handlers).
- One new file `tests/_langfuse_fake.py` (~120 lines) — a `FakeLangfuseClient` that implements the v4 contract and records every call.
- One rewritten `tests/test_observability.py` Phase-7 block (3 tests dropped + 4 tests added; total file delta ≈ 200 lines).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/07-profile-resume-upload/07-CONTEXT.md
@.planning/phases/07-profile-resume-upload/07-VERIFICATION.md
@.planning/phases/07-profile-resume-upload/07-HUMAN-UAT.md
@.planning/phases/07-profile-resume-upload/07-04-upload-routes-diff-langfuse-SUMMARY.md
@src/job_rag/api/routes.py
@src/job_rag/observability.py
@tests/test_observability.py

<interfaces>
<!-- Concrete Langfuse 4.1.0 surface the executor MUST use. Inspected from the
     installed `langfuse` package via `inspect.signature(...)` and docstrings —
     do NOT use any v3 method name. The 5 broken call sites in routes.py call
     v3 methods that do NOT exist on this version. -->

Installed version (verified via `uv pip list | grep langfuse`):
  langfuse  4.1.0

v4 Langfuse class public methods that EXIST (use only these):
  - start_as_current_observation(*, name, as_type='span'|'generation'|..., trace_context=None,
                                  input=None, output=None, metadata=None, end_on_exit=True,
                                  ...) -> ContextManager[LangfuseSpan|LangfuseGeneration|...]
  - start_observation(*, name, as_type='span', trace_context=None, input=None, output=None,
                       metadata=None, ...) -> LangfuseSpan|LangfuseGeneration  (manual .end() required)
  - update_current_span(*, name=None, input=None, output=None, metadata=None, version=None,
                         level=None, status_message=None)
  - update_current_generation(*, name=None, input=None, output=None, metadata=None, ...)
  - set_current_trace_io(*, input=None, output=None)   # DEPRECATED but works; used for
                                                       # trace-level PII redaction (overrides
                                                       # any input/output the langfuse.openai
                                                       # wrapper writes to the trace root)
  - create_trace_id(seed: str | None = None) -> str    # 32-hex lowercase deterministic
                                                       # when `seed` is provided
  - get_current_trace_id() -> str | None
  - get_current_observation_id() -> str | None
  - flush()
  - auth_check() -> bool
  - shutdown()

v3 method names that DO NOT EXIST on v4 (forbid in routes.py and observability.py):
  - lf.trace(...)                  # gone — replaced by start_as_current_observation
  - trace.span(...).end(...)       # gone — replaced by start_as_current_observation
  - lf.update_current_observation(...)  # gone — split into update_current_span /
                                        #   update_current_generation

TraceContext shape (from `langfuse.types`):
  class TraceContext(TypedDict):
      trace_id: str
      parent_span_id: NotRequired[str]

  # Use trace_context to attach a span to an existing/derived trace_id (this is
  # the v4 mechanism that replaces v3's `lf.trace(id=str(extraction_id))`).

Cross-request correlation pattern (REPLACES the v3 `lf.trace(id=str(extraction_id))`):

  # POST /profile/upload — start the trace:
  trace_id = lf.create_trace_id(seed=str(extraction_id))  # 32-hex deterministic
  with lf.start_as_current_observation(
      name="resume_upload",
      as_type="span",
      trace_context={"trace_id": trace_id},
      metadata={"extraction_id": str(extraction_id), "phase": "7"},
  ) as root_span:
      # All nested start_as_current_observation calls and the langfuse.openai
      # auto-generation are automatically children of this span / trace via the
      # OTel context propagation.
      ...

  # PATCH /profile (only if payload.extraction_id is provided) —
  # re-derive the same trace_id from the same seed:
  trace_id = lf.create_trace_id(seed=str(payload.extraction_id))
  with lf.start_as_current_observation(
      name="profile_save",
      as_type="span",
      trace_context={"trace_id": trace_id},
      metadata={"written_skill_count": len(payload.skills)},
  ) as save_span:
      ...

PII redaction pattern (REPLACES the v3 `lf.update_current_observation(input=...)`):

  # The langfuse.openai wrapper auto-captures a CHILD `OpenAI-generation`
  # observation INSIDE the resume_upload parent (because we wrap the LLM call
  # inside the start_as_current_observation context). To redact the resume
  # text from that auto-captured generation, do TWO things AFTER the LLM call
  # returns:
  #
  # 1. Overwrite the CHILD generation's input (auto-captured by langfuse.openai):
  lf.update_current_generation(
      input={"text": f"[REDACTED — char_count={len(resume_text)}]"}
  )
  # NOTE: update_current_generation targets the currently-active generation in
  # the OTel context. When called immediately after `await asyncio.to_thread(
  # extract_resume, ...)` returns, the auto-captured generation is still the
  # current observation (the wrapper sets it, we're back in the parent span
  # context). If this proves fragile, the fallback is to wrap the extract_resume
  # call inside an explicit `with lf.start_as_current_observation(name="llm_extract",
  # as_type="generation") as g:` block and call `g.update(input=..., output=...)`.
  #
  # 2. Overwrite the TRACE-LEVEL input (which langfuse.openai also writes — this
  # is what showed PII in trace-c744bb2d...json's trace.input):
  lf.set_current_trace_io(
      input={"text": f"[REDACTED — char_count={len(resume_text)}]"}
  )

Existing code in src/job_rag/observability.py that stays AS-IS:
  - is_enabled()                — returns bool(public_key and secret_key)
  - _ensure_env()               — copies settings into os.environ
  - get_openai_client()         — @lru_cache; returns langfuse.openai.OpenAI when enabled
  - _langfuse_handler()         — LangChain callback handler factory
  - get_langchain_callbacks()   — returns [handler] or []
  - flush()                     — best-effort flush
  - get_langfuse_client()       — @lru_cache; returns Langfuse(public_key, secret_key, host)
                                  when enabled, None otherwise (v4-compatible — Langfuse
                                  class init signature is unchanged across v3→v4)
</interfaces>

<existing_call_sites>
<!-- The 5 broken sites in src/job_rag/api/routes.py the executor must rewrite.
     Line numbers are from current HEAD; expect ±10 line drift after edit. -->

routes.py:683-694   (upload handler, trace setup)
  lf = get_langfuse_client()
  trace = None
  if lf:
      try:
          trace = lf.trace(name="resume_upload", id=str(extraction_id),
                           user_id=str(user_id), tags=["resume", "phase-7"])
      except Exception:
          trace = None
  ↓ MUST BECOME (top-of-handler trace_id derivation + with-block that wraps
  the remainder of the handler):
  trace_id = derive_langfuse_trace_id(extraction_id)  # NEW helper in observability.py
  lf = get_langfuse_client()
  # Use an ExitStack or an `async with` pattern so the `if lf:` branch can
  # conditionally enter the context manager. See task 2 implementation notes
  # for the recommended `contextlib.AsyncExitStack` + manual span lifecycle.

routes.py:753-765   (text_extract span)
  if trace is not None:
      try:
          trace.span(name="text_extract").end(metadata={...})
      except Exception:
          pass
  ↓ MUST BECOME:
  if lf:
      with lf.start_as_current_observation(name="text_extract", as_type="span",
                                           metadata={...}):
          pass  # the metadata is on the span; nothing to do inside

routes.py:802-808   (PII redaction on the auto-captured GENERATION)
  if lf is not None:
      try:
          lf.update_current_observation(
              input={"text": f"[REDACTED — char_count={len(resume_text)}]"}
          )
      except Exception:
          pass
  ↓ MUST BECOME (call redact_current_generation_input helper from observability.py
  which fail-open-wraps BOTH update_current_generation AND set_current_trace_io):
  if lf:
      redact_current_generation_input(lf, char_count=len(resume_text))

routes.py:815-832   (diff_compute span)
  if trace is not None:
      try:
          trace.span(name="diff_compute").end(metadata={...})
      except Exception:
          pass
  ↓ MUST BECOME:
  if lf:
      with lf.start_as_current_observation(name="diff_compute", as_type="span",
                                           metadata={...}):
          pass

routes.py:893-901   (PATCH /profile — profile_save span attaches via re-derived trace_id)
  if lf is not None and payload.extraction_id is not None:
      try:
          trace = lf.trace(id=str(payload.extraction_id))
          trace.span(name="profile_save").end(metadata={...})
      except Exception:
          pass
  ↓ MUST BECOME:
  if lf and payload.extraction_id is not None:
      try:
          trace_id = derive_langfuse_trace_id(payload.extraction_id)
          with lf.start_as_current_observation(
              name="profile_save",
              as_type="span",
              trace_context={"trace_id": trace_id},
              metadata={"written_skill_count": len(payload.skills)},
          ):
              pass
      except Exception:  # pragma: no cover — fail-open per T-07-08
          pass
</existing_call_sites>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add v4 helpers to observability.py + scaffold FakeLangfuseClient</name>
  <files>src/job_rag/observability.py, tests/_langfuse_fake.py</files>
  <behavior>
    Test cases that MUST exist and pass after this task:

    Test 1 — `tests/test_observability.py::TestDeriveLangfuseTraceId::test_deterministic_for_same_seed`:
      - `derive_langfuse_trace_id(uuid.UUID("11111111-1111-1111-1111-111111111111"))`
        returns the SAME 32-char lowercase hex string on every call.
      - Returns `len(s) == 32 and all(c in "0123456789abcdef" for c in s)`.

    Test 2 — `tests/test_observability.py::TestDeriveLangfuseTraceId::test_different_for_different_seeds`:
      - Two different UUIDs produce two different 32-hex IDs.

    Test 3 — `tests/test_observability.py::TestRedactCurrentGenerationInput::test_calls_both_update_and_set_trace_io`:
      - Build a `FakeLangfuseClient`; call `redact_current_generation_input(client, char_count=42)`.
      - Assert client recorded `update_current_generation(input={"text": "[REDACTED — char_count=42]"})`
        AND `set_current_trace_io(input={"text": "[REDACTED — char_count=42]"})`.

    Test 4 — `tests/test_observability.py::TestRedactCurrentGenerationInput::test_fail_open_when_client_raises`:
      - Build a `FakeLangfuseClient` configured to raise `RuntimeError("boom")` from `update_current_generation`.
      - Call `redact_current_generation_input(client, char_count=99)`.
      - Assert NO exception propagates (T-07-08 fail-open contract).
      - Assert `set_current_trace_io` was still attempted (the redaction helper retries the trace-level
        write even when the generation-level write failed — defense in depth for PII).

    Test 5 — `tests/_langfuse_fake.py::FakeLangfuseClient` exists with the methods listed in <interfaces>
      and `__call_log` recording every call.

    Test 6 — `FakeLangfuseClient` raises `AttributeError` on every v3 method name (regression guard):
      - `fake.trace(name="x")` → AttributeError mentioning "v3 API removed; use start_as_current_observation".
      - `fake.update_current_observation(input={})` → AttributeError.
      - Any attribute access for `update_current_observation` or `trace` (callable or not) raises AttributeError.
  </behavior>
  <read_first>
    - src/job_rag/observability.py — current state (107 lines). Confirm `get_langfuse_client()`
      already exists with the v4-compatible `from langfuse import Langfuse` signature.
    - Re-read the <interfaces> block above for the exact v4 method names.
    - tests/test_observability.py lines 1-273 — to confirm import style + naming convention; do NOT
      modify it in this task (Task 3 rewrites the Phase-7 block).
  </read_first>
  <action>
    Step 1 — Append two helpers to `src/job_rag/observability.py` (below the existing
    `get_langfuse_client()` function). Use the exact signatures and bodies below — do NOT improvise:

    ```python
    import uuid as _uuid  # local alias to avoid shadowing if uuid is used elsewhere


    def derive_langfuse_trace_id(seed: _uuid.UUID | str) -> str:
        """Derive a deterministic 32-char hex Langfuse trace_id from an extraction_id (Phase 7 G-07-UAT-01).

        Langfuse 4.x replaces the v3 `lf.trace(id=...)` correlation API with a
        `create_trace_id(seed=...)` helper that hashes the seed into a 16-byte
        OTel-compatible trace_id. Both POST /profile/upload and PATCH /profile
        derive the same trace_id from the same `extraction_id` so spans land on
        the same trace.

        Fail-open: returns the (deterministic) ID even when Langfuse is disabled —
        callers should check `get_langfuse_client()` before consuming the ID for
        actual tracing. This avoids a None-check at every call site.
        """
        lf = get_langfuse_client()
        seed_str = str(seed)
        if lf is None:
            # Compute the same 32-hex via the underlying mechanism so tests that
            # patch out the client still get a stable ID.
            # Langfuse uses BLAKE2b(seed)[:16].hex(); we replicate to keep the
            # promise of determinism when the client is absent.
            import hashlib
            return hashlib.blake2b(seed_str.encode("utf-8"), digest_size=16).hexdigest()
        return lf.create_trace_id(seed=seed_str)


    def redact_current_generation_input(client: Any, *, char_count: int) -> None:
        """Overwrite resume PII on the auto-captured GENERATION + trace input (D-33 / G-07-UAT-01).

        The `langfuse.openai` wrapper auto-captures the LLM call as a child
        GENERATION observation AND writes the raw input to the trace root.
        This helper performs BOTH redactions in v4-compatible style:

        1. `client.update_current_generation(input=REDACTED)` — overrides the
           CHILD generation's input field.
        2. `client.set_current_trace_io(input=REDACTED)` — overrides the
           TRACE-LEVEL input (which is what showed PII in the
           trace-c744bb2d...json export captured during live UAT).

        Both calls are wrapped in `try/except Exception: pass` per T-07-08
        fail-open semantics. If step 1 raises, step 2 is still attempted.
        """
        redacted = {"text": f"[REDACTED — char_count={char_count}]"}
        try:
            client.update_current_generation(input=redacted)
        except Exception:  # pragma: no cover - fail-open per T-07-08
            log.warning("langfuse_redact_generation_failed", char_count=char_count)
        try:
            client.set_current_trace_io(input=redacted)
        except Exception:  # pragma: no cover - fail-open per T-07-08
            log.warning("langfuse_redact_trace_failed", char_count=char_count)
    ```

    Step 2 — Create `tests/_langfuse_fake.py` with the `FakeLangfuseClient` class.
    This is a contract-faithful fake (NOT a Mock) — it implements the v4 surface as
    real Python methods, records every call into `self.calls: list[tuple[str, dict]]`,
    and explicitly raises `AttributeError` on v3 method names so SDK regressions are
    caught at test time:

    ```python
    """Contract-faithful fake of the Langfuse 4.x client surface.

    Replaces the Mock-based tests that let G-07-UAT-01 slip through: a
    MagicMock() accepts any method call without raising, so v3 calls like
    `lf.trace(...)` looked fine in tests but were AttributeErrors in
    production. This fake implements EXACTLY the v4 surface and raises
    AttributeError on every known v3 method name.

    Used by tests/test_observability.py — never imported by production code.
    """
    from __future__ import annotations

    import contextlib
    import hashlib
    from typing import Any, Iterator


    # v3 names that MUST raise AttributeError if accessed — keeps the next SDK
    # regression from slipping through silently.
    _V3_REMOVED_NAMES = frozenset({
        "trace",
        "update_current_observation",
        "span",  # was a method on trace, not Langfuse, but guard anyway
    })


    class _FakeObservation:
        """Stand-in for LangfuseSpan / LangfuseGeneration as a context manager."""

        def __init__(self, parent: "FakeLangfuseClient", name: str, as_type: str,
                     trace_id: str | None, metadata: dict | None,
                     input_: Any, output: Any) -> None:
            self._parent = parent
            self.name = name
            self.as_type = as_type
            self.trace_id = trace_id
            self.metadata = metadata or {}
            self.input = input_
            self.output = output
            self.id = f"obs-{len(parent.calls)}"

        def __enter__(self) -> "_FakeObservation":
            self._parent.calls.append(("enter_observation", {
                "name": self.name, "as_type": self.as_type,
                "trace_id": self.trace_id, "metadata": dict(self.metadata),
                "input": self.input,
            }))
            self._parent._active_stack.append(self)
            return self

        def __exit__(self, *exc_info: Any) -> None:
            self._parent.calls.append(("exit_observation", {"name": self.name}))
            self._parent._active_stack.pop()

        def update(self, **kwargs: Any) -> None:
            self._parent.calls.append(("observation_update",
                                        {"name": self.name, **kwargs}))

        def end(self, **kwargs: Any) -> None:
            # v4 spans do NOT need explicit end() — the context manager handles it.
            # We still implement it so legacy patterns don't crash, but record
            # it so tests can detect lingering v3 idioms in production code.
            self._parent.calls.append(("observation_end_called",
                                        {"name": self.name, **kwargs}))


    class FakeLangfuseClient:
        """Fake of langfuse.Langfuse implementing the v4 contract.

        Every call is recorded in `self.calls` as `(method_name, kwargs_dict)`.
        Access to any v3 method name raises AttributeError with a migration hint.

        Optional `raise_on` attribute lets tests force a specific method to
        raise — used to verify fail-open semantics.
        """

        def __init__(self, *, raise_on: dict[str, Exception] | None = None) -> None:
            self.calls: list[tuple[str, dict]] = []
            self._active_stack: list[_FakeObservation] = []
            self._raise_on = raise_on or {}
            self._authed = True

        # ---- v4 surface ----

        def create_trace_id(self, seed: str | None = None) -> str:
            if "create_trace_id" in self._raise_on:
                raise self._raise_on["create_trace_id"]
            self.calls.append(("create_trace_id", {"seed": seed}))
            if seed is None:
                return "00" * 16
            return hashlib.blake2b(seed.encode("utf-8"), digest_size=16).hexdigest()

        @contextlib.contextmanager
        def start_as_current_observation(
            self,
            *,
            name: str,
            as_type: str = "span",
            trace_context: dict | None = None,
            input: Any = None,
            output: Any = None,
            metadata: dict | None = None,
            **kwargs: Any,
        ) -> Iterator[_FakeObservation]:
            if "start_as_current_observation" in self._raise_on:
                raise self._raise_on["start_as_current_observation"]
            trace_id = (trace_context or {}).get("trace_id")
            obs = _FakeObservation(self, name=name, as_type=as_type,
                                    trace_id=trace_id, metadata=metadata,
                                    input_=input, output=output)
            with obs:
                yield obs

        def start_observation(self, *, name: str, as_type: str = "span",
                              trace_context: dict | None = None,
                              metadata: dict | None = None, **kwargs: Any) -> _FakeObservation:
            self.calls.append(("start_observation", {"name": name, "as_type": as_type}))
            trace_id = (trace_context or {}).get("trace_id")
            return _FakeObservation(self, name=name, as_type=as_type,
                                     trace_id=trace_id, metadata=metadata,
                                     input_=None, output=None)

        def update_current_span(self, **kwargs: Any) -> None:
            if "update_current_span" in self._raise_on:
                raise self._raise_on["update_current_span"]
            current = self._active_stack[-1].name if self._active_stack else None
            self.calls.append(("update_current_span", {"current": current, **kwargs}))

        def update_current_generation(self, **kwargs: Any) -> None:
            if "update_current_generation" in self._raise_on:
                raise self._raise_on["update_current_generation"]
            current = self._active_stack[-1].name if self._active_stack else None
            self.calls.append(("update_current_generation", {"current": current, **kwargs}))

        def set_current_trace_io(self, **kwargs: Any) -> None:
            if "set_current_trace_io" in self._raise_on:
                raise self._raise_on["set_current_trace_io"]
            self.calls.append(("set_current_trace_io", kwargs))

        def get_current_trace_id(self) -> str | None:
            if not self._active_stack:
                return None
            return self._active_stack[-1].trace_id

        def get_current_observation_id(self) -> str | None:
            if not self._active_stack:
                return None
            return self._active_stack[-1].id

        def flush(self) -> None:
            self.calls.append(("flush", {}))

        def auth_check(self) -> bool:
            return self._authed

        def shutdown(self) -> None:
            self.calls.append(("shutdown", {}))

        # ---- v3 guard ----

        def __getattr__(self, name: str) -> Any:
            if name in _V3_REMOVED_NAMES:
                raise AttributeError(
                    f"Langfuse v3 API removed in v4: '{name}'. "
                    "Migrate to start_as_current_observation / update_current_span / "
                    "update_current_generation. See observability.py docstring."
                )
            raise AttributeError(name)

        # ---- test helpers ----

        def span_names_recorded(self) -> list[str]:
            """Return the ordered list of span names that entered the context."""
            return [
                kwargs["name"]
                for method, kwargs in self.calls
                if method == "enter_observation"
            ]

        def all_recorded_inputs(self) -> list[Any]:
            """Return every input/metadata payload written via any method.
            Used by the PII-redaction test to scan for resume bytes."""
            payloads: list[Any] = []
            for method, kwargs in self.calls:
                for key in ("input", "output", "metadata"):
                    if key in kwargs:
                        payloads.append(kwargs[key])
            return payloads
    ```

    Step 3 — Run the 4 helper tests + 2 fake-API tests (described in <behavior>).
    Place the helper tests in `tests/test_observability.py` under new classes
    `TestDeriveLangfuseTraceId` and `TestRedactCurrentGenerationInput`. Place the
    FakeLangfuseClient tests in a new module-level class `TestFakeLangfuseClient`
    inside `tests/test_observability.py`.

    Step 4 — Run `uv run pytest tests/test_observability.py -k "DeriveLangfuseTraceId or RedactCurrentGenerationInput or FakeLangfuseClient" -x` and confirm all 6 tests pass.
  </action>
  <verify>
    <automated>uv run pytest tests/test_observability.py -k "DeriveLangfuseTraceId or RedactCurrentGenerationInput or FakeLangfuseClient" -x -v</automated>
  </verify>
  <done>
    - `src/job_rag/observability.py` exports `derive_langfuse_trace_id(seed)` and `redact_current_generation_input(client, *, char_count)`.
    - `tests/_langfuse_fake.py` exists with `FakeLangfuseClient` per the spec above.
    - 6 new tests pass under `pytest -k "DeriveLangfuseTraceId or RedactCurrentGenerationInput or FakeLangfuseClient"`.
    - `grep -E "lf.trace\\(|update_current_observation\\(|trace\\.span\\(" src/job_rag/observability.py` returns NO matches (helpers use only v4 names).
    - `uv run pyright src/job_rag/observability.py tests/_langfuse_fake.py` returns 0 errors.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite the 5 broken Langfuse call sites in routes.py to v4 API</name>
  <files>src/job_rag/api/routes.py</files>
  <behavior>
    Test cases that the rewritten code must satisfy (these tests are written in Task 3
    but the behaviour they assert is the contract Task 2 must deliver):

    Behaviour 1 — Real `langfuse.Langfuse` 4.1.0 client (or `FakeLangfuseClient` standing in
    via dependency injection) receives `start_as_current_observation(name='resume_upload',
    as_type='span', trace_context={'trace_id': <32-hex derived from extraction_id>}, ...)`
    AS THE FIRST `start_as_current_observation` CALL during a `POST /profile/upload`.

    Behaviour 2 — Within that parent context, the executor calls `start_as_current_observation`
    for `text_extract` AND `diff_compute` (2 explicit children), and the `extract_resume`
    call happens INSIDE the parent context so the langfuse.openai wrapper attaches its
    auto-GENERATION as a child of the same trace.

    Behaviour 3 — IMMEDIATELY after `await asyncio.to_thread(extract_resume, resume_text)`
    returns, the executor calls `redact_current_generation_input(lf, char_count=len(resume_text))`
    — and this happens while still inside the `resume_upload` parent context.

    Behaviour 4 — `PATCH /profile` with a payload that includes `extraction_id` derives
    the SAME trace_id via `derive_langfuse_trace_id(payload.extraction_id)` and opens
    `start_as_current_observation(name='profile_save', trace_context={'trace_id': trace_id},
    metadata={'written_skill_count': N})`.

    Behaviour 5 — When `get_langfuse_client()` returns `None` (T-07-08 fail-open), the
    upload AND PATCH paths complete normally (200 response, no trace), no AttributeError
    propagates, the response shape is unchanged.

    Behaviour 6 — `grep -nE "lf\\.trace\\(|trace\\.span\\(|update_current_observation\\(" src/job_rag/api/routes.py`
    returns ZERO matches.

    Behaviour 7 — `grep -nE "start_as_current_observation\\(name=.resume_upload\\.|name=.text_extract\\.|name=.diff_compute\\.|name=.profile_save\\." src/job_rag/api/routes.py`
    returns AT LEAST 4 matches.

    Behaviour 8 — Pyright clean: `uv run pyright src/job_rag/api/routes.py` returns 0 errors.

    Behaviour 9 — Existing 22 tests in `tests/test_profile.py` + `tests/test_resume_extractor.py`
    continue to pass (no regression on PROF-02/03/04/05/06 code paths outside the trace).
  </behavior>
  <read_first>
    - src/job_rag/api/routes.py lines 605-908 — the existing upload_resume + update_profile
      handlers (~300 lines). Pay particular attention to the `if lf:` / `if trace is not None:`
      guard structure — the new code must collapse the dual `lf` + `trace` variables into a
      single `lf` reference (no more `trace = lf.trace(...)`).
    - The <existing_call_sites> block above for the verbatim before/after of each of the 5
      sites.
    - The <interfaces> block for the v4 method signatures.
    - src/job_rag/observability.py (post-Task-1 state) — confirm `derive_langfuse_trace_id`
      and `redact_current_generation_input` exist and behave per Task 1 contract.
  </read_first>
  <action>
    Step 1 — Add imports at the top of `routes.py` (next to the existing
    `from job_rag.observability import get_langfuse_client`):

    ```python
    from job_rag.observability import (
        derive_langfuse_trace_id,
        get_langfuse_client,
        redact_current_generation_input,
    )
    ```

    Step 2 — Replace the upload_resume handler's tracing flow. The structural change is:
    the entire post-Content-Length-check body becomes wrapped in an
    `if lf:` / `else:` branch where the `if` branch uses
    `with lf.start_as_current_observation(name="resume_upload", ...)` as a context manager
    around ALL the work (text_extract → LLM → diff_compute → response build), and the
    `else` branch runs the same code without the wrapper.

    To avoid massive duplication, factor the body into a private async helper inside
    the file (top-level, not nested — easier to type-check):

    ```python
    async def _run_resume_upload_pipeline(
        session: AsyncSession,
        user_id: uuid.UUID,
        extraction_id: uuid.UUID,
        raw: bytes,
        suffix: str,
    ) -> ResumeUploadResponse:
        """The actual upload pipeline — extracted so it can run inside-or-outside
        a Langfuse trace context without code duplication. Caller wraps in
        `with lf.start_as_current_observation(name='resume_upload', ...)` when
        Langfuse is enabled."""
        lf = get_langfuse_client()  # already inside the parent context if any

        # ---- text_extract span (D-32 #1) ----
        text_extract_start = time.perf_counter()
        page_count: int | None = None
        try:
            if suffix == ".pdf":
                resume_text = await asyncio.to_thread(_extract_pdf_text, raw)
                file_type = "pdf"
                page_count = _pdf_page_count(raw)
            else:  # .docx
                resume_text = await asyncio.to_thread(_extract_docx_text, raw)
                file_type = "docx"
        except pypdf.errors.PdfReadError:
            log.warning("resume_upload_failed", reason="pdf_encrypted")
            raise HTTPException(
                status_code=422,
                detail={"reason": "pdf_encrypted",
                        "message": "Remove the password and try again."},
            ) from None
        except Exception:
            log.exception("resume_upload_failed", reason="text_extraction_failed")
            raise HTTPException(
                status_code=422,
                detail={"reason": "text_extraction_failed",
                        "message": "Could not read the file."},
            ) from None
        text_extract_ms = int((time.perf_counter() - text_extract_start) * 1000)

        if len(resume_text.strip()) < 100:
            log.warning("resume_upload_failed", reason="text_extraction_failed",
                        char_count=len(resume_text.strip()))
            raise HTTPException(
                status_code=422,
                detail={"reason": "text_extraction_failed",
                        "message": "The file appears to be a scanned image. v1 doesn't support OCR."},
            )

        # D-11: cap text at 50 KB pre-LLM.
        if len(resume_text) > 50_000:
            log.warning("resume_text_truncated",
                        original_chars=len(resume_text), truncated_chars=50_000)
            resume_text = resume_text[:50_000]

        if lf:
            # T-07-07: metadata only — NO raw text. v4 emits as a child span of
            # the parent resume_upload context.
            try:
                with lf.start_as_current_observation(
                    name="text_extract",
                    as_type="span",
                    metadata={
                        "file_type": file_type,
                        "char_count": len(resume_text),
                        "page_count": page_count,
                        "latency_ms": text_extract_ms,
                    },
                ):
                    pass
            except Exception:  # pragma: no cover - fail-open per T-07-08
                pass

        # ---- LLM extraction (auto-captured by langfuse.openai as a child GENERATION) ----
        try:
            extraction, _usage_info = await asyncio.to_thread(extract_resume, resume_text)
        except ValidationError:
            log.exception("resume_extraction_failed", attempts=3)
            raise HTTPException(
                status_code=422,
                detail={"reason": "extraction_failed",
                        "message": "The agent could not parse the resume. Try again or simplify the formatting."},
            ) from None
        except openai.APIError:
            log.exception("resume_upload_failed", reason="llm_unavailable")
            raise HTTPException(
                status_code=503,
                detail={"reason": "llm_unavailable",
                        "message": "The LLM is down. Try again later."},
            ) from None

        if not extraction.skills:
            raise HTTPException(
                status_code=422,
                detail={"reason": "empty_skills",
                        "message": "No skills found. Is this a resume?"},
            )

        # PII redaction on auto-captured GENERATION + trace root (D-33 / T-07-07).
        # Must happen INSIDE the parent resume_upload context so the
        # update_current_generation call targets the LLM child observation.
        if lf:
            redact_current_generation_input(lf, char_count=len(resume_text))

        # ---- diff_compute span (D-32 #3) ----
        diff_start = time.perf_counter()
        current = await load_profile(session, user_id=user_id)
        skills_diff = compute_skills_diff(current, extraction.skills)
        diff_ms = int((time.perf_counter() - diff_start) * 1000)

        if lf:
            try:
                with lf.start_as_current_observation(
                    name="diff_compute",
                    as_type="span",
                    metadata={
                        "added_count": sum(1 for d in skills_diff if d.source == "added"),
                        "removed_count": sum(1 for d in skills_diff if d.source == "removed"),
                        "unchanged_count": sum(1 for d in skills_diff if d.source == "unchanged"),
                        "latency_ms": diff_ms,
                    },
                ):
                    pass
            except Exception:  # pragma: no cover - fail-open per T-07-08
                pass

        log.info("resume_skills_extracted",
                 skills_count=len(extraction.skills),
                 added=sum(1 for d in skills_diff if d.source == "added"))

        return ResumeUploadResponse(
            extracted=extraction,
            skills_diff=skills_diff,
            prompt_version=RESUME_PROMPT_VERSION,
            extraction_id=extraction_id,
        )
    ```

    Step 3 — Rewrite the public `upload_resume` handler to: (a) read the raw bytes
    with the existing chunked-encoding guard (keep that block unchanged), (b)
    set up the parent trace via `start_as_current_observation` when Langfuse is
    enabled, (c) call `_run_resume_upload_pipeline` inside the with-block:

    ```python
    @router.post(
        "/profile/upload",
        dependencies=[Depends(require_api_key), Depends(standard_limit)],
        response_model=ResumeUploadResponse,
    )
    async def upload_resume(
        file: UploadFile,
        session: Session,
        user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    ) -> ResumeUploadResponse:
        """POST /profile/upload — PDF/DOCX → Instructor extraction → skill diff.

        Phase 7 D-06..D-35 + T-07-02/05/07/08 + G-07-UAT-01 (Langfuse v4 migration):
        - 2 MB cap pre-body via ResumeUploadSizeGuard + chunked fallback.
        - Type whitelist = extension AND Content-Type (D-08); 415 otherwise.
        - Errors map to D-35 reason taxonomy.
        - Langfuse trace correlates 4 child observations under a single
          `resume_upload` parent span keyed by `derive_langfuse_trace_id(extraction_id)`
          (D-32, post-G-07-UAT-01 v4 migration).
        - Raw resume text NEVER reaches Langfuse — redact_current_generation_input
          overrides BOTH the auto-captured generation input AND the trace-level
          input (D-33).
        """
        extraction_id = uuid.uuid4()

        # ---- Type whitelist (D-08, T-07-05) ----
        # [...] EXISTING type-whitelist block 1:1 unchanged [...]

        # ---- Chunked-encoding fallback for D-07 (no Content-Length header) ----
        # [...] EXISTING chunked-read block 1:1 unchanged, produces `raw` and `suffix` [...]

        lf = get_langfuse_client()
        if lf is None:
            return await _run_resume_upload_pipeline(
                session, user_id, extraction_id, raw, suffix
            )

        # Langfuse enabled — wrap the pipeline in a `resume_upload` parent span.
        trace_id = derive_langfuse_trace_id(extraction_id)
        try:
            with lf.start_as_current_observation(
                name="resume_upload",
                as_type="span",
                trace_context={"trace_id": trace_id},
                metadata={
                    "extraction_id": str(extraction_id),
                    "user_id": str(user_id),
                    "phase": "7",
                    "tags": ["resume", "phase-7"],
                },
            ):
                return await _run_resume_upload_pipeline(
                    session, user_id, extraction_id, raw, suffix
                )
        except HTTPException:
            # Re-raise FastAPI errors verbatim (don't be swallowed by the
            # fail-open guard — they must reach the client).
            raise
        except Exception:  # pragma: no cover - fail-open per T-07-08
            log.exception("langfuse_trace_setup_failed", extraction_id=str(extraction_id))
            return await _run_resume_upload_pipeline(
                session, user_id, extraction_id, raw, suffix
            )
    ```

    Step 4 — Rewrite the `update_profile` (`PATCH /profile`) tracing block. Keep the SQL
    update unchanged; replace the trailing trace block:

    ```python
    # ---- profile_save span (D-32 #4) ----
    # Re-derives the same trace_id from the same extraction_id seed so this
    # span attaches to the SAME trace as the original POST /profile/upload.
    lf = get_langfuse_client()
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
        except Exception:  # pragma: no cover - fail-open per T-07-08
            log.warning("langfuse_profile_save_span_failed",
                        extraction_id=str(payload.extraction_id))
    ```

    Step 5 — Verify the rewrite:

    ```bash
    grep -nE "lf\.trace\(|trace\.span\(|update_current_observation\(" src/job_rag/api/routes.py
    # Expect: 0 matches
    grep -nE "start_as_current_observation" src/job_rag/api/routes.py
    # Expect: ≥4 matches (resume_upload, text_extract, diff_compute, profile_save)
    uv run pyright src/job_rag/api/routes.py
    # Expect: 0 errors
    uv run pytest tests/test_profile.py tests/test_resume_extractor.py -x
    # Expect: 22 passed (no regression)
    ```
  </action>
  <verify>
    <automated>bash -c 'set -e; grep -qE "start_as_current_observation\(name=.resume_upload" src/job_rag/api/routes.py; grep -qE "start_as_current_observation\(name=.text_extract" src/job_rag/api/routes.py; grep -qE "start_as_current_observation\(name=.diff_compute" src/job_rag/api/routes.py; grep -qE "start_as_current_observation\(name=.profile_save" src/job_rag/api/routes.py; ! grep -qE "lf\.trace\(|trace\.span\(|update_current_observation\(" src/job_rag/api/routes.py; uv run pyright src/job_rag/api/routes.py; uv run pytest tests/test_profile.py tests/test_resume_extractor.py -x'</automated>
  </verify>
  <done>
    - `routes.py` contains 4 `start_as_current_observation(name=...)` call sites named `resume_upload`, `text_extract`, `diff_compute`, `profile_save`.
    - `routes.py` contains exactly 0 occurrences of `lf.trace(`, `trace.span(`, or `update_current_observation(` (regex match, case-sensitive).
    - `routes.py` calls `redact_current_generation_input(lf, char_count=len(resume_text))` exactly once, IMMEDIATELY after the `await asyncio.to_thread(extract_resume, resume_text)` line.
    - `tests/test_profile.py` + `tests/test_resume_extractor.py` (22 tests) still pass with zero changes to those test files.
    - `uv run pyright src/job_rag/api/routes.py` returns 0 errors, 0 warnings.
    - Manual visual confirmation: the parent `with lf.start_as_current_observation(name="resume_upload", ...)` block encloses BOTH the text-extract and the `await asyncio.to_thread(extract_resume, ...)` call so the langfuse.openai auto-GENERATION lands as a child.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Replace Mock-based Langfuse tests with FakeLangfuseClient integration tests</name>
  <files>tests/test_observability.py</files>
  <behavior>
    The 4 tests below replace the existing 3 Phase-7 Langfuse tests (currently at
    `tests/test_observability.py:100-272`). They MUST hold the same contract those
    tests intended to verify, but using `FakeLangfuseClient` so that any future v3
    method-name regression fails CI.

    Test A — `TestResumeUploadV4Tracing::test_post_upload_records_three_child_observations`:
      - Patch `job_rag.api.routes.get_langfuse_client` to return a fresh `FakeLangfuseClient()`.
      - Patch `load_profile` to return `UserSkillProfile(skills=[])`.
      - Patch `extract_resume` to return `(_fake_extraction(), {})`.
      - POST /profile/upload with `sample_resume_pdf`.
      - Assert response 200, extract `extraction_id` from the body.
      - Assert `fake.span_names_recorded() == ["resume_upload", "text_extract", "diff_compute"]`
        (NO `llm_extract` — that's auto-captured by langfuse.openai which the fake doesn't
        simulate; the auto-capture is verified by Test C against a real client at integration
        level).
      - Assert the FIRST `enter_observation` event has `trace_id == derive_langfuse_trace_id(extraction_id)`.

    Test B — `TestResumeUploadV4Tracing::test_post_then_patch_share_trace_id`:
      - Same setup as Test A.
      - POST /profile/upload → capture `extraction_id`.
      - PATCH /profile with `{"skills": [{"name": "Python"}], "extraction_id": extraction_id}`.
      - Assert the fake recorded an `enter_observation` for `profile_save` whose `trace_id`
        EQUALS the `resume_upload` enter_observation's `trace_id` (proves correlation works
        via the deterministic `create_trace_id(seed=...)` mechanism).

    Test C — `TestResumeUploadV4Tracing::test_no_resume_pii_in_recorded_payloads`:
      - Same setup; use `sample_resume_pdf` (the synthetic fixture contains the
        watermark strings `"TEST FIXTURE"` and `"synthetic data"`).
      - POST /profile/upload.
      - Iterate `fake.all_recorded_inputs()` (every input/output/metadata payload across
        every recorded call).
      - For each payload (str or nested dict/list of strs), assert NEITHER `"TEST FIXTURE"`
        NOR `"synthetic data"` appears anywhere.
      - Also assert that the fake recorded a `set_current_trace_io` call with input
        containing `"[REDACTED — char_count="`.
      - Also assert that the fake recorded a `update_current_generation` call with input
        containing `"[REDACTED — char_count="`.

    Test D — `TestResumeUploadV4Tracing::test_v3_method_calls_would_fail_loudly`:
      - SDK-regression guard. Build a `FakeLangfuseClient`.
      - Assert `pytest.raises(AttributeError, match="v3 API removed")` when calling
        `fake.trace(name="x")`.
      - Assert `pytest.raises(AttributeError, match="v3 API removed")` when calling
        `fake.update_current_observation(input={})`.
      - This test PROVES that if a developer accidentally writes `lf.trace(...)` in
        future code AND the production code paths it under a real `FakeLangfuseClient`
        in tests, the test suite catches the regression — fixing the why-tests-passed
        gap that let G-07-UAT-01 ship.

    Test E — `TestResumeUploadV4Tracing::test_fail_open_when_langfuse_disabled` (rewritten):
      - Patch `observability.settings.langfuse_public_key` and `..._secret_key` to empty.
      - Clear the `get_langfuse_client.cache_clear()`.
      - POST /profile/upload (with `load_profile` + `extract_resume` patched as above).
      - Assert 200; assert response contains a valid UUID `extraction_id`.
      - Confirm no AttributeError, no traceback in caplog.

    Tests that get DELETED (per "Out of scope" — old Mock-based tests):
      - `test_resume_upload_trace_has_four_spans` (uses `mock_lf.trace.return_value`).
      - `test_resume_trace_does_not_capture_text` (uses `mock_trace.span.call_args_list`).
      - `test_langfuse_fail_open_when_keys_missing` — REWRITTEN as Test E above.
  </behavior>
  <read_first>
    - tests/test_observability.py lines 56-273 — the existing Phase-7 block that gets
      DROPPED and REPLACED. Preserve the lines 1-55 (the pre-Phase-7 tests on is_enabled,
      get_openai_client, get_langchain_callbacks, flush) verbatim.
    - tests/_langfuse_fake.py (post-Task-1) — confirm `FakeLangfuseClient` is importable.
    - tests/conftest.py — confirm `sample_resume_pdf` fixture path + content.
  </read_first>
  <action>
    Step 1 — Delete the existing Phase-7 block in `tests/test_observability.py`
    (lines 56-273 inclusive of the original file — the section that starts with
    `# Phase 7: resume_upload trace tests (Plan 04 — D-32 / D-33 / T-07-07 / T-07-08)`
    through the end of `test_langfuse_fail_open_when_keys_missing`). Keep the
    pre-Phase-7 block (lines 1-55) intact: `TestIsEnabled`, `TestGetOpenAIClient`,
    `TestGetLangchainCallbacks`, `TestFlush`.

    Step 2 — Append the new Phase-7 block. Include the 4 tests TestA..TestE above
    plus the 3 helper tests from Task 1's behaviour spec (TestDeriveLangfuseTraceId,
    TestRedactCurrentGenerationInput, TestFakeLangfuseClient) if they aren't already
    present. The full new block looks like this:

    ```python
    # Phase 7 G-07-UAT-01: Langfuse SDK v4 migration tests.
    #
    # Replaces the Mock-based tests that let G-07-UAT-01 ship: a MagicMock()
    # accepts any method call without raising, so `lf.trace(...)` calls looked
    # fine in tests but raised AttributeError on the installed Langfuse 4.x
    # client. The FakeLangfuseClient below implements the v4 contract surface
    # explicitly and raises AttributeError on every known v3 method name.


    import uuid  # noqa: E402
    from unittest.mock import AsyncMock, patch  # noqa: E402

    import pytest  # noqa: E402
    from httpx import ASGITransport, AsyncClient  # noqa: E402

    from job_rag.api.app import app  # noqa: E402
    from job_rag.models import (  # noqa: E402
        RemotePolicy,
        ResumeExtraction,
        UserSkill,
        UserSkillProfile,
    )
    from job_rag.observability import derive_langfuse_trace_id  # noqa: E402
    from tests._langfuse_fake import FakeLangfuseClient  # noqa: E402


    def _fake_extraction() -> ResumeExtraction:
        return ResumeExtraction(
            skills=[UserSkill(name="Python"), UserSkill(name="Rust")],
            target_roles=["AI Engineer"],
            preferred_locations=["Berlin"],
            min_salary_eur=70000,
            remote_preference=RemotePolicy.REMOTE,
            years_experience=5,
        )


    def _override_session_user():
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings as _settings

        async def override_session():
            yield AsyncMock()

        async def override_user():
            return _settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user


    class TestDeriveLangfuseTraceId:
        def test_deterministic_for_same_seed(self):
            seed = uuid.UUID("11111111-1111-1111-1111-111111111111")
            id1 = derive_langfuse_trace_id(seed)
            id2 = derive_langfuse_trace_id(seed)
            assert id1 == id2
            assert len(id1) == 32
            assert all(c in "0123456789abcdef" for c in id1)

        def test_different_for_different_seeds(self):
            a = derive_langfuse_trace_id(uuid.UUID("11111111-1111-1111-1111-111111111111"))
            b = derive_langfuse_trace_id(uuid.UUID("22222222-2222-2222-2222-222222222222"))
            assert a != b


    class TestRedactCurrentGenerationInput:
        def test_calls_both_update_and_set_trace_io(self):
            from job_rag.observability import redact_current_generation_input
            fake = FakeLangfuseClient()
            redact_current_generation_input(fake, char_count=42)
            gens = [k for m, k in fake.calls if m == "update_current_generation"]
            traces = [k for m, k in fake.calls if m == "set_current_trace_io"]
            assert len(gens) == 1
            assert len(traces) == 1
            assert gens[0]["input"] == {"text": "[REDACTED — char_count=42]"}
            assert traces[0]["input"] == {"text": "[REDACTED — char_count=42]"}

        def test_fail_open_when_client_raises(self):
            from job_rag.observability import redact_current_generation_input
            fake = FakeLangfuseClient(raise_on={
                "update_current_generation": RuntimeError("boom"),
            })
            # Must NOT raise:
            redact_current_generation_input(fake, char_count=99)
            # Trace-level write still attempted:
            traces = [k for m, k in fake.calls if m == "set_current_trace_io"]
            assert len(traces) == 1


    class TestFakeLangfuseClient:
        def test_v3_method_names_raise_attributeerror(self):
            fake = FakeLangfuseClient()
            with pytest.raises(AttributeError, match="v3 API removed"):
                fake.trace(name="x")
            with pytest.raises(AttributeError, match="v3 API removed"):
                fake.update_current_observation(input={})

        def test_records_start_as_current_observation_calls(self):
            fake = FakeLangfuseClient()
            with fake.start_as_current_observation(
                name="foo", as_type="span",
                trace_context={"trace_id": "deadbeef" * 4},
                metadata={"x": 1},
            ):
                pass
            assert fake.span_names_recorded() == ["foo"]
            enter = next(k for m, k in fake.calls if m == "enter_observation")
            assert enter["trace_id"] == "deadbeef" * 4
            assert enter["metadata"] == {"x": 1}


    class TestResumeUploadV4Tracing:
        @pytest.mark.asyncio
        async def test_post_upload_records_three_child_observations(self, sample_resume_pdf):
            _override_session_user()
            fake = FakeLangfuseClient()
            try:
                with patch(
                    "job_rag.api.routes.get_langfuse_client", return_value=fake
                ), patch(
                    "job_rag.api.routes.load_profile",
                    new_callable=AsyncMock,
                    return_value=UserSkillProfile(skills=[]),
                ), patch(
                    "job_rag.api.routes.extract_resume",
                    return_value=(_fake_extraction(), {}),
                ):
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.post(
                            "/profile/upload",
                            files={"file": ("test.pdf", sample_resume_pdf, "application/pdf")},
                        )
                assert resp.status_code == 200, resp.text
                extraction_id = uuid.UUID(resp.json()["extraction_id"])
                names = fake.span_names_recorded()
                assert names == ["resume_upload", "text_extract", "diff_compute"], names
                first_enter = next(k for m, k in fake.calls if m == "enter_observation")
                assert first_enter["trace_id"] == derive_langfuse_trace_id(extraction_id)
            finally:
                app.dependency_overrides.clear()

        @pytest.mark.asyncio
        async def test_post_then_patch_share_trace_id(self, sample_resume_pdf):
            _override_session_user()
            fake = FakeLangfuseClient()
            try:
                with patch(
                    "job_rag.api.routes.get_langfuse_client", return_value=fake
                ), patch(
                    "job_rag.api.routes.load_profile",
                    new_callable=AsyncMock,
                    return_value=UserSkillProfile(skills=[]),
                ), patch(
                    "job_rag.api.routes.extract_resume",
                    return_value=(_fake_extraction(), {}),
                ):
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.post(
                            "/profile/upload",
                            files={"file": ("test.pdf", sample_resume_pdf, "application/pdf")},
                        )
                        assert resp.status_code == 200, resp.text
                        eid = resp.json()["extraction_id"]
                        r2 = await client.patch(
                            "/profile",
                            json={"skills": [{"name": "Python"}], "extraction_id": eid},
                        )
                        assert r2.status_code == 200, r2.text
                upload_root = next(
                    k for m, k in fake.calls
                    if m == "enter_observation" and k["name"] == "resume_upload"
                )
                save_span = next(
                    k for m, k in fake.calls
                    if m == "enter_observation" and k["name"] == "profile_save"
                )
                assert upload_root["trace_id"] == save_span["trace_id"]
            finally:
                app.dependency_overrides.clear()

        @pytest.mark.asyncio
        async def test_no_resume_pii_in_recorded_payloads(self, sample_resume_pdf):
            """T-07-07 + G-07-UAT-01 regression: raw resume bytes ('TEST FIXTURE'
            / 'synthetic data' watermarks) must NEVER appear in any recorded
            input/output/metadata. The redact_current_generation_input helper must
            ALSO have written the [REDACTED] marker to both generation input and
            trace-level input."""
            _override_session_user()
            fake = FakeLangfuseClient()
            try:
                with patch(
                    "job_rag.api.routes.get_langfuse_client", return_value=fake
                ), patch(
                    "job_rag.api.routes.load_profile",
                    new_callable=AsyncMock,
                    return_value=UserSkillProfile(skills=[]),
                ), patch(
                    "job_rag.api.routes.extract_resume",
                    return_value=(_fake_extraction(), {}),
                ):
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.post(
                            "/profile/upload",
                            files={"file": ("test.pdf", sample_resume_pdf, "application/pdf")},
                        )
                assert resp.status_code == 200, resp.text

                def _flatten(obj):
                    if isinstance(obj, str):
                        yield obj
                    elif isinstance(obj, dict):
                        for v in obj.values():
                            yield from _flatten(v)
                    elif isinstance(obj, (list, tuple)):
                        for v in obj:
                            yield from _flatten(v)

                for payload in fake.all_recorded_inputs():
                    for s in _flatten(payload):
                        assert "TEST FIXTURE" not in s, f"PII leaked: {s!r}"
                        assert "synthetic data" not in s, f"PII leaked: {s!r}"

                # And the redaction helper DID overwrite both layers:
                gen_inputs = [
                    k["input"]
                    for m, k in fake.calls
                    if m == "update_current_generation" and "input" in k
                ]
                trace_inputs = [
                    k["input"]
                    for m, k in fake.calls
                    if m == "set_current_trace_io" and "input" in k
                ]
                assert any(
                    isinstance(i, dict) and "[REDACTED — char_count=" in i.get("text", "")
                    for i in gen_inputs
                ), gen_inputs
                assert any(
                    isinstance(i, dict) and "[REDACTED — char_count=" in i.get("text", "")
                    for i in trace_inputs
                ), trace_inputs
            finally:
                app.dependency_overrides.clear()

        @pytest.mark.asyncio
        async def test_v3_method_calls_would_fail_loudly(self):
            """SDK-regression guard. If a future PR writes `lf.trace(...)` in
            production code AND the test uses FakeLangfuseClient, the test
            suite catches it — fixing the why-tests-passed gap that let
            G-07-UAT-01 ship."""
            fake = FakeLangfuseClient()
            with pytest.raises(AttributeError, match="v3 API removed"):
                fake.trace(name="resume_upload")
            with pytest.raises(AttributeError, match="v3 API removed"):
                fake.update_current_observation(input={"redacted": True})

        @pytest.mark.asyncio
        async def test_fail_open_when_langfuse_disabled(self, sample_resume_pdf, monkeypatch):
            """T-07-08: missing keys leave the upload functional, no exception."""
            _override_session_user()
            monkeypatch.setattr(observability.settings, "langfuse_public_key", "")
            monkeypatch.setattr(observability.settings, "langfuse_secret_key", "")
            observability.get_langfuse_client.cache_clear()
            try:
                with patch(
                    "job_rag.api.routes.load_profile",
                    new_callable=AsyncMock,
                    return_value=UserSkillProfile(skills=[]),
                ), patch(
                    "job_rag.api.routes.extract_resume",
                    return_value=(_fake_extraction(), {}),
                ):
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.post(
                            "/profile/upload",
                            files={"file": ("test.pdf", sample_resume_pdf, "application/pdf")},
                        )
                assert resp.status_code == 200, resp.text
                uuid.UUID(resp.json()["extraction_id"])
            finally:
                app.dependency_overrides.clear()
                observability.get_langfuse_client.cache_clear()
    ```

    Step 3 — Run the full test_observability.py module + the upload integration tests:

    ```bash
    uv run pytest tests/test_observability.py -x -v
    uv run pytest tests/test_profile.py tests/test_resume_extractor.py -x
    ```

    Both must be green. The old `mock_lf.trace.return_value` patterns are gone;
    `grep -nE "mock_lf\.trace|mock_trace\.span" tests/test_observability.py` returns 0 matches.
  </action>
  <verify>
    <automated>bash -c 'set -e; uv run pytest tests/test_observability.py -x -v; uv run pytest tests/test_profile.py tests/test_resume_extractor.py -x; ! grep -nE "mock_lf\.trace|mock_trace\.span" tests/test_observability.py; grep -q "FakeLangfuseClient" tests/test_observability.py; grep -q "TestResumeUploadV4Tracing" tests/test_observability.py'</automated>
  </verify>
  <done>
    - `tests/test_observability.py` contains a `TestResumeUploadV4Tracing` class with the 5 tests above plus 3 helper-test classes (TestDeriveLangfuseTraceId, TestRedactCurrentGenerationInput, TestFakeLangfuseClient).
    - `grep "FakeLangfuseClient" tests/test_observability.py` returns matches; `grep -E "mock_lf\\.trace|mock_trace\\.span" tests/test_observability.py` returns 0 matches.
    - The full `tests/test_observability.py` test module passes under `uv run pytest tests/test_observability.py -x -v`.
    - `tests/test_profile.py` + `tests/test_resume_extractor.py` (22 tests) still pass — no regression from Task 2's routes.py rewrite.
    - The full backend suite `uv run pytest -x` passes (or only fails on the pre-documented `test_0005_upgrade_populates_oid_when_env_set` per `deferred-items.md` — not introduced by this plan).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| `routes.py` → `langfuse.Langfuse` 4.x SDK | Production code calls an external observability library; method-name drift breaks tracing silently due to T-07-08 fail-open guards |
| `routes.py` → `langfuse.openai` wrapper | Wrapper auto-captures the LLM call's INPUT (the resume text). Without explicit redaction, PII leaves the process into a third-party SaaS |
| `tests/_langfuse_fake.py` → production code | The fake mirrors the v4 contract; if the fake drifts from the real SDK, the regression-guard test loses fidelity |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-UAT-01.A | Information Disclosure | `langfuse.openai` auto-captured GENERATION's `input` field | mitigate | `redact_current_generation_input(lf, char_count=len(resume_text))` called immediately after the LLM call returns, overriding the input on BOTH the GENERATION observation AND the trace root (`set_current_trace_io`). Verified by `TestResumeUploadV4Tracing::test_no_resume_pii_in_recorded_payloads`. |
| T-07-UAT-01.B | Tampering / Repudiation | Manual spans (`text_extract`, `diff_compute`, `profile_save`) silently dropping if the SDK API drifts again | mitigate | `FakeLangfuseClient` raises `AttributeError` on every v3 method name. `TestResumeUploadV4Tracing::test_v3_method_calls_would_fail_loudly` proves the guard works. Future SDK changes that break the contract surface fail CI loudly rather than silently no-op. |
| T-07-UAT-01.C | Denial of Service | A bug in Langfuse SDK 4.x raising an exception during `start_as_current_observation` breaks the upload endpoint | mitigate | The outer `try/except Exception:` in the `upload_resume` handler around the `with lf.start_as_current_observation(...)` block falls back to running `_run_resume_upload_pipeline` WITHOUT the parent span (still without tracing, but the upload succeeds). T-07-08 fail-open contract preserved end-to-end. |
| T-07-UAT-01.D | Information Disclosure | `trace_context.trace_id` derived from `extraction_id` is deterministic — an adversary who can guess `extraction_id` could craft a synthetic Langfuse query that joins their span data into a real user's trace | accept | `extraction_id` is `uuid.uuid4()` — 122 bits of entropy. Adversarial trace pollution requires Langfuse API credentials AND brute-forcing the UUID, both of which are higher-cost than the v1 single-user threat model warrants. Not in scope for ASVS L1. |
</threat_model>

<verification>
After all 3 tasks complete, run the full verification sequence:

```bash
# 1. Static check: no v3 API anywhere in production code.
! grep -rnE "lf\.trace\(|trace\.span\(|update_current_observation\(" src/

# 2. Static check: production code uses v4 API.
grep -E "start_as_current_observation\(name=.(resume_upload|text_extract|diff_compute|profile_save)." src/job_rag/api/routes.py

# 3. Static check: PII redaction helper invoked.
grep -E "redact_current_generation_input\(lf" src/job_rag/api/routes.py

# 4. Pyright clean across the touched files.
uv run pyright src/job_rag/observability.py src/job_rag/api/routes.py tests/_langfuse_fake.py tests/test_observability.py

# 5. Targeted test runs.
uv run pytest tests/test_observability.py -x -v
uv run pytest tests/test_profile.py tests/test_resume_extractor.py -x

# 6. Full backend suite (no regressions).
uv run pytest --ignore=tests/test_alembic.py -x   # alembic seed test is PG-gated; skip when local DB not running

# 7. Manual UAT replay (Adrian, post-merge):
#    a. With LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY set, upload a 1.5 MB PDF
#       via the running UI.
#    b. Open the Langfuse dashboard; find the most recent trace.
#    c. Confirm: trace contains a parent span named "resume_upload" with the
#       metadata.extraction_id field set, 2 explicit child spans (text_extract,
#       diff_compute), and 1 auto-captured GENERATION child (OpenAI-generation
#       or similar — the langfuse.openai wrapper's default name).
#    d. PATCH the profile via the Save button; the same trace gains a
#       profile_save child span.
#    e. Confirm: NEITHER the trace root input NOR the generation child input
#       contains Adrian's name, email, phone, LinkedIn, GitHub, or address.
#       The text "[REDACTED — char_count=N]" should appear in their place.
```
</verification>

<success_criteria>
- All 5 explicit v3 API call sites in `src/job_rag/api/routes.py` are rewritten using `start_as_current_observation` + `update_current_generation` + `set_current_trace_io`; ZERO `lf.trace(`, `trace.span(`, or `update_current_observation(` remain anywhere under `src/`.
- A live Langfuse 4.1.0 client receiving a real upload produces a single trace whose root span is `resume_upload` (keyed by `derive_langfuse_trace_id(extraction_id)`) with 3 explicit child spans (`text_extract`, `diff_compute`, plus `profile_save` after PATCH) and 1 auto-captured GENERATION child.
- Both the GENERATION's `input` AND the trace-level `input` contain the literal string `"[REDACTED — char_count=N]"` instead of raw resume text — verified at unit-test level via `FakeLangfuseClient` AND at manual UAT level via the Langfuse dashboard.
- A new `tests/test_observability.py::TestResumeUploadV4Tracing` class with 5 tests passes; the `FakeLangfuseClient` in `tests/_langfuse_fake.py` is contract-faithful to v4 AND raises AttributeError on every v3 method name (regression guard).
- T-07-08 fail-open preserved: with `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` unset, `POST /profile/upload` + `PATCH /profile` return 200 normally with no traceback.
- All 22 existing Phase 7 backend tests (`test_profile.py` + `test_resume_extractor.py`) continue to pass with zero modification — proves the rewrite is behaviour-preserving outside the trace contract.
- After execution, `.planning/phases/07-profile-resume-upload/07-HUMAN-UAT.md` Test 1 can be re-run by Adrian and PASS (single trace per upload with 4 spans, no PII).
</success_criteria>

<output>
After completion, create `.planning/phases/07-profile-resume-upload/07-06-langfuse-sdk-v4-migration-SUMMARY.md` documenting:
- The 5 v3 → v4 API mappings with before/after snippets.
- The exact char-count of `routes.py` diff and `observability.py` diff for tracking.
- The 5 new tests in `TestResumeUploadV4Tracing` and what each one proves.
- The `FakeLangfuseClient` design rationale (contract-faithful fake vs Mock) and how it closes the why-tests-passed gap.
- A pointer to Adrian's post-merge live-UAT replay step for closing G-07-UAT-01 in `07-VERIFICATION.md`.
</output>
