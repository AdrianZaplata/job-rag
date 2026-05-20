import { useState } from 'react'
import { Copy as CopyIcon, ShieldX } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/EmptyState'

import { msalInstance } from '@/auth/msal'
import { loginRequest } from '@/auth/scopes'
import { decodeOidFromJwt } from '@/lib/decodeOidFromJwt'

/**
 * Synchronously compute the oid from MSAL state at mount time. Run as a lazy
 * useState initializer (avoids the set-state-in-effect cascade lint rule).
 */
function computeInitialOid(): string | null {
  const account = msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0]
  const claimsOid = account?.idTokenClaims?.oid as string | undefined
  if (claimsOid) return claimsOid
  if (account?.idToken) return decodeOidFromJwt(account.idToken)
  return null
}

/**
 * D-09 first-login bootstrap surface — OUTSIDE AuthGate per D-18 (else infinite
 * redirect loop on 403 response).
 *
 * UI-SPEC §8 anatomy:
 *  - Empty-OID fallback: EmptyState with "Sign in first" + Sign-in CTA (UI-SPEC §8
 *    explicitly: do NOT show an empty <pre> block).
 *  - Populated OID: Card max-w-2xl mx-auto mt-12 p-8; <pre><code> mono block;
 *    Copy ID button; Sonner toast on copy success/failure; admin runbook code block.
 *
 * Trust boundary T-04-05-02: the displayed oid is the user's OWN MSAL-parsed
 * claim; never used as an auth decision (backend validates oid independently).
 */
export function AccessDeniedPage() {
  // Lazy initializer reads MSAL state once at mount — no useEffect cascade.
  const [oid] = useState<string | null>(computeInitialOid)

  async function copyOid() {
    if (!oid) return
    try {
      await navigator.clipboard.writeText(oid)
      toast.success('Copied to clipboard')
    } catch {
      toast.error("Couldn't copy — please select and copy manually")
    }
  }

  if (!oid) {
    return (
      <EmptyState
        icon={ShieldX}
        heading="Sign in first"
        body="Sign in to see the account ID you need to share."
        cta={{
          label: 'Sign in',
          onClick: () => {
            msalInstance.loginRedirect(loginRequest)
          },
        }}
      />
    )
  }

  const runbook = `1. az keyvault secret set \\
   --vault-name jobrag-prod-kv \\
   --name seeded-user-entra-oid \\
   --value ${oid}

2. az containerapp revision restart \\
   --name jobrag-api-prod \\
   --resource-group jobrag-prod-rg

3. Reload this page and sign in again.`

  return (
    <Card className="max-w-2xl mx-auto mt-12 p-8">
      <CardHeader>
        <CardTitle className="text-2xl font-semibold">Access denied</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground mb-8">
          Your account is not on the allowlist. Send the ID below to the administrator to request
          access.
        </p>
        <div
          role="region"
          aria-label="Your account ID"
          className="mb-8 p-4 bg-muted rounded"
        >
          <p className="text-xs text-muted-foreground mb-2">Your account ID</p>
          <pre className="font-mono text-sm overflow-x-auto">
            <code>{oid}</code>
          </pre>
          <div className="flex justify-end mt-4">
            <Button variant="default" onClick={copyOid}>
              <CopyIcon className="h-4 w-4 mr-2" />
              Copy ID
            </Button>
          </div>
        </div>
        <h2 className="text-lg font-semibold mb-4">Administrator runbook</h2>
        <pre className="font-mono text-xs bg-muted p-4 overflow-x-auto whitespace-pre-wrap">
          {runbook}
        </pre>
      </CardContent>
    </Card>
  )
}
