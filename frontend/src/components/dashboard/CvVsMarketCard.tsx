import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Target } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/EmptyState'

import { cvVsMarket } from '@/api/jobs'
import { useDashboardFilters } from './useDashboardFilters'
import { describeError } from './errors'

function CvVsMarketSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading match score" aria-live="polite">
      <div className="space-y-2 border-b border-border pb-4">
        <Skeleton className="h-12 w-24" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-32" />
        <div className="flex flex-wrap gap-1.5">
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-14" />
        </div>
      </div>
    </div>
  )
}

export function CvVsMarketCard() {
  const { filters } = useDashboardFilters()
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['dashboard', 'cv-vs-market', filters],
    queryFn: ({ signal }) => cvVsMarket(filters, signal),
    staleTime: 5 * 60_000,
  })

  const hasData = data != null && data.mean_score != null

  return (
    <Card className="flex flex-col" data-testid="cv-vs-market-card">
      <CardHeader>
        <CardTitle className="text-sm font-medium">CV vs market</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 space-y-4">
        {isPending && <CvVsMarketSkeleton />}
        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Couldn't load match score</AlertTitle>
            <AlertDescription>{describeError(error)}</AlertDescription>
          </Alert>
        )}
        {!isPending && !isError && data && !hasData && (
          <EmptyState
            icon={Target}
            heading="No postings to compare"
            body="No postings to compare against — try adjusting filters."
          />
        )}
        {!isPending && !isError && hasData && data.mean_score !== null && data.mean_score !== undefined && (
          <>
            <div className="space-y-1 border-b border-border pb-4">
              <div
                className="text-5xl font-medium tabular-nums"
                aria-label={`Match score ${data.mean_score.toFixed(2)}`}
              >
                {data.mean_score.toFixed(2)}
              </div>
              <div className="text-xs text-muted-foreground">Match score</div>
            </div>
            {data.top_missing_must_have.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">Missing must-haves</div>
                <div className="flex flex-wrap gap-1.5">
                  {data.top_missing_must_have.map((m) => (
                    <Badge key={m.skill} variant="secondary">
                      <span className="font-mono">{m.skill}</span>
                      <span className="ml-1 text-muted-foreground tabular-nums">
                        {Math.round(m.percentage)}%
                      </span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
      {data && !isError && (
        <CardFooter className="text-xs text-muted-foreground">
          Score across {data.postings_compared}{' '}
          {data.postings_compared === 1 ? 'posting' : 'postings'}
        </CardFooter>
      )}
    </Card>
  )
}
