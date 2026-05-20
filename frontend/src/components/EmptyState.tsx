import type { LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

/**
 * D-19c/d — typed empty-state primitive. UI-SPEC §10 contract.
 *
 * Phase 5/6/7 will compose this with feature-specific copy. Phase 4 uses it
 * indirectly via PhasePlaceholder + AccessDenied empty-OID fallback + NotFound.
 */
export type EmptyStateProps = {
  icon: LucideIcon
  heading: string
  body: string
  cta?: { label: string; onClick: () => void }
}

export function EmptyState({ icon: Icon, heading, body, cta }: EmptyStateProps) {
  return (
    <Card className="max-w-md mx-auto mt-24 p-8 text-center">
      <CardContent className="space-y-4">
        <Icon className="h-12 w-12 text-muted-foreground mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-2xl font-semibold">{heading}</h2>
        <p className="text-sm text-muted-foreground">{body}</p>
        {cta && (
          <Button variant="default" onClick={cta.onClick} className="mt-4">
            {cta.label}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
