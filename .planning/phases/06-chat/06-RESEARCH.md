# Phase 6: Chat - Research

**Researched:** 2026-05-23
**Domain:** Streaming chat UI (fetch + ReadableStream SSE consumption) on top of an existing typed Pydantic AgentEvent contract, rendered in React 19 + Vite + Tailwind v4 + shadcn/ui (radix-nova style)
**Confidence:** HIGH for backend method change + frontend ReadableStream consumption + AbortController lifecycle + shadcn primitive install; MEDIUM for smart-autoscroll mechanics (taste/perf-sensitive) and React 19 StrictMode AbortError handling nuances (covered by guard); LOW on none.

## Summary

CONTEXT.md is exceptionally well-developed (32 locked decisions across A–L sections, all carried forward from Phase 4/5 precedent; UI-SPEC.md is 1600+ lines with verbatim JSX skeletons for all 6 components). This RESEARCH.md's job is **NOT** to re-litigate locked decisions but to:

1. Confirm the version-pinned dependency set is current and the install command produces files compatible with the existing `radix-nova` shadcn preset on disk.
2. Surface React-19-specific implementation pitfalls around `fetch + ReadableStream + AbortController + useEffect cleanup` that CONTEXT.md flagged but didn't fully resolve.
3. Provide concrete, copy-able TypeScript snippets for the parts that the planner / executor will need to write fresh: `useChatStream`, `streamAgent`, AbortController-in-ref lifecycle, smart-autoscroll via IntersectionObserver, cold-start timer cleanup, AbortError vs network-error vs ErrorEvent triage.
4. Validate the GET→POST migration approach against the EventSource-can't-attach-Bearer-headers constraint (CHAT-01 literal) and confirm `fetch + ReadableStream` is the only viable path.
5. Identify the Validation Architecture / Nyquist sampling per CHAT requirement so the planner can wire automated acceptance gates from Wave 0.

**Primary recommendation:** Build the planner around 4 plans matching CONTEXT D-K closure (estimate confirmed in §"Plan Grain Recommendation" below): (1) Wave 0 foundation + 2 shadcn primitive installs + 5 test stub files + DebugAgentStream body-key fix; (2) backend GET→POST method change + 4 test call-site rewrites + OpenAPI snapshot regen; (3) frontend `useChatStream` hook + `streamAgent` typed helper + activated hook tests; (4) frontend presentation components (ChatTranscript / ChatMessage / ToolChip / ChatComposer / ChatEmptyState) + cursor CSS + Chat.tsx route composition + activated component tests; UAT runbook can fold into Plan 4 close-out or live as Plan 5 depending on Adrian's preference for separating live-Azure verification from local test green.

## User Constraints (from CONTEXT.md)

### Locked Decisions

Verbatim from `06-CONTEXT.md` `<decisions>` block — DO NOT re-litigate. All 32 decisions (D-01 through D-32) are locked. Highlights for planner enforcement:

**A. Backend method change**
- **D-01:** `/agent/stream` switches from `GET ?q=...` to `POST {query: string}` body. NO support-both path. NO GET fallback.
- **D-02:** Reuse the existing `AgentQuery(BaseModel) { query: str }` Pydantic model at `routes.py:340-341`. Decorator changes `@router.get` → `@router.post`; parameter signature changes `q: str` → `payload: AgentQuery`; body reference `q` → `payload.query`. All other handler internals (timeout, active_streams, error frames, ping_message_factory, shutdown_event, defensive headers) stay identical.
- **D-03:** Test call sites in `tests/test_api.py` lines 165-186, 342-366 switch from `client.get("/agent/stream", params={"q": "..."})` → `client.post("/agent/stream", json={"query": "..."})`; streaming-context call from `"GET", "/agent/stream?q=test"` → `"POST", "/agent/stream"` with JSON body.
- **D-04:** Regenerate `frontend/openapi.snapshot.json` via `npm run codegen:snapshot`. Sequence backend-then-frontend OR co-land in one PR.
- **D-05:** `agent_limit` (10/min) stays attached — no change.

**B. Transcript & message model**
- **D-06:** Linear-dense flat thread, NOT ChatGPT bubbles. `text-[10px] uppercase tracking-wider text-muted-foreground` role labels.
- **D-07:** `TranscriptItem` discriminated union with `kind: 'user-message' | 'assistant-text' | 'tool-call' | 'error'`; `id: crypto.randomUUID()` per item.
- **D-08:** Interleaved tool calls + text segments — each turn's response is a list of items, not one bubble.
- **D-09:** Append-only within session, ZERO persistence (no localStorage, no IndexedDB).

**C. Tool-call chip UX**
- **D-10:** Collapsed by default, click anywhere on chip header to expand. shadcn `collapsible` primitive (NEW install).
- **D-11:** Args: `JSON.stringify(args)` compact for collapsed preview (`truncate`); `JSON.stringify(args, null, 2)` for expanded view.
- **D-12:** Output truncation: literal `.slice(0, 200)` + `'…'` ellipsis. "Show full output" → shadcn `Dialog`.
- **D-13:** Running spinner: `<span className="animate-pulse">·</span>` while `output === null`.

**D. Composer UX**
- **D-14:** Sticky-bottom multi-line `<Textarea>` (NEW shadcn install) with `min-h-[44px] max-h-[200px]` auto-grow.
- **D-15:** Enter submits, Shift+Enter inserts newline. No Cmd/Ctrl+Enter binding.
- **D-16:** Stop button replaces Send during streaming. `AbortController.abort()` → fetch terminates → useChatStream catches AbortError → marks current `assistant-text` `stopped: true` + suffix `(stopped)`.
- **D-17:** Smart autoscroll: default-on; suppressed when user scrolls up; re-engaged on user scroll-to-bottom OR new submit.

**E. Streaming UX states**
- **D-18:** Pre-first-token = `Thinking…` + 3 animated dots.
- **D-19:** Cold-start at 10s elapsed → swap label to `Warming up the agent — this can take ~4 minutes after idle`. Em-dash literal U+2014.
- **D-20:** HeartbeatEvents silently consumed (no UI surface); they DO clear the cold-start timer.
- **D-21:** Blinking caret `▍` (U+258D) at end of streaming text; 1s blink cycle, `step-end` easing; respects `prefers-reduced-motion` (cursor stays solid).

**F. Error rendering**
- **D-22:** Inline destructive shadcn `Alert` at message position where stream stopped. Composer re-enables. No retry button in v1.
- **D-23:** Per-reason copy verbatim for all 4 `ErrorEvent.reason` Literals (`agent_timeout`, `shutdown`, `llm_error`, `internal`).
- **D-24:** Network errors (fetch throws before any event) = top-of-route destructive Alert. Per-HTTP-code copy table.

**G. Empty state**
- **D-25:** EmptyState wraps Phase 4 `<EmptyState>`; 4 sample query chips (Badge variant="outline") that **PRE-FILL** composer; NO auto-submit.

**H. Cancellation**
- **D-26:** Single in-flight stream at a time. AbortController in `useRef`. `useEffect` cleanup runs `abort()` on unmount.

**I. Component tree**
- **D-27:** `components/chat/` feature folder (7 files); 2 net-new shadcn primitives (`collapsible`, `textarea`); `frontend/src/api/agent.ts` filled; `frontend/src/routes/Chat.tsx` replaces PhasePlaceholder; `frontend/src/routes/DebugAgentStream.tsx` body-key fix `{message}` → `{query}`.
- **D-28:** `useChatStream` hook signature returns `{ items, isStreaming, coldStart, submit, stop, networkError }`. Hook owns state + lifecycle + abort + cold-start timer; presentation components are state-free.

**J. Tests**
- **D-29:** Vitest + RTL + mock fetch returning ReadableStream of SSE frames. 4 new test files in `frontend/src/components/chat/__tests__/` or `frontend/src/test/`.
- **D-30:** Backend tests = 3 call-site updates in `tests/test_api.py`. No new test classes.

**K. Aesthetic**
- **D-31:** No bubbles, no avatars, no time-tooltips. Density target: 4–6 messages in 600px viewport.

**L. Accessibility**
- **D-32:** `<ol role="log" aria-live="polite" aria-relevant="additions">`. Tool chips: `aria-expanded` + `aria-controls`. Composer: `aria-label="Ask the agent"`. Cursor: `aria-hidden`. Stop button: `aria-label="Stop streaming response"`.

### Claude's Discretion

Verbatim from CONTEXT.md `### Claude's Discretion` and UI-SPEC §17 (already resolved):

