# Phase 6: Chat - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered
> and notes which gray areas were auto-resolved versus user-decided.

**Date:** 2026-05-23
**Phase:** 06-chat
**Mode:** Auto-resolved (background session)
**Areas discussed:** Backend transport, Transcript model, Tool-call chip UX, Composer
UX, Streaming UX states, Error rendering, Empty state, Cancellation, Component tree,
Test strategy, Aesthetic, Accessibility

---

## Auto-resolution context

This session ran in a background job with the system reminder "The user has asked
to work without stopping for clarifying questions. When you'd normally pause to
check, make the reasonable call and continue; they'll redirect if needed."

Prior phases established a strong user-locked "Recommended" pattern (20/20 in
Phase 4 interactive; 23/23 in Phase 5 auto-resolved). Phase 6 applied the same
auto-resolved approach: each gray area was researched, the recommended option
was selected with rationale + counterfactual, and the decision was committed to
CONTEXT.md without an AskUserQuestion turn.

Adrian retains full redirect authority on any decision by editing CONTEXT.md or
re-running `/gsd-discuss-phase 6 --update` before planning.

---

## Backend transport

**Gray area:** `/agent/stream` currently exposes `GET ?q=...`, but the Phase 4
debug page (`DebugAgentStream.tsx`) was scaffolded to POST `{message: query}` —
a latent mismatch that never surfaced because the probe was never live-exercised
against the actual backend. Phase 6 must reconcile.

| Option | Description | Selected |
|--------|-------------|----------|
| POST `{query: string}` | Align backend to `/agent` POST convention; reuse `AgentQuery` model; closes the debug-page mismatch; no URL-length ceiling for long queries | ✓ |
| GET `?q=...` (keep) | Lower-touch; no test changes; HTTP-semantic "read-only" stream | |
| Support both | Doubles OpenAPI surface, rate-limit policy, error path | |

**Selected:** POST. CONTEXT.md D-01..D-05.
**Notes:** Three reasons: consistency with `/agent`, no URL-length ceiling for
long pasted queries, alignment with the debug-page's assumed contract. Backend
deviation flagged for the PR description.

---

## Transcript layout (the defining aesthetic call)

**Gray area:** Chat transcript visual style.

| Option | Description | Selected |
|--------|-------------|----------|
| Linear-dense flat thread | Left-aligned both roles, small role labels, no bubbles, no avatars; reads like Linear comments | ✓ |
| ChatGPT-style bubbles | User right-aligned colored bubble; assistant left-aligned; conventional but adds visual weight that competes with tool chips | |
| Q&A blocks (Stack Overflow style) | Full-width assistant blocks with small user header | |

**Selected:** Linear-dense flat thread. CONTEXT.md D-06 / D-31.
**Notes:** PROJECT.md "Linear-style dense aesthetic" is the controlling
constraint. Bubble-style would also work but introduces unnecessary chrome and
attention-competition with the chips.

---

## Tool-call chip UX (THE differentiator)

**Gray area:** How are `tool_start`/`tool_end` pairs rendered?

| Option | Description | Selected |
|--------|-------------|----------|
| Collapsed-by-default inline chip with expand-on-click + "Show full output" Dialog | shadcn Collapsible primitive; spinner during run; 200-char output preview; Dialog for full output | ✓ |
| Always-expanded inline block | More legible by default but pollutes the transcript for users who don't care about reasoning | |
| Side panel (split-pane) | Cleaner transcript but adds layout complexity and competes with composer for vertical space | |

**Selected:** Collapsed inline + expand-on-click + Dialog for full output.
CONTEXT.md D-10..D-13.
**Notes:** Per FEATURES.md line 44, this IS the portfolio differentiator. The
collapsed-default keeps the transcript readable; the expand affordance + Dialog
makes it inspectable on demand — the "production agent UX" demo story.

---

## Composer UX

**Gray area:** Input affordance + keyboard semantics.

| Option | Description | Selected |
|--------|-------------|----------|
| Sticky-bottom multi-line Textarea + Enter submits, Shift+Enter newline | Modern chat convention (ChatGPT / Claude.app / Linear); auto-grows up to ~6 rows | ✓ |
| Single-line Input + Enter submits | Simpler but forces users to paste long queries into a tiny box | |
| In-flow composer at end of transcript | Cleaner doc-style but forces scroll-back to type after long agent responses | |

**Selected:** Sticky-bottom Textarea + Enter/Shift+Enter. CONTEXT.md D-14 / D-15.
**Notes:** Enter-submits-Shift+Enter-newline matches Adrian's existing chat
muscle memory.

---

## Cancellation

**Gray area:** Can user stop streaming mid-flight?

| Option | Description | Selected |
|--------|-------------|----------|
| Stop button replaces Send during streaming + AbortController per stream + unmount cleanup | Explicit affordance; resource-leak-safe; ready for Phase 8 keyboard shortcuts | ✓ |
| No cancellation | Simpler but feels broken if a query is misformed | |
| Auto-cancel on new submit only (no Stop button) | Implicit; less discoverable | |

**Selected:** Stop button + AbortController. CONTEXT.md D-16 / D-26.

