import { useState } from 'react'
import { layUrlAnh } from './imageUtils'
import { usePoiStore } from '../stores/poiStore'
import { useUiBundle } from '../i18n/bundles'

interface PoiGalleryProps {
  images?: string[]
  poiName: string
}

function ChevronLeftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}

export function PoiGallery({ images = [], poiName }: PoiGalleryProps) {
  const [viTriChon, setViTriChon] = useState(0)
  const [anhLoi, setAnhLoi] = useState<Record<number, boolean>>({})
  const lang = usePoiStore((state) => state.lang)
  const { t } = useUiBundle(lang)

  // Nếu không có ảnh nào được tải lên
  if (!images || images.length === 0) {
    return (
      <div className="poi-gallery poi-gallery--empty" aria-label={t('gallery_empty_aria', { name: poiName })}>
        <div className="poi-gallery__placeholder">
          <svg className="poi-gallery__placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
          </svg>
          <span className="poi-gallery__placeholder-text">{t('gallery_empty')}</span>
        </div>
      </div>
    )
  }

  const chiSoHienTai = viTriChon < images.length ? viTriChon : 0
  const urlHienTai = layUrlAnh(images[chiSoHienTai])
  const biLoi = anhLoi[chiSoHienTai]

  const chuyenSau = () => {
    setViTriChon((prev) => (prev + 1) % images.length)
  }

  const chuyenTruoc = () => {
    setViTriChon((prev) => (prev - 1 + images.length) % images.length)
  }

  return (
    <div className="poi-gallery" aria-label={t('gallery_aria', { name: poiName })}>
      {/* Khung ảnh chính */}
      <div className="poi-gallery__main">
        {!biLoi ? (
          <img
            {...{ src: urlHienTai }}
            alt={`${poiName} - ${t('gallery_thumbnail', { number: chiSoHienTai + 1 })}`}
            className="poi-gallery__img"
            loading="lazy"
            onError={() => setAnhLoi((prev) => ({ ...prev, [chiSoHienTai]: true }))}
          />
        ) : (
          <div className="poi-gallery__placeholder">
            <svg className="poi-gallery__placeholder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
            </svg>
            <span className="poi-gallery__placeholder-text">{t('gallery_error')}</span>
          </div>
        )}

        {/* Nút điều hướng trước/sau khi có từ 2 ảnh */}
        {images.length > 1 && (
          <>
            <button
              type="button"
              className="poi-gallery__nav-btn poi-gallery__nav-btn--prev"
              onClick={chuyenTruoc}
              aria-label={t('gallery_previous')}
            >
              <ChevronLeftIcon />
            </button>
            <button
              type="button"
              className="poi-gallery__nav-btn poi-gallery__nav-btn--next"
              onClick={chuyenSau}
              aria-label={t('gallery_next')}
            >
              <ChevronRightIcon />
            </button>
            <div className="poi-gallery__counter">
              {chiSoHienTai + 1} / {images.length}
            </div>
          </>
        )}
      </div>

      {/* Dải thumbnail xem nhanh */}
      {images.length > 1 && (
        <div className="poi-gallery__thumbs" role="tablist" aria-label={t('gallery_thumbnails')}>
          {images.map((imgUrl, idx) => {
            const isSelected = idx === chiSoHienTai
            const thumbUrl = layUrlAnh(imgUrl)
            return (
              <button
                key={imgUrl + idx}
                type="button"
                role="tab"
                aria-selected={isSelected}
                className={`poi-gallery__thumb${isSelected ? ' poi-gallery__thumb--active' : ''}`}
                onClick={() => setViTriChon(idx)}
              >
                <img
                  {...{ src: thumbUrl }}
                  alt={t('gallery_thumbnail', { number: idx + 1 })}
                  className="poi-gallery__thumb-img"
                  loading="lazy"
                  onError={(e) => {
                    ;(e.currentTarget as HTMLImageElement).style.opacity = '0.3'
                  }}
                />
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
export default PoiGallery
