import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Euro } from 'lucide-react'
import { Bar, BarChart, LabelList, XAxis } from 'recharts'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { ChartContainer, type ChartConfig } from '@/components/ui/chart'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/EmptyState'

import { salaryBands } from '@/api/jobs'
import { useDashboardFilters } from './useDashboardFilters'
import { describeError } from './errors'

const chartConfig: ChartConfig = {
  value: { label: 'Salary', color: 'var(--chart-1)' },
}

function formatEur(value: number): string {
  return `€${value.toLocaleString('en-US')}`
}

function SalaryBandsSkeleton() {
  return (
    <div
      className="flex h-48 items-end justify-around gap-4 px-4"
      role="status"
      aria-label="Loading salary bands"
      aria-live="polite"
    >
      <Skeleton className="h-16 w-12" />
      <Skeleton className="h-28 w-12" />
      <Skeleton className="h-40 w-12" />
    </div>
  )
}

export function SalaryBandsCard() {
  const { filters } = useDashboardFilters()
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['dashboard', 'salary-bands', filters],
    queryFn: ({ signal }) => salaryBands(filters, signal),
    staleTime: 5 * 60_000,
  })

  const hasData = data != null && data.p50 != null

  const bars = hasData
    ? [
        { band: 'p25', value: data.p25 ?? 0 },
        { band: 'p50', value: data.p50 ?? 0 },
        { band: 'p75', value: data.p75 ?? 0 },
      ]
    : []

  return (
    <Card className="flex flex-col" data-testid="salary-bands-card">
      <CardHeader>
        <CardTitle className="text-sm font-medium">Salary bands</CardTitle>
      </CardHeader>
      <CardContent className="flex-1">
        {isPending && <SalaryBandsSkeleton />}
        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Couldn't load salary bands</AlertTitle>
            <AlertDescription>{describeError(error)}</AlertDescription>
          </Alert>
        )}
        {!isPending && !isError && data && !hasData && (
          <EmptyState
            icon={Euro}
            heading="No salary data"
            body="No postings with salary data match these filters."
          />
        )}
        {!isPending && !isError && hasData && (
          <ChartContainer
            config={chartConfig}
            className="h-48 w-full"
            aria-label={`Salary band chart: p25 ${formatEur(data.p25 ?? 0)}/yr, p50 ${formatEur(data.p50 ?? 0)}/yr, p75 ${formatEur(data.p75 ?? 0)}/yr`}
          >
            <BarChart data={bars} accessibilityLayer>
              <XAxis dataKey="band" tickLine={false} axisLine={false} />
              <Bar dataKey="value" fill="var(--chart-1)" radius={4}>
                <LabelList
                  dataKey="value"
                  position="top"
                  formatter={(v: number) => `${formatEur(v)}/yr`}
                  className="fill-foreground text-xs"
                />
              </Bar>
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
      {data && !isError && (
        <CardFooter className="text-xs text-muted-foreground">
          {data.postings_with_salary} of {data.total_postings}{' '}
          {data.total_postings === 1 ? 'posting' : 'postings'} had salary data
        </CardFooter>
      )}
    </Card>
  )
}
