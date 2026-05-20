import {
  InteractionRequiredAuthError,
  BrowserAuthError,
  type AuthenticationResult,
} from '@azure/msal-browser'
import { msalInstance } from '@/auth/msal'
import { loginRequest, API_SCOPE } from '@/auth/scopes'

const INTERACTION_REQUIRED_CODES = new Set([
  'monitor_window_timeout',
  'no_account_error',
  'silent_sso_error',
])

async function acquireToken(): Promise<string> {
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0]
  if (!account) {
    // No account at all — must login. Throws by way of navigation.
    await msalInstance.acquireTokenRedirect({ scopes: [API_SCOPE] })
    throw new Error('Token acquisition required login redirect')
  }
  msalInstance.setActiveAccount(account)

  try {
    const result: AuthenticationResult = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account,
    })
    return result.accessToken
  } catch (err) {
    if (
      err instanceof InteractionRequiredAuthError ||
      (err instanceof BrowserAuthError && INTERACTION_REQUIRED_CODES.has(err.errorCode))
    ) {
      // Hand off to MSAL — navigates away; this promise never resolves.
      await msalInstance.acquireTokenRedirect({ scopes: [API_SCOPE] })
      throw err
    }
    throw err
  }
}

/**
 * Native fetch wrapper that attaches the MSAL access token as Bearer.
 *
 * D-11 / D-13: ~30-50 LOC native fetch. acquireTokenSilent before every call.
 * On InteractionRequiredAuthError (or matching BrowserAuthError per Pitfall 12)
 * → acquireTokenRedirect (full-page navigation).
 * On 401 from backend → retry once after silent refresh; second 401 ⇒ redirect.
 *
 * Honours init.signal so TanStack Query cancellation propagates into fetch.
 */
export async function authedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  let token = await acquireToken()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${token}`)

  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const url =
    typeof input === 'string' && !input.startsWith('http')
      ? `${baseUrl}${input}`
      : input

  let response = await fetch(url, { ...init, headers, signal: init.signal })

  // 401 retry-after-refresh per D-11. Second 401 ⇒ acquireTokenRedirect.
  if (response.status === 401) {
    token = await acquireToken()
    headers.set('Authorization', `Bearer ${token}`)
    response = await fetch(url, { ...init, headers, signal: init.signal })
    if (response.status === 401) {
      await msalInstance.acquireTokenRedirect({ scopes: [API_SCOPE] })
      throw new Error('Authentication required')
    }
  }

  return response
}
