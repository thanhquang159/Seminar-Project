import { expect, test } from '@playwright/test'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const POIS = [
  {
    id: 'offline-poi-1',
    name: 'Quán ăn kiểm thử offline',
    description: 'Nội dung POI được lưu trong IndexedDB.',
    lat: 10.7569,
    lng: 106.7641,
    trigger_radius: 30,
    audio_priority: 0,
    lang: 'vi',
    is_fallback: false,
    audio_url: null,
    images: [],
  },
]

const PMTILES = (() => {
  const data = Buffer.alloc(133)
  data.write('PMTiles\u0003', 0, 'binary')
  data.writeBigUInt64LE(127n, 8)
  data.writeBigUInt64LE(5n, 16)
  data.writeBigUInt64LE(132n, 56)
  data.writeBigUInt64LE(1n, 64)
  data.writeBigUInt64LE(1n, 72)
  data.writeBigUInt64LE(1n, 80)
  data.writeBigUInt64LE(1n, 88)
  data[97] = 1
  data[98] = 1
  data[99] = 1
  data.set([1, 0, 1, 1, 1], 127)
  return data
})()

const STYLE_JSON = JSON.stringify({
  version: 8,
  name: 'Offline test',
  glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
  sources: {
    offline: {
      type: 'vector',
      url: 'pmtiles://http://127.0.0.1:8000/maps/pack/quan4/quan4.pmtiles',
    },
    boundary: {
      type: 'geojson',
      data: 'quan4-boundary.geojson',
    },
  },
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#fff' } }],
})
const GLYPH_PBF = Buffer.from([1, 2, 3, 4])
const BOUNDARY_GEOJSON = Buffer.from('{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}')

function taoMapFiles(styleJson: string) {
  return [
    {
      file: 'quan4/quan4.pmtiles',
      sha256: createHash('sha256').update(PMTILES).digest('hex'),
      bytes: PMTILES.byteLength,
    },
    {
      file: 'quan4/style.json',
      sha256: createHash('sha256').update(styleJson).digest('hex'),
      bytes: Buffer.byteLength(styleJson),
    },
    {
      file: 'quan4/quan4-boundary.geojson',
      sha256: createHash('sha256').update(BOUNDARY_GEOJSON).digest('hex'),
      bytes: BOUNDARY_GEOJSON.byteLength,
    },
    {
      file: 'quan4/fonts/Noto Sans Regular/0-255.pbf',
      sha256: createHash('sha256').update(GLYPH_PBF).digest('hex'),
      bytes: GLYPH_PBF.byteLength,
    },
  ]
}

const MAP_FILES = taoMapFiles(STYLE_JSON)
const UPDATED_STYLE_JSON = STYLE_JSON.replace('Offline test', 'Updated offline test')
const UPDATED_MAP_FILES = taoMapFiles(UPDATED_STYLE_JSON)

const REAL_MAP_DIR = fileURLToPath(new URL('../../backend/static/maps/quan4/', import.meta.url))
const REAL_MAP_ASSETS = [
  'quan4.pmtiles',
  'style.json',
  'quan4-boundary.geojson',
  'fonts/OFL.txt',
  'fonts/Noto Sans Regular/0-255.pbf',
  'fonts/Noto Sans Regular/256-511.pbf',
  'fonts/Noto Sans Regular/768-1023.pbf',
  'fonts/Noto Sans Regular/7680-7935.pbf',
].map((path) => ({
  file: `quan4/${path}`,
  content: readFileSync(join(REAL_MAP_DIR, path)),
}))
const REAL_MAP_FILES = REAL_MAP_ASSETS.map(({ file, content }) => ({
  file,
  sha256: createHash('sha256').update(content).digest('hex'),
  bytes: content.byteLength,
}))
const REAL_MAP_FINGERPRINT = createHash('sha256')
  .update(JSON.stringify(REAL_MAP_FILES))
  .digest('hex')

