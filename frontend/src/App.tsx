import { lazy, Suspense, useCallback, useEffect, useRef, useState, type ComponentType } from 'react'
import ConsentBanner from './components/ConsentBanner'
import LanguagePicker from './components/LanguagePicker'
import OfflinePacks from './components/OfflinePacks'
import { PoiDetail, PoiList } from './components/PoiList'
import { useMapPack } from './components/useMapPack'
import Settings from './components/Settings'
import { apiText } from './admin/api'
import { playWithFallback } from './audio/playback'
import { useGeofence } from './geofence/useGeofence'
import { useViTri } from './geofence/useViTri'
import { chonPrefetch, tinhBackoff } from './geofence/prefetch'
import { useStartup } from './startup'
import { batDauAnalytics, ghiSuKien } from './analytics/service'
import { baoMau, batDauQuanSatVịTri } from './telemetry/location'
import { laySessionId, useConsentStore } from './stores/consentStore'
import { usePoiStore } from './stores/poiStore'

import HomeSplash from './components/HomeSplash'
import './App.css'

// PERF-004: tách chunk cho mã chỉ cần khi vào tab tương ứng. MapView kéo theo
// maplibre-gl (hàng trăm KB, parse chậm trên điện thoại); AdminApp/OwnerApp
// chỉ dùng khi chủ/admin mở tab. Chunk lười vẫn nằm trong precache của SW nên
// offline dùng được sau lần cài đầu.
const MapView = lazy(() => import('./components/MapView'))
const AdminApp = lazy(() => import('./admin/AdminApp'))
const OwnerApp = lazy(() => import('./admin/OwnerApp'))

export type TabType = 'trang-chu' | 'kham-pha' | 'admin' | 'chu-quan' | 'goi-offline' | 'cai-dat'

/* =========================================================================
   Inline SVG Icons nét mảnh (strokeWidth="1.75") thay thế toàn bộ Emoji
   ========================================================================= */

function LanternIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="12" y1="2" x2="12" y2="5" />
      <rect x="5" y="5" width="14" height="13" rx="4" />
      <line x1="9" y1="5" x2="9" y2="18" />
      <line x1="15" y1="5" x2="15" y2="18" />
      <line x1="10" y1="18" x2="10" y2="22" />
      <line x1="14" y1="18" x2="14" y2="22" />
    </svg>
  )
}

function FoodIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 11h16a8 8 0 0 1-16 0z" />
      <path d="M6 11v1a6 6 0 0 0 12 0v-1" />
      <path d="M8 4c0 2-1 3-1 4" />
      <path d="M12 3c0 2.5-1 3.5-1 5" />
      <path d="M16 4c0 2-1 3-1 4" />
    </svg>
  )
}

function StoreIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7" />
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
      <path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4" />
      <path d="M2 7h20" />
    </svg>
  )
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  )
}

function OfflineIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

interface TabItem {
  ma: TabType
  ten: string
  icon: ComponentType<{ className?: string }>
}

const TAB: TabItem[] = [
  { ma: 'trang-chu', ten: 'Trang chủ', icon: LanternIcon },
  { ma: 'kham-pha', ten: 'Khám phá', icon: FoodIcon },
  { ma: 'chu-quan', ten: 'Chủ quán', icon: StoreIcon },
  { ma: 'admin', ten: 'Quản trị', icon: ShieldIcon },
  { ma: 'goi-offline', ten: 'Gói offline', icon: OfflineIcon },
  { ma: 'cai-dat', ten: 'Cài đặt', icon: SettingsIcon },
]

function khoiTaoTab(): TabType {
  try {
    const params = new URLSearchParams(window.location.search)
    const t = params.get('tab') as TabType | null
    if (t && ['trang-chu', 'kham-pha', 'admin', 'chu-quan', 'goi-offline', 'cai-dat'].includes(t)) {
      return t
    }
  } catch {
    // fallback
  }
  return 'trang-chu'
}

