import { Skeleton } from '@/components/ui/skeleton'

/**
 * D-19b — per-route Suspense fallback for React.lazy code-split chunks.
 *
 * UI-SPEC §11 container shape matches EmptyState (max-w-md mx-auto mt-24 p-8)
 * so there is no layout shift between RouteSkeleton and the resolved EmptyState
 * / PhasePlaceholder content.
 *
 * Honours `prefers-reduced-motion` via `motion-reduce:animate-none` (UI-SPEC §14).
 */
export function RouteSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading"
      className="max-w-md mx-auto mt-24 p-8 space-y-4 motion-reduce:animate-none"
    >
      <Skeleton className="h-6 w-1/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-9 w-32 mt-4" />
    </div>
  )
}
