import { NGON_NGU, usePoiStore } from '../stores/poiStore'
import { useUiBundle } from '../i18n/bundles'

function InfoIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
}

export default function LanguagePicker() {
  const { lang, setLang, pois } = usePoiStore()
  const { t } = useUiBundle(lang)
  const duPhong = pois.some((p) => p.is_fallback)

  return (
    <div className="language-bar" aria-label={t('home_language_aria')}>
      <div className="language-bar__scroll" role="group">
        {NGON_NGU.map((n) => {
          const isSelected = n.ma === lang
          return (
            <button
              key={n.ma}
              type="button"
              className={`lang-chip${isSelected ? ' lang-chip--active' : ''}`}
              disabled={isSelected}
              onClick={() => setLang(n.ma)}
              aria-label={n.ten}
              title={n.ten}
            >
              <span className="lang-chip__code" aria-hidden="true">
                {n.ma.toUpperCase()}
              </span>
              <span className="lang-chip__label">{n.ten}</span>
            </button>
          )
        })}
      </div>
      {duPhong && (
        <div className="language-fallback-hint" title={t('lang_note_fallback')}>
          <span className="language-fallback-icon" aria-hidden="true">
            <InfoIcon />
          </span>
          <span className="sr-only">{t('lang_note_fallback')}</span>
        </div>
      )}
    </div>
  )
}