---

## Streaming UX states

**Gray area:** What's shown before the first token? During? On cold start?

| Option | Description | Selected |
|--------|-------------|----------|
| "Thinking…" + animated dots → flips to tokens; cold-start awareness via "Warming up… ~4 min after idle" at 10s timeout; blinking caret as streaming cursor | Honest about scale-to-zero architecture; demo-friendly; closes Phase 4 UI-SPEC §18 deferred item | ✓ |
| Generic full-bubble skeleton | Looks polished but doesn't explain the cold-start wait | |
| Silent until first token | Feels broken — no feedback for the ~225s cold-start window | |

**Selected:** Thinking → Warming up + cursor. CONTEXT.md D-18..D-21.
**Notes:** Cold-start honesty is portfolio-positive per memory
`aca-cold-start-profile.md`. Hiding the wait makes the demo flaky; surfacing it
makes scale-to-zero a feature, not a bug.

---

## Error rendering

**Gray area:** How are typed ErrorEvent frames + network errors shown?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline shadcn Alert (destructive) at the position streaming stopped; per-reason copy for all 4 Literal reasons; no retry button in v1 | Stays in-transcript context; user can re-ask manually; one less state to track | ✓ |
| Toast notification + half-finished bubble | Disconnects error from cause; toasts can be missed | |
| Full-page error replacement | Loses the transcript; over-reactive for recoverable errors | |

**Selected:** Inline Alert. CONTEXT.md D-22..D-24.

---

## Empty state / first-load

**Gray area:** What does an empty `/chat` page show?

| Option | Description | Selected |
|--------|-------------|----------|
| EmptyState + 3-4 sample query chips that pre-fill (not auto-submit) the composer | Demo-friendly; shows off chips + streaming on first interaction; chips let Adrian iterate wording | ✓ |
| Minimal blank composer | Cleanest but unhelpful on first load | |
| Help text without chips | Verbose; chips are more discoverable | |

**Selected:** EmptyState + sample chips. CONTEXT.md D-25.

---

## Within-session history behavior

**Gray area:** CHAT-06 says "refresh clears". What about multiple turns within one
session?

| Option | Description | Selected |
|--------|-------------|----------|
| Append-only within session (multiple Q→A pairs accumulate until refresh; each backend call independent — no conversation context passed) | UI affordance to review prior turns; agent remains single-turn per CHAT-06 spirit | ✓ |
| Clear on each submit | Purest single-turn; loses visible context too aggressively | |
| Persist to localStorage with TTL | Violates CHAT-06 literal | |

**Selected:** Append-only within session. CONTEXT.md D-09.

---

## Component tree

**Gray area:** File structure for the chat feature.

| Option | Description | Selected |
|--------|-------------|----------|
| `components/chat/` feature folder mirroring Phase 5's `components/dashboard/`; useChatStream hook owns state; presentation components state-free | Established precedent; one folder per feature surface | ✓ |
| Flat under `components/` | Pollutes the shared component dir | |
| `routes/Chat/` with co-located components | Routes folder normally just has route entries | |

**Selected:** `components/chat/` folder. CONTEXT.md D-27 / D-28.

---

## Test strategy

**Gray area:** How are streaming + chip + composer tested?

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest + RTL + mock fetch returning ReadableStream of SSE frames; per-component test files; existing readSSEStream tests already cover the helper | Pattern proven in Phase 4 D-16 readSSEStream tests | ✓ |
| Playwright E2E only | Slower; harder to assert intermediate state | |
| Skip frontend tests entirely | Loses regression net | |

**Selected:** Vitest + mock fetch. CONTEXT.md D-29 / D-30.

---

## Claude's Discretion

Areas where the planner has flexibility:
- Exact lucide-react icon choices for chips
- Animation timing for blinking cursor (0.8 / 1.0 / 1.2s)
- `scrollIntoView` vs `scrollTop = scrollHeight` for autoscroll
- Heartbeat event rendering in DEV-only Debug page vs production Chat
- Exact sample query phrasing in D-25
- Stop button icon (`Square` filled vs `XCircle` close)
- Markdown rendering — deferred to Phase 8
- Code-block syntax highlighting — deferred
- Phase 6 commit grain — planner to decide (~4 plans estimated)

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section:
- Conversation history persistence (CHAT2-01, v2)
- Multi-turn agent memory (v2 platform)
- Chat branching / forking (CHAT2-02, v2)
- Export chat as Markdown (CHAT2-03, v2)
- Markdown rendering in assistant text (Phase 8 polish)
- Syntax highlighting in tool outputs (defer)
- Retry button on error events (defer)
- "Copy to clipboard" on assistant response (Phase 8)
- Keyboard shortcuts (Phase 8)
- shadcn/ai or assistant-ui registry blocks (deferred — build from primitives)
- Conversation download as JSON (v2)
- "Regenerate response" button (implies multi-turn, v2)
- Selective tool cancellation (mid-stream) (defer)
- Always-warm ACA (out of budget — Phase 8 polish may revisit)
- Phase 04.1 follow-ups (independent of Phase 6)
- Phase 5 polish candidates (independent of Phase 6)
