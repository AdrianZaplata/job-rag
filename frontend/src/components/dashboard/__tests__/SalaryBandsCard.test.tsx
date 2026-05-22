import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'

import { SalaryBandsCard } from '@/components/dashboard/SalaryBandsCard'

vi.mock('@/api/jobs', () => ({
  topSkills: vi.fn(),
  salaryBands: vi.fn(),
  cvVsMarket: vi.fn(),
}))

import { salaryBands } from '@/api/jobs'

function renderWithProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter initialEntries={['/']}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('SalaryBandsCard', () => {
  it('renders the Card with title "Salary bands"', () => {
    vi.mocked(salaryBands).mockResolvedValue({
      p25: 60000, p50: 75000, p75: 90000,
      postings_with_salary: 8, total_postings: 12, currency: 'EUR',
    })
    renderWithProviders(<SalaryBandsCard />)
    expect(screen.getByText('Salary bands')).toBeInTheDocument()
  })

  it('shows EmptyState "No salary data" when data.p50 === null', async () => {
    vi.mocked(salaryBands).mockResolvedValue({
      p25: null, p50: null, p75: null,
      postings_with_salary: 0, total_postings: 12, currency: 'EUR',
    })
    renderWithProviders(<SalaryBandsCard />)
    expect(await screen.findByText('No salary data')).toBeInTheDocument()
    expect(
      screen.getByText('No postings with salary data match these filters.'),
    ).toBeInTheDocument()
  })

  it('shows Alert "Couldn\'t load salary bands" when isError', async () => {
    vi.mocked(salaryBands).mockRejectedValue(new Error('salary-bands: HTTP 500'))
    renderWithProviders(<SalaryBandsCard />)
    expect(await screen.findByText("Couldn't load salary bands")).toBeInTheDocument()
  })

  it('renders footer "41 of 98 postings had salary data" (literal DASH-02 footnote)', async () => {
    vi.mocked(salaryBands).mockResolvedValue({
      p25: 60000, p50: 75000, p75: 90000,
      postings_with_salary: 41, total_postings: 98, currency: 'EUR',
    })
    renderWithProviders(<SalaryBandsCard />)
    expect(await screen.findByText(/41 of 98 postings had salary data/)).toBeInTheDocument()
  })

  it('singular pluralization at total=1', async () => {
    vi.mocked(salaryBands).mockResolvedValue({
      p25: 60000, p50: 75000, p75: 90000,
      postings_with_salary: 1, total_postings: 1, currency: 'EUR',
    })
    renderWithProviders(<SalaryBandsCard />)
    expect(await screen.findByText(/1 of 1 posting had salary data/)).toBeInTheDocument()
  })

  it('shows Skeleton when isPending', () => {
    vi.mocked(salaryBands).mockImplementation(() => new Promise(() => {}))
    renderWithProviders(<SalaryBandsCard />)
    expect(screen.getByRole('status', { name: 'Loading salary bands' })).toBeInTheDocument()
  })
})
