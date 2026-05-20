// Thin re-export wrapper for the SHEL-06 layer-a global render-error boundary.
//
// main.tsx wraps <App/> with react-error-boundary's <ErrorBoundary> directly and
// passes FallbackComponent={ErrorBoundaryFallback}. This module exports both so
// downstream consumers can import a single name from a single path.
export { ErrorBoundary } from 'react-error-boundary'
export { ErrorBoundaryFallback } from './ErrorBoundaryFallback'
