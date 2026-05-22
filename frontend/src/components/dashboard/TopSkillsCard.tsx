import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, BarChart3 } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/EmptyState'

import { topSkills, type TopSkillItem } from '@/api/jobs'
import { useDashboardFilters } from './useDashboardFilters'
import { TopSkillsDialog } from './TopSkillsDialog'
import { describeError } from './errors'

const VISIBLE_ROWS = 10

function TopSkillsSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading top skills" aria-live="polite">
      {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <div key={i} className="space-y-1">
          <div className="flex items-center justify-between">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-3 w-12" />
          </div>
          <Skeleton className="h-1.5 w-full" />
        </div>
      ))}
    </div>
  )
}

function SkillRow({ skill, max }: { skill: TopSkillItem; max: number }) {
  const widthPct = Math.round((skill.total / max) * 100)
  const mustPct = Math.round((skill.must_count / skill.total) * 100)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono text-xs">{skill.skill}</span>
        <span className="text-xs text-muted-foreground tabular-nums">
          {skill.total} ({skill.must_count}m / {skill.nice_count}n)
        </span>
      </div>
      <div
        className="mt-1 h-1.5 w-full overflow-hidden rounded-sm bg-muted"
        role="presentation"
      >
        <div
          className="h-full bg-foreground"
          style={{ width: `${widthPct}%` }}
          aria-hidden="true"
        >
          <div
            className="h-full bg-primary"
            style={{ width: `${mustPct}%` }}
            aria-hidden="true"
          />
        </div>
      </div>
    </div>
  )
}

function SkillsBarList({ skills }: { skills: TopSkillItem[] }) {
  if (skills.length === 0) return null
  const max = skills[0].total || 1
  return (
    <div className="space-y-2">
      {skills.map((s) => (
        <SkillRow key={s.skill} skill={s} max={max} />
      ))}
    </div>
  )
}

export function TopSkillsCard() {
  const { filters } = useDashboardFilters()
  const [open, setOpen] = useState(false)

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['dashboard', 'top-skills', filters],
    queryFn: ({ signal }) => topSkills(filters, signal),
    staleTime: 5 * 60_000, // D-22 override of Phase 4 30s default
  })

  return (
    <Card className="flex flex-col" data-testid="top-skills-card">
      <CardHeader>
        <CardTitle className="text-sm font-medium">Top skills</CardTitle>
      </CardHeader>
      <CardContent className="flex-1">
        {isPending && <TopSkillsSkeleton />}
        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Couldn't load top skills</AlertTitle>
            <AlertDescription>{describeError(error)}</AlertDescription>
          </Alert>
        )}
        {!isPending && !isError && data && data.skills.length === 0 && (
          <EmptyState
            icon={BarChart3}
            heading="No skills"
            body="No skills match these filters. Try widening the filter set."
          />
        )}
        {!isPending && !isError && data && data.skills.length > 0 && (
          <>
            <SkillsBarList skills={data.skills.slice(0, VISIBLE_ROWS)} />
            {data.skills.length > VISIBLE_ROWS && (
              <div className="flex justify-end pt-2">
                <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
                  Show more
                </Button>
              </div>
            )}
            <TopSkillsDialog open={open} onOpenChange={setOpen} skills={data.skills} />
          </>
        )}
      </CardContent>
      {data && !isError && (
        <CardFooter className="text-xs text-muted-foreground">
          {data.total_postings} {data.total_postings === 1 ? 'posting' : 'postings'}
          {' · '}
          {data.unique_skills}{' '}
          {data.unique_skills === 1 ? 'unique hard skill' : 'unique hard skills'}
        </CardFooter>
      )}
    </Card>
  )
}
