---
phase: 06-chat
plan: 01
subsystem: frontend
tags: [chat, foundation, shadcn, wave-0, types, scaffolding]
dependency_graph:
  requires: []
  provides:
    - "@/components/ui/collapsible"
    - "@/components/ui/textarea"
    - "@/components/chat/types (TranscriptItem | NetworkError | TranscriptAction | ERROR_TITLE | ERROR_BODY)"
    - "@/test/sseMockUtils (mockSseResponse, mockSseHangingResponse)"
    - "app.css .animate-blink utility"
  affects:
    - frontend/src/routes/DebugAgentStream.tsx (body-key aligned to AgentQuery)
tech-stack:
  added:
    - "shadcn collapsible primitive (radix-ui unified import)"
    - "shadcn textarea primitive (pure-CVA wrapper)"
  patterns:
    - "Skip-guarded test stub (string-concat import specifier + try/catch + symbol-presence check)"
    - "Append-only CSS extension (preserves @theme inline / :root / .dark / @layer base blocks intact)"
    - "Discriminated union TranscriptItem + reducer-action TranscriptAction co-located in feature folder"
    - "Re-export wire-format types from feature module for single-import-source convenience"
key-files:
  created:
    - frontend/src/components/ui/collapsible.tsx
    - frontend/src/components/ui/textarea.tsx
    - frontend/src/components/chat/types.ts
    - frontend/src/test/sseMockUtils.ts
    - frontend/src/test/useChatStream.test.tsx
    - frontend/src/test/ToolChip.test.tsx
    - frontend/src/test/ChatComposer.test.tsx
    - frontend/src/test/ChatTranscript.test.tsx
  modified:
    - frontend/src/app.css (appended blink keyframes block; no edits to existing @theme/@layer)
    - frontend/src/routes/DebugAgentStream.tsx (1-line body-key fix per Pitfall H)
decisions:
  - "Used unified `radix-ui` import for Collapsible (shadcn CLI emitted per Feb 2026 changelog migration); no separate @radix-ui/react-collapsible install needed (radix-ui ^1.4.3 already pinned)"
  - "Test files live in `frontend/src/test/` (Phase 4 baseline; matches AppShell.test.tsx, AuthGate.test.tsx, readSSEStream.test.ts location — NOT `__tests__/` which is dashboard-only)"
  - "Skip-stub control flow uses `let mod` (definitely-assigned by try-catch) + early return when symbol missing — lint-clean against `no-useless-assignment` rule"
  - "ERROR_TITLE / ERROR_BODY tables use Record<SseErrorEvent['reason'], …> for compile-time exhaustiveness — adding a new reason literal in Phase 1 D-19 surfaces TypeScript errors here, not silent runtime fallback"
metrics:
  duration: "~4 minutes (executor time; 10 files touched: 8 created + 2 modified)"
  completed_date: "2026-05-23"
---

# Phase 6 Plan 1: Chat Wave 0 Foundation Summary

**One-liner:** Wave 0 scaffolding for Phase 6 chat surface — 2 net-new shadcn primitives (collapsible + textarea), TranscriptItem discriminated union + ERROR copy tables, blink keyframes for streaming cursor, shared SSE mock util, 4 skip-guarded test stubs that auto-activate as Plans 03/04 land target modules, plus Pitfall H closure (DebugAgentStream body-key aligned to AgentQuery model).

## Tasks Executed (3/3)

### Task 1: Install shadcn primitives (collapsible + textarea) — commit `e8fbf2d`

Ran `cd frontend && npx shadcn@latest add collapsible textarea` (bare invocation per Phase 5 Pitfall 8 — no `--style` flag). CLI created:
- `frontend/src/components/ui/collapsible.tsx` (31 lines, `import { Collapsible as CollapsiblePrimitive } from "radix-ui"` — unified import per Feb 2026 changelog)
- `frontend/src/components/ui/textarea.tsx` (18 lines, pure-CVA single-element wrapper; `field-sizing-content` for auto-grow)

`components.json` preset (radix-nova / neutral / lucide) preserved untouched. `git diff --stat frontend/src/components/ui/` confirms only the 2 new files; no existing UI primitives mutated. Typecheck green.

### Task 2: Create chat types module + append blink keyframes — commit `3c5e323`

**`frontend/src/components/chat/types.ts` (NEW — 84 lines):**
- `TranscriptItem` discriminated union (D-07): `user-message | assistant-text | tool-call | error` with `stopped?: boolean` on assistant-text per D-16
- `NetworkError` type (D-24): 5-variant kind union (`401 | 403 | 5xx | unreachable | unknown`) + message
- `TranscriptAction` reducer union: 9 action types for `useChatStream`'s `useReducer` per RESEARCH §"Code Examples"
- `ERROR_TITLE: Record<SseErrorEvent['reason'], string>` lookup table — verbatim D-23 copy ("Agent timed out", "Server restarting", "Language model error", "Something went wrong")
- `ERROR_BODY: Record<SseErrorEvent['reason'], string | undefined>` lookup table — verbatim D-23 copy; `internal` set to `undefined` so it falls through to `item.message` (sanitized backend message)
- Re-exports `AgentEvent` and `ErrorEvent` from `@/api/readSSEStream` per RESEARCH Open Q3 recommendation (avoids 2-source-import pattern in `useChatStream` / `ChatMessage`)

