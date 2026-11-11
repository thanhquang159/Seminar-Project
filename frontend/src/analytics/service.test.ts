import { beforeEach, describe, expect, it, vi } from 'vitest'
import { batDauAnalytics, batDauChiaSeMacDinh, flush, ghiSuKien, ghiSuKienNgay, xinDongY } from './service'
import { daDongY, damBaoAnonymousId, useConsentStore } from '../stores/consentStore'

const outbox = vi.hoisted(() => ({
  themSuKien: vi.fn().mockResolvedValue(undefined),
  laySuKien: vi.fn().mockResolvedValue([]),
  xoaSuKien: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('./outbox', () => outbox)

// Không mock module nào: muốn chứng minh "chưa đồng ý thì không gọi request"
// thì phải để chính cái cổng đó quyết định, không làm thay nó.
// Import tĩnh cả hai module để chúng dùng CHUNG một instance store —
// resetModules rồi import lại sẽ tạo store khác và test sẽ kiểm nhầm store rỗng.

function laiFetch() {
  const goi: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      goi.push(String(url))
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({ status: 'granted', receipt: 'r', tracked_online_users: 1, accepted: 1 }),
      })
    }),
  )
  return goi
}

function resetConsent() {
  vi.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
  useConsentStore.setState({ trangThai: 'chua-chon', receipt: null, trackedOnlineUsers: null })
}

describe('cổng consent', () => {
  beforeEach(resetConsent)

  it('chưa chọn thì chưa đồng ý', () => {
    expect(useConsentStore.getState().trangThai).toBe('chua-chon')
    expect(daDongY()).toBe(false)
  })

  it('đồng ý rồi mới coi là granted và nhớ lựa chọn', () => {
    useConsentStore.getState().datTrangThai('granted')
    expect(daDongY()).toBe(true)
    expect(localStorage.getItem('quan4-consent')).toBe('granted')
  })

  it('lưu receipt để tiếp tục gửi analytics sau khi tải lại trang', () => {
    useConsentStore.getState().datTrangThai('granted')
    useConsentStore.getState().datReceipt('receipt-can-khoi-phuc')

    expect(localStorage.getItem('quan4-consent-receipt')).toBe('receipt-can-khoi-phuc')
    useConsentStore.getState().datReceipt(null)
    expect(localStorage.getItem('quan4-consent-receipt')).toBeNull()
  })

  it('từ chối thì không phải granted', () => {
    useConsentStore.getState().datTrangThai('revoked')
    expect(daDongY()).toBe(false)
  })

  it('anonymous_id ổn định giữa các lần gọi', () => {
    const a = damBaoAnonymousId()
    expect(a).toBe(damBaoAnonymousId())
    expect(a.startsWith('anon-')).toBe(true)
    expect(a.length).toBeGreaterThanOrEqual(16)
  })

  it('anonymous_id và session_id là hai định danh khác nhau', () => {
    const anon = damBaoAnonymousId()
    expect(sessionStorage.getItem('quan4-session-id') ?? '').not.toBe(anon)
  })
})

describe('không có consent thì không gửi request analytics nào', () => {
  beforeEach(resetConsent)

  it('ghiSuKien bị chặn ngay ở cổng, không gọi fetch', async () => {
    const goi = laiFetch()
    await ghiSuKien('page_viewed', { poi_id: 'x' })
    batDauAnalytics()
    await flush(true)
    expect(goi.filter((u) => u.includes('/analytics/'))).toHaveLength(0)
  })

  it('batDauAnalytics không hẹn giờ gì khi chưa đồng ý', () => {
    const hen = vi.spyOn(window, 'setInterval')
    batDauAnalytics()
    expect(hen).not.toHaveBeenCalled()
    hen.mockRestore()
  })

  it('đã đồng ý thì mới gọi /analytics/collect', async () => {
    const goi = laiFetch()
    useConsentStore.setState({ trangThai: 'granted', receipt: 'receipt-hop-le' })
    await flush(true)
    expect(goi.some((u) => u.includes('/analytics/collect'))).toBe(true)
  })

  it('thiếu receipt thì không gửi, dù đã đồng ý', async () => {
    const goi = laiFetch()
    useConsentStore.setState({ trangThai: 'granted', receipt: null })
    expect(await flush(true)).toBe(0)
    expect(goi).toHaveLength(0)
  })

  it('gửi lượt nghe trực tiếp lên API khi consent hợp lệ', async () => {
    const goi = laiFetch()
    useConsentStore.setState({ trangThai: 'granted', receipt: 'receipt-hop-le' })

    await expect(
      ghiSuKienNgay('audio_played', { poi_id: 'poi-1', lang: 'vi', tier: 'tier1' }),
    ).resolves.toBe(true)

    expect(goi).toEqual([expect.stringContaining('/analytics/collect')])
    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)
    expect(body.heartbeat).toBe(false)
    expect(body.events).toEqual([
      expect.objectContaining({
        name: 'audio_played',
        properties: { poi_id: 'poi-1', lang: 'vi', tier: 'tier1' },
      }),
    ])
  })

  it('xếp lượt nghe vào outbox nếu gửi trực tiếp gặp lỗi mạng', async () => {
    useConsentStore.setState({ trangThai: 'granted', receipt: 'receipt-hop-le' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(ghiSuKienNgay('audio_played', { poi_id: 'poi-1' })).resolves.toBe(false)
    expect(outbox.themSuKien).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'audio_played',
        properties: { poi_id: 'poi-1' },
      }),
    )
  })
})

describe('xinDongY phải bật được trạng thái, không chỉ lưu receipt', () => {
  beforeEach(resetConsent)

  it('gọi API thành công thì trạng thái thành granted', async () => {
    laiFetch()
    const ok = await xinDongY()
    expect(ok).toBe(true)
    expect(useConsentStore.getState().trangThai).toBe('granted')
    expect(useConsentStore.getState().receipt).toBe('r')
    expect(localStorage.getItem('quan4-consent')).toBe('granted')
  })

  it('bật analytics mặc định cho thiết bị chưa có lựa chọn', async () => {
    laiFetch()
    await expect(batDauChiaSeMacDinh()).resolves.toBe(true)
    expect(useConsentStore.getState().trangThai).toBe('granted')
  })

  it('không ghi đè lựa chọn đã tắt trước đó', async () => {
    useConsentStore.getState().datTrangThai('revoked')
    const goi = laiFetch()
    await expect(batDauChiaSeMacDinh()).resolves.toBe(false)
    expect(goi).toHaveLength(0)
    expect(useConsentStore.getState().trangThai).toBe('revoked')
  })

  it('API lỗi thì không được bật, và không ghi consent vào localStorage', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })),
    )
    const ok = await xinDongY()
    expect(ok).toBe(false)
    expect(useConsentStore.getState().trangThai).toBe('chua-chon')
    expect(localStorage.getItem('quan4-consent')).toBeNull()
  })

  it('sau khi bật thì batDauAnalytics mới hẹn được nhịp gửi', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })),
    )
    // Chưa đồng ý: không hẹn gì.
    let hen = vi.spyOn(window, 'setInterval')
    batDauAnalytics()
    expect(hen).not.toHaveBeenCalled()
    hen.mockRestore()

    laiFetch()
    await xinDongY()

    hen = vi.spyOn(window, 'setInterval')
    batDauAnalytics()
    // session_started + page_viewed, và hai nhịp 15s/20s.
    expect(hen).toHaveBeenCalled()
    hen.mockRestore()
  })
})