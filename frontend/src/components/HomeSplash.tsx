import { usePoiStore } from '../stores/poiStore'
import { useViTri } from '../geofence/useViTri'
import { useUiBundle } from '../i18n/bundles'

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
  const { t, sanSang: uiSanSang } = useUiBundle(lang)
  const viTri = useViTri()

  // Tiến trình sẵn sàng hệ thống
  let progress = 65
  if (viTri) progress += 15
  if (pois.length > 0 && !loading) progress += 10
  if (uiSanSang) progress += 10
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
            {viTri ? t('home_gps_ready') : t('home_gps_searching')}
          </span>
        </div>

        {/* 2. Hero Brand Section */}
        <section className="home-hero-brand">
          <div className="home-hero-logo" aria-hidden="true">
            <LanternEmblem />
          </div>

          <div className="home-hero-tagline">
            <span className="badge badge--accent">
              {t('home_tagline')}
            </span>
          </div>

          <h1 className="home-hero-title">
            {t('home_title')}
          </h1>
          <p className="home-hero-desc">
            {t('home_description')}
          </p>
        </section>

        {/* 3. Three Core Pillars (3 gạch đầu dòng tính năng cốt lõi) */}
        <section className="home-hero-features" aria-label={t('home_features_aria')}>
          <div className="home-feature-item">
            <div className="home-feature-icon">
              <CompassIcon />
            </div>
            <div className="home-feature-text">
              <strong>{t('home_map_feature')}</strong>
              <span>{t('home_map_description')}</span>
            </div>
          </div>

          <div className="home-feature-item">
            <div className="home-feature-icon">
              <HeadphonesIcon />
            </div>
            <div className="home-feature-text">
              <strong>{t('home_audio_feature')}</strong>
              <span>{t('home_audio_description')}</span>
            </div>
          </div>

          <div className="home-feature-item">
            <div className="home-feature-icon">
              <OfflineIcon />
            </div>
            <div className="home-feature-text">
              <strong>{t('home_offline_feature')}</strong>
              <span>{t('home_offline_description')}</span>
            </div>
          </div>
        </section>

        {/* 4. Minimalist Language Selector Chips */}
        <section className="home-hero-languages" aria-label={t('home_language_aria')}>
          <div className="home-section-label">
            <span>{t('home_language_label')}</span>
            <span className="badge badge--neutral" style={{ fontSize: '0.72rem' }}>{t('home_language_count')}</span>
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
            <span>{t('home_progress', { progress })}</span>
            <span>{pois.length > 0 ? t('home_places_loaded', { count: pois.length }) : t('home_syncing')}</span>
          </div>
        </div>

        {/* 6. Primary Action Buttons (2 CTA buttons) */}
        <div className="home-hero-actions">
          <button
            type="button"
            onClick={onStart}
            className="btn btn--primary btn--lg btn--block"
          >
            <span>{t('home_start')}</span>
            <ArrowRightIcon />
          </button>

          <button
            type="button"
            onClick={onOffline}
            className="btn btn--secondary btn--lg btn--block"
          >
            <OfflineIcon />
            <span>{t('home_download_offline')}</span>
          </button>
        </div>

        {/* 7. Secondary Footer Navigation */}
        {onNavigate && (
          <nav className="home-secondary-nav" aria-label={t('home_secondary_aria')}>
            <button
              type="button"
              onClick={() => onNavigate('chu-quan')}
              className="home-nav-link"
            >
              {t('nav_owner')}
            </button>
            <span className="home-nav-divider">·</span>
            <button
              type="button"
              onClick={() => onNavigate('admin')}
              className="home-nav-link"
            >
              {t('nav_admin')}
            </button>
            <span className="home-nav-divider">·</span>
            <button
              type="button"
              onClick={() => onNavigate('goi-offline')}
              className="home-nav-link"
            >
              {t('nav_packs')}
            </button>
            <span className="home-nav-divider">·</span>
            <button
              type="button"
              onClick={() => onNavigate('cai-dat')}
              className="home-nav-link"
            >
              {t('nav_settings')}
            </button>
          </nav>
        )}
      </div>
    </div>
  )
}
