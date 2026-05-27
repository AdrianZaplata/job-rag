---
phase: 6
slug: chat
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-27
---

# Phase 6 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Phase 6 ships the Chat surface: backend POST `/agent/stream` (method-flipped from
> GET), frontend `useChatStream` hook + `streamAgent` helper, shadcn-based
> presentation components (ChatTranscript / ChatMessage / ToolChip / ChatComposer /
> ChatEmptyState), and a live UAT runbook. All threats trace to either a code
> mitigation grep-verified below or an entry in the Accepted Risks Log.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Browser ↔ SWA | TLS-terminated public ingress to the SPA (HTTPS only in prod) | HTML/JS bundles; static assets |
| SPA ↔ ACA (`/agent/*`) | Authenticated cross-origin POST + SSE stream over HTTPS | Bearer JWT (Authorization header), `{query: string}` POST body, `text/event-stream` AgentEvent frames |
| ACA ↔ OpenAI / LangGraph | Egress to external LLM API (server-side) | Prompt context, tool args, completion tokens |
| ACA ↔ Postgres | Internal VNet TLS connection | Corpus reads (retrieval tools invoked by ReAct agent) |
| Entra External ID ↔ SPA + ACA | OIDC authority issuing/validating ID + access tokens | OAuth2 access token (`oid` claim used for single-user allowlist) |
| Browser DOM ↔ React render tree | In-memory only; CHAT-06 forbids `localStorage`/`indexedDB`/`sessionStorage` writes from `useChatStream` | Transcript items (lost on refresh by design) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-06-01-01 | Tampering | shadcn install (collapsible, textarea) | accept | shadcn primitives generated from registry, lockfile-pinned. `frontend/src/components/ui/{collapsible,textarea}.tsx` present. | closed |
| T-06-01-02 | Info Disclosure | DebugAgentStream body-key + gating | mitigate | `frontend/src/routes/DebugAgentStream.tsx:37` sends `{query}`. App.tsx:21 gates by `import.meta.env.DEV \|\| VITE_DEBUG_PAGES==='true'`; route nested inside `<AuthGate>` (App.tsx:45,72). | closed |
| T-06-01-03 | DoS | New chat test files | accept | Skip-stubs only; no runtime cost in product code. | closed |
| T-06-01-04 | Tampering | types.ts shape + lookup tables | accept | Pure TypeScript types + `Record<reason,string>` lookup tables in `frontend/src/components/chat/types.ts:65-78` (ERROR_TITLE / ERROR_BODY). | closed |
| T-06-01-05 | Info Disclosure | app.css blink keyframes | accept | CSS-only animation; `@media (prefers-reduced-motion: reduce)` carve-out at `frontend/src/app.css:142-145` keeps cursor visible without blink. | closed |
| T-06-02-01 | Tampering | OpenAPI snapshot drift (T-V13) | mitigate | `frontend/openapi.snapshot.json` (1169 lines) committed. CI drift-check at `.github/workflows/ci.yml:178-186` boots the FastAPI app, fetches `/openapi.json`, and diffs against the snapshot — any drift fails CI. | closed |
| T-06-02-02 | Tampering / CSRF | POST `/agent/stream` | accept (inherited Phase 4) | Bearer JWT in `Authorization` header (not a cookie) — see `streamAgent` (`frontend/src/api/agent.ts:20-25`) and `azure_scheme` validation in `src/job_rag/api/auth.py:71-82`. CORS allowlist inherited from Phase 1 D-26. | closed |
| T-06-02-03 | Input Validation | `AgentQuery.query` unbounded length | accept | Pydantic `str` intentionally unbounded; `asyncio.timeout(settings.agent_timeout_seconds)` at `src/job_rag/api/routes.py:416` bounds compute. agent_limit (10/min/IP) caps frequency. | closed |
| T-06-02-04 | Info Disclosure | Stack-trace leak via ErrorEvent | mitigate (inherited Phase 1 D-19) | `_sanitize` defined at `src/job_rag/api/routes.py:99-109` (200-char bound, strips `\n` and `\r`). All three exception branches in `typed_event_generator` (lines 419-453) route through `_sanitize` or a hardcoded message; `asyncio.CancelledError` uses verbatim copy "Server is shutting down — please retry shortly". | closed |
| T-06-02-05 | DoS | POST body without size limit | accept | Single-user v1; `agent_limit = RateLimiter(calls=10, period=60)` (`src/job_rag/api/auth.py:136`) caps inbound frequency. | closed |
| T-06-02-06 | Authentication | AUTH-06 single-user oid guard | accept (inherited Phase 4 D-08) | POST `/agent/stream` declares `dependencies=[Depends(require_api_key), Depends(agent_limit)]` (`src/job_rag/api/routes.py:366`); `get_current_user_id` enforces `oid == settings.seeded_user_entra_oid` (`src/job_rag/api/auth.py:161-167`). | closed |
| T-06-02-07 | Heartbeat / Timeout Regression | sse-starlette ping + `asyncio.timeout(60)` + shutdown drain | mitigate | `ping=settings.heartbeat_interval_seconds` + `ping_message_factory=_heartbeat_factory` (`src/job_rag/api/routes.py:460-461`); `shutdown_event=app.state.shutdown_event, shutdown_grace_period=30.0` (lines 465-466); `active_streams` registration at lines 411-413 / 454-456. `tests/test_api.py::TestAgentStream` covers heartbeat (line 381) + timeout (line 410); shutdown wiring confirmed in `src/job_rag/api/app.py` lifespan (Plan 02 SUMMARY). | closed |
| T-06-03-01 | Info Disclosure | localStorage / IndexedDB residue (CHAT-06 / T-V8) | mitigate | `grep -c "localStorage\|indexedDB\|sessionStorage" frontend/src/components/chat/useChatStream.ts` = 0. Spy test at `frontend/src/test/useChatStream.test.tsx:193-214` asserts `setItemSpy.not.toHaveBeenCalled()` across submit cycles. | closed |
| T-06-03-02 | Tampering | AbortError vs network-error triage | mitigate | `useChatStream.ts:247-250` discriminates `err.name === 'AbortError'` → `MARK_STOPPED` + early return; other errors flow to `classifyNetworkError` (line 251). | closed |
| T-06-03-03 | DoS | StrictMode double-fire (2× OpenAI cost) | mitigate | `submit` exposed via `useCallback` and bound to the click handler — not invoked from `useEffect`. Internal `isStreamingRef` guard at `useChatStream.ts:159` blocks re-entrant submit. | closed |
| T-06-03-04 | DoS | Cold-start timer leak (rapid submit/stop/submit) | mitigate | `clearColdStartTimer()` invoked at submit start (`useChatStream.ts:173`), inside every event of the stream loop (line 193), and in `finally` (line 255). useEffect cleanup also clears on unmount (lines 142-145). | closed |
| T-06-03-05 | Info Disclosure | Stale network-error Alert across submits | mitigate | `setNetworkError(null)` runs only after `streamAgent` resolves with a `Response` (`useChatStream.ts:189`) — atomic replacement, not pre-clear. | closed |
| T-06-03-06 | DoS | Memory leak from un-aborted fetch on route nav | mitigate | useEffect cleanup at `useChatStream.ts:139-147` calls `abortControllerRef.current?.abort()` on unmount + clears the cold-start timer. | closed |
| T-06-03-07 | Tampering | `crypto.randomUUID` secure-context requirement | accept | Vite dev runs on localhost (secure context); prod is HTTPS via Azure Static Web Apps. LAN testing out of scope for v1. | closed |
| T-06-03-08 | XSS via user-typed query | accept | React escapes `{item.content}` in ChatMessage; `grep -rc "dangerouslySetInnerHTML" frontend/src/components/chat/` = 0. | closed |
| T-06-04-01 | XSS via tool output | mitigate | ToolChip renders `<pre>{argsPretty}</pre>` (line 102) and `<pre>{preview}</pre>` (line 110) and `<pre>{item.output ?? ''}</pre>` (line 139); React escapes the children. No `dangerouslySetInnerHTML` anywhere under `frontend/src/components/chat/`. | closed |
| T-06-04-02 | XSS via user-typed content | mitigate | ChatMessage user-message variant renders `{item.content}` (`ChatMessage.tsx:72`); shadcn Textarea is a native form element. No `dangerouslySetInnerHTML`. | closed |
| T-06-04-03 | Info Disclosure via stack trace | mitigate (inherited Phase 1 D-19) | ErrorEvent.message reaches the SPA already sanitized by `_sanitize`. ChatMessage shows `<AlertDescription>{ERROR_BODY[item.reason] ?? item.message}</AlertDescription>` (`ChatMessage.tsx:113-115`) so the verbatim copy table is preferred and the bounded `item.message` is the fallback. | closed |
| T-06-04-04 | A11y regression (per-token announce) | mitigate | `ChatTranscript.tsx:82-84` declares `<ol role="log" aria-live="polite" aria-relevant="additions">` (NOT "text"); StreamingCursor and ThinkingDots carry `aria-hidden="true"` (`ChatMessage.tsx:33, 45-58`). | closed |
| T-06-04-05 | Density target regression | accept | Density verified by manual UAT (UI-SPEC §15). M6 in `.planning/phases/06-chat/06-UAT.md` marker PASS. | closed |
| T-06-04-06 | Dialog focus-trap escape | accept | shadcn Dialog wraps Radix Dialog which provides focus trap + Escape close + focus return out of the box (no custom wiring required). | closed |
| T-06-04-07 | Composer focus loss on submit | accept | Textarea remains in DOM with `disabled={isStreaming || disabled}` (`ChatComposer.tsx:85`); focus stays on the element, re-enables when streaming ends. | closed |
| T-06-04-08 | Sample-chip rapid double-click race | accept | `onSampleClick` is idempotent (pure prefill + focus); no async work behind it. | closed |
| T-06-04-09 | Network-error Alert flash (Pitfall I) | mitigate (inherited Plan 03) | Atomic state transition: `setNetworkError(null)` runs only after Response (`useChatStream.ts:189`); error renders via `<ChatTranscript>` backstop. | closed |
| T-06-05-01 | Info Disclosure | Cold-start UX masking real outage | accept (code present; live wall-clock verification deferred per UAT.md M2) | `setTimeout(() => setColdStart(true), COLD_START_DELAY_MS)` at `useChatStream.ts:174-177` (10 000 ms); ChatMessage shows "Warming up the agent — this can take ~4 minutes after idle" when `coldStart && isStreamingEmpty` (`ChatMessage.tsx:87-90`). M2 marker DEFERRED in `06-UAT.md:126-132` because a 4+ hour ACA idle window was not achievable during the UAT session; copy is unit-tested. | closed |
| T-06-05-02 | Info Disclosure | CHAT-06 chat-state leak via OTHER subsystem | mitigate (M5 PASSED) | M5 DevTools Application-tab inspection in `06-UAT.md` confirms only `msal.*` + `server-telemetry-{clientId}` keys (MSAL-owned) are present; no chat residue. | closed |
| T-06-05-03 | DoS | Rapid Stop+Submit race | mitigate (M4 PASSED) | `06-UAT.md` M4 marker PASS — AbortError classified correctly, no top-of-route Alert flash; `(stopped)` rendered on the in-flight bubble per `ChatMessage.tsx:96-100`. | closed |
| T-06-05-04 | A11y regression (screen reader) | accept | Code-level aria attributes verified (T-06-04-04); full VoiceOver / NVDA pass out of scope for v1 (single-user). | closed |
| T-06-05-05 | Demoability subjective | accept | Portfolio claim — verified by Adrian as demo author (`06-UAT.md` overall_verdict PASS WITH MINOR DEVIATIONS). | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-06-01 | T-06-01-01 | shadcn install is a code-generation step that copies vetted Radix primitives into the repo; supply-chain risk is bounded by the npm lockfile + Radix dependencies already in tree from Phase 4 dialog work. | Adrian (project owner) | 2026-05-27 |
| AR-06-02 | T-06-01-03 | New chat test files are skip-stubs at the time of scaffold; no runtime path executes them in product builds. | Adrian | 2026-05-27 |
| AR-06-03 | T-06-01-04 | `types.ts` exports pure types and frozen lookup tables; no runtime side-effects. Tampering would require modifying source under code review. | Adrian | 2026-05-27 |
| AR-06-04 | T-06-01-05 | CSS-only animation, scoped to the streaming cursor and three thinking dots. `prefers-reduced-motion` carve-out in app.css respects user preference. | Adrian | 2026-05-27 |
| AR-06-05 | T-06-02-02 | Phase 4 D-26 established Bearer-in-Authorization (not cookies) + CORS allowlist; SameSite/CSRF surfaces are not exposed by this design. Re-validation deferred to a future audit if cookie-auth is ever introduced. | Adrian | 2026-05-27 |
| AR-06-06 | T-06-02-03 | The Chat surface is single-user; unbounded `query` length is bounded operationally by `asyncio.timeout(60s)` and the 10/min IP rate-limiter. A future multi-user phase will revisit Pydantic `max_length`. | Adrian | 2026-05-27 |
| AR-06-07 | T-06-02-05 | POST body size is governed by ACA ingress limits + uvicorn defaults; agent_limit (10/min/IP) is the v1 control. Re-evaluate if multi-user is enabled. | Adrian | 2026-05-27 |
| AR-06-08 | T-06-02-06 | Phase 4 D-08 single-user allowlist is the canonical access-control gate; Phase 6 inherits without modification. | Adrian | 2026-05-27 |
| AR-06-09 | T-06-03-07 | `crypto.randomUUID` requires a secure context; localhost dev + Azure Static Web Apps prod both qualify. LAN testing intentionally out of scope. | Adrian | 2026-05-27 |
| AR-06-10 | T-06-03-08 | React escapes string children by default; the absence of `dangerouslySetInnerHTML` under `components/chat/` is grep-verified (count = 0) and a project linter rule could codify it in a follow-up phase. | Adrian | 2026-05-27 |
| AR-06-11 | T-06-04-05 | Density target is a UI-SPEC §15 cosmetic concern; the M6 marker in 06-UAT.md confirmed in-spec rendering at 1366×768. | Adrian | 2026-05-27 |
| AR-06-12 | T-06-04-06 | shadcn Dialog inherits Radix focus-trap + Escape close + focus return; no project code is required to implement or maintain this control. | Adrian | 2026-05-27 |
| AR-06-13 | T-06-04-07 | Textarea remains mounted (visible + disabled) during streaming; focus stays on the element by browser default. UX verified in M3. | Adrian | 2026-05-27 |
| AR-06-14 | T-06-04-08 | `onSampleClick` is a synchronous prefill + focus call; double-click is idempotent. | Adrian | 2026-05-27 |
| AR-06-15 | T-06-05-01 | The cold-start UX timer is present in code (`useChatStream.ts:174-177`) and the copy is unit-tested. Live wall-clock verification was deferred in UAT.md M2 because the ACA replica was warm during the session; scheduled for the next overnight idle window. Code mitigation is in place; the deferral concerns only the live observation. | Adrian | 2026-05-27 |
| AR-06-16 | T-06-05-04 | Aria attributes are code-verified (T-06-04-04 mitigation); a full VoiceOver / NVDA pass is intentionally out of scope for a single-user portfolio surface. | Adrian | 2026-05-27 |
| AR-06-17 | T-06-05-05 | Demoability is a subjective portfolio criterion; the demo author signs off on the live UAT verdict in `06-UAT.md`. | Adrian | 2026-05-27 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-27 | 34 | 34 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-27
