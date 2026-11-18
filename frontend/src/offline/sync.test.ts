import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Poi } from '../stores/poiStore'

const idb = vi.hoisted(() => ({
  docCursor: vi.fn(),
  docPois: vi.fn(),
  docPoisFallback: vi.fn(),
  luuCursor: vi.fn(),
  luuPois: vi.fn(),
  luuThucDonCongKhai: vi.fn(),
  xoaTatCaCachePois: vi.fn(),
}))

vi.mock('./idb', () => idb)

import { dongBo, gopDelta } from './sync'

const poi = (id: string, name: string): Poi => ({
  id, name, description: '', lat: 0, lng: 0, trigger_radius: 30, audio_priority: 0,
  lang: 'vi', is_fallback: false, audio_url: null,
})

beforeEach(() => {
  vi.resetAllMocks()
})

describe('gopDelta', () => {
  it('xóa theo removed, cập nhật theo id, giữ còn lại', () => {
    const cu = [poi('1', 'Mot'), poi('2', 'Hai'), poi('3', 'Ba')]
    const gop = gopDelta(cu, [poi('2', 'Hai-moi'), poi('4', 'Bon')], ['3'])
    const ten = new Map(gop.map((p) => [p.id, p.name]))
    expect(ten.get('1')).toBe('Mot')
    expect(ten.get('2')).toBe('Hai-moi')
    expect(ten.get('4')).toBe('Bon')
    expect(ten.has('3')).toBe(false)
  })

  it('delta rỗng thì giữ nguyên', () => {
    const cu = [poi('1', 'Mot')]
    expect(gopDelta(cu, [], [])).toEqual(cu)
  })
})

describe('dongBo', () => {
  it('thay cache cũ bằng snapshot đầy đủ khi khởi động online', async () => {
    const snapshot = [poi('db-1', 'POI từ PostgreSQL')]
    idb.docCursor.mockResolvedValue(100)
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ version: 50, sync_cursor: 50, pois: snapshot }), {
        status: 200,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await dongBo('vi', true)

    expect(result).toEqual({ pois: snapshot, tuMang: true })
    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock.mock.calls[0][0]).toContain('/poi/load-all?lang=vi')
    expect(idb.luuPois).toHaveBeenCalledWith('vi', snapshot, 50)
    expect(idb.luuCursor).toHaveBeenCalledWith('vi', 50)
  })

  it('vẫn trả POI online khi IndexedDB không ghi được cache', async () => {
    const snapshot = [poi('db-1', 'POI từ PostgreSQL')]
    idb.luuPois.mockRejectedValue(new Error('IndexedDB unavailable'))
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ version: 50, sync_cursor: 50, pois: snapshot }), {
        status: 200,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    const result = await dongBo('vi', true)

    expect(result).toEqual({ pois: snapshot, tuMang: true })
    expect(idb.luuPois).toHaveBeenCalledWith('vi', snapshot, 50)
  })

  it('báo rõ lỗi API khi không có cache ngoại tuyến', async () => {
    idb.docPoisFallback.mockResolvedValue([])
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(dongBo('vi', true)).rejects.toThrow(
      'Không thể tải POI từ máy chủ và không có cache ngoại tuyến. Failed to fetch',
    )
  })

  it('tải lại toàn bộ khi cursor offline mới hơn server', async () => {
    const snapshot = [poi('db-1', 'POI từ PostgreSQL')]
    idb.docCursor.mockResolvedValue(200)
    idb.docPois.mockResolvedValue({ pois: [poi('stale-1', 'POI cũ')], version: 200 })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ count: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response('{}', { status: 400 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ version: 50, sync_cursor: 50, pois: snapshot }), {
          status: 200,
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const result = await dongBo('vi')

    expect(result).toEqual({ pois: snapshot, tuMang: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[0][0]).toContain('/poi/count')
    expect(fetchMock.mock.calls[1][0]).toContain('/poi/delta?')
    expect(fetchMock.mock.calls[2][0]).toContain('/poi/load-all?lang=vi')
    expect(idb.luuPois).toHaveBeenCalledWith('vi', snapshot, 50)
  })

  it('xóa toàn bộ cache POI khi số lượng trên máy chủ thay đổi rồi tải snapshot mới', async () => {
    const snapshot = [poi('db-1', 'POI mới 1'), poi('db-2', 'POI mới 2'), poi('db-3', 'POI mới 3')]
    idb.docPois.mockResolvedValue({
      pois: [poi('old-1', 'POI cũ 1'), poi('old-2', 'POI cũ 2')],
      version: 10,
    })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ count: 3 }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ version: 20, sync_cursor: 20, pois: snapshot }), {
          status: 200,
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const result = await dongBo('vi')

    expect(result).toEqual({ pois: snapshot, tuMang: true })
    expect(idb.xoaTatCaCachePois).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][0]).toContain('/poi/load-all?lang=vi')
    expect(idb.luuPois).toHaveBeenCalledWith('vi', snapshot, 20)
  })

  it('không xóa cache khi số lượng POI không thay đổi', async () => {
    const cached = [poi('db-1', 'POI hiện có')]
    idb.docPois.mockResolvedValue({ pois: cached, version: 20 })
    idb.docCursor.mockResolvedValue(20)
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ count: 1 }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ version: 20, sync_cursor: 20, updated: [], removed_poi_ids: [] }),
          { status: 200 },
        ),
      ))

    const result = await dongBo('vi')

    expect(result).toEqual({ pois: cached, tuMang: true })
    expect(idb.xoaTatCaCachePois).not.toHaveBeenCalled()
  })
})

describe('taiThucDonNgoaiTuyen', () => {
  it('nhóm thực đơn theo POI và lưu theo ngôn ngữ đã chọn', async () => {
    const menus = [
      { id: 'm1', poi_id: 'p1', name: 'Menu 1', description: null, items: [] },
      { id: 'm2', poi_id: 'p1', name: 'Menu 2', description: null, items: [] },
      { id: 'm3', poi_id: 'p2', name: 'Menu 3', description: null, items: [] },
    ]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify(menus), { status: 200 }),
    ))

    const { taiThucDonNgoaiTuyen } = await import('./sync')
    await expect(taiThucDonNgoaiTuyen('ja')).resolves.toBe(3)

    expect(idb.luuThucDonCongKhai).toHaveBeenCalledWith('ja', {
      p1: menus.slice(0, 2),
      p2: menus.slice(2),
    })
  })
})
