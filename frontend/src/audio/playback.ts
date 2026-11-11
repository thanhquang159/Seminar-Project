import { api, apiText } from '../admin/api'
import { speak } from '../geofence/audio'
import { API_BASE_URL } from '../config'

const API_GOC = API_BASE_URL

// Hàng đợi một ô cho file audio: thay thế khi ưu tiên cao hơn.
class FileQueue {
  private audio: HTMLAudioElement | null = null
  private uuTien: number | null = null
  private cancelPending: (() => void) | null = null
  private objectUrl: string | null = null

  async play(url: string, uuTien: number): Promise<boolean> {
    if (this.uuTien !== null && uuTien >= this.uuTien) return false
    this.stop()
    if (typeof Audio === 'undefined') return false
    return this.start(url, uuTien)
  }

  private start(url: string, uuTien: number): Promise<boolean> {
    const audio = new Audio()
    this.audio = audio
    this.uuTien = uuTien

    return new Promise((resolve) => {
      let settled = false
      const finish = (started: boolean) => {
        if (settled) return
        settled = true
        window.clearTimeout(timeout)
        audio.onplaying = null
        audio.onerror = null
        this.cancelPending = null
        if (!started && this.audio === audio) {
          audio.pause()
          this.audio = null
          this.uuTien = null
          this.revokeObjectUrl()
        }
        resolve(started)
      }

      const timeout = window.setTimeout(() => finish(false), 10_000)
      this.cancelPending = () => finish(false)
      audio.onplaying = () => finish(true)
      audio.onerror = () => finish(false)
      audio.onended = () => {
        if (this.audio === audio) {
          this.audio = null
          this.uuTien = null
          this.revokeObjectUrl()
        }
      }
      audio.src = url
      void audio.play().catch(() => finish(false))
    })
  }

  stop(): void {
    const cancelPending = this.cancelPending
    this.cancelPending = null
    this.audio?.pause()
    this.audio = null
    this.uuTien = null
    this.revokeObjectUrl()
    cancelPending?.()
  }

  playBlob(blob: Blob, uuTien: number): Promise<boolean> {
    if (this.uuTien !== null && uuTien >= this.uuTien) return Promise.resolve(false)
    this.stop()
    this.revokeObjectUrl()
    this.objectUrl = URL.createObjectURL(blob)
    if (typeof Audio === 'undefined') {
      this.revokeObjectUrl()
      return Promise.resolve(false)
    }
    return this.start(this.objectUrl, uuTien)
  }

  private revokeObjectUrl(): void {
    if (this.objectUrl !== null) {
      URL.revokeObjectURL(this.objectUrl)
      this.objectUrl = null
    }
  }
}

export const fileQueue = new FileQueue()
let lanPhat = 0

export interface PhatYeuCau {
  poiId: string
  lang: string
  text: string
  audioUrl: string | null
  isFallback: boolean
  uuTien: number
}

// 4 tầng: file sinh sẵn → on-demand → stream → đọc trình duyệt.
// Đổi ngôn ngữ giữa chừng thì bỏ kết quả lỗi thời.
export async function playWithFallback(yeuCau: PhatYeuCau): Promise<string> {
  const token = ++lanPhat
  const conHan = () => token === lanPhat
  const { poiId, lang, text, audioUrl, isFallback, uuTien } = yeuCau

  if (audioUrl !== null && !isFallback) {
    const url = new URL(audioUrl, API_GOC).toString()
    if (await fileQueue.play(url, uuTien)) return 'tier1'
    if (!conHan()) return 'bo'
  }
  if (isFallback || audioUrl !== null) {
    try {
      const goi = await api<{ audio_url: string }>('/audio/on-demand', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ poi_id: poiId, lang }),
      })
      if (!conHan()) return 'bo'
      const url = new URL(goi.audio_url, API_GOC).toString()
      if (await fileQueue.play(url, uuTien)) return 'tier1.5'
    } catch {
      if (!conHan()) return 'bo'
    }
  }
  try {
    const res = await apiText('/audio/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, lang }),
    })
    if (!conHan()) return 'bo'
    if (!res.ok) throw new Error()
    const blob = await res.blob()
    if (!conHan()) return 'bo'
    if (await fileQueue.playBlob(blob, uuTien)) return 'tier2'
  } catch {
    if (!conHan()) return 'bo'
  }
  speak(text, lang)
  return 'tier3'
}