**`frontend/src/app.css` (MODIFIED — append-only):**
- Added 17 lines AFTER the existing `@layer base { ... }` block:
  - `@keyframes blink` (0%, 50%: opacity 1; 50.01%, 100%: opacity 0 — step-end discrete blink)
  - `.animate-blink` utility (`animation: blink 1s step-end infinite`)
  - `@media (prefers-reduced-motion: reduce)` carve-out (animation: none; opacity: 1 — cursor stays visible per WCAG 2.3.3)
- `@theme inline`, `:root`, `.dark`, `@layer base` blocks unchanged (verified `grep -c "@theme inline"` returns 1, unchanged from pre-task state)

### Task 3: sseMockUtils + 4 skip-guarded test stubs + DebugAgentStream Pitfall H fix — commit `bf94d6b`

**`frontend/src/test/sseMockUtils.ts` (NEW — 53 lines):**
- `mockSseResponse(events: AgentEvent[]): Response` — TextEncoder + ReadableStream<Uint8Array> producing SSE-framed bytes (`event: <type>\ndata: <JSON>\n\n`); status 200 + `Content-Type: text/event-stream` (passes readSSEStream `!res.ok` guard)
- `mockSseHangingResponse(initialEvents: AgentEvent[]): Response` — same shape but stream never closes (for Pitfall B AbortError cancellation tests in Plan 03)
- Implementation verbatim from RESEARCH §"Mock Fetch for Vitest" lines 994-1042; extracted from the existing `frontend/src/test/readSSEStream.test.ts` `streamFromString` inline helper (Phase 4 D-16 pattern) so multiple Phase 6 test files share one impl

**4 skip-guarded test stubs (NEW — ~20-30 lines each):**
- `useChatStream.test.tsx`, `ToolChip.test.tsx`, `ChatComposer.test.tsx`, `ChatTranscript.test.tsx`
- Each uses string-concat import specifier (`'@/components/chat/' + 'useChatStream'`) so `tsc` doesn't resolve at type-check time — mirrors `frontend/src/test/AppShell.test.tsx` skip-on-missing pattern
- Each wraps the dynamic import in `try/catch` (skip-clean when module not yet shipped) + symbol-presence check (skip-clean when module exists but the target export is missing)
- The 4 stubs all pass on first run (skip-clean, 4ms each) and will activate the moment Plans 03/04 land `useChatStream`, `ToolChip`, `ChatComposer`, `ChatTranscript` target symbols

**`frontend/src/routes/DebugAgentStream.tsx` (1-line MODIFIED):**
- `body: JSON.stringify({ message: query })` → `body: JSON.stringify({ query })` per Pitfall H
- Closes the latent body-key mismatch that would 422 against Plan 02's POST `AgentQuery(query: str)` backend; aligns dev probe to the canonical Pydantic model
- Nothing else changes — POST method, `Content-Type: application/json`, AbortController, error handling, lines log all identical

## Verification Evidence

### Per-task automated verifies

- **Task 1:** `test -f` both files (pass) + grep for radix-ui import (count=1) + grep for Textarea (count=2) + `npm run typecheck` (green)
- **Task 2:** grep `@keyframes blink` (count=1), `prefers-reduced-motion: reduce` (count=1), `.animate-blink` (count=2), `@theme inline` (count=1 — unchanged) + 7 types.ts greps (TranscriptItem, NetworkError, TranscriptAction, ERROR_TITLE×2, ERROR_BODY×2, "Agent timed out", "Container is shutting down") + `npm run typecheck` (green)
- **Task 3:** 5 `test -f` checks (pass) + mockSseResponse/mockSseHangingResponse export greps (1 each) + DebugAgentStream `{message:` grep (0 — old pattern gone) + `{query})` grep (1 — new pattern present) + typecheck + lint + tests (all 55 pass)

### Overall verification (post-Task 3)

```
1) shadcn primitives reachable from Plan 04 components:
   grep "Collapsible" → 11 occurrences in collapsible.tsx
   grep "Textarea" → 2 occurrences in textarea.tsx
2) Types module via tsc resolution:
   npm run typecheck → exit 0 (no errors)
3) 4 scaffold tests skip-pass cleanly:
   npm test -- --run useChatStream ToolChip ChatComposer ChatTranscript
   → 4 Test Files passed, 4 Tests passed (480ms)
4) DebugAgentStream Pitfall H closed:
   grep "body: JSON.stringify({ message:" → 0 (no match)
5) Production build:
   npm run build → tsc -b + vite build → 194ms, 2655 modules transformed, no errors/warnings
```

### Full test suite

```
17 Test Files passed (was 13 pre-task; +4 new scaffold files)
55 Tests passed (was 51 pre-task; +4 new scaffold tests)
Duration: 1.88s (full suite); 480ms (4 scaffolds targeted)
```

