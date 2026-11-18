
// API configuration for local development and production.

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim()
const defaultApiHost =
  typeof window !== 'undefined' && window.location.hostname !== ''
    ? window.location.hostname
    : 'localhost'

export function resolveApiBaseUrl(
  configuredUrl: string | undefined,
  pageHostname: string,
  production: boolean,
): string {
  if (!configuredUrl && production) {
    throw new Error(
      'Missing VITE_API_URL. Please configure it in Vercel Environment Variables.',
    )
  }

  const resolvedUrl = new URL(configuredUrl || `http://${pageHostname}:8000`)
  const loopbackHosts = new Set(['localhost', '127.0.0.1'])
  // Keep local API requests same-site so browsers send the Lax auth cookies.
  if (
    !production
    && loopbackHosts.has(pageHostname)
    && loopbackHosts.has(resolvedUrl.hostname)
  ) {
    resolvedUrl.hostname = pageHostname
  }

  return resolvedUrl.toString().replace(/\/+$/, '')
}

export const API_BASE_URL = resolveApiBaseUrl(
  configuredApiUrl,
  defaultApiHost,
  import.meta.env.PROD,
)
