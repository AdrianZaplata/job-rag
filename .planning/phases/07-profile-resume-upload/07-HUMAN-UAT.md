---
status: partial
phase: 07-profile-resume-upload
source: [07-VERIFICATION.md]
started: 2026-05-28T13:50:00Z
updated: 2026-05-30T16:30:00Z
---

## Current Test

[Test 1 re-runnable after Plan 07-06 gap closure — Tests 1-5 awaiting Adrian's manual replay]

## Tests

### 1. Langfuse trace rendering (M-marker 3)
expected: Single Langfuse trace per upload spanning extraction → Instructor → diff → PATCH; 4 spans (text_extract, llm_extract auto, diff_compute, profile_save) correlated by extraction_id; raw resume text NOT visible in any span input/metadata
result: pending
re_run_after: Plan 07-06 closed G-07-UAT-01 at code level (commits ad31379, 3ffc244, 82bb8d5). Adrian must replay the live UAT with `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` set, upload a 1.5 MB PDF via the deployed UI, and confirm in the Langfuse dashboard: (a) single trace with parent `resume_upload` span keyed by `derive_langfuse_trace_id(extraction_id)`, (b) 3 explicit child spans (`text_extract`, `diff_compute`, `profile_save` after PATCH) + 1 auto-captured GENERATION child, (c) `[REDACTED — char_count=N]` watermark in BOTH trace root input AND generation input — no name/email/phone/LinkedIn/GitHub/address.

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
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

### G-07-UAT-01: Langfuse SDK 3.x → 4.x migration (PROF-06 trace contract broken)
status: resolved_at_code_level
resolution_commits: [ad31379, 3ffc244, 82bb8d5, f8a90bf]
resolution_summary: |
  Plan 07-06 migrated 5 v3 call sites to v4 OTel-based API
  (`start_as_current_observation`, `update_current_generation`,
  `set_current_trace_io`), added `derive_langfuse_trace_id` helper for
  POST/PATCH trace_id correlation, added two-layer PII redaction via
  `redact_current_generation_input`, and replaced Mock-based tests with
  contract-faithful `FakeLangfuseClient` that raises AttributeError on
  every v3 method name. Pending Adrian's live replay (Test 1) to close
  the gap end-to-end.
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
