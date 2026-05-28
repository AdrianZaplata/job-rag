---
status: partial
phase: 07-profile-resume-upload
source: [07-VERIFICATION.md]
started: 2026-05-28T13:50:00Z
updated: 2026-05-28T13:50:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Langfuse trace rendering (M-marker 3)
expected: Single Langfuse trace per upload spanning extraction → Instructor → diff → PATCH; 4 spans (text_extract, llm_extract auto, diff_compute, profile_save) correlated by extraction_id; raw resume text NOT visible in any span input/metadata
result: [pending]

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
