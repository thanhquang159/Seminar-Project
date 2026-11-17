import { useEffect, useMemo, useState } from 'react'
import QRCode from 'qrcode'
import './OwnerPoiQrCodes.css'

const PUBLIC_POI_BASE_URL = 'https://seminar-project-tau.vercel.app'

interface OwnerPoi {
  id: string
  name: string
  publication_status: string
  is_active: boolean
}

interface GeneratedQr {
  url: string
  image?: string
  error?: string
}

export default function OwnerPoiQrCodes({ pois }: { pois: OwnerPoi[] }) {
  const [selectedId, setSelectedId] = useState('')
  const [generated, setGenerated] = useState<GeneratedQr>()
  const [isGenerating, setIsGenerating] = useState(false)
  const [notice, setNotice] = useState('')

  const publishedPois = useMemo(
    () => pois.filter((poi) => poi.publication_status === 'published' && poi.is_active),
    [pois],
  )
  const selectedPoi =
    publishedPois.find((poi) => poi.id === selectedId) ?? publishedPois[0]
  const url = selectedPoi
    ? `${PUBLIC_POI_BASE_URL}/${encodeURIComponent(selectedPoi.id)}`
    : ''
  const qrImage = generated?.url === url ? generated.image : undefined
  const qrError = generated?.url === url ? generated.error : undefined

  useEffect(() => {
    if (!notice) return
    const timeout = window.setTimeout(() => setNotice(''), 2800)
    return () => window.clearTimeout(timeout)
  }, [notice])

  async function generateQr() {
    if (!url || isGenerating) return
    setGenerated(undefined)
    setNotice('')
    setIsGenerating(true)
    try {
      const image = await QRCode.toDataURL(url, {
        width: 420,
        margin: 2,
        errorCorrectionLevel: 'H',
        color: { dark: '#173b31', light: '#ffffff' },
      })
      setGenerated({ url, image })
    } catch {
      setGenerated({ url, error: 'Không tạo được mã QR. Vui lòng thử lại.' })
    } finally {
      setIsGenerating(false)
    }
  }

  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(url)
      setNotice('Đã sao chép đường dẫn POI.')
    } catch {
      setNotice('Không thể sao chép tự động. Bạn có thể chọn và sao chép đường dẫn bên dưới.')
    }
  }

  function downloadQr() {
    if (!qrImage || !selectedPoi) return
    const link = document.createElement('a')
    link.href = qrImage
    link.download = `poi-${selectedPoi.id}-qr.png`
    link.click()
    setNotice('Đã tải mã QR PNG.')
  }

  return (
    <section className="card dashboard-content-card owner-qr-management">
      <div className="section-header">
        <div>
          <h2 className="card__title">Mã QR địa điểm</h2>
          <p className="card__subtitle">
            Chọn POI đã được Admin duyệt để tạo mã dẫn thẳng đến trang khám phá.
          </p>
        </div>
      </div>

      {publishedPois.length === 0 ? (
        <div className="empty-state" role="status">
          <p className="muted">
            Chưa có POI nào được duyệt và đang hiển thị. Mã QR sẽ sẵn sàng sau khi POI được duyệt.
          </p>
        </div>
      ) : (
        <div className="owner-qr-layout">
          <div className="owner-qr-list" role="group" aria-label="POI đã được duyệt">
            <p className="owner-qr-list__label">POI CỦA BẠN</p>
            {publishedPois.map((poi) => (
              <button
                className={`owner-qr-poi${selectedPoi?.id === poi.id ? ' owner-qr-poi--selected' : ''}`}
                key={poi.id}
                type="button"
                aria-pressed={selectedPoi?.id === poi.id}
                disabled={isGenerating}
                onClick={() => setSelectedId(poi.id)}
              >
                <span className="owner-qr-poi__icon" aria-hidden="true">
                  <svg viewBox="0 0 20 20" fill="none">
                    <path d="M16.2 8.3c0 4.4-6.2 9-6.2 9s-6.2-4.6-6.2-9a6.2 6.2 0 1 1 12.4 0Z" stroke="currentColor" strokeWidth="1.5" />
                    <circle cx="10" cy="8" r="2" stroke="currentColor" strokeWidth="1.5" />
                  </svg>
                </span>
                <span className="owner-qr-poi__copy">
                  <strong>{poi.name}</strong>
                  <small>{poi.id}</small>
                </span>
                <span className="badge badge--ok">Đã duyệt</span>
              </button>
            ))}
          </div>

          {selectedPoi && (
            <div className="owner-qr-result">
              <div className="owner-qr-preview">
                {qrImage ? (
                  <img src={qrImage} alt={`Mã QR cho ${selectedPoi.name}`} />
                ) : (
                  <p className="muted" role={qrError ? 'alert' : 'status'} aria-live="polite">
                    {qrError ?? (isGenerating ? 'Đang tạo mã QR…' : 'Nhấn “Tạo mã QR” để tạo mã cho POI này.')}
                  </p>
                )}
              </div>
              <strong className="owner-qr-result__name">{selectedPoi.name}</strong>
              <label className="field__label" htmlFor="owner-poi-qr-url">ĐƯỜNG DẪN POI</label>
              <input
                id="owner-poi-qr-url"
                className="input owner-qr-url"
                type="url"
                value={url}
                readOnly
                onFocus={(event) => event.currentTarget.select()}
              />
              <div className="owner-qr-actions">
                <button className="btn btn--primary" type="button" disabled={isGenerating} onClick={() => void generateQr()}>
                  {isGenerating ? 'Đang tạo mã QR…' : qrImage ? 'Tạo lại mã QR' : 'Tạo mã QR'}
                </button>
                <button className="btn btn--secondary" type="button" disabled={!qrImage} onClick={downloadQr}>
                  Tải mã QR PNG
                </button>
                <button className="btn btn--secondary" type="button" onClick={() => void copyUrl()}>
                  Sao chép đường dẫn
                </button>
              </div>
              {notice && <div className="notice notice--info mt" role="status">{notice}</div>}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
