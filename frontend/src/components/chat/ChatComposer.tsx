/**
 * Phase 6 Plan 04 — ChatComposer presentation component (UI-SPEC §6d verbatim).
 *
 * Sticky-bottom multi-line Textarea + conditional Send/Stop button.
 *
 * Contract:
 *  - Enter (no shift) submits (D-15)
 *  - Shift+Enter inserts newline (D-15)
 *  - Send button hidden during streaming; Stop button (destructive) appears
 *    in the same slot with Square icon (D-16)
 *  - Disabled while streaming OR when disabled prop true (network-error state)
 *  - composer + stop button get explicit aria-labels (D-32)
 *  - Auto-grow Textarea via useEffect on value (height: auto -> scrollHeight)
 *
 * forwardRef + ChatComposerHandle so the parent route can call .focus() on
 * the textarea after a sample-chip click (UI-SPEC §6e "pre-fill, no auto-submit" D-25).
 * useImperativeHandle exposes only `focus()` — keeps contract minimal.
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { Send, Square } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

export type ChatComposerProps = {
  value: string
  onChange: (next: string) => void
  onSubmit: () => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
}

export type ChatComposerHandle = {
  focus: () => void
}

export const ChatComposer = forwardRef<ChatComposerHandle, ChatComposerProps>(
  function ChatComposer(
    { value, onChange, onSubmit, onStop, isStreaming, disabled = false },
    ref,
  ) {
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    useImperativeHandle(
      ref,
      () => ({
        focus() {
          textareaRef.current?.focus()
        },
      }),
      [],
    )

    // Auto-grow textarea on value change
    useEffect(() => {
      const ta = textareaRef.current
      if (!ta) return
      ta.style.height = 'auto'
      ta.style.height = `${ta.scrollHeight}px`
    }, [value])

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        if (!isStreaming && !disabled && value.trim() !== '') {
          onSubmit()
        }
      }
    }

    return (
      <div className="sticky bottom-0 border-t bg-background px-4 py-3">
        <div className="flex items-end gap-2">
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask the agent something…"
            aria-label="Ask the agent"
            rows={1}
            className="min-h-[44px] max-h-[200px] resize-none flex-1"
            disabled={isStreaming || disabled}
          />
          {isStreaming ? (
            <Button
              type="button"
              size="sm"
              variant="destructive"
              onClick={onStop}
              aria-label="Stop streaming response"
            >
              <Square className="h-4 w-4 mr-1" aria-hidden="true" />
              Stop
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={onSubmit}
              disabled={disabled || value.trim() === ''}
              aria-label="Send message"
            >
              <Send className="h-4 w-4 mr-1" aria-hidden="true" />
              Send
            </Button>
          )}
        </div>
      </div>
    )
  },
)
