/**
 * Phase 6 D-28 — single owner of chat transcript state, AbortController, and
 * cold-start timer. UI-SPEC §7 state machine + §12 cold-start contract.
 *
 * Presentation components (ChatTranscript / ChatMessage / ToolChip / ChatComposer /
 * ChatEmptyState) consume props from the Chat route which calls this hook once.
 * No state lives below this hook.
 *
 * CHAT-06 enforcement: this module MUST NOT reference any browser persistence API
 * (refresh clears the transcript entirely; single-user, single-session). The
 * acceptance grep verifies zero occurrences; the test file spies on the spec'd APIs.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import { streamAgent } from '@/api/agent'
import type { ErrorEvent as SseErrorEvent } from '@/api/readSSEStream'
import {
  type NetworkError,
  type TranscriptAction,
  type TranscriptItem,
} from '@/components/chat/types'

const COLD_START_DELAY_MS = 10_000

function transcriptReducer(
  state: TranscriptItem[],
  action: TranscriptAction,
): TranscriptItem[] {
  switch (action.type) {
    case 'APPEND_USER_MESSAGE':
      return [
        ...state,
        { kind: 'user-message', id: action.id, content: action.content },
      ]
    case 'APPEND_ASSISTANT_TEXT':
      return [
        ...state,
        { kind: 'assistant-text', id: action.id, content: '', streaming: true },
      ]
    case 'APPEND_TOKEN': {
      // Tokens append in-place on the LAST item if it's a streaming assistant-text.
      // Acceptable at LLM cadence ~30-80 tokens/s; immutable update.
      return state.map((item, i) => {
        if (i !== state.length - 1) return item
        if (item.kind !== 'assistant-text' || !item.streaming) return item
        return { ...item, content: item.content + action.content }
      })
    }
    case 'CLOSE_CURRENT_TEXT': {
      return state.map((item) => {
        if (item.kind === 'assistant-text' && item.streaming) {
          return { ...item, streaming: false }
        }
        return item
      })
    }
    case 'APPEND_TOOL_START':
      return [
        ...state,
        {
          kind: 'tool-call',
          id: action.id,
          name: action.name,
          args: action.args,
          output: null,
          expanded: false,
        },
      ]
    case 'UPDATE_TOOL_OUTPUT': {
      return state.map((item) =>
        item.kind === 'tool-call' && item.id === action.id
          ? { ...item, output: action.output }
          : item,
      )
    }
    case 'TOGGLE_TOOL_EXPANDED': {
      return state.map((item) =>
        item.kind === 'tool-call' && item.id === action.id
          ? { ...item, expanded: !item.expanded }
          : item,
      )
    }
    case 'APPEND_ERROR':
      return [
        ...state,
        { kind: 'error', id: action.id, reason: action.reason, message: action.message },
      ]
    case 'MARK_STOPPED': {
      return state.map((item) => {
        if (item.kind === 'assistant-text' && item.streaming) {
          return { ...item, streaming: false, stopped: true }
        }
        return item
      })
    }
    default:
      return state
  }
}

function classifyNetworkError(err: unknown): NetworkError {
  // D-24 copy-table mapping
  if (err instanceof Error) {
    const msg = err.message
    if (msg.includes('401')) return { kind: '401', message: 'Session expired' }
    if (msg.includes('403')) return { kind: '403', message: 'Not authorized' }
    if (msg.match(/5\d\d/)) return { kind: '5xx', message: 'Server error' }
    if (err.name === 'TypeError') {
      return { kind: 'unreachable', message: "Can't reach the server" }
    }
    return { kind: 'unknown', message: msg.slice(0, 200) }
  }
  return { kind: 'unknown', message: 'Unknown error' }
}

export type UseChatStreamReturn = {
  items: TranscriptItem[]
  isStreaming: boolean
  coldStart: boolean
  networkError: NetworkError | null
  submit: (query: string) => Promise<void>
  stop: () => void
  toggleToolExpanded: (id: string) => void
}

export function useChatStream(): UseChatStreamReturn {
  const [items, dispatch] = useReducer(transcriptReducer, [] as TranscriptItem[])
  const [isStreaming, setIsStreaming] = useState(false)
  const [coldStart, setColdStart] = useState(false)
  const [networkError, setNetworkError] = useState<NetworkError | null>(null)

  const abortControllerRef = useRef<AbortController | null>(null)
  const coldStartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Stable ref to avoid stale-closure on isStreaming inside submit's guard
  const isStreamingRef = useRef(false)

  // Pitfall A — cleanup on unmount aborts in-flight fetch + clears timer
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      if (coldStartTimerRef.current) {
        clearTimeout(coldStartTimerRef.current)
        coldStartTimerRef.current = null
      }
    }
  }, [])

  const clearColdStartTimer = useCallback(() => {
    if (coldStartTimerRef.current) {
      clearTimeout(coldStartTimerRef.current)
      coldStartTimerRef.current = null
    }
  }, [])

  const submit = useCallback(
    async (query: string) => {
      // Pitfall A guard — defense-in-depth against programmatic double-submit
      if (isStreamingRef.current) return
      if (query.trim() === '') return

      isStreamingRef.current = true

      const userId = crypto.randomUUID()
      const assistantId = crypto.randomUUID()

      dispatch({ type: 'APPEND_USER_MESSAGE', id: userId, content: query })
      dispatch({ type: 'APPEND_ASSISTANT_TEXT', id: assistantId })
      setIsStreaming(true)
      setColdStart(false)

      // Pitfall D — clear stale timer before setting a fresh one
      clearColdStartTimer()
      coldStartTimerRef.current = setTimeout(
        () => setColdStart(true),
        COLD_START_DELAY_MS,
      )

      // Per-submit AbortController (one-shot; Pitfall C)
      const controller = new AbortController()
      abortControllerRef.current = controller

      // Per-tool-call id queue for tool_start <-> tool_end matching
      const pendingToolIds: string[] = []

      try {
        const stream = await streamAgent(query, controller.signal)
        // Pitfall I — only clear networkError on successful Response (atomic replace)
        setNetworkError(null)

        for await (const event of stream) {
          // First event clears cold-start state (heartbeat also clears)
          clearColdStartTimer()
          setColdStart(false)

          switch (event.type) {
            case 'token':
              dispatch({ type: 'APPEND_TOKEN', content: event.content })
              break
            case 'tool_start': {
              const toolId = crypto.randomUUID()
              pendingToolIds.push(toolId)
              dispatch({ type: 'CLOSE_CURRENT_TEXT' })
              dispatch({
                type: 'APPEND_TOOL_START',
                id: toolId,
                name: event.name,
                args: (event.args ?? null) as object | null,
              })
              // D-08 — open fresh assistant-text for subsequent tokens
              dispatch({
                type: 'APPEND_ASSISTANT_TEXT',
                id: crypto.randomUUID(),
              })
              break
            }
            case 'tool_end': {
              const toolId = pendingToolIds.shift()
              if (toolId) {
                dispatch({
                  type: 'UPDATE_TOOL_OUTPUT',
                  id: toolId,
                  output: event.output,
                })
              }
              break
            }
            case 'heartbeat':
              // D-20 — silent; timer already cleared above
              break
            case 'error':
              dispatch({ type: 'CLOSE_CURRENT_TEXT' })
              dispatch({
                type: 'APPEND_ERROR',
                id: crypto.randomUUID(),
                reason: (event as SseErrorEvent).reason,
                message: (event as SseErrorEvent).message,
              })
              break
            case 'final':
              dispatch({ type: 'CLOSE_CURRENT_TEXT' })
              break
          }
        }
      } catch (err: unknown) {
        // Pitfall B — AbortError is intentional cancellation, NOT a network error
        if (err instanceof Error && err.name === 'AbortError') {
          dispatch({ type: 'MARK_STOPPED' })
          return
        }
        setNetworkError(classifyNetworkError(err))
      } finally {
        setIsStreaming(false)
        isStreamingRef.current = false
        clearColdStartTimer()
        abortControllerRef.current = null
      }
    },
    [clearColdStartTimer],
  )

  const stop = useCallback(() => {
    abortControllerRef.current?.abort()
    // submit's catch block handles MARK_STOPPED + isStreaming=false via finally
  }, [])

  const toggleToolExpanded = useCallback((id: string) => {
    dispatch({ type: 'TOGGLE_TOOL_EXPANDED', id })
  }, [])

  return {
    items,
    isStreaming,
    coldStart,
    networkError,
    submit,
    stop,
    toggleToolExpanded,
  }
}
