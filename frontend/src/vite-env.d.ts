/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TENANT_SUBDOMAIN: string
  readonly VITE_TENANT_ID: string
  readonly VITE_SPA_CLIENT_ID: string
  readonly VITE_API_AUDIENCE: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_DEBUG_PAGES?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
