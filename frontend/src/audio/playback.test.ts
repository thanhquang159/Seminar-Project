import { beforeEach, describe, expect, it, vi } from 'vitest'

const { speak } = vi.hoisted(() => ({ speak: vi.fn() }))
vi.mock('../geofence/audio', () => ({ speak }))

import { fileQueue, playWithFallback } from './playback'

const GOC = { poiId: 'p1', lang: 'ja', text: 'Phở ngon', audioUrl: null as string | null, isFallback: true, uuTien: 0 }

beforeEach(() => {
  fileQueue.stop()
  vi.unstubAllGlobals()
  speak.mockReset()
})

describe('playWithFallback', () => {
  it('tier1 khi có file và không fallback', async () => {
    class FakeAudio {
      src = ''
      onplaying: (() => void) | null = null
      onerror: (() => void) | null = null
      onended: (() => void) | null = null
      pause = vi.fn()
      play = vi.fn(async () => {
        this.onplaying?.()
        this.onended?.()
      })
    }
    vi.stubGlobal('Audio', FakeAudio)

    const tier = await playWithFallback({
      ...GOC,
      audioUrl: 'https://cdn.example.test/f.mp3',
      isFallback: false,
    })
    expect(tier).toBe('tier1')
  })

  it('uses the absolute audio URL as-is', async () => {
    const instances: FakeAudio[] = []
    class FakeAudio {
      src = ''
      onplaying: (() => void) | null = null
      onerror: (() => void) | null = null
      onended: (() => void) | null = null
      constructor() {
        instances.push(this)
      }
      pause = vi.fn()
      play = vi.fn(async () => {
        this.onplaying?.()
        this.onended?.()
      })
    }
    vi.stubGlobal('Audio', FakeAudio)

    await playWithFallback({
      ...GOC,
      audioUrl: 'https://cdn.example.test/f.mp3',
      isFallback: false,
    })

    expect(instances[0].src).toBe('https://cdn.example.test/f.mp3')
  })

  it('falls back to browser speech when a saved audio file fails', async () => {
    class FakeAudio {
      src = ''
      onplaying: (() => void) | null = null
      onerror: (() => void) | null = null
      onended: (() => void) | null = null
      pause = vi.fn()
      play = vi.fn(() => {
        this.onerror?.()
        return Promise.resolve()
      })
    }
    vi.stubGlobal('Audio', FakeAudio)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 401 })))

    const tier = await playWithFallback({
      ...GOC,
      audioUrl: '/missing.mp3',
      isFallback: false,
    })

    expect(tier).toBe('tier3')
    expect(speak).toHaveBeenCalledWith('Phở ngon', 'ja')
  })

  it('rơi dần 1.5 → 2 → 3 khi từng tầng lỗi', async () => {
    const goi = vi.fn()
    class FakeAudio {
      src = ''
      onplaying: (() => void) | null = null
      onerror: (() => void) | null = null
      onended: (() => void) | null = null
      pause = vi.fn()
      play = vi.fn(async () => {
        this.onplaying?.()
        this.onended?.()
      })
    }
    vi.stubGlobal('Audio', FakeAudio)
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-audio')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    vi.stubGlobal('fetch', goi)
    goi.mockResolvedValueOnce({ ok: true, json: async () => ({ audio_url: '/o.mp3' }) })
    expect(await playWithFallback(GOC)).toBe('tier1.5')
    goi.mockRejectedValueOnce(new Error('mang hong'))
    goi.mockResolvedValueOnce({ ok: true, blob: async () => new Blob(['x']) })
    expect(await playWithFallback(GOC)).toBe('tier2')
    goi.mockRejectedValue(new Error('mang hong'))
    expect(await playWithFallback(GOC)).toBe('tier3')
    vi.unstubAllGlobals()
  })

  it('đổi ngôn ngữ giữa chừng thì bỏ kết quả cũ', async () => {
    const goi = vi.fn()
    vi.stubGlobal('fetch', goi)
    let giai: (v: { ok: boolean; json: () => Promise<unknown> }) => void = () => {}
    goi.mockImplementationOnce(() => new Promise((res) => { giai = res }))
    const truoc = playWithFallback(GOC)
    const sau = playWithFallback({ ...GOC, lang: 'ko' })
    giai({ ok: true, json: async () => ({ audio_url: '/cu.mp3' }) })
    expect(await truoc).toBe('bo')
    await sau
    vi.unstubAllGlobals()
  })
})
