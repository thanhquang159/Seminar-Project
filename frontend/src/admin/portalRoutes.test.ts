import { describe, expect, it } from 'vitest'
import {
  getAdminPortalPage,
  getOwnerPortalPage,
  getPortalPath,
  isStaleLoginSessionCheck,
} from './portalRoutes'

describe('portal routes', () => {
  it('resolves owner sections and accepts the submission route alias', () => {
    expect(getOwnerPortalPage('/owner')).toBe('submission')
    expect(getOwnerPortalPage('/owner/submission')).toBe('submission')
    expect(getOwnerPortalPage('/owner/menu')).toBe('menu')
    expect(getOwnerPortalPage('/owner/unknown')).toBeNull()
  })

  it('resolves admin sections and accepts the POI route alias', () => {
    expect(getAdminPortalPage('/admin')).toBe('pois')
    expect(getAdminPortalPage('/admin/pois')).toBe('pois')
    expect(getAdminPortalPage('/admin/approvals')).toBe('approvals')
    expect(getAdminPortalPage('/admin/translations')).toBe('translations')
    expect(getAdminPortalPage('/admin/unknown')).toBeNull()
  })

  it('builds canonical paths for dashboard links', () => {
    expect(getPortalPath('owner', 'submission')).toBe('/owner')
    expect(getPortalPath('owner', 'notifications')).toBe('/owner/notifications')
    expect(getPortalPath('admin', 'pois')).toBe('/admin')
    expect(getPortalPath('admin', 'analytics')).toBe('/admin/analytics')
    expect(getPortalPath('admin', 'translations')).toBe('/admin/translations')
  })

  it('ignores a failed login-page session probe after navigation has moved on', () => {
    expect(isStaleLoginSessionCheck('/admin/login', '/admin', '/admin/login')).toBe(true)
    expect(isStaleLoginSessionCheck('/admin/approvals', '/admin/approvals', '/admin/login')).toBe(false)
  })
})
