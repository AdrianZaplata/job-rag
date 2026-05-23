import { useRef, useState } from 'react'

import { ChatComposer, type ChatComposerHandle } from '@/components/chat/ChatComposer'
import { ChatEmptyState } from '@/components/chat/ChatEmptyState'
import { ChatTranscript } from '@/components/chat/ChatTranscript'
import { useChatStream } from '@/components/chat/useChatStream'

/**
 * Phase 6 — /chat route composition. Replaces Phase 4 PhasePlaceholder.
 *
 * useChatStream owns transcript state + AbortController + cold-start timer.
 * Presentation components (ChatTranscript / ChatEmptyState / ChatComposer)
 * receive props; no state lives below this route.
 *
 * Layout (UI-SPEC §3 + §17 #12-13):
 *   route container uses 768px reading width (smaller than Dashboard's 6xl
 *   since chat is a single-column read, not a 3-up grid) + fills remaining
 *   viewport below the h-12 top-nav so composer pins to viewport bottom.
 */
export function ChatPage() {
  const {
    items,
    isStreaming,
    coldStart,
    networkError,
    submit,
    stop,
    toggleToolExpanded,
  } = useChatStream()
  const [composerValue, setComposerValue] = useState('')
  const composerRef = useRef<ChatComposerHandle>(null)

  const handleSampleClick = (query: string) => {
    setComposerValue(query)
    // Focus the textarea so cursor is positioned for the user to edit / hit Enter.
    // UI-SPEC §6e "pre-fill, no auto-submit" — D-25.
    composerRef.current?.focus()
  }

  const handleSubmit = () => {
    const trimmed = composerValue.trim()
    if (trimmed === '') return
    void submit(trimmed)
    setComposerValue('')
  }

  return (
    <div
      className="mx-auto max-w-3xl flex h-[calc(100vh-3rem)] flex-col"
      data-testid="chat-page"
    >
      {items.length === 0 && !isStreaming ? (
        <ChatEmptyState onSampleClick={handleSampleClick} />
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
        onSubmit={handleSubmit}
        onStop={stop}
        isStreaming={isStreaming}
      />
    </div>
  )
}
