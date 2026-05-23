---
phase: 06-chat
plan: 03
subsystem: frontend
tags: [chat, frontend, hook, streaming, abort, sse, react, reducer, useChatStream]
dependency_graph:
  requires:
    - "Phase 6 Plan 01 (Wave 0 — types.ts TranscriptItem union + TranscriptAction + ERROR copy tables + sseMockUtils + 4 skip-guarded scaffolds + DebugAgentStream Pitfall H fix)"
    - "Phase 6 Plan 02 (Wave 1 — POST /agent/stream backend + AgentQuery body + snapshot regen + types.ts codegen)"
    - "Phase 4 Plan 04 (api/readSSEStream.ts AgentEvent typed iterator; api/authedFetch.ts POST+JSON+signal-threaded wrapper)"
  provides:
    - "frontend/src/api/agent.ts streamAgent(query, signal): Promise<AsyncIterable<AgentEvent>>"
    - "frontend/src/components/chat/useChatStream.ts hook returning {items, isStreaming, coldStart, networkError, submit, stop, toggleToolExpanded}"
    - "frontend/src/test/useChatStream.test.tsx — 7 active tests covering CHAT-01/02/05/06 + Pitfalls A/B/D"
  affects:
    - "Plan 06-04 (presentation components consume hook return values; ChatPage route wires hook once at the top)"
tech-stack:
  added: []  # No new deps — pure typed-hook + helper landing on existing React 19 + readSSEStream + authedFetch stack
  patterns:
    - "Per-submit AbortController owned in useRef + cleanup-on-unmount Pitfall A defense"
    - "Stale-closure-safe submit guard via parallel isStreamingRef mirror of isStreaming state"
    - "AbortError triage in catch: name === 'AbortError' → MARK_STOPPED dispatch (control flow); other errors → setNetworkError(classify(err))"
    - "Cold-start setTimeout(10_000) cleared in 3 places (submit-start, every event, finally) — Pitfall D leak proof"
    - "Per-submit fresh AbortController stored in ref so stop() can reach it via ref.current?.abort()"
    - "abortableGenerator test helper races source.next() vs AbortSignal — simulates native fetch+stream AbortError without depending on real fetch"
    - "Source-level CHAT-06 enforcement via acceptance grep (0 references) + test-level CHAT-06 spy (0 .setItem / .open calls)"
key-files:
  created:
    - frontend/src/components/chat/useChatStream.ts
  modified:
    - frontend/src/api/agent.ts          # 3-line stub → 27-line typed streamAgent helper
    - frontend/src/test/useChatStream.test.tsx  # Wave 0 skip-stub → 7 active covering tests
