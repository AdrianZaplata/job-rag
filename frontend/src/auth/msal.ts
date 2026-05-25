import { PublicClientApplication, type Configuration, LogLevel } from '@azure/msal-browser'

const tenantSubdomain = import.meta.env.VITE_TENANT_SUBDOMAIN
const tenantId = import.meta.env.VITE_TENANT_ID
const clientId = import.meta.env.VITE_SPA_CLIENT_ID

// Authority follows the CIAM (Entra External ID) shape — D-07 amendment /
// RESEARCH §Open Question Q1. NOT login.microsoftonline.com.
const authority = `https://${tenantSubdomain}.ciamlogin.com/${tenantId}/v2.0`

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority,
    // Without knownAuthorities MSAL refuses non-microsoftonline.com authorities
    // (RESEARCH §Pitfall 1).
    knownAuthorities: [`${tenantSubdomain}.ciamlogin.com`],
    // SPA + PKCE auth-code flow (AUTH-02 / Pitfall 2).
    redirectUri: window.location.origin + '/',
    postLogoutRedirectUri: window.location.origin + '/',
    // navigateToLoginRequestUrl moved from BrowserAuthOptions to per-request
    // HandleRedirectPromiseOptions in @azure/msal-browser 5.x; the default (true)
    // already matches the desired behaviour.
  },
  cache: {
    // D-06 — tab-scoped; lower XSS blast radius vs localStorage.
    cacheLocation: 'sessionStorage',
    // storeAuthStateInCookie was removed from CacheOptions in @azure/msal-browser 5.x;
    // the library no longer uses cookies for auth state on modern browsers.
  },
  system: {
    // MSAL 5.x renamed the silent-iframe wait — it's `iframeBridgeTimeout` now
    // (BroadcastChannel-based, default 10000ms per BrowserConstants
    // DEFAULT_IFRAME_TIMEOUT_MS). The older `iframeHashTimeout` / `windowHashTimeout`
    // options were removed from `BrowserSystemOptions` in 5.x — keeping the old
    // names breaks `tsc -b --noEmit`.
    //
    // Bump to 30s so cold CIAM / ciamlogin.com responses, slow networks, and
    // Microsoft session-cookie propagation don't fall through to the redirect
    // fallback unnecessarily. The popup path (`popupBridgeTimeout`) already
    // defaults to 60s and we don't use popup acquisition, so leave it.
    iframeBridgeTimeout: 30000,
    loggerOptions: {
      logLevel: import.meta.env.DEV ? LogLevel.Verbose : LogLevel.Error,
      piiLoggingEnabled: false,
      loggerCallback: (_level, message) => {
        if (import.meta.env.DEV) {
          console.log('[MSAL]', message)
        }
      },
    },
  },
}

// Singleton — created at module-load. main.tsx awaits initialize() +
// handleRedirectPromise() BEFORE ReactDOM.createRoot().render() per AUTH-07 / D-05.
export const msalInstance = new PublicClientApplication(msalConfig)
