import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Poi } from './poiStore'

const mocks = vi.hoisted(() => ({
  docPois: vi.fn(),
  dongBo: vi.fn(),
  stopPlayback: vi.fn(),
}))

vi.mock('../audio/playback', () => ({ stopPlayback: mocks.stopPlayback }))
vi.mock('../offline/idb', () => ({ docPois: mocks.docPois }))
vi.mock('../offline/sync', () => ({ dongBo: mocks.dongBo }))

import { usePoiStore } from './poiStore'

const poi = (name: string): Poi => ({
  id: name,
  name,
  description: '',
  lat: 0,
  lng: 0,
  trigger_radius: 30,
  audio_priority: 0,
  lang: 'en',
  is_fallback: false,
  audio_url: null,
})

beforeEach(() => {
  vi.resetAllMocks()
  usePoiStore.setState({
    pois: [],
    loading: false,
    daTaiDuLieu: false,
    error: '',
    lang: 'en',
  })
})

describe('POI IndexedDB startup', () => {
  it('không nháy bản EN từ cache VI cũ khi đang đồng bộ', async () => {
    const fixed = [{ ...poi('Ốc Tô'), lang: 'vi' }]
    usePoiStore.setState({ lang: 'vi' })
    mocks.docPois.mockResolvedValue({ pois: [{ ...poi('Snail Bowl'), is_fallback: true }], version: 10 })
    mocks.dongBo.mockImplementation(async () => {
      expect(usePoiStore.getState().pois).toEqual([])
      return { pois: fixed, tuMang: true }
    })
    await usePoiStore.getState().fetchPOIs()
    expect(usePoiStore.getState().pois).toEqual(fixed)
  })

  it('đổi ngôn ngữ dừng audio, bỏ nội dung cũ và không nhận response EN đến muộn', async () => {
    let complete: (value: { pois: Poi[]; tuMang: boolean }) => void = () => {}
    mocks.docPois.mockResolvedValue(null)
    mocks.dongBo.mockImplementationOnce(() => new Promise((resolve) => { complete = resolve }))
      .mockResolvedValueOnce({ pois: [{ ...poi('Ốc Tô'), lang: 'vi' }], tuMang: true })
    const oldRequest = usePoiStore.getState().fetchPOIs()
    await Promise.resolve()
    usePoiStore.getState().setLang('vi')
    expect(mocks.stopPlayback).toHaveBeenCalledOnce()
    expect(usePoiStore.getState().pois).toEqual([])
    await Promise.resolve()
    await Promise.resolve()
    complete({ pois: [poi('Snail Bowl')], tuMang: true })
    await oldRequest
    expect(usePoiStore.getState().lang).toBe('vi')
    expect(usePoiStore.getState().pois[0].name).toBe('Ốc Tô')
  })

  it('shows the saved POIs before applying the online sync result', async () => {
    const cached = [poi('cached')]
    const refreshed = [poi('refreshed')]
    mocks.docPois.mockResolvedValue({ pois: cached, version: 10 })
    mocks.dongBo.mockImplementation(async () => {
      expect(usePoiStore.getState().pois).toEqual(cached)
      return { pois: refreshed, tuMang: true }
    })

    await usePoiStore.getState().fetchPOIs()

    expect(mocks.dongBo).toHaveBeenCalledWith('en', false)
    expect(usePoiStore.getState().pois).toEqual(refreshed)
    expect(usePoiStore.getState().loading).toBe(false)
  })
})
