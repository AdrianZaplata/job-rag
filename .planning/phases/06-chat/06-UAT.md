---
phase: 6
slug: chat
status: testing
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md, 06-03-SUMMARY.md, 06-04-SUMMARY.md]
started: 2026-05-24T00:00:00Z
updated: 2026-05-24T00:00:00Z
uat_environment: production SWA + deployed ACA
swa_origin: https://witty-flower-065dac003.7.azurestaticapps.net
backend_aca_fqdn: https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io
signed_in_oid: 18d774c1-62ac-4416-8945-b5eca715e9ed
build_sha_at_scaffold: 2e82389
overall_verdict: [pending]
---

# Phase 6 — Live UAT Evidence

> Per VALIDATION.md "Manual-Only Verifications" + ROADMAP §Phase 6 success
> criteria. 6 M-markers; each must PASS or be documented as FAIL-with-note.
> Closes 6 CHAT-* requirements + 5 ROADMAP success criteria + the ≤30s
> demoable screen recording portfolio artifact.
>
> SCAFFOLD: All 6 markers are `[pending]`. Adrian executes them live against
> the deployed stack, then Task 2 of Plan 06-05 transcribes observations into
> the fields below + flips status → `complete`.

## Current Test

number: 1
name: M1 — Happy path (one full chat turn)
expected: |
  Sample-chip click pre-fills composer → submit → "Thinking…" → tokens stream
  incrementally (DevTools EventStream tab shows discrete token/tool_start/
  tool_end/final frames) → tool chip appears mid-stream → final closes
  bubble → composer re-enables.
awaiting: Adrian executes M1 against production SWA URL

## Environment

- **SWA origin:** https://witty-flower-065dac003.7.azurestaticapps.net (chat at `/chat`)
- **Backend ACA FQDN:** https://jobrag-prod-api.gentlebay-598f6d02.westeurope.azurecontainerapps.io
- **Adrian's signed-in oid:** `18d774c1-62ac-4416-8945-b5eca715e9ed` (seeded local customer `adrian@jobrag.onmicrosoft.com`)
- **Browser:** [pending — record at session start, e.g. Chromium incognito per gstack `/browse` convention]
- **Date / time (ISO):** [pending — fill at session start]
- **Build SHA at UAT execution:** [pending — `git rev-parse HEAD` at run time; scaffold captured at `2e82389`]
- **ACA cold-start state at UAT start:** [pending — warm / cold (4+ hour idle); decides whether M2 can run today]

---

## Setup (do once before starting M-markers)

1. **Confirm production deployment up-to-date:**
   ```bash
   gh run list --workflow deploy-api.yml --limit 1
   gh run list --workflow deploy-spa.yml --limit 1
   ```
   Both runs should be successful + reference Phase 6 commits (Plans 01-04 — through `7d56992`). If older, push/redeploy first.

2. **Confirm ACA cold-start state for M2** (decide DURING the UAT session):
   - M2 (cold-start UX) requires a 4+ hour ACA idle window. Schedule intentionally.
   - Quick check: `az containerapp revision show ...` for `provisioningState: Provisioned, activeRevisionsMode: Single, properties.replicas: 0` → scaled-to-zero. If currently running and Adrian doesn't have a 4-hour idle window in this session, mark M2 as DEFERRED and schedule a later session.

3. **Prep a quiet desktop** for M6 screen recording — close noisy tabs, hide menu bars, full-screen the browser.

---

## M1 — Happy path (one full chat turn)

**Requirement coverage:** CHAT-01, CHAT-02, CHAT-05; ROADMAP §Phase 6 success criterion 1.

### Steps

