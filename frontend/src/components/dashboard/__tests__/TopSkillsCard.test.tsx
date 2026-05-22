import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'

import { TopSkillsCard } from '@/components/dashboard/TopSkillsCard'

// Mock the API module so tests are hermetic (no real network).
vi.mock('@/api/jobs', () => ({
  topSkills: vi.fn(),
  salaryBands: vi.fn(),
  cvVsMarket: vi.fn(),
}))

import { topSkills } from '@/api/jobs'

function renderWithProviders(ui: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <MemoryRouter initialEntries={['/']}>
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('TopSkillsCard', () => {
  it('renders the Card with title "Top skills"', () => {
    vi.mocked(topSkills).mockResolvedValue({
      skills: [],
      total_postings: 0,
      unique_skills: 0,
    })
    renderWithProviders(<TopSkillsCard />)
    expect(screen.getByText('Top skills')).toBeInTheDocument()
  })

  it('shows Skeleton when isPending (query never resolves)', () => {
    // Mock a never-resolving promise to simulate isPending
    vi.mocked(topSkills).mockImplementation(() => new Promise(() => {}))
    renderWithProviders(<TopSkillsCard />)
    expect(screen.getByRole('status', { name: 'Loading top skills' })).toBeInTheDocument()
  })

  it('shows Alert "Couldn\'t load top skills" when isError', async () => {
    vi.mocked(topSkills).mockRejectedValue(new Error('top-skills: HTTP 500'))
    renderWithProviders(<TopSkillsCard />)
    expect(await screen.findByText("Couldn't load top skills")).toBeInTheDocument()
  })

  it('shows EmptyState "No skills" when data.skills.length === 0', async () => {
    vi.mocked(topSkills).mockResolvedValue({
      skills: [],
      total_postings: 12,
      unique_skills: 0,
    })
    renderWithProviders(<TopSkillsCard />)
    expect(await screen.findByText('No skills')).toBeInTheDocument()
    expect(
      screen.getByText('No skills match these filters. Try widening the filter set.'),
    ).toBeInTheDocument()
  })

  it('renders Show more button when data.skills.length > 10', async () => {
    const manySkills = Array.from({ length: 15 }, (_, i) => ({
      skill: `skill${i}`,
      must_count: 5,
      nice_count: 2,
      total: 7 - Math.floor(i / 5),
    }))
    vi.mocked(topSkills).mockResolvedValue({
      skills: manySkills,
      total_postings: 50,
      unique_skills: 15,
    })
    renderWithProviders(<TopSkillsCard />)
    expect(await screen.findByRole('button', { name: 'Show more' })).toBeInTheDocument()
  })

  it('renders footer with pluralization "98 postings · 187 unique hard skills"', async () => {
    vi.mocked(topSkills).mockResolvedValue({
      skills: [{ skill: 'Python', must_count: 1, nice_count: 0, total: 1 }],
      total_postings: 98,
      unique_skills: 187,
    })
    renderWithProviders(<TopSkillsCard />)
    expect(await screen.findByText(/98 postings/)).toBeInTheDocument()
    expect(screen.getByText(/187 unique hard skills/)).toBeInTheDocument()
  })

  it('singular pluralization at count=1: "1 posting · 1 unique hard skill"', async () => {
    vi.mocked(topSkills).mockResolvedValue({
      skills: [{ skill: 'Python', must_count: 1, nice_count: 0, total: 1 }],
      total_postings: 1,
      unique_skills: 1,
    })
    renderWithProviders(<TopSkillsCard />)
    expect(await screen.findByText(/1 posting/)).toBeInTheDocument()
    expect(screen.getByText(/1 unique hard skill/)).toBeInTheDocument()
    // Make sure plural didn't sneak in
    expect(screen.queryByText(/1 postings/)).not.toBeInTheDocument()
  })
})
