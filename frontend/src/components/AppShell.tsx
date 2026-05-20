import { Link, NavLink, Outlet } from 'react-router'
import { User as UserIcon } from 'lucide-react'

import { Toaster } from '@/components/ui/sonner'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

import { msalInstance } from '@/auth/msal'
import { ThemeToggle } from '@/components/ThemeToggle'

/**
 * D-18 / UI-SPEC §7 — top-nav layout wrapper. Renders inside AuthGate's
 * authenticated branch; layout-route shape: AuthGate → AppShell → <Outlet/>.
 *
 * Anatomy (h-12 px-6 border-b):
 *   left cluster:  logo wordmark "job-rag" → /dashboard
 *                  Dashboard / Chat / Profile NavLinks (gap-6, 2px active accent)
 *   right cluster: ThemeToggle (icon) + account DropdownMenu (User icon)
 *                  account menu single item: "Sign out" (destructive variant) →
 *                  logoutRedirect with postLogoutRedirectUri=window.location.origin
 *                  per D-12.
 *   <Toaster /> mounted at the bottom so toasts persist across route transitions.
 */
function NavTab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `text-sm py-2 border-b-2 ${
          isActive
            ? 'border-primary text-foreground'
            : 'border-transparent text-muted-foreground hover:border-muted-foreground/50'
        }`
      }
    >
      {({ isActive }) => <span aria-current={isActive ? 'page' : undefined}>{label}</span>}
    </NavLink>
  )
}

export function AppShell() {
  function signOut() {
    msalInstance.logoutRedirect({
      postLogoutRedirectUri: window.location.origin,
    })
  }

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="h-12 border-b border-border flex items-center px-6 justify-between">
        <nav aria-label="Primary" className="flex items-center gap-6">
          <Link to="/dashboard" className="text-sm font-semibold">
            job-rag
          </Link>
          <NavTab to="/dashboard" label="Dashboard" />
          <NavTab to="/chat" label="Chat" />
          <NavTab to="/profile" label="Profile" />
        </nav>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Open account menu">
                <UserIcon className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                variant="destructive"
                onSelect={(e) => {
                  e.preventDefault()
                  signOut()
                }}
              >
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <Toaster position="bottom-right" richColors />
    </div>
  )
}
