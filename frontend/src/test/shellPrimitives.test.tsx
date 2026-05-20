import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { ErrorBoundary } from 'react-error-boundary'
import { Inbox } from 'lucide-react'

import { ErrorBoundaryFallback } from '@/components/ErrorBoundaryFallback'
import { EmptyState } from '@/components/EmptyState'
import { RouteSkeleton } from '@/components/RouteSkeleton'

// SHEL-06 (VALIDATION.md) — three rendering proofs covering the three layered
// loading/error primitives. Grep on class names alone is insufficient per the
// validator's per-task verification map.

// Component that always throws — used to exercise the ErrorBoundary fallback path.
// Return type annotated as `never` so TS treats the throw as the function's exit.
function Boom(): never {
  throw new Error('boom from test')
}

describe('shell primitives (SHEL-06)', () => {
  it('ErrorBoundary renders ErrorBoundaryFallback with "Something went wrong" on throw', () => {
    // MemoryRouter needed because ErrorBoundaryFallback calls useNavigate().
    // Silence the expected console.error spam from React's error logging.
    const consoleError = console.error
    console.error = () => undefined
    try {
      render(
        <MemoryRouter>
          <ErrorBoundary FallbackComponent={ErrorBoundaryFallback}>
            <Boom />
          </ErrorBoundary>
        </MemoryRouter>,
      )
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    } finally {
      console.error = consoleError
    }
  })

  it('EmptyState renders heading and body', () => {
    render(<EmptyState icon={Inbox} heading="Empty" body="No data" />)
    expect(screen.getByRole('heading', { name: /empty/i })).toBeInTheDocument()
    expect(screen.getByText(/no data/i)).toBeInTheDocument()
  })

  it('RouteSkeleton renders without throwing', () => {
    render(<RouteSkeleton />)
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
  })
})
