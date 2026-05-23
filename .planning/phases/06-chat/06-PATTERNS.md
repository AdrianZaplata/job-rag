# Phase 6: Chat - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 19 (4 backend/test + 15 frontend, 2 of which are shadcn-installed)
**Analogs found:** 17 / 19 (2 net-new shadcn primitives have no analog; CLI generates them)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/job_rag/api/routes.py` (modify) | route handler (FastAPI) | streaming/request-response | `src/job_rag/api/routes.py:344-347` (`/agent` POST) + same file lines 364-474 (`/agent/stream` GET, the very block being mutated) | exact (in-file precedent) |
| `tests/test_api.py` (modify 3 sites) | integration test | request-response | `tests/test_api.py:140-163` (`TestAgentEndpoint.test_agent_query_success` — POST + JSON body) | exact |
| `tests/test_sse_contract.py` (modify) | contract test | n/a — schema introspection | `tests/test_sse_contract.py:87-135` (existing `TestOpenAPISchema.test_openapi_includes_agent_event`) | exact (in-file precedent) |
| `frontend/openapi.snapshot.json` (regen) | committed artifact | codegen output | regenerated via `npm run codegen:snapshot` — no source analog; Phase 5 plan 05-03 is the precedent | n/a (build artifact) |
| `frontend/src/api/agent.ts` (fill stub) | service module (typed API client) | streaming | `frontend/src/api/jobs.ts` (typed authedFetch wrapper) + `frontend/src/api/health.ts` (single-function shape) | role-match (closest streaming analog is `readSSEStream.ts` itself which Phase 6 calls) |
| `frontend/src/api/types.ts` (regen) | codegen output | n/a | already exists, regenerated via `npm run codegen` | n/a (build artifact) |
| `frontend/src/routes/Chat.tsx` (replace) | route page (composition) | local state | `frontend/src/routes/Dashboard.tsx` (Phase 5 — replaces PhasePlaceholder with feature composition) | exact (same Phase 4→5/6 progression) |
| `frontend/src/routes/DebugAgentStream.tsx` (1-line fix) | route page (dev probe) | streaming | self (only the body-key string changes; existing scaffold is the template) | exact (in-file fix) |
| `frontend/src/components/chat/ChatTranscript.tsx` (NEW) | presentation component | local-state read | `frontend/src/components/dashboard/TopSkillsCard.tsx` (Card-shaped panel with skeleton/error/empty branches) — but ChatTranscript is a list-shaped log, so partial-match | role-match (presentation only; layered loading/empty/error per SHEL-06) |
| `frontend/src/components/chat/ChatMessage.tsx` (NEW) | presentation component | render-prop | `frontend/src/components/dashboard/TopSkillsCard.tsx` lines 40-69 (`SkillRow` internal component — single-item render) | role-match |
| `frontend/src/components/chat/ToolChip.tsx` (NEW) | presentation component (with Dialog) | local state + Dialog | `frontend/src/components/dashboard/TopSkillsDialog.tsx` (shadcn Dialog wrapper with footer Close) + `TopSkillsCard.tsx` (`Show more` button → dialog open) | exact (Dialog pattern); role-match (Collapsible is new) |
| `frontend/src/components/chat/ChatComposer.tsx` (NEW) | presentation component (controlled input) | DOM events + callbacks | `frontend/src/components/dashboard/DashboardFilters.tsx` (typed controlled inputs + setter callbacks) + `frontend/src/routes/DebugAgentStream.tsx` (`Input` + Send button + disabled-while-streaming) | exact (DebugAgentStream is the direct shape) |
| `frontend/src/components/chat/ChatEmptyState.tsx` (NEW) | presentation component | render-only | `frontend/src/components/EmptyState.tsx` (the primitive being composed) + `frontend/src/components/PhasePlaceholder.tsx` (composes EmptyState with feature-specific copy) | exact (PhasePlaceholder is the precedent for "compose EmptyState with feature copy") |
| `frontend/src/components/chat/useChatStream.ts` (NEW) | custom hook (state + lifecycle) | streaming + abort + timer | `frontend/src/components/dashboard/useDashboardFilters.ts` (Phase 5 D-17 typed custom hook owning state machine) — but useChatStream owns async lifecycle which useDashboardFilters does not; partial-match for STRUCTURE; `frontend/src/routes/DebugAgentStream.tsx` for the streaming/abort lifecycle pattern | role-match (no existing hook owns AbortController + timer + async iterator; useDashboardFilters is the typed-hook shape; DebugAgentStream is the streaming lifecycle shape) |
| `frontend/src/components/chat/types.ts` (NEW) | type module | static types | `frontend/src/api/readSSEStream.ts` lines 1-23 (AgentEvent discriminated union pattern) + `frontend/src/components/dashboard/useDashboardFilters.ts` lines 19-26 (feature-folder type definitions) | exact (discriminated union pattern is in readSSEStream.ts) |
| `frontend/src/components/ui/collapsible.tsx` (NEW shadcn install) | shadcn primitive | n/a | `frontend/src/components/ui/dialog.tsx` (similar Radix primitive install) | n/a (CLI-generated; no analog needed) |
| `frontend/src/components/ui/textarea.tsx` (NEW shadcn install) | shadcn primitive | n/a | `frontend/src/components/ui/input.tsx` (similar shadcn primitive install) | n/a (CLI-generated; no analog needed) |
| `frontend/src/test/useChatStream.test.tsx` (NEW) | unit test (hook) | render-and-assert | `frontend/src/components/dashboard/useDashboardFilters.test.tsx` (Phase 5 hook test with `renderHook` + `act`) — but useChatStream involves mock fetch, so combine with `frontend/src/test/readSSEStream.test.ts` (ReadableStream mock pattern) | exact (combination of two existing patterns) |
| `frontend/src/test/ToolChip.test.tsx` (NEW) | unit test (component) | render-and-assert | `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx` (renderWithProviders + screen.getByText/findByText) | role-match (provider wrapping not needed for ToolChip since no useQuery) |
| `frontend/src/test/ChatComposer.test.tsx` (NEW) | unit test (component) | render-and-assert | `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx` (controlled-input test pattern) | role-match |
| `frontend/src/test/ChatTranscript.test.tsx` (NEW) | unit test (component) | render-and-assert | `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx` (data-driven render + branching states) | role-match |
| `frontend/src/test/sseMockUtils.ts` (NEW shared util) | test helper | mock factory | `frontend/src/test/readSSEStream.test.ts` lines 4-13 (`streamFromString` inline helper — extract for reuse) | exact (extraction of existing pattern) |

## Pattern Assignments

### `src/job_rag/api/routes.py` modify (route handler — request-response with SSE streaming)

**Analog:** `src/job_rag/api/routes.py` itself — the existing `/agent` POST handler at lines 344-347 is the body-shape template, the existing `/agent/stream` GET handler at lines 364-474 is the routing template. Phase 6 mutates exactly 3 lines.

**Decorator pattern** (`routes.py:344` — `/agent` POST sibling pattern Phase 6 mirrors):
```python
@router.post("/agent", dependencies=[Depends(require_api_key), Depends(agent_limit)])
async def agent_query(payload: AgentQuery) -> dict[str, Any]:
    """Run the LangGraph agent to completion on a single query."""
    return await run_agent(payload.query)
