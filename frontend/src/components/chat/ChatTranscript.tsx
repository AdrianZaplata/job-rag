/**
 * Phase 6 Plan 04 — ChatTranscript presentation component (UI-SPEC §6a + RESEARCH
 * §"Smart Autoscroll Pattern" verbatim).
 *
 * Scrollable container wrapping an <ol role="log" aria-live="polite" aria-relevant="additions">
 * for screen-reader announcement of new items only (D-32 a11y; aria-relevant=additions
 * prevents per-token re-announcement).
 *
 * Smart autoscroll (D-17) via IntersectionObserver on a bottom sentinel div:
 *  - When sentinel is intersecting (default state, user at bottom), autoscroll engaged
 *  - When user scrolls up past the sentinel, observer flips to !intersecting and
 *    suppresses scrollIntoView so the viewport doesn't yank during token streaming
 *  - When user scrolls back down, sentinel re-intersects and autoscroll re-engages
 *
 * Discriminates over TranscriptItem.kind: tool-call → ToolChip; others → ChatMessage.
 *
 * Network-error Alert backstop (D-24) renders above the <ol> when networkError !== null;
 * the in-transcript per-message error Alert is a different layer (D-22, owned by ChatMessage).
 */

import { useEffect, useRef, useState } from 'react'
import { AlertCircle } from 'lucide-react'

import { Alert, AlertTitle } from '@/components/ui/alert'
import { ChatMessage } from '@/components/chat/ChatMessage'
import { ToolChip } from '@/components/chat/ToolChip'
import type {
  NetworkError,
  TranscriptItem,
} from '@/components/chat/types'

export type ChatTranscriptProps = {
  items: TranscriptItem[]
  isStreaming: boolean
  coldStart: boolean
  networkError: NetworkError | null
  onToggleToolExpanded: (id: string) => void
}

export function ChatTranscript({
  items,
  coldStart,
  networkError,
  onToggleToolExpanded,
}: ChatTranscriptProps) {
  const bottomSentinelRef = useRef<HTMLDivElement>(null)
  const [autoscrollEngaged, setAutoscrollEngaged] = useState(true)

  // IntersectionObserver on bottom sentinel — engages autoscroll when visible
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

  // Scroll into view when items change AND autoscroll engaged
  useEffect(() => {
    if (!autoscrollEngaged) return
    bottomSentinelRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [items, autoscrollEngaged])

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      {networkError && (
        <div className="mx-4 mt-4">
          <Alert variant="destructive" role="alert">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>{networkError.message}</AlertTitle>
          </Alert>
        </div>
      )}
      <ol
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        className="space-y-4"
      >
        {items.map((item) =>
          item.kind === 'tool-call' ? (
            <ToolChip
              key={item.id}
              item={item}
              onToggleExpand={onToggleToolExpanded}
            />
          ) : (
            <ChatMessage key={item.id} item={item} coldStart={coldStart} />
          ),
        )}
        <div
          ref={bottomSentinelRef}
          aria-hidden="true"
          className="h-px w-px"
        />
      </ol>
    </div>
  )
}