decisions:
  - "isStreamingRef mirror of isStreaming React state (RESEARCH skeleton deviation) — the `if (isStreaming) return` guard at submit() top reads from React state which has a stale closure if submit is called twice in the same render frame; mirroring the same flag into a ref keeps the second call's guard accurate under Pitfall A. Adds ~3 lines (declare ref + 2 mutations in finally block) for closure correctness. Tested by Pitfall A under StrictMode wrapper."
  - "(event.args ?? null) as object | null cast (RESEARCH skeleton deviation) — openapi-typescript codegen surfaces ToolStartEvent.args as Record<string, unknown> | undefined; cast narrows to TranscriptItem.args shape (object | null) without runtime change. Defensive cast per Phase 1 Plan 01-04 D-05 boundary coercion convention. Could also have used a type guard helper; chose inline cast for surface-area minimization."
  - "abortableGenerator test helper races source.next() vs an AbortSignal-driven rejection promise — chosen over alternatives (a) writing a real ReadableStream that observes signal (more complex; needs reader.cancel() wiring on abort), and (b) ad-hoc mock implementations per test (duplicate logic). The helper centralizes abort propagation so all 7 tests get realistic AbortError semantics without each test re-implementing the race. Mirrors native fetch+stream behavior where reader.read() rejects with AbortError when its AbortSignal fires."
  - "indexedDB shim installed in beforeEach (jsdom doesn't ship IndexedDB on Node 22+). Without the shim, vi.spyOn(indexedDB, 'open') crashes with ReferenceError before the spy runs. The shim is a no-op object with an open() method that the spy can wrap; the test asserts 0 calls regardless. Keeps the CHAT-06 spy assertion robust across Node versions without forcing every contributor to install fake-indexeddb."
  - "Pitfall B test uses await act(async () => { stop(); await submitPromise }) instead of separate `act(stop)` + `await submitPromise` lines. The async finally block in submit() dispatches setIsStreaming(false) + isStreamingRef mutation + clearColdStartTimer + abortControllerRef = null, and React state propagation needs to settle before the assertion can read isStreaming === false. Wrapping both stop() AND the await in a single act() block ensures the dispatch queue drains within the act-wrapped scope. Sibling Pitfall D cleanup follows the same pattern."
  - "Did NOT add a separate test for null/empty-query no-op. The `if (query.trim() === '') return` guard is covered indirectly by CHAT-05 — submit() blocks on isStreaming OR empty trim; the CHAT-05 test asserts streamAgent called once and one user-message appended, which would also fail if the empty-string guard were missing. Out-of-scope for Plan 03 dedicated coverage; Plan 04 ChatComposer can add a dedicated empty-input UI test."
  - "Did NOT spy on sessionStorage (acceptance criteria only requires localStorage + indexedDB spies). Source-level grep catches sessionStorage at the acceptance gate (count == 0); test-level spy is redundant. Defense-in-depth lives in the grep + Plan 05 manual UAT (DevTools Application tab inspection)."
metrics:
  duration: "~6m 42s (executor wall-clock; 3 files touched: 1 modified + 1 created + 1 overwritten)"
  completed_date: "2026-05-23"
  tasks: 2
  files_changed: 3
  commits: 2
requirements: [CHAT-01, CHAT-02, CHAT-05, CHAT-06]
---

# Phase 6 Plan 3: Frontend Data Layer Summary

**One-liner:** Filled the `frontend/src/api/agent.ts` stub with a typed `streamAgent(query, signal)` POST wrapper threading `AbortSignal` through `authedFetch` to `readSSEStream`, then implemented `useChatStream` as the single owner of the chat lifecycle (reducer with 9 action types + per-submit `AbortController` + 10s cold-start timer + AbortError triage), with 7 activated tests covering CHAT-01/02/05/06 + RESEARCH Pitfalls A (StrictMode), B (AbortError), D (timer cleanup).

## Tasks Executed (2/2)

### Task 1: Fill streamAgent helper — commit `ecc6ea2`

**`frontend/src/api/agent.ts` (27 lines, replaces the 3-line `export {}` stub):**