1. Sign in at production SWA URL (`https://witty-flower-065dac003.7.azurestaticapps.net`) using Adrian's customer Entra account (`adrian@jobrag.onmicrosoft.com`).
2. Navigate to `/chat`. Verify `<ChatEmptyState>` renders (4 sample chips visible; MessageSquare icon; heading "Ask the agent about the job-market corpus").
3. Click sample chip "What's the top must-have skill in Berlin?" → verify the composer Textarea populates with the chip text + cursor focused at end of textarea.
4. (Optional) Edit the query.
5. Open DevTools → Network tab → filter "EventStream" (or `text/event-stream` MIME).
6. Hit Enter → verify:
   - POST `/agent/stream` request fires (status 200; `Authorization: Bearer ...` header attached)
   - Network tab "EventStream" sub-tab shows discrete `event: token` / `event: tool_start` / `event: tool_end` / `event: final` frames arriving — NOT a single buffered response (this is the Pitfall E preservation check)
   - In the UI: user-message renders → assistant-text bubble appears with "Thinking..." → first token swaps it to streaming content with blinking `▍` cursor → if agent calls `search_jobs`, tool chip appears collapsed (running state pulse `·`) → tool returns → chip fills with output preview → assistant-text continues streaming → final closes the bubble (cursor disappears) → composer re-enables
   - Composer Send button reappears after final
7. **Capture:** Network tab EventStream sub-tab screenshot + UI screenshot of the completed turn.

### PASS criteria

Tokens streamed incrementally (NOT buffered) AND at least one tool chip appeared AND final marked the bubble complete AND composer re-enabled.

### Result

| Property | Value |
|----------|-------|
| CHAT-* coverage | CHAT-01, CHAT-02, CHAT-05 |
| ROADMAP criterion | #1 (tokens stream incrementally) |
| **Result** | **[pending]** |
| First token latency | [pending — e.g. ~1.2s on warm container] |
| Tokens streamed incrementally (EventStream tab discrete frames) | [pending — YES / NO] |
| Tool chip appeared mid-stream | [pending — YES / NO; tool name if YES] |
| Final closed bubble + composer re-enabled | [pending — YES / NO] |
| Evidence | [pending — screenshots/m1-network.png, screenshots/m1-ui.png] |
| Notes | [pending] |

---

## M2 — Cold-start UX (the portfolio differentiator)

**Requirement coverage:** D-19 + UI-SPEC §12 + memory/aca-cold-start-profile.

**Prerequisite:** ACA replica is genuinely scaled-to-zero (4+ hour idle, or just-restarted). If you cannot achieve this in the current session, mark as DEFERRED and re-run after the window.

### Steps

