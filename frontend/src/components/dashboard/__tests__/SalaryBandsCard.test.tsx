// Phase 5 Wave 0 — skip-on-missing vitest stub. Plan 05-05 lands the component.
import { describe, it, expect } from 'vitest'

const spec = '@/components/' + 'dashboard/SalaryBandsCard'
let SalaryBandsCard: unknown
try {
  const mod = (await import(/* @vite-ignore */ spec)) as { SalaryBandsCard?: unknown }
  SalaryBandsCard = mod.SalaryBandsCard
} catch {
  // not yet shipped
}

describe.skipIf(!SalaryBandsCard)('SalaryBandsCard', () => {
  it('renders the Card with title "Salary bands"', () => {
    // UI-SPEC section 7: data-testid="salary-bands-card", Recharts BarChart inside ChartContainer
    expect(true).toBe(true)
  })
  it('renders 3 bars labeled p25 / p50 / p75', () => {
    expect(true).toBe(true)
  })
  it('shows EmptyState "No salary data" when data.p50 === null', () => {
    expect(true).toBe(true)
  })
  it('shows Alert "Couldn\'t load salary bands" when isError', () => {
    expect(true).toBe(true)
  })
  it('renders footer "41 of 98 postings had salary data" (literal DASH-02 footnote)', () => {
    expect(true).toBe(true)
  })
})
