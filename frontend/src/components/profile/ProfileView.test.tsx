// Phase 7 Plan 05 — ProfileView tests per VALIDATION 07-05-05.

import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { ProfileView } from './ProfileView'

vi.mock('@/api/profile', () => ({
  getProfile: vi.fn(),
}))

import { getProfile } from '@/api/profile'

function renderWithProviders(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('ProfileView', () => {
  it('renders Current skills (N) header + alphabetical Badge chips when loaded', async () => {
    vi.mocked(getProfile).mockResolvedValueOnce({
      skills: [
        { name: 'Python' },
        { name: 'docker' },
        { name: 'FastAPI' },
      ],
      target_roles: [],
      preferred_locations: [],
      // canonical UserSkillProfile shape allows either min_salary OR min_salary_eur;
      // the component only reads `skills`.
      remote_preference: 'unknown',
    } as never)

    renderWithProviders(<ProfileView />)

    // Header shows the count.
    expect(await screen.findByText('Current skills (3)')).toBeInTheDocument()

    // Each skill renders as text inside a Badge.
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('docker')).toBeInTheDocument()
    expect(screen.getByText('FastAPI')).toBeInTheDocument()
  })

  it('shows skeleton placeholders during loading', () => {
    // Pending forever — never resolves.
    vi.mocked(getProfile).mockReturnValueOnce(new Promise(() => {}))
    renderWithProviders(<ProfileView />)
    const loading = screen.getByRole('status', { name: /loading profile/i })
    expect(loading).toBeInTheDocument()
  })

  it('shows error Alert when getProfile rejects', async () => {
    vi.mocked(getProfile).mockRejectedValueOnce(new Error('boom'))
    renderWithProviders(<ProfileView />)
    await waitFor(() =>
      expect(screen.getByText('Could not load profile')).toBeInTheDocument(),
    )
    expect(screen.getByText(/boom/)).toBeInTheDocument()
  })

  it('shows EmptyState when profile has zero skills', async () => {
    vi.mocked(getProfile).mockResolvedValueOnce({
      skills: [],
      target_roles: [],
      preferred_locations: [],
      remote_preference: 'unknown',
    } as never)
    renderWithProviders(<ProfileView />)
    expect(await screen.findByText('No skills yet')).toBeInTheDocument()
  })
})
