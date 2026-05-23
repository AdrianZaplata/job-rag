/**
 * Phase 6 D-07 — TranscriptItem discriminated union (UI in-memory shape).
 * D-23 — per-reason ERROR_TITLE / ERROR_BODY lookup tables.
 * D-24 — NetworkError shape for top-of-route Alert backstop.
 *
 * Distinct from `AgentEvent` (wire format, owned by api/readSSEStream.ts).
 * `useChatStream` reducer dispatches `TranscriptAction` to mutate `TranscriptItem[]`.
 */

import type { ErrorEvent as SseErrorEvent } from '@/api/readSSEStream'

// ───────────────────────── TranscriptItem ─────────────────────────

export type TranscriptItem =
  | { kind: 'user-message'; id: string; content: string }
  | {
      kind: 'assistant-text'
      id: string
      content: string
      streaming: boolean
      stopped?: boolean
    }
  | {
      kind: 'tool-call'
      id: string
      name: string
      args: object | null
      output: string | null
      expanded: boolean
    }
  | {
      kind: 'error'
      id: string
      reason: SseErrorEvent['reason']
      message: string
    }

// ───────────────────────── NetworkError ───────────────────────────

export type NetworkError = {
  kind: '401' | '403' | '5xx' | 'unreachable' | 'unknown'
  message: string
}

// ───────────────────────── TranscriptAction (reducer) ─────────────

export type TranscriptAction =
  | { type: 'APPEND_USER_MESSAGE'; id: string; content: string }
  | { type: 'APPEND_ASSISTANT_TEXT'; id: string }
  | { type: 'APPEND_TOKEN'; content: string }
  | { type: 'CLOSE_CURRENT_TEXT' }
  | { type: 'APPEND_TOOL_START'; id: string; name: string; args: object | null }
  | { type: 'UPDATE_TOOL_OUTPUT'; id: string; output: string }
  | { type: 'TOGGLE_TOOL_EXPANDED'; id: string }
  | {
      type: 'APPEND_ERROR'
      id: string
      reason: SseErrorEvent['reason']
      message: string
    }
  | { type: 'MARK_STOPPED' }

// ───────────────────────── ERROR copy tables (D-23 verbatim) ──────

export const ERROR_TITLE: Record<SseErrorEvent['reason'], string> = {
  agent_timeout: 'Agent timed out',
  shutdown: 'Server restarting',
  llm_error: 'Language model error',
  internal: 'Something went wrong',
}

export const ERROR_BODY: Record<SseErrorEvent['reason'], string | undefined> = {
  agent_timeout:
    'The agent took longer than 60 seconds to respond. Try a more specific question, or check the agent logs.',
  shutdown: 'Container is shutting down. Please try again in a moment.',
  llm_error: 'The LLM call failed. Please try again.',
  internal: undefined, // falls through to item.message (sanitized backend message)
}

// ───────────────────────── Re-exports (convenience) ───────────────

export type { AgentEvent, ErrorEvent } from '@/api/readSSEStream'
