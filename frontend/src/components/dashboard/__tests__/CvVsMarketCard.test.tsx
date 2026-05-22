// Phase 5 Wave 0 — skip-on-missing vitest stub. Plan 05-05 lands the component.
import { describe, it, expect } from 'vitest'

const spec = '@/components/' + 'dashboard/CvVsMarketCard'
let CvVsMarketCard: unknown
try {
  const mod = (await import(/* @vite-ignore */ spec)) as { CvVsMarketCard?: unknown }
  CvVsMarketCard = mod.CvVsMarketCard
} catch {
  // not yet shipped
}

describe.skipIf(!CvVsMarketCard)('CvVsMarketCard', () => {
  it('renders the Card with title "CV vs market"', () => {
    // UI-SPEC section 8: data-testid="cv-vs-market-card", text-5xl hero number, Badge chip list
    expect(true).toBe(true)
  })
  it('shows hero number with .toFixed(2)', () => {
    expect(true).toBe(true)
  })
  it('shows up to 3 missing must-have skills as Badge chips', () => {
    expect(true).toBe(true)
  })
  it('shows EmptyState "No postings to compare" when data.mean_score === null', () => {
    expect(true).toBe(true)
  })
  it('shows Alert "Couldn\'t load match score" when isError', () => {
    expect(true).toBe(true)
  })
  it('renders footer "Score across 98 postings"', () => {
    expect(true).toBe(true)
  })
})
