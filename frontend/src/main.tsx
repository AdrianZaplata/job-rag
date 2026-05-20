import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MsalProvider } from '@azure/msal-react'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { BrowserRouter } from 'react-router'
import { ErrorBoundary } from 'react-error-boundary'

import { msalInstance } from '@/auth/msal'
import { queryClient } from '@/api/queryClient'
import App from '@/App'
import { ErrorBoundaryFallback } from '@/components/ErrorBoundaryFallback'
import '@/app.css'

// D-05 literal AUTH-07 race fix — both promises resolve BEFORE first render.
// CONTEXT.md D-05: "No wrapping component, no Suspense + use() overengineering,
// no flash-of-null. Accepts ~50-150ms of blank first paint on cold load."
await msalInstance.initialize()
await msalInstance.handleRedirectPromise()

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('Root element #root not found in index.html')

createRoot(rootEl).render(
  <StrictMode>
    <MsalProvider instance={msalInstance}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ErrorBoundary FallbackComponent={ErrorBoundaryFallback}>
            <App />
          </ErrorBoundary>
        </BrowserRouter>
        {import.meta.env.DEV && <ReactQueryDevtools />}
      </QueryClientProvider>
    </MsalProvider>
  </StrictMode>,
)
