import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

describe('ThemeToggle', () => {
  // Bind to window.localStorage explicitly. Node 22+ ships its own global
  // localStorage (experimental, --localstorage-file backed) which can shadow
  // jsdom's per-window implementation depending on Node version and runtime
  // flags. Using `window.localStorage` ensures we hit the jsdom one consistently.
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('toggles theme + persists to localStorage', async () => {
    const { ThemeToggle } = await import('@/components/ThemeToggle')
    render(<ThemeToggle />)
    const btn = screen.getByRole('button', { name: /toggle theme/i })
    // Default dark per UI-SPEC §1 — first click toggles to light.
    fireEvent.click(btn)
    expect(window.localStorage.getItem('theme')).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    fireEvent.click(btn)
    expect(window.localStorage.getItem('theme')).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
