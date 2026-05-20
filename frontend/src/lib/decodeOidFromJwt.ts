/**
 * Decode a JWT id-token to extract the `oid` claim (single-user bootstrap UX per D-09).
 *
 * NOT a validator — only used to display the oid value to the user so they can copy
 * it into the AccessDenied runbook. Trust boundary: presented oid is user-readable
 * only; never passed back to the backend as an auth decision (T-04-04-08).
 */
export function decodeOidFromJwt(idToken: string): string | null {
  try {
    const parts = idToken.split('.')
    if (parts.length !== 3) return null
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.oid === 'string' ? payload.oid : null
  } catch {
    return null
  }
}