function installMapPackMocks(page: import('@playwright/test').Page, quotaExceeded = false) {
  return page.addInitScript(({ mapFiles, updatedMapFiles, styleJson, updatedStyleJson, pmtilesBase64, glyphPbfBase64, boundaryGeojsonBase64, quota }) => {
    localStorage.setItem('quan4-consent', 'revoked')

    const fetchThat = window.fetch.bind(window)
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const requestUrl = input instanceof Request ? input.url : String(input)
      const url = new URL(requestUrl, window.location.href)
      if (url.pathname === '/maps/offline-options') {
        return Response.json({ scopes: ['quan4'] })
      }
      if (url.pathname === '/maps/manifest') {
        localStorage.setItem('__map_pack_api_origin', url.origin)
        const isUpdated = localStorage.getItem('__map_pack_update') === 'true'
        return Response.json({
          scope: 'quan4',
          files: isUpdated ? updatedMapFiles : mapFiles,
          fingerprint: (isUpdated ? 'b' : 'a').repeat(64),
        })
      }
      if (url.pathname === '/maps/pack/quan4/quan4.pmtiles') {
        const bytes = Uint8Array.from(atob(pmtilesBase64), (char) => char.charCodeAt(0))
        return new Response(bytes)
      }
      if (url.pathname === '/maps/pack/quan4/style.json') {
        const content = localStorage.getItem('__map_pack_update') === 'true' ? updatedStyleJson : styleJson
        return new Response(content, { headers: { 'Content-Type': 'application/json' } })
      }
      if (decodeURIComponent(url.pathname) === '/maps/pack/quan4/fonts/Noto Sans Regular/0-255.pbf') {
        return new Response(Uint8Array.from(atob(glyphPbfBase64), (char) => char.charCodeAt(0)))
      }
      if (url.pathname === '/maps/pack/quan4/quan4-boundary.geojson') {
        return new Response(Uint8Array.from(atob(boundaryGeojsonBase64), (char) => char.charCodeAt(0)))
      }
      if (url.pathname === '/poi/load-all') {
        return Response.json({ version: 1, sync_cursor: 1, pois: [] })
      }
      if (url.pathname.startsWith('/ui-bundles/')) {
        return Response.json({ status: 'ready', bundle: { app_title: 'PWA test' } })
      }
      if (url.pathname === '/health') return Response.json({})
      return fetchThat(input, init)
    }

    if (quota) {
      const putThat = Cache.prototype.put
      Cache.prototype.put = function (request, response) {
        const requestUrl = typeof request === 'string' ? request : request.url
        if (
          localStorage.getItem('__map_pack_quota') === 'true' &&
          new URL(requestUrl, window.location.href).pathname.startsWith('/maps/pack/')
        ) {
          throw new DOMException('Storage quota exceeded', 'QuotaExceededError')
        }
        return putThat.call(this, request, response)
      }
    }
  }, {
    mapFiles: MAP_FILES,
    updatedMapFiles: UPDATED_MAP_FILES,
    styleJson: STYLE_JSON,
    updatedStyleJson: UPDATED_STYLE_JSON,
    pmtilesBase64: PMTILES.toString('base64'),
    glyphPbfBase64: GLYPH_PBF.toString('base64'),
    boundaryGeojsonBase64: BOUNDARY_GEOJSON.toString('base64'),
    quota: quotaExceeded,
  })
}