```

**Pydantic body model already exists** (`routes.py:340-341`):
```python
class AgentQuery(BaseModel):
    query: str
```

**Current decorator + signature to mutate** (`routes.py:364-383`):
```python
@router.get(
    "/agent/stream",
    dependencies=[Depends(require_api_key), Depends(agent_limit)],
    responses={ ... },  # block stays IDENTICAL
)
async def agent_stream(request: Request, q: str) -> EventSourceResponse:
```

**Phase 6 mutates exactly 3 lines** (verified per RESEARCH §"Backend Route Change Diff"):
1. Line 364: `@router.get(` → `@router.post(`
2. Line 383: `async def agent_stream(request: Request, q: str)` → `async def agent_stream(request: Request, payload: AgentQuery)`
3. Line 417: `async for event in stream_agent(q):` → `async for event in stream_agent(payload.query):`

**All other internals stay identical** — timeout wrap, active_streams tracking, error frames (TimeoutError/CancelledError/Exception branches), ping_message_factory, shutdown_event, defensive headers. The `responses={...}` block stays identical (already wires `_AGENT_EVENT_JSON_SCHEMA` for codegen).

**Auth/Guard pattern** (`routes.py:344, 366`):
```python
dependencies=[Depends(require_api_key), Depends(agent_limit)]
```
Both `/agent` and `/agent/stream` already share this dependency chain; Phase 6 D-05 keeps `agent_limit` (10/min) unchanged.

**Error handling pattern** (`routes.py:419-453` — three try-branches each emit a typed `ErrorEvent` then close):
```python
except TimeoutError:
    yield to_sse(ErrorEvent(type="error", reason="agent_timeout", message=...))
except asyncio.CancelledError:
    yield to_sse(ErrorEvent(type="error", reason="shutdown", message=...))
    raise
except Exception as e:
    yield to_sse(ErrorEvent(type="error", reason="internal", message=_sanitize(e)))
```
Pattern UNCHANGED. The frontend D-23 lookup table maps each `ErrorEvent.reason` literal to display copy.

---

### `tests/test_api.py` modify (integration test — 3 call sites)

**Analog:** `tests/test_api.py:140-163` (`TestAgentEndpoint.test_agent_query_success` — already uses POST + `json=`)

**POST + JSON body pattern** (`test_api.py:155-159` paraphrased — the canonical POST shape):
```python
response = await client.post("/agent", json={"query": "test"})
```

**Current GET pattern to mutate** (`test_api.py:186`):
```python
response = await client.get("/agent/stream", params={"q": "test"})
```

**Phase 6 D-03 transformation** (verified per RESEARCH §"Test Call-Site Diffs"):
```python
# Line ~186
response = await client.post("/agent/stream", json={"query": "test"})
```

**Streaming context current pattern** (`test_api.py:365-367`):
```python
async with client.stream("GET", "/agent/stream?q=test") as resp:
```

**Phase 6 D-03 transformation**:
```python
async with client.stream("POST", "/agent/stream", json={"query": "test"}) as resp:
```

**Imports/setup pattern** (`test_api.py:165-186`):
```python
from asgi_lifespan import LifespanManager
from job_rag.api.sse import FinalEvent, TokenEvent, ToolStartEvent

async def fake_stream(_query):
    yield ToolStartEvent(type="tool_start", name="search_jobs", args={"query": "rag"})
    yield TokenEvent(type="token", content="Hello")
    yield FinalEvent(type="final", content="Hello")

with patch("job_rag.api.routes.stream_agent", side_effect=fake_stream):
    async with LifespanManager(app, startup_timeout=60):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # ← method+payload swap happens here
```

Pattern stays — only the `client.get(..., params=...)` → `client.post(..., json=...)` call sites change. All 3 call sites are in `tests/test_api.py` (lines 186, 365, plus any sibling streaming context calls — grep `client.stream\("GET", "/agent/stream` and `client\.get\("/agent/stream` to enumerate).

---

### `tests/test_sse_contract.py` modify (contract test)

**Analog:** `tests/test_sse_contract.py:87-135` itself (`TestOpenAPISchema.test_openapi_includes_agent_event` — schema-only assertions are method-agnostic).

**Existing pattern that survives unchanged** (`test_sse_contract.py:108-118`):
```python
spec = app.openapi()
schemas = spec.get("components", {}).get("schemas", {})
event_classes = ["TokenEvent", "ToolStartEvent", "ToolEndEvent",
                 "HeartbeatEvent", "ErrorEvent", "FinalEvent"]
found = [c for c in event_classes if c in schemas]
```

This test asserts SHAPE not METHOD. Phase 6 D-04 explicitly notes "Phase 6 keeps the schema intent, just changes the operation method" — so this file is checked for any direct method assertions (likely no-op). If grep finds `client.get` / `client.stream("GET"` against `/agent/stream` in this file, swap to POST per the test_api.py pattern above.

---

### `frontend/src/api/agent.ts` fill stub (service module — typed authedFetch wrapper)

**Analog:** `frontend/src/api/jobs.ts` (3 typed authedFetch wrappers per dashboard endpoint).

**Imports pattern** (`jobs.ts:12-13`):
```typescript
import { authedFetch } from '@/api/authedFetch'
import type { components } from '@/api/types'
```

**Function-shape pattern** (`jobs.ts:40-47` — the `topSkills` shape Phase 6 mirrors for `streamAgent`):
```typescript
/** GET /dashboard/top-skills - DASH-01 */
export async function topSkills(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<TopSkillsResponse> {
  const res = await authedFetch(`/dashboard/top-skills${buildFilterQuery(filters)}`, { signal })
  if (!res.ok) throw new Error(`top-skills: HTTP ${res.status}`)
  return res.json() as Promise<TopSkillsResponse>
}
```

**Phase 6 D-27 streamAgent shape** (per RESEARCH §"Code Examples — streamAgent typed helper"):
```typescript
import { authedFetch } from '@/api/authedFetch'
import { readSSEStream, type AgentEvent } from '@/api/readSSEStream'

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

**Key differences from `jobs.ts` pattern:**
- Returns an `AsyncIterable<AgentEvent>` from `readSSEStream(response)` instead of `res.json()` — streaming, not request-response
- `signal` is REQUIRED (not optional) — Phase 6 D-26 mandates abort capability per submit
- POST with explicit `Content-Type: application/json` + `JSON.stringify({ query })` body — matches Phase 6 D-01 backend contract
- `readSSEStream` handles the `!res.ok` check internally (it throws in its own guard at lines 41-42 of `readSSEStream.ts`); no duplicate check needed

**Comment-as-stub already in `agent.ts`** (lines 1-3) gives the executor the intent:
```typescript
// Phase 6 (Chat) fills this module per D-15.
// export async function streamAgent(query, signal) { ... }   // uses readSSEStream
```

---

### `frontend/src/routes/Chat.tsx` replace PhasePlaceholder (route page — composition)

**Analog:** `frontend/src/routes/Dashboard.tsx` (Phase 5 — exactly the same Phase 4→5/6 PhasePlaceholder replacement progression).

**Pattern** (`Dashboard.tsx:5-21` — composition of feature-folder components with route-level layout class):
```typescript
import { CvVsMarketCard } from '@/components/dashboard/CvVsMarketCard'
import { DashboardFilters } from '@/components/dashboard/DashboardFilters'
import { SalaryBandsCard } from '@/components/dashboard/SalaryBandsCard'
import { TopSkillsCard } from '@/components/dashboard/TopSkillsCard'

export function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6" data-testid="dashboard-page">
      <DashboardFilters />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <TopSkillsCard />
        <SalaryBandsCard />
        <CvVsMarketCard />
      </div>
    </div>
  )
}
```

**Phase 6 ChatPage adaptation** (per UI-SPEC §3 layout — `max-w-3xl` for chat, full-height column for transcript+composer):

```typescript
import { useRef, useState } from 'react'

import { ChatComposer } from '@/components/chat/ChatComposer'
import { ChatEmptyState } from '@/components/chat/ChatEmptyState'
import { ChatTranscript } from '@/components/chat/ChatTranscript'
import { useChatStream } from '@/components/chat/useChatStream'

export function ChatPage() {
  const { items, isStreaming, coldStart, networkError, submit, stop, toggleToolExpanded } =
    useChatStream()
  const [composerValue, setComposerValue] = useState('')
  const composerRef = useRef<HTMLTextAreaElement>(null)

  return (
    <div className="mx-auto max-w-3xl flex h-[calc(100vh-3rem)] flex-col" data-testid="chat-page">
      {items.length === 0 && !isStreaming ? (
        <ChatEmptyState onSampleClick={(q) => { setComposerValue(q); composerRef.current?.focus() }} />
      ) : (
        <ChatTranscript
          items={items}
          isStreaming={isStreaming}
          coldStart={coldStart}
          networkError={networkError}
          onToggleToolExpanded={toggleToolExpanded}
        />
      )}
      <ChatComposer
        ref={composerRef}
        value={composerValue}
        onChange={setComposerValue}
        onSubmit={() => { submit(composerValue); setComposerValue('') }}
        onStop={stop}
        isStreaming={isStreaming}
      />
    </div>
  )
}
```

**Current placeholder being replaced** (`Chat.tsx:1-5` — full file):
```typescript
import { PhasePlaceholder } from '@/components/PhasePlaceholder'

export function ChatPage() {
  return <PhasePlaceholder phase={6} feature="Chat" />
}
```

**Key constraint:** Named export `ChatPage` MUST be preserved (lazy import in App.tsx). Dashboard.tsx confirms the naming convention.

---

### `frontend/src/routes/DebugAgentStream.tsx` 1-line fix

**Analog:** Self. Phase 4 D-16 shipped the file; Phase 6 D-27 only swaps a string literal in the body.

**Current body assembly** (`DebugAgentStream.tsx:34-39`):
```typescript
const res = await authedFetch('/agent/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: query }),
  signal: abortRef.current.signal,
})
```

**Phase 6 D-27 transformation** (per RESEARCH §"DebugAgentStream Body-Key Fix"):
```typescript
body: JSON.stringify({ query }),
```

That is the entire change — `message: query` → `query` (shorthand). Defends Pitfall H closure: backend `AgentQuery(query: str)` rejects unknown field `message` with 422.

**Plan checker grep guard** (per RESEARCH §Pitfall H):
```bash
grep -n "body: JSON.stringify({ message:" frontend/src/routes/DebugAgentStream.tsx
# expected output: 0 lines (no match)
```

---

### `frontend/src/components/chat/ChatTranscript.tsx` (NEW — presentation component, list-shaped log)

**Analog:** `frontend/src/components/dashboard/TopSkillsCard.tsx` (Card-shaped panel with skeleton/error/empty/data branches) — but ChatTranscript is a `<ol role="log">` not a Card, and the loading/error/empty branches operate per-item not per-card. The closer pattern is the per-item conditional render from the same file's `SkillsBarList`.

**Imports pattern** (per Phase 4/5 convention — `TopSkillsCard.tsx:1-19`):
```typescript
import { useEffect, useRef, useState } from 'react'
import { AlertCircle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ChatMessage } from '@/components/chat/ChatMessage'
import { ToolChip } from '@/components/chat/ToolChip'
import type { TranscriptItem, NetworkError } from '@/components/chat/types'
```

**Smart-autoscroll pattern** (NEW pattern, per RESEARCH §"Smart Autoscroll Pattern"):
```typescript
const bottomSentinelRef = useRef<HTMLDivElement>(null)
const [autoscrollEngaged, setAutoscrollEngaged] = useState(true)

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

useEffect(() => {
  if (!autoscrollEngaged) return
  bottomSentinelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}, [items, autoscrollEngaged])
```

**Network-error Alert pattern** (mirror `TopSkillsCard.tsx:100-106` — destructive Alert with `AlertCircle` icon):
```typescript
{networkError && (
  <div className="mx-4 mt-4">
    <Alert variant="destructive" role="alert">
      <AlertCircle className="h-4 w-4" aria-hidden="true" />
      <AlertTitle>{networkError.message}</AlertTitle>
    </Alert>
  </div>
)}
```

**Discriminated render pattern** (per UI-SPEC §6a — tool-call goes to ToolChip, everything else goes to ChatMessage):
```typescript
<ol role="log" aria-live="polite" aria-relevant="additions" className="space-y-4">
  {items.map((item) =>
    item.kind === 'tool-call'
      ? <ToolChip key={item.id} item={item} onToggleExpand={onToggleToolExpanded} />
      : <ChatMessage key={item.id} item={item} coldStart={coldStart} />
  )}
  <div ref={bottomSentinelRef} aria-hidden="true" className="h-px w-px" />
</ol>
```

**Container layout class** (per UI-SPEC §3): `flex-1 overflow-y-auto px-4 py-6`

---

### `frontend/src/components/chat/ChatMessage.tsx` (NEW — presentation component with 3 variants)

**Analog:** `frontend/src/components/dashboard/TopSkillsCard.tsx` lines 40-69 (`SkillRow` internal component pattern) for the "single-item discriminated render". For the inline subcomponent pattern (`StreamingCursor`, `ThinkingDots`), the same file's `TopSkillsSkeleton` + `SkillRow` + `SkillsBarList` co-location convention is the precedent.

**Imports pattern** (per UI-SPEC §6b):
```typescript
import { AlertCircle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { TranscriptItem } from '@/components/chat/types'
import { ERROR_TITLE, ERROR_BODY } from '@/components/chat/types'
```

**Inline subcomponent pattern** (mirror `TopSkillsCard.tsx:24-38` `TopSkillsSkeleton` co-location):
```typescript
function StreamingCursor() {
  return <span className="animate-blink" aria-hidden="true">▍</span>
}

function ThinkingDots() {
  return (
    <>
      <span className="animate-pulse motion-reduce:animate-none" style={{ animationDelay: '0ms' }}>.</span>
      <span className="animate-pulse motion-reduce:animate-none" style={{ animationDelay: '150ms' }}>.</span>
      <span className="animate-pulse motion-reduce:animate-none" style={{ animationDelay: '300ms' }}>.</span>
    </>
  )
}
```

**Discriminated render pattern** (per UI-SPEC §6b — verbatim JSX skeletons for 3 variants):
- `user-message`: `<li><span role-label>YOU</span><p>{content}</p></li>`
- `assistant-text`: same with `AGENT` label + conditional cursor / dots / stopped suffix
- `error`: shadcn destructive Alert with `ERROR_TITLE[reason]` + `ERROR_BODY[reason] ?? message` (per D-23)

**Error Alert pattern** (mirror `TopSkillsCard.tsx:100-106` exactly):
```typescript
<Alert variant="destructive" role="alert">
  <AlertCircle className="h-4 w-4" aria-hidden="true" />
  <AlertTitle>{ERROR_TITLE[item.reason]}</AlertTitle>
  <AlertDescription>{ERROR_BODY[item.reason] ?? item.message}</AlertDescription>
</Alert>
```

**Role label class string** (per UI-SPEC §4 documented exception):
```
text-[10px] uppercase tracking-wider text-muted-foreground
```

---

### `frontend/src/components/chat/ToolChip.tsx` (NEW — collapsible chip + Dialog)

**Analog:** `frontend/src/components/dashboard/TopSkillsDialog.tsx` (shadcn Dialog wrapper with `max-w-2xl` + `max-h-[70vh]` scrollable body + footer Close button) is the **EXACT** Dialog pattern Phase 6 mirrors. The Collapsible portion is NEW (no existing analog — shadcn `collapsible` ships in this phase).

**Dialog pattern (exact mirror of TopSkillsDialog.tsx:13-62):**
```typescript
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

// inside component:
<Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
  <DialogContent className="max-w-2xl">
    <DialogHeader>
      <DialogTitle>Tool output</DialogTitle>
      <DialogDescription>
        Full output of <span className="font-mono">{item.name}</span>
      </DialogDescription>
    </DialogHeader>
    <div className="max-h-[70vh] overflow-y-auto">
      <pre className="rounded-sm bg-muted p-2 text-xs font-mono whitespace-pre-wrap">
        {item.output ?? ''}
      </pre>
    </div>
    <DialogFooter>
      <Button variant="ghost" onClick={() => setDialogOpen(false)}>
        Close
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

The shape mirrors `TopSkillsDialog.tsx:22-62` 1:1 (same `max-w-2xl`, same `max-h-[70vh]`, same `<Button variant="ghost">Close</Button>` footer). Phase 5 dialog content is a `<table>`; Phase 6 dialog content is a `<pre>`. Structure identical.

**Collapsible pattern (NEW)** — full JSX skeleton already locked in UI-SPEC §6c lines 547-636 (read those directly; verbatim copy-paste with `Collapsible` + `CollapsibleTrigger` + `CollapsibleContent` from `@/components/ui/collapsible`).

**Inline state pattern** (mirror `TopSkillsCard.tsx:84-85` — local `useState` for dialog `open`):
```typescript
const [dialogOpen, setDialogOpen] = useState(false)
```

**"Show full output" button pattern** (mirror `TopSkillsCard.tsx:119-121` — `Button variant="link" size="sm"` triggers dialog):
```typescript
<Button variant="link" size="sm" onClick={() => setDialogOpen(true)}>
  Show full output
</Button>
```

(`Show more` in TopSkillsCard uses `variant="ghost"`; ToolChip uses `variant="link"` per UI-SPEC §6c table — but the click → setOpen(true) → Dialog pattern is exact.)

---

### `frontend/src/components/chat/ChatComposer.tsx` (NEW — controlled multi-line input + Send/Stop)

**Analog:** `frontend/src/routes/DebugAgentStream.tsx` (Phase 4 D-16 — `Input` + Send button + `disabled={streaming}` + AbortController stored in ref). DebugAgentStream is the **direct shape** — Phase 6's ChatComposer just swaps `Input` → `Textarea`, adds Stop button, and lifts state ownership to the parent.

**Imports pattern** (mirror `DebugAgentStream.tsx:1-8`):
```typescript
import { useEffect, useRef } from 'react'
import { Send, Square } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
```

**DebugAgentStream's Input + Send pattern** (`DebugAgentStream.tsx:61-71` — the precedent):
```typescript
<div className="flex gap-2">
  <Input
    placeholder="Ask the agent something…"
    value={query}
    onChange={(e) => setQuery(e.target.value)}
    disabled={streaming}
  />
  <Button onClick={send} disabled={streaming}>
    Send query
  </Button>
</div>
```

**Phase 6 ChatComposer adaptation** — full JSX skeleton already locked verbatim in UI-SPEC §6d lines 738-814. Key Phase 6 additions vs DebugAgentStream:
- `<Textarea>` instead of `<Input>` (multi-line)
- Sticky-bottom container: `sticky bottom-0 border-t bg-background px-4 py-3`
- Stop button conditional render with `variant="destructive"` (DebugAgentStream has no Stop)
- Auto-grow `useEffect` on `value` (DebugAgentStream's Input has no auto-grow)
- Enter/Shift+Enter `onKeyDown` keymap (DebugAgentStream has none)
- `aria-label="Ask the agent"` + `aria-label="Send message"` + `aria-label="Stop streaming response"` per D-32

**Auto-grow `useEffect` pattern** (NEW — UI-SPEC §6d JSX skeleton lines 757-762):
```typescript
const textareaRef = useRef<HTMLTextAreaElement>(null)

useEffect(() => {
  const ta = textareaRef.current
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = `${ta.scrollHeight}px`
}, [value])
```

**Keymap pattern** (NEW — UI-SPEC §6d JSX skeleton lines 764-771):
```typescript
const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (!isStreaming && !disabled && value.trim() !== '') {
      onSubmit()
    }
  }
}
```

**Note on state lifting:** DebugAgentStream owns its own `query` state via `useState`. ChatComposer is fully controlled — the Chat route owns `composerValue` so EmptyState sample chips can write into it (D-25). The Chat route pattern mirrors Dashboard.tsx's "compose stateful feature components" approach but with the value lifted higher than in TopSkillsCard's pattern.

---

### `frontend/src/components/chat/ChatEmptyState.tsx` (NEW — wraps EmptyState primitive with chat-specific copy + sample chips)

**Analog:** `frontend/src/components/PhasePlaceholder.tsx` is the **EXACT** precedent for "compose EmptyState with feature-specific copy via lookup table". Phase 6 ChatEmptyState extends the pattern by adding a sample-chip cluster underneath.

**PhasePlaceholder pattern** (`PhasePlaceholder.tsx:16-42`):
```typescript
const COPY: Record<...> = {
  Chat: {
    heading: 'Chat coming soon',
    body: 'The streaming chat surface lands in Phase 6. ...',
    icon: MessageSquare,
  },
  // ...
}

export function PhasePlaceholder({ feature }: PhasePlaceholderProps) {
  const copy = COPY[feature]
  return <EmptyState icon={copy.icon} heading={copy.heading} body={copy.body} />
}
```

**Phase 6 ChatEmptyState adaptation** — UI-SPEC §6e JSX skeleton lines 890-934 has the verbatim locked structure. Key differences vs PhasePlaceholder:
- Inlines Card + CardContent (instead of `<EmptyState>` primitive) because the sample-chip cluster needs to sit INSIDE the Card per UI-SPEC §6e visual structure
- Adds a flex-wrap cluster of `<Badge variant="outline" role="button" tabIndex={0} onClick={onSampleClick}>` chips
- Locks copy verbatim (4 sample queries, exact heading + body text per D-25)

**Badge-as-button pattern** (per UI-SPEC §6e — Badge rendered as `<span>` underlying, so explicit `role="button" tabIndex={0}` + `onKeyDown` for keyboard activation):
```typescript
<Badge
  key={query}
  variant="outline"
  className="cursor-pointer hover:bg-muted transition-colors text-xs whitespace-normal text-left h-auto py-1 px-2"
  role="button"
  tabIndex={0}
  onClick={() => onSampleClick(query)}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSampleClick(query)
    }
  }}
