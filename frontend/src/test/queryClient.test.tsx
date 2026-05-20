import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClientProvider, useQuery } from '@tanstack/react-query'
import { queryClient } from '@/api/queryClient'

// SHEL-03 proof per VALIDATION.md: the QueryClient instance composes with `useQuery`
// inside a real `QueryClientProvider` without throwing.

function Probe() {
  const { data } = useQuery({
    queryKey: ['probe'],
    queryFn: async () => 'ok',
    staleTime: Infinity,
  })
  return <span data-testid="probe">{data ?? 'loading'}</span>
}

describe('queryClient', () => {
  it('composes useQuery and resolves', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <Probe />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('probe').textContent).toBe('ok'))
  })
})
