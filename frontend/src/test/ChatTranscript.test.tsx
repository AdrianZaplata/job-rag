/**
 * Phase 6 Plan 04 — activated tests for ChatTranscript presentation component.
 * Coverage: items render in order, network-error Alert conditional render, role=log a11y.
 *           D-17 smart-autoscroll behavioral verification is integration-shaped and
 *           verified manually in Plan 05 UAT (jsdom IntersectionObserver requires polyfill).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

import { ChatTranscript } from '@/components/chat/ChatTranscript'
import type { NetworkError, TranscriptItem } from '@/components/chat/types'

// jsdom doesn't ship IntersectionObserver; provide a deterministic stub so
// ChatTranscript's useEffect doesn't throw. The stub returns intersecting=true,
// matching the default-engaged autoscroll state per UI-SPEC §17 #4.
beforeEach(() => {
  class MockIntersectionObserver {
    private cb: IntersectionObserverCallback
    constructor(cb: IntersectionObserverCallback) {
      this.cb = cb
    }
    observe = vi.fn((target: Element) => {
      this.cb(
        [{ isIntersecting: true, target } as IntersectionObserverEntry],
        this as unknown as IntersectionObserver,
      )
    })
    unobserve = vi.fn()
    disconnect = vi.fn()
    takeRecords = vi.fn(() => [])
    root = null
    rootMargin = ''
    thresholds = []
  }
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  // scrollIntoView isn't implemented by jsdom; stub it
  Element.prototype.scrollIntoView = vi.fn()
})

describe('ChatTranscript — item rendering', () => {
  it('renders items in order via <ol role="log">', () => {
    const items: TranscriptItem[] = [
      { kind: 'user-message', id: 'u1', content: 'Hello' },
      {
        kind: 'assistant-text',
        id: 'a1',
        content: 'Hi there',
        streaming: false,
      },
    ]
    render(
      <ChatTranscript
        items={items}
        isStreaming={false}
        coldStart={false}
        networkError={null}
        onToggleToolExpanded={vi.fn()}
      />,
    )
    const log = screen.getByRole('log')
    expect(log).toBeInTheDocument()
    expect(log).toHaveAttribute('aria-live', 'polite')
    expect(log).toHaveAttribute('aria-relevant', 'additions')
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('Hi there')).toBeInTheDocument()
  })

  it('renders tool-call items via ToolChip discriminant', () => {
    const items: TranscriptItem[] = [
      {
        kind: 'tool-call',
        id: 't1',
        name: 'search_jobs',
        args: { query: 'rag' },
        output: '[result]',
        expanded: false,
      },
    ]
    render(
      <ChatTranscript
        items={items}
        isStreaming={false}
        coldStart={false}
        networkError={null}
        onToggleToolExpanded={vi.fn()}
      />,
    )
    // ToolChip renders the tool name in a font-mono span
    expect(screen.getByText('search_jobs')).toBeInTheDocument()
  })

  it('renders error items via destructive Alert with ERROR_TITLE copy', () => {
    const items: TranscriptItem[] = [
      {
        kind: 'error',
        id: 'e1',
        reason: 'agent_timeout',
        message: 'Agent exceeded 60s timeout',
      },
    ]
    render(
      <ChatTranscript
        items={items}
        isStreaming={false}
        coldStart={false}
        networkError={null}
        onToggleToolExpanded={vi.fn()}
      />,
    )
    // ERROR_TITLE['agent_timeout'] === 'Agent timed out'
    expect(screen.getByText('Agent timed out')).toBeInTheDocument()
  })
})

describe('ChatTranscript — network-error Alert conditional render (D-24)', () => {
  it('renders network-error Alert at top when networkError !== null', () => {
    const items: TranscriptItem[] = []
    const networkError: NetworkError = {
      kind: '5xx',
      message: 'Server error',
    }
    render(
      <ChatTranscript
        items={items}
        isStreaming={false}
        coldStart={false}
        networkError={networkError}
        onToggleToolExpanded={vi.fn()}
      />,
    )
    expect(screen.getByText('Server error')).toBeInTheDocument()
    // Alert has role="alert" via shadcn variant="destructive"
    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0)
  })

  it('does NOT render network-error Alert when networkError === null', () => {
    render(
      <ChatTranscript
        items={[]}
        isStreaming={false}
        coldStart={false}
        networkError={null}
        onToggleToolExpanded={vi.fn()}
      />,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
