// Đồng bộ delta: tải toàn bộ lần đầu, sau chỉ tải phần đổi.

import type { Poi } from '../stores/poiStore'
import { API_BASE_URL } from '../config'
import { docCursor, docPois, docPoisFallback, luuCursor, luuPois } from './idb'

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

export async function dongBo(
  lang: string,
  taiLaiToanBo = false,
): Promise<{ pois: Poi[]; tuMang: boolean }> {
  try {
    if (taiLaiToanBo) {
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
    let banCu: { pois: Poi[]; version: number } | null
    try {
      banCu = await docPois(lang)
    } catch (error) {
      console.warn('Không đọc được danh sách POI trong cache ngoại tuyến:', error)
      banCu = null
    }
    if (!banCu) {
      return { pois: await taiToanBo(lang), tuMang: true }
    }
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