>
  {query}
</Badge>
```

---

### `frontend/src/components/chat/useChatStream.ts` (NEW — custom hook owning stream state + AbortController + cold-start timer)

**Analog (for TYPED-HOOK SHAPE):** `frontend/src/components/dashboard/useDashboardFilters.ts` (Phase 5 D-17 — typed custom hook with explicit return type, lives in feature folder, owns state via React primitives, exports companion types from same file).

**Analog (for STREAMING-LIFECYCLE SHAPE):** `frontend/src/routes/DebugAgentStream.tsx` (Phase 4 D-16 — `AbortController` in `useRef`, `try/catch/finally` around `for await (... readSSEStream)`, `setStreaming(true/false)` lifecycle).

**Phase 6 useChatStream combines both:**

**Typed hook shape from useDashboardFilters.ts:**
- File lives at `components/chat/useChatStream.ts` (feature folder, NOT `hooks/`)
- Exports a single named function `useChatStream()`
- Companion types live in sibling `components/chat/types.ts`
- Return type is an inline object literal (per useDashboardFilters.ts:98 `return { filters, setFilters }`)

**Streaming lifecycle shape from DebugAgentStream.tsx:**
- `useRef<AbortController | null>(null)` (DebugAgentStream.tsx:26)
- `abortRef.current = new AbortController()` on each submit (line 32)
- `for await (const event of readSSEStream(res))` loop (line 42)
- `try { ... } catch (err) { ... } finally { setStreaming(false) }` (lines 33-53)
- `await authedFetch('/agent/stream', { method: 'POST', ..., signal: abortRef.current.signal })` (lines 34-39)

**Phase 6 useChatStream additions (NO existing analog):**
- `useReducer(transcriptReducer, [])` for transcript items (per RESEARCH Pattern 3)
- `useEffect(() => () => abortControllerRef.current?.abort(), [])` cleanup on unmount (per Pitfall A)
- `setTimeout(10_000)` cold-start timer in `coldStartTimerRef` (per D-19)
- AbortError vs network-error triage in catch block (per Pitfall B)
- `pendingToolIds[]` map for tool_start ↔ tool_end matching (per RESEARCH §"Code Examples — useChatStream Hook")
- `crypto.randomUUID()` for stable item IDs (per D-07)

**Full reducer + hook skeleton locked in RESEARCH §"Code Examples — useChatStream Hook Skeleton" lines 712-944** — executor copies that pattern verbatim, adapting only the import paths.

**Error classification helper** (RESEARCH lines 932-943 — pattern matches D-24 copy table):
```typescript
function classifyNetworkError(err: unknown): NetworkError {
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

---

### `frontend/src/components/chat/types.ts` (NEW — discriminated union + ERROR copy tables)

**Analog:** `frontend/src/api/readSSEStream.ts` lines 1-23 (discriminated union pattern for AgentEvent — perfect template for TranscriptItem) + `frontend/src/components/dashboard/useDashboardFilters.ts` lines 17-26 (feature-folder type module convention — re-exports codegen types + declares local union types).

**Discriminated union pattern** (mirror `readSSEStream.ts:10-23`):
```typescript
import type { components } from '@/api/types'

export type TokenEvent = components['schemas']['TokenEvent']
export type ToolStartEvent = components['schemas']['ToolStartEvent']
// ...

export type AgentEvent =
  | TokenEvent
  | ToolStartEvent
  | ToolEndEvent
  // ...
```

**Phase 6 D-07 TranscriptItem union** (per CONTEXT.md D-07 verbatim, adapted for `stopped?: boolean` per D-16):
```typescript
import type { ErrorEvent as SseErrorEvent } from '@/api/readSSEStream'

export type TranscriptItem =
  | { kind: 'user-message'; id: string; content: string }
  | { kind: 'assistant-text'; id: string; content: string; streaming: boolean; stopped?: boolean }
  | { kind: 'tool-call'; id: string; name: string; args: object | null; output: string | null; expanded: boolean }
  | { kind: 'error'; id: string; reason: SseErrorEvent['reason']; message: string }
```

**NetworkError type** (per D-24 classification):
```typescript
export type NetworkError = {
  kind: '401' | '403' | '5xx' | 'unreachable' | 'unknown'
  message: string
}
```

**TranscriptAction union** (for `useReducer` typing per RESEARCH §"Code Examples"):
```typescript
export type TranscriptAction =
  | { type: 'APPEND_USER_MESSAGE'; id: string; content: string }
  | { type: 'APPEND_ASSISTANT_TEXT'; id: string }
  | { type: 'APPEND_TOKEN'; content: string }
  | { type: 'CLOSE_CURRENT_TEXT' }
  | { type: 'APPEND_TOOL_START'; id: string; name: string; args: object | null }
  | { type: 'UPDATE_TOOL_OUTPUT'; id: string; output: string }
  | { type: 'TOGGLE_TOOL_EXPANDED'; id: string }
  | { type: 'APPEND_ERROR'; id: string; reason: SseErrorEvent['reason']; message: string }
  | { type: 'MARK_STOPPED' }
```

**ERROR copy tables** (per D-23 verbatim — UI-SPEC §6b ERROR_TITLE/ERROR_BODY lookup):
```typescript
export const ERROR_TITLE: Record<SseErrorEvent['reason'], string> = {
  agent_timeout: 'Agent timed out',
  shutdown: 'Server restarting',
  llm_error: 'Language model error',
  internal: 'Something went wrong',
}

export const ERROR_BODY: Record<SseErrorEvent['reason'], string | undefined> = {
  agent_timeout: 'The agent took longer than 60 seconds to respond. Try a more specific question, or check the agent logs.',
  shutdown: 'Container is shutting down. Please try again in a moment.',
  llm_error: 'The LLM call failed. Please try again.',
  internal: undefined,  // falls through to item.message (sanitized backend message)
}
```

**Re-export convenience** (per RESEARCH Open Question 3 recommendation):
```typescript
export type { AgentEvent, ErrorEvent } from '@/api/readSSEStream'
```

---

### `frontend/src/components/ui/collapsible.tsx` (NEW shadcn install)

**Analog:** `frontend/src/components/ui/dialog.tsx` (similar Radix-backed shadcn primitive). No direct copy-from; the file is CLI-generated by `npx shadcn@latest add collapsible`.

**Install command** (per UI-SPEC §2 + Pitfall 8 from Phase 5 — bare invocation):
```bash
cd frontend && npx shadcn@latest add collapsible textarea
```

**Verification** (per RESEARCH §"Installation"):
```bash
test -f src/components/ui/collapsible.tsx && echo "collapsible installed"
grep -q "from \"radix-ui\"" src/components/ui/collapsible.tsx && echo "uses unified radix-ui import"
```

The unified `radix-ui` package is already in `frontend/package.json` (`^1.4.3`). No separate Radix install needed.

---

### `frontend/src/components/ui/textarea.tsx` (NEW shadcn install)

**Analog:** `frontend/src/components/ui/input.tsx` (similar shadcn primitive — single-element wrapper with CVA styling, no Radix peer).

Installed alongside `collapsible` via the same `npx shadcn@latest add` invocation.

---

### `frontend/src/test/useChatStream.test.tsx` (NEW — hook test combining renderHook + mock fetch)

**Analog (renderHook pattern):** `frontend/src/components/dashboard/useDashboardFilters.test.tsx` (Phase 5 — `renderHook` + `act` + wrapper).

**Analog (ReadableStream mock pattern):** `frontend/src/test/readSSEStream.test.ts` (Phase 4 — `streamFromString` helper produces a Response with a mock ReadableStream body).

**Imports pattern** (mirror useDashboardFilters.test.tsx:11-16):
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'

import { useChatStream } from '@/components/chat/useChatStream'
import { mockSseResponse, mockSseHangingResponse } from '@/test/sseMockUtils'
```

**Mock-streamAgent pattern** (mirror Phase 5 `vi.mock('@/api/jobs', ...)` from TopSkillsCard.test.tsx:9-13):
```typescript
vi.mock('@/api/agent', () => ({
  streamAgent: vi.fn(),
}))
import { streamAgent } from '@/api/agent'
```

**ReadableStream mock pattern** (extract from readSSEStream.test.ts:4-13):
```typescript
import { streamAgent } from '@/api/agent'
import { mockSseResponse } from '@/test/sseMockUtils'

vi.mocked(streamAgent).mockResolvedValue(
  readSSEStream(mockSseResponse([
    { type: 'token', content: 'Hello' },
    { type: 'final', content: 'Hello' },
  ]))
)
```

**Storage spy pattern (CHAT-06 verification)** — NEW; recommended pattern:
```typescript
const setItemSpy = vi.spyOn(window.localStorage, 'setItem')
// ... run hook submit cycles ...
expect(setItemSpy).not.toHaveBeenCalled()
```

(`setup.ts` already installs a Storage shim on `window.localStorage`, so this spy works deterministically per the existing `installLocalStorageShim()` pattern in `frontend/src/test/setup.ts`.)

**Fake timers pattern for cold-start (Pitfall D)** — NEW; standard Vitest pattern:
```typescript
vi.useFakeTimers()
await act(async () => { result.current.submit('test') })
vi.advanceTimersByTime(11_000)
expect(result.current.coldStart).toBe(true)
```

---

### `frontend/src/test/ToolChip.test.tsx` (NEW — component test)

**Analog:** `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx` (Phase 5 component test with `render` + `screen.findByText`).

**Imports + render pattern** (mirror TopSkillsCard.test.tsx:1-26):
```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import { ToolChip } from '@/components/chat/ToolChip'

// No QueryClientProvider needed — ToolChip is pure presentation.
function renderToolChip(item: ToolCallItem, onToggleExpand = vi.fn()) {
  return render(<ToolChip item={item} onToggleExpand={onToggleExpand} />)
}
```

**Assertions pattern** (mirror TopSkillsCard.test.tsx:28-50):
```typescript
describe('ToolChip', () => {
  it('renders running state with pulsing dot when output === null', () => {
    renderToolChip({ kind: 'tool-call', id: '1', name: 'search_jobs',
                    args: { query: 'rag' }, output: null, expanded: false })
    expect(screen.getByText('search_jobs')).toBeInTheDocument()
  })

  it('shows "Show full output" when output > 200 chars', () => {
    const longOutput = 'x'.repeat(300)
    renderToolChip({ kind: 'tool-call', id: '1', name: 'search_jobs',
                    args: null, output: longOutput, expanded: true })
    expect(screen.getByRole('button', { name: 'Show full output' })).toBeInTheDocument()
  })

  it('opens Dialog on "Show full output" click', () => {
    // ... fireEvent.click + screen.findByText('Tool output')
  })
})
```

---

### `frontend/src/test/ChatComposer.test.tsx` (NEW — component test)

**Analog:** `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx` (Phase 5 controlled-input test — verifies aria labels and rendered text).

**Test cases per RESEARCH §Validation Architecture → Test Map:**
- Enter submits (no shift) → assert `onSubmit` called
- Shift+Enter inserts newline → assert `onSubmit` NOT called
- Stop button replaces Send during streaming → assert `getByRole('button', { name: 'Stop streaming response' })`
- Disabled-while-streaming → assert Textarea has `disabled` attribute

---

### `frontend/src/test/ChatTranscript.test.tsx` (NEW — component test)

**Analog:** `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx` (Phase 5 data-driven render test with branching states).

**Test cases per RESEARCH §Validation Architecture → Test Map:**
- Items render in order
- Smart-autoscroll respects user scroll position
- Network-error Alert conditional render

---

### `frontend/src/test/sseMockUtils.ts` (NEW shared test util)

**Analog:** `frontend/src/test/readSSEStream.test.ts:4-13` (`streamFromString` inline helper — Phase 4 D-16 precedent).

**Extraction pattern** (per RESEARCH §"Mock Fetch for Vitest" lines 994-1042 — verbatim copy):
```typescript
import type { AgentEvent } from '@/api/readSSEStream'

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

export function mockSseHangingResponse(initialEvents: AgentEvent[]): Response {
  // ... yields events but never closes — for cancellation tests
}
```

---

## Shared Patterns

### Pattern S1: Imports — feature-folder + path aliases

**Source:** Phase 4/5 convention — `tsconfig.json` aliases `@/` to `./src/`. ALL chat-feature files use absolute imports.

**Apply to:** Every Phase 6 frontend file.

**Example** (mirror `frontend/src/components/dashboard/TopSkillsCard.tsx:1-19`):
```typescript
import { useState } from 'react'                              // React first
import { useQuery } from '@tanstack/react-query'              // third-party
import { AlertCircle, BarChart3 } from 'lucide-react'         // third-party

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'  // ui primitives
import { Button } from '@/components/ui/button'
// ...
import { EmptyState } from '@/components/EmptyState'           // shared components

import { topSkills, type TopSkillItem } from '@/api/jobs'      // API/services
import { useDashboardFilters } from './useDashboardFilters'    // sibling (relative OK within feature folder)
import { TopSkillsDialog } from './TopSkillsDialog'
import { describeError } from './errors'
```

Order: React → third-party → `@/components/ui/*` → `@/components/*` → `@/api/*` → siblings via relative path.

---

### Pattern S2: Auth — inherit `authedFetch` (no per-route guard)

**Source:** `frontend/src/api/authedFetch.ts` (Phase 4 D-13).

**Apply to:** `frontend/src/api/agent.ts` `streamAgent` (the only Phase 6 frontend network call).

**Pattern** (from `authedFetch.ts:54-82`):
```typescript
import { authedFetch } from '@/api/authedFetch'

// authedFetch handles:
//   - acquireTokenSilent before every call (MSAL)
//   - Authorization: Bearer <jwt> header attachment
//   - 401 retry-after-refresh; second 401 → acquireTokenRedirect
//   - InteractionRequiredAuthError → full-page redirect
//   - signal threading
const res = await authedFetch('/agent/stream', { method: 'POST', body, signal })
```

No additional auth code in `agent.ts` or `useChatStream.ts`. Route-level `AuthGate` (Phase 4 D-18) wraps `/chat` upstream in `App.tsx`.

---

### Pattern S3: Error handling — destructive Alert with `AlertCircle` icon

**Source:** `frontend/src/components/dashboard/TopSkillsCard.tsx:100-106` (Phase 5 — all 3 dashboard widgets use the identical Alert shape).

**Apply to:**
- `ChatTranscript.tsx` (network-error Alert at top of route per D-24)
- `ChatMessage.tsx` (inline destructive Alert for `kind: 'error'` items per D-22 + D-23)

**Pattern:**
```typescript
import { AlertCircle } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

<Alert variant="destructive" role="alert">
  <AlertCircle className="h-4 w-4" aria-hidden="true" />
  <AlertTitle>{titleText}</AlertTitle>
  <AlertDescription>{bodyText}</AlertDescription>
</Alert>
```

shadcn `Alert` component already includes `role="alert"` internally (per `alert.tsx:30`), so the explicit `role="alert"` prop is redundant-but-explicit (matches Phase 5 widget convention).

---

### Pattern S4: Dialog — shadcn Dialog with `max-w-2xl` body + `max-h-[70vh]` scroll + ghost Close

**Source:** `frontend/src/components/dashboard/TopSkillsDialog.tsx` (Phase 5 — direct precedent).

**Apply to:** `ToolChip.tsx` "Show full output" Dialog.

**Pattern:**
```typescript
<Dialog open={open} onOpenChange={onOpenChange}>
  <DialogContent className="max-w-2xl">
    <DialogHeader>
      <DialogTitle>{title}</DialogTitle>
      <DialogDescription>{description}</DialogDescription>
    </DialogHeader>
    <div className="max-h-[70vh] overflow-y-auto">
      {/* body content */}
    </div>
    <DialogFooter>
      <Button variant="ghost" onClick={() => onOpenChange(false)}>
        Close
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

