import { QueryClient } from '@tanstack/react-query'

/**
 * Skip retrying 4xx client errors — they won't fix themselves on retry and
 * just multiply the rate-limit pressure (especially against the proxy-IP
 * collapse behind SWA→ACA). Retry transient 5xx / network errors twice.
 */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false
  const message = error instanceof Error ? error.message : String(error)
  const match = /HTTP (\d{3})/.exec(message)
  if (match) {
    const status = Number(match[1])
    if (status >= 400 && status < 500) return false
  }
  return true
}

// Defaults per CONTEXT.md Claude's Discretion (immutable).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: shouldRetry,
      networkMode: 'online',
    },
    mutations: {
      networkMode: 'online',
      retry: 0,
    },
  },
})
