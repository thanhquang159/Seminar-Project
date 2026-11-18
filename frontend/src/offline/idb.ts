// IndexedDB hai lớp cùng SW cache: SW bị dọn thì IDB còn dữ liệu.
//
// Module này là **chủ sở hữu duy nhất** của schema `quan4-offline`. Ai cần
// thêm object store thì khai ở đây và export hằng tên ra, đừng tự mở DB ở
// module khác: IndexedDB chỉ cho mở đúng version đã tồn tại, nên nếu outbox
// mở phiên bản cũ rồi idb.ts mở version mới thì mọi lần đọc POI offline sẽ ném
// `VersionError` — lúc đó mới phát hiện là quá trễ.

import type { Poi } from '../stores/poiStore'

const TEN_DB = 'quan4-offline'
export const KHO_POI = 'pois_by_lang'
export const KHO_META = 'meta'
export const KHO_OUTBOX = 'analytics_outbox'
export const KHO_UI_BUNDLES = 'ui_translation_bundles'
export const KHO_MAP_PACKS = 'map_packs'
export const KHO_POI_MENUS = 'menus_by_lang'
// v1: POI + meta. v2: outbox analytics. v3: UI bundles + map packs. v4: public menus.
const PHIEN_DB = 4

export interface PublicPoiMenu {
  id: string
  poi_id: string
  name: string
  description: string | null
  items: {
    id: string
    name: string
    description: string | null
    price: number | string | null
    currency_code: string
    is_available: boolean
  }[]
}

export type PublicPoiMenuItem = PublicPoiMenu['items'][number]

type PublicPoiMenusRecord = {
  lang: string
  menusByPoi: Record<string, PublicPoiMenu[]>
  saved_at: number
}

export interface UiBundleRecord {
  id: string
  language_code: string
  namespace: string
  version_code: string
  translations: Record<string, string>
}

export interface MapPackMetadata {
  scope: string
  cacheName: string
  fingerprint: string
  styleUrl: string
  files: { file: string; sha256: string; bytes: number }[]
}

interface MapPackRecord extends MapPackMetadata {
  id: string
  assets: Record<string, Blob>
}

export function moDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const yeuCau = indexedDB.open(TEN_DB, PHIEN_DB)
    yeuCau.onupgradeneeded = () => {
      const db = yeuCau.result
      if (!db.objectStoreNames.contains(KHO_POI)) {
        db.createObjectStore(KHO_POI, { keyPath: 'lang' })
      }
      if (!db.objectStoreNames.contains(KHO_META)) {
        db.createObjectStore(KHO_META, { keyPath: 'khoa' })
      }
      if (!db.objectStoreNames.contains(KHO_OUTBOX)) {
        db.createObjectStore(KHO_OUTBOX, { keyPath: 'id', autoIncrement: true })
      }
      if (!db.objectStoreNames.contains(KHO_UI_BUNDLES)) {
        db.createObjectStore(KHO_UI_BUNDLES, { keyPath: 'id' })
      }
      if (!db.objectStoreNames.contains(KHO_MAP_PACKS)) {
        db.createObjectStore(KHO_MAP_PACKS, { keyPath: 'id' })
      }
      if (!db.objectStoreNames.contains(KHO_POI_MENUS)) {
        db.createObjectStore(KHO_POI_MENUS, { keyPath: 'lang' })
      }
    }
    yeuCau.onsuccess = () => resolve(yeuCau.result)
    yeuCau.onerror = () => reject(yeuCau.error)
  })
}

function ghi(db: IDBDatabase, kho: string, giaTri: unknown): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(kho, 'readwrite')
    tx.objectStore(kho).put(giaTri)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

function doc<T>(db: IDBDatabase, kho: string, khoa: string): Promise<T | null> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(kho, 'readonly')
    const yeuCau = tx.objectStore(kho).get(khoa)
    yeuCau.onsuccess = () => resolve((yeuCau.result as T) ?? null)
    yeuCau.onerror = () => reject(yeuCau.error)
  })
}

export async function luuPois(lang: string, pois: Poi[], version: number): Promise<void> {
  const db = await moDb()
  await ghi(db, KHO_POI, { lang, pois, version, saved_at: Date.now() })
  db.close()
}

export async function docPois(lang: string): Promise<{ pois: Poi[]; version: number } | null> {
  const db = await moDb()
  const ban = await doc<{ pois: Poi[]; version: number }>(db, KHO_POI, lang)
  db.close()
  return ban
}

export async function xoaTatCaCachePois(): Promise<void> {
  const db = await moDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction([KHO_POI, KHO_META], 'readwrite')
      tx.objectStore(KHO_POI).clear()
      const cursorRequest = tx.objectStore(KHO_META).openCursor()
      cursorRequest.onsuccess = () => {
        const cursor = cursorRequest.result
        if (!cursor) return
        const value = cursor.value as { khoa?: unknown }
        if (typeof value.khoa === 'string' && value.khoa.startsWith('cursor-')) {
          cursor.delete()
        }
        cursor.continue()
      }
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
      tx.onabort = () => reject(tx.error ?? new Error('Không thể xóa cache POI trong IndexedDB'))
    })
  } finally {
    db.close()
  }
}