function installRealMapPackMocks(page: import('@playwright/test').Page) {
  const assets = Object.fromEntries(
    REAL_MAP_ASSETS.map(({ file, content }) => [file, content.toString('base64')]),
  )
  const styleJson = REAL_MAP_ASSETS.find(({ file }) => file === 'quan4/style.json')?.content.toString('utf8')
  if (styleJson === undefined) throw new Error('Thiếu style.json của map pack Quận 4')

  return page.addInitScript(({ files, fingerprint, assetContents, style }) => {
    localStorage.setItem('quan4-consent', 'revoked')
    localStorage.setItem('quan4-mapmode', 'offline')

    const cacheMatch = Cache.prototype.match
    Cache.prototype.match = function (request, options) {
      const requestUrl = typeof request === 'string' ? request : request.url
      const path = new URL(requestUrl, window.location.href).pathname
      const counter = path.endsWith('/quan4.pmtiles')
        ? '__q4_pmtiles_cache_reads'
        : path.endsWith('/quan4-boundary.geojson')
          ? '__q4_boundary_cache_reads'
          : path.endsWith('.pbf')
            ? '__q4_glyph_cache_reads'
            : null
      if (counter !== null) {
        const reads = Number(localStorage.getItem(counter) ?? '0')
        localStorage.setItem(counter, String(reads + 1))
      }
      return cacheMatch.call(this, request, options)
    }

    const fetchThat = window.fetch.bind(window)
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const requestUrl = input instanceof Request ? input.url : String(input)
      const url = new URL(requestUrl, window.location.href)
      if (url.pathname === '/maps/offline-options') {
        return Response.json({ scopes: ['quan4'] })
      }
      if (url.pathname === '/maps/manifest') {
        return Response.json({ scope: 'quan4', files, fingerprint })
      }
      if (url.pathname === '/maps/pack/quan4/style.json') {
        return new Response(style, { headers: { 'Content-Type': 'application/json' } })
      }
      const file = decodeURIComponent(url.pathname.replace('/maps/pack/', ''))
      const base64 = assetContents[file]
      if (base64 !== undefined) {
        const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
        return new Response(bytes)
      }
      if (url.pathname === '/poi/load-all') {
        return Response.json({ version: 1, sync_cursor: 1, pois: [] })
      }
      if (url.pathname.startsWith('/ui-bundles/')) {
        return Response.json({ status: 'ready', bundle: { app_title: 'PWA test' } })
      }
      if (url.pathname === '/health') return Response.json({})
      return fetchThat(input, init)
    }
  }, {
    files: REAL_MAP_FILES,
    fingerprint: REAL_MAP_FINGERPRINT,
    assetContents: assets,
    style: styleJson,
  })
}

