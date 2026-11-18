export type PortalRole = 'admin' | 'owner'
export type OwnerPortalPage = 'submission' | 'history' | 'places' | 'qr' | 'menu' | 'notifications'
export type AdminPortalPage = 'pois' | 'approvals' | 'audio' | 'analytics' | 'access' | 'audit'
export type PortalPage = OwnerPortalPage | AdminPortalPage

const OWNER_PATHS: Record<OwnerPortalPage, string> = {
  submission: '/owner',
  history: '/owner/history',
  places: '/owner/places',
  qr: '/owner/qr',
  menu: '/owner/menu',
  notifications: '/owner/notifications',
}

const OWNER_PAGES: Record<string, OwnerPortalPage> = {
  '/owner': 'submission',
  '/owner/submission': 'submission',
  '/owner/history': 'history',
  '/owner/places': 'places',
  '/owner/qr': 'qr',
  '/owner/menu': 'menu',
  '/owner/notifications': 'notifications',
}

const ADMIN_PATHS: Record<AdminPortalPage, string> = {
  pois: '/admin',
  approvals: '/admin/approvals',
  audio: '/admin/audio',
  analytics: '/admin/analytics',
  access: '/admin/access',
  audit: '/admin/audit',
}

const ADMIN_PAGES: Record<string, AdminPortalPage> = {
  '/admin': 'pois',
  '/admin/pois': 'pois',
  '/admin/approvals': 'approvals',
  '/admin/audio': 'audio',
  '/admin/analytics': 'analytics',
  '/admin/access': 'access',
  '/admin/audit': 'audit',
}

const PORTAL_PATHS: Record<PortalRole, Record<string, string>> = {
  owner: OWNER_PATHS,
  admin: ADMIN_PATHS,
}

function normalizePath(pathname: string): string {
  return pathname.replace(/\/+$/, '') || '/'
}

export function getOwnerPortalPage(pathname: string): OwnerPortalPage | null {
  return OWNER_PAGES[normalizePath(pathname)] ?? null
}

export function getAdminPortalPage(pathname: string): AdminPortalPage | null {
  return ADMIN_PAGES[normalizePath(pathname)] ?? null
}

export function getPortalPath(role: PortalRole, page: PortalPage): string {
  return PORTAL_PATHS[role][page] ?? `/${role}`
}

export function isStaleLoginSessionCheck(pathAtStart: string, currentPath: string, loginPath: string): boolean {
  return pathAtStart === loginPath && currentPath !== loginPath
}

export function navigateToPath(path: string, replace = false): void {
  const currentPath = `${window.location.pathname}${window.location.search}`
  if (currentPath === path) return

  if (replace) {
    window.history.replaceState(null, '', path)
  } else {
    window.history.pushState(null, '', path)
  }
  window.dispatchEvent(new PopStateEvent('popstate'))
}