Radix Dialog defaults handle focus trap, Escape close, overlay click — no manual a11y wiring needed.

---

### Pattern S5: Empty state — compose `EmptyState` primitive with feature copy

**Source:** `frontend/src/components/PhasePlaceholder.tsx` (Phase 4 D-19 — exact precedent for "compose EmptyState with feature-specific COPY lookup").

**Apply to:** `ChatEmptyState.tsx` — extends the pattern by adding a sample-chip cluster inside the Card.

**Pattern (PhasePlaceholder.tsx:37-42)**:
```typescript
import { EmptyState } from '@/components/EmptyState'

const COPY = { ... }

export function FeatureEmptyState({ feature }) {
  const copy = COPY[feature]
  return <EmptyState icon={copy.icon} heading={copy.heading} body={copy.body} />
}
```

Phase 6 ChatEmptyState inlines Card + CardContent (rather than wrapping EmptyState primitive) because the sample-chip cluster must sit INSIDE the same Card (per UI-SPEC §6e visual structure). The COPY lookup convention still applies — `SAMPLE_QUERIES` const array (UI-SPEC §6e lines 895-900) is the equivalent.

---

### Pattern S6: Typed custom hook + companion type module (feature folder)

**Source:** `frontend/src/components/dashboard/useDashboardFilters.ts` (Phase 5 D-17 — typed hook + sibling type definitions).