- Imports `authedFetch` from `@/api/authedFetch` (Phase 4 D-13) and `readSSEStream` + `type AgentEvent` from `@/api/readSSEStream` (Phase 4 D-16)
- `async function streamAgent(query: string, signal: AbortSignal): Promise<AsyncIterable<AgentEvent>>`
- Calls `authedFetch('/agent/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }), signal })`
- Returns `readSSEStream(response)` directly (AsyncGenerator is AsyncIterable; no extra wrapping)
- `signal` is REQUIRED (not optional) per Phase 6 D-26 mandate
- No additional `!res.ok` guard — `readSSEStream` owns it internally (line 41-42 of that module)
- AbortError propagates to caller (useChatStream's `catch` block handles)

### Task 2: useChatStream hook + activated tests — commit `9946f2d`

**`frontend/src/components/chat/useChatStream.ts` (272 lines, NEW):**

Top-level structure:
- `COLD_START_DELAY_MS = 10_000` module constant (D-19 + UI-SPEC §12 verbatim)
- `transcriptReducer(state, action)` — switch over 9 `TranscriptAction` variants from `types.ts`
- `classifyNetworkError(err)` — D-24 copy-table maps 401/403/5xx/TypeError-unreachable/unknown
- `UseChatStreamReturn` named export type
- `useChatStream()` hook export

Reducer action handlers:
| Action | Behavior |
|---|---|
| `APPEND_USER_MESSAGE` | Append `{ kind: 'user-message', id, content }` |
| `APPEND_ASSISTANT_TEXT` | Append `{ kind: 'assistant-text', id, content: '', streaming: true }` |
| `APPEND_TOKEN` | Mutate last item in-place if `assistant-text && streaming` — append `action.content` |
| `CLOSE_CURRENT_TEXT` | Flip `streaming: false` on any streaming assistant-text items |
| `APPEND_TOOL_START` | Append `{ kind: 'tool-call', id, name, args, output: null, expanded: false }` |
| `UPDATE_TOOL_OUTPUT` | Set `output` on matching `tool-call` item by id |
| `TOGGLE_TOOL_EXPANDED` | Flip `expanded` on matching `tool-call` item by id |
| `APPEND_ERROR` | Append `{ kind: 'error', id, reason, message }` |
| `MARK_STOPPED` | On streaming assistant-text: set `streaming: false, stopped: true` |

Refs used (4 total):
- `abortControllerRef: useRef<AbortController | null>(null)` — per-submit fresh controller; `stop()` calls `.abort()`
- `coldStartTimerRef: useRef<ReturnType<typeof setTimeout> | null>(null)` — 10s timer; cleared in 3 places
- `isStreamingRef: useRef<boolean>(false)` — stale-closure-safe mirror of `isStreaming` state for submit guard

useEffect cleanup (Pitfall A — single useEffect with `[]` deps):
- Aborts in-flight controller on unmount
- Clears cold-start timer on unmount

`submit(query)` lifecycle:
1. Guard: `if (isStreamingRef.current) return` (Pitfall A defense-in-depth) + `if (query.trim() === '') return`
2. Set `isStreamingRef.current = true`
3. Dispatch `APPEND_USER_MESSAGE` + `APPEND_ASSISTANT_TEXT`
4. `setIsStreaming(true) + setColdStart(false)`
5. Schedule fresh cold-start timer (clearing any stale one first — Pitfall D)
6. Create fresh `AbortController`; store in ref
7. `try`: `streamAgent(query, signal)` → `setNetworkError(null)` (Pitfall I atomic clear) → `for await` event loop
8. Event loop: on every event, clear cold-start timer + setColdStart(false); switch on `event.type`:
   - `token` → `APPEND_TOKEN`
   - `tool_start` → `CLOSE_CURRENT_TEXT` + `APPEND_TOOL_START` + `APPEND_ASSISTANT_TEXT` (fresh, D-08)
   - `tool_end` → `UPDATE_TOOL_OUTPUT` (matches via pendingToolIds queue)
   - `heartbeat` → silent (D-20; timer clear is the only effect)
   - `error` → `CLOSE_CURRENT_TEXT` + `APPEND_ERROR`
   - `final` → `CLOSE_CURRENT_TEXT`
9. `catch`: AbortError → `MARK_STOPPED` (Pitfall B control flow); other → `setNetworkError(classify(err))`
10. `finally`: `setIsStreaming(false)` + `isStreamingRef.current = false` + clearColdStartTimer + `abortControllerRef.current = null`

`stop()`: calls `abortControllerRef.current?.abort()`; submit's catch+finally handles state cleanup.

`toggleToolExpanded(id)`: dispatches `TOGGLE_TOOL_EXPANDED`.

**`frontend/src/test/useChatStream.test.tsx` (282 lines, REPLACES Wave 0 skip-stub):**

7 active tests across 6 describe blocks:

| Describe | Test | Requirement / Pitfall |
|---|---|---|
| CHAT-01/02 happy path | appends user message then assistant text, streaming token content incrementally | CHAT-01, CHAT-02 |
| CHAT-01/02 happy path | interleaves tool-call items between text segments (D-08) | D-08 |
| CHAT-05 submit-during-stream blocked | submit() is a no-op while isStreaming === true | CHAT-05 |
| CHAT-06 storage spy (zero residue) | never calls localStorage.setItem across multiple submit cycles | CHAT-06 |
| Pitfall A | clicking submit once under StrictMode results in exactly one streamAgent call | Pitfall A |
| Pitfall B | stop() during streaming sets stopped=true on current text + leaves networkError null | Pitfall B |
| Pitfall D | stopping mid-stream clears the cold-start timer so a stale timer cannot flip coldStart on the next submit | Pitfall D |

Test helpers:
- `abortableGenerator(source, signal)` — async generator that races `source.next()` against an AbortSignal-driven reject promise; throws `AbortError` (Error with `name = 'AbortError'`) when signal fires. Used by both `setStreamMock` and `setHangingStreamMock` to simulate native fetch+stream abort semantics.
- `setStreamMock(events)` / `setHangingStreamMock(initialEvents)` — `vi.mocked(streamAgent).mockImplementation(async (_query, signal) => abortableStream(readSSEStream(mockSse{Hanging,}Response(events)), signal))`
- `strictWrapper({ children })` — StrictMode wrapper for renderHook's `wrapper` option (Pitfall A test)
- `beforeEach`: `vi.useRealTimers()` + `vi.mocked(streamAgent).mockReset()` + indexedDB shim install when global is undefined (jsdom on Node 22+ omits IndexedDB)

## Verification Evidence

### Per-task automated verifies

**Task 1:**
```
grep -c "export async function streamAgent" → 1
grep -c "import { authedFetch }" → 1
grep -c "import { readSSEStream, type AgentEvent }" → 1
grep -c "method: 'POST'" → 1
grep -c "body: JSON.stringify({ query })" → 1
grep -c "signal: AbortSignal" → 1
grep -c "Promise<AsyncIterable<AgentEvent>>" → 1
grep -c "export {}" → 0 (stub line gone)
npm run typecheck → exit 0
npm run lint → exit 0
```

**Task 2:**
```
grep -c "export function useChatStream" → 1
grep -c "useReducer" → 2
grep -c "AbortController" → 4
grep -c "COLD_START_DELAY_MS = 10_000" → 1
grep -cF "if (err instanceof Error && err.name === 'AbortError')" → 1
grep -c "localStorage\|sessionStorage\|indexedDB\|IndexedDB" → 0  # CHAT-06 source enforcement
grep -c "crypto.randomUUID" → 5
grep -c "describe('useChatStream" → 6
grep -c "vi.spyOn(window.localStorage" → 1
grep -c "StrictMode" → 5
grep -c "vi.useFakeTimers" → 1
npm run typecheck → exit 0
npm run lint → exit 0
npm test -- --run useChatStream → 7 tests passed
```

### Overall verification trifecta (post-Task 2)

```
Frontend gate:
- npm run typecheck ........................... exit 0
- npm run lint ................................ exit 0
- npm test -- --run ........................... 17 files, 61 tests passed
                                                (was 17/55 before Plan 03; +6 covering
                                                 useChatStream tests, scaffold activated)
- npm run build ............................... built in 193ms, no errors

Plan 01 scaffold sanity (still skip-clean):
- npm test -- --run ToolChip ChatComposer ChatTranscript
  → 3 files / 3 tests pass (skip-clean — target components ship in Plan 04)
```

## Pitfall Closures

### Pitfall A — React 19 StrictMode does NOT double-fire submit
- **Mechanism:** submit is a click-handler-bound `useCallback`, NOT inside a useEffect; click handlers don't double-fire under StrictMode. The single useEffect has `[]` deps and only does cleanup-abort + timer-clear (idempotent).
- **Defense-in-depth:** `isStreamingRef.current` guard at submit() top blocks any programmatic re-entry within a single render.
- **Test:** `renderHook(() => useChatStream(), { wrapper: strictWrapper })` → `submit('test')` → `expect(vi.mocked(streamAgent)).toHaveBeenCalledTimes(1)`. PASSES.

### Pitfall B — AbortError treated as control flow, not networkError
- **Mechanism:** catch block discriminates on `err instanceof Error && err.name === 'AbortError'`; if true, dispatches `MARK_STOPPED` and returns (skips `setNetworkError`). Other errors route to `setNetworkError(classify(err))`.
- **Test:** start hanging stream → wait for first token → `stop()` → `expect(networkError).toBeNull()` AND `expect(items.at(-1).stopped).toBe(true)`. PASSES.

### Pitfall C — ReadableStream reader release via for-await
- **Inherited from Phase 4 D-16:** `readSSEStream` already has `finally { reader.releaseLock() }`. The hook's for-await loop terminates on AbortError or generator return, triggering Phase 4's finally cleanup transitively.
- **No additional test needed** — covered by the Pitfall B test's successful resource cleanup (afterEach doesn't leak).

