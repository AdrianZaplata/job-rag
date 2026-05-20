import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

vi.mock('@/auth/msal', () => ({
  msalInstance: {
    logoutRedirect: vi.fn(),
  },
}))

describe('AppShell', () => {
  it('renders nav with Dashboard / Chat / Profile + account menu', async () => {
    const { AppShell } = await import('@/components/AppShell')
    render(
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>,
    )
    expect(screen.getByRole('navigation', { name: /primary/i })).toBeInTheDocument()
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument()
    expect(screen.getByText(/chat/i)).toBeInTheDocument()
    expect(screen.getByText(/profile/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /open account menu/i })).toBeInTheDocument()
  })
})