### Lint + typecheck + build trifecta (all exit 0)

- `npm run typecheck` → 0
- `npm run lint` → 0
- `npm run build` → 0
- `npm test -- --run` → 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `no-useless-assignment` lint errors in skip-stub control flow**
- **Found during:** Task 3 verification (ran `npm run lint` after writing the 4 test stub files)
- **Issue:** Initial scaffold pattern declared `let mod: Record<string, unknown> | null = null` then immediately reassigned in the try block. ESLint flagged the null assignment as useless because the catch block returns before the assignment is ever read.
- **Fix:** Changed to `let mod: Record<string, unknown>` (definitely-assigned by try/catch + early return on catch) and dropped the now-redundant `!mod ||` guard from the symbol-presence check (mod is guaranteed assigned if execution reaches that line).
- **Files modified:** all 4 test stub files (useChatStream.test.tsx, ToolChip.test.tsx, ChatComposer.test.tsx, ChatTranscript.test.tsx)
- **Commit:** `bf94d6b` (folded into Task 3 commit since fix was inline before committing)
- **Why Rule 1 not Rule 4:** Pure stylistic correction to a control-flow pattern; preserves semantics exactly (still skip-clean when module/symbol missing, still asserts when present). No architectural change.

### Auth gates

None — fully automated; no auth required for any shadcn install, file creation, or test run.

## Assumption Closures

- **A2 (RESEARCH §Open Question 2 — radix-ui import shape):** shadcn CLI emitted `import { Collapsible as CollapsiblePrimitive } from "radix-ui"` (unified package import per Feb 2026 changelog migration). Verified via `grep -E "from [\"']radix-ui[\"']|from [\"']@radix-ui/react-collapsible[\"']" frontend/src/components/ui/collapsible.tsx` → 1 match (unified path). No separate `@radix-ui/react-collapsible` dependency needed; `radix-ui: ^1.4.3` in package.json covers it.
- **A6 (RESEARCH §Open Question 6 — test file location):** Used `frontend/src/test/` (Phase 4 baseline matching `AppShell.test.tsx`, `AuthGate.test.tsx`, `readSSEStream.test.ts`) rather than co-locating in `frontend/src/components/chat/__tests__/`. The `__tests__/` subfolder pattern is dashboard-only (Phase 5 convention); Phase 6 follows Phase 4 baseline per VALIDATION.md Wave 0 Requirements section.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The DebugAgentStream body-key fix is the only behavior change, and it REDUCES surface (aligns dev probe to canonical AgentQuery model, preventing 422 against the Plan 02 backend) per T-06-01-02 mitigation in the plan's threat model.

## Known Stubs

The 4 test scaffold files are intentional skip-stubs that activate as Plans 03/04 land target symbols. They are NOT productive code — they are deterministic activation gates. Per the plan's Wave 0 design (Phase 1/4/5 precedent), these stubs allow Plans 03/04 to land their target symbols (`useChatStream`, `ToolChip`, `ChatComposer`, `ChatTranscript`) without touching the test scaffolds, and the test bodies activate automatically once the symbol resolves at import time. Each stub contains a comment block referencing the requirements it will eventually cover.

This is NOT a violation of the no-stub rule — these stubs are explicitly required by VALIDATION.md §"Wave 0 Requirements" and PLAN.md §`<truths>`.

## Next Plan

**06-02** (backend GET→POST method change on `/agent/stream`):
- Mutates 3 lines in `src/job_rag/api/routes.py` (decorator method, handler signature, generator reference)
- Updates 3 call sites in `tests/test_api.py` from `client.get(..., params=...)` to `client.post(..., json={"query": ...})`
- Regenerates `frontend/openapi.snapshot.json` + `frontend/src/api/types.ts` via `npm run codegen:snapshot`
- The DebugAgentStream Pitfall H closure shipped in this plan (06-01 Task 3) means the dev probe will continue working the moment Plan 02 flips the backend; no second touch needed

## Self-Check: PASSED

### Created files exist

```
FOUND: frontend/src/components/ui/collapsible.tsx
FOUND: frontend/src/components/ui/textarea.tsx
FOUND: frontend/src/components/chat/types.ts
FOUND: frontend/src/test/sseMockUtils.ts
FOUND: frontend/src/test/useChatStream.test.tsx
FOUND: frontend/src/test/ToolChip.test.tsx
FOUND: frontend/src/test/ChatComposer.test.tsx
FOUND: frontend/src/test/ChatTranscript.test.tsx
```

### Commits exist in git history

```
FOUND: e8fbf2d (Task 1: shadcn primitives install)
FOUND: 3c5e323 (Task 2: types.ts + app.css blink keyframes)
FOUND: bf94d6b (Task 3: sseMockUtils + 4 test stubs + DebugAgentStream Pitfall H fix)
```

### Modified files contain expected changes

```
frontend/src/app.css: @keyframes blink present (count=1), prefers-reduced-motion present (count=1), @theme inline unchanged (count=1)
frontend/src/routes/DebugAgentStream.tsx: old "{message:" pattern absent (count=0), new "{query})" pattern present (count=1)
```
