import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('khôi phục consent analytics', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
  })

  it('khôi phục receipt nếu thiết bị đã đồng ý trước đó', async () => {
    localStorage.setItem('quan4-consent', 'granted')
    localStorage.setItem('quan4-consent-receipt', 'receipt-da-luu')

    const { useConsentStore } = await import('./consentStore')

    expect(useConsentStore.getState().trangThai).toBe('granted')
    expect(useConsentStore.getState().receipt).toBe('receipt-da-luu')
  })

  it('không khôi phục receipt nếu consent đã bị thu hồi', async () => {
    localStorage.setItem('quan4-consent', 'revoked')
    localStorage.setItem('quan4-consent-receipt', 'receipt-cu')

    const { useConsentStore } = await import('./consentStore')

    expect(useConsentStore.getState().trangThai).toBe('revoked')
    expect(useConsentStore.getState().receipt).toBeNull()
  })

  it('yêu cầu xác nhận lại nếu consent cũ không còn receipt', async () => {
    localStorage.setItem('quan4-consent', 'granted')

    const { useConsentStore } = await import('./consentStore')

    expect(useConsentStore.getState().trangThai).toBe('chua-chon')
    expect(useConsentStore.getState().receipt).toBeNull()
  })
})
