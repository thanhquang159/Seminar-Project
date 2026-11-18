import { useEffect, useRef, useState } from 'react'
import type { StyleSpecification } from 'maplibre-gl'
import type { Protocol } from 'pmtiles'
import { API_BASE_URL } from '../config'
import {
  docMapPack,
  docMapPackDangHoatDong,
  docMapPackTheoScope,
  kichHoatMapPack,
  luuMapPack,
  xoaMapPack,
  type MapPackMetadata,
} from '../offline/idb'

const API_GOC = API_BASE_URL
const CACHE_CHI_MUC = 'map-pack-index'
const CACHE_CHI_MUC_URL = `${window.location.origin}/__offline/map-packs`

export type CheDo = 'cloud' | 'offline' | 'hybrid'

// Đăng ký giao thức một lần, tile đi qua fetch nên SW cache phục vụ offline.
// Import động để không kéo MapLibre vào chunk chính.
let dangKyPmtiles: Promise<void> | null = null
let pmtilesProtocol: Protocol | null = null
let PMTilesClass: typeof import('pmtiles').PMTiles | null = null
async function damBaoPmtiles() {
  if (dangKyPmtiles === null) {
    dangKyPmtiles = Promise.all([import('maplibre-gl'), import('pmtiles')]).then(
      ([{ addProtocol }, pmtiles]) => {
        pmtilesProtocol = new pmtiles.Protocol()
        PMTilesClass = pmtiles.PMTiles
        addProtocol('pmtiles', pmtilesProtocol.tile)
        addProtocol('offlineasset', async (request, abortController) => {
          const parsed = new URL(request.url)
          const scope = parsed.hostname
          const [fingerprint, ...segments] = parsed.pathname
            .split('/')
            .filter(Boolean)
            .map(decodeURIComponent)
          if (
            !['quan4', 'hcm'].includes(scope) ||
            fingerprint === undefined ||
            !/^[a-f0-9]{64}$/i.test(fingerprint) ||
            segments.length === 0
          ) {
            throw new Error(`Đường dẫn tài nguyên offline không hợp lệ: ${request.url}`)
          }

          const tep = `${scope}/${segments.join('/')}`
          const asset = await docTaiSanPack(scope, fingerprint, tep)
          if (asset !== null) {
            if (abortController.signal.aborted) {
              throw new DOMException('Tải tài nguyên offline đã bị hủy', 'AbortError')
            }
            if (request.type === 'json') {
              return { data: JSON.parse(await asset.text()) }
            }
            if (request.type === 'string') {
              return { data: await asset.text() }
            }
            return { data: await asset.arrayBuffer() }
          }
          const cache = await caches.open(`map-pack-${scope}-${fingerprint}`)
          const cached = await cache.match(urlTepPack(scope, tep))
          if (cached === undefined) {
            throw new Error(`Thiếu tài nguyên offline trong pack: ${tep}`)
          }
          if (abortController.signal.aborted) {
            throw new DOMException('Tải tài nguyên offline đã bị hủy', 'AbortError')
          }
          if (request.type === 'json') return { data: await cached.json() }
          if (request.type === 'string') return { data: await cached.text() }
          return { data: await cached.arrayBuffer() }
        })
      },
    )
  }
  await dangKyPmtiles
}

export interface TepPack {
  file: string
  sha256: string
  bytes: number
}

interface ManifestPack {
  files: TepPack[]
  fingerprint: string
}

type BanGhiPack = MapPackMetadata

interface GoiMapPack extends BanGhiPack {
  assets: Record<string, Blob>
}

// Hysteresis: vào offline ngay khi mất mạng, về cloud trễ để chống nhấp nháy.
const TRE_VE_CLOUD_MS = 10000

async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', buf)
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function laDoiTuong(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function laManifestPack(value: unknown): value is ManifestPack {
  if (!laDoiTuong(value) || typeof value.fingerprint !== 'string' || !/^[a-f0-9]{64}$/i.test(value.fingerprint)) {
    return false
  }
  return Array.isArray(value.files) && value.files.every((tep: unknown) =>
    laDoiTuong(tep) &&
    typeof tep.file === 'string' &&
    /^[a-f0-9]{64}$/i.test(String(tep.sha256)) &&
    Number.isSafeInteger(tep.bytes) &&
    (tep.bytes as number) > 0,
  )
}

function urlTepPack(scope: string, file: string): string {
  const phan = file.split('/')
  if (
    phan.length < 2 ||
    phan[0] !== scope ||
    phan.some((muc) => muc === '' || muc === '.' || muc === '..')
  ) {
    throw new Error(`Đường dẫn tệp pack không hợp lệ: ${file}`)
  }
  return `${API_GOC}/maps/pack/${phan.map(encodeURIComponent).join('/')}`
}

async function docGoiMapPack(scope: string, fingerprint: string): Promise<GoiMapPack | null> {
  try {
    return await docMapPack(scope, fingerprint)
  } catch (error) {
    console.warn('Không đọc được gói bản đồ trong IndexedDB:', error)
    return null
  }
}

async function docTaiSanPack(
  scope: string,
  fingerprint: string,
  file: string,
): Promise<Blob | null> {
  const pack = await docGoiMapPack(scope, fingerprint)
  const asset = pack?.assets[file]
  return asset ?? null
}

async function docResponsePack(ghi: BanGhiPack, file: string): Promise<Response | undefined> {
  const asset = await docTaiSanPack(ghi.scope, ghi.fingerprint, file)
  if (asset !== null) return new Response(asset)
  const cache = await caches.open(ghi.cacheName)
  return cache.match(urlTepPack(ghi.scope, file))
}

async function damBaoPackTrongIDB(ghi: BanGhiPack): Promise<void> {
  if ((await docGoiMapPack(ghi.scope, ghi.fingerprint)) !== null) return
  const assets: Record<string, ArrayBuffer> = {}
  for (const tep of ghi.files) {
    const response = await docResponsePack(ghi, tep.file)
    if (response === undefined) {
      throw new Error(`Thiếu tệp ${tep.file} trong pack; cần tải lại gói bản đồ`)
    }
    assets[tep.file] = await response.arrayBuffer()
  }
  await luuMapPack(ghi, assets)
}

function pmtilesCoDuLieu(buf: ArrayBuffer): boolean {
  if (buf.byteLength < 128) return false
  const data = new Uint8Array(buf)
  if (new TextDecoder().decode(data.subarray(0, 8)) !== 'PMTiles\u0003') return false

  const view = new DataView(buf)
  const rootOffset = view.getBigUint64(8, true)
  const rootLength = view.getBigUint64(16, true)
  if (
    rootOffset < 127n ||
    rootLength === 0n ||
    rootOffset + rootLength > BigInt(buf.byteLength) ||
    view.getBigUint64(72, true) === 0n ||
    view.getBigUint64(80, true) === 0n ||
    view.getBigUint64(88, true) === 0n
  ) {
    return false
  }

  let soMuc = 0n
  let shift = 0n
  const batDau = Number(rootOffset)
  for (let i = batDau; i < Math.min(buf.byteLength, batDau + Number(rootLength)) && shift < 70n; i += 1) {
    const byte = data[i]
    soMuc |= BigInt(byte & 0x7f) << shift
    if (byte < 0x80) return soMuc > 0n
    shift += 7n
  }
  return false
}

function taoStyleDaChuanHoa(
  value: unknown,
  scope: string,
  fingerprint: string,
  files: TepPack[],
): StyleSpecification {
  if (
    !laDoiTuong(value) ||
    value.version !== 8 ||
    !laDoiTuong(value.sources) ||
    !Array.isArray(value.layers)
  ) {
    throw new Error('style.json không đúng định dạng MapLibre')
  }

  const style = value as unknown as StyleSpecification
  const filesPmtiles = files.filter((tep) => tep.file.endsWith('.pmtiles'))
  let daChuanHoaNguon = false

  for (const source of Object.values(value.sources)) {
    if (!laDoiTuong(source)) continue
    if (source.type === 'vector' && typeof source.url === 'string' && source.url.startsWith('pmtiles://')) {
      const urlGoc = new URL(source.url.slice('pmtiles://'.length), API_GOC)
      const tenTep = decodeURIComponent(urlGoc.pathname.split('/').pop() ?? '')
      const tep = filesPmtiles.find((candidate) => candidate.file.split('/').pop() === tenTep)
        ?? (filesPmtiles.length === 1 ? filesPmtiles[0] : undefined)
      if (tep === undefined) {
        throw new Error(`style.json tham chiếu PMTiles không có trong manifest: ${tenTep}`)
      }
      source.url = `pmtiles://${urlTepPack(scope, tep.file)}`
      daChuanHoaNguon = true
    }

    if (source.type === 'geojson' && typeof source.data === 'string') {
      const urlGoc = new URL(source.data, API_GOC)
      const tenTep = decodeURIComponent(urlGoc.pathname.split('/').pop() ?? '')
      const tep = files.find((candidate) => candidate.file.endsWith(`/${tenTep}`) && candidate.file.endsWith('.geojson'))
      if (tep === undefined) {
        throw new Error(`style.json tham chiếu GeoJSON không có trong manifest: ${tenTep}`)
      }
      source.data = `offlineasset://${scope}/${fingerprint}/${tep.file.slice(scope.length + 1)}`
    }
  }

  if (!daChuanHoaNguon) {
    throw new Error('style.json không có nguồn PMTiles để dùng offline')
  }
  if (typeof value.glyphs === 'string') {
    if (!files.some((tep) => tep.file.startsWith(`${scope}/fonts/`) && tep.file.endsWith('.pbf'))) {
      throw new Error('style.json cần glyphs nhưng manifest không có font PBF ngoại tuyến')
    }
    style.glyphs = `offlineasset://${scope}/${fingerprint}/fonts/{fontstack}/{range}.pbf`
  }
  return style
}

function laBanGhiPack(value: unknown, scope?: string): value is BanGhiPack {
  return (
    laDoiTuong(value) &&
    typeof value.scope === 'string' &&
    (scope === undefined || value.scope === scope) &&
    typeof value.cacheName === 'string' &&
    value.cacheName === `map-pack-${value.scope}-${String(value.fingerprint)}` &&
    typeof value.fingerprint === 'string' &&
    /^[a-f0-9]{64}$/i.test(value.fingerprint) &&
    typeof value.styleUrl === 'string' &&
    Array.isArray(value.files) &&
    value.files.every((tep) => laManifestPack({ fingerprint: value.fingerprint, files: [tep] }))
  )
}

function urlChiMuc(scope: string): string {
  return `${CACHE_CHI_MUC_URL}/${encodeURIComponent(scope)}`
}

function urlPackDangHoatDong(): string {
  return `${CACHE_CHI_MUC_URL}/active`
}

function laQuotaExceeded(error: unknown): boolean {
  return laDoiTuong(error) && error.name === 'QuotaExceededError'
}

function thongBaoLoi(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

async function dangKyNguonPMTiles(ghi: BanGhiPack): Promise<void> {
  await damBaoPmtiles()
  if (pmtilesProtocol === null || PMTilesClass === null) {
    throw new Error('Không khởi tạo được giao thức PMTiles')
  }

  for (const tep of ghi.files.filter((file) => file.file.endsWith('.pmtiles'))) {
    const url = urlTepPack(ghi.scope, tep.file)
    const source = {
      getKey: () => url,
      getBytes: async (offset: number, length: number, signal?: AbortSignal) => {
        const asset = await docTaiSanPack(ghi.scope, ghi.fingerprint, tep.file)
        if (asset !== null) {
          if (signal?.aborted) {
            throw new DOMException('Tải tài nguyên offline đã bị hủy', 'AbortError')
          }
          return { data: await asset.slice(offset, offset + length).arrayBuffer() }
        }
        const cache = await caches.open(ghi.cacheName)
        const cached = await cache.match(url)
        if (cached !== undefined) {
          const blob = await cached.blob()
          return { data: await blob.slice(offset, offset + length).arrayBuffer() }
        }

        const response = await fetch(url, {
          headers: { Range: `bytes=${offset}-${offset + length - 1}` },
          signal,
        })
        if (!response.ok) throw new Error(`Đọc PMTiles thất bại: HTTP ${response.status}`)
        const data = await response.arrayBuffer()
        return {
          data: response.status === 200
            ? data.slice(offset, offset + length)
            : data,
        }
      },
    }
    const archive = new PMTilesClass(source)
    pmtilesProtocol.add(archive)
    const header = await archive.getHeader()
    if (header.numAddressedTiles === 0 || header.numTileEntries === 0 || header.numTileContents === 0) {
      throw new Error(`Tệp ${tep.file} không chứa tile bản đồ`)
    }
  }
}

async function docBanGhiPack(scope: string): Promise<BanGhiPack | null> {
  try {
    const saved = await docMapPackTheoScope(scope)
    if (saved !== null) return saved
  } catch (error) {
    console.warn('Không đọc được chỉ mục gói bản đồ trong IndexedDB:', error)
  }
  const index = await caches.open(CACHE_CHI_MUC)
  const response = await index.match(urlChiMuc(scope))
  if (response === undefined) return null
  const raw: unknown = await response.json()
  return laBanGhiPack(raw, scope) ? raw : null
}

async function kichHoatBanGhiPack(ghi: BanGhiPack): Promise<StyleSpecification> {
  const styleFile = ghi.files.find((tep) => urlTepPack(ghi.scope, tep.file) === ghi.styleUrl)
  if (styleFile === undefined) throw new Error('Pack thiếu style.json')
  const styleResponse = await docResponsePack(ghi, styleFile.file)
  if (styleResponse === undefined) {
    throw new Error('Thiếu style.json trong pack; cần tải lại gói bản đồ')
  }
  for (const tep of ghi.files) {
    if (!(await docResponsePack(ghi, tep.file))) {
      throw new Error(`Thiếu tệp ${tep.file} trong pack; cần tải lại gói bản đồ`)
    }
  }
  const style = await styleResponse.json()
  const normalizedStyle = taoStyleDaChuanHoa(
    style,
    ghi.scope,
    ghi.fingerprint,
    ghi.files,
  )
  await dangKyNguonPMTiles(ghi)
  return normalizedStyle
}

export function useMapPack() {
  const [cheDo, setCheDoState] = useState<CheDo>(() => {
    try {
      const saved = localStorage.getItem('quan4-mapmode')
      if (saved === 'cloud' || saved === 'offline' || saved === 'hybrid') return saved
    } catch {
      // fallback
    }
    return 'hybrid'
  })

  const setCheDo = (c: CheDo) => {
    try {
      localStorage.setItem('quan4-mapmode', c)
    } catch {
      // fallback
    }
    setCheDoState(c)
  }

  const [stylePack, setStylePack] = useState<StyleSpecification | null>(null)
  const [trangThai, setTrangThai] = useState('')
  const henGio = useRef(0)
  const dangTaiRef = useRef(false)

  useEffect(() => {
    let huy = false
    const phucHoi = async () => {
      let ghi: BanGhiPack | null = null
      try {
        ghi = await docMapPackDangHoatDong()
      } catch (error) {
        console.warn('Không đọc được gói bản đồ đang dùng trong IndexedDB:', error)
      }

      if (ghi === null) {
        const index = await caches.open(CACHE_CHI_MUC)
        const activeResponse = await index.match(urlPackDangHoatDong())
        if (activeResponse !== undefined) {
          const raw: unknown = await activeResponse.json()
          if (!laBanGhiPack(raw)) {
            setTrangThai('Thông tin pack đã lưu không hợp lệ; cần tải lại gói bản đồ')
            return
          }
          ghi = raw
        }
      }

      if (ghi === null) {
        try {
          ghi = await docMapPackTheoScope('quan4')
        } catch (error) {
          console.warn('Không đọc được gói Quận 4 trong IndexedDB:', error)
        }
      }

      if (ghi === null) {
        if (navigator.onLine) await taiPack('quan4')
        return
      }

      if (!laBanGhiPack(ghi)) {
        setTrangThai('Thông tin pack đã lưu không hợp lệ; cần tải lại gói bản đồ')
        return
      }

      await damBaoPackTrongIDB(ghi)
      const style = await kichHoatBanGhiPack(ghi)
      if (huy) return
      await kichHoatMapPack(ghi)
      setStylePack(style)
    }
    void phucHoi().catch((error: unknown) => {
      if (!huy) setTrangThai(`Không khôi phục được map pack: ${thongBaoLoi(error)}`)
    })
    return () => {
      huy = true
    }
  }, [])

  async function taiPack(scope: string, thayThe = false) {
    if (dangTaiRef.current) {
      setTrangThai('Đang có một gói bản đồ khác được tải')
      return
    }
    dangTaiRef.current = true
    let cacheName: string | null = null
    let cacheLaPackDangHoatDong = false
    let daLuuBanGhiPack = false
    let daLuuTrongIDB = false
    let daKichHoatTrongIDB = false
    let fingerprintDaLuu: string | null = null

    try {
      setTrangThai('Đang tải manifest...')
      const response = await fetch(`${API_GOC}/maps/manifest?scope=${encodeURIComponent(scope)}`)
      if (!response.ok) throw new Error(`Tải manifest thất bại: HTTP ${response.status}`)
      const raw: unknown = await response.json()
      if (!laManifestPack(raw)) throw new Error('Manifest gói bản đồ không hợp lệ')
      const manifest = raw
      fingerprintDaLuu = manifest.fingerprint
      const filesPmtiles = manifest.files.filter((tep) => tep.file.endsWith('.pmtiles'))
      const filesStyle = manifest.files.filter((tep) => tep.file.endsWith('/style.json'))
      if (filesPmtiles.length === 0 || filesStyle.length === 0) {
        throw new Error('Gói cần có ít nhất một PMTiles và style.json')
      }

      const index = await caches.open(CACHE_CHI_MUC)
      const banGhiCu = await docBanGhiPack(scope)
      const packDaLuu = await docGoiMapPack(scope, manifest.fingerprint)
      const banGhiDangHoatDongResponse = await index.match(urlPackDangHoatDong())
      const rawDangHoatDong: unknown = banGhiDangHoatDongResponse === undefined
        ? null
        : await banGhiDangHoatDongResponse.json()
      cacheLaPackDangHoatDong =
        laBanGhiPack(rawDangHoatDong) &&
        rawDangHoatDong.scope === scope &&
        rawDangHoatDong.fingerprint === manifest.fingerprint

      if (!thayThe && banGhiCu?.fingerprint === manifest.fingerprint) {
        await damBaoPackTrongIDB(banGhiCu)
        const style = await kichHoatBanGhiPack(banGhiCu)
        await kichHoatMapPack(banGhiCu)
        daKichHoatTrongIDB = true
        const responseIndex = new Response(JSON.stringify(banGhiCu), {
          headers: { 'Content-Type': 'application/json' },
        })
        await index.put(urlPackDangHoatDong(), responseIndex)
        setStylePack(style)
        setTrangThai('Đã có pack, dùng luôn')
        return
      }

      cacheName = `map-pack-${scope}-${manifest.fingerprint}`
      const cache = await caches.open(cacheName)
      const assets: Record<string, ArrayBuffer> = {}
      let styleUrl: string | null = null

      for (const tep of manifest.files) {
        const url = urlTepPack(scope, tep.file)
        let buf: ArrayBuffer | null = null
        const fromIdb = packDaLuu?.assets[tep.file]
        const fromIdbBuffer = fromIdb === undefined ? null : await fromIdb.arrayBuffer()
        if (
          fromIdbBuffer !== null &&
          fromIdbBuffer.byteLength === tep.bytes &&
          (await sha256Hex(fromIdbBuffer)) === tep.sha256
        ) {
          buf = fromIdbBuffer
        } else if (fromIdbBuffer !== null) {
          console.warn(`Tệp ${tep.file} trong IndexedDB sai kích thước hoặc SHA-256`)
        }

        const cached = buf === null ? await cache.match(url) : undefined
        if (buf === null && cached !== undefined) {
          const cachedBuffer = await cached.arrayBuffer()
          if (cachedBuffer.byteLength === tep.bytes && (await sha256Hex(cachedBuffer)) === tep.sha256) {
            buf = cachedBuffer
          } else {
            await cache.delete(url)
          }
        }

        if (buf === null) {
          setTrangThai(`Đang tải ${tep.file}...`)
          const fileResponse = await fetch(`${url}?pack=${encodeURIComponent(manifest.fingerprint)}`)
          if (!fileResponse.ok) throw new Error(`Tải ${tep.file} thất bại: HTTP ${fileResponse.status}`)
          buf = await fileResponse.arrayBuffer()
          if (buf.byteLength !== tep.bytes || (await sha256Hex(buf)) !== tep.sha256) {
            throw new Error(`Tệp ${tep.file} sai kích thước hoặc SHA-256; gói chưa được kích hoạt`)
          }
          if (tep.file.endsWith('.pmtiles') && !pmtilesCoDuLieu(buf)) {
            throw new Error(`Tệp ${tep.file} không chứa dữ liệu PMTiles hợp lệ`)
          }
          await cache.put(url, new Response(buf))
        } else if (tep.file.endsWith('.pmtiles') && !pmtilesCoDuLieu(buf)) {
          throw new Error(`Tệp ${tep.file} không chứa dữ liệu PMTiles hợp lệ`)
        }

        if (tep.file.endsWith('.json')) {
          const style = taoStyleDaChuanHoa(
            JSON.parse(new TextDecoder().decode(buf)),
            scope,
            manifest.fingerprint,
            manifest.files,
          )
          await cache.put(url, new Response(JSON.stringify(style), {
            headers: { 'Content-Type': 'application/json' },
          }))
          styleUrl = url
        }
        assets[tep.file] = buf
      }

      if (styleUrl === null) throw new Error('Pack thiếu style.json')
      const ghiMoi: BanGhiPack = {
        scope,
        cacheName,
        fingerprint: manifest.fingerprint,
        styleUrl,
        files: manifest.files,
      }
      await luuMapPack(ghiMoi, assets)
      daLuuTrongIDB = true
      const style = await kichHoatBanGhiPack(ghiMoi)

      await kichHoatMapPack(ghiMoi)
      daKichHoatTrongIDB = true
      await index.put(urlChiMuc(scope), new Response(JSON.stringify(ghiMoi), {
        headers: { 'Content-Type': 'application/json' },
      }))
      daLuuBanGhiPack = true
      await index.put(urlPackDangHoatDong(), new Response(JSON.stringify(ghiMoi), {
        headers: { 'Content-Type': 'application/json' },
      }))
      setStylePack(style)

      if (banGhiCu !== null && banGhiCu.cacheName !== cacheName) {
        await caches.delete(banGhiCu.cacheName)
        await xoaMapPack(banGhiCu.scope, banGhiCu.fingerprint)
      }
      await caches.delete(`map-pack-${scope}`)
      setTrangThai(`Cài xong pack ${scope}`)
    } catch (error) {
      if (daLuuTrongIDB && !daKichHoatTrongIDB) {
        try {
          if (fingerprintDaLuu !== null) await xoaMapPack(scope, fingerprintDaLuu)
        } catch (cleanupError) {
          console.warn('Không dọn được gói bản đồ lỗi trong IndexedDB:', cleanupError)
        }
      }
      if (cacheName !== null && !cacheLaPackDangHoatDong && !daLuuBanGhiPack) {
        await caches.delete(cacheName)
      }
      setTrangThai(
        laQuotaExceeded(error)
          ? 'Không đủ dung lượng để cài pack. Pack đang dùng và dữ liệu ngoại tuyến được giữ nguyên; hãy giải phóng dung lượng rồi thử lại.'
          : `Không cài được pack: ${thongBaoLoi(error)}`,
      )
    } finally {
      dangTaiRef.current = false
    }
  }

  useEffect(() => {
    const taiKhiCoMang = () => {
      if (stylePack === null && !dangTaiRef.current) void taiPack('quan4')
    }
    window.addEventListener('online', taiKhiCoMang)
    return () => window.removeEventListener('online', taiKhiCoMang)
  }, [stylePack])

  // Hybrid: rớt mạng thì giữ pack, có mạng lại thì chờ 10s mới về cloud.
  const [tamOffline, setTamOffline] = useState(false)
  useEffect(() => {
    if (cheDo !== 'hybrid') return
    const capNhat = () => {
      if (!navigator.onLine) {
        window.clearTimeout(henGio.current)
        setTamOffline(true)
      } else {
        window.clearTimeout(henGio.current)
        henGio.current = window.setTimeout(() => setTamOffline(false), TRE_VE_CLOUD_MS)
      }
    }
    window.addEventListener('online', capNhat)
    window.addEventListener('offline', capNhat)
    return () => {
      window.removeEventListener('online', capNhat)
      window.removeEventListener('offline', capNhat)
    }
  }, [cheDo])

  useEffect(() => () => window.clearTimeout(henGio.current), [])

  return { cheDo, setCheDo, stylePack, tamOffline, trangThai, taiPack }
}

export type PackHook = ReturnType<typeof useMapPack>
