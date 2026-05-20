import type { FallbackProps } from 'react-error-boundary'

// Wave 3a placeholder — Plan 04-05 replaces with the full ErrorBoundary component
// (Linear-styled card with "Back to dashboard" + "Reload" + collapsed stack).
export default function GlobalErrorFallback({ error }: FallbackProps) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div role="alert" style={{ padding: '2rem', fontFamily: 'system-ui' }}>
      <h1>Something went wrong</h1>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{message}</pre>
    </div>
  )
}
