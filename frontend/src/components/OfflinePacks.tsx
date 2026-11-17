import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../config'
import { type PackHook } from './useMapPack'

const API_GOC = API_BASE_URL

interface TepAudio {
  url: string
  sha256: string
  bytes: number
}

const TEN_NGON_NGU: Record<string, string> = {
  vi: 'Tiếng Việt',
  en: 'English',
  zh: '中文',
  ja: '日本語',
  ko: '한국어',
}

const MA_NGON_NGU: Record<string, string> = {
  vi: 'VI',
  en: 'EN',
  zh: 'ZH',
  ja: 'JA',
  ko: 'KO',
}

export default function OfflinePacks({ pack }: { pack: PackHook }) {
  const { cheDo, setCheDo, trangThai, taiPack } = pack
  const [scopes, setScopes] = useState<string[]>([])
  const [langPack, setLangPack] = useState('')
  const [dangTaiAudio, setDangTaiAudio] = useState(false)
  const [thatBaiLienTiep, setThatBaiLienTiep] = useState(0)

  useEffect(() => {
    fetch(`${API_GOC}/maps/offline-options`)
      .then((r) => r.json())
      .then((d: { scopes: string[] }) => {
        setScopes(d.scopes)
        setThatBaiLienTiep(0)
      })
      .catch(() => setThatBaiLienTiep((n) => n + 1))
  }, [])

  const taiAudioPack = async (lang: string) => {
    setDangTaiAudio(true)
    try {
      const man = (await fetch(`${API_GOC}/maps/audio-pack?lang=${lang}`).then((r) => r.json())) as { files: TepAudio[] }
      const cache = await caches.open(`audio-pack-${lang}`)
      for (const tep of man.files) {
        const res = await fetch(`${API_GOC}${tep.url.split('?')[0]}?l=${lang}`)
        await cache.put(`${API_GOC}${tep.url}`, res.clone())
      }
      setLangPack(lang)
    } finally {
      setDangTaiAudio(false)
    }
  }

  const loiTaiMapPack =
    trangThai.startsWith('Không đủ dung lượng') ||
    trangThai.startsWith('Không cài được') ||
    trangThai.startsWith('Không khôi phục được')

  return (
    <div className="offline-packs-container">
      <div className="section-header">
        <div>
          <h2 className="section-title">Quản lý Gói Offline</h2>
          <p className="card__subtitle">Tải trước bản đồ PMTiles và âm thanh thuyết minh để trải nghiệm trọn vẹn khi không có mạng</p>
        </div>
      </div>

      {/* 1. Chế độ hoạt động bản đồ */}
      <div className="card mt">
        <h3 className="card__title">Chế độ tải bản đồ</h3>
        <p className="card__subtitle">Chọn nguồn nạp dữ liệu gạch bản đồ số (vector tiles)</p>

        <div className="mode-selector-grid mt">
          {(['cloud', 'offline', 'hybrid'] as const).map((c) => {
            const isSelected = c === cheDo
            const moTa =
              c === 'cloud'
                ? 'Tải trực tiếp qua Internet (MapTiler Cloud)'
                : c === 'offline'
                ? 'Chỉ dùng tệp PMTiles đã tải trước trên máy'
                : 'Tự động dùng offline nếu mất mạng, ngược lại ưu tiên cloud'

            return (
              <button
                key={c}
                type="button"
                className={`mode-card${isSelected ? ' mode-card--active' : ''}`}
                onClick={() => setCheDo(c)}
              >
                <div className="mode-card__radio">
                  <span className={`radio-dot${isSelected ? ' radio-dot--checked' : ''}`} />
                  <strong className="mode-card__name">Chế độ: {c.toUpperCase()}</strong>
                </div>
                <p className="mode-card__desc">{moTa}</p>
              </button>
            )
          })}
        </div>
      </div>

      {thatBaiLienTiep >= 3 && (
        <div className="notice notice--error mt">
          Máy chủ offline đang bận hoặc không kết nối được. Vui lòng thử lại sau giây lát.
        </div>
      )}

      {/* 2. Gói bản đồ offline */}
      <div className="card mt">
        <div className="section-header">
          <div>
            <h3 className="card__title">Gói vector bản đồ Quận 4</h3>
            <p className="card__subtitle">Đóng gói định dạng PMTiles siêu nhẹ, hỗ trợ Range Request</p>
          </div>
        </div>

        {scopes.length === 0 ? (
          <div className="empty-state">
            <p className="muted">Không có gói bản đồ nào khả dụng trên máy chủ lúc này.</p>
          </div>
        ) : (
          <div className="pack-list mt">
            {scopes.map((s) => (
              <div key={s} className="pack-item">
                <div className="pack-info">
                  <div className="pack-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" />
                      <line x1="9" y1="3" x2="9" y2="18" />
                      <line x1="15" y1="6" x2="15" y2="21" />
                    </svg>
                  </div>
                  <div>
                    <strong className="pack-name">Khu vực: {s}</strong>
                    <p className="pack-sub">Gói dữ liệu bản đồ số Quận 4 hoàn chỉnh</p>
                  </div>
                </div>

                <div className="pack-actions">
                  <button
                    className="btn btn--sm btn--primary"
                    type="button"
                    onClick={() => void taiPack(s)}
                  >
                    Tải về máy
                  </button>
                  <button
                    className="btn btn--sm btn--secondary"
                    type="button"
                    onClick={() => void taiPack(s, true)}
                  >
                    Tải lại (Cài đè)
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {trangThai !== '' && (
          <div className={`notice notice--${loiTaiMapPack ? 'error' : 'info'} mt`} role={loiTaiMapPack ? 'alert' : 'status'}>
            Tiến độ gói bản đồ: <strong>{trangThai}</strong>
          </div>
        )}
      </div>

      {/* 3. Gói audio thuyết minh */}
      <div className="card mt">
        <div className="section-header">
          <div>
            <h3 className="card__title">Gói thuyết minh âm thanh theo ngôn ngữ</h3>
            <p className="card__subtitle">Lưu toàn bộ MP3 giọng nói vào Cache Storage của trình duyệt</p>
          </div>
        </div>

        <div className="audio-pack-grid mt">
          {['vi', 'en', 'zh', 'ja', 'ko'].map((l) => {
            const ten = TEN_NGON_NGU[l] || l
            const code = MA_NGON_NGU[l] || l.toUpperCase()
            const isInstalled = langPack === l

            return (
              <button
                key={l}
                type="button"
                className={`audio-pack-btn${isInstalled ? ' audio-pack-btn--installed' : ''}`}
                disabled={dangTaiAudio}
                onClick={() => void taiAudioPack(l)}
              >
                <span className="audio-pack-flag">{code}</span>
                <span className="audio-pack-name">{ten}</span>
                <span className="audio-pack-status">
                  {isInstalled ? (
                    <span className="inline-flex items-center gap-1">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      Đã cài
                    </span>
                  ) : (
                    'Tải gói'
                  )}
                </span>
              </button>
            )
          })}
        </div>

        {langPack !== '' && (
          <div className="badge badge--ok mt">
            Đã đồng bộ sẵn sàng toàn bộ audio {TEN_NGON_NGU[langPack] || langPack} để nghe ngoại tuyến!
          </div>
        )}
      </div>
    </div>
  )
}
