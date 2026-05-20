import { useEffect, useState } from 'react'
import { Sun, Moon } from 'lucide-react'

import { Button } from '@/components/ui/button'

/**
 * D-20 — top-nav theme toggle.
 *
 * Read order: localStorage['theme'] → matchMedia('prefers-color-scheme') → 'dark'
 * (default per UI-SPEC §1). Persists every toggle to localStorage; applies via the
 * Tailwind `class="dark"` literal on `<html>`. Matches the FOUC script in
 * index.html (Pitfall 10) so the first paint already has the right class.
 */
type Theme = 'light' | 'dark'

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem('theme')
    if (stored === 'dark' || stored === 'light') return stored
    // No stored preference — fall back to OS preference; default dark when
    // matchMedia is unavailable or reports light (UI-SPEC §1 default dark).
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      const preferDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      return preferDark ? 'dark' : 'dark'
    }
    return 'dark'
  } catch {
    return 'dark'
  }
}

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    applyTheme(theme)
    try {
      localStorage.setItem('theme', theme)
    } catch {
      // localStorage unavailable (private mode / disabled storage); non-fatal.
    }
  }, [theme])

  const next: Theme = theme === 'dark' ? 'light' : 'dark'
  const Icon = theme === 'dark' ? Sun : Moon

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`Toggle theme (currently ${theme})`}
      onClick={() => setTheme(next)}
      className="transition-all duration-150"
    >
      <Icon className="h-4 w-4" />
    </Button>
  )
}