test('production PWA mở lại được app shell và POI đã cache khi mất mạng', async ({ page, context }) => {
  await page.addInitScript((pois) => {
    if (localStorage.getItem('quan4-consent') === null) {
      localStorage.setItem('quan4-consent', 'revoked')
    }

    const fetchThat = window.fetch.bind(window)
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const requestUrl = input instanceof Request ? input.url : String(input)
      const url = new URL(requestUrl, window.location.href)
      const dangOffline = localStorage.getItem('__pwa_test_offline') === 'true'

      if (!dangOffline && url.pathname === '/poi/load-all') {
        return new Response(JSON.stringify({ version: 1, sync_cursor: 1, pois }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (!dangOffline && url.pathname.startsWith('/ui-bundles/')) {
        return new Response(JSON.stringify({ status: 'ready', bundle: { app_title: 'PWA test' } }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (!dangOffline && url.pathname === '/health') {
        return new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      return fetchThat(input, init)
    }
  }, POIS)

  await page.goto('/?tab=kham-pha')
  await expect(page.locator('.poi-btn')).toHaveCount(1)
  await expect(page.locator('.poi-btn')).toContainText('Quán ăn kiểm thử offline')

  await page.evaluate(async () => {
    await navigator.serviceWorker.ready
  })
  await page.reload()
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null)

  await page.evaluate(() => localStorage.setItem('__pwa_test_offline', 'true'))
  await context.setOffline(true)
  await page.reload()

  await expect(page.locator('.poi-btn')).toHaveCount(1)
  await page.locator('.poi-btn').click()
  await expect(page.getByRole('heading', { name: 'Quán ăn kiểm thử offline' }).last()).toBeVisible()

  await page.goto('/offline-poi-1')
  await expect(page).toHaveURL(/\/offline-poi-1$/)
  await expect(page.getByRole('heading', { name: 'Quán ăn kiểm thử offline' }).last()).toBeVisible()
})

test('hết quota khi tải map pack không xóa cache đang có', async ({ page }) => {
  await installMapPackMocks(page, true)
  await page.goto('/?tab=goi-offline')
  const taiPack = page.getByRole('button', { name: 'Tải về máy' })
  await expect(taiPack).toBeVisible()
  await taiPack.click()
  await expect(page.getByText('Cài xong pack quan4')).toBeVisible()
  const activeTruocKhiTai = await page.evaluate(async () => {
    const index = await caches.open('map-pack-index')
    const active = await index.match(`${window.location.origin}/__offline/map-packs/active`)
    return active ? active.json() : null
  })
  expect(activeTruocKhiTai).not.toBeNull()
  const cacheTruocKhiTai = await page.evaluate(() => caches.keys())
  await page.evaluate(() => {
    localStorage.setItem('__map_pack_update', 'true')
    localStorage.setItem('__map_pack_quota', 'true')
  })

  await page.getByRole('button', { name: 'Tải lại (Cài đè)' }).click()

  await expect(page.getByText(/Không đủ dung lượng để cài pack/)).toBeVisible()
  const cacheSauKhiTai = await page.evaluate(() => caches.keys())
  const activeSauKhiTai = await page.evaluate(async () => {
    const index = await caches.open('map-pack-index')
    const active = await index.match(`${window.location.origin}/__offline/map-packs/active`)
    return active ? active.json() : null
  })
  expect(cacheSauKhiTai).toEqual(expect.arrayContaining(cacheTruocKhiTai))
  expect(activeSauKhiTai).toMatchObject({
    cacheName: activeTruocKhiTai?.cacheName,
    fingerprint: activeTruocKhiTai?.fingerprint,
  })
  expect(cacheSauKhiTai).not.toContain(`map-pack-quan4-${'b'.repeat(64)}`)
})

test('map pack đã xác minh được lưu lại và khôi phục sau reload', async ({ page }) => {
  await installMapPackMocks(page)
  await page.goto('/?tab=goi-offline')
  await page.getByRole('button', { name: 'Tải về máy' }).click()
  await expect(page.getByText('Cài xong pack quan4')).toBeVisible()

  const packDaLuu = await page.evaluate(async () => {
    const index = await caches.open('map-pack-index')
    const activeResponse = await index.match(`${window.location.origin}/__offline/map-packs/active`)
    if (!activeResponse) return null
    const active = await activeResponse.json()
    const pack = await caches.open(active.cacheName)
    const styleResponse = await pack.match(active.styleUrl)
    if (!styleResponse) return null
    const style = await styleResponse.json()
    const apiOrigin = localStorage.getItem('__map_pack_api_origin')
    const glyphUrl = `${apiOrigin}/maps/pack/quan4/fonts/Noto%20Sans%20Regular/0-255.pbf`
    const boundaryUrl = `${apiOrigin}/maps/pack/quan4/quan4-boundary.geojson`
    return {
      scope: active.scope,
      cacheName: active.cacheName,
      sourceUrl: style.sources.offline.url,
      boundaryUrl: style.sources.boundary.data,
      glyphsUrl: style.glyphs,
      glyphCached: Boolean(await pack.match(glyphUrl)),
      boundaryCached: Boolean(await pack.match(boundaryUrl)),
      apiOrigin,
    }
  })
  expect(packDaLuu).not.toBeNull()
  expect(packDaLuu?.scope).toBe('quan4')
  expect(packDaLuu?.sourceUrl).toBe(`pmtiles://${packDaLuu?.apiOrigin}/maps/pack/quan4/quan4.pmtiles`)
  expect(packDaLuu?.boundaryUrl).toBe(`offlineasset://quan4/${'a'.repeat(64)}/quan4-boundary.geojson`)
  expect(packDaLuu?.glyphsUrl).toMatch(/^offlineasset:\/\/quan4\/a{64}\/fonts\/\{fontstack\}\/\{range\}\.pbf$/)
  expect(packDaLuu?.glyphCached).toBe(true)
  expect(packDaLuu?.boundaryCached).toBe(true)

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Quản lý Gói Offline' })).toBeVisible()
  const packSauReload = await page.evaluate(async () => {
    const index = await caches.open('map-pack-index')
    const active = await index.match(`${window.location.origin}/__offline/map-packs/active`)
    return active ? (await active.json()).cacheName : null
  })
  expect(packSauReload).toBe(packDaLuu?.cacheName)
})

test('bản đồ Quận 4 thực tế hiển thị sau khi tải pack và tải lại khi offline', async ({ page, context }) => {
  await context.grantPermissions(['geolocation'])
  await context.setGeolocation({ latitude: 10.760734, longitude: 106.704351 })
  await installRealMapPackMocks(page)
  await page.goto('/?tab=goi-offline')
  await page.getByRole('button', { name: 'Tải về máy' }).click()
  await expect(page.getByText('Cài xong pack quan4')).toBeVisible()
  const readsBeforeRender = await page.evaluate(() => ({
    pmtiles: Number(localStorage.getItem('__q4_pmtiles_cache_reads') ?? '0'),
    boundary: Number(localStorage.getItem('__q4_boundary_cache_reads') ?? '0'),
    glyphs: Number(localStorage.getItem('__q4_glyph_cache_reads') ?? '0'),
  }))

  await page.goto('/?tab=kham-pha')
  const canvas = page.locator('.maplibregl-canvas')
  await expect(canvas).toBeVisible()
  await expect(page.locator('.maplibregl-ctrl-attrib')).toContainText('OpenStreetMap contributors')
  await expect(page.locator('.maplibregl-ctrl-attrib')).not.toContainText('MapTiler')
  await expect.poll(() => page.evaluate(() =>
    Number(localStorage.getItem('__q4_pmtiles_cache_reads') ?? '0'),
  )).toBeGreaterThan(readsBeforeRender.pmtiles)
  await expect.poll(() => page.evaluate(() =>
    Number(localStorage.getItem('__q4_boundary_cache_reads') ?? '0'),
  )).toBeGreaterThan(readsBeforeRender.boundary)
  await expect.poll(() => page.evaluate(() =>
    Number(localStorage.getItem('__q4_glyph_cache_reads') ?? '0'),
  )).toBeGreaterThan(readsBeforeRender.glyphs)
  const readsAfterRender = await page.evaluate(() => ({
    pmtiles: Number(localStorage.getItem('__q4_pmtiles_cache_reads') ?? '0'),
    boundary: Number(localStorage.getItem('__q4_boundary_cache_reads') ?? '0'),
    glyphs: Number(localStorage.getItem('__q4_glyph_cache_reads') ?? '0'),
  }))
  expect(readsAfterRender.pmtiles).toBeGreaterThan(readsBeforeRender.pmtiles)
  expect(readsAfterRender.boundary).toBeGreaterThan(readsBeforeRender.boundary)
  expect(readsAfterRender.glyphs).toBeGreaterThan(readsBeforeRender.glyphs)

  const readsBeforeOfflineReload = await page.evaluate(() => ({
    pmtiles: Number(localStorage.getItem('__q4_pmtiles_cache_reads') ?? '0'),
    boundary: Number(localStorage.getItem('__q4_boundary_cache_reads') ?? '0'),
    glyphs: Number(localStorage.getItem('__q4_glyph_cache_reads') ?? '0'),
  }))
  await context.setOffline(true)
  await page.reload()
  await expect(page.locator('.maplibregl-ctrl-attrib')).toContainText('OpenStreetMap contributors')
  await expect(page.locator('.maplibregl-ctrl-attrib')).not.toContainText('MapTiler')
  await expect.poll(() => page.evaluate(() =>
    Number(localStorage.getItem('__q4_pmtiles_cache_reads') ?? '0'),
  )).toBeGreaterThan(readsBeforeOfflineReload.pmtiles)
  await expect.poll(() => page.evaluate(() =>
    Number(localStorage.getItem('__q4_boundary_cache_reads') ?? '0'),
  )).toBeGreaterThan(readsBeforeOfflineReload.boundary)
  await expect.poll(() => page.evaluate(() =>
    Number(localStorage.getItem('__q4_glyph_cache_reads') ?? '0'),
  )).toBeGreaterThan(readsBeforeOfflineReload.glyphs)
  await expect(page.locator('.map-view-card .notice--warn')).toHaveCount(0)
})
