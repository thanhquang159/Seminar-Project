import { lazy, Suspense, useCallback, useEffect, useRef, useState, type ComponentType } from 'react'
import LanguagePicker from './components/LanguagePicker'
import OfflinePacks from './components/OfflinePacks'
import { PoiDetail, PoiList } from './components/PoiList'
import { useMapPack } from './components/useMapPack'
import Settings from './components/Settings'
import { apiText } from './admin/api'
import { playWithFallback, stopPlayback } from './audio/playback'
import { useGeofence } from './geofence/useGeofence'
import { useViTri } from './geofence/useViTri'
import { chonPrefetch, tinhBackoff } from './geofence/prefetch'
import { useStartup } from './startup'
import { batDauAnalytics, batDauChiaSeMacDinh, ghiSuKienNgay } from './analytics/service'
import { baoMau, batDauQuanSatVịTri } from './telemetry/location'
import { laySessionId, useConsentStore } from './stores/consentStore'
import { usePoiStore } from './stores/poiStore'
import { useUiBundle } from './i18n/bundles'

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

const TAB: { ma: TabType; khoaTen: string; icon: ComponentType<{ className?: string }> }[] = [
  { ma: 'trang-chu', khoaTen: 'nav_home', icon: LanternIcon },
  { ma: 'kham-pha', khoaTen: 'nav_explore', icon: FoodIcon },
  { ma: 'chu-quan', khoaTen: 'nav_owner', icon: StoreIcon },
  { ma: 'admin', khoaTen: 'nav_admin', icon: ShieldIcon },
  { ma: 'goi-offline', khoaTen: 'nav_packs', icon: OfflineIcon },
  { ma: 'cai-dat', khoaTen: 'nav_settings', icon: SettingsIcon },
]

function layPoiIdTuDuongDan(pathname = window.location.pathname): string | null {
  const path = pathname.replace(/\/+$/, '') || '/'
  if (path === '/' || path === '/admin/login' || path === '/owner/login') return null

  const segment = path.slice(1)
  if (segment.includes('/')) return null
  try {
    return decodeURIComponent(segment)
  } catch {
    return segment
  }
}

function capNhatDuongDan(path: string, thayThe = false) {
  const diaChiHienTai = `${window.location.pathname}${window.location.search}`
  if (diaChiHienTai === path) return
  if (thayThe) {
    window.history.replaceState(null, '', path)
  } else {
    window.history.pushState(null, '', path)
  }
}