### Pitfall D — Cold-start timer cleanup across rapid submit/stop/submit
- **Mechanism:** `clearColdStartTimer()` runs in 3 places: (a) at submit start before setting a fresh timer, (b) on every event received in the for-await loop, (c) in the `finally` block. `stop()` triggers `finally` via the catch (AbortError) path.
- **Test:** `vi.useFakeTimers({ shouldAdvanceTime: true })` → submit → advanceTimersByTime(9_000) → stop → submit → advanceTimersByTime(2_000) → `expect(coldStart).toBe(false)`. The 9+2=11s would have fired the first timer if it leaked; coldStart remains false → timer cleanup verified. PASSES.

### Pitfall I — Atomic networkError replacement
- **Mechanism:** `setNetworkError(null)` only fires AFTER `streamAgent(...)` resolves successfully (i.e., after the Response arrives). If the new submit also fails, the old Alert is replaced by the new one without flashing to empty.
- **No dedicated test in Plan 03** — covered indirectly by the happy-path test (`expect(networkError).toBeNull()`) and by the absence of a setNetworkError call before the await.

## CHAT-06 Storage Spy Enforcement (Two-Layer)

1. **Source-level acceptance grep:** `grep -c "localStorage\|sessionStorage\|indexedDB\|IndexedDB" frontend/src/components/chat/useChatStream.ts` returns **0**. Verified at the acceptance criterion gate; will fail CI if any future contributor adds storage code.
2. **Test-level spy:** `vi.spyOn(window.localStorage, 'setItem')` + `vi.spyOn(indexedDB, 'open')` across 2 submit/final cycles → `expect(setItemSpy).not.toHaveBeenCalled()` + `expect(idbOpenSpy).not.toHaveBeenCalled()`. PASSES.
3. **Plan 05 UAT runbook (future):** DevTools Application-tab inspection is the manual third layer for end-to-end coverage. Out of scope for Plan 03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CHAT-06 grep failure on docstring containing literal storage names**
- **Found during:** Task 2 verification — first run of `grep -c "localStorage\|sessionStorage\|indexedDB\|IndexedDB"` returned 1 (not 0) because the file header docstring read "this module MUST NOT reference localStorage, sessionStorage, or indexedDB".
- **Issue:** The acceptance criterion is a literal grep against the source file. Comment text is matched too, so the policy reminder violated its own policy at the grep level.
- **Fix:** Rewrote the docstring to describe the policy without naming the specific APIs ("MUST NOT reference any browser persistence API"). Policy intent preserved; grep gate now passes.
- **Files modified:** `frontend/src/components/chat/useChatStream.ts` (docstring only)
- **Folded into:** Task 2 commit `9946f2d` (inline fix before commit)