**Apply to:**
- `useChatStream.ts` (hook signature, return type, types co-located in `types.ts` sibling)

**Pattern conventions** (from useDashboardFilters.ts):
- File lives at `components/<feature>/use<Feature><Concern>.ts` (NOT `hooks/`)
- Companion types in `components/<feature>/types.ts` or inline in hook file
- Hook returns inline object literal: `return { items, isStreaming, ... }`
- Type definitions exported as `export type` (not default)
- React hooks (`useState`, `useReducer`, `useRef`, `useEffect`, `useCallback`) used directly — no abstractions over React primitives

---

### Pattern S7: Test file location — `frontend/src/test/<Subject>.test.tsx`

**Source:** Phase 4 testing baseline — `frontend/src/test/AppShell.test.tsx`, `AuthGate.test.tsx`, `readSSEStream.test.ts`, etc. (NOT `frontend/src/test/__tests__/`; the `__tests__` subfolder is dashboard-only).

**Apply to:** All 4 new Phase 6 test files + 1 shared util.

**Per RESEARCH §"Plan grain":**
- `frontend/src/test/useChatStream.test.tsx`
- `frontend/src/test/ToolChip.test.tsx`
- `frontend/src/test/ChatComposer.test.tsx`
- `frontend/src/test/ChatTranscript.test.tsx`
- `frontend/src/test/sseMockUtils.ts` (shared test util)

