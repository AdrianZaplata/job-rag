/**
 * Phase 6 — shared SSE mock helpers for vitest tests of useChatStream / ToolChip /
 * ChatComposer / ChatTranscript. Extracted from frontend/src/test/readSSEStream.test.ts
 * `streamFromString` pattern (Phase 4 D-16) so multiple test files share one impl.
 */

import type { AgentEvent } from '@/api/readSSEStream'

/**
 * Produce a mock Response object whose body is a ReadableStream yielding
 * SSE-formatted bytes for the given events. Each event is serialized with
 * CRLF line endings to match what sse-starlette emits in production:
 *
 *     event: <type>\r\n
 *     data: <JSON>\r\n
 *     \r\n
 *
 * Using `\n\n` here would mask Phase 6 Bug #5 — the SPA's parser previously
 * searched for `\n\n` and never matched the real CRLF frame boundary.
 *
 * Status 200 + Content-Type: text/event-stream so readSSEStream's !res.ok
 * guard doesn't reject.
 */
export function mockSseResponse(events: AgentEvent[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        const frame = `event: ${event.type}\r\ndata: ${JSON.stringify(event)}\r\n\r\n`
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

/**
 * Produce a Response that yields events but never closes — for cancellation
 * tests (Pitfall B AbortError verification). Caller must abort via signal.
 *
 * Uses CRLF line endings to match production (see mockSseResponse above).
 */
export function mockSseHangingResponse(initialEvents: AgentEvent[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of initialEvents) {
        controller.enqueue(
          encoder.encode(
            `event: ${event.type}\r\ndata: ${JSON.stringify(event)}\r\n\r\n`,
          ),
        )
      }
      // Do NOT close — caller must abort via signal
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}
