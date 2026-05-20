import { QueryClient } from '@tanstack/react-query'

// Defaults per CONTEXT.md Claude's Discretion (immutable).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 2,
      networkMode: 'online',
    },
    mutations: {
      networkMode: 'online',
      retry: 0,
    },
  },
})
