// AnalyticsService: consent là điều kiện tiên quyết, không phải lựa chọn.
//
// Ràng buộc cứng của ANA-001: **chưa đồng ý thì không có một request analytics
// nào được gửi** (kiểm được bằng tab Network). Vì vậy `ghiSuKien` kiểm tra
// consent ngay ở cổng, trước cả khi ghi vào outbox — nếu chỉ kiểm ở lúc
// flush thì mất mạng rồi mới đồng ý vẫn có sự kiện nằm sẵn trong IDB.

import { laySuKien, themSuKien, xoaSuKien, type SuKienOutbox } from './outbox'
import { damBaoAnonymousId, daDongY, laySessionId, useConsentStore } from '../stores/consentStore'
import { API_BASE_URL } from '../config'

const API_GOC = API_BASE_URL
let consentRevision = 0
let consentQueue: Promise<void> = Promise.resolve()

function xepYeuCauConsent<T>(operation: () => Promise<T>): Promise<T> {
  const result = consentQueue.then(operation)
  consentQueue = result.then(() => undefined, () => undefined)
  return result
}

// Nhịp gửi: 15s gộp lô, 20s nhịp tim. Lấy từ sơ đồ luồng analytics.
export const CHU_KY_FLUSH_MS = 15000
export const CHU_KY_HEARTBEAT_MS = 20000
// page_engaged chỉ tính sau 10s người dùng thực sự nhìn trang.
export const NGHENG_ENGAGED_MS = 10000

export const TEN_SU_KIEN = [
  'session_started',
  'page_viewed',
  'page_engaged',
  'search',
  'audio_played',
  'poi_viewed',
] as const

export type TenSuKien = (typeof TEN_SU_KIEN)[number]

export function tenHopLe(ten: string): ten is TenSuKien {
  return (TEN_SU_KIEN as readonly string[]).includes(ten)
}

// Thuộc tính được gửi đi. Không có mục nào chứa thông tin định danh — nếu sau
// này cần thêm, phải thêm vào danh sách chặn phía server trước, không thêm
// ở đây rồi hy vọng server tự lọc.
const THUOC_TINH_CHO_PHEP = ['poi_id', 'query', 'lang', 'tier', 'duration_ms']

export function locThuocTinh(raw: Record<string, unknown>): Record<string, string | number | boolean> {
  const sach: Record<string, string | number | boolean> = {}
  for (const khoa of THUOC_TINH_CHO_PHEP) {
    const gt = raw[khoa]
    if (typeof gt === 'string') sach[khoa] = gt.slice(0, 120)
    else if (typeof gt === 'number' && Number.isFinite(gt)) sach[khoa] = gt
    else if (typeof gt === 'boolean') sach[khoa] = gt
  }
  return sach
}

export async function ghiSuKien(ten: TenSuKien, thuoc_tinh: Record<string, unknown> = {}): Promise<void> {
  if (!daDongY() || !tenHopLe(ten)) return
  const sk: SuKienOutbox = { name: ten, at: Date.now(), properties: locThuocTinh(thuoc_tinh) }
  try {
    await themSuKien(sk)
  } catch {
    return
  }
}

async function gui(
  bo: { name: string; at: number; properties: Record<string, unknown> }[],
  heartbeat: boolean,
): Promise<number> {
  const { receipt } = useConsentStore.getState()
  if (receipt === null) throw new Error('Thiếu receipt consent analytics')
  const res = await fetch(`${API_GOC}/analytics/collect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      anonymous_id: damBaoAnonymousId(),
      receipt,
      session_id: laySessionId(),
      heartbeat,
      events: bo,
    }),
  })
  if (res.status === 403) {
    // Server nói consent không còn hiệu lực (thu hồi từ tab khác, hết hạn).
    // Dừng ngay thay vì cứ gửi tiếp rồi nhận 403 mãi.
    useConsentStore.getState().datTrangThai('revoked')
    useConsentStore.getState().datReceipt(null)
    return 0
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const goi = (await res.json()) as {
    accepted?: number
    tracked_online_users: number | null
  }
  useConsentStore.getState().datTrackedOnlineUsers(goi.tracked_online_users)
  return goi.accepted ?? bo.length
}

export async function ghiSuKienNgay(
  ten: TenSuKien,
  thuoc_tinh: Record<string, unknown> = {},
): Promise<boolean> {
  if (!daDongY() || !tenHopLe(ten)) return false
  const suKien: SuKienOutbox = {
    name: ten,
    at: Date.now(),
    properties: locThuocTinh(thuoc_tinh),
  }
  try {
    return (await gui([suKien], false)) > 0
  } catch (error) {
    try {
      await themSuKien(suKien)
    } catch (storageError) {
      console.error('Không thể gửi hoặc xếp hàng sự kiện analytics:', {
        event: ten,
        networkError: error,
        storageError,
      })
    }
    return false
  }
}

export async function flush(heartbeat = false): Promise<number> {
  if (!daDongY()) return 0
  if (useConsentStore.getState().receipt === null) return 0
  const bo = await laySuKien().catch(() => [])
  try {
    await gui(bo, heartbeat)
  } catch {
    return 0
  }
  await xoaSuKien(bo.map((s) => s.id))
  return bo.length
}

export async function xinDongY(): Promise<boolean> {
  const revision = ++consentRevision
  return xepYeuCauConsent(async () => {
    const res = await fetch(`${API_GOC}/analytics/consent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ anonymous_id: damBaoAnonymousId(), granted: true }),
    })
    if (!res.ok) return false
    const goi = (await res.json()) as { status: string; receipt: string }
    if (goi.status !== 'granted' || revision !== consentRevision) return false
    useConsentStore.getState().datTrangThai('granted')
    useConsentStore.getState().datReceipt(goi.receipt)
    return true
  })
}

export async function batDauChiaSeMacDinh(): Promise<boolean> {
  if (useConsentStore.getState().trangThai !== 'chua-chon') return false
  return xinDongY()
}

export async function thuHoiDongY(): Promise<boolean> {
  ++consentRevision
  useConsentStore.getState().datTrangThai('revoked')
  useConsentStore.getState().datReceipt(null)
  useConsentStore.getState().datTrackedOnlineUsers(null)
  try {
    return await xepYeuCauConsent(async () => {
      const res = await fetch(`${API_GOC}/analytics/consent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ anonymous_id: damBaoAnonymousId(), granted: false }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return true
    })
  } catch (error) {
    console.error('Không thể đồng bộ việc tắt analytics lên máy chủ:', error)
    return false
  }
}

/** Mount một lần ở App. Tự dừng khi thu hồi consent, không gửi gì thêm. */
export function batDauAnalytics(): () => void {
  const { trangThai } = useConsentStore.getState()
  if (trangThai !== 'granted') return () => {}

  void ghiSuKien('session_started')
  void ghiSuKien('page_viewed')

  const henEngaged = window.setTimeout(() => {
    if (document.visibilityState === 'visible') void ghiSuKien('page_engaged')
  }, NGHENG_ENGAGED_MS)

  const henFlush = window.setInterval(() => {
    if (useConsentStore.getState().trangThai !== 'granted') return
    void flush(true)
  }, CHU_KY_FLUSH_MS)

  const henHeartbeat = window.setInterval(() => {
    if (document.visibilityState !== 'visible') return
    if (useConsentStore.getState().trangThai !== 'granted') return
    void flush(true)
  }, CHU_KY_HEARTBEAT_MS)

  return () => {
    window.clearTimeout(henEngaged)
    window.clearInterval(henFlush)
    window.clearInterval(henHeartbeat)
  }
}