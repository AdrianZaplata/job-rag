---
phase: 6
slug: chat
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-23
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 06-RESEARCH.md §Validation Architecture (lines 599–678) + CONTEXT.md §D-29/§D-30.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Frontend framework** | Vitest 3.2.x + @testing-library/react 16.3.x + @testing-library/jest-dom 6.9.x + jsdom 29.x |
| **Frontend config** | `frontend/vite.config.ts` (`test` block) + `frontend/src/test/setup.ts` |
| **Frontend quick run** | `cd frontend && npm test -- --run` |
| **Frontend full suite** | `cd frontend && npm run typecheck && npm run lint && npm test -- --run` |
| **Backend framework** | pytest 9.0.3+ + pytest-asyncio + httpx 0.28+ + asgi-lifespan 2.x |
| **Backend config** | `pyproject.toml` `[tool.pytest.ini_options]` + `tests/conftest.py` |
| **Backend quick run** | `uv run pytest tests/test_api.py tests/test_sse_contract.py -x` |
| **Backend full suite** | `uv run ruff check src/ tests/ && uv run pyright src/ && uv run pytest -x` |
| **OpenAPI drift check** | `cd frontend && npm run codegen:snapshot && git diff --exit-code frontend/src/api/types.ts` |
| **Estimated runtime** | Frontend ~5s; Backend ~20s; Full suite (both) ~30s |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm test -- --run` (frontend tasks) OR `uv run pytest tests/test_api.py tests/test_sse_contract.py -x` (backend tasks); commit-targeted file if commit touches one file
- **After every plan wave:** Run full frontend (`npm run typecheck && npm run lint && npm test -- --run`) + chat-relevant backend (`uv run pytest tests/test_api.py tests/test_sse_contract.py -x`)
- **Before `/gsd-verify-work`:** Full suite green — frontend (`typecheck + lint + build + test`) + backend (`ruff + pyright + pytest`) + OpenAPI drift check + manual UAT runbook
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-XX | 01 | 0 | (foundation) | — | Test stubs skip-clean before targets land | infra | `npm test -- --run` | ❌ W0 | ⬜ pending |
| 06-02-XX | 02 | 1 | D-01..D-04 backend | T-V13 OpenAPI drift | POST `/agent/stream` accepts `{query}` body via AgentQuery | integration | `uv run pytest tests/test_api.py::TestAgentStream -x` | ✅ existing file | ⬜ pending |
| 06-02-XX | 02 | 1 | D-04 OpenAPI snapshot | T-V13 | Snapshot reflects POST contract; types.ts compiles | integration | `npm run codegen:snapshot && git diff --exit-code` + `npm run typecheck` | ✅ existing scripts | ⬜ pending |
| 06-03-XX | 03 | 2 | CHAT-01, CHAT-02 | T-V8 no persistence | `/chat` streams via fetch+ReadableStream w/ Bearer; tokens render incrementally; storage spies remain at 0 calls | integration | `npm test -- --run useChatStream` | ❌ W0 — `frontend/src/test/useChatStream.test.tsx` | ⬜ pending |
| 06-03-XX | 03 | 2 | CHAT-05 | T-V8 / T-Pitfall A | `final` event sets `isStreaming === false`; React-19 StrictMode does NOT double-fire | unit (StrictMode + final event) | `npm test -- --run useChatStream` | ❌ W0 (same file) | ⬜ pending |
| 06-03-XX | 03 | 2 | CHAT-06 | T-V8 storage spy | `useChatStream` never calls `localStorage.setItem` or `indexedDB.open` across submit/stop cycles | unit (spy assertion) | `npm test -- --run useChatStream` | ❌ W0 (same file) | ⬜ pending |
| 06-03-XX | 03 | 2 | Pitfall B AbortError | — | Stop click → `networkError === null` AND current item marked `stopped: true` | unit | `npm test -- --run useChatStream` | ❌ W0 (same file) | ⬜ pending |
| 06-03-XX | 03 | 2 | Pitfall D timer cleanup | — | Rapid submit/stop/submit does not leak cold-start timer; `vi.useFakeTimers()` advance verifies `coldStart === false` after reset | unit | `npm test -- --run useChatStream` | ❌ W0 (same file) | ⬜ pending |
| 06-04-XX | 04 | 3 | CHAT-03 | — | `tool_start` renders collapsed chip with name + JSON args; `aria-expanded="false"` | unit | `npm test -- --run ToolChip` | ❌ W0 — `frontend/src/test/ToolChip.test.tsx` | ⬜ pending |
| 06-04-XX | 04 | 3 | CHAT-04 | — | `tool_end` populates chip with 200-char truncated output + `…`; "Show full" Dialog opens with full text | unit | `npm test -- --run ToolChip` | ❌ W0 (same file) | ⬜ pending |
| 06-04-XX | 04 | 3 | CHAT-05 (UI half) | — | Enter submits; Shift+Enter inserts newline; Stop click aborts; composer disabled-while-streaming | unit | `npm test -- --run ChatComposer` | ❌ W0 — `frontend/src/test/ChatComposer.test.tsx` | ⬜ pending |
| 06-04-XX | 04 | 3 | D-17 smart autoscroll | — | Items render in order; autoscroll suppressed when user scrolls up | unit | `npm test -- --run ChatTranscript` | ❌ W0 — `frontend/src/test/ChatTranscript.test.tsx` | ⬜ pending |
| 06-04-XX | 04 | 3 | Pitfall H DebugAgentStream | T-V13 contract drift | DebugAgentStream POSTs `{query}` not `{message}` | grep guard | `grep -n "body: JSON.stringify({ message:" frontend/src/routes/DebugAgentStream.tsx` (expect 0 lines) | n/a — grep | ⬜ pending |
| 06-05-XX | 05 | 4 | UAT (live) | — | Live demo: cold-start "Warming up…" appears, tokens stream, tool chips expand, refresh wipes state | manual | UAT runbook in `06-05-PLAN.md` | n/a — manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Plan numbering above is a planner-time hint per RESEARCH.md plan-grain recommendation (4-5 plans). Final task IDs are assigned by gsd-planner.*

---

## Wave 0 Requirements

- [ ] `frontend/src/test/useChatStream.test.tsx` — covers CHAT-01, CHAT-02, CHAT-05, CHAT-06 (storage spy), Pitfalls A (StrictMode), B (AbortError), D (timer cleanup)
- [ ] `frontend/src/test/ToolChip.test.tsx` — covers CHAT-03 (collapsed chip render), CHAT-04 (output truncation + "Show full" Dialog)
- [ ] `frontend/src/test/ChatComposer.test.tsx` — covers CHAT-05 submit-blocked-during-stream, Enter/Shift+Enter keymap, Stop click
- [ ] `frontend/src/test/ChatTranscript.test.tsx` — covers D-17 smart-autoscroll, item ordering, conditional network-error Alert
- [ ] `frontend/src/test/sseMockUtils.ts` — shared `mockSseResponse(frames: AgentEvent[]): Response` helper producing a `Response` with `ReadableStream` body of SSE-formatted bytes (extracted from existing Phase 4 `readSSEStream.test.ts` pattern to avoid duplication)

*Test stubs activate as plans land per Phase 1/4/5 precedent: each test guards `import.fail` and `mock target missing` so they skip-clean in Wave 0 and activate the moment downstream plans land the target symbols.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cold-start "Warming up the agent — ~4 minutes after idle" copy renders at 10s mark | D-19 | Requires real ACA scale-from-zero (~225s); cannot be reliably simulated against fixture | After 4+ hour idle: load `/chat`, submit query, screenshot at T=11s showing "Warming up…" copy |
| Live demoability (≤30s recording of one chat turn) | ROADMAP §Phase 6 success criterion 5 | Requires running deployed ACA stack with warmed agent | After cold-start mitigation: record screen of question → tool_start chip → tool_end chip → streamed synthesis → final; assert ≤30s total |
| Zero localStorage / IndexedDB residue after refresh | CHAT-06 (UAT side) | Storage spy unit test covers code path; UAT confirms no other code (Phase 4 MSAL, Phase 5 dashboard) leaves chat-related residue | Submit query, wait for `final`; refresh; DevTools Application tab inspect localStorage + IndexedDB; assert no `chat-*` or `transcript-*` keys |
| Tool chip expand/collapse on real `search_jobs` output | CHAT-03, CHAT-04 (live) | Unit tests use mock fetch; live test validates against real agent + real tool output shape | Submit "What's the top must-have skill in Berlin?"; click chip header; verify args + 200-char output + "Show full" Dialog with full output |
| Stop button mid-stream cancels cleanly (no orphaned tokens after) | D-16 | Race condition timing depends on real fetch + agent latency | Submit a long-running query; click Stop during streaming; verify no additional tokens append; composer re-enables; `(stopped)` suffix visible |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (5 new test files listed above)
- [ ] No watch-mode flags (every command uses `--run` for single-pass)
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner assigns final task IDs)

**Approval:** pending (planner-time; gsd-planner finalizes task IDs and flips nyquist_compliant)
