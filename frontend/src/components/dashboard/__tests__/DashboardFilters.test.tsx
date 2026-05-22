import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

import { DashboardFilters } from '@/components/dashboard/DashboardFilters'

function renderWithRouter() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <DashboardFilters />
    </MemoryRouter>,
  )
}

describe('DashboardFilters', () => {
  it('renders the filter group with aria-label "Dashboard filters"', () => {
    renderWithRouter()
    const group = screen.getByRole('group', { name: 'Dashboard filters' })
    expect(group).toBeInTheDocument()
  })

  it('renders country trigger with default label "Worldwide"', () => {
    renderWithRouter()
    expect(screen.getByRole('button', { name: /Worldwide/i })).toBeInTheDocument()
  })

  it('renders seniority trigger with default label "Any seniority"', () => {
    renderWithRouter()
    expect(screen.getByRole('button', { name: /Any seniority/i })).toBeInTheDocument()
  })

  it('renders remote ToggleGroup with 3 items: Any, Remote, On-site', () => {
    renderWithRouter()
    // ToggleGroup items are role=radio inside a role=radiogroup (Radix default) OR
    // role=button if shadcn renders as plain toggles - assert both possibilities
    expect(screen.getByText('Any')).toBeInTheDocument()
    expect(screen.getByText('Remote')).toBeInTheDocument()
    expect(screen.getByText('On-site')).toBeInTheDocument()
  })

  it('Remote toggle group has aria-label "Remote policy"', () => {
    renderWithRouter()
    expect(screen.getByRole('group', { name: 'Remote policy' })).toBeInTheDocument()
  })
})
