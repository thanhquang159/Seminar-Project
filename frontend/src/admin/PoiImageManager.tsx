import { useRef, useState } from 'react'
import { API_BASE_URL } from '../config'
import { apiText } from './api'
import { layUrlAnh } from '../components/imageUtils'

interface PoiImageManagerProps {
  poiId: string
  poiName: string
  images: string[]
  onCapNhatAnh: (poiId: string, danhSachMoi: string[]) => void
  onDong: () => void
}

const MAX_ANH = 8
const MAX_BYTE = 5 * 1024 * 1024 // 5 MB (theo đặc tả SEC-012)
const API_GOC = API_BASE_URL

export default function PoiImageManager({
  poiId,
  poiName,
  images = [],
  onCapNhatAnh,
  onDong,
}: PoiImageManagerProps) {
  const [danhSach, setDanhSach] = useState<string[]>(images)
  const [dangTai, setDangTai] = useState(false)
  const [dangXoa, setDangXoa] = useState<string | null>(null)
  const [thongBao, setThongBao] = useState<{ loai: 'ok' | 'loi'; noiDung: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Tải lại danh sách ảnh thực tế từ backend
  const lamMoi = async () => {
    try {
      const res = await apiText(`/admin/pois/${poiId}/images`)
      if (res.ok) {
        const data = (await res.json()) as { images: string[] }
        setDanhSach(data.images)
        onCapNhatAnh(poiId, data.images)
      }
    } catch {
      // Bỏ qua lỗi mạng nền
    }
  }

  // Xử lý khi người dùng chọn tệp ảnh để tải lên
  const xuLyChonTep = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setThongBao(null)

    // Kiểm tra số lượng
    if (danhSach.length >= MAX_ANH) {
      setThongBao({ loai: 'loi', noiDung: `Mỗi quán chỉ được tối đa ${MAX_ANH} ảnh` })
      return
    }

    // Kiểm tra kích thước
    if (file.size > MAX_BYTE) {
      setThongBao({ loai: 'loi', noiDung: 'Dung lượng ảnh vượt quá giới hạn 5 MB' })
      return
    }

    // Kiểm tra định dạng đuôi
    const duoiHopLe = ['jpg', 'jpeg', 'png', 'webp']
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!duoiHopLe.includes(ext)) {
      setThongBao({ loai: 'loi', noiDung: 'Chỉ chấp nhận định dạng ảnh JPEG, PNG hoặc WebP' })
      return
    }

    setDangTai(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch(`${API_GOC}/admin/pois/${poiId}/images`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: 'Tải ảnh thất bại' }))
        setThongBao({ loai: 'loi', noiDung: errorData.detail || 'Tải ảnh thất bại' })
        setDangTai(false)
        return
      }

      const ketQua = (await res.json()) as { images: string[]; moi_tai: string }
      setDanhSach(ketQua.images)
      onCapNhatAnh(poiId, ketQua.images)
      setThongBao({ loai: 'ok', noiDung: 'Tải ảnh lên thành công!' })
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch {
      setThongBao({ loai: 'loi', noiDung: 'Lỗi mạng khi tải ảnh lên máy chủ' })
    } finally {
      setDangTai(false)
    }
  }

  // Xóa một ảnh của POI
  const xuLyXoaAnh = async (urlAnh: string) => {
    const tenTep = urlAnh.split('/').pop()
    if (!tenTep) return

    if (!window.confirm('Bạn có chắc chắn muốn xóa ảnh này khỏi quán không?')) return

    setDangXoa(urlAnh)
    setThongBao(null)
    try {
      const res = await apiText(`/admin/pois/${poiId}/images/${tenTep}`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        setThongBao({ loai: 'loi', noiDung: 'Xóa ảnh thất bại' })
        setDangXoa(null)
        return
      }

      const conLai = danhSach.filter((u) => u !== urlAnh)
      setDanhSach(conLai)
      onCapNhatAnh(poiId, conLai)
      setThongBao({ loai: 'ok', noiDung: 'Đã xóa ảnh thành công' })
    } catch {
      setThongBao({ loai: 'loi', noiDung: 'Lỗi mạng khi gửi yêu cầu xóa ảnh' })
    } finally {
      setDangXoa(null)
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="image-mgr-title">
      <div className="modal-content modal-content--wide">
        <div className="modal-header">
          <div>
            <h3 id="image-mgr-title" className="modal-title">Quản lý hình ảnh quán</h3>
            <p className="modal-subtitle">
              Quán: <strong>{poiName}</strong> · Đã có {danhSach.length}/{MAX_ANH} ảnh
            </p>
          </div>
          <button
            type="button"
            className="btn-icon"
            onClick={onDong}
            aria-label="Đóng cửa sổ"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {thongBao && (
          <div className={`notice notice--${thongBao.loai === 'ok' ? 'ok' : 'error'} mb`}>
            {thongBao.noiDung}
          </div>
        )}

        {/* Khu vực tải ảnh lên */}
        <div className="image-uploader-box">
          <input
            ref={fileInputRef}
            type="file"
            id="poi-image-input"
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={(e) => void xuLyChonTep(e)}
            disabled={dangTai || danhSach.length >= MAX_ANH}
          />

          <div className="image-uploader-action">
            <button
              type="button"
              className="btn btn--primary"
              disabled={dangTai || danhSach.length >= MAX_ANH}
              onClick={() => fileInputRef.current?.click()}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                <circle cx="12" cy="13" r="4" />
              </svg>
              {dangTai ? 'Đang tải lên…' : 'Chọn ảnh tải lên'}
            </button>
            <span className="muted" style={{ fontSize: '0.85rem' }}>
              Tối đa 5 MB/ảnh (JPEG, PNG, WebP). Giới hạn tối đa 8 ảnh.
            </span>
          </div>
        </div>

        {/* Lưới hiển thị danh sách ảnh */}
        <div className="image-grid mt">
          {danhSach.length === 0 ? (
            <div className="empty-state">
              <p className="muted">Quán này chưa có ảnh nào. Hãy nhấn &quot;Chọn ảnh tải lên&quot; ở trên.</p>
            </div>
          ) : (
            danhSach.map((imgUrl, index) => {
              const fullUrl = layUrlAnh(imgUrl)
              const dangXuLy = dangXoa === imgUrl
              return (
                <div key={imgUrl + index} className="image-grid__item">
                  <img
                    {...{ src: fullUrl }}
                    alt={`${poiName} ảnh ${index + 1}`}
                    className="image-grid__thumb"
                    loading="lazy"
                  />
                  <div className="image-grid__overlay">
                    <span className="image-grid__badge">#{index + 1}</span>
                    <button
                      type="button"
                      className="btn-icon btn-icon--danger"
                      disabled={dangXuLy}
                      onClick={() => void xuLyXoaAnh(imgUrl)}
                      title="Xóa ảnh này"
                      aria-label={`Xóa ảnh ${index + 1}`}
                    >
                      {dangXuLy ? (
                        '…'
                      ) : (
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>

        <div className="modal-footer mt">
          <button type="button" className="btn btn--secondary" onClick={() => void lamMoi()}>
            Làm mới danh sách
          </button>
          <button type="button" className="btn btn--primary" onClick={onDong}>
            Hoàn tất
          </button>
        </div>
      </div>
    </div>
  )
}
