import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router'

// Mock the MSAL React hooks BEFORE importing AuthGate.
vi.mock('@azure/msal-react', () => ({
  useIsAuthenticated: () => false,
  useMsal: () => ({ inProgress: 'none' }),
}))

const loginRedirectMock = vi.fn().mockResolvedValue(undefined)
vi.mock('@/auth/msal', () => ({
  msalInstance: {
    loginRedirect: loginRedirectMock,
  },
}))
vi.mock('@/auth/scopes', () => ({
  loginRequest: { scopes: ['api://test/access_as_user'] },
}))

describe('AuthGate', () => {
  it('calls loginRedirect when unauthenticated and inProgress=none', async () => {
    const { AuthGate } = await import('@/components/AuthGate')
    render(
      <MemoryRouter>
        <Routes>
          <Route element={<AuthGate />}>
            <Route path="/" element={<div>protected</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )
    // useEffect dispatch is async; flush a tick.
    await new Promise((r) => setTimeout(r, 0))
    expect(loginRedirectMock).toHaveBeenCalledTimes(1)
  })
})
