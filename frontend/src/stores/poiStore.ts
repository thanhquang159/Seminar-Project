import { create } from 'zustand'
import { dongBo } from '../offline/sync'
import { docPois } from '../offline/idb'
import { stopPlayback } from '../audio/playback'

// Một POI như backend trả về ở GET /poi (đã hydrate ngôn ngữ).
export interface Poi {
  id: string
  name: string
  description: string
  category?: string
  lat: number
  lng: number
  trigger_radius: number
  audio_priority: number
  lang: string
  is_fallback: boolean
  audio_url: string | null
  images?: string[]
}

export const NGON_NGU: { ma: string; ten: string }[] = [
  { ma: 'vi', ten: 'Tiếng Việt' },
  { ma: 'en', ten: 'English' },
  { ma: 'zh', ten: '中文' },
  { ma: 'ja', ten: '日本語' },
  { ma: 'ko', ten: '한국어' },
]

const ngonNguDaLuu = localStorage.getItem('quan4-lang')
const ngonNguMacDinh =
  ngonNguDaLuu !== null && NGON_NGU.some((ngonNgu) => ngonNgu.ma === ngonNguDaLuu)
    ? ngonNguDaLuu
    : 'en'

interface PoiState {
  pois: Poi[]
  loading: boolean
  daTaiDuLieu: boolean
  error: string
  lang: string
  setLang: (lang: string) => void
  fetchPOIs: (taiLaiToanBo?: boolean) => Promise<void>
}

// State toàn cục (nơi duy nhất giữ danh sách POI cho mọi component).
export const usePoiStore = create<PoiState>((set, get) => ({
  pois: [],
  loading: false,
  daTaiDuLieu: false,
  error: '',
  // Cài đặt ngôn ngữ nội dung, không phải bí mật nên lưu localStorage được.
  lang: ngonNguMacDinh,
  setLang: (lang: string) => {
    localStorage.setItem('quan4-lang', lang)
    stopPlayback()
    set({ lang, pois: [], loading: true, daTaiDuLieu: false })
    void get().fetchPOIs()
  },
  fetchPOIs: async (taiLaiToanBo = false) => {
    set({ loading: true, error: '' })
    const lang = get().lang
    try {
      try {
        const banLuu = await docPois(lang)
        if (banLuu !== null && get().lang === lang
          && !(lang === 'vi' && banLuu.pois.some((p) => p.lang !== 'vi' || p.is_fallback))) {
          set({ pois: banLuu.pois, loading: false, daTaiDuLieu: true })
        }
      } catch (error) {
        console.warn('Không đọc được POI trong IndexedDB:', error)
      }

      // Hiển thị bản lưu trước; đồng bộ delta hoặc tải snapshot nếu chưa có.
      const { pois } = await dongBo(lang, taiLaiToanBo)
      if (get().lang !== lang) return
      set({ pois, loading: false, daTaiDuLieu: true })
    } catch (err) {
      if (get().lang !== lang) return
      set({
        error: err instanceof Error ? err.message : 'Lỗi không rõ',
        loading: false,
        daTaiDuLieu: true,
      })
    }
  },
}))
