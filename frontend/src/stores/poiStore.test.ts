import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Poi } from './poiStore'

const mocks = vi.hoisted(() => ({
  docPois: vi.fn(),
  dongBo: vi.fn(),
}))

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
