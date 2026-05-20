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
})
