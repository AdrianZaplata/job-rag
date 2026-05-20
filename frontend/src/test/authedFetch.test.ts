import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock msal singleton + scopes BEFORE importing authedFetch.
vi.mock('@/auth/msal', () => ({
  msalInstance: {
    getActiveAccount: vi.fn(() => ({ homeAccountId: 'test-account' })),
    getAllAccounts: vi.fn(() => [{ homeAccountId: 'test-account' }]),
    setActiveAccount: vi.fn(),
    acquireTokenSilent: vi.fn(async () => ({ accessToken: 'fake-jwt-token-12345' })),
    acquireTokenRedirect: vi.fn(),
    loginRedirect: vi.fn(),
  },
}))

vi.mock('@/auth/scopes', () => ({
  loginRequest: { scopes: ['api://test/access_as_user'] },
  API_SCOPE: 'api://test/access_as_user',
}))

describe('authedFetch', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('attaches Bearer header from MSAL silent token', async () => {
    const { authedFetch } = await import('@/api/authedFetch')
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{}', { status: 200 }))
    await authedFetch('/api/test')
    const call = fetchSpy.mock.calls[0]
    const headers = (call?.[1]?.headers as Headers) || new Headers()
    expect(headers.get('Authorization')).toBe('Bearer fake-jwt-token-12345')
  })

  it('retries once after 401 with fresh token', async () => {
    const { authedFetch } = await import('@/api/authedFetch')
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response('{}', { status: 200 }))
    const result = await authedFetch('/api/test')
    expect(result.status).toBe(200)
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })
})
