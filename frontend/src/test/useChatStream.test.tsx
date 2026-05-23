/**
 * Phase 6 Plan 03 — activated tests for useChatStream hook.
 *
 * Coverage: CHAT-01 / CHAT-02 / CHAT-05 (hook half) / CHAT-06 (storage spy)
 *         + Pitfall A (StrictMode no double-fire)
 *         + Pitfall B (AbortError vs networkError)
 *         + Pitfall D (cold-start timer cleanup)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { StrictMode, type ReactNode } from 'react'

import { mockSseResponse, mockSseHangingResponse } from '@/test/sseMockUtils'
import type { AgentEvent } from '@/api/readSSEStream'
import { readSSEStream } from '@/api/readSSEStream'

vi.mock('@/api/agent', () => ({
  streamAgent: vi.fn(),
}))
import { streamAgent } from '@/api/agent'
import { useChatStream } from '@/components/chat/useChatStream'

function strictWrapper({ children }: { children: ReactNode }) {
  return <StrictMode>{children}</StrictMode>
}

/**
 * Async iterable that yields the underlying stream events but also races against
 * the AbortSignal — if signal aborts mid-iteration, throws a DOMException-style
 * AbortError matching native fetch+stream behavior. This is how the hook would
 * observe abort in a real environment (native fetch rejects the reader.read()
 * promise with AbortError when its AbortSignal fires).
 */
async function* abortableGenerator(
  source: AsyncGenerator<AgentEvent, void, undefined>,
  signal: AbortSignal,
): AsyncGenerator<AgentEvent, void, undefined> {
  while (true) {
    if (signal.aborted) {
      const err = new Error('The operation was aborted.')
      err.name = 'AbortError'
      throw err
    }
    const abortPromise: Promise<IteratorResult<AgentEvent, void>> = new Promise(
      (_, reject) => {
        const onAbort = () => {
          const err = new Error('The operation was aborted.')
          err.name = 'AbortError'
          reject(err)
        }
        if (signal.aborted) onAbort()
        else signal.addEventListener('abort', onAbort, { once: true })
      },
    )
    const next = await Promise.race([source.next(), abortPromise])
    if (next.done) {
      return
    }
    yield next.value as AgentEvent
  }
}

function abortableStream(
  source: AsyncGenerator<AgentEvent, void, undefined>,
  signal: AbortSignal,
): AsyncIterable<AgentEvent> {
  return abortableGenerator(source, signal)
}

function setStreamMock(events: AgentEvent[]) {
  vi.mocked(streamAgent).mockImplementation(async (_query, signal) => {
    return abortableStream(readSSEStream(mockSseResponse(events)), signal)
  })
}

function setHangingStreamMock(initialEvents: AgentEvent[]) {
  vi.mocked(streamAgent).mockImplementation(async (_query, signal) => {
    return abortableStream(readSSEStream(mockSseHangingResponse(initialEvents)), signal)
  })
}

beforeEach(() => {
  vi.useRealTimers()
  vi.mocked(streamAgent).mockReset()
  // Provide no-op indexedDB shim so vi.spyOn doesn't crash on environments where
  // jsdom omits the IndexedDB API (Node 22+ default). The spy verifies the hook
  // never calls .open(); if the global doesn't exist, set it to a stub object.
  if (typeof globalThis.indexedDB === 'undefined') {
    Object.defineProperty(globalThis, 'indexedDB', {
      configurable: true,
      writable: true,
      value: { open: () => undefined } as unknown as IDBFactory,
    })
  }
})