**Setup pattern** (`frontend/src/test/setup.ts` already installs `localStorage` shim + `matchMedia` stub; no Phase 6 changes needed).

---

### Pattern S8: shadcn install via bare `npx shadcn@latest add`

**Source:** Phase 4 + Phase 5 install workflow (Phase 5 Pitfall 8 enforcement: NO `--style` flag).

**Apply to:** Phase 6 Wave 0 — `collapsible` + `textarea` installs.

**Pattern:**
```bash
cd frontend && npx shadcn@latest add collapsible textarea
```

**Verification** (post-install):
```bash
test -f src/components/ui/collapsible.tsx && test -f src/components/ui/textarea.tsx
```

The CLI reads `components.json` (`style=radix-nova`, `baseColor=neutral`, `iconLibrary=lucide`) and writes into `src/components/ui/`. Passing flags risks clobbering preset.

---

### Pattern S9: Backend test — `LifespanManager` + `ASGITransport` + `vi.patch` of `stream_agent`

**Source:** `tests/test_api.py:180-186` (`TestAgentEndpoint.test_agent_stream_emits_sse_events` — the canonical mock-stream test setup that Phase 6 D-03 mutates).

**Apply to:** Phase 6 test_api.py mutations.

**Pattern (UNCHANGED — only the method/payload swap inside the `async with client.<method>(...)` line is mutated):**
```python
from asgi_lifespan import LifespanManager
from job_rag.api.sse import FinalEvent, TokenEvent, ToolStartEvent

async def fake_stream(_query):
    yield ToolStartEvent(type="tool_start", name="search_jobs", args={"query": "rag"})
    yield TokenEvent(type="token", content="Hello")
    yield FinalEvent(type="final", content="Hello")

with patch("job_rag.api.routes.stream_agent", side_effect=fake_stream):
    async with LifespanManager(app, startup_timeout=60):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/agent/stream", json={"query": "test"})  # ← swap GET→POST here
```

