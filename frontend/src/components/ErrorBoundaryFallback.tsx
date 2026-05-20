import { useNavigate } from 'react-router'
import type { FallbackProps } from 'react-error-boundary'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

/**
 * D-19a global render-error fallback. UI-SPEC §9 anatomy + §13 copywriting +
 * §15 a11y (role="alert" announces on mount).
 *
 * Truncates the stack to 1000 chars (UI-SPEC §9) so the card doesn't overflow.
 */
export function ErrorBoundaryFallback({ error, resetErrorBoundary }: FallbackProps) {
  const navigate = useNavigate()
  const truncated =
    error instanceof Error
      ? (error.stack ?? error.message).slice(0, 1000)
      : String(error).slice(0, 1000)

  return (
    <Card className="max-w-2xl mx-auto mt-12 p-8">
      <CardHeader>
        <CardTitle role="alert" className="text-lg font-semibold">
          Something went wrong
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-6">
          The app hit an unexpected error. You can try going back to the dashboard, or reload the
          page.
        </p>
        <div className="flex gap-2 mb-6">
          <Button
            variant="default"
            onClick={() => {
              resetErrorBoundary()
              navigate('/dashboard')
            }}
          >
            Back to dashboard
          </Button>
          <Button variant="outline" onClick={() => window.location.reload()}>
            Reload page
          </Button>
        </div>
        <details>
          <summary className="text-xs cursor-pointer">Technical details</summary>
          <pre className="font-mono text-xs bg-muted p-4 mt-2 overflow-x-auto">{truncated}</pre>
        </details>
      </CardContent>
    </Card>
  )
}
