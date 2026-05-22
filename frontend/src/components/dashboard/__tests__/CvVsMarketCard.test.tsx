import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'

import { CvVsMarketCard } from '@/components/dashboard/CvVsMarketCard'

vi.mock('@/api/jobs', () => ({
  topSkills: vi.fn(),
  salaryBands: vi.fn(),
  cvVsMarket: vi.fn(),
}))

import { cvVsMarket } from '@/api/jobs'

function renderWithProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter initialEntries={['/']}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('CvVsMarketCard', () => {
  it('renders the Card with title "CV vs market"', () => {
    vi.mocked(cvVsMarket).mockResolvedValue({
      mean_score: 0.42,
      postings_compared: 98,
      top_missing_must_have: [],
    })
    renderWithProviders(<CvVsMarketCard />)
    expect(screen.getByText('CV vs market')).toBeInTheDocument()
  })

  it('shows hero number with .toFixed(2)', async () => {
    vi.mocked(cvVsMarket).mockResolvedValue({
      mean_score: 0.42,
      postings_compared: 98,
      top_missing_must_have: [],
    })
    renderWithProviders(<CvVsMarketCard />)
    expect(await screen.findByText('0.42')).toBeInTheDocument()
    expect(screen.getByText('Match score')).toBeInTheDocument()
  })

  it('shows up to 3 missing must-have skills as Badge chips', async () => {
    vi.mocked(cvVsMarket).mockResolvedValue({
      mean_score: 0.42,
      postings_compared: 98,
      top_missing_must_have: [
        { skill: 'AWS', count: 42, percentage: 42.9 },
        { skill: 'SQL', count: 35, percentage: 35.7 },
        { skill: 'docker', count: 28, percentage: 28.6 },
      ],
    })
    renderWithProviders(<CvVsMarketCard />)
    expect(await screen.findByText('AWS')).toBeInTheDocument()
    expect(screen.getByText('SQL')).toBeInTheDocument()
    expect(screen.getByText('docker')).toBeInTheDocument()
    // Percentages rendered as integers
    expect(screen.getByText('43%')).toBeInTheDocument()
  })

  it('shows EmptyState "No postings to compare" when data.mean_score === null', async () => {
    vi.mocked(cvVsMarket).mockResolvedValue({
      mean_score: null,
      postings_compared: 0,
      top_missing_must_have: [],
    })
    renderWithProviders(<CvVsMarketCard />)
    expect(await screen.findByText('No postings to compare')).toBeInTheDocument()
  })

  it('shows Alert "Couldn\'t load match score" when isError', async () => {
    vi.mocked(cvVsMarket).mockRejectedValue(new Error('cv-vs-market: HTTP 500'))
    renderWithProviders(<CvVsMarketCard />)
    expect(await screen.findByText("Couldn't load match score")).toBeInTheDocument()
  })

  it('renders footer "Score across 98 postings"', async () => {
    vi.mocked(cvVsMarket).mockResolvedValue({
      mean_score: 0.42,
      postings_compared: 98,
      top_missing_must_have: [],
    })
    renderWithProviders(<CvVsMarketCard />)
    expect(await screen.findByText('Score across 98 postings')).toBeInTheDocument()
  })
})