---

### Pattern S10: Structlog backend logging (no changes in Phase 6)

**Source:** `src/job_rag/logging.py` + structlog convention.

**Apply to:** `src/job_rag/api/routes.py` `/agent/stream` handler — already emits structured logs; Phase 6 D-01 mutation doesn't add or remove log lines.

**Pattern verified:** Phase 6 backend changes don't touch logging. The frontend useChatStream hook has no `console.log` calls per Phase 5 production convention.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/components/ui/collapsible.tsx` | shadcn primitive | n/a | CLI-generated; closest precedent is `dialog.tsx` (Radix-backed) but file is auto-emitted by `npx shadcn@latest add` |
| `frontend/src/components/ui/textarea.tsx` | shadcn primitive | n/a | CLI-generated; closest precedent is `input.tsx` (single-element CVA wrapper) but file is auto-emitted |
| `frontend/openapi.snapshot.json` | committed build artifact | n/a | Regenerated via `npm run codegen:snapshot` — no source-code analog; Phase 5 plan 05-03 D-04 is the procedural precedent (in-process `app.openapi()` capture) |
| `frontend/src/api/types.ts` | codegen output | n/a | Generated by openapi-typescript from openapi.snapshot.json; no manual edits |

**Partial-analog files** (these have role-match but need RESEARCH.md or UI-SPEC.md verbatim code as the primary source rather than codebase analog):
- `useChatStream.ts` — useDashboardFilters.ts provides SHAPE; DebugAgentStream.tsx provides LIFECYCLE; the combined hook is new. RESEARCH §"Code Examples — useChatStream Hook Skeleton" lines 712-944 has the verbatim implementation to copy.
- `ToolChip.tsx` Collapsible portion — no existing analog in repo (Phase 6 installs the primitive). UI-SPEC §6c lines 527-636 has the verbatim JSX skeleton.
- `ChatTranscript.tsx` smart-autoscroll IntersectionObserver — no existing analog. RESEARCH §"Smart Autoscroll Pattern" lines 948-992 has the verbatim implementation.
- `app.css` blink keyframes (CSS append) — UI-SPEC §6f lines 982-998 has the verbatim CSS to append. The file structure pattern (`@theme inline`, `:root`, `.dark`, `@layer base`) is preserved.

