// Phase 5 - Dashboard page composition (DASH-04).
// Replaces the Phase 4 placeholder stub. App.tsx lazy-imports the
// `DashboardPage` named export, so the named export is preserved.

import { CvVsMarketCard } from '@/components/dashboard/CvVsMarketCard'
import { DashboardFilters } from '@/components/dashboard/DashboardFilters'
import { SalaryBandsCard } from '@/components/dashboard/SalaryBandsCard'
import { TopSkillsCard } from '@/components/dashboard/TopSkillsCard'

export function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6" data-testid="dashboard-page">
      <DashboardFilters />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <TopSkillsCard />
        <SalaryBandsCard />
        <CvVsMarketCard />
      </div>
    </div>
  )
}