1. Sign in at the production SWA URL (cold-start window: this initial page load might already trigger a cold-start; if you see "Warming up" on the page-load fetch, that's NOT this test — wait until it completes).
2. Navigate to `/chat`. Verify EmptyState renders.
3. Open DevTools → Console (clear any logs).
4. **Time T=0s:** Click a sample chip or type a query; hit Enter.
5. **Observe T=0s:** Assistant text bubble appears with **"Thinking"** + three pulsing dots.
6. **Observe T=10s:** Label swaps to **"Warming up the agent — this can take ~4 minutes after idle"** (verbatim per D-19; em-dash U+2014).
7. **Observe T=10s–225s:** Label stays steady on "Warming up..."; no further changes.
8. **Observe T≈225s (or whenever fetch resolves):** First event arrives; label disappears; tokens start streaming OR tool chip appears + content streams normally.
9. **Capture:** Screenshots at T=2s ("Thinking..."), T=12s ("Warming up..."), T=stream-start (cursor appears with content).

### PASS criteria

"Thinking..." renders at T<10s AND "Warming up the agent — this can take ~4 minutes after idle" renders at T≥10s AND eventually streams successfully (does NOT timeout at 60s on the asyncio side — cold-start latency is on the fetch establishment, not the agent generation).

### Result

| Property | Value |
|----------|-------|
| D-19 coverage | UI-SPEC §12 cold-start swap at T=10s |
| **Result** | **[pending]** (PASS / FAIL / DEFERRED — no cold-start window achievable) |
| Cold-start latency observed (submit → first event) | [pending — e.g. ~215s] |
| "Thinking..." rendered at T<10s | [pending — YES / NO] |
| "Warming up the agent — this can take ~4 minutes after idle" rendered at T≥10s | [pending — YES / NO] |
| Em-dash U+2014 verbatim verified | [pending — YES / NO] |
| Eventually streams successfully (no false 60s timeout) | [pending — YES / NO] |
| Evidence | [pending — screenshots/m2-t0.png, screenshots/m2-t12.png, screenshots/m2-stream-start.png] |
| Notes | [pending] |

---

## M3 — Tool chip live: expand + "Show full output" Dialog

**Requirement coverage:** CHAT-03, CHAT-04, FEATURES.md "Inspectable agent tool calls" portfolio differentiator.

**Prerequisite:** A real `search_jobs` tool call from M1 (or trigger a fresh one with a query like "Find postings for Senior Python engineers in Berlin").

### Steps

1. After a turn that triggered `search_jobs` (or any tool), locate the collapsed chip in the transcript.
2. Verify collapsed appearance: `→ search_jobs {"query":"...","seniority":"senior"}` with a `▶` chevron on the right.
3. Click anywhere on the chip header (NOT just the chevron — full-row click target per D-10).
4. Verify chip expands: chevron rotates 90° to `▼`; body shows `args` block (pretty-printed JSON) + `output` block (preview text, first 200 chars).
5. Determine if "Show full output" Button is visible (only renders if `output.length > 200`).
6. If visible: click "Show full output" → Dialog opens with title "Tool output", description "Full output of `search_jobs`", and the FULL output text in a scrollable `<pre>` block.
7. Verify Dialog focus trap (Tab cycles inside dialog; first tab lands on first focusable element); press Escape → Dialog closes; focus returns to "Show full output" trigger.
8. Click chip header again → chip collapses (chevron back to `▶`).
9. **Capture:** Screenshots of (a) collapsed chip with args preview, (b) expanded chip with truncated output + Show full button, (c) Dialog open with full output, (d) Dialog closed → chip stays expanded.

### PASS criteria

Chip toggles open/closed on header click AND args render as pretty-printed JSON AND output preview truncates ≥200 chars with `…` AND Dialog opens with full output AND Escape closes Dialog.

### Result

| Property | Value |
|----------|-------|
| CHAT-* coverage | CHAT-03, CHAT-04 |
| ROADMAP criterion | #2 (tool_start chip → tool_end with 200-char preview + Show full) |
| **Result** | **[pending]** |
| Tool called | [pending — e.g. search_jobs] |
| Output length (chars) | [pending] |
| Output > 200 chars (Show full visible) | [pending — YES / NO] |
| Chip header click toggles expand/collapse | [pending — YES / NO] |
| Dialog opens with full output | [pending — YES / NO] |
| Dialog Escape closes + focus returns to "Show full output" trigger | [pending — YES / NO] |
| args rendered as pretty-printed JSON | [pending — YES / NO] |
| Evidence | [pending — screenshots/m3-collapsed.png, screenshots/m3-expanded.png, screenshots/m3-dialog.png] |
| Notes | [pending] |

---

## M4 — Stop mid-stream cancels cleanly

**Requirement coverage:** D-16 + Pitfall B (live verification of unit test).

### Steps

1. Submit a query likely to trigger a longer tool call + synthesis (e.g., "Summarize the top 20 skills across all Berlin senior postings").
2. As soon as Stop button appears (replaces Send), click Stop **before** the first tool chip or before all tokens stream in.
3. Verify:
   - Streaming halts immediately (no further tokens append to the current assistant-text bubble)
   - Current assistant-text bubble gets `(stopped)` suffix in muted-foreground after its accumulated content
   - Stop button disappears; Send button reappears (composer re-enables)
   - NO top-of-route "Server error" Alert appears (Pitfall B verification — AbortError is NOT a network error)
   - networkError stays null (verify via DevTools React DevTools → useChatStream hook state, or simply by absence of the top-of-route Alert)
4. Re-submit a fresh query → verify new stream works normally (proves AbortController is fresh per submit; no orphaned signal).
5. **Capture:** Screenshot of `(stopped)` suffix on truncated assistant text + Send button visible + transcript scrolling normally.

### PASS criteria

Stop click halted streaming AND `(stopped)` suffix rendered AND composer re-enabled AND no false network-error Alert AND next submit worked.

### Result

| Property | Value |
|----------|-------|
| D-16 + Pitfall B coverage | yes |
| ROADMAP criterion | #3 (final marks bubble complete; submit-during-stream blocked — Stop is the inverse path) |
| **Result** | **[pending]** |
| Streaming halted on Stop click | [pending — YES / NO] |
| "(stopped)" suffix rendered on truncated assistant text | [pending — YES / NO] |
| Top-of-route network-error Alert appeared | [pending — NO (correct) / YES (FAIL — Pitfall B regression)] |
| networkError stayed null | [pending — YES / NO] |
| Composer Send button reappeared | [pending — YES / NO] |
| Next submit worked normally | [pending — YES / NO] |
| Evidence | [pending — screenshots/m4-stopped.png] |
| Notes | [pending] |

---

## M5 — Refresh = zero residue (CHAT-06)

**Requirement coverage:** CHAT-06; ROADMAP §Phase 6 success criterion 4.

### Steps

1. After at least one completed turn from M1 (transcript has user-message + assistant-text + tool-call items), open DevTools → Application tab.
2. Inspect each storage section:
   - **Local Storage** for the SWA origin: expand → list all keys
   - **Session Storage** for the SWA origin: expand → list all keys
   - **IndexedDB** for the SWA origin: expand → list all databases
3. Verify: no keys/databases match patterns like `chat-*`, `transcript-*`, `agent-*`, `message-*`. The only allowed keys are:
   - `theme` (Phase 4 D-20 — light/dark mode preference)
   - MSAL-related keys (e.g., `msal.account.keys`, `msal.token.keys.*`, `msal.cache`, etc. — Phase 4 D-06 sessionStorage cache)
   - Sonner / shadcn-related keys (if any — typically none)
4. **Capture:** Application-tab screenshot showing the exhaustive key list (annotated to call out absence of chat-related keys).
5. Refresh the browser (F5 / Cmd+R) → verify EmptyState renders again (transcript wiped). Click a sample chip → composer populates (proves React-only state).

### PASS criteria

Zero `chat-*` / `transcript-*` / `agent-*` / `message-*` keys in localStorage / sessionStorage / IndexedDB AND refresh wipes transcript entirely AND post-refresh state is clean EmptyState.

### Result

| Property | Value |
|----------|-------|
| CHAT-* coverage | CHAT-06 |
| ROADMAP criterion | #4 (refresh clears transcript; zero localStorage/IndexedDB residue) |
| **Result** | **[pending]** |
| Chat-related keys in localStorage | [pending — 0 (correct) / N (FAIL with key list)] |
| Chat-related keys in sessionStorage | [pending — 0 / N] |
| Chat-related IndexedDB databases | [pending — 0 / N] |
| Allowed keys present (theme, msal.*) | [pending — list, e.g. theme, msal.account.keys, msal.cache.b2c_account.*] |
| Refresh wipes transcript entirely | [pending — YES / NO] |
| Post-refresh state = EmptyState | [pending — YES / NO] |
| Evidence | [pending — screenshots/m5-application-tab.png] |
| Notes | [pending] |

---

## M6 — ≤30s demoable screen recording

**Requirement coverage:** ROADMAP §Phase 6 success criterion 5.

### Steps

1. Use macOS Screenshot (Cmd+Shift+5 → Record Selected Portion) or QuickTime → New Screen Recording. Resolution: at least 1080p.
2. Start recording.
3. Navigate to `/chat` → EmptyState renders.
4. Click sample chip "What's the top must-have skill in Berlin?" (or another that produces a tool call).
5. Hit Enter.
6. Wait for: assistant Thinking → tool_start chip → tool_end with output preview → streaming synthesis → final.
7. Click the tool chip → it expands to show args + output.
8. (Optional) Click "Show full output" → Dialog opens → close.
9. Stop recording. Trim to ≤30 seconds total.
10. **Capture:** Save as `06-chat-demo.mp4` (or .mov / .gif as appropriate) in `.planning/phases/06-chat/`. Add screenshot stills to UAT.md if recording is too large for git.

### PASS criteria

Recording is ≤30 seconds AND captures one full chat turn AND tool chip expansion is visible AND demoable as-is (no edits needed; the streaming UX speaks for itself).

### Result

| Property | Value |
|----------|-------|
| ROADMAP criterion | #5 (≤30s demoable recording) |
| **Result** | **[pending]** |
| Recording duration | [pending — e.g. 24s] (must be ≤30s) |
| Recording captures one full chat turn (question → tool chip → stream → final) | [pending — YES / NO] |
| Tool chip expansion visible in recording | [pending — YES / NO] |
| File location | [pending — .planning/phases/06-chat/06-chat-demo.mp4 (or screenshots/m6-frames/)] |
| Demoable as-is (no edits needed) | [pending — YES / NO] |
| Notes | [pending] |

---

## Phase 6 ROADMAP success criteria closure

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Tokens stream incrementally (DevTools EventStream tab discrete frames, not buffered) | [pending] | M1 |
| 2 | tool_start chip collapsed → tool_end chip expanded with 200-char preview + "Show full" affordance | [pending] | M3 |
| 3 | `final` marks bubble complete + re-enables composer; submit-during-stream blocked | [pending] | M1 (final + composer re-enable) + M4 (Stop inverse) |
| 4 | Refresh clears transcript entirely; zero localStorage/IndexedDB residue | [pending] | M5 |
| 5 | ≤30s demoable screen recording of one chat turn | [pending] | M6 |

---

## CHAT-* requirement closure

| ID | Description | Status | Marker |
|----|-------------|--------|--------|
| CHAT-01 | Chat React page consumes `/agent/stream` via `fetch` + `ReadableStream` | [pending] | M1 |
| CHAT-02 | `token` events render incrementally into assistant bubble | [pending] | M1 |
| CHAT-03 | `tool_start` events render as collapsed chip with name + JSON args preview | [pending] | M3 |
| CHAT-04 | `tool_end` expands chip with output preview (≥200 chars truncated with "expand" affordance) | [pending] | M3 |
| CHAT-05 | `final` marks bubble complete + re-enables composer; attempting submit-during-stream blocked | [pending] | M1 + M4 |
| CHAT-06 | Single-turn only; refreshing clears conversation; no history persistence | [pending] | M5 |

---

## Issues encountered / hotfixes applied during UAT

[pending — Free-form list. If any markers FAILED and a hotfix landed during the UAT session, list:
- Commit SHA of the hotfix
- Brief description
- Marker that was re-tested + final result

OR write "None — all 6 markers PASS on first attempt."]

---

## Overall Phase 6 verdict

**[pending]** — will be one of: PASS / PASS WITH MINOR DEVIATIONS / FAIL

---

## Deviations from spec (if any)

[pending — List any observed UI deviations vs UI-SPEC §6 / class strings / copy / a11y attributes.
Cross-reference the affected D-XX decision so future readers can trace the divergence.
Common harmless deviations: 1-2 px spacing tweaks observed live but not noticed in unit tests, etc.

OR write "None — UI matches UI-SPEC §6 verbatim."]

---

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

---

## Gaps

<!-- APPEND when M-markers FAIL. YAML format for /gsd-plan-phase --gaps consumption.
Empty until first FAIL observation. -->

---

## Next

Run `/gsd-verify-work 6` to formalize Phase 6 closure. Then either:
- Proceed to Phase 7 (Profile & Resume Upload) — parallel-eligible per ROADMAP §"Phase Ordering Notes"
- OR Phase 8 (Eval & Documentation) — terminal phase

---

*Phase: 06-chat*
*UAT scaffold created: 2026-05-24*
*Status: testing (awaiting Adrian's M1-M6 execution against deployed SWA + ACA)*
