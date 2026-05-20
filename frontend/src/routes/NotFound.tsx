import { FileQuestion } from 'lucide-react'
import { useNavigate } from 'react-router'

import { EmptyState } from '@/components/EmptyState'

/**
 * `*` fallback route (outside AuthGate per UI-SPEC §6). Copy from §13.
 */
export function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <EmptyState
      icon={FileQuestion}
      heading="Page not found"
      body="The page you're looking for doesn't exist."
      cta={{ label: 'Go to dashboard', onClick: () => navigate('/dashboard') }}
    />
  )
}
