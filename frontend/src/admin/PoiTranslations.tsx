import { useEffect, useMemo, useState } from 'react'
import type { Poi } from '../stores/poiStore'
import { api } from './api'

interface MissingTranslation {
  poi_id: string
  lang: string
}

interface MissingTranslationResponse {
  tong: number
  thieu: MissingTranslation[]
}

const NGON_NGU_DICH = [
  { code: 'en', name: 'English' },
  { code: 'zh', name: '中文' },
  { code: 'ja', name: '日本語' },
  { code: 'ko', name: '한국어' },
]

interface PoiTranslationsProps {
  pois: Poi[]
  onSaved: () => Promise<void>
}

export default function PoiTranslations({ pois, onSaved }: PoiTranslationsProps) {
  const [missing, setMissing] = useState<MissingTranslation[]>([])
  const [lang, setLang] = useState('zh')
  const [poiId, setPoiId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    void api<MissingTranslationResponse>('/localizations/warmup-status')
      .then((response) => {
        if (!active) return
        const publicPoiIds = new Set(pois.map((item) => item.id))
        const supported = response.thieu.filter((item) =>
          publicPoiIds.has(item.poi_id)
          && NGON_NGU_DICH.some((language) => language.code === item.lang),
        )
        setMissing(supported)
        const firstMissing = supported[0]
        if (firstMissing) {
          setLang(firstMissing.lang)
          setPoiId(firstMissing.poi_id)
        } else if (pois.length > 0) {
          setPoiId(pois[0].id)
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : 'Không tải được danh sách bản dịch.')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [pois])

  const poi = pois.find((item) => item.id === poiId) ?? null
  const pendingForLanguage = useMemo(
    () => missing.filter((item) => item.lang === lang),
    [lang, missing],
  )

  const changeLanguage = (nextLang: string) => {
    setLang(nextLang)
    const firstMissing = missing.find((item) => item.lang === nextLang)
    setPoiId(firstMissing?.poi_id ?? pois[0]?.id ?? '')
    setName('')
    setDescription('')
    setNotice('')
  }

  const saveTranslation = async () => {
    if (!poi || name.trim() === '' || saving) return
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await api('/localizations/on-demand', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          poi_id: poi.id,
          lang,
          name: name.trim(),
          description: description.trim(),
        }),
      })
      setMissing((current) =>
        current.filter((item) => item.poi_id !== poi.id || item.lang !== lang),
      )
      setName('')
      setDescription('')
      setNotice(`Đã lưu bản dịch ${lang.toUpperCase()} cho ${poi.name}.`)
      await onSaved()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không lưu được bản dịch.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="card admin-translations">
      <header className="section-header">
        <div>
          <h2 className="card__title">Bổ sung bản dịch POI</h2>
          <p className="card__subtitle">
            Nhập bản dịch đã được kiểm tra. Nội dung được lưu trong hệ thống và không gửi đến dịch vụ bên ngoài.
          </p>
        </div>
        <span className="badge badge--neutral">
          {pendingForLanguage.length} POI còn thiếu {lang.toUpperCase()}
        </span>
      </header>

      {loading ? (
        <p className="muted mt" role="status">Đang tải danh sách POI cần dịch…</p>
      ) : (
        <>
          <div className="admin-translations__form mt">
            <div className="field">
              <label className="field__label" htmlFor="poi-translation-language">Ngôn ngữ đích</label>
              <select
                id="poi-translation-language"
                className="input"
                value={lang}
                onChange={(event) => changeLanguage(event.target.value)}
              >
                {NGON_NGU_DICH.map((language) => (
                  <option key={language.code} value={language.code}>{language.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field__label" htmlFor="poi-translation-place">Địa điểm</label>
              <select
                id="poi-translation-place"
                className="input"
                value={poiId}
                onChange={(event) => {
                  setPoiId(event.target.value)
                  setName('')
                  setDescription('')
                  setNotice('')
                }}
              >
                {pois.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </div>
          </div>

          {poi ? (
            <div className="admin-translations__source mt">
              <h3 className="card__title">Nội dung gốc (tiếng Việt)</h3>
              <strong>{poi.name}</strong>
              <p>{poi.description || 'Chưa có mô tả.'}</p>
            </div>
          ) : (
            <p className="notice notice--info mt">Không có POI công khai để dịch.</p>
          )}

          <div className="field mt">
            <label className="field__label" htmlFor="poi-translation-name">Tên POI đã dịch *</label>
            <input
              id="poi-translation-name"
              className="input"
              maxLength={200}
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="poi-translation-description">Mô tả đã dịch</label>
            <textarea
              id="poi-translation-description"
              className="input textarea"
              rows={4}
              maxLength={5000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>

          <button
            className="btn btn--primary"
            type="button"
            disabled={!poi || name.trim() === '' || saving}
            onClick={() => void saveTranslation()}
          >
            {saving ? 'Đang lưu…' : 'Lưu bản dịch'}
          </button>
        </>
      )}

      {error && <div className="notice notice--error mt" role="alert">{error}</div>}
      {notice && <div className="notice notice--ok mt" role="status">{notice}</div>}
    </section>
  )
}