## Metadata

**Analog search scope:**
- `src/job_rag/api/` — routes.py, sse.py, auth.py (read for handler/dependency patterns)
- `tests/` — test_api.py, test_sse_contract.py (read for test patterns)
- `frontend/src/api/` — agent.ts (stub), authedFetch.ts, jobs.ts, health.ts, readSSEStream.ts, types.ts
- `frontend/src/components/` — AppShell, AuthGate, EmptyState, ErrorBoundary, PhasePlaceholder, RouteSkeleton
- `frontend/src/components/dashboard/` — all 5 widgets + useDashboardFilters hook + types/errors + tests
- `frontend/src/components/ui/` — alert, badge, button, card, dialog, input, skeleton (for primitive composition patterns)
- `frontend/src/routes/` — Dashboard.tsx (PhasePlaceholder→feature replacement pattern), DebugAgentStream.tsx (streaming lifecycle + AbortController shape)
- `frontend/src/test/` — setup.ts (localStorage shim), readSSEStream.test.ts (ReadableStream mock), AuthGate.test.tsx (mock import pattern)

**Files scanned:** 32 (10 backend + 22 frontend)

**Pattern extraction date:** 2026-05-23

**Authoritative source-of-truth hierarchy for planner:**
1. `.planning/phases/06-chat/06-CONTEXT.md` — 32 locked decisions (D-01..D-32)
2. `.planning/phases/06-chat/06-UI-SPEC.md` — verbatim JSX skeletons + class strings + a11y contract (1600+ lines)
3. `.planning/phases/06-chat/06-RESEARCH.md` — verified code excerpts for hook + streamAgent + mockSseResponse + diffs
4. **THIS file (PATTERNS.md)** — codebase analogs and reusable patterns
5. Codebase verbatim (read files at provided line numbers)

Order matters: UI-SPEC + RESEARCH JSX skeletons are LOCKED for net-new components; analog patterns from this file inform STYLE / IMPORTS / ERROR HANDLING / TEST SHAPES around the locked skeletons.
