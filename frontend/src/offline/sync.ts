// Đồng bộ delta: tải toàn bộ lần đầu, sau chỉ tải phần đổi.

import type { Poi } from '../stores/poiStore'
import { API_BASE_URL } from '../config'
import {
  docCursor,
  docPois,
  docPoisFallback,
  luuCursor,
  luuPois,
  luuThucDonCongKhai,
  xoaTatCaCachePois,
  type PublicPoiMenu,
  type PublicPoiMenuItem,
} from './idb'

const API_GOC = API_BASE_URL

// Gộp delta vào danh sách cũ: cập nhật/thêm, xóa theo removed_poi_ids.
export function gopDelta(cu: Poi[], capNhat: Poi[], xoaIds: string[]): Poi[] {
  const boXoa = new Set(xoaIds)
  const bang = new Map(cu.filter((p) => !boXoa.has(p.id)).map((p) => [p.id, p]))
  for (const p of capNhat) bang.set(p.id, p)
  return [...bang.values()]
}

async function luuCache(lang: string, pois: Poi[], version: number): Promise<void> {
  try {
    await luuPois(lang, pois, version)
    await luuCursor(lang, version)
  } catch (error) {
    console.warn('Không lưu được POI vào cache ngoại tuyến:', error)
  }
}

async function taiToanBo(lang: string): Promise<Poi[]> {
  const res = await fetch(`${API_GOC}/poi/load-all?lang=${lang}`)
  if (!res.ok) throw new Error(`Không thể tải danh sách POI (HTTP ${res.status})`)
  const goi = (await res.json()) as { version: number; sync_cursor: number; pois: Poi[] }
  await luuCache(lang, goi.pois, goi.sync_cursor)
  return goi.pois
}

export async function taiThucDonNgoaiTuyen(lang: string): Promise<number> {
  const response = await fetch(`${API_GOC}/poi/menus`)
  if (!response.ok) {
    throw new Error(`Không thể tải thực đơn ngoại tuyến (HTTP ${response.status})`)
  }
  const payload: unknown = await response.json()
  if (!Array.isArray(payload) || !payload.every(laThucDonCongKhai)) {
    throw new Error('Dữ liệu thực đơn ngoại tuyến không hợp lệ')
  }
  const menusByPoi = payload.reduce<Record<string, PublicPoiMenu[]>>((grouped, menu) => {
    const menus = grouped[menu.poi_id] ?? []
    menus.push(menu)
    grouped[menu.poi_id] = menus
    return grouped
  }, {})
  await luuThucDonCongKhai(lang, menusByPoi)
  return payload.length
}

function laThucDonCongKhai(value: unknown): value is PublicPoiMenu {
  if (typeof value !== 'object' || value === null) return false
  const menu = value as Record<string, unknown>
  return (
    typeof menu.id === 'string'
    && typeof menu.poi_id === 'string'
    && typeof menu.name === 'string'
    && (typeof menu.description === 'string' || menu.description === null)
    && Array.isArray(menu.items)
    && menu.items.every(laMonCongKhai)
  )
}

function laMonCongKhai(value: unknown): value is PublicPoiMenuItem {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  return (
    typeof item.id === 'string'
    && typeof item.name === 'string'
    && (typeof item.description === 'string' || item.description === null)
    && (typeof item.price === 'number' || typeof item.price === 'string' || item.price === null)
    && typeof item.currency_code === 'string'
    && typeof item.is_available === 'boolean'
  )
}

export async function dongBo(
  lang: string,
  taiLaiToanBo = false,
): Promise<{ pois: Poi[]; tuMang: boolean }> {
  try {
    if (taiLaiToanBo) {
      return { pois: await taiToanBo(lang), tuMang: true }
    }

    let banCu: { pois: Poi[]; version: number } | null
    try {
      banCu = await docPois(lang)
    } catch (error) {
      console.warn('Không đọc được danh sách POI trong cache ngoại tuyến:', error)
      banCu = null
    }

    // Cache VI từ bản cũ có thể chứa fallback EN dù nội dung nguồn VI đã có.
    // Tải snapshot để sửa cả khi cursor và số lượng POI không thay đổi.
    if (lang === 'vi' && banCu?.pois.some((p) => p.lang !== 'vi' || p.is_fallback)) {
      return { pois: await taiToanBo(lang), tuMang: true }
    }

    if (banCu !== null) {
      const response = await fetch(`${API_GOC}/poi/count`)
      if (!response.ok) {
        throw new Error(`Không thể kiểm tra số lượng POI (HTTP ${response.status})`)
      }
      const payload: unknown = await response.json()
      if (
        typeof payload !== 'object'
        || payload === null
        || !('count' in payload)
        || typeof payload.count !== 'number'
        || !Number.isInteger(payload.count)
        || payload.count < 0
      ) {
        throw new Error('Số lượng POI từ máy chủ không hợp lệ')
      }
      if (payload.count !== banCu.pois.length) {
        await xoaTatCaCachePois()
        return { pois: await taiToanBo(lang), tuMang: true }
      }
    } else {
      return { pois: await taiToanBo(lang), tuMang: true }
    }

    let cursor = 0
    try {
      cursor = await docCursor(lang)
    } catch (error) {
      console.warn('Không đọc được cursor POI trong cache ngoại tuyến:', error)
    }
    if (cursor === 0) {
      return { pois: await taiToanBo(lang), tuMang: true }
    }

    const res = await fetch(`${API_GOC}/poi/delta?updated_after=${cursor}&lang=${lang}`)
    if (res.status === 400) {
      // Local cursor can belong to another database snapshot. A full snapshot
      // replaces stale IDs that have no tombstone in this database's history.
      return { pois: await taiToanBo(lang), tuMang: true }
    }
    if (!res.ok) throw new Error(`Không thể đồng bộ POI (HTTP ${res.status})`)
    const goi = (await res.json()) as { version: number; sync_cursor: number; updated: Poi[]; removed_poi_ids: string[] }
    const gop = gopDelta(banCu.pois, goi.updated, goi.removed_poi_ids)
    await luuCache(lang, gop, goi.sync_cursor)
    return { pois: gop, tuMang: true }
  } catch (error) {
    const pois = await docPoisFallback(lang)
    if (pois.length > 0) {
      console.warn('Không kết nối được API POI; đang dùng dữ liệu ngoại tuyến:', error)
      return { pois, tuMang: false }
    }
    const chiTiet = error instanceof Error ? error.message : 'Lỗi không xác định'
    throw new Error(`Không thể tải POI từ máy chủ và không có cache ngoại tuyến. ${chiTiet}`, {
      cause: error,
    })
  }
}