function App() {
  const { pois, loading, error, fetchPOIs, lang } = usePoiStore()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [dangDoc, setDangDoc] = useState<string | null>(null)
  const [tab, setTab] = useState<TabType>(khoiTaoTab)
  const pack = useMapPack()
  const khoiDong = useStartup()
  const viTri = useViTri()
  const trangThaiConsent = useConsentStore((s) => s.trangThai)
  const langRef = useRef(lang)
  useEffect(() => {
    langRef.current = lang
  })

  // ANA-001: chỉ khi đã đồng ý mới bật; thu hồi consent thì teardown ngay.
  useEffect(() => batDauAnalytics(), [trangThaiConsent])

  // ANA-005: lane runtime chẩn đoán, cố ý không phụ thuộc consent.
  useEffect(() => batDauQuanSatVịTri(laySessionId), [])

  useEffect(() => {
    if (viTri === null) return
    baoMau({ lat: viTri.lat, lng: viTri.lng, outcome: 'ok' })
  }, [viTri])

  // GEO-011: prefetch nền fallback trong 500m, 3/batch, 429 thì backoff.
  useEffect(() => {
    if (viTri === null || pois.length === 0) return
    let dung = false
    let thatBai = 0
    let henGio = 0
    // SEC-010: server 409 khi POI chưa có bản dịch (không còn dịch máy tự
    // sinh). Ghi nhớ để không gọi lại cùng một cặp (POI, ngôn ngữ) mỗi vòng —
    // nếu không, mỗi POI thiếu bản dịch sẽ tốn một request mỗi 60 giây, suốt
    // cả buổi đi bộ.
    const thieu = new Set<string>()
    const chay = async () => {
      if (dung) return
      for (const p of chonPrefetch(pois, viTri.lat, viTri.lng)) {
        const khoa = `${p.id}:${langRef.current}`
        if (thieu.has(khoa)) continue
        try {
          const res = await apiText('/audio/on-demand', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ poi_id: p.id, lang: langRef.current }),
          })
          if (res.status === 409) {
            thieu.add(khoa)
            continue
          }
          if (res.status === 429) {
            thatBai += 1
            henGio = window.setTimeout(chay, tinhBackoff(thatBai))
            return
          }
          thatBai = 0
        } catch {
          return
        }
      }
      henGio = window.setTimeout(chay, 60000)
    }
    henGio = window.setTimeout(chay, 5000)
    return () => {
      dung = true
      window.clearTimeout(henGio)
    }
  }, [viTri, pois])

  const chonPoi = useCallback((id: string) => setSelectedId(id), [])

  // GEO-004 + AUD-009: vào vòng thì phát 4 tầng, đổi ngôn ngữ thì bỏ cũ.
  const docPoi = useCallback(
    (id: string) => {
      const poi = pois.find((p) => p.id === id)
      if (poi === undefined) return
      setSelectedId(id)
      setDangDoc(poi.name)
      void ghiSuKien('poi_viewed', { poi_id: poi.id, lang: langRef.current })
      void playWithFallback({
        poiId: poi.id,
        lang: langRef.current,
        text: poi.description,
        audioUrl: poi.audio_url,
        isFallback: poi.is_fallback,
        uuTien: poi.audio_priority,
      }).then((tier) => {
        // Chỉ ghi khi thật sự có tiếng; 'bo' nghĩa là bị lượt mới hơn cắt ngang
        // thì tính vào số liệu sẽ làm sai tỉ lệ nghe.
        if (tier !== 'bo') {
          return ghiSuKien('audio_played', { poi_id: poi.id, lang: langRef.current, tier })
        }
      })
    },
    [pois],
  )

  useGeofence(pois, (poi) => docPoi(poi.id))
  const dangChon = pois.find((p) => p.id === selectedId) ?? null

  if (tab === 'trang-chu') {
    return (
      <HomeSplash
        onStart={() => setTab('kham-pha')}
        onOffline={() => setTab('goi-offline')}
        onNavigate={(target) => setTab(target)}
      />
    )
  }

  return (
    <div className="app-layout">
      {/* Header thương hiệu chính: 56px, cố định phía trên, hiệu ứng kính mờ */}
      <header className="app-header">
        <div className="app-header__container">
          <div
            className="brand-badge"
            role="button"
            tabIndex={0}
            onClick={() => setTab('trang-chu')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') setTab('trang-chu')
            }}
            style={{ cursor: 'pointer' }}
            title="Quay về trang chủ"
          >
            <span className="brand-badge__icon" aria-hidden="true">
              <LanternIcon />
            </span>
            <div className="brand-badge__text">
              <h1 className="brand-badge__title">AMDS · Ẩm Thực Quận 4</h1>
              <p className="brand-badge__subtitle">Bản đồ số &amp; Thuyết minh tự động theo vị trí</p>
              <h1 className="sr-only">Linh Ứng Guide</h1>
            </div>
          </div>

          <div className="app-header__right">
            <div className="network-status" title={navigator.onLine !== false ? 'Đang trực tuyến' : 'Ngoại tuyến'}>
              <span className="network-status__dot" />
              <span className="network-status__label">{navigator.onLine !== false ? 'Online' : 'Offline'}</span>
            </div>
            <LanguagePicker />
          </div>
        </div>
      </header>

      {/* Thanh điều hướng chính (Laptop: tab ngang tinh gọn / Mobile: Bottom Navigation Bar) */}
      <nav className="nav-container" aria-label="Điều hướng chính">
        <div className="nav-tabs" role="tablist">
          {TAB.map((t) => {
            const isActive = tab === t.ma
            const Icon = t.icon
            return (
              <button
                key={t.ma}
                type="button"
                role="tab"
                aria-selected={isActive}
                aria-label={t.ma === 'admin' ? 'Admin · Quản trị' : t.ten}
                className={`nav-tab-item${isActive ? ' nav-tab-item--active' : ''}`}
                onClick={() => setTab(t.ma)}
              >
                <span className="nav-tab-item__icon" aria-hidden="true">
                  <Icon />
                </span>
                <span className="nav-tab-item__label">{t.ten}</span>
              </button>
            )
          })}
        </div>
      </nav>

      {/* Nội dung chính của ứng dụng */}
      <main className="app-main-content">
        {/* Banner khởi động và consent */}
        {!khoiDong.hoanTat && (
          <div className="notice notice--info mb">
            Đang khởi động… (nội dung {khoiDong.noiDungSanSang ? 'sẵn sàng' : 'đang tải'}, giao diện {khoiDong.uiSanSang ? 'sẵn sàng' : 'đang tải'})
          </div>
        )}

        <ConsentBanner />

        {/* Floating Glass Pill: Thanh phát âm thanh hiện đại, không đẩy lệch bố cục trang */}
        {dangDoc !== null && (
          <div className="audio-playing-bar" role="status" aria-live="polite">
            <div className="audio-playing-bar__wave" aria-hidden="true">
              <span className="wave-bar" />
              <span className="wave-bar" />
              <span className="wave-bar" />
            </div>
            <span className="audio-playing-bar__text">
              Đang phát thuyết minh: <strong>{dangDoc}</strong>
            </span>
            <button
              type="button"
              className="btn-icon btn-icon--sm"
              onClick={() => setDangDoc(null)}
              title="Đóng thông báo âm thanh"
              aria-label="Đóng thông báo âm thanh"
            >
              <CloseIcon />
            </button>
          </div>
        )}

        <Suspense fallback={<div className="notice notice--info">Đang tải giao diện…</div>}>
          {tab === 'admin' && <AdminApp onPoisChanged={fetchPOIs} />}
          {tab === 'chu-quan' && <OwnerApp />}
          {tab === 'goi-offline' && <OfflinePacks pack={pack} />}
          {tab === 'cai-dat' && <Settings pack={pack} />}

          {tab === 'kham-pha' && (
            <div className="kham-pha-layout">
              {/* Lỗi hoặc trạng thái rỗng */}
              {loading && <div className="notice notice--info mb">Đang tải danh sách quán ăn…</div>}
              {error !== '' && (
                <div className="notice notice--error mb">
                  Không kết nối được máy chủ (uvicorn app.main:app --reload). Lỗi: {error}
                </div>
              )}
              {!loading && error === '' && pois.length === 0 && (
                <div className="notice notice--warn mb">
                  Chưa có dữ liệu quán ăn. Vui lòng kiểm tra cơ sở dữ liệu MongoDB.
                </div>
              )}

              {/* Lưới 2 cột cho Laptop (Split-view cố định chiều cao, cuộn độc lập) / Mobile (Tránh scroll trap) */}
              <div className="kham-pha-grid">
                {/* Cột trái: Bản đồ */}
                <div className="kham-pha-grid__map-col">
                  <MapView
                    pois={pois}
                    selectedId={selectedId}
                    onSelect={chonPoi}
                    stylePack={(pack.cheDo === 'offline' || (pack.cheDo === 'hybrid' && pack.tamOffline)) ? pack.stylePack : null}
                  />
                </div>

                {/* Cột phải: Chi tiết quán (nếu có chọn) & Danh sách quán ăn */}
                <div className="kham-pha-grid__list-col">
                  {dangChon !== null && (
                    <div className="kham-pha-detail-wrap mb">
                      <PoiDetail
                        poi={dangChon}
                        onNghe={() => void docPoi(dangChon.id)}
                        onDong={() => setSelectedId(null)}
                      />
                    </div>
                  )}
                  <PoiList pois={pois} selectedId={selectedId} onChon={chonPoi} />
                </div>
              </div>
            </div>
          )}
        </Suspense>
      </main>

      {/* Footer bản quyền & thông tin: Tối giản, ẩn trên Khám phá để tối đa diện tích bản đồ */}
      {tab !== 'kham-pha' && (
        <footer className="app-footer">
          <p>Hệ thống hướng dẫn du lịch ẩm thực Quận 4 · Hỗ trợ PWA &amp; Ngoại tuyến hoàn toàn</p>
        </footer>
      )}
    </div>
  )
}

export default App
