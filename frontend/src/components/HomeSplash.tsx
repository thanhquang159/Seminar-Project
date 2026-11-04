import { usePoiStore } from '../stores/poiStore'
import { useViTri } from '../geofence/useViTri'
import { useStartup } from '../startup'

interface HomeSplashProps {
  onStart: () => void
  onOffline: () => void
  onNavigate?: (tab: 'kham-pha' | 'admin' | 'chu-quan' | 'goi-offline' | 'cai-dat') => void
}

interface LanguageOption {
  code: string
  name: string
  subtext: string
}

const LANGUAGES: LanguageOption[] = [
  { code: 'vi', name: 'Tiếng Việt', subtext: 'Bản địa Q.4' },
  { code: 'en', name: 'English', subtext: 'Local Foodie' },
  { code: 'zh', name: '中文', subtext: '第4郡美食' },
  { code: 'ja', name: '日本語', subtext: '屋台グルメ' },
  { code: 'ko', name: '한국어', subtext: '미식 골목' },
]

/* =========================================================================
   Inline SVG Icons nét mảnh (strokeWidth="1.75")
   ========================================================================= */

function CompassIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  )
}

function HeadphonesIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
      <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
    </svg>
  )
}

function OfflineIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

function LanternEmblem() {
  return (
    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="12" y1="2" x2="12" y2="5" />
      <rect x="5" y="5" width="14" height="13" rx="4" />
      <line x1="9" y1="5" x2="9" y2="18" />
      <line x1="15" y1="5" x2="15" y2="18" />
      <line x1="10" y1="18" x2="10" y2="22" />
      <line x1="14" y1="18" x2="14" y2="22" />
    </svg>
  )
}

function ArrowRightIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

export default function HomeSplash({ onStart, onOffline, onNavigate }: HomeSplashProps) {
  const { lang, setLang, pois, loading } = usePoiStore()
  const viTri = useViTri()
  const khoiDong = useStartup()

  // Tiến trình sẵn sàng hệ thống
  let progress = 65
  if (viTri) progress += 15
  if (pois.length > 0 && !loading) progress += 10
  if (khoiDong.uiSanSang) progress += 10
  if (progress > 100) progress = 100

  return (
    <div className="home-hero-container">
      {/* Centered Minimalist Hero Canvas */}
      <div className="home-hero-card">
        {/* 1. Header Badges: PWA Offline-First & GPS Status */}
        <div className="home-hero-header">
          <span className="badge badge--neutral">
            <span className="pulse-dot" />
            PWA Offline-First · v2.1
          </span>
          <span className={`badge ${viTri ? 'badge--ok' : 'badge--neutral'}`}>
            <span className={`pulse-dot ${viTri ? 'pulse-dot--active' : ''}`} />
            {viTri ? 'GPS Đã định vị' : 'Đang tìm GPS'}
          </span>
        </div>

        {/* 2. Hero Brand Section */}
        <section className="home-hero-brand">
          <div className="home-hero-logo" aria-hidden="true">
            <LanternEmblem />
          </div>

          <div className="home-hero-tagline">
            <span className="badge badge--accent">
              Phố ẩm thực Vĩnh Khánh &amp; Quận 4
            </span>
          </div>

          <h1 className="home-hero-title">
            Ẩm Thực Quận 4
          </h1>
          <p className="home-hero-desc">
            Hướng dẫn du lịch ẩm thực đường phố Quận 4 với bản đồ số thông minh và thuyết minh âm thanh tự động theo vị trí bước chân.
          </p>
        </section>

        {/* 3. Three Core Pillars (3 gạch đầu dòng tính năng cốt lõi) */}
        <section className="home-hero-features" aria-label="Tính năng chính">
          <div className="home-feature-item">
            <div className="home-feature-icon">
              <CompassIcon />
            </div>
            <div className="home-feature-text">
              <strong>Bản đồ định vị GPS</strong>
              <span>Dẫn lối qua các ngõ hẻm ốc, phá lấu, bánh tráng nướng</span>
            </div>
          </div>

          <div className="home-feature-item">
            <div className="home-feature-icon">
              <HeadphonesIcon />
            </div>
            <div className="home-feature-text">
              <strong>Thuyết minh tự động</strong>
              <span>Tự động phát audio thuyết minh khi bạn tới gần từng quán</span>
            </div>
          </div>

          <div className="home-feature-item">
            <div className="home-feature-icon">
              <OfflineIcon />
            </div>
            <div className="home-feature-text">
              <strong>Ngoại tuyến 100%</strong>
              <span>Hoạt động mượt mà không cần mạng Internet hay 4G</span>
            </div>
          </div>
        </section>

        {/* 4. Minimalist Language Selector Chips */}
        <section className="home-hero-languages" aria-label="Chọn ngôn ngữ">
          <div className="home-section-label">
            <span>Ngôn ngữ thuyết minh / Language</span>
            <span className="badge badge--neutral" style={{ fontSize: '0.72rem' }}>5 Bản ngữ</span>
          </div>

          <div className="home-lang-grid" role="group">
            {LANGUAGES.map((item) => {
              const isSelected = lang === item.code
              return (
                <button
                  key={item.code}
                  type="button"
                  onClick={() => setLang(item.code)}
                  className={`home-lang-btn${isSelected ? ' home-lang-btn--active' : ''}`}
                  aria-pressed={isSelected}
                >
                  <div className="home-lang-btn__left">
                    <span className="home-lang-btn__code">{item.code.toUpperCase()}</span>
                    <span className="home-lang-btn__name">{item.name}</span>
                  </div>
                  {isSelected && (
                    <span className="home-lang-btn__check" aria-hidden="true">
                      <CheckIcon />
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </section>

        {/* 5. Minimalist System Warmup Status */}
        <div className="home-warmup-status">
          <div className="home-warmup-bar">
            <div className="home-warmup-fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="home-warmup-info">
            <span>Khởi tạo hệ thống ({progress}%)</span>
            <span>{pois.length > 0 ? `${pois.length} quán đã nạp` : 'Đang đồng bộ dữ liệu…'}</span>
          </div>
        </div>

        {/* 6. Primary Action Buttons (2 CTA buttons) */}
        <div className="home-hero-actions">
          <button
            type="button"
            onClick={onStart}
            className="btn btn--primary btn--lg btn--block"
          >
            <span>Bắt đầu khám phá</span>
            <ArrowRightIcon />
          </button>

          <button
            type="button"
            onClick={onOffline}
            className="btn btn--secondary btn--lg btn--block"
          >
            <OfflineIcon />
            <span>Tải dữ liệu Offline</span>
          </button>
        </div>

        {/* 7. Secondary Footer Navigation */}
        {onNavigate && (
          <nav className="home-secondary-nav" aria-label="Liên kết phụ">
            <button
              type="button"
              onClick={() => onNavigate('chu-quan')}
              className="home-nav-link"
            >
              Chủ quán
            </button>
            <span className="home-nav-divider">·</span>
            <button
              type="button"
              onClick={() => onNavigate('admin')}
              className="home-nav-link"
            >
              Quản trị
            </button>
            <span className="home-nav-divider">·</span>
            <button
              type="button"
              onClick={() => onNavigate('goi-offline')}
              className="home-nav-link"
            >
              Gói offline
            </button>
            <span className="home-nav-divider">·</span>
            <button
              type="button"
              onClick={() => onNavigate('cai-dat')}
              className="home-nav-link"
            >
              Cài đặt
            </button>
          </nav>
        )}
      </div>
    </div>
  )
}
