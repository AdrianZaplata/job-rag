// Phase 5 Wave 0 — skip-on-missing vitest stub. Plan 05-05 lands the component.
import { describe, it, expect } from 'vitest'

// String-concat the import spec so tsc doesn't try to resolve it at type-check time.
// Plan 04-04 pattern — see .planning/phases/04-frontend-shell-auth/04-04-SUMMARY.md.
const spec = '@/components/' + 'dashboard/TopSkillsCard'

let TopSkillsCard: unknown
try {
  const mod = (await import(/* @vite-ignore */ spec)) as { TopSkillsCard?: unknown }
  TopSkillsCard = mod.TopSkillsCard
} catch {
  // module not yet shipped — Plan 05-05 will land it
}

describe.skipIf(!TopSkillsCard)('TopSkillsCard', () => {
  it('renders the Card with title "Top skills"', () => {
    // Plan 05-05 fills body per UI-SPEC section 5:
    //   - data-testid="top-skills-card"
    //   - CardTitle text "Top skills"
    //   - per-state branch: Skeleton (isPending) / Alert (isError) / EmptyState (data.skills.length===0) / SkillsBarList
    expect(true).toBe(true)
  })
  it('shows Skeleton when isPending', () => {
    expect(true).toBe(true)
  })
  it('shows Alert "Couldn\'t load top skills" when isError', () => {
    expect(true).toBe(true)
  })
  it('shows EmptyState "No skills" when data.skills.length === 0', () => {
    expect(true).toBe(true)
  })
  it('renders Show more button when data.skills.length > 10', () => {
    expect(true).toBe(true)
  })
  it('renders footer "98 postings · 187 unique hard skills"', () => {
    expect(true).toBe(true)
  })
})