**2. [Rule 3 - Blocking] indexedDB is not defined in jsdom (Node 22+)**
- **Found during:** Task 2 first test run — `vi.spyOn(indexedDB, 'open')` crashed with `ReferenceError: indexedDB is not defined`.
- **Issue:** jsdom on Node 22+ does not provide the IndexedDB API by default. The CHAT-06 storage spy needs to assert 0 calls to indexedDB.open, but the spy can't be installed if the global is undefined.
- **Fix:** Added an indexedDB shim in `beforeEach`: when `globalThis.indexedDB === 'undefined'`, install a no-op object with an `open()` method. The spy then wraps the shim; assertion verifies 0 calls regardless. Honors the threat-model intent (T-06-03-01) without requiring contributors to install fake-indexeddb.
- **Files modified:** `frontend/src/test/useChatStream.test.tsx` (beforeEach hook)
- **Folded into:** Task 2 commit `9946f2d`

**3. [Rule 3 - Blocking] AbortError not propagating from mocked streamAgent + hanging stream**
- **Found during:** Task 2 first test run — Pitfall B test timed out at 5000ms because `controller.abort()` had no effect on the mocked readSSEStream of a hanging mockSseHangingResponse (the mock response has no AbortSignal wiring; only real `fetch` rejects the reader on signal abort).
- **Issue:** The Wave 0 mockSseHangingResponse is a pure ReadableStream that never closes; abort doesn't propagate because there's no fetch+signal binding.
- **Fix:** Added `abortableGenerator(source, signal)` test helper that races `source.next()` against an AbortSignal-driven reject promise. When signal aborts, the generator throws `AbortError` (Error with `name = 'AbortError'`) mid-iteration, matching native fetch+stream behavior. `setStreamMock` and `setHangingStreamMock` now wire signal through `abortableStream(readSSEStream(mockResponse), signal)`.
- **Files modified:** `frontend/src/test/useChatStream.test.tsx` (mock helpers + abortableGenerator function)
- **Folded into:** Task 2 commit `9946f2d`

