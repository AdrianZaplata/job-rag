// Phase 5 (Dashboard) - typed analytics service module per CONTEXT.md D-15 / D-16 /
// PATTERNS C.7. Three async functions wrap authedFetch and return the
// openapi-typescript-codegened response types.
//
// Used by Plan 05-05's widget components via TanStack Query:
//   const { data } = useQuery({
//     queryKey: ['dashboard', 'top-skills', filters],
//     queryFn: ({ signal }) => topSkills(filters, signal),
//     staleTime: 5 * 60_000,
//   })

import { authedFetch } from '@/api/authedFetch'
import type { components } from '@/api/types'

import type { DashboardFilters } from '@/components/dashboard/useDashboardFilters'

// Re-export the codegen-derived response types so widgets can import type from here.
export type TopSkillsResponse = components['schemas']['DashboardTopSkillsResponse']
export type SalaryBandsResponse = components['schemas']['DashboardSalaryBandsResponse']
export type CvMatchResponse = components['schemas']['DashboardCvMatchResponse']
export type TopSkillItem = components['schemas']['TopSkillItem']
export type MissingSkillItem = components['schemas']['MissingSkillItem']

/**
 * Build the ?country=&seniority=&remote= query string from a DashboardFilters object.
 *
 * Default elision matches the URL-side (useDashboardFilters): WW / undefined / any
 * are omitted from the query string so the URL stays clean.
 */
function buildFilterQuery(filters: DashboardFilters): string {
  const params = new URLSearchParams()
  if (filters.country !== 'WW') params.set('country', filters.country)
  if (filters.seniority !== undefined) params.set('seniority', filters.seniority)
  if (filters.remote !== 'any') params.set('remote', filters.remote)
  const q = params.toString()
  return q ? `?${q}` : ''
}

/** GET /dashboard/top-skills - DASH-01 */
export async function topSkills(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<TopSkillsResponse> {
  const res = await authedFetch(`/dashboard/top-skills${buildFilterQuery(filters)}`, { signal })
  if (!res.ok) throw new Error(`top-skills: HTTP ${res.status}`)
  return res.json() as Promise<TopSkillsResponse>
}

/** GET /dashboard/salary-bands - DASH-02 */
export async function salaryBands(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<SalaryBandsResponse> {
  const res = await authedFetch(`/dashboard/salary-bands${buildFilterQuery(filters)}`, { signal })
  if (!res.ok) throw new Error(`salary-bands: HTTP ${res.status}`)
  return res.json() as Promise<SalaryBandsResponse>
}

/** GET /dashboard/cv-vs-market - DASH-03 */
export async function cvVsMarket(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<CvMatchResponse> {
  const res = await authedFetch(`/dashboard/cv-vs-market${buildFilterQuery(filters)}`, { signal })
  if (!res.ok) throw new Error(`cv-vs-market: HTTP ${res.status}`)
  return res.json() as Promise<CvMatchResponse>
}
