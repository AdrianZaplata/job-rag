import type { components } from '@/api/types'

// AgentEvent isn't exported as a unified schema by FastAPI's OpenAPI emitter — the
// discriminated union only appears as an inline `oneOf` on /agent and /agent/stream.
// We reconstruct it client-side from the 6 individual event schemas that openapi-typescript
// did extract (matches src/job_rag/api/sse.py 1:1).
//
// If the backend schema flow ever changes (Phase 1 D-04 makes AgentEvent a named ref),
// swap this for `components['schemas']['AgentEvent']`.
export type TokenEvent = components['schemas']['TokenEvent']
export type ToolStartEvent = components['schemas']['ToolStartEvent']
export type ToolEndEvent = components['schemas']['ToolEndEvent']
export type HeartbeatEvent = components['schemas']['HeartbeatEvent']
export type FinalEvent = components['schemas']['FinalEvent']
export type ErrorEvent = components['schemas']['ErrorEvent']

export type AgentEvent =
  | TokenEvent
  | ToolStartEvent
  | ToolEndEvent
  | HeartbeatEvent
  | FinalEvent
  | ErrorEvent

/**
 * Async generator over an SSE response body.
 *
 * D-16: ~60 LOC. Yields typed AgentEvent. Cancellable via init.signal upstream
 * (the caller's fetch passes signal; releasing the reader on AbortError is
 * implicit because the fetch terminates the underlying ReadableStream).
 *
 * Pitfall 5: must buffer partial chunks; do NOT JSON.parse mid-frame.
 */
export async function* readSSEStream(
  response: Response,
): AsyncGenerator<AgentEvent, void, undefined> {
  if (!response.body) {
    throw new Error('readSSEStream: response body is null')
  }
  if (!response.ok) {
    throw new Error(`readSSEStream: ${response.status} ${response.statusText}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  // True when the previous chunk ended with a lone trailing `\r`. The next
  // chunk may begin with `\n`, in which case the pair is a single CRLF line
  // terminator and must collapse to one `\n`. Without this carry-over the
  // per-chunk regex below would turn that lone `\r` into `\n` and then leave
  // the next chunk's `\n` intact, producing a false `\n\n` frame boundary.
  let pendingCR = false

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        // Treat any deferred `\r` as a terminating `\n` on close.
        if (pendingCR) {
          buffer += '\n'
          pendingCR = false
        }
        // Flush any remaining buffered frame.
        if (buffer.trim()) {
          const event = parseSSEFrame(buffer)
          if (event) yield event
        }
        return
      }
      // Normalize CRLF/CR to LF — SSE spec (HTML Living Standard §9.2.6)
      // permits LF, CRLF, or CR line endings. sse-starlette emits CRLF, so
      // searching only for '\n\n' would never find a frame boundary and the
      // SPA would hang at "Warming up…" forever (Phase 6 Bug #5).
      let chunk = decoder.decode(value, { stream: true })
      if (pendingCR) {
        // Prepend the deferred `\r`; the regex will fuse it with a leading
        // `\n` into a single LF if the CRLF was split across chunks.
        chunk = '\r' + chunk
        pendingCR = false
      }
      if (chunk.endsWith('\r')) {
        chunk = chunk.slice(0, -1)
        pendingCR = true
      }
      buffer += chunk.replace(/\r\n?/g, '\n')

      // SSE frame boundary = blank line (\n\n after normalization).
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const rawFrame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const event = parseSSEFrame(rawFrame)
        if (event) yield event
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseSSEFrame(rawFrame: string): AgentEvent | null {
  // SSE frame fields: event:, data:, id:, retry:. We only care about event + data.
  let eventName: string | undefined
  const dataLines: string[] = []
  for (const line of rawFrame.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim())
    }
    // Ignore id:, retry:, comments (lines starting with `:`).
  }
  if (dataLines.length === 0) {
    // heartbeat events sometimes arrive without a data: line; synthesize an empty
    // payload so downstream consumers can still type-narrow on type === 'heartbeat'.
    if (eventName === 'heartbeat') {
      return { type: 'heartbeat' } as HeartbeatEvent
    }
    return null
  }
  try {
    const data = JSON.parse(dataLines.join('\n'))
    // The backend's AgentEvent.type field is the canonical discriminator (Phase 1 D-04).
    // The SSE `event:` line is redundant — we trust `data.type` if present, otherwise
    // fall back to the SSE event: name.
    if (typeof data === 'object' && data !== null && typeof data.type === 'string') {
      return data as AgentEvent
    }
    if (eventName) {
      return { type: eventName, ...data } as AgentEvent
    }
    return null
  } catch {
    // Malformed JSON — log and skip rather than throw mid-stream.
    console.warn('readSSEStream: failed to parse data payload', dataLines)
    return null
  }
}