**4. [Rule 1 - Bug] TypeScript narrowing failure on abortableGenerator's `yield next.value`**
- **Found during:** Task 2 typecheck after AbortError mock fix — TS reported `Type 'void | AgentEvent' is not assignable to type 'AgentEvent'` because the IteratorResult<AgentEvent, void> shape leaks `void` past `if (next.done) return`.
- **Issue:** Inline arrow generators (`async *[Symbol.asyncIterator]() { ... }`) don't get an explicit return type, so TS infers `void | AgentEvent` on the yield expression even after the done check.
- **Fix:** Hoisted `abortableGenerator` to a module-level `async function*` with explicit `AsyncGenerator<AgentEvent, void, undefined>` return type, plus a `next.value as AgentEvent` cast to narrow past the IteratorResult union. `abortableStream` becomes a thin wrapper that just calls `abortableGenerator(...)`.
- **Files modified:** `frontend/src/test/useChatStream.test.tsx` (refactor)
- **Folded into:** Task 2 commit `9946f2d`

**5. [Rule 1 - Bug] React state lag on Pitfall B + D test assertions**
- **Found during:** Task 2 after-AbortError-mock-fix run — Pitfall B failed `expect(isStreaming).toBe(false)` because the finally block's `setIsStreaming(false)` hadn't propagated to the rendered hook state by the time the assertion ran.
- **Issue:** `await submitPromise` returns once the promise resolves, but React state updates queued during the finally block may not have batched/flushed before the next assertion line.
- **Fix:** Wrapped the `stop()` + `await submitPromise` chain in `await act(async () => { ... })` so React's state updates are flushed within the act-wrapped scope. Added `await waitFor(() => expect(isStreaming).toBe(false))` as an additional settle gate. Applied same pattern to Pitfall D's cleanup section.
- **Files modified:** `frontend/src/test/useChatStream.test.tsx` (Pitfall B + Pitfall D test bodies)
- **Folded into:** Task 2 commit `9946f2d`

### Auth gates

None — fully automated; no auth required for hook implementation, test runs, or commits.

### Pre-existing out-of-scope issues observed