- **Lucide icons resolved (UI-SPEC §17 #1, #7):** `ArrowRight` for tool-call chip, `Square` for Stop button, `Send` for Send button, `ChevronRight` for chip expand/collapse, `MessageSquare` for EmptyState, `AlertCircle` for error Alerts.
- **Blink timing resolved (UI-SPEC §17 #2):** 1s cycle (500ms visible / 500ms hidden), `step-end` easing.
- **`<pre>` max-width resolved (UI-SPEC §17 #3):** `max-w-full` + `overflow-x-auto`.
- **Autoscroll mechanism resolved (UI-SPEC §17 #4):** `scrollIntoView({behavior: 'smooth', block: 'end'})` on bottom-sentinel ref.
- **Heartbeat rendering resolved (UI-SPEC §17 #5):** silent in Chat.tsx, visible in DebugAgentStream.tsx (existing asymmetry preserved).
- **Sample query phrasing resolved (UI-SPEC §6e + §17 #6):** 4 verbatim chips locked. Planner may swap any single chip during UAT if corpus shape produces zero results, but ships v1 with the locked 4.
- **Markdown rendering (UI-SPEC §17 #8):** NO in v1; deferred to Phase 8. Render via `whitespace-pre-wrap` only.
- **Syntax highlighting in tool outputs (UI-SPEC §17 #9):** NO in v1.
- **Composer padding (UI-SPEC §17 #10):** `py-3` (12px) — 1-token spacing exception, documented.
- **Composer & route widths (UI-SPEC §17 #11, #12, #13):** Route = `max-w-3xl h-[calc(100vh-3rem)]`. Composer inherits container width.
- **Cursor glyph (UI-SPEC §17 #14):** `▍` (U+258D).
- **Tool chip header padding (UI-SPEC §17 #15):** `p-2` (8px).
- **Args delimiter for collapsed (UI-SPEC §17 #16):** `JSON.stringify(args)` (no `null, 2`) + `truncate`.
- **Network error Alert dismissal (UI-SPEC §17 #17):** auto-dismiss on next successful submit; NO manual close button.

**Planner discretion items (not yet resolved):**

- **Plan grain** (CONTEXT.md "Phase 6 commit grain" Claude's Discretion): Phase 5 used 6 plans. Phase 6 likely needs 4. Recommendation in §"Plan Grain" below.
- **Test file location:** `frontend/src/components/chat/__tests__/` (Jest-style colocation) OR `frontend/src/test/` (mirrors Phase 4 D-19 pattern — `AppShell.test.tsx` lives at `frontend/src/test/AppShell.test.tsx`). Phase 4 precedent points to `frontend/src/test/` per the existing `setup.ts` + `AppShell.test.tsx` shape. **Recommend: `frontend/src/test/chat.<component>.test.tsx`** — matches Phase 4 file naming.
- **Test file granularity:** D-29 names 4 test files. Confirmed; no consolidation recommended.

### Deferred Ideas (OUT OF SCOPE)

Verbatim from CONTEXT.md `<deferred>`:

- Conversation history persistence (CHAT2-01, v2)
- Multi-turn agent memory (v2)
- Chat branching / forking (CHAT2-02, v2)
- Export chat as Markdown (CHAT2-03, v2)
- Markdown rendering in assistant text (Phase 8 polish)
- Syntax highlighting in tool outputs (defer)
- Retry button on error events (defer)
- "Copy to clipboard" on assistant response (Phase 8)
- Keyboard shortcuts `/`, `G+C`, `Esc` (Phase 8)
- shadcn/ai or assistant-ui registry blocks (build from primitives instead)
- Conversation download as JSON (v2)
- "Regenerate response" button (v2)
- Selective tool cancellation (mid-stream) — Stop aborts the entire stream
- Always-warm ACA (out of budget — Phase 8 polish may revisit)
- Phase 04.1 follow-ups (independent)
- Phase 5 polish candidates (independent)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CHAT-01 | Chat React page consumes `/agent/stream` via `fetch` + `ReadableStream` (EventSource cannot attach Bearer JWT headers) | §"GET→POST Validation" confirms `fetch + ReadableStream` is the only viable path; CHAT-01 is satisfied by the existing Phase 4 D-16 `readSSEStream` helper (no rewrite) + `streamAgent` typed wrapper in `frontend/src/api/agent.ts`; §"Code Examples" shows the integration. |
| CHAT-02 | `token` events render incrementally into the assistant bubble with smooth text append | §"Code Examples — useChatStream Hook" shows the dispatch reducer pattern for `TokenEvent` → append to current `assistant-text` item content; §"Streaming Render Performance" addresses 30–80 tokens/s cadence without React jank. |
| CHAT-03 | `tool_start` events render as a collapsed chip showing tool name + JSON-preview of args | §"Code Examples — ToolChip render" + UI-SPEC §6c JSX skeleton + CONTEXT D-10/D-11 fully cover. shadcn `collapsible` primitive install verified compatible with `radix-nova` preset. |
| CHAT-04 | `tool_end` events expand the chip with an output preview (truncated ≥ 200 chars with "expand" affordance) | UI-SPEC §6c (`output.slice(0, 200) + '…'` + Dialog) + CONTEXT D-12 fully cover. Dialog primitive already on disk from Phase 4. |
| CHAT-05 | `final` event marks the assistant bubble complete and re-enables the input | §"Code Examples — useChatStream Hook" shows `FinalEvent` → set `isStreaming: false`, mark current `assistant-text` `streaming: false`, composer re-enables. Submitting during streaming is blocked by `disabled={isStreaming || disabled}` on the Textarea per UI-SPEC §6d. |
| CHAT-06 | Single-turn only in v1 — refreshing the page clears the conversation; no history persistence | CONTEXT D-09 enforces React-state-only. `useChatStream` uses `useState`/`useReducer` exclusively — no `localStorage.setItem`, no `IndexedDB` invocations anywhere in `components/chat/`. UAT verifies via DevTools Application tab empty for chat-related keys. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP method + body validation (GET→POST switch) | API / Backend | — | Method semantics live in the FastAPI decorator; Pydantic `AgentQuery` body validation owned by the API layer. Frontend just sends `Content-Type: application/json`. |
| LangGraph agent execution (unchanged) | API / Backend | Service layer (LangGraph) | Backend internals (timeout wrap, active_streams tracking, error frames, ping factory, shutdown_event) all stay in `routes.py` and `agent/stream.py`. No frontend involvement. |
| SSE event serialization + heartbeat + shutdown drain (unchanged) | API / Backend | — | sse-starlette + `EventSourceResponse` + Pydantic discriminated union — all live in `routes.py` + `sse.py`. Frontend consumes the wire format only. |
| Authenticated SSE consumption (`fetch + ReadableStream`) | Frontend (Browser SPA) | — | EventSource can't attach Bearer headers (verified). `fetch` + `response.body.getReader()` + `TextDecoder` happens entirely in the browser. Backend has no notion of "Bearer-via-fetch" vs "Bearer-via-XHR" — both are HTTP. |
| Transcript state + AbortController + cold-start timer | Frontend (Browser SPA) | — | Pure UI concern. `useChatStream` hook owns; no backend touchpoint. |
| Tool-call chip rendering (collapse/expand, args preview, output truncation, full-output Dialog) | Frontend (Browser SPA) | — | shadcn primitives + React state. No backend involvement. |
| Composer (multi-line Textarea, Enter/Shift+Enter, Stop button) | Frontend (Browser SPA) | — | DOM event handling + AbortController.abort() — pure browser. |
| Smart autoscroll (IntersectionObserver) | Frontend (Browser SPA) | — | DOM API; runs locally. |
| Per-reason error rendering | Frontend (Browser SPA) | API / Backend | Backend emits typed `ErrorEvent.reason` (closed Literal set per Phase 1 D-19); frontend looks up `ERROR_TITLE[reason]` + `ERROR_BODY[reason]` from local copy tables (D-23). Two-tier shared contract. |
| Cold-start "Warming up…" copy | Frontend (Browser SPA) | — | UI affordance; backend has no notion of "warmth". Frontend's 10s timer is purely client-side. |
| 60s timeout enforcement | API / Backend | — | `asyncio.timeout(60)` in `routes.py` — emits `ErrorEvent(reason="agent_timeout")`. Frontend just renders the typed error. |
| Heartbeat emission (15s) | API / Backend | — | sse-starlette `ping_message_factory` — emits typed `HeartbeatEvent`. Frontend silently consumes per D-20 (in production Chat; visible in DebugAgentStream). |
| Auth (`get_current_user_id` AUTH-06 single-user guard) | API / Backend | — | Phase 4 D-08 — single-place guard; Phase 6 inherits unchanged. |
| OpenAPI snapshot regen | Build tool (codegen) | — | `openapi-typescript` reads `frontend/openapi.snapshot.json` and emits `frontend/src/api/types.ts`. Frontend imports the resulting types. |

**No misassignment risk:** Every capability is clearly tier-owned. Chat is structurally a thin SPA-side wrapper around a typed backend stream.

## Standard Stack

### Core (already installed, no changes)

| Library | Version (on disk) | Purpose | Why Standard |
|---------|------------------|---------|--------------|
| React | 19.2.6 [VERIFIED: package.json] | UI library | Project frozen at React 19; matches Phase 4 D-17 + STACK §1. |
| TypeScript | 5.9.x [VERIFIED: package.json] | Static types | Strict mode + bundler resolution; consistent with Phases 4/5. |
| Vite | 8.0.12 [VERIFIED: package.json] | Dev server + bundler | Frozen frontend; Phase 4 chose v8 for React 19 + Tailwind v4 first-class support. |
| Tailwind CSS | 4.3.x [VERIFIED: package.json] | Utility CSS | `@tailwindcss/vite` integration; tokens declared in `frontend/src/app.css` `@theme inline` block. |
| `@tanstack/react-query` | 5.100.x [VERIFIED: package.json] | Server state (NOT used for chat streaming) | Phase 5 uses for dashboard widgets; Phase 6 chat uses local React state for transcript because TanStack Query has no native SSE/ReadableStream subscription primitive. Per CONTEXT canonical_refs SHEL-03 note: "Phase 6 uses local React state for the streaming transcript because TanStack Query doesn't natively handle SSE." [VERIFIED: TanStack Query docs — no `useStreamQuery` primitive as of v5.100]. |
| `@azure/msal-react` + `@azure/msal-browser` | 5.4.x + 5.11.x [VERIFIED: package.json] | Auth | `authedFetch` Phase 4 D-13 wraps; Phase 6 uses AS-IS. |
| shadcn/ui CLI | 4.7.x [VERIFIED: package.json] | Component installer | Reads `components.json` (`radix-nova` style on disk); `add` subcommand resolves to official registry. Phase 5 Pitfall 8 enforcement: NO `--style` flag on `add`. |
| `lucide-react` | 1.16.x [VERIFIED: package.json] | Icons | `ArrowRight`, `ChevronRight`, `Send`, `Square`, `MessageSquare`, `AlertCircle` all already exported (icons used in Phase 4 + 5 + 6). |
| Vitest + @testing-library/react | 3.2.x + 16.3.x [VERIFIED: package.json] | Tests | Phase 4 testing baseline; Phase 6 D-29 reuses. |

### Net-New (Phase 6 installs)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@radix-ui/react-collapsible` (transitive via `radix-ui` per Feb 2026 unified package) | 1.1.12 [VERIFIED: npm registry as of 2026-05-09; latest stable] | Collapsible primitive backing shadcn `collapsible` component | Tool chip expand/collapse per D-10; official shadcn registry component; no third-party alternative considered (Registry Safety per UI-SPEC §16). |
| (textarea has no Radix peer dep — pure CVA + Tailwind) | n/a | Multi-line input | Composer per D-14; official shadcn registry component. |

**Note on Feb 2026 shadcn unified `radix-ui` package change** [VERIFIED: https://ui.shadcn.com/docs/changelog/2026-02-radix-ui]: As of February 2026, the `new-york` style and successor styles (including `radix-nova`, which is what `frontend/components.json` declares) import from the unified `radix-ui` package instead of individual `@radix-ui/react-*` packages. The project already has `"radix-ui": "^1.4.3"` listed in `package.json` (verified). Running `npx shadcn@latest add collapsible textarea` will install components that import from `radix-ui` (collapsible) and pure CSS (textarea); no separate `@radix-ui/react-collapsible` install needed. [VERIFIED: package.json line `"radix-ui": "^1.4.3"`.]

### Alternatives Considered (and rejected)

| Instead of | Could Use | Tradeoff | Decision |
|------------|-----------|----------|----------|
| Build chips from shadcn primitives | shadcn/ai or assistant-ui pre-built chat blocks | Pre-built blocks land faster but undermine the Linear-dense aesthetic + force a specific visual that doesn't match Phase 4 §4 color tokens | REJECTED per CONTEXT.md Out of Scope (line 56) + UI-SPEC §16 — full control over aesthetic. |
| `fetch + ReadableStream` | Native `EventSource` API | EventSource can't attach `Authorization: Bearer <jwt>` headers (W3C spec limitation) — see §"GET→POST Validation" | REJECTED — incompatible with Phase 4 D-13 `authedFetch` Bearer pattern. CHAT-01 literal mandates `fetch + ReadableStream`. |
| Custom CSS keyframe blink for cursor | shadcn `animate-pulse` repurposed | `animate-pulse` is opacity ramp (smooth fade); cursor blinks should be hard on/off (`step-end`) — wrong animation curve | REJECTED — UI-SPEC §6f + §10 lock `@keyframes blink` with `step-end`. |
| `react-markdown` for assistant text | Plain `<p>` + `whitespace-pre-wrap` | `react-markdown` ~10 KB gzipped; agent responses occasionally use backticks/lists which would render prettier | REJECTED FOR V1 — UI-SPEC §17 #8 defers to Phase 8 polish. |
| `react-intersection-observer` lib | Native `IntersectionObserver` API + ref | Library adds ~3 KB; native API works in all modern browsers (Phase 4 target = evergreen) | REJECTED — use native; one less dep. |
| `useReducer` for transcript items | `useState` for transcript items + ref | useReducer reduces prop drilling of dispatch functions; but Phase 6 hook is the single owner, no drilling needed | RECOMMEND: **`useReducer` for items, `useState` for `isStreaming`/`coldStart`/`networkError`** — see §"Code Examples — useChatStream Hook" rationale. |

### Installation (Phase 6 commands)

```bash
cd frontend && npx shadcn@latest add collapsible textarea
```

**Bare invocation** — NO `--style`, `--base-color`, `--icon-library`, or `--registry` flags. The existing `frontend/components.json` declares `radix-nova` + `neutral` + `lucide`; passing flags risks clobbering. (Phase 5 Pitfall 8 enforcement.) The `add` subcommand reads `components.json` and writes into `aliases.ui` (`@/components/ui/`).

**Verification commands** (to run post-install):
```bash
cd frontend
test -f src/components/ui/collapsible.tsx && echo "collapsible installed"
test -f src/components/ui/textarea.tsx && echo "textarea installed"
grep -q "from \"radix-ui\"" src/components/ui/collapsible.tsx && echo "uses unified radix-ui import" || echo "uses individual @radix-ui/react-collapsible — file an issue"
```

**Version verification** [VERIFIED 2026-05-23]:
- `@radix-ui/react-collapsible` latest 1.1.12 (2026-05-09 publish) per https://www.npmjs.com/package/@radix-ui/react-collapsible
- `radix-ui` unified package (per Feb 2026 changelog) already pinned `^1.4.3` in `frontend/package.json`
- `shadcn` CLI `^4.7.0` already pinned in `frontend/package.json` — compatible with `radix-nova` style add commands

## Architecture Patterns

### System Architecture Diagram

```
                                          ┌──────────────────────────────────────┐
                                          │  Browser (SPA) — Chat surface        │
                                          │                                      │
   User types ─Enter─→ ChatComposer ───────┼─► useChatStream.submit(query)        │
                                          │                                      │
                                          │  1. dispatch APPEND_USER_MESSAGE     │
                                          │  2. dispatch APPEND_ASSISTANT_TEXT   │
                                          │     (content='', streaming=true)     │
                                          │  3. setIsStreaming(true)             │
                                          │  4. setColdStart(false)              │
                                          │  5. setTimeout(10000) for cold-start │
                                          │  6. abortControllerRef = new AC      │
                                          │  7. authedFetch('/agent/stream',     │
                                          │       POST, JSON, signal)            │
                                          │                                      │
                                          └──────────────────┬───────────────────┘
                                                             │
                                                             ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │  Network — HTTPS POST to /agent/stream                                       │
   │  Headers: Authorization: Bearer <jwt>, Content-Type: application/json        │
   │  Body: {"query": "...user text..."}                                          │
   └─────────────────────────────────────────────────────────────────────────────┘
                                                             │
                                                             ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │  Azure Container Apps (Envoy ingress)                                        │
   │   → 60s asyncio.timeout wraps stream_agent()                                 │
   │   → 15s ping_message_factory injects HeartbeatEvent                          │
   │   → defensive X-Accel-Buffering: no + Content-Encoding: identity headers     │
   └─────────────────────────────────────────────────────────────────────────────┘
                                                             │
                                                             ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │  FastAPI /agent/stream (routes.py:364-474)                                   │
   │                                                                              │
   │   @router.post(/agent/stream)   ← Phase 6 D-01 change from @router.get       │
   │   async def agent_stream(request, payload: AgentQuery):  ← D-02 signature    │
   │     async for event in stream_agent(payload.query):  ← D-02 body ref change  │
   │       yield to_sse(event)                                                    │
   │                                                                              │
   │   On error: emits typed ErrorEvent(reason=...) before close                  │
   │   On shutdown: yields ErrorEvent(reason='shutdown') then re-raises           │
   └─────────────────────────────────────────────────────────────────────────────┘
                                                             │
                                                             ▼
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │  agent/stream.py stream_agent()                                              │
   │                                                                              │
   │   yields TokenEvent(content='...')                                           │
   │   yields ToolStartEvent(name='search_jobs', args={'query': '...'})           │
   │   yields ToolEndEvent(name='search_jobs', output='[...]')                    │
   │   yields TokenEvent(content='...')   (interleaved synthesis)                 │
   │   yields FinalEvent(content='...')                                           │
   └─────────────────────────────────────────────────────────────────────────────┘
                                                             │
                                                             ▼
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │  Browser (SPA) — useChatStream consuming                                     │
   │                                                                              │
   │   for await (const event of readSSEStream(response)):                        │
   │     // First event clears cold-start timer + sets coldStart=false            │
   │     switch (event.type):                                                      │
   │       'token'     → dispatch APPEND_TOKEN({assistantId, content})            │
   │       'tool_start'→ dispatch CLOSE_CURRENT_TEXT + APPEND_TOOL_START          │
   │       'tool_end'  → dispatch UPDATE_TOOL_OUTPUT + (next token reopens text)  │
   │       'heartbeat' → silently consume; clear cold-start timer                 │
   │       'error'     → dispatch CLOSE_CURRENT_TEXT + APPEND_ERROR; setIsStreaming(false) │
   │       'final'     → dispatch CLOSE_CURRENT_TEXT; setIsStreaming(false)       │
   │                                                                              │
   │   On Stop click: abortControllerRef.current.abort()                          │
   │   On unmount: useEffect cleanup runs abortControllerRef.current?.abort()     │
   │   On network failure: setNetworkError({status, message})                     │
   └──────────────────────────────────────────────────────────────────────────────┘
                                                             │
                                                             ▼
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │  React re-render — ChatTranscript reads items[]                              │
   │                                                                              │
   │   ChatMessage renders for kind='user-message' | 'assistant-text' | 'error'   │
   │   ToolChip renders for kind='tool-call'                                      │
   │   Smart autoscroll: scrollIntoView() on bottom sentinel IF sentinel-visible  │
   │   Streaming cursor `▍` renders inside current assistant-text whose streaming=true │
   └──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| File | Responsibility |
|------|----------------|
| `src/job_rag/api/routes.py:340-474` | `AgentQuery` model (unchanged) + `/agent/stream` POST handler (Phase 6 D-01 decorator change + D-02 signature change). All other handler internals (timeout, drain, ping factory) unchanged. |
| `src/job_rag/api/sse.py` | AgentEvent discriminated union (unchanged from Phase 1 D-04). Phase 6 reads, does not modify. |
| `src/job_rag/agent/stream.py` | `stream_agent` async iterator (unchanged from Phase 1). Phase 6 reads, does not modify. |
| `tests/test_api.py:165-186, 342-366` | 3 call-site method updates (D-03). |
| `tests/test_sse_contract.py:90-133` | Schema-contract tests stay; any direct method assertions update to POST. |
| `frontend/openapi.snapshot.json` | Regenerated via `npm run codegen:snapshot` after backend lands D-01. |
| `frontend/src/api/types.ts` | Regenerated via `npm run codegen:snapshot` (script reads `openapi.snapshot.json`). |
| `frontend/src/api/agent.ts` | NEW: `streamAgent(query, signal)` typed wrapper around `authedFetch` + `readSSEStream`. |
| `frontend/src/api/authedFetch.ts` | UNCHANGED — supports POST + JSON body via standard fetch API (Phase 4 D-13). |
| `frontend/src/api/readSSEStream.ts` | UNCHANGED — method-agnostic; only upstream fetch method changes (Phase 4 D-16). |
| `frontend/src/routes/Chat.tsx` | REPLACES PhasePlaceholder with composition: `useChatStream` hook + conditional `<ChatEmptyState>` vs `<ChatTranscript>` + always-rendered `<ChatComposer>`. |
| `frontend/src/routes/DebugAgentStream.tsx` | 1-line fix: change `JSON.stringify({ message: query })` → `JSON.stringify({ query })` to match `AgentQuery` model. |
| `frontend/src/components/chat/types.ts` | NEW: `TranscriptItem` discriminated union + `NetworkError` type + `ERROR_TITLE` / `ERROR_BODY` lookup tables (D-23 verbatim). |
| `frontend/src/components/chat/useChatStream.ts` | NEW: state hook owning `useReducer` for items + `useState` for streaming/coldStart/networkError + `useRef` for AbortController + cold-start timer + cleanup on unmount. |
| `frontend/src/components/chat/ChatTranscript.tsx` | NEW: scrollable `<ol role="log">` + smart-autoscroll via IntersectionObserver on bottom sentinel + conditional network-error Alert. |
| `frontend/src/components/chat/ChatMessage.tsx` | NEW: 3 variants (user-message / assistant-text / error) + `<StreamingCursor>` + `<ThinkingDots>` inline subcomponents. |
| `frontend/src/components/chat/ToolChip.tsx` | NEW: Collapsible-wrapped chip + 3 visual states (running / done-collapsed / done-expanded) + full-output Dialog. |
| `frontend/src/components/chat/ChatComposer.tsx` | NEW: sticky-bottom Textarea + auto-grow + Send/Stop button + Enter/Shift+Enter keymap. |
| `frontend/src/components/chat/ChatEmptyState.tsx` | NEW: wraps Phase 4 `<EmptyState>` + 4 sample-query Badges (D-25). |
| `frontend/src/components/ui/collapsible.tsx` | NEW (shadcn install). |
| `frontend/src/components/ui/textarea.tsx` | NEW (shadcn install). |
| `frontend/src/app.css` | APPEND ONLY: `@keyframes blink` + `.animate-blink` utility + `prefers-reduced-motion` carve-out. Do NOT touch the `@theme inline` block. |

### Pattern 1: Custom Hook Owns State + Lifecycle, Presentation is State-Free

**What:** A single custom hook (`useChatStream`) owns every piece of stream state, the AbortController ref, the cold-start timer, and the cleanup-on-unmount effect. Presentation components (`ChatTranscript`, `ChatMessage`, `ToolChip`, `ChatComposer`, `ChatEmptyState`) receive props and render — no `fetch`, no `useState` for stream concerns, no AbortController.

**When to use:** Whenever an interactive surface combines async lifecycle (fetch, timer, abort) with multiple presentation pieces. Phase 5 D-17 `useDashboardFilters` is the precedent — hook owns URL-search-params and defensive coercion; widgets are state-free.

**Why:** Tests can mock the hook (or call the underlying `streamAgent` directly with a fake response) without rendering the whole component tree. Presentation components can be Storybook-rendered with fake item arrays. Aborting a fetch on route navigation is one `useEffect` cleanup in one file — not scattered across the component tree.

### Pattern 2: AbortController in `useRef`, Aborted in `useEffect` Cleanup

**What:** The single in-flight AbortController instance lives in `useRef<AbortController | null>(null)`. Every new `submit()` creates a fresh controller and stores it in the ref. The Stop button calls `abortControllerRef.current?.abort()`. A `useEffect(() => { return () => abortControllerRef.current?.abort() }, [])` cleanup aborts on unmount.

**When to use:** Any time a long-running fetch/stream must be cancellable AND the component might unmount mid-stream (route navigation, error boundary fallback, hot reload).

**Why React 19 specifically:** React 19's StrictMode mounts components twice in development. Without an AbortController-on-cleanup, the first mount's fetch would leak through and yield events into a dispatch that's now orphaned (React doesn't error but warns about state-updates-on-unmounted-component). The AbortController pattern is the canonical fix — `controller.abort()` throws an `AbortError` in the `for await` loop, which the catch block treats as "intentional cancellation, not an error to surface" [VERIFIED: facebook/react#25962 — recommended pattern from React maintainers].

### Pattern 3: Discriminated-Union Items + Reducer for Append Operations

**What:** `TranscriptItem` is a TypeScript discriminated union on `kind`. State updates use `useReducer` with action types like `APPEND_USER_MESSAGE`, `APPEND_ASSISTANT_TEXT`, `APPEND_TOKEN`, `APPEND_TOOL_START`, `UPDATE_TOOL_OUTPUT`, `TOGGLE_TOOL_EXPANDED`, `APPEND_ERROR`, `MARK_STOPPED`, `CLOSE_CURRENT_TEXT`.

**When to use:** When state shape has multiple coherent variants AND high-frequency updates need batching guarantees.

**Why:** `useReducer` batches synchronous dispatches during React 18+ automatic batching; the reducer is a pure function that can be unit-tested independently of React; and the action-name vocabulary documents the state machine. The alternative — `useState<TranscriptItem[]>` with `setItems(prev => [...prev, ...])` — works but spreads stream-mutation logic across the hook body, making the state machine harder to read.

### Pattern 4: Smart Autoscroll via Bottom-Sentinel IntersectionObserver

**What:** A 1×1 invisible `<div ref={bottomSentinelRef} aria-hidden="true" />` sits at the bottom of the transcript `<ol>`. An IntersectionObserver watches the sentinel; when intersecting (user is at the bottom), autoscroll is engaged. New items / new tokens call `bottomSentinelRef.current?.scrollIntoView({behavior: 'smooth', block: 'end'})` IFF the sentinel was last seen as intersecting.

**When to use:** Any append-only log view (chat, terminal, build log, comment thread) where the user can scroll up to review history without being yanked back to the bottom.

**Why:** Polling `scrollTop`/`scrollHeight`/`clientHeight` on every token fires up to 80×/sec — IntersectionObserver fires once on enter/exit. Saves CPU, avoids layout thrash. [VERIFIED: MDN IntersectionObserver docs + tuffstuff9.hashnode.dev/intuitive-scrolling-for-chatbot-message-streaming pattern].

### Anti-Patterns to Avoid

- **`useEffect(() => { fetch(...) }, [])` for the stream:** No AbortController, no React-19-StrictMode handling. UseChatStream's `submit()` is invoked from a click handler, NOT from an effect — bypasses StrictMode double-fire entirely. The only useEffect in `useChatStream` is the unmount-cleanup effect with empty deps.
- **`setItems` with array spread inside the SSE consumer loop:** O(n²) re-allocation per token; React's reconciler batches but the spread itself thrashes GC. Use `useReducer` with `(state, action) => [...state, newItem]` once per *item* (not per *token*); tokens append in-place via reducer-state-mutation on a `Map<id, TranscriptItem>` adapter OR via the standard immutable update on the last item (acceptable at LLM cadence ~30–80 tokens/s).
- **Persisting to localStorage "just in case":** Violates CHAT-06 literal. The hook MUST NOT call `localStorage.setItem` or `indexedDB.open` anywhere. UAT verifies via DevTools Application tab.
- **Reusing the same AbortController across submits:** AbortController is one-shot — once aborted, all signals derived from it are aborted forever. Create a fresh `new AbortController()` per submit.
- **Catching AbortError as a "real" error:** AbortError surfaces when the user clicks Stop or unmounts. Treat it as expected control flow, NOT as `networkError`. The pattern: `catch (err) { if (err.name === 'AbortError') { /* mark stopped, do not setNetworkError */ } else { setNetworkError(...) } }`.
- **Submitting during streaming via keyboard race:** Even with the disabled Textarea, a programmatic submit (`useChatStream.submit()` called from elsewhere) could fire. The hook itself guards: `if (isStreaming) return` at the top of `submit()`. Defense in depth.
- **Using EventSource:** EventSource can't attach `Authorization: Bearer <jwt>` (W3C spec — only `withCredentials` cookie auth). CHAT-01 literal mandates `fetch + ReadableStream`. The Phase 4 D-16 `readSSEStream` helper is the canonical consumer; do not introduce EventSource.
- **`@router.get` + `@router.post` both decorating the handler:** YAGNI per CONTEXT D-01 counterfactual rejection. One method, one OpenAPI op, one rate-limit policy.
- **JSON.parse a partial SSE frame:** The existing `readSSEStream` helper buffers correctly on `\n\n` boundaries (Phase 4 D-16 + Pitfall 5). Do not write a second SSE parser anywhere.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE frame parsing | Custom `Stream` parser splitting on `\n\n` and managing buffer state | Existing `frontend/src/api/readSSEStream.ts` (Phase 4 D-16) | Already shipped, tested (`frontend/src/test/readSSEStream.test.ts`), handles partial-chunk buffering, malformed JSON skip, heartbeat-without-data special case. Re-implementing risks Pitfall 5 (split-mid-frame). |
| Bearer-attached fetch | New fetch wrapper | Existing `frontend/src/api/authedFetch.ts` (Phase 4 D-13) | Already shipped; handles `acquireTokenSilent`, retry-on-401, InteractionRequiredAuthError → redirect, AbortSignal threading. Supports POST + JSON body natively. |
| Auth gate around /chat | New AuthGate | Existing `AuthGate` wraps `/chat` route in App.tsx (Phase 4 D-18) | Unchanged from Phase 4; the route is automatically auth-gated. Phase 6 doesn't touch routing. |
| Empty state primitive | Hand-rolled card with chips | `<EmptyState>` (Phase 4 D-19) composed inside `<ChatEmptyState>` | Reuses the design-tokens-locked primitive; Phase 6 just adds chat-specific copy + sample chips. |
| Collapsible / disclosure widget | Custom show/hide state + ARIA | shadcn `collapsible` primitive (Radix Collapsible) | Radix handles `aria-expanded`, `aria-controls`, keyboard activation (Enter/Space), focus management. Building from scratch = re-implementing 5 a11y concerns. Install via `npx shadcn@latest add collapsible`. |
| Multi-line textarea with auto-grow | Custom textarea + measure-and-resize logic | shadcn `textarea` primitive + 4-line `useEffect` for height auto-grow per UI-SPEC §6d | shadcn ships the styled element with consistent focus rings, disabled states, placeholder styling. Auto-grow is 4 lines of code referenced in UI-SPEC §6d verbatim. |
| Dialog for full tool output | Custom modal + backdrop + focus trap | shadcn `dialog` primitive (Phase 4) | Radix handles focus trap (focus enters DialogContent on open, returns to trigger on close), Escape close, overlay click, ARIA. Already installed. |
| Destructive Alert UI | Custom red-bordered box | shadcn `alert` primitive with `variant="destructive"` (Phase 5) | Already installed (Phase 5 install); locked color tokens; `role="alert"` for screen-reader announce. |
| Discriminated union types for events | Manual type unions in each component | Existing `frontend/src/api/readSSEStream.ts` exports `AgentEvent`, `TokenEvent`, `ToolStartEvent`, `ToolEndEvent`, `HeartbeatEvent`, `FinalEvent`, `ErrorEvent` | Re-export from `components/chat/types.ts`; do NOT re-derive from `components['schemas']`. |
| IntersectionObserver wrapper | `react-intersection-observer` npm dep | Native `IntersectionObserver` + `useRef` + `useEffect` | Native API works in all evergreen browsers; library is ~3 KB for one-line wrapper. Anti-dep. |
| MSAL token refresh on stream | Custom token refresh inside the stream loop | Phase 4 `authedFetch` handles ALL token acquisition before the fetch resolves | If MSAL needs an interactive re-login mid-stream, the stream simply ends with a network-error 401 and the user re-submits. Token refresh during an in-flight stream is out of scope (MSAL silent refresh runs on the next `submit()` call, not mid-stream). |

**Key insight:** Phase 4 D-13/D-16/D-19/D-20 + Phase 5 D-15 + the typed Pydantic AgentEvent contract from Phase 1 D-04 mean Phase 6 has ZERO low-level plumbing left to write. Phase 6 is pure composition + render logic + one backend method-change. No new dependencies beyond 2 shadcn primitives. No new fetch wrapper. No new SSE parser.

## Common Pitfalls

### Pitfall A: React 19 StrictMode Double-Fires Effects — AbortController on Cleanup is Mandatory

**What goes wrong:** In dev mode with React 19 StrictMode (default in Vite's `npm create vite` template), every `useEffect` runs twice on mount. If `useChatStream`'s submit-triggered fetch lived in an effect, it would fire two POSTs to `/agent/stream`, double-charging OpenAI and racing two streams into the same transcript. The first stream would update state for an "unmounted" component on the StrictMode discard, logging React warnings.

**Why it happens:** StrictMode is intentional — it forces developers to write effects that survive re-running. The bug surfaces only in dev; prod is fine. But "fine in prod" is exactly when latent bugs hide.

**How to avoid:**
- `useChatStream.submit()` is called from the Send button's `onClick` handler, NOT from `useEffect`. Click handlers don't double-fire in StrictMode.
- The ONE `useEffect` in `useChatStream` is the unmount-cleanup effect with `[]` deps: `useEffect(() => { return () => abortControllerRef.current?.abort() }, [])`. Returns from a `useEffect` ARE called twice in StrictMode (mount → cleanup → mount → final cleanup), so the abort runs harmlessly on the StrictMode re-mount; the second `new AbortController()` is created on the user's next submit (not on the effect re-run).
- The fetch inside `submit()` uses `abortControllerRef.current.signal`; if a second `submit()` somehow fires while one is in flight, the hook's `if (isStreaming) return` guard at the top of `submit()` rejects the second call.

**Warning signs:**
- Two POST /agent/stream calls visible in DevTools Network tab on a single click.
- React console warning: "Can't perform a React state update on an unmounted component".
- Transcript shows duplicate user-message items.
- OpenAI bill shows 2× the expected query count.

**Verification:** Toggle StrictMode in `main.tsx` (`<React.StrictMode>` wrapper) ON for dev verification; the test in `useChatStream.test.tsx` should pass under StrictMode-true render.

[VERIFIED: facebook/react#25962 + facebook/react#25284 — AbortController-on-cleanup is the React-maintainer-recommended pattern.]

### Pitfall B: AbortError vs Real Network Error — Two Different Code Paths

**What goes wrong:** When the user clicks Stop OR the component unmounts, `abortController.abort()` causes the `for await (const event of readSSEStream(response))` loop to throw an `AbortError`. If the catch block treats this as a `networkError`, the top-of-route Alert will incorrectly say "Server error" or "Can't reach the server" on every Stop click.

**Why it happens:** `AbortError` looks like an exception to typeof-checks. Distinguishing requires `err.name === 'AbortError'` OR `err.code === 'ABORT_ERR'` check.

**How to avoid:**
```typescript
try {
  for await (const event of readSSEStream(response)) {
    // dispatch
  }
} catch (err: unknown) {
  if (err instanceof Error && err.name === 'AbortError') {
    // Intentional cancellation. Mark current item stopped.
    dispatch({ type: 'MARK_STOPPED', assistantId })
    return  // do NOT set networkError
  }
  // Real network failure — set top-of-route Alert
  setNetworkError(classifyNetworkError(err))
} finally {
  setIsStreaming(false)
  if (coldStartTimerRef.current) clearTimeout(coldStartTimerRef.current)
}
```

**Warning signs:**
- Clicking Stop produces a top-of-route "Server error" Alert (incorrect behavior).
- Unit test for `onStop` fails with `networkError !== null`.

### Pitfall C: ReadableStream `getReader().releaseLock()` is Critical on Early Exit

**What goes wrong:** The existing `readSSEStream` helper (Phase 4 D-16) has a `finally { reader.releaseLock() }` block; that's correct. BUT if the caller breaks out of the `for await` loop early (e.g., on error frame received), the underlying `response.body` reader stays locked until garbage collection. Subsequent attempts to abort the fetch may not actually release the underlying connection.

**Why it happens:** ReadableStream locks are per-reader; releasing the reader returns the lock to the stream so future readers (or the abort signal) can act on the underlying stream.

**How to avoid:**
- Trust the existing `readSSEStream` helper (it does the right thing in its `finally`). DO NOT manually `getReader()` in `useChatStream` — only consume via `for await`.
- After `for await` completes (naturally, on error, or on AbortError), `readSSEStream`'s `finally` block runs and releases the reader.
- The `AbortController` signal threaded through `authedFetch` → `fetch` is what actually terminates the underlying TCP connection. The reader release is housekeeping.

**Warning signs:**
- Connection-pool exhaustion on rapid submit/stop cycles in dev.
- DevTools Network tab shows "(canceled)" but the connection lingers in "Established" state in `chrome://net-internals/#sockets`.

**Verification:** Mock-test in `useChatStream.test.tsx` should call `controller.abort()` mid-stream and assert the mock fetch's `signal.aborted === true` AND that the next `submit()` call succeeds without "ReadableStream already locked" errors.

### Pitfall D: Cold-Start Timer Race — User Submits Twice Fast, Timers Stack

**What goes wrong:** User clicks Send → cold-start timer starts. User clicks Stop → timer should be cleared. User clicks Send again → fresh timer starts. If the Stop path doesn't clear the timer, the prior timer fires and incorrectly flips `coldStart: true` on the new stream.

**Why it happens:** `setTimeout` IDs accumulate if not cleared. Stop-then-Send creates two timers if Stop forgets to clear.

**How to avoid:**
- The hook's `stop()` function explicitly clears the timer: `if (coldStartTimerRef.current) clearTimeout(coldStartTimerRef.current); coldStartTimerRef.current = null`.
- The hook's `submit()` function clears any existing timer BEFORE setting a new one: `if (coldStartTimerRef.current) clearTimeout(coldStartTimerRef.current); coldStartTimerRef.current = setTimeout(() => setColdStart(true), 10_000)`.
- The `finally` block in `runStream` also clears the timer (defensive — on any path out, no leftover timer).
- The unmount cleanup effect (Pitfall A) doesn't need to clear the timer because the abort path runs the `finally` first.

**Warning signs:**
- "Warming up…" label flashing for ~10s after a fast stream completes.
- Console shows multiple `setTimeout` IDs (visible if logged for debug).

### Pitfall E: SSE Through Envoy (ACA) Without `Content-Encoding: identity` = Buffered Garbage

**Already mitigated by Phase 1 D-18**, but worth re-flagging for Phase 6 PR review:
- Phase 1 D-18 sets `X-Accel-Buffering: no` + `Content-Encoding: identity` on `/agent/stream`. Phase 6's POST migration MUST preserve these. UI-SPEC + CONTEXT D-02 explicitly call out "All other code inside the handler ... stays identical."
- The `test_no_gzip_middleware` test in `tests/test_api.py` (line 297-309) is a regression guard.
- Live verification: DevTools EventStream tab shows discrete `event: token` frames, not a single buffered response. [PITFALLS.md §6 "EventSource + gzip = buffered garbage" — full pitfall.]

### Pitfall F: ACA Cold-Start "Hang" Without User Feedback

**Already mitigated by D-19** "Warming up…" 10s swap, but worth confirming the UX flow under genuine 225s cold start [memory: aca-cold-start-profile.md]:

1. 0s — user clicks Send → "Thinking…" appears
2. 10s — timer fires → label swaps to "Warming up the agent — this can take ~4 minutes after idle"
3. ~225s — fetch finally resolves, first heartbeat or first token arrives → label clears, real content streams in

**No further user feedback between 10s and 225s** — the label sets honest expectations and the user knows to wait. This is portfolio-positive per CONTEXT.md "specifics" — cold-start honesty is a feature, not a bug.

**Warning sign of regression:** If "Thinking…" never swaps to "Warming up…" during a real cold-start demo, the 10s timer isn't firing — check `useEffect` cleanup is not eating the timer (Pitfall D), check `setTimeout` isn't being called outside the React reconciler context.

### Pitfall G: `npm run codegen:snapshot` Drift — Backend Lands Before Snapshot Regen

**What goes wrong:** Backend lands GET→POST. Frontend's `openapi.snapshot.json` still describes the old GET endpoint. Frontend codegen produces TS types that say `/agent/stream` accepts `q: string` query param — does not match runtime POST body shape. CI's drift-check job (Phase 4 D-14) FAILS LOUD.

**Why it happens:** The snapshot is committed to git; codegen reads from it. If backend changes ship without re-running `npm run codegen:snapshot` (after regenerating `openapi.snapshot.json` from the running backend's `/openapi.json`), drift propagates.

**How to avoid:**
- Plan sequence: backend method change → backend tests green → backend pushed → snapshot regen step → frontend codegen → frontend tests green → frontend pushed. CONTEXT D-04 calls this out: "plans must sequence backend-then-frontend OR co-land in one PR."
- Snapshot regen script in `frontend/package.json`: `"codegen:snapshot": "openapi-typescript ./openapi.snapshot.json -o src/api/types.ts"` (verified in package.json). The snapshot itself needs a separate "fetch openapi.json from running backend" step — Phase 5 plan 05-03 has this pattern via "in-process app.openapi() capture".
- Recommended: plan task uses `python -c "import json; from job_rag.api.app import app; print(json.dumps(app.openapi()))" > frontend/openapi.snapshot.json` to capture; matches Phase 5 plan 05-03 D-04 pattern.

**Warning signs:**
- CI fails with "openapi snapshot drift detected" or similar.
- Frontend TS compilation errors after backend merge.
- `frontend/src/api/types.ts` references symbols the openapi.snapshot.json doesn't contain.

### Pitfall H: DebugAgentStream Body-Key Mismatch (Latent)

**Already in CONTEXT D-01:** DebugAgentStream Phase 4 was scaffolded to POST `{message: query}` (frontend/src/routes/DebugAgentStream.tsx:36-38) but Phase 4 never live-exercised it against the GET-only backend. Phase 6 fixes the latent mismatch by aligning the backend to POST AND updating the debug page's body key from `{message: query}` → `{query}`.

**Why this matters for Phase 6:** If the body-key fix is forgotten, DebugAgentStream will 422 immediately after Phase 6 lands (FastAPI rejects unknown body field). The QA value of the probe page is destroyed precisely when Phase 6 needs it most.

**How to avoid:** D-27 explicitly lists `frontend/src/routes/DebugAgentStream.tsx` in the "files Phase 6 creates/modifies" inventory; the plan executor must verify the 1-line change. Plan checker should grep for `body: JSON.stringify({ message:` (the old shape) in `frontend/src/routes/DebugAgentStream.tsx` and FAIL if found.

### Pitfall I: Network-Error Alert "Auto-Dismiss on Next Successful Submit" Logic

**What goes wrong:** UI-SPEC §17 #17 says network-error Alert auto-dismisses on next successful submit. Implementing this naively: `submit()` clears `networkError` at the top — but if the new submit ALSO fails (real network outage), the user sees the old Alert flash to empty before the new one renders, looking like the click did nothing.

**How to avoid:**
- Clear `networkError` only AFTER the new fetch's `Response` arrives (i.e., after `await authedFetch(...)`). If fetch throws before the Response, the catch block sets the new `networkError` directly and the old one is replaced atomically.
- Pattern:
```typescript
async function submit(query: string) {
  if (isStreaming) return
  // ... append items, set timers ...
  try {
    const response = await authedFetch('/agent/stream', { method: 'POST', body, signal })
    setNetworkError(null)  // <-- only clear on successful Response
    for await (const event of readSSEStream(response)) { ... }
  } catch (err) {
    if (isAbortError(err)) { /* mark stopped */ return }
    setNetworkError(classify(err))  // replaces any prior networkError
  } finally {
    setIsStreaming(false)
    clearColdStartTimer()
  }
}
```

### Pitfall J: Tool-Chip "Show full output" Dialog Open State Tied to Item ID

**What goes wrong:** UI-SPEC §6c JSX skeleton uses `useState(false)` for the Dialog `open` state INSIDE the `ToolChip` component. If two tool chips are expanded simultaneously and the user opens chip A's dialog, then expands chip B and opens chip B's dialog — both dialogs render (Radix allows multiple Dialog instances). The visual appearance is one modal stacked on top of another (acceptable; Radix handles focus correctly).

**How to verify acceptable:** Test `ToolChip.test.tsx` should render TWO ToolChips, expand both, click "Show full output" on both, and assert both Dialogs render without crashing. Visually inspect that the second open clones into the foreground (Radix default behavior).

**No fix needed:** Per UI-SPEC §6c JSX, each ToolChip owns its own dialog state via `useState(false)`. This is the simplest correct pattern. Multi-instance Dialog rendering is intentional.

### Pitfall K: `crypto.randomUUID()` Browser Compatibility

**What goes wrong:** D-07 mandates `crypto.randomUUID()` for `TranscriptItem.id`. This is widely supported in evergreen browsers as of 2026, BUT only on HTTPS or localhost (per browser security policy). On `http://192.168.x.x:5173` (LAN testing), `crypto.randomUUID()` throws `TypeError: crypto.randomUUID is not a function`.

**How to avoid:**
- Vite dev server defaults to `http://localhost:5173` — secure context, works fine.
- For LAN/mobile testing, add `--host` flag (`npm run dev -- --host`) AND test exclusively on `localhost` from a separate browser window with port forwarding, OR use `https-localhost` plugin.
- Production runs on HTTPS via SWA → secure context → works.

**Fallback (not recommended):** `function generateId() { return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) }`. The `Math.random()` fallback is collision-prone; only use as defense-in-depth.

**Decision:** No fallback needed. Document in plan checker that `crypto.randomUUID()` is intentional and verified secure-context-only.

## Runtime State Inventory

**Trigger check:** Phase 6 is NOT a rename / refactor / migration phase. It's a feature build. However, it DOES introduce one backend HTTP-contract change (GET→POST on `/agent/stream`). Let me check each category against this single backend change:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `/agent/stream` is a transient streaming endpoint; nothing is persisted under the GET-vs-POST distinction. No database rows reference the HTTP method. | None. |
| Live service config | **OpenAPI snapshot** (`frontend/openapi.snapshot.json`) is a committed artifact that captures the runtime API surface. It currently describes `/agent/stream` as GET. Must be regenerated after backend D-01 lands. | Run `npm run codegen:snapshot` (after capturing fresh openapi.json from running backend) — covered by D-04. |
| OS-registered state | None — ACA Container App + Envoy + the Container Image don't bake the GET/POST routing into anything at OS level. The route registers at FastAPI startup. | None. |
| Secrets/env vars | None — no env var name references the method. `JOB_RAG_API_KEY`, `OPENAI_API_KEY`, Langfuse keys, MSAL config are all method-agnostic. | None. |
| Build artifacts / installed packages | **`frontend/src/api/types.ts`** is generated from `openapi.snapshot.json`; will be regenerated. **`tests/test_api.py`** has 3 call sites + 1 streaming-context call site (lines 165-186, 342-366) that bake the GET method into test code. **`tests/test_sse_contract.py`** doesn't directly assert method (only schema). | Update 3 test call sites per D-03; regen types.ts; verify test_sse_contract.py stays method-agnostic. |

**Nothing else found:** No Langfuse trace name embeds the method, no Docker tag references the method, no documentation file in `docs/` mentions the GET method as a contract (Phase 8 owns DOCS-03, not yet written).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Vite build, shadcn CLI, npm install | ✓ (Phase 4 verified) | 20.19+ or 22.12+ per Vite 8 reqs | — |
| npm | Package install | ✓ | (matches Node) | — |
| `npx shadcn@latest` | shadcn primitive install | ✓ (works in Phase 4 + 5) | CLI 4.7.x (per package.json) | — |
| `openapi-typescript` | Codegen | ✓ (devDep 7.13.x) | 7.13.0 | — |
| Python 3.12 + FastAPI test runner | Backend test updates | ✓ (Phases 1-5 verified) | 3.12+ | — |
| Running local backend on `localhost:8000` | OpenAPI snapshot regen (optional — in-process capture is the recommended path per Phase 5 plan 05-03) | ✓ optional; preferred path is in-process `app.openapi()` capture | — | In-process Python one-liner suffices. |
| Docker Compose dev stack | Local manual testing of POST | ✓ (Phases 1-5 verified) | — | Not strictly needed for Phase 6 plan execution; tests cover the contract. |

**Missing dependencies:** NONE. All tooling is in place from Phase 4 + 5.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Frontend framework | Vitest 3.2.x + @testing-library/react 16.3.x + @testing-library/jest-dom 6.9.x + jsdom 29.x [VERIFIED: frontend/package.json] |
| Frontend config | `frontend/vite.config.ts` (`test` block) + `frontend/src/test/setup.ts` |
| Frontend quick run | `cd frontend && npm test -- --run` (single pass; `npm test` is watch mode) |
| Frontend full suite | `cd frontend && npm run typecheck && npm run lint && npm test -- --run` |
| Backend framework | pytest 9.0.3+ + pytest-asyncio + httpx 0.28+ + asgi-lifespan 2.x [VERIFIED: pyproject.toml + tests/conftest.py] |
| Backend config | `pyproject.toml` `[tool.pytest.ini_options]` + `tests/conftest.py` (LifespanManager, dependency overrides) |
| Backend quick run | `uv run pytest tests/test_api.py tests/test_sse_contract.py -x` |
| Backend full suite | `uv run ruff check src/ tests/ && uv run pyright src/ && uv run pytest -x` |
| OpenAPI drift check | CI job per Phase 4 D-14 — captures live openapi.json and compares to `frontend/openapi.snapshot.json`; fails on diff. Manual: `npm run codegen:snapshot && git diff --exit-code frontend/src/api/types.ts` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHAT-01 | `/chat` route consumes `/agent/stream` via fetch + ReadableStream with Bearer header | integration (mock fetch returning ReadableStream of SSE bytes) | `cd frontend && npm test -- --run useChatStream` | ❌ Wave 0 — `frontend/src/test/useChatStream.test.tsx` to create |
| CHAT-02 | `token` events render incrementally into assistant bubble | unit (mock fetch yields 3 TokenEvents; assert RTL screen.getByRole('log') text grows) | `cd frontend && npm test -- --run useChatStream` | ❌ Wave 0 (same file as CHAT-01) |
| CHAT-03 | `tool_start` events render as collapsed chip with name + JSON args | unit (mock yields ToolStartEvent; assert ToolChip renders with `aria-expanded="false"` + args preview text) | `cd frontend && npm test -- --run ToolChip` | ❌ Wave 0 — `frontend/src/test/ToolChip.test.tsx` to create |
| CHAT-04 | `tool_end` expands chip output preview with truncation + "Show full" Dialog | unit (mock yields ToolEndEvent with >200 char output; expand chip; assert truncated text `…` + button; click button; assert Dialog opens with full text) | `cd frontend && npm test -- --run ToolChip` | ❌ Wave 0 (same file as CHAT-03) |
| CHAT-05 | `final` event marks bubble complete + re-enables composer; submit-during-stream blocked | unit (mock yields FinalEvent; assert `isStreaming === false` + Textarea not disabled. Second test: assert `submit()` called while `isStreaming === true` is a no-op.) | `cd frontend && npm test -- --run useChatStream && npm test -- --run ChatComposer` | ❌ Wave 0 — `frontend/src/test/ChatComposer.test.tsx` to create |
| CHAT-06 | Refresh clears transcript — no localStorage / IndexedDB residue | unit (assert `useChatStream` never calls `localStorage.setItem` or `indexedDB.open` — spy on the methods; assert 0 calls after multiple submit/stop cycles) + manual UAT (DevTools Application tab inspect) | `cd frontend && npm test -- --run useChatStream` + manual `UAT/M-storage-residue` | ❌ Wave 0 (storage-spy test in useChatStream.test.tsx) |
| D-01 backend method change | `/agent/stream` accepts POST with `{query: string}` JSON body | integration (existing `TestAgentStream` in `tests/test_api.py` after D-03 method update) | `uv run pytest tests/test_api.py::TestAgentStream -x` | ✅ — D-03 updates 3 call sites in existing file |
| D-04 OpenAPI snapshot regen | `openapi.snapshot.json` describes POST contract; `frontend/src/api/types.ts` reflects | integration (CI drift check; type imports compile) | `cd frontend && npm run codegen:snapshot && git diff --exit-code` + `npm run typecheck` | ✅ — existing scripts |
| Pitfall A: React 19 StrictMode | `useChatStream` does NOT double-fire fetch under StrictMode | unit (render hook inside `<React.StrictMode>`; click submit; assert mock fetch called exactly once) | `cd frontend && npm test -- --run useChatStream` | ❌ Wave 0 (same file as CHAT-01) |
| Pitfall B: AbortError handling | Stop click → `networkError === null` AND current item marked `stopped: true` | unit (start stream; call `stop()`; assert state assertions) | `cd frontend && npm test -- --run useChatStream` | ❌ Wave 0 |
| Pitfall D: Cold-start timer cleanup | Rapid submit/stop/submit doesn't leak timers | unit (`vi.useFakeTimers()`; submit → advance 9s → stop → submit → advance 11s → assert coldStart === false) | `cd frontend && npm test -- --run useChatStream` | ❌ Wave 0 |
| Pitfall H: DebugAgentStream body key | DebugAgentStream POSTs `{query}` not `{message}` | unit (existing test or new — check `frontend/src/test/` for DebugAgentStream test) + grep guard in plan checker | `grep -n "body: JSON.stringify({ message:" frontend/src/routes/DebugAgentStream.tsx` (should return 0 lines) | n/a — grep is the check |

### Sampling Rate

- **Per task commit:** `cd frontend && npm test -- --run` (Vitest single pass; targeted file if commit touches one file)
- **Per wave merge:** `cd frontend && npm run typecheck && npm run lint && npm test -- --run` (full frontend) + `uv run pytest tests/test_api.py tests/test_sse_contract.py -x` (backend chat-related)
- **Phase gate:** Full suite green before `/gsd-verify-work`: `cd frontend && npm run typecheck && npm run lint && npm run build && npm test -- --run` + `uv run ruff check && uv run pyright src/ && uv run pytest -x` + OpenAPI snapshot drift check + manual UAT runbook

### Wave 0 Gaps

- [ ] `frontend/src/test/useChatStream.test.tsx` — covers CHAT-01, CHAT-02, CHAT-05, CHAT-06 (storage spy), Pitfalls A, B, D
- [ ] `frontend/src/test/ToolChip.test.tsx` — covers CHAT-03, CHAT-04
- [ ] `frontend/src/test/ChatComposer.test.tsx` — covers CHAT-05 submit blocked, Enter/Shift+Enter, Stop click
- [ ] `frontend/src/test/ChatTranscript.test.tsx` — covers smart-autoscroll, item ordering, network-error Alert conditional render
- [ ] Mock-fetch helper (likely inline in each test or shared in `frontend/src/test/sseMockUtils.ts`) — produces a `Response` with a `ReadableStream` body that yields SSE frames on cue. **Recommendation:** Add `frontend/src/test/sseMockUtils.ts` with `mockSseResponse(frames: AgentEvent[]): Response` helper. Phase 4 readSSEStream tests already use a similar pattern in `frontend/src/test/readSSEStream.test.ts`; recommend extracting to shared util to avoid duplication.
- [ ] Test stubs activate as plans land per the Phase 1/4/5 precedent: each test guards `import.fail` and `mock target missing` so they skip-clean in Wave 0 and activate the moment downstream plans land the target symbols.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Phase 4 D-07 fastapi-azure-auth 5.x `B2CMultiTenantAuthorizationCodeBearer` — unchanged. Phase 6 POST inherits the same `Depends(require_api_key), Depends(agent_limit)` chain as the GET version. |
| V3 Session Management | yes | Phase 4 D-06 MSAL `sessionStorage` cache — unchanged. Phase 6 doesn't introduce a new auth surface. |
| V4 Access Control | yes | Phase 4 D-08 AUTH-06 single-user `oid` guard via `get_current_user_id` Depends — unchanged. Phase 6's POST goes through the same dependency tree. |
| V5 Input Validation | yes | Pydantic `AgentQuery(query: str)` validates request body shape. Phase 6 reuses existing model. No new fields. Length-cap consideration: `str` has no built-in max in Pydantic; the agent's own `asyncio.timeout(60)` bounds compute. Add a soft `max_length=10000` to `AgentQuery.query` as a defense-in-depth IF a future request brings copy-pasted JD spam — out of v1 scope but flagged. |
| V6 Cryptography | n/a | No new crypto. JWT validation handled by `fastapi-azure-auth`. AbortController + sessionStorage handled by browser APIs. |
| V7 Error Handling and Logging | yes | Phase 1 D-19 `_sanitize` helper truncates ErrorEvent.message to 200 chars + strips newlines — unchanged. Frontend D-23 lookup tables (ERROR_TITLE / ERROR_BODY) never display raw backend internals to the user (except `internal` reason which falls through to `_sanitize`d message). |
| V8 Data Protection | yes | CHAT-06 literal — NO transcript persistence. `useChatStream` MUST NOT call `localStorage.setItem` or `indexedDB.open`. Verified by storage-spy unit test (CHAT-06 in Test Map). |
| V12 Files and Resources | n/a | No file upload in chat. (Phase 7 handles resume PDF upload.) |
| V13 API and Web Services | yes | OpenAPI snapshot drift check (Phase 4 D-14) catches API contract changes. Phase 6 changes the method; CI must flag for human review. |

### Known Threat Patterns for FastAPI POST + SSE + React SPA + MSAL

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Bearer token leaked via XSS exfiltration of sessionStorage | Information Disclosure | Phase 4 D-06: sessionStorage (tab-scoped); React's escape-by-default prevents XSS in component output; user-typed query is rendered via `{item.content}` (escaped), never `dangerouslySetInnerHTML`. |
| CSRF on POST `/agent/stream` | Tampering | Bearer JWT in Authorization header (NOT cookie) is immune to CSRF — third-party origin's `<form>` can't set arbitrary headers. CORS allowlist (Phase 1 D-26) excludes unknown origins. |
| Prompt injection via composer text | Tampering / Elevation | The agent's `_sanitize_delimiters` helper (existing Phase 1) defends. Frontend treats user input as data, NOT instructions. |
| Stack trace leaked in ErrorEvent | Information Disclosure | Phase 1 D-19 `_sanitize` truncates + strips newlines. Frontend D-23 falls through to `_sanitize`d message for `internal` reason only. |
| AccessDenied bypass via deep-link | Elevation | Phase 4 D-18 AuthGate wraps `/chat` route; AUTH-06 guard at backend rejects non-Adrian `oid` before route handler. Defense-in-depth. |
| Stop button DoS (rapid submit/stop cycles consume OpenAI quota) | Denial of Service | Phase 1 D-25 `agent_limit` 10/min per-IP rate limit. Single user can't burst more than 10 streams/min regardless of how fast they Stop+Submit. |
| Cold-start hang masks a real outage | Information Disclosure (poor UX channel) | D-19 honest "Warming up the agent — this can take ~4 minutes after idle" copy sets expectations. If hang exceeds reasonable cold-start + 60s timeout, ErrorEvent(reason="agent_timeout") arrives and is rendered honestly. |
| Mid-stream connection drop (revision swap, network blip) | Availability | Phase 1 D-17 30s cooperative drain + Phase 1 D-19 `ErrorEvent(reason="shutdown")` frame. Frontend D-23 renders "Server restarting — please try again in a moment." User re-submits. |
| Tool output containing malicious HTML/script | Tampering | Tool outputs are rendered inside `<pre>{output}</pre>` blocks (escaped text content). No `dangerouslySetInnerHTML` anywhere in `components/chat/`. |

**No new threat vectors introduced by Phase 6.** All mitigations are Phase 1 + Phase 4 inheritance.

## Code Examples

Verified patterns. Snippets are illustrative; planner/executor adapt to project conventions.

### `streamAgent` typed helper (`frontend/src/api/agent.ts`)

```typescript
// Source: CONTEXT D-27 + Phase 4 D-13 + D-16 inheritance
import { authedFetch } from '@/api/authedFetch'
import { readSSEStream, type AgentEvent } from '@/api/readSSEStream'

/**
 * Phase 6 D-27. POST /agent/stream with {query} body; returns the typed
 * AgentEvent async iterator from readSSEStream. Caller threads AbortSignal
 * (typically from useChatStream's abortControllerRef.current.signal).
 *
 * Throws on non-OK response (readSSEStream's check) or fetch failure
 * (network error, MSAL InteractionRequired). AbortError propagates to caller.
 */
export async function streamAgent(
  query: string,
  signal: AbortSignal,
): Promise<AsyncIterable<AgentEvent>> {
  const response = await authedFetch('/agent/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal,
  })
  return readSSEStream(response)
}
```

### `useChatStream` Hook Skeleton (`frontend/src/components/chat/useChatStream.ts`)

```typescript
// Source: CONTEXT D-28 + UI-SPEC §7 state machine + §12 cold-start
import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { streamAgent } from '@/api/agent'
import type { AgentEvent, ErrorEvent as SseErrorEvent } from '@/api/readSSEStream'
import type {
  TranscriptItem,
  NetworkError,
  TranscriptAction,
} from '@/components/chat/types'

const COLD_START_DELAY_MS = 10_000

function transcriptReducer(state: TranscriptItem[], action: TranscriptAction): TranscriptItem[] {
  switch (action.type) {
    case 'APPEND_USER_MESSAGE':
      return [...state, { kind: 'user-message', id: action.id, content: action.content }]
    case 'APPEND_ASSISTANT_TEXT':
      return [...state, {
        kind: 'assistant-text', id: action.id, content: '', streaming: true,
      }]
    case 'APPEND_TOKEN': {
      // Find the last assistant-text item with streaming=true and append.
      // Tokens at LLM cadence (~30-80/s) on top of acceptable; immutable update is fine.
      return state.map((item, i) => {
        if (i !== state.length - 1) return item
        if (item.kind !== 'assistant-text' || !item.streaming) return item
        return { ...item, content: item.content + action.content }
      })
    }
    case 'CLOSE_CURRENT_TEXT': {
      return state.map((item) => {
        if (item.kind === 'assistant-text' && item.streaming) {
          return { ...item, streaming: false }
        }
        return item
      })
    }
    case 'APPEND_TOOL_START':
      return [...state, {
        kind: 'tool-call', id: action.id, name: action.name,
        args: action.args, output: null, expanded: false,
      }]
    case 'UPDATE_TOOL_OUTPUT': {
      return state.map((item) =>
        item.kind === 'tool-call' && item.id === action.id
          ? { ...item, output: action.output }
          : item,
      )
    }
    case 'TOGGLE_TOOL_EXPANDED': {
      return state.map((item) =>
        item.kind === 'tool-call' && item.id === action.id
          ? { ...item, expanded: !item.expanded }
          : item,
      )
    }
    case 'APPEND_ERROR':
      return [...state, {
        kind: 'error', id: action.id, reason: action.reason, message: action.message,
      }]
    case 'MARK_STOPPED': {
      return state.map((item) => {
        if (item.kind === 'assistant-text' && item.streaming) {
          return { ...item, streaming: false, stopped: true }
        }
        return item
      })
    }
    default:
      return state
  }
}

export function useChatStream() {
  const [items, dispatch] = useReducer(transcriptReducer, [] as TranscriptItem[])
  const [isStreaming, setIsStreaming] = useState(false)
  const [coldStart, setColdStart] = useState(false)
  const [networkError, setNetworkError] = useState<NetworkError | null>(null)

  const abortControllerRef = useRef<AbortController | null>(null)
  const coldStartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Cleanup on unmount — Pitfall A
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      if (coldStartTimerRef.current) {
        clearTimeout(coldStartTimerRef.current)
        coldStartTimerRef.current = null
      }
    }
  }, [])

  const clearColdStartTimer = useCallback(() => {
    if (coldStartTimerRef.current) {
      clearTimeout(coldStartTimerRef.current)
      coldStartTimerRef.current = null
    }
  }, [])

  const submit = useCallback(async (query: string) => {
    if (isStreaming) return  // Pitfall A guard
    if (query.trim() === '') return

    const userId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    dispatch({ type: 'APPEND_USER_MESSAGE', id: userId, content: query })
    dispatch({ type: 'APPEND_ASSISTANT_TEXT', id: assistantId })
    setIsStreaming(true)
    setColdStart(false)

    // Cold-start timer
    clearColdStartTimer()
    coldStartTimerRef.current = setTimeout(() => setColdStart(true), COLD_START_DELAY_MS)

    // Abort controller per submit (one-shot)
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      const stream = await streamAgent(query, controller.signal)
      setNetworkError(null)  // Pitfall I — only clear on successful Response

      // Per-tool-call id map so UPDATE_TOOL_OUTPUT can match on tool name
      // (LangGraph doesn't supply a stable tool-call id; we generate one
      // at tool_start and match by name + insertion order)
      const pendingToolIds: string[] = []

      for await (const event of stream) {
        clearColdStartTimer()  // First event clears warming state
        setColdStart(false)

        switch (event.type) {
          case 'token':
            dispatch({ type: 'APPEND_TOKEN', content: event.content })
            break
          case 'tool_start': {
            const toolId = crypto.randomUUID()
            pendingToolIds.push(toolId)
            dispatch({ type: 'CLOSE_CURRENT_TEXT' })
            dispatch({
              type: 'APPEND_TOOL_START',
              id: toolId,
              name: event.name,
              args: event.args,
            })
            // Open a fresh assistant-text for subsequent tokens (D-08)
            dispatch({
              type: 'APPEND_ASSISTANT_TEXT',
              id: crypto.randomUUID(),
            })
            break
          }
          case 'tool_end': {
            const toolId = pendingToolIds.shift()
            if (toolId) {
              dispatch({
                type: 'UPDATE_TOOL_OUTPUT',
                id: toolId,
                output: event.output,
              })
            }
            break
          }
          case 'heartbeat':
            // Silent — only purpose is keep-alive; timer already cleared above
            break
          case 'error':
            dispatch({ type: 'CLOSE_CURRENT_TEXT' })
            dispatch({
              type: 'APPEND_ERROR',
              id: crypto.randomUUID(),
              reason: (event as SseErrorEvent).reason,
              message: (event as SseErrorEvent).message,
            })
            // Server-side error closes the stream after emitting; loop will exit naturally
            break
          case 'final':
            dispatch({ type: 'CLOSE_CURRENT_TEXT' })
            break
        }
      }
    } catch (err: unknown) {
      // Pitfall B — AbortError vs real error
      if (err instanceof Error && err.name === 'AbortError') {
        dispatch({ type: 'MARK_STOPPED' })
        return  // do NOT set networkError
      }
      setNetworkError(classifyNetworkError(err))
    } finally {
      setIsStreaming(false)
      clearColdStartTimer()
      abortControllerRef.current = null
    }
  }, [isStreaming, clearColdStartTimer])

  const stop = useCallback(() => {
    abortControllerRef.current?.abort()
    // The catch block in submit() handles MARK_STOPPED + isStreaming=false
  }, [])

  const toggleToolExpanded = useCallback((id: string) => {
    dispatch({ type: 'TOGGLE_TOOL_EXPANDED', id })
  }, [])

  return {
    items,
    isStreaming,
    coldStart,
    networkError,
    submit,
    stop,
    toggleToolExpanded,
  }
}

function classifyNetworkError(err: unknown): NetworkError {
  // Pattern matches D-24 copy table
  if (err instanceof Error) {
    const msg = err.message
    if (msg.includes('401')) return { kind: '401', message: 'Session expired' }
    if (msg.includes('403')) return { kind: '403', message: 'Not authorized' }
    if (msg.match(/5\d\d/)) return { kind: '5xx', message: 'Server error' }
    if (err.name === 'TypeError') return { kind: 'unreachable', message: "Can't reach the server" }
    return { kind: 'unknown', message: msg.slice(0, 200) }
  }
  return { kind: 'unknown', message: 'Unknown error' }
}
```

### Smart Autoscroll Pattern (`ChatTranscript.tsx` excerpt)

```typescript
// Source: UI-SPEC §6a + §17 #4 + Pattern 4 above
import { useEffect, useRef, useState } from 'react'

export function ChatTranscript({ items, isStreaming, coldStart, networkError }: ChatTranscriptProps) {
  const bottomSentinelRef = useRef<HTMLDivElement>(null)
  const [autoscrollEngaged, setAutoscrollEngaged] = useState(true)

  // IntersectionObserver on bottom sentinel — engages autoscroll when visible
  useEffect(() => {
    const sentinel = bottomSentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      ([entry]) => setAutoscrollEngaged(entry.isIntersecting),
      { root: null, threshold: 0 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [])

  // Scroll into view when items grow AND autoscroll is engaged
  useEffect(() => {
    if (!autoscrollEngaged) return
    bottomSentinelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [items, autoscrollEngaged])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      {networkError && (
        <div className="mx-4 mt-4">
          {/* destructive Alert per D-24 */}
        </div>
      )}
      <ol role="log" aria-live="polite" aria-relevant="additions" className="space-y-4">
        {items.map((item) =>
          item.kind === 'tool-call'
            ? <ToolChip key={item.id} item={item} onToggleExpand={...} />
            : <ChatMessage key={item.id} item={item} coldStart={coldStart} />
        )}
        <div ref={bottomSentinelRef} aria-hidden="true" className="h-px w-px" />
      </ol>
    </div>
  )
}
```

### Mock Fetch for Vitest (recommended `frontend/src/test/sseMockUtils.ts`)

```typescript
// Source: Phase 4 readSSEStream.test.ts pattern, extracted for reuse
import type { AgentEvent } from '@/api/readSSEStream'

/**
 * Produce a mock Response object whose body is a ReadableStream yielding
 * SSE-formatted bytes for the given events. Used by useChatStream tests.
 *
 * Each event is serialized as:
 *   event: <type>\n
 *   data: <JSON>\n
 *   \n
 */
export function mockSseResponse(events: AgentEvent[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        const frame = `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`
        controller.enqueue(encoder.encode(frame))
      }
      controller.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

/** Produce a Response that yields events but never closes (for cancellation tests). */
export function mockSseHangingResponse(initialEvents: AgentEvent[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of initialEvents) {
        controller.enqueue(encoder.encode(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`))
      }
      // Do NOT close — caller must abort via signal
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}
```

### Backend Route Change Diff (`src/job_rag/api/routes.py:364-383`)

```diff
- @router.get(
+ @router.post(
      "/agent/stream",
      dependencies=[Depends(require_api_key), Depends(agent_limit)],
      responses={
          # OpenAPI exposure of the AgentEvent union — consumed by openapi-typescript
          # in Phase 6 so the frontend gets a discriminated-union type for free.
          200: {
              "content": {
                  "text/event-stream": {
                      "schema": _AGENT_EVENT_JSON_SCHEMA,
                  }
              },
              "description": (
                  "Stream of AgentEvent variants (token, tool_start, tool_end, "
                  "heartbeat, error, final)"
              ),
          }
      },
  )
- async def agent_stream(request: Request, q: str) -> EventSourceResponse:
+ async def agent_stream(request: Request, payload: AgentQuery) -> EventSourceResponse:
      """Stream agent execution as SSE: typed events + heartbeat + 60s timeout + drain.

      ... (docstring unchanged) ...
      """
      app = request.app

      async def typed_event_generator():
          current_task = asyncio.current_task()
          if current_task is not None:
              app.state.active_streams.add(current_task)
          try:
              try:
                  async with asyncio.timeout(settings.agent_timeout_seconds):
-                     async for event in stream_agent(q):
+                     async for event in stream_agent(payload.query):
                          yield to_sse(event)
              ...
```

Exactly 3 lines change. ALL other handler code stays identical. This is critical for the plan checker: lines added/removed = 3 (`@router.get` → `@router.post`, `q: str` → `payload: AgentQuery`, `stream_agent(q)` → `stream_agent(payload.query)`).

### Test Call-Site Diffs (`tests/test_api.py`)

```diff
  # Line ~186 — TestAgentEndpoint.test_agent_stream_emits_sse_events
- response = await client.get("/agent/stream", params={"q": "test"})
+ response = await client.post("/agent/stream", json={"query": "test"})
```

```diff
  # Line ~366 — TestAgentStream._stream_bytes helper
- async with client.stream("GET", "/agent/stream?q=test") as resp:
+ async with client.stream("POST", "/agent/stream", json={"query": "test"}) as resp:
```

(plus any sibling references inside TestAgentStream that use the same pattern — grep `client.stream\("GET", "/agent/stream` to enumerate)

### DebugAgentStream Body-Key Fix (`frontend/src/routes/DebugAgentStream.tsx:36-38`)

```diff
  const res = await authedFetch('/agent/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
-   body: JSON.stringify({ message: query }),
+   body: JSON.stringify({ query }),
    signal: abortRef.current.signal,
  })
```

## GET→POST Validation (CHAT-01 Confirmation)

CONTEXT D-01 and CHAT-01 both assert that `fetch + ReadableStream` is the only viable consumption path because EventSource cannot attach Bearer headers. Confirmed:

- **EventSource API constraint** [VERIFIED: MDN https://developer.mozilla.org/en-US/docs/Web/API/EventSource]: The `EventSource()` constructor accepts only a URL and an optional `{ withCredentials: boolean }` options object. There is NO `headers` option. The only auth mechanism EventSource supports is browser-managed cookies (via `withCredentials: true`).
- **Bearer JWT delivery constraint** [VERIFIED: Phase 4 D-13 + RFC 6750]: MSAL-issued access tokens are delivered via `Authorization: Bearer <jwt>` header, NOT cookies. Phase 4's auth architecture (sessionStorage cache + per-request `acquireTokenSilent` + header attachment) is fundamentally incompatible with EventSource.
- **The only viable path:** `fetch()` + `response.body.getReader()` + `TextDecoder` + SSE frame parsing — exactly what `readSSEStream` (Phase 4 D-16) implements.
- **POST vs GET on the backend:** Once the consumer is `fetch`, the HTTP method becomes a free design choice. CONTEXT D-01 prefers POST for three reasons (consistency, no URL-length ceiling, debug-page alignment). All three are valid; POST is the right call.

**No regressions:**
- Heartbeat (Phase 1 D-15) — works identically over POST.
- 60s timeout (Phase 1 D-16) — works identically over POST.
- Cooperative shutdown drain (Phase 1 D-17) — works identically over POST.
- Defensive headers `X-Accel-Buffering: no` + `Content-Encoding: identity` (Phase 1 D-18) — preserved on POST.
- ping_message_factory typed HeartbeatEvent — preserved on POST.
- ACA Envoy 240s request cap (PITFALLS.md §3) — applies to POST identically; 60s `asyncio.wait_for` is well inside the cap.

**FastAPI 0.135.3 [VERIFIED: pyproject.toml] supports POST + sse-starlette EventSourceResponse + Bearer auth natively** — no upgrade required. The decorator `@router.post(...)` + `payload: AgentQuery` parameter signature is the standard Pydantic body pattern.

## Plan Grain Recommendation

Phase 5 used 6 plans. Phase 6 is materially smaller — 1 backend method change + 1 frontend feature + 2 shadcn primitive installs. Recommend **4 plans**:

1. **06-01-PLAN: Wave 0 Foundation** — 2 shadcn primitive installs (`collapsible`, `textarea`), 4 test stub files (`useChatStream.test.tsx`, `ToolChip.test.tsx`, `ChatComposer.test.tsx`, `ChatTranscript.test.tsx`) with import-guarded skip stubs, 1 shared test util (`sseMockUtils.ts`), `frontend/src/components/chat/types.ts` shell + ERROR_TITLE/ERROR_BODY tables, `@keyframes blink` CSS append to `app.css`, DebugAgentStream body-key fix (Pitfall H closure). All scaffolding. No behavior change.

2. **06-02-PLAN: Backend method change** — `routes.py` `@router.get` → `@router.post` + signature update (3-line diff), `tests/test_api.py` 3 call-site updates (D-03), `tests/test_sse_contract.py` any method assertions (likely no-op — schema tests are method-agnostic), regenerate `frontend/openapi.snapshot.json` via in-process `app.openapi()` capture + `npm run codegen:snapshot`. Local CI green. Backend pushed.

3. **06-03-PLAN: Frontend data layer + state hook** — `frontend/src/api/agent.ts` filled with `streamAgent(query, signal)`; `frontend/src/components/chat/useChatStream.ts` implementation per UI-SPEC §7 + §12 + this RESEARCH §"Code Examples"; activate `useChatStream.test.tsx` (covers CHAT-01, CHAT-02, CHAT-05 hook portion, CHAT-06 storage spy, Pitfalls A/B/D). Hook-level tests green.

4. **06-04-PLAN: Frontend presentation + route composition + UAT** — `ChatTranscript.tsx`, `ChatMessage.tsx`, `ToolChip.tsx`, `ChatComposer.tsx`, `ChatEmptyState.tsx` per UI-SPEC §6a–§6e verbatim JSX skeletons; `routes/Chat.tsx` replaces PhasePlaceholder with composition; activate remaining tests (`ToolChip.test.tsx`, `ChatComposer.test.tsx`, `ChatTranscript.test.tsx`); local UAT runbook (M1 happy-path chat against deployed ACA, M2 Stop mid-stream, M3 refresh-clears, M4 cold-start "Warming up" copy verification, M5 tool chip expand + Dialog).

Plan 4 may optionally split into 04a (components + route + tests) + 04b (live UAT runbook autonomous: false) following Phase 5's 05-05 + 05-06 split. Phase 5 verifier confirmed the runbook split is a worthy investment when live-Azure verification is the close-out gate. Recommend the split.

**Total: 4–5 plans** depending on UAT split.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| EventSource API for SSE | `fetch + ReadableStream + TextDecoder` | ~2019 (Streams API standardized); ~2021 (Bearer-auth requirements + custom headers became mainstream for SSE in SPA contexts) | Modern SPA SSE consumption is `fetch`-based; EventSource is legacy + cookie-only auth. [VERIFIED: Phase 4 D-16 + WHATWG SSE spec.] |
| Individual `@radix-ui/react-*` packages | Unified `radix-ui` package | February 2026 [VERIFIED: shadcn changelog] | shadcn's new-york / radix-nova styles now import from `radix-ui` directly. Project already pins `"radix-ui": "^1.4.3"`; no migration needed. |
| TanStack Query `useQuery` for everything | useReducer / useState for streaming + useQuery for request-response | ~2024+ as streaming UX became standard | TanStack Query has no native SSE primitive; chat streaming uses React state directly. CONTEXT canonical_refs SHEL-03 note captures this. |
| `setItems(prev => [...prev, ...])` array spread | `useReducer` with discriminated-action types | React 18+ as automatic batching matured | Reducer is testable + state machine is explicit. Phase 5 D-17 `useDashboardFilters` already follows. |
| Polling `scrollTop`/`scrollHeight` for autoscroll | IntersectionObserver on bottom sentinel | ~2019 IntersectionObserver mainstream support | Saves CPU; one observer fires once per visibility change, not on every scroll tick. |

**Deprecated/outdated:**
- EventSource for authenticated SSE — replaced by fetch+ReadableStream
- Individual `@radix-ui/react-*` package imports in shadcn `new-york`/`radix-nova` styles — replaced by unified `radix-ui` import (Feb 2026 changelog)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `useReducer` for transcript items + `useState` for other flags is the right granularity | Pattern 3 + Code Examples | If executor finds `useState` simpler and prefers single-call setItems(prev=>...), behavior is identical at LLM cadence (~30–80 tokens/s). Refactor is local to useChatStream. LOW risk. |
| A2 | `radix-ui` unified package (v1.4.3 on disk) ships `@radix-ui/react-collapsible` 1.1.x equivalent | Standard Stack — Net-New | If the unified package omits Collapsible or pins an old version, `npx shadcn@latest add collapsible` would either install a separate `@radix-ui/react-collapsible` package OR fail with an import error. Plan executor runs install + grep verification; if mismatch, fall back to separate package install. LOW risk. [Verified Feb 2026 changelog mentions unified package shipped Collapsible; npm shows latest 1.1.12 separately, suggesting both paths work.] |
| A3 | `crypto.randomUUID()` is available in all evergreen browsers + Vite dev server `localhost:5173` is a secure context | Pitfall K | If users access via LAN IP, crypto.randomUUID fails. Pitfall K documents the fallback option; v1 ships without fallback because Vite default is localhost. MEDIUM risk if Adrian ever runs LAN demo on phone. |
| A4 | LangGraph tool_start / tool_end events arrive in matched pairs in order | Code Examples — useChatStream pendingToolIds | If LangGraph ever interleaves multiple in-flight tools, the `pendingToolIds.shift()` pattern could mismatch. Phase 1 D-04 + agent/stream.py:63-84 confirms LangGraph yields them sequentially via `astream_events("v2")`. LOW risk based on current LangGraph 1.1.x behavior. |
| A5 | The `radix-nova` style ships with the same Collapsible visual that the JSX skeleton in UI-SPEC §6c assumes (Tailwind class compatibility) | Architecture Patterns | If `radix-nova` Collapsible has different default styling than `new-york`, the JSX skeleton might need class adjustments. The skeleton uses standard Tailwind utilities (`rounded-md`, `border`, `bg-card`, etc.) which are token-driven, not style-specific. LOW risk. |
| A6 | Frontend test file location `frontend/src/test/` matches Phase 4 precedent (vs `frontend/src/components/chat/__tests__/`) | Validation Architecture — Wave 0 Gaps | If executor places tests in a different location, plan checker grep would miss them. Recommended location is explicit; executor follows. LOW risk. |
| A7 | OpenAPI snapshot regeneration via in-process `app.openapi()` capture is the preferred path | Pitfall G | If executor uses live-backend capture instead, requires running Docker Compose. In-process is faster + matches Phase 5 plan 05-03 D-04 pattern. LOW risk — both produce identical output. |
| A8 | The existing `readSSEStream` helper's `data: data.type ?? eventName` fallback handles the typed Pydantic `model_dump_json()` output (which always includes `type`) | Code Examples + Don't Hand-Roll | Phase 1 D-04 + sse.py confirm every AgentEvent variant includes `type` in `model_dump_json()`. The fallback path is defensive for the heartbeat-without-data case. LOW risk. |

**If this table seems short:** Phase 6's substrate (Phase 1 D-04 typed AgentEvent + Phase 4 D-13 authedFetch + Phase 4 D-16 readSSEStream + Phase 4 D-19 EmptyState/ErrorBoundary primitives) is heavily verified. Phase 6 is composition, not invention.

## Open Questions

1. **Should the OpenAPI snapshot regen step (Pitfall G) live in Plan 02 (backend) or Plan 03 (frontend)?**
   - What we know: Phase 5 plan 05-03 regenerates the snapshot at the end of the backend route plan. The frontend plan then runs `npm run codegen:snapshot` (a different script that reads the local snapshot file) to update `types.ts`.
   - What's unclear: Whether Phase 6 should follow the same split or co-locate both steps in one plan to avoid the "snapshot lives in repo without matching types.ts for 1 commit" window.
   - Recommendation: Follow Phase 5 precedent (snapshot regen in backend plan, types.ts regen in frontend plan). The 1-commit window is acceptable; CI drift check catches mismatches.

2. **Does the planner want Plan 04 to split into 04a (frontend code + tests) + 04b (UAT runbook autonomous:false) per Phase 5's 05-05 + 05-06 split?**
   - What we know: Phase 5 found the split valuable because UAT required Adrian's manual interaction with the live ACA + SWA stack; the runbook lives in a non-autonomous plan.
   - What's unclear: Whether Phase 6's UAT will require live-Azure verification (likely YES — cold-start demo only works against a scaled-to-zero ACA replica) or can be local-only.
   - Recommendation: SPLIT. UAT runbook for Phase 6 should be `autonomous: false` and require Adrian to (a) trigger a scale-to-zero by waiting / forcing replica scale-down, (b) submit a chat query and observe the 10s "Warming up…" copy swap, (c) verify tool chips render + expand, (d) DevTools Application tab inspection for CHAT-06 zero-residue, (e) refresh-clears verification.

3. **Should `frontend/src/components/chat/types.ts` re-export `AgentEvent` from `@/api/readSSEStream` or import-and-use it as a foreign type?**
   - What we know: `readSSEStream.ts` already exports all 6 event types + the union. CONTEXT D-07 defines `TranscriptItem` separately. The two are distinct: `AgentEvent` = wire format, `TranscriptItem` = in-memory UI shape.
   - What's unclear: Whether `types.ts` should also re-export `AgentEvent` for convenience or leave callers to import from `@/api/readSSEStream`.
   - Recommendation: Re-export for convenience — `export type { AgentEvent, ErrorEvent } from '@/api/readSSEStream'`. Avoids 2-source-import pattern in `useChatStream.ts`.

## Sources

### Primary (HIGH confidence)

- `06-CONTEXT.md` — 32 locked decisions; the single source of truth for Phase 6 scope.
- `06-UI-SPEC.md` — 1648-line UI design contract with verbatim JSX skeletons.
- `frontend/components.json` — `style: radix-nova`, `baseColor: neutral`, `iconLibrary: lucide` confirmed on disk.
- `frontend/package.json` — All version pins verified (React 19.2.6, Vite 8.0.12, Tailwind 4.3, MSAL 5.x, shadcn 4.7, openapi-typescript 7.13, Vitest 3.2, etc.).
- `src/job_rag/api/routes.py` lines 340-474 — exact handler internals to preserve unchanged.
- `src/job_rag/api/sse.py` — typed AgentEvent discriminated union (Phase 1 D-04).
- `frontend/src/api/readSSEStream.ts` — Phase 4 D-16 SSE helper (consumed AS-IS).
- `frontend/src/api/authedFetch.ts` — Phase 4 D-13 Bearer-attached fetch (consumed AS-IS).
- `tests/test_api.py` lines 165-186, 342-366 — exact call-site update targets.
- `.planning/research/PITFALLS.md` §4 (scale-to-zero), §6 (gzip), §3 (240s timeout), §"Looks Done But Isn't" checklist.
- [shadcn February 2026 unified Radix UI changelog](https://ui.shadcn.com/docs/changelog/2026-02-radix-ui)
- [Collapsible — shadcn/ui official component docs](https://ui.shadcn.com/docs/components/radix/collapsible)
- [Textarea — shadcn/ui official component docs](https://ui.shadcn.com/docs/components/radix/textarea)
- [@radix-ui/react-collapsible — npm registry, latest 1.1.12](https://www.npmjs.com/package/@radix-ui/react-collapsible)

### Secondary (MEDIUM confidence — verified via web search + cross-referenced with official docs)

- [Server-Sent Events (SSE) — FastAPI official docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [sse-starlette — PyPI](https://pypi.org/project/sse-starlette/)
- [sse-starlette GitHub](https://github.com/sysid/sse-starlette)
- [Why is useEffect Running Twice? React 19 Strict Mode Guide (DEV Community, 2026)](https://dev.to/pockit_tools/why-is-useeffect-running-twice-the-complete-guide-to-react-19-strict-mode-and-effect-cleanup-1n60)
- [Bug: React.StrictMode causes AbortController to cancel — facebook/react#25962](https://github.com/facebook/react/issues/25962)
- [Cancelling In-Flight Fetch Requests with AbortController (OpenReplay, 2024+)](https://blog.openreplay.com/cancelling-in-flight-fetch-abortcontroller/)
- [Intuitive Scrolling for Chatbot Message Streaming (tuffstuff9.hashnode.dev)](https://tuffstuff9.hashnode.dev/intuitive-scrolling-for-chatbot-message-streaming)
- [Using Intersection Observer API in React (DEV Community)](https://dev.to/emmanueloloke/using-intersection-observer-api-in-react-56b0)
- [How to Stream Data to the Browser with Fetch (OpenReplay)](https://blog.openreplay.com/stream-data-browser-fetch/)
- [How to Implement Server-Sent Events (SSE) in React — January 2026](https://oneuptime.com/blog/post/2026-01-15-server-sent-events-sse-react/view)

### Tertiary (LOW confidence — informational, not load-bearing)

- [useState vs useReducer (TkDodo blog)](https://tkdodo.eu/blog/use-state-vs-use-reducer)
- [Consuming Web Streams with useState, SWR and React Query (DEV Community)](https://dev.to/fibonacid/consuming-web-streams-with-usestate-swr-and-react-query-3mjf)
- [shadcn/ui Component Styles: Vega, Nova, Maia, Lyra, Mira (Shadcnblocks)](https://www.shadcnblocks.com/blog/shadcn-component-styles-vega-nova-maia-lyra-mira)

## Metadata

**Confidence breakdown:**
- User Constraints inheritance: HIGH — verbatim copy from CONTEXT.md, no re-litigation
- Standard Stack: HIGH — every version verified against on-disk `frontend/package.json` + `pyproject.toml`
- Architecture: HIGH — Phase 4/5 precedent already shipped the substrate; Phase 6 composes
- Pitfalls: HIGH for A-E (verified via React maintainer pattern + Phase 1 D-18 inheritance + cross-checked Vite/Vitest docs); MEDIUM for K (crypto.randomUUID secure-context edge case)
- Validation Architecture: HIGH — test framework / config / scripts all verified in repo
- Code Examples: HIGH for backend diff (3 lines), MEDIUM for useChatStream hook (illustrative; executor adapts to project conventions while preserving the state-machine contract per UI-SPEC §7)
- GET→POST validation: HIGH — verified against MDN EventSource constraint + Phase 4 D-13 Bearer architecture

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (30 days for stable stack; shadcn / Vite ecosystem unlikely to ship breaking changes in that window)
