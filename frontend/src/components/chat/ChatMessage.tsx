/**
 * Phase 6 Plan 04 — ChatMessage presentation component (UI-SPEC §6b verbatim).
 *
 * Renders 3 variants of TranscriptItem (excluding tool-call which ToolChip owns):
 *  1. user-message  — role label YOU + content as <p text-sm whitespace-pre-wrap>
 *  2. assistant-text — role label AGENT + 4 substates (thinking / warming / streaming / final / stopped)
 *  3. error          — shadcn destructive Alert with per-reason title + body (D-23)
 *
 * Inline subcomponents (UI-SPEC §6f, §6b):
 *  - StreamingCursor — blink ▍ after streaming content (D-21 + app.css util)
 *  - ThinkingDots    — 3 staggered animate-pulse dots (D-18); motion-reduce no-op
 */

import { AlertCircle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  ERROR_BODY,
  ERROR_TITLE,
  type TranscriptItem,
} from '@/components/chat/types'

type ChatMessageItem = Exclude<TranscriptItem, { kind: 'tool-call' }>

export type ChatMessageProps = {
  item: ChatMessageItem
  coldStart: boolean
}

function StreamingCursor() {
  // UI-SPEC §6f — blinking cursor (utility class defined in app.css per Plan 01).
  return (
    <span className="animate-blink" aria-hidden="true">
      ▍
    </span>
  )
}

function ThinkingDots() {
  // Three staggered pulse dots; respects prefers-reduced-motion per UI-SPEC §10.
  return (
    <>
      <span
        className="animate-pulse motion-reduce:animate-none"
        style={{ animationDelay: '0ms' }}
      >
        .
      </span>
      <span
        className="animate-pulse motion-reduce:animate-none"
        style={{ animationDelay: '150ms' }}
      >
        .
      </span>
      <span
        className="animate-pulse motion-reduce:animate-none"
        style={{ animationDelay: '300ms' }}
      >
        .
      </span>
    </>
  )
}

export function ChatMessage({ item, coldStart }: ChatMessageProps) {
  if (item.kind === 'user-message') {
    return (
      <li className="space-y-1">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          YOU
        </span>
        <p className="text-sm whitespace-pre-wrap">{item.content}</p>
      </li>
    )
  }

  if (item.kind === 'assistant-text') {
    const isStreamingEmpty = item.streaming && item.content === ''
    const isStreamingActive = item.streaming && item.content !== ''
    return (
      <li className="space-y-1">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          AGENT
        </span>
        {isStreamingEmpty ? (
          <p className="text-sm text-muted-foreground">
            {coldStart
              ? 'Warming up the agent — this can take ~4 minutes after idle'
              : 'Thinking'}
            <ThinkingDots />
          </p>
        ) : (
          <p className="text-sm whitespace-pre-wrap">
            {item.content}
            {isStreamingActive && <StreamingCursor />}
            {item.stopped && (
              <span className="text-xs text-muted-foreground ml-2">
                (stopped)
              </span>
            )}
          </p>
        )}
      </li>
    )
  }

  // item.kind === 'error'
  return (
    <li>
      <Alert variant="destructive" role="alert">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        <AlertTitle>{ERROR_TITLE[item.reason]}</AlertTitle>
        <AlertDescription>
          {ERROR_BODY[item.reason] ?? item.message}
        </AlertDescription>
      </Alert>
    </li>
  )
}