- `.planning/phases/04.1-phase-4-follow-ups-runbook-deviation-cleanup/04.1-VERIFICATION.md` shows pending modifications in the working tree from a prior session. Not part of this plan's scope; deliberately excluded from both commits in this plan.
- One residual `act()` console warning in the Pitfall D test (from the abortable generator's late settle after fake-timer advancement). Cosmetic, non-blocking, tests pass.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The streamAgent helper consumes the Phase 6 Plan 02 POST contract through the Phase 4 D-13 authedFetch wrapper (Bearer JWT chain unchanged); the useChatStream hook is purely client-side state. T-06-03-01 (CHAT-06 storage residue) is fully mitigated by the two-layer enforcement above.

## Assumption Closures

- **Heartbeat handling (D-20):** Verified — heartbeat events fall through to the `default` cold-start timer clear at the top of the for-await body; no dispatch, no UI change. The `case 'heartbeat'` branch is an explicit no-op for readability.
- **Tool-call id pairing (D-08):** Verified — `pendingToolIds: string[]` queue inside submit's closure. `tool_start` pushes a fresh id; `tool_end` shifts the head. Order-preserving even if multiple tool calls are in-flight (single-stream serial; no parallel tools per Phase 1 agent design).
- **`setNetworkError(null)` placement (Pitfall I):** Verified — fires AFTER `await streamAgent(...)` succeeds (i.e., after Response arrives), not before. If MSAL refresh inside authedFetch fails, the previous error stays visible until the new fetch succeeds.

## Known Stubs

None — this plan ships production-ready data layer. The Plan 01 scaffold tests for `ToolChip`, `ChatComposer`, `ChatTranscript` remain skip-clean as intended; they will activate when Plan 04 lands those presentation components.

## Self-Check: PASSED

### Created/modified files exist

```
FOUND: frontend/src/api/agent.ts                            (modified: 27 lines)
FOUND: frontend/src/components/chat/useChatStream.ts        (created: 272 lines)
FOUND: frontend/src/test/useChatStream.test.tsx             (rewritten: 282 lines)
FOUND: .planning/phases/06-chat/06-03-SUMMARY.md            (this file)
```

### Commits exist in git history

```
FOUND: ecc6ea2 feat(06-03): fill streamAgent typed POST wrapper for /agent/stream
FOUND: 9946f2d feat(06-03): implement useChatStream hook + activate covering tests
```

### Acceptance grep gates (all match expected counts)

```
agent.ts:
  export async function streamAgent ........... 1 ✓
  import { authedFetch } ...................... 1 ✓
  import { readSSEStream, type AgentEvent } ... 1 ✓
  method: 'POST' .............................. 1 ✓
  body: JSON.stringify({ query }) ............. 1 ✓
  signal: AbortSignal ......................... 1 ✓
  Promise<AsyncIterable<AgentEvent>> .......... 1 ✓
  export {} ................................... 0 ✓

useChatStream.ts:
  export function useChatStream ............... 1 ✓
  useReducer .................................. 2 (≥1) ✓
  AbortController ............................. 4 (≥1) ✓
  COLD_START_DELAY_MS = 10_000 ................ 1 ✓
  AbortError triage (literal) ................. 1 ✓
  localStorage|sessionStorage|indexedDB ....... 0 ✓ (CHAT-06)
  crypto.randomUUID ........................... 5 (≥3) ✓

useChatStream.test.tsx:
  describe('useChatStream ..................... 6 (≥3) ✓
  vi.spyOn(window.localStorage ................ 1 ✓
  StrictMode .................................. 5 (≥1) ✓
  vi.useFakeTimers ............................ 1 ✓
```

### Frontend gate trifecta

```
npm run typecheck → exit 0
npm run lint → exit 0
npm test -- --run → 17 files / 61 tests passed (was 17/55; +6 active tests)
npm run build → built in 193ms, 0 errors
```

## Next Plan

**06-04** (presentation components + route composition):
- Build `ChatTranscript.tsx`, `ChatMessage.tsx`, `ToolChip.tsx`, `ChatComposer.tsx`, `ChatEmptyState.tsx` — all state-free presentation components driven by `useChatStream` return values
- Replace `<PhasePlaceholder phase={6} feature="Chat" />` in `Chat.tsx` with the live wiring
- Plan 01 skip-stubs for `ToolChip`, `ChatComposer`, `ChatTranscript` auto-activate as their target components land
- Linear-dense aesthetic per UI-SPEC §6 + §31 — flat thread, no bubbles, role labels, monospace tool-call args
