import { useState } from 'react'
import { useConsentStore } from '../stores/consentStore'
import { thuHoiDongY, xinDongY } from '../analytics/service'

function ShieldCheckIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  )
}

// ANA-001 + UI-002: hỏi rõ ràng, cho cả hai lựa chọn, nhớ lựa chọn.
// "Từ chối" phải dễ bấm bằng "Đồng ý" — không tính giá trị của việc đồng ý.
export default function ConsentBanner() {
  const trangThai = useConsentStore((s) => s.trangThai)
  const tracked = useConsentStore((s) => s.trackedOnlineUsers)
  const [dangCapNhat, setDangCapNhat] = useState(false)
  const [loi, setLoi] = useState('')

  const batChiaSe = async () => {
    if (dangCapNhat) return
    setDangCapNhat(true)
    setLoi('')
    try {
      if (!(await xinDongY())) {
        setLoi('Chưa bật được chia sẻ dữ liệu. Kiểm tra kết nối máy chủ rồi thử lại.')
      }
    } catch {
      setLoi('Không kết nối được máy chủ. Dữ liệu analytics vẫn đang tắt.')
    } finally {
      setDangCapNhat(false)
    }
  }

  const tatChiaSe = async () => {
    if (dangCapNhat) return
    setDangCapNhat(true)
    setLoi('')
    try {
      await thuHoiDongY()
    } finally {
      setDangCapNhat(false)
    }
  }

  if (trangThai !== 'chua-chon') {
    return (
      <>
        <div className="consent-status-bar mb">
          <div className="spread">
            <div className="consent-status-info">
              <span
                className="consent-status-dot"
                style={{ backgroundColor: trangThai === 'granted' ? 'var(--amds-success)' : 'var(--amds-text-faint)' }}
              />
              <span className="consent-status-text">
                Chia sẻ dữ liệu ẩn danh: <strong>{trangThai === 'granted' ? 'đang bật' : 'đang tắt'}</strong>
                {trangThai === 'granted' && tracked !== null && ` · ${tracked} thiết bị đang dùng`}
              </span>
            </div>
            {trangThai === 'granted' ? (
              <button
                className="btn btn--sm btn--secondary"
                type="button"
                disabled={dangCapNhat}
                onClick={() => void tatChiaSe()}
              >
                {dangCapNhat ? 'Đang cập nhật…' : 'Tắt thu thập'}
              </button>
            ) : (
              <button
                className="btn btn--sm btn--primary"
                type="button"
                disabled={dangCapNhat}
                onClick={() => void batChiaSe()}
              >
                {dangCapNhat ? 'Đang bật…' : 'Bật chia sẻ'}
              </button>
            )}
          </div>
        </div>
        {loi !== '' && <div className="notice notice--error mb" role="alert">{loi}</div>}
      </>
    )
  }

  return (
    <div className="card consent-card mb" role="dialog" aria-label="Xin phép chia sẻ dữ liệu ẩn danh">
      <div className="consent-card__header">
        <div className="consent-card__icon-box">
          <ShieldCheckIcon />
        </div>
        <div>
          <h3 className="card__title" style={{ fontSize: '1rem', margin: 0 }}>
            Chia sẻ dữ liệu ẩn danh để nâng cao trải nghiệm?
          </h3>
          <p className="card__subtitle" style={{ marginTop: 4, marginBottom: 0 }}>
            Chỉ gom số lượt xem, lượt nghe và cụm từ tìm kiếm. Không ghi tên, không ghi tài khoản, không ghi vị trí
            của bạn vào phần này. Bạn tắt bất cứ lúc nào.
          </p>
        </div>
      </div>

      <div className="button-group mt" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn--secondary btn--sm" type="button" onClick={() => void thuHoiDongY()}>
          Không cho phép
        </button>
        <button
          className="btn btn--primary btn--sm"
          type="button"
          disabled={dangCapNhat}
          onClick={() => void batChiaSe()}
        >
          {dangCapNhat ? 'Đang bật…' : 'Cho phép'}
        </button>
      </div>
      {loi !== '' && <div className="notice notice--error mt" role="alert">{loi}</div>}
    </div>
  )
}
