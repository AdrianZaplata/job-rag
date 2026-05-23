import { useState, useRef } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import { authedFetch } from '@/api/authedFetch'
import { readSSEStream } from '@/api/readSSEStream'

/**
 * D-16 — dev-only SSE probe. UI-SPEC §12 contract:
 *  - DEV badge + heading
 *  - Input + Send button (button disabled while streaming)
 *  - scrolling <pre> log; each event is one line; mono 12px
 *  - Lifecycle copy: "… connecting" before first byte; "--- end of stream ---"
 *    on final; "--- error: <reason> ---" on failure
 *
 * Gated in App.tsx by `import.meta.env.DEV || VITE_DEBUG_PAGES === 'true'`; AuthGate
 * wraps it as a defense-in-depth so even with the flag, only the seeded oid can hit
 * it (T-04-05-01 mitigation).
 */
export function DebugAgentStreamPage() {
  const [query, setQuery] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [lines, setLines] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)

  async function send() {
    if (!query.trim()) return
    setLines(['… connecting'])
    setStreaming(true)
    abortRef.current = new AbortController()
    try {
      const res = await authedFetch('/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
        signal: abortRef.current.signal,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setLines([]) // Clear "connecting" once headers resolved.
      for await (const event of readSSEStream(res)) {
        const dataString = JSON.stringify({ ...event, type: undefined })
        setLines((prev) => [...prev, `event: ${event.type}  data: ${dataString}`])
      }
      setLines((prev) => [...prev, '--- end of stream ---'])
    } catch (err) {
      const reason = err instanceof Error ? err.message : String(err)
      setLines((prev) => [...prev, `--- error: ${reason} ---`])
    } finally {
      setStreaming(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Badge variant="outline">DEV</Badge>
        <h1 className="text-lg font-semibold">Agent stream probe</h1>
      </div>
      <div className="flex gap-2">
        <Input
          placeholder="Ask the agent something…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={streaming}
        />
        <Button onClick={send} disabled={streaming}>
          Send query
        </Button>
      </div>
      <pre className="max-h-96 overflow-y-auto bg-muted p-4 font-mono text-xs leading-snug whitespace-pre-wrap break-all">
        {lines.length === 0 ? '(no events yet)' : lines.join('\n')}
      </pre>
    </div>
  )
}
