interface BootErrorFallbackProps {
  error: unknown
}

/**
 * Phase 04.1 fix 3 — minimal Tailwind-only boot-time error surface. Shown when
 * main.tsx's top-level await (msalInstance.initialize / handleRedirectPromise)
 * or the initial createRoot().render() rejects. Deliberately does NOT use
 * shadcn primitives, MSAL, or React Router — those subsystems may be exactly
 * what failed, so the fallback path must be hermetic.
 *
 * See .planning/phases/04-frontend-shell-auth/04-06-SUMMARY.md deviation #10.
 */
export function BootErrorFallback({ error }: BootErrorFallbackProps) {
  const message =
    error instanceof Error ? (error.stack ?? error.message) : String(error)
  const truncated = message.slice(0, 1000)

  return (
    <div
      role="alert"
      className="min-h-screen flex items-center justify-center bg-neutral-950 text-neutral-100 p-6"
    >
      <div className="max-w-2xl w-full rounded-lg border border-neutral-800 bg-neutral-900 p-8 shadow-lg">
        <h1 className="text-xl font-semibold mb-2">We hit a problem starting the app.</h1>
        <p className="text-sm text-neutral-400 mb-6">
          The app couldn't finish loading. Try reloading the page. If this keeps happening,
          your session may need to be refreshed.
        </p>
        <pre className="font-mono text-xs bg-neutral-950 border border-neutral-800 rounded p-4 mb-6 overflow-x-auto whitespace-pre-wrap">
          {truncated}
        </pre>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex items-center justify-center rounded-md bg-neutral-100 text-neutral-950 px-4 py-2 text-sm font-medium hover:bg-neutral-200 focus:outline-none focus:ring-2 focus:ring-neutral-400"
        >
          Reload page
        </button>
      </div>
    </div>
  )
}
