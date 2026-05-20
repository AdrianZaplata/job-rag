import { Routes, Route, Navigate } from 'react-router'
import { Suspense, lazy } from 'react'
import type { ReactNode } from 'react'

import { AuthGate } from '@/components/AuthGate'
import { AppShell } from '@/components/AppShell'
import { RouteSkeleton } from '@/components/RouteSkeleton'
import { AccessDeniedPage } from '@/routes/AccessDenied'
import { NotFoundPage } from '@/routes/NotFound'

// Code-split phase placeholders so the initial bundle stays small (D-19b).
const DashboardPage = lazy(() =>
  import('@/routes/Dashboard').then((m) => ({ default: m.DashboardPage })),
)
const ChatPage = lazy(() => import('@/routes/Chat').then((m) => ({ default: m.ChatPage })))
const ProfilePage = lazy(() =>
  import('@/routes/Profile').then((m) => ({ default: m.ProfilePage })),
)

// Dev-only debug page — gated; falls through to NotFound if not enabled.
const debugEnabled = import.meta.env.DEV || import.meta.env.VITE_DEBUG_PAGES === 'true'
const DebugAgentStreamPage = debugEnabled
  ? lazy(() =>
      import('@/routes/DebugAgentStream').then((m) => ({ default: m.DebugAgentStreamPage })),
    )
  : null

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteSkeleton />}>{children}</Suspense>
}

/**
 * Route table per UI-SPEC §6.
 *
 * - / → /dashboard (redirect)
 * - /dashboard, /chat, /profile inside AuthGate (Phase 5/6/7 placeholders)
 * - /debug/agent-stream inside AuthGate, dev-flag gated
 * - /access-denied OUTSIDE AuthGate (D-18 — avoid redirect loop on 403)
 * - * (404) OUTSIDE AuthGate
 */
export default function App() {
  return (
    <Routes>
      {/* Layout route: AuthGate wraps AppShell wraps protected children. */}
      <Route element={<AuthGate />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route
            path="dashboard"
            element={
              <Lazy>
                <DashboardPage />
              </Lazy>
            }
          />
          <Route
            path="chat"
            element={
              <Lazy>
                <ChatPage />
              </Lazy>
            }
          />
          <Route
            path="profile"
            element={
              <Lazy>
                <ProfilePage />
              </Lazy>
            }
          />
          {DebugAgentStreamPage && (
            <Route
              path="debug/agent-stream"
              element={
                <Lazy>
                  <DebugAgentStreamPage />
                </Lazy>
              }
            />
          )}
        </Route>
      </Route>

      {/* Outside AuthGate per D-18 (avoid redirect loop on AccessDenied). */}
      <Route path="/access-denied" element={<AccessDeniedPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
