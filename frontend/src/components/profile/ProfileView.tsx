// Phase 7 Plan 05 — read-only display of the persisted user_profile row.
//
// CONTEXT.md D-Discretion: shows current skills as alphabetical secondary Badge
// chips with count in the header. PATTERNS §17 / UI-SPEC §6b analog.
// Consumes the GET /profile endpoint shipped by Plan 04 Task 3 via getProfile().
//
// TanStack Query key ['profile'] matches the cache that useResumeUpload writes to
// on save (D-22), so the chip list updates immediately after a profile save.

import { useQuery } from '@tanstack/react-query'
import { AlertCircle, User } from 'lucide-react'

import { getProfile } from '@/api/profile'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/EmptyState'

export function ProfileView() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['profile'],
    queryFn: ({ signal }) => getProfile(signal),
    staleTime: 5 * 60_000,
  })

  return (
    <Card data-testid="profile-view">
      <CardHeader>
        <CardTitle className="text-sm font-medium">
          Current skills{data ? ` (${data.skills.length})` : ''}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isPending && (
          <div
            className="flex flex-wrap gap-2"
            role="status"
            aria-label="Loading profile"
            aria-live="polite"
          >
            {Array.from({ length: 12 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-20" />
            ))}
          </div>
        )}
        {isError && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            <AlertTitle>Could not load profile</AlertTitle>
            <AlertDescription>{(error as Error).message}</AlertDescription>
          </Alert>
        )}
        {!isPending && !isError && data && data.skills.length === 0 && (
          <EmptyState
            icon={User}
            heading="No skills yet"
            body="Upload your resume below to seed your profile."
          />
        )}
        {!isPending && !isError && data && data.skills.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {[...data.skills]
              .sort((a, b) =>
                a.name.toLowerCase().localeCompare(b.name.toLowerCase()),
              )
              .map((s) => (
                <Badge key={s.name} variant="secondary">
                  {s.name}
                </Badge>
              ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
