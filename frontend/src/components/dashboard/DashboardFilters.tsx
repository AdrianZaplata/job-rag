import { ChevronDown } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

import { useDashboardFilters } from './useDashboardFilters'

const COUNTRY_LABEL: Record<'PL' | 'DE' | 'EU' | 'WW', string> = {
  PL: 'Poland',
  DE: 'Germany',
  EU: 'EU',
  WW: 'Worldwide',
}

const SENIORITY_LABEL: Record<'junior' | 'mid' | 'senior' | 'staff' | 'lead', string> = {
  junior: 'Junior',
  mid: 'Mid',
  senior: 'Senior',
  staff: 'Staff',
  lead: 'Lead',
}

export function DashboardFilters() {
  const { filters, setFilters } = useDashboardFilters()

  return (
    <div
      className="flex flex-col gap-2 md:flex-row md:items-center"
      role="group"
      aria-label="Dashboard filters"
      data-testid="dashboard-filters"
    >
      {/* Country */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="justify-between md:w-40">
            {COUNTRY_LABEL[filters.country]}
            <ChevronDown className="h-4 w-4 opacity-50" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuRadioGroup
            value={filters.country}
            onValueChange={(v) => setFilters({ country: v as typeof filters.country })}
          >
            <DropdownMenuRadioItem value="WW">Worldwide</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="EU">EU</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="DE">Germany</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="PL">Poland</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Seniority */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="justify-between md:w-40">
            {filters.seniority && filters.seniority in SENIORITY_LABEL
              ? SENIORITY_LABEL[filters.seniority as keyof typeof SENIORITY_LABEL]
              : 'Any seniority'}
            <ChevronDown className="h-4 w-4 opacity-50" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuRadioGroup
            value={filters.seniority ?? ''}
            onValueChange={(v) =>
              setFilters({
                seniority: v === '' ? undefined : (v as typeof filters.seniority),
              })
            }
          >
            <DropdownMenuRadioItem value="">Any seniority</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="junior">Junior</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="mid">Mid</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="senior">Senior</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="staff">Staff</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="lead">Lead</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Remote */}
      <ToggleGroup
        type="single"
        value={filters.remote}
        onValueChange={(v) => {
          if (v) setFilters({ remote: v as typeof filters.remote })
        }}
        aria-label="Remote policy"
        size="sm"
      >
        <ToggleGroupItem value="any" aria-label="Any remote policy">
          Any
        </ToggleGroupItem>
        <ToggleGroupItem value="remote" aria-label="Remote only">
          Remote
        </ToggleGroupItem>
        <ToggleGroupItem value="non_remote" aria-label="On-site or hybrid only">
          On-site
        </ToggleGroupItem>
      </ToggleGroup>
    </div>
  )
}