// Chuỗi fallback offline: chọn → en → vi để không màn hình trống.
export async function docPoisFallback(lang: string): Promise<Poi[]> {
  for (const thu of [lang, 'en', 'vi']) {
    try {
      const ban = await docPois(thu)
      if (ban && ban.pois.length > 0) return ban.pois
    } catch {
      continue
    }
  }
  return []
}

export async function luuThucDonCongKhai(
  lang: string,
  menusByPoi: Record<string, PublicPoiMenu[]>,
): Promise<void> {
  const db = await moDb()
  try {
    await ghi(db, KHO_POI_MENUS, { lang, menusByPoi, saved_at: Date.now() })
  } finally {
    db.close()
  }
}

export async function docThucDonCongKhai(
  lang: string,
): Promise<Record<string, PublicPoiMenu[]> | null> {
  const db = await moDb()
  try {
    const record = await doc<PublicPoiMenusRecord>(db, KHO_POI_MENUS, lang)
    return record?.menusByPoi ?? null
  } finally {
    db.close()
  }
}

export async function luuCursor(lang: string, cursor: number): Promise<void> {
  const db = await moDb()
  await ghi(db, KHO_META, { khoa: `cursor-${lang}`, cursor })
  db.close()
}

export async function docCursor(lang: string): Promise<number> {
  const db = await moDb()
  const ban = await doc<{ cursor: number }>(db, KHO_META, `cursor-${lang}`)
  db.close()
  return ban?.cursor ?? 0
}

export async function luuUiBundle(
  locale: string,
  translations: Record<string, string>,
  version: string,
  namespace = 'public-ui',
): Promise<void> {
  const db = await moDb()
  try {
    await ghi(db, KHO_UI_BUNDLES, {
      id: `${locale}:${namespace}`,
      language_code: locale,
      namespace,
      version_code: version,
      translations,
    } satisfies UiBundleRecord)
  } finally {
    db.close()
  }
}

export async function docUiBundle(
  locale: string,
  namespace = 'public-ui',
): Promise<UiBundleRecord | null> {
  const db = await moDb()
  try {
    return await doc<UiBundleRecord>(db, KHO_UI_BUNDLES, `${locale}:${namespace}`)
  } finally {
    db.close()
  }
}

function khoaMapPack(scope: string, fingerprint: string): string {
  return `${scope}:${fingerprint}`
}

export async function luuMapPack(
  metadata: MapPackMetadata,
  assets: Record<string, ArrayBuffer>,
): Promise<void> {
  const db = await moDb()
  try {
    const blobs: Record<string, Blob> = {}
    for (const [file, data] of Object.entries(assets)) {
      blobs[file] = new Blob([data])
    }
    await ghi(db, KHO_MAP_PACKS, {
      id: khoaMapPack(metadata.scope, metadata.fingerprint),
      ...metadata,
      assets: blobs,
    } satisfies MapPackRecord)
  } finally {
    db.close()
  }
}

export async function kichHoatMapPack(metadata: MapPackMetadata): Promise<void> {
  const db = await moDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(KHO_META, 'readwrite')
      const store = tx.objectStore(KHO_META)
      store.put({
        khoa: `map-pack-${metadata.scope}`,
        fingerprint: metadata.fingerprint,
      })
      store.put({
        khoa: 'active-map-pack',
        scope: metadata.scope,
        fingerprint: metadata.fingerprint,
      })
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  } finally {
    db.close()
  }
}

export async function docMapPack(
  scope: string,
  fingerprint: string,
): Promise<(MapPackMetadata & { assets: Record<string, Blob> }) | null> {
  const db = await moDb()
  try {
    return await doc<MapPackRecord>(db, KHO_MAP_PACKS, khoaMapPack(scope, fingerprint))
  } finally {
    db.close()
  }
}

export async function docMapPackTheoScope(
  scope: string,
): Promise<(MapPackMetadata & { assets: Record<string, Blob> }) | null> {
  const db = await moDb()
  try {
    const index = await doc<{ fingerprint: string }>(db, KHO_META, `map-pack-${scope}`)
    return index === null
      ? null
      : await doc<MapPackRecord>(db, KHO_MAP_PACKS, khoaMapPack(scope, index.fingerprint))
  } finally {
    db.close()
  }
}

export async function docMapPackDangHoatDong(): Promise<
  (MapPackMetadata & { assets: Record<string, Blob> }) | null
> {
  const db = await moDb()
  try {
    const active = await doc<{ scope: string; fingerprint: string }>(
      db,
      KHO_META,
      'active-map-pack',
    )
    return active === null
      ? null
      : await doc<MapPackRecord>(
          db,
          KHO_MAP_PACKS,
          khoaMapPack(active.scope, active.fingerprint),
        )
  } finally {
    db.close()
  }
}

export async function xoaMapPack(scope: string, fingerprint: string): Promise<void> {
  const db = await moDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(KHO_MAP_PACKS, 'readwrite')
      tx.objectStore(KHO_MAP_PACKS).delete(khoaMapPack(scope, fingerprint))
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  } finally {
    db.close()
  }
}
