---
status: partial
phase: 07-profile-resume-upload
source: [07-VERIFICATION.md]
started: 2026-05-28T13:50:00Z
updated: 2026-05-29T00:00:00Z
---

## Current Test

[Test 1 failed — gap closure triggered; remaining tests deferred until fix lands]

## Tests

### 1. Langfuse trace rendering (M-marker 3)
expected: Single Langfuse trace per upload spanning extraction → Instructor → diff → PATCH; 4 spans (text_extract, llm_extract auto, diff_compute, profile_save) correlated by extraction_id; raw resume text NOT visible in any span input/metadata
result: failed
evidence: Live Langfuse export `trace-c744bb2d0683a35da965946940e70bab.json` from Adrian's first real upload showed (a) a single standalone GENERATION trace named `OpenAI-generation` with no `extraction_id` correlation, and (b) the full unredacted resume in `trace.input` — name, email, phone +49 174 608 8033, LinkedIn URL, GitHub URL, address, full skills list. Manual spans `text_extract`, `diff_compute`, `profile_save` are completely absent.
root_cause: Phase 7 code (`src/job_rag/api/routes.py:687,756,804,817,897` + `src/job_rag/observability.py`) calls the Langfuse SDK 3.x API (`lf.trace()`, `trace.span().end()`, `lf.update_current_observation()`). Installed SDK is **4.1.0** (OTel-based rewrite) where these methods do not exist. Every call raises `AttributeError`, gets swallowed by the T-07-08 `try/except Exception: pass` fail-open guards, and the manual spans + PII redaction silently never happen. Only `langfuse.openai` auto-instrumentation (which speaks v4 correctly) survives — hence the lone `OpenAI-generation` trace.
why_tests_passed: `tests/test_observability.py` mocks `get_langfuse_client()`. The mock accepts any method call without raising, so tests verified intent (`.trace.called_with(...)`) rather than SDK compatibility. Live UAT was the first contact with a real Langfuse 4.x client.

### 2. Dashboard CV-vs-market refresh after save
expected: Dashboard widget reflects the new skill list within one re-render (TanStack cache invalidation propagates from save → dashboard)
result: [pending]

### 3. Pre-body 413 on >2 MB upload
expected: 413 response returned BEFORE the full body is uploaded (Content-Length-based reject); body bytes transmitted < 2 MB cap (observe in browser DevTools Network panel)
result: [pending]

### 4. Cold-start stepped status copy
expected: Copy transitions 0-2s "Reading…" → 2-10s "Asking the agent…" → 10s+ "Still working…" per D-31; requires real cold-start latency (set ACA min-replicas=0 + idle 5 min)
result: [pending]

### 5. Inline-edit rename persistence
expected: Renamed skill on an added chip appears in ProfileView Badge list after refresh — proves the edited name persists through PATCH round-trip
result: [pending]

## Summary

total: 5
passed: 0
issues: 1
pending: 4
skipped: 0
blocked: 0

## Gaps

### G-07-UAT-01: Langfuse SDK 3.x → 4.x migration (PROF-06 trace contract broken)
status: failed
source_test: 1
severity: blocking
scope: backend
evidence:
  - file: trace-c744bb2d0683a35da965946940e70bab.json
    finding: "Single standalone GENERATION trace; no parent `resume_upload` trace; no extraction_id; manual spans absent"
  - file: trace-c744bb2d0683a35da965946940e70bab.json
    finding: "Full unredacted resume PII in trace.input — name, email, phone, LinkedIn, GitHub, address"
affected_files:
  - src/job_rag/api/routes.py:687
  - src/job_rag/api/routes.py:756
  - src/job_rag/api/routes.py:804
  - src/job_rag/api/routes.py:817
  - src/job_rag/api/routes.py:897
  - src/job_rag/observability.py
  - tests/test_observability.py
affected_requirements:
  - PROF-06 (Langfuse trace + redaction half)
fix_summary: |
  Rewrite the 5 backend Langfuse call sites using the SDK 4.x OTel-based API
  (`langfuse.start_as_current_span(...)`, `span.update(...)`, proper PII
  redaction at the OpenAI wrapper layer). Cross-request `extraction_id`
  correlation needs to use `langfuse.create_trace_id()` + parent context
  propagation (or accept that POST and PATCH each get their own trace but
  share the `extraction_id` as metadata/tag for join in dashboard queries).
  Replace the mocked-client unit tests with an integration test that hits a
  real Langfuse client (or a contract-faithful fake) so SDK version mismatches
  can't regress silently.
recommended_research:
  - Langfuse Python SDK 4.x migration guide (https://langfuse.com/docs/sdk/python/sdk-v3 → v4 migration)
  - OpenTelemetry span hierarchy semantics for cross-request correlation
  - langfuse.openai wrapper input/output transformation hooks for PII redaction
