import { useEffect } from 'react'
import { useIsAuthenticated, useMsal } from '@azure/msal-react'
import { Outlet } from 'react-router'

import { msalInstance } from '@/auth/msal'
import { loginRequest } from '@/auth/scopes'
import { RouteSkeleton } from '@/components/RouteSkeleton'

/**
 * D-18 protected-route boundary. Outside-AuthGate routes per UI-SPEC §6:
 * /access-denied + /404 (avoid redirect loops).
 *
 * UI-SPEC §16 loading-state policy:
 *  - inProgress !== 'none' → RouteSkeleton (NEVER render a login form as first UI;
 *    the loginRedirect is the only path to auth UI).
 *  - !isAuthenticated → fire loginRedirect in useEffect, render nothing while
 *    the redirect navigation is in flight.
 *  - authenticated → render the child route via <Outlet/>.
 *
 * AUTH-07 race-fix race: main.tsx already awaits initialize() + handleRedirectPromise()
 * BEFORE createRoot, so by the time AuthGate mounts, MSAL state is settled. The
 * inProgress check is defensive (StrictMode double-render + cross-tab interactions).
 */
export function AuthGate() {
  const isAuthenticated = useIsAuthenticated()
  const { inProgress } = useMsal()

  useEffect(() => {
    if (!isAuthenticated && inProgress === 'none') {
      msalInstance.loginRedirect(loginRequest).catch((err) => {
        // eslint-disable-next-line no-console
        console.error('loginRedirect failed', err)
      })
    }
  }, [isAuthenticated, inProgress])

  if (inProgress !== 'none') {
    return <RouteSkeleton />
  }
  if (!isAuthenticated) {
    // Render nothing while the redirect navigation is in flight.
    return null
  }
  return <Outlet />
}
