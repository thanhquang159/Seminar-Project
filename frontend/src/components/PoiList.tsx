import { useState } from 'react'
import type { Poi } from '../stores/poiStore'
import { layUrlAnh } from './imageUtils'
import { PoiGallery } from './PoiGallery'

// OWN-005: tên quán và mô tả là dữ liệu chủ quán gửi lên — tức là nội dung
// không đáng tin. Ở đây chỉ đặt chúng vào vị trí text của JSX (React escape sẵn),
// tuyệt đối không đưa vào HTML dạng thô. `PoiList.test.tsx` kiểm đúng điều đó.

function LocationPinIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ marginRight: '4px', verticalAlign: 'text-bottom' }}>
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  )
}

function VolumeIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

interface DanhSachProps {
  pois: Poi[]
  selectedId?: string | null
  onChon: (id: string) => void
}

export function PoiList({ pois, selectedId, onChon }: DanhSachProps) {
  const [anhLoiMap, setAnhLoiMap] = useState<Record<string, boolean>>({})

  return (
    <div className="poi-list-section">
      <div className="section-header">
        <h2 className="section-title">Danh sách điểm ẩm thực</h2>
        <span className="badge badge--neutral">{pois.length} quán ăn</span>
      </div>

      {pois.length === 0 ? (
        <div className="empty-state">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--amds-text-faint)' }}>
            <circle cx="12" cy="12" r="10" />
            <line x1="8" y1="12" x2="16" y2="12" />
          </svg>
          <p className="muted">Chưa có điểm ẩm thực nào trong danh sách.</p>
        </div>
      ) : (
        <ul className="poi-list" role="list">
          {pois.map((poi) => {
          const isSelected = selectedId === poi.id
          const coAnh = poi.images && poi.images.length > 0 && !anhLoiMap[poi.id]
          const anhDau = coAnh ? layUrlAnh(poi.images![0]) : null

          return (
            <li key={poi.id} className="poi-item">
              <button
                type="button"
                className={`poi-card poi-btn${isSelected ? ' poi-card--selected' : ''}`}
                onClick={() => onChon(poi.id)}
              >
                {/* Ảnh đại diện nếu có, nếu không thì dùng icon ẩm thực SVG (không dùng thẻ img để giữ test sạch) */}
                <div className="poi-card__media">
                  {coAnh && anhDau ? (
                    <img
                      {...{ src: anhDau }}
                      alt=""
                      className="poi-card__thumb"
                      loading="lazy"
                      onError={() => setAnhLoiMap((prev) => ({ ...prev, [poi.id]: true }))}
                    />
                  ) : (
                    <div className="poi-card__media-placeholder" aria-hidden="true">
                      <svg className="poi-card__media-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                      </svg>
                    </div>
                  )}
                  {coAnh && (
                    <span className="poi-card__img-count" title={`${poi.images!.length} ảnh`}>
                      {poi.images!.length}
                    </span>
                  )}
                </div>

                <div className="poi-card__content">
                  <div className="poi-card__top">
                    <h3 className="poi-card__name">{poi.name}</h3>
                    <span className="poi-card__arrow" aria-hidden="true">›</span>
                  </div>

                  <p className="poi-card__desc">{poi.description}</p>

                  <div className="poi-card__meta">
                    <span className="poi-card__tag">
                      <LocationPinIcon />
                      {poi.trigger_radius}m
                    </span>
                    {poi.audio_url && (
                      <span className="poi-card__tag poi-card__tag--audio">
                        <VolumeIcon />
                        Thuyết minh
                      </span>
                    )}
                  </div>
                </div>
              </button>
            </li>
          )
        })}
        </ul>
      )}
    </div>
  )
}

interface ChiTietProps {
  poi: Poi
  onNghe: (id: string) => void
  onDong?: () => void
}

export function PoiDetail({ poi, onNghe, onDong }: ChiTietProps) {
  return (
    <section className="card poi-detail-card" aria-label="Chi tiết điểm tham quan">
      {/* Nút đóng nếu được nhúng trong modal / bottom sheet / panel */}
      {onDong && (
        <button
          type="button"
          className="poi-detail__close-btn btn-icon btn-icon--sm"
          onClick={onDong}
          title="Đóng chi tiết quán"
          aria-label="Đóng chi tiết quán"
        >
          <CloseIcon />
        </button>
      )}

      {/* Thư viện ảnh quán ăn */}
      <PoiGallery images={poi.images} poiName={poi.name} />

      <div className="poi-detail__header mt">
        <div className="spread">
          <h2 className="poi-detail__title">{poi.name}</h2>
          {poi.is_fallback && <span className="badge badge--warn">Bản dịch máy tạm</span>}
        </div>

        <div className="poi-detail__badges">
          <span className="badge badge--neutral">
            <LocationPinIcon />
            {poi.lat.toFixed(4)}, {poi.lng.toFixed(4)}
          </span>
          <span className="badge badge--info">
            Vùng phát: {poi.trigger_radius} m
          </span>
          {poi.images && poi.images.length > 0 && (
            <span className="badge badge--accent">
              {poi.images.length} ảnh thực tế
            </span>
          )}
        </div>
      </div>

      <div className="poi-detail__body mt">
        <h4 className="poi-detail__section-heading">Giới thiệu quán ăn</h4>
        <p className="poi-detail__description">{poi.description}</p>
      </div>

      <div className="poi-detail__actions mt">
        <div className="poi-detail__audio-box">
          <div className="poi-detail__audio-header">
            <span className="poi-detail__audio-label">Thuyết minh GPS đa ngôn ngữ</span>
            {poi.is_fallback ? (
              <span className="badge badge--warn">Bản dịch máy tạm</span>
            ) : (
              <span className="badge badge--ok">Bản địa</span>
            )}
          </div>
          <button
            className="btn btn--primary btn--lg btn--block"
            type="button"
            onClick={() => onNghe(poi.id)}
          >
            <svg className="btn__icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Nghe thuyết minh hướng dẫn
          </button>
        </div>
      </div>
    </section>
  )
}
