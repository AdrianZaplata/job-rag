// /health is the only unauth route per Phase 1 / CONTEXT.md Claude's Discretion.
// Kept as plain fetch (not authedFetch) — /health is the bootstrap probe that runs
// BEFORE auth completes (e.g., readiness checks).

/** GET /health — returns {status: 'ok'} (or 503 on degraded). Unauthenticated. */
export async function getHealth(signal?: AbortSignal): Promise<{ status: string }> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const res = await fetch(`${baseUrl}/health`, { signal })
  if (!res.ok) throw new Error(`health: ${res.status}`)
  return res.json()
}
