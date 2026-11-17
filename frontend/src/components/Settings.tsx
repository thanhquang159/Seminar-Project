import { useState } from 'react'
import { NGON_NGU, usePoiStore } from '../stores/poiStore'
import { useConsentStore } from '../stores/consentStore'
import { xinDongY, thuHoiDongY } from '../analytics/service'
import { type PackHook, type CheDo } from './useMapPack'
import { useUiBundle } from '../i18n/bundles'

const MA_NGON_NGU: Record<string, string> = {
  vi: 'VI',
  en: 'EN',
  zh: 'ZH',
  ja: 'JA',
  ko: 'KO',
}

interface SettingsProps {
  pack?: PackHook
}

export default function Settings({ pack }: SettingsProps) {
  const { lang, setLang } = usePoiStore()
  const { t } = useUiBundle(lang)
  const trangThaiConsent = useConsentStore((s) => s.trangThai)
  const [dangCapNhatConsent, setDangCapNhatConsent] = useState(false)
  const [loiConsent, setLoiConsent] = useState('')

  const cheDoBanDo = pack ? pack.cheDo : (localStorage.getItem('quan4-mapmode') as CheDo) ?? 'hybrid'

  const doiBanDo = (c: CheDo) => {
    localStorage.setItem('quan4-mapmode', c)
    if (pack) {
      pack.setCheDo(c)
    }
  }

  const doiRiengTu = async (muc: 'granted' | 'revoked') => {
    setDangCapNhatConsent(true)
    setLoiConsent('')
    try {
      if (muc === 'granted') {
        if (!(await xinDongY())) {
          setLoiConsent(t('settings_error_update'))
        }
      } else {
        if (!(await thuHoiDongY())) {
          setLoiConsent(t('settings_error_sync'))
        }
      }
    } catch {
      setLoiConsent(t('settings_error_connection'))
    } finally {
      setDangCapNhatConsent(false)
    }
  }

  return (
    <div className="settings-container">
      <div className="section-header">
        <div>
          <h2 className="section-title">{t('settings_title')}</h2>
          <p className="card__subtitle">{t('settings_description')}</p>
        </div>
      </div>

      {/* 1. Ngôn ngữ nội dung */}
      <div className="card mt">
        <h3 className="card__title">{t('settings_language_title')}</h3>
        <p className="card__subtitle">{t('settings_language_description')}</p>

        <div className="settings-pill-group mt">
          {NGON_NGU.map((n) => {
            const isSelected = n.ma === lang
            return (
              <button
                key={n.ma}
                type="button"
                className={`settings-pill${isSelected ? ' settings-pill--active' : ''}`}
                disabled={isSelected}
                onClick={() => setLang(n.ma)}
              >
                <span className="settings-pill__code">
                  {MA_NGON_NGU[n.ma] || n.ma.toUpperCase()}
                </span>
                <span>{n.ten}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* 2. Chế độ bản đồ */}
      <div className="card mt">
        <h3 className="card__title">{t('settings_map_title')}</h3>
        <p className="card__subtitle">
          {t('settings_map_current')}: <strong>{cheDoBanDo.toUpperCase()}</strong>
          {pack?.trangThai && ` · ${pack.trangThai}`}
        </p>

        <div className="settings-pill-group mt">
          {([
            { ma: 'cloud', ten: t('settings_map_cloud') },
            { ma: 'hybrid', ten: t('settings_map_hybrid') },
            { ma: 'offline', ten: t('settings_map_offline') },
          ] as const).map((c) => {
            const isSelected = c.ma === cheDoBanDo
            return (
              <button
                key={c.ma}
                type="button"
                className={`settings-pill${isSelected ? ' settings-pill--active' : ''}`}
                disabled={isSelected}
                onClick={() => doiBanDo(c.ma)}
              >
                <span>{c.ten}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* 3. Chính sách quyền riêng tư */}
      <div className="card mt">
        <h3 className="card__title">{t('settings_privacy_title')}</h3>
        <p className="card__subtitle">
          {t('settings_privacy_description')}
        </p>
        <p className="card__subtitle">
          {t('settings_privacy_current')}{' '}
          <strong>
            {trangThaiConsent === 'granted'
              ? t('settings_privacy_shared')
              : trangThaiConsent === 'revoked'
              ? t('settings_privacy_blocked')
              : t('settings_privacy_unset')}
          </strong>
        </p>

        <div className="settings-pill-group mt">
          {[
            { ma: 'granted', ten: t('settings_privacy_option_shared') },
            { ma: 'revoked', ten: t('settings_privacy_option_blocked') },
          ].map((m) => {
            const isSelected = m.ma === trangThaiConsent
            return (
              <button
                key={m.ma}
                type="button"
                className={`settings-pill${isSelected ? ' settings-pill--active' : ''}`}
                disabled={isSelected || dangCapNhatConsent}
                onClick={() => void doiRiengTu(m.ma as 'granted' | 'revoked')}
              >
                <span>{m.ten}</span>
              </button>
            )
          })}
        </div>
        {loiConsent !== '' && <div className="notice notice--error mt" role="alert">{loiConsent}</div>}
      </div>
    </div>
  )
}
