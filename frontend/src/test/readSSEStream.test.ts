import { describe, it, expect } from 'vitest'
import { readSSEStream, type AgentEvent } from '@/api/readSSEStream'

function streamFromString(s: string): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(s))
      controller.close()
    },
  })
  return new Response(stream)
}

describe('readSSEStream', () => {
  it('yields typed events from SSE frames', async () => {
    const frames =
      'event: token\ndata: {"type":"token","text":"Hello"}\n\n' +
      'event: token\ndata: {"type":"token","text":" world"}\n\n' +
      'event: final\ndata: {"type":"final","reason":"complete"}\n\n'
    const response = streamFromString(frames)
    const events: AgentEvent[] = []
    for await (const event of readSSEStream(response)) {
      events.push(event)
    }
    expect(events).toHaveLength(3)
    expect(events[0]).toMatchObject({ type: 'token', text: 'Hello' })
    expect(events[1]).toMatchObject({ type: 'token', text: ' world' })
    expect(events[2]).toMatchObject({ type: 'final', reason: 'complete' })
  })

  it('handles heartbeat with empty data', async () => {
    const frames = 'event: heartbeat\n\n'
    const response = streamFromString(frames)
    const events: AgentEvent[] = []
    for await (const event of readSSEStream(response)) {
      events.push(event)
    }
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ type: 'heartbeat' })
  })

  it('buffers partial multi-chunk frames', async () => {
    // Simulate a frame split across two chunks at an awkward byte boundary.
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: token\ndata: {"type":"to'))
        controller.enqueue(encoder.encode('ken","text":"split"}\n\n'))
        controller.close()
      },
    })
    const response = new Response(stream)
    const events: AgentEvent[] = []
    for await (const event of readSSEStream(response)) {
      events.push(event)
    }
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ type: 'token', text: 'split' })
  })

  it('parses CRLF line endings as emitted by sse-starlette (Bug #5)', async () => {
    // Production sse-starlette serializes frames with \r\n line endings per
    // the HTML SSE spec. Parser must accept either form — using only \n\n
    // for the frame boundary would never match the real wire format.
    const frames =
      'event: token\r\ndata: {"type":"token","text":"Hi"}\r\n\r\n' +
      'event: token\r\ndata: {"type":"token","text":" there"}\r\n\r\n' +
      'event: final\r\ndata: {"type":"final","content":"Hi there"}\r\n\r\n'
    const response = streamFromString(frames)
    const events: AgentEvent[] = []
    for await (const event of readSSEStream(response)) {
      events.push(event)
    }
    expect(events).toHaveLength(3)
    expect(events[0]).toMatchObject({ type: 'token', text: 'Hi' })
    expect(events[1]).toMatchObject({ type: 'token', text: ' there' })
    expect(events[2]).toMatchObject({ type: 'final', content: 'Hi there' })
  })

  it('handles a CRLF frame split mid-boundary across chunks', async () => {
    // The \r\n\r\n separator can be split between chunks (e.g., \r\n in one
    // chunk and \r\n in the next). Normalization + buffering must still
    // produce one frame.
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: token\r\ndata: {"type":"token","text":"x"}\r\n'))
        controller.enqueue(encoder.encode('\r\n'))
        controller.close()
      },
    })
    const response = new Response(stream)
    const events: AgentEvent[] = []
    for await (const event of readSSEStream(response)) {
      events.push(event)
    }
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ type: 'token', text: 'x' })
  })

  it('handles a single CRLF split mid-character across chunks', async () => {
    // Harder case than the test above: a single \r\n line terminator is split
    // such that \r ends chunk N and \n starts chunk N+1. Without the
    // pendingCR carry-over, per-chunk regex normalization would convert the
    // lone \r to \n and leave the next chunk's \n intact, producing a false
    // \n\n boundary that severs the event: line from its data: line.
    //
    // To make the regression observable, this frame omits `data.type` so the
    // parser must use the SSE `event:` line as the discriminator
    // (readSSEStream.ts parseSSEFrame fallback path). With the bug, the
    // false boundary drops `event: token` and the orphan data frame has no
    // discriminator → event lost. With the fix, exactly one event surfaces.
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        // Chunk 1 ends with the \r of the first \r\n in the frame.
        controller.enqueue(encoder.encode('event: token\r'))
        controller.enqueue(encoder.encode('\ndata: {"text":"y"}\r\n\r\n'))
        controller.close()
      },
    })
    const response = new Response(stream)
    const events: AgentEvent[] = []
    for await (const event of readSSEStream(response)) {
      events.push(event)
    }
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ type: 'token', text: 'y' })
  })
})
