/**
 * Phase 6 D-27 — typed POST wrapper around /agent/stream.
 *
 * Returns the AgentEvent async iterator yielded by readSSEStream. Caller
 * threads AbortSignal (typically from useChatStream's abortControllerRef.signal).
 *
 * Throws on:
 *   - Non-OK response (readSSEStream's internal !res.ok guard)
 *   - Fetch failure (network error, MSAL InteractionRequired)
 *   - AbortError (propagates to caller; useChatStream catches as expected control flow)
 */

import { authedFetch } from '@/api/authedFetch'
import { readSSEStream, type AgentEvent } from '@/api/readSSEStream'

export async function streamAgent(
  query: string,
  signal: AbortSignal,
): Promise<AsyncIterable<AgentEvent>> {
  const response = await authedFetch('/agent/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal,
  })
  return readSSEStream(response)
}