function khoiTaoTab(): TabType {
  if (layPoiIdTuDuongDan() !== null) return 'kham-pha'
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

function MainApp() {
  const { pois, loading, daTaiDuLieu, error, fetchPOIs, lang } = usePoiStore()
  const { t } = useUiBundle(lang)
  const [selectedId, setSelectedId] = useState<string | null>(() => layPoiIdTuDuongDan())
  const [dangDoc, setDangDoc] = useState<string | null>(null)
  useEffect(() => usePoiStore.subscribe((state, previous) => {
    if (state.lang !== previous.lang) setDangDoc(null)
  }), [])
  const [tab, setTab] = useState<TabType>(khoiTaoTab)
  const pack = useMapPack()
  const khoiDong = useStartup()
  const viTri = useViTri()
  const trangThaiConsent = useConsentStore((s) => s.trangThai)
  const langRef = useRef(lang)
  useEffect(() => {
    document.documentElement.lang = lang
    document.title = `AMDS — ${t('app_title')}`
  }, [lang, t])

  useEffect(() => {
    langRef.current = lang
  })

  useEffect(() => {
    const dongBoTheoDuongDan = () => {
      const poiId = layPoiIdTuDuongDan()
      setSelectedId(poiId)
      setTab(poiId === null ? khoiTaoTab() : 'kham-pha')
    }

    window.addEventListener('popstate', dongBoTheoDuongDan)
    return () => window.removeEventListener('popstate', dongBoTheoDuongDan)
  }, [])

  useEffect(() => {
    const poiId = layPoiIdTuDuongDan()
    if (poiId === null || !daTaiDuLieu || pois.some((poi) => poi.id === poiId)) return

    capNhatDuongDan('/?tab=kham-pha', true)
  }, [daTaiDuLieu, pois])

  const chuyenTab = useCallback((tabMoi: TabType) => {
    if (tabMoi !== 'kham-pha' && layPoiIdTuDuongDan() !== null) {
      setSelectedId(null)
      capNhatDuongDan(`/?tab=${encodeURIComponent(tabMoi)}`)
    }
    setTab(tabMoi)
  }, [])

  useEffect(() => {
    if (trangThaiConsent !== 'chua-chon') return
    let active = true
    let dangBat = false
    const enableByDefault = async () => {
      if (dangBat) return
      dangBat = true
      try {
        const enabled = await batDauChiaSeMacDinh()
        if (active && !enabled) {
          console.error('Không thể bật analytics mặc định; khách vẫn chưa được theo dõi.')
        }
      } catch (error) {
        if (active) console.error('Không kết nối được để bật analytics mặc định:', error)
      } finally {
        dangBat = false
      }
    }

    void enableByDefault()
    const retry = window.setInterval(() => {
      if (useConsentStore.getState().trangThai === 'chua-chon') void enableByDefault()
    }, 30000)

    return () => {
      active = false
      window.clearInterval(retry)
    }
  }, [trangThaiConsent])

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

  const chonPoi = useCallback(
    (id: string) => {
      setSelectedId(id)
      setTab('kham-pha')
      const poi = pois.find((item) => item.id === id)
      if (poi !== undefined) {
        capNhatDuongDan(`/${encodeURIComponent(id)}`)
        void ghiSuKienNgay('poi_viewed', { poi_id: poi.id, lang: langRef.current })
      }
    },
    [pois],
  )
  const dongChiTiet = useCallback(() => {
    setSelectedId(null)
    setTab('kham-pha')
    capNhatDuongDan('/?tab=kham-pha')
  }, [])
  const vaoCong = useCallback((cong: 'admin' | 'chu-quan') => {
    window.location.assign(cong === 'admin' ? '/admin/login' : '/owner/login')
  }, [])

  // GEO-004 + AUD-009: vào vòng thì phát 4 tầng, đổi ngôn ngữ thì bỏ cũ.
  const docPoi = useCallback(
    (id: string) => {
      const poi = pois.find((p) => p.id === id)
      if (poi === undefined) return
      setSelectedId(id)
      setDangDoc(poi.name)
      void playWithFallback({
        poiId: poi.id,
        lang: langRef.current,
        text: poi.description,
        contentLang: poi.lang,
        audioUrl: poi.audio_url,
        isFallback: poi.is_fallback,
        uuTien: poi.audio_priority,
      })
    },
    [pois],
  )
  const nghePoi = useCallback(
    (id: string) => {
      const poi = pois.find((item) => item.id === id)
      if (poi === undefined) return
      void ghiSuKienNgay('audio_played', { poi_id: poi.id, lang: langRef.current })
      docPoi(id)
    },
    [docPoi, pois],
  )

  useGeofence(pois, (poi) => docPoi(poi.id))
  const dangChon = pois.find((p) => p.id === selectedId) ?? null

  if (tab === 'trang-chu') {
    return (
      <HomeSplash
        onStart={() => chuyenTab('kham-pha')}
        onOffline={() => chuyenTab('goi-offline')}
        onNavigate={(target) => {
          if (target === 'admin' || target === 'chu-quan') {
            vaoCong(target)
            return
          }
          chuyenTab(target)
        }}
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
            onClick={() => chuyenTab('trang-chu')}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') chuyenTab('trang-chu')
            }}
            style={{ cursor: 'pointer' }}
            title={t('home_link')}
          >
            <span className="brand-badge__icon" aria-hidden="true">
              <LanternIcon />
            </span>
            <div className="brand-badge__text">
              <h1 className="brand-badge__title">{t('brand_title')}</h1>
              <p className="brand-badge__subtitle">{t('brand_subtitle')}</p>
              <h1 className="sr-only">Linh Ứng Guide</h1>
            </div>
          </div>

          <div className="app-header__right">
            <div className="network-status" title={navigator.onLine !== false ? t('network_online') : t('network_offline')}>
              <span className="network-status__dot" />
              <span className="network-status__label">{navigator.onLine !== false ? 'Online' : 'Offline'}</span>
            </div>
            <LanguagePicker />
          </div>
        </div>
      </header>

      {/* Thanh điều hướng chính (Laptop: tab ngang tinh gọn / Mobile: Bottom Navigation Bar) */}
      <nav className="nav-container" aria-label={t('nav_main_aria')}>
        <div className="nav-tabs" role="tablist">
          {TAB.map((muc) => {
            const isActive = tab === muc.ma
            const Icon = muc.icon
            return (
              <button
                key={muc.ma}
                type="button"
                role="tab"
                aria-selected={isActive}
                aria-label={muc.ma === 'admin' ? `${t('nav_admin')} · ${t('nav_admin')}` : t(muc.khoaTen)}
                className={`nav-tab-item${isActive ? ' nav-tab-item--active' : ''}`}
                onClick={() => {
                  if (muc.ma === 'admin' || muc.ma === 'chu-quan') {
                    vaoCong(muc.ma)
                    return
                  }
                  chuyenTab(muc.ma)
                }}
              >
                <span className="nav-tab-item__icon" aria-hidden="true">
                  <Icon />
                </span>
                <span className="nav-tab-item__label">{t(muc.khoaTen)}</span>
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
            {t('startup_working', {
              content: khoiDong.noiDungSanSang ? t('startup_ready') : t('startup_loading'),
              interface: khoiDong.uiSanSang ? t('startup_ready') : t('startup_loading'),
            })}
          </div>
        )}

        {/* Floating Glass Pill: Thanh phát âm thanh hiện đại, không đẩy lệch bố cục trang */}
        {dangDoc !== null && (
          <div className="audio-playing-bar" role="status" aria-live="polite">
            <div className="audio-playing-bar__wave" aria-hidden="true">
              <span className="wave-bar" />
              <span className="wave-bar" />
              <span className="wave-bar" />
            </div>
            <span className="audio-playing-bar__text">
              {t('audio_playing_prefix')}<strong>{dangDoc}</strong>
            </span>
            <button
              type="button"
              className="btn-icon btn-icon--sm"
              onClick={() => { stopPlayback(); setDangDoc(null) }}
              title={t('close_audio')}
              aria-label={t('close_audio')}
            >
              <CloseIcon />
            </button>
          </div>
        )}

        <Suspense fallback={<div className="notice notice--info">{t('suspense_loading')}</div>}>
          {tab === 'admin' && <AdminApp onPoisChanged={fetchPOIs} />}
          {tab === 'chu-quan' && <OwnerApp />}
          {tab === 'goi-offline' && <OfflinePacks pack={pack} />}
          {tab === 'cai-dat' && <Settings pack={pack} />}

          {tab === 'kham-pha' && (
            <div className="kham-pha-layout">
              {/* Lỗi hoặc trạng thái rỗng */}
              {loading && <div className="notice notice--info mb">{t('explore_loading')}</div>}
              {error !== '' && (
                <div className="notice notice--error mb">
                  {t('explore_error', { error })}
                </div>
              )}
              {!loading && error === '' && pois.length === 0 && (
                <div className="notice notice--warn mb">
                  {t('no_public_pois')}
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
                        onNghe={() => nghePoi(dangChon.id)}
                        onDong={dongChiTiet}
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
          <p>{t('brand_subtitle')}</p>
        </footer>
      )}
    </div>
  )
}

function PortalPage({ portal }: { portal: 'admin' | 'owner' }) {
  const isAdmin = portal === 'admin'

  if (isAdmin) {
    return (
      <div className="portal-page portal-page--admin">
        <main className="admin-login-layout">
          <section className="admin-login-main">
            <a className="admin-login-mobile-brand" href="/" aria-label="Về trang chủ Ẩm Thực Quận 4">
              <span className="admin-login-mobile-brand__mark" aria-hidden="true">A</span>
              <span>Ẩm Thực Quận 4</span>
            </a>
            <div className="admin-login-form">
              <Suspense fallback={<div className="notice notice--info">Đang tải cổng đăng nhập…</div>}>
                <AdminApp onPoisChanged={() => void usePoiStore.getState().fetchPOIs()} />
              </Suspense>
            </div>
            <footer className="admin-login-footer">
              <span>© 2026 Ẩm Thực Quận 4</span>
              <a href="/">Về trang khám phá</a>
            </footer>
          </section>
          <aside className="admin-login-art" aria-label="Cổng quản trị hệ thống">
            <svg className="admin-login-art__waves" viewBox="0 0 640 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
              <path d="M-80 250C100 120 160 370 320 240S520 130 720 260" />
              <path d="M-100 300C80 170 170 420 340 290S540 170 740 310" />
              <path d="M-90 360C90 230 180 480 350 350S550 220 730 370" />
              <path d="M-80 430C80 300 180 560 360 420S540 310 720 450" />
              <path d="M-70 520C100 370 190 650 380 500S560 390 720 530" />
              <path d="M-80 620C90 470 200 730 390 590S560 480 730 620" />
              <path d="M-70 720C90 570 210 820 400 690S570 570 730 720" />
              <path d="M-90 810C100 660 220 900 410 780S570 670 740 810" />
            </svg>
            <div className="admin-login-art__content">
              <div className="admin-login-art__brand">
                <span className="admin-login-art__brand-mark" aria-hidden="true">A</span>
                <span>Ẩm Thực Quận 4</span>
              </div>
              <div className="admin-login-art__message">
                <span className="admin-login-art__eyebrow">CỔNG QUẢN TRỊ</span>
                <h1>Vận hành dễ dàng,<br />trải nghiệm trọn vẹn.</h1>
                <p>Quản lý điểm đến, nội dung và hành trình khám phá ẩm thực Quận 4 tại một nơi.</p>
              </div>
              <div className="admin-login-art__dots" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            </div>
          </aside>
        </main>
      </div>
    )
  }

  return (
    <div className="portal-page portal-page--owner">
      <main className="owner-login-layout">
        <aside className="owner-login-art" aria-label="Đồng hành cùng quán ngon Quận 4">
          <div className="owner-login-art__top">
            <a className="owner-login-art__brand" href="/" aria-label="Về trang chủ Ẩm Thực Quận 4">
              <span className="owner-login-art__brand-mark" aria-hidden="true">A</span>
              <span>Ẩm Thực Quận 4</span>
            </a>
            <span className="owner-login-art__tag">GÓC BẾP ĐỊA PHƯƠNG</span>
          </div>
          <svg className="owner-login-art__illustration" viewBox="0 0 520 420" fill="none" aria-hidden="true">
            <ellipse cx="260" cy="337" rx="177" ry="25" fill="#12243D" fillOpacity=".16" />
            <path d="M101 211c7 97 70 153 159 153s152-56 159-153H101Z" fill="#F6E8C9" />
            <path d="M103 211c7 97 70 153 157 153 89 0 152-56 159-153H103Z" stroke="#E4D2AB" strokeWidth="5" />
            <ellipse cx="260" cy="211" rx="159" ry="42" fill="#FFF8E9" stroke="#E4D2AB" strokeWidth="5" />
            <ellipse cx="260" cy="207" rx="139" ry="28" fill="#B9472D" />
            <path d="M145 206c25-25 46 22 70-2 22-21 38-25 58-2 17 20 34 14 49-3 15-17 37-21 55 5" stroke="#F0B35B" strokeWidth="9" strokeLinecap="round" />
            <circle cx="206" cy="197" r="13" fill="#F1D77A" />
            <circle cx="303" cy="211" r="12" fill="#F1D77A" />
            <path d="M178 169c-17-24-9-46 12-61 7 25 3 45-12 61Zm58-12c-4-31 13-51 42-58-3 30-18 50-42 58Zm66 4c4-26 22-39 49-37-8 26-25 39-49 37Z" fill="#7D9BC4" />
            <path d="M176 170c17-17 26-34 34-56m26 43c11-18 21-35 42-54m24 56c10-15 20-25 39-35" stroke="#D3DEEF" strokeWidth="4" strokeLinecap="round" />
            <path d="M93 130c-36-14-49-43-39-79 32 19 46 45 39 79Zm336 8c14-36 42-51 78-42-17 33-43 48-78 42ZM97 287c-39 3-65-17-72-55 38 7 62 26 72 55Zm327-7c27-29 59-33 91-11-29 24-59 28-91 11Z" fill="#D9804E" />
            <path d="M94 129c-13-24-24-43-39-65m375 73c20-17 39-29 64-37M97 286c-24-17-42-32-59-54m386 48c22-14 41-22 66-26" stroke="#F4C39A" strokeWidth="4" strokeLinecap="round" />
            <path d="M118 109c-8-28-1-49 22-66 11 29 4 51-22 66Zm288 12c12-29 34-41 64-36-12 29-34 41-64 36Z" fill="#7D9BC4" />
            <circle cx="125" cy="222" r="5" fill="#E4B85F" />
            <circle cx="386" cy="221" r="5" fill="#E4B85F" />
          </svg>
          <div className="owner-login-art__message">
            <span className="owner-login-art__eyebrow">CÂU CHUYỆN CỦA BẠN</span>
            <h1>Mỗi quán ngon<br />đều có một câu chuyện.</h1>
            <p>Chia sẻ hương vị và dấu ấn riêng của quán bạn với những người yêu ẩm thực Quận 4.</p>
          </div>
          <div className="owner-login-art__bottom">
            <span>Vị ngon địa phương · Kết nối gần hơn</span>
            <span className="owner-login-art__spark" aria-hidden="true">✳</span>
          </div>
        </aside>
        <section className="owner-login-main">
          <header className="owner-login-main__header">
            <a href="/">← Trang khám phá</a>
            <span>Đội ngũ vận hành? <a href="/admin/login">Đăng nhập Admin</a></span>
          </header>
          <div className="owner-login-form">
            <Suspense fallback={<div className="notice notice--info">Đang tải cổng đăng nhập…</div>}>
              <OwnerApp />
            </Suspense>
          </div>
          <footer className="owner-login-main__footer">
            <span>© 2026 Ẩm Thực Quận 4</span>
            <span>Phát triển cùng cộng đồng địa phương</span>
          </footer>
        </section>
      </main>
    </div>
  )
}

function App() {
  const [path, setPath] = useState(() => window.location.pathname.replace(/\/+$/, '') || '/')

  useEffect(() => {
    const syncPath = () => setPath(window.location.pathname.replace(/\/+$/, '') || '/')
    window.addEventListener('popstate', syncPath)
    return () => window.removeEventListener('popstate', syncPath)
  }, [])

  if (path === '/admin/login') return <PortalPage portal="admin" />
  if (path === '/owner/login') return <PortalPage portal="owner" />
  if (path === '/admin' || path.startsWith('/admin/')) {
    return (
      <Suspense fallback={<div className="notice notice--info">Đang tải cổng quản trị…</div>}>
        <AdminApp onPoisChanged={() => void usePoiStore.getState().fetchPOIs()} />
      </Suspense>
    )
  }
  if (path === '/owner' || path.startsWith('/owner/')) {
    return (
      <Suspense fallback={<div className="notice notice--info">Đang tải cổng chủ quán…</div>}>
        <OwnerApp />
      </Suspense>
    )
  }
  return <MainApp />
}

export default App