describe('useChatStream — CHAT-01 / CHAT-02 happy path', () => {
  it('appends user message then assistant text, streaming token content incrementally', async () => {
    setStreamMock([
      { type: 'token', content: 'Hello' },
      { type: 'token', content: ', world!' },
      { type: 'final', content: 'Hello, world!' },
    ])

    const { result } = renderHook(() => useChatStream())

    await act(async () => {
      await result.current.submit('hi')
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(false))

    expect(result.current.items).toHaveLength(2)
    expect(result.current.items[0]).toMatchObject({ kind: 'user-message', content: 'hi' })
    expect(result.current.items[1]).toMatchObject({
      kind: 'assistant-text',
      content: 'Hello, world!',
      streaming: false,
    })
    expect(result.current.networkError).toBeNull()
  })

  it('interleaves tool-call items between text segments (D-08)', async () => {
    setStreamMock([
      { type: 'token', content: 'Looking up...' },
      { type: 'tool_start', name: 'search_jobs', args: { query: 'rag' } },
      { type: 'tool_end', name: 'search_jobs', output: '[result]' },
      { type: 'token', content: 'Found it.' },
      { type: 'final', content: 'Found it.' },
    ])

    const { result } = renderHook(() => useChatStream())
    await act(async () => {
      await result.current.submit('search please')
    })
    await waitFor(() => expect(result.current.isStreaming).toBe(false))

    // user-message + assistant-text(Looking up...) + tool-call + assistant-text(Found it.)
    expect(result.current.items).toHaveLength(4)
    expect(result.current.items[1]).toMatchObject({
      kind: 'assistant-text',
      content: 'Looking up...',
      streaming: false,
    })
    expect(result.current.items[2]).toMatchObject({
      kind: 'tool-call',
      name: 'search_jobs',
      output: '[result]',
      expanded: false,
    })
    expect(result.current.items[3]).toMatchObject({
      kind: 'assistant-text',
      content: 'Found it.',
      streaming: false,
    })
  })
})

describe('useChatStream — CHAT-05 submit-during-stream blocked', () => {
  it('submit() is a no-op while isStreaming === true', async () => {
    setHangingStreamMock([{ type: 'token', content: 'Hi' }])

    const { result } = renderHook(() => useChatStream())

    // First submit — fire-and-don't-await (stream hangs deliberately)
    let firstSubmit: Promise<void> | undefined
    act(() => {
      firstSubmit = result.current.submit('first')
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    // Second submit while streaming
    await act(async () => {
      await result.current.submit('second')
    })

    // streamAgent called exactly once — second submit was rejected by guard
    expect(vi.mocked(streamAgent)).toHaveBeenCalledTimes(1)
    // items contains only ONE user-message (the first), one assistant-text shell
    const userMessages = result.current.items.filter((i) => i.kind === 'user-message')
    expect(userMessages).toHaveLength(1)
    expect(userMessages[0]).toMatchObject({ content: 'first' })

    // Cleanup: abort the hanging stream so afterEach doesn't leak
    act(() => result.current.stop())
    await firstSubmit
  })
})

describe('useChatStream — CHAT-06 storage spy (zero residue)', () => {
  it('never calls localStorage.setItem across multiple submit cycles', async () => {
    const setItemSpy = vi.spyOn(window.localStorage, 'setItem')
    const idbOpenSpy = vi.spyOn(indexedDB, 'open')

    setStreamMock([
      { type: 'token', content: 'A' },
      { type: 'final', content: 'A' },
    ])
    const { result } = renderHook(() => useChatStream())
    await act(async () => {
      await result.current.submit('first')
    })

    setStreamMock([
      { type: 'token', content: 'B' },
      { type: 'final', content: 'B' },
    ])
    await act(async () => {
      await result.current.submit('second')
    })

    expect(setItemSpy).not.toHaveBeenCalled()
    expect(idbOpenSpy).not.toHaveBeenCalled()
  })
})

describe('useChatStream — Pitfall A: React 19 StrictMode does not double-fire submit', () => {
  it('clicking submit once under StrictMode results in exactly one streamAgent call', async () => {
    setStreamMock([
      { type: 'token', content: 'X' },
      { type: 'final', content: 'X' },
    ])

    const { result } = renderHook(() => useChatStream(), { wrapper: strictWrapper })

    await act(async () => {
      await result.current.submit('test')
    })

    expect(vi.mocked(streamAgent)).toHaveBeenCalledTimes(1)
  })
})

describe('useChatStream — Pitfall B: AbortError handled as control flow, not networkError', () => {
  it('stop() during streaming sets stopped=true on current text + leaves networkError null', async () => {
    setHangingStreamMock([{ type: 'token', content: 'Streaming' }])

    const { result } = renderHook(() => useChatStream())

    let submitPromise: Promise<void> | undefined
    act(() => {
      submitPromise = result.current.submit('long')
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    // Wait briefly for first token to dispatch into the current assistant text
    await waitFor(() => {
      const last = result.current.items.at(-1)
      expect(last?.kind).toBe('assistant-text')
      expect((last as { content: string }).content).toContain('Streaming')
    })

    await act(async () => {
      result.current.stop()
      await submitPromise
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(false))

    expect(result.current.networkError).toBeNull()
    const last = result.current.items.at(-1)
    expect(last).toMatchObject({
      kind: 'assistant-text',
      streaming: false,
      stopped: true,
    })
  })
})

describe('useChatStream — Pitfall D: cold-start timer cleanup across rapid submit/stop/submit', () => {
  it('stopping mid-stream clears the cold-start timer so a stale timer cannot flip coldStart on the next submit', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })

    setHangingStreamMock([])
    const { result } = renderHook(() => useChatStream())

    // First submit — schedule cold-start timer
    let firstPromise: Promise<void> | undefined
    act(() => {
      firstPromise = result.current.submit('first')
    })
    await vi.waitFor(() => expect(result.current.isStreaming).toBe(true))

    // Advance 9s (1s before cold-start fires)
    await act(async () => {
      vi.advanceTimersByTime(9_000)
    })
    expect(result.current.coldStart).toBe(false)

    // Stop before 10s
    await act(async () => {
      result.current.stop()
      await firstPromise
    })

    // Second submit — fresh timer
    setHangingStreamMock([])
    let secondPromise: Promise<void> | undefined
    act(() => {
      secondPromise = result.current.submit('second')
    })
    await vi.waitFor(() => expect(result.current.isStreaming).toBe(true))

    // Advance 2s into second submit — would have fired the first timer (9+2=11s)
    // if the first timer had leaked. Confirm coldStart still false.
    await act(async () => {
      vi.advanceTimersByTime(2_000)
    })
    expect(result.current.coldStart).toBe(false)

    // Cleanup
    await act(async () => {
      result.current.stop()
      await secondPromise
    })

    vi.useRealTimers()
  })
})
