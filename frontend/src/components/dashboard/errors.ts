// Shared error-description helper for Phase 5 dashboard widget Alert states.
// UI-SPEC section 9 verbatim fallback copy: "Unexpected error. Reload the page or try again later."

export function describeError(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'Unexpected error. Reload the page or try again later.'
}
