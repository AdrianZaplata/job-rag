// Phase 5 - typed URL-state hook for the dashboard filter bar (DASH-06).
//
// Reads `?country=&seniority=&remote=` from React Router's useSearchParams; returns
// a typed DashboardFilters object with defaults applied. setFilters(patch) writes
// the new state with default elision (omit `country=WW` and `remote=any` from URL
// so /dashboard (no params) is canonical for the all-defaults state).
//
// Used by:
//   - DashboardFilters (component) for the filter bar controls
//   - TopSkillsCard / SalaryBandsCard / CvVsMarketCard for the useQuery key + fetcher

import { useSearchParams } from 'react-router'

import type { components } from '@/api/types'

// Seniority union from codegen (matches src/job_rag/models.py::Seniority StrEnum)
export type Seniority = components['schemas']['Seniority']

export type Country = 'PL' | 'DE' | 'EU' | 'WW'
export type Remote = 'any' | 'remote' | 'non_remote'

export type DashboardFilters = {
  country: Country
  seniority: Seniority | undefined
  remote: Remote
}

const DEFAULT_COUNTRY: Country = 'WW'
const DEFAULT_REMOTE: Remote = 'any'

const COUNTRIES: readonly Country[] = ['PL', 'DE', 'EU', 'WW'] as const
const REMOTES: readonly Remote[] = ['any', 'remote', 'non_remote'] as const
const SENIORITIES: readonly Seniority[] = [
  'junior',
  'mid',
  'senior',
  'staff',
  'lead',
  'unknown',
] as const

function isCountry(v: string | null): v is Country {
  return v !== null && (COUNTRIES as readonly string[]).includes(v)
}

function isRemote(v: string | null): v is Remote {
  return v !== null && (REMOTES as readonly string[]).includes(v)
}

function isSeniority(v: string | null): v is Seniority {
  return v !== null && (SENIORITIES as readonly string[]).includes(v)
}

export function useDashboardFilters() {
  const [params, setParams] = useSearchParams()

  const countryRaw = params.get('country')
  const seniorityRaw = params.get('seniority')
  const remoteRaw = params.get('remote')

  const filters: DashboardFilters = {
    country: isCountry(countryRaw) ? countryRaw : DEFAULT_COUNTRY,
    seniority: isSeniority(seniorityRaw) ? seniorityRaw : undefined,
    remote: isRemote(remoteRaw) ? remoteRaw : DEFAULT_REMOTE,
  }

  function setFilters(patch: Partial<DashboardFilters>) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if ('country' in patch) {
          if (patch.country && patch.country !== DEFAULT_COUNTRY) {
            next.set('country', patch.country)
          } else {
            next.delete('country')
          }
        }
        if ('seniority' in patch) {
          if (patch.seniority) {
            next.set('seniority', patch.seniority)
          } else {
            next.delete('seniority')
          }
        }
        if ('remote' in patch) {
          if (patch.remote && patch.remote !== DEFAULT_REMOTE) {
            next.set('remote', patch.remote)
          } else {
            next.delete('remote')
          }
        }
        return next
      },
      { replace: false },
    )
  }

  return { filters, setFilters }
}
