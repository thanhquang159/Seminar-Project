import { useEffect, useState } from 'react'
import { api, apiText } from './api'
import AnalyticsPanel from './AnalyticsPanel'
import AudioTasks from './AudioTasks'
import OwnerApprovals from './OwnerApprovals'
import PoiImageManager from './PoiImageManager'
import { layUrlAnh } from '../components/imageUtils'
import type { Poi } from '../stores/poiStore'

const TRONG: Poi = {
  id: '',
  name: '',
  description: '',
  lat: 10.7569,
  lng: 106.7641,
  trigger_radius: 30,
  audio_priority: 0,
  lang: 'vi',
  is_fallback: false,
  audio_url: null,
  images: [],
}

// Hai cổng dùng chung MỘT cookie phiên, nên phiên chủ quán có thể "tràn" sang
// tab Admin khi đổi tab: `/admin/auth/me` trả 200 cho mọi phiên đã đăng nhập
// (hợp đồng class A) nên client phải tự chặn phiên cổng khách khỏi render
// giao diện quản trị. Quyền thật vẫn do server giữ (test ma trận quyền) —
// đây chỉ là chặn hiển thị, không phải phân quyền.
const CONG_KHACH = new Set(['poi_owner', 'user'])

export default function AdminApp({ onPoisChanged }: { onPoisChanged: () => void }) {
  const [user, setUser] = useState<string | null>(null)
  const [ten, setTen] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [loi, setLoi] = useState('')
  const [pois, setPois] = useState<Poi[]>([])
  const [form, setForm] = useState<Poi>(TRONG)
  const [dangSua, setDangSua] = useState(false)
  const [poiQuanLyAnh, setPoiQuanLyAnh] = useState<Poi | null>(null)
  const [adminTab, setAdminTab] = useState<'pois' | 'approvals' | 'audio' | 'analytics'>('pois')

  const taiPois = async () => {
    try {
      const danhSach = await api<Poi[]>('/poi')
      setPois(danhSach)
    } catch {
      // Bỏ qua lỗi
    }
  }

  useEffect(() => {
    api<{ username: string; role: string }>('/admin/auth/me')
      .then((me) => {
        if (CONG_KHACH.has(me.role)) return
        setUser(me.username)
        void taiPois()
      })
      .catch(() => {})
  }, [])

  const dangNhap = async () => {
    setLoi('')
    const res = await apiText('/admin/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: ten, password: matKhau }),
    })
    if (!res.ok) {
      setLoi('Sai tên đăng nhập hoặc mật khẩu')
      return
    }
    const me = (await res.json()) as { username: string; role: string }
    if (CONG_KHACH.has(me.role)) {
      setLoi('Tài khoản này là chủ quán, không mở được cổng quản trị')
      return
    }
    setUser(me.username)
    setMatKhau('')
    await taiPois()
  }

  const dangXuat = async () => {
    await apiText('/admin/auth/logout', { method: 'POST' })
    setUser(null)
    setPois([])
  }

  const luu = async () => {
    setLoi('')
    try {
      if (dangSua) {
        await api(`/admin/pois/${form.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...form, id: undefined }),
        })
      } else {
        await api('/admin/pois', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...form, id: undefined }),
        })
      }
      setForm(TRONG)
      setDangSua(false)
      await taiPois()
      onPoisChanged()
    } catch {
      setLoi('Lưu thất bại, kiểm tra toạ độ lat/lng và bán kính 5-200m')
    }
  }

  const xoa = async (id: string) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa điểm quán này không?')) return
    await api(`/admin/pois/${id}`, { method: 'DELETE' })
    await taiPois()
    onPoisChanged()
  }

  const capNhatAnhChoPoi = (poiId: string, danhSachMoi: string[]) => {
    setPois((prev) =>
      prev.map((p) => (p.id === poiId ? { ...p, images: danhSachMoi } : p))
    )
    if (form.id === poiId) {
      setForm((prev) => ({ ...prev, images: danhSachMoi }))
    }
    if (poiQuanLyAnh && poiQuanLyAnh.id === poiId) {
      setPoiQuanLyAnh((prev) => (prev ? { ...prev, images: danhSachMoi } : null))
    }
    onPoisChanged()
  }

  if (user === null) {
    return (
      <div className="login-card-wrapper">
        <div className="card login-card">
          <div className="login-card__header">
            <div className="login-card__icon-wrap">
              <svg className="login-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <h2 className="card__title">Đăng nhập Quản trị viên</h2>
            <p className="card__subtitle">Dành riêng cho cán bộ điều hành hệ thống AMDS Quận 4</p>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="admin-username">Tên đăng nhập</label>
            <input
              id="admin-username"
              className="input"
              placeholder="Tên đăng nhập"
              value={ten}
              onChange={(e) => setTen(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label" htmlFor="admin-password">Mật khẩu</label>
            <input
              id="admin-password"
              className="input"
              placeholder="Mật khẩu"
              type="password"
              value={matKhau}
              onChange={(e) => setMatKhau(e.target.value)}
            />
          </div>

          <button
            className="btn btn--primary btn--block btn--lg mt"
            type="button"
            onClick={() => void dangNhap()}
          >
            Đăng nhập
          </button>

          {loi !== '' && <div className="notice notice--error mt">{loi}</div>}
        </div>
      </div>
    )
  }

  return (
    <div className="admin-container">
      {/* Thanh chào & Đăng xuất */}
      <div className="card admin-header-card">
        <div className="spread">
          <div className="admin-user-info">
            <div className="admin-user-avatar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div>
              <p className="admin-user-title">
                Xin chào, <strong>{user}</strong>
              </p>
              <span className="badge badge--ok">Phiên làm việc Quản trị viên</span>
            </div>
          </div>
          <button className="btn btn--secondary btn--sm" type="button" onClick={() => void dangXuat()}>
            Đăng xuất
          </button>
        </div>
      </div>

      {/* Thanh tab nội bộ của Admin */}
      <div className="admin-tabs-nav mt" role="tablist">
        <button
          type="button"
          className={`admin-tab-btn${adminTab === 'pois' ? ' admin-tab-btn--active' : ''}`}
          onClick={() => setAdminTab('pois')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          Quản lý quán ({pois.length})
        </button>
        <button
          type="button"
          className={`admin-tab-btn${adminTab === 'approvals' ? ' admin-tab-btn--active' : ''}`}
          onClick={() => setAdminTab('approvals')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          Duyệt chủ quán
        </button>
        <button
          type="button"
          className={`admin-tab-btn${adminTab === 'audio' ? ' admin-tab-btn--active' : ''}`}
          onClick={() => setAdminTab('audio')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
          Tác vụ âm thanh
        </button>
        <button
          type="button"
          className={`admin-tab-btn${adminTab === 'analytics' ? ' admin-tab-btn--active' : ''}`}
          onClick={() => setAdminTab('analytics')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          Thống kê & Giám sát
        </button>
      </div>

      {/* NỘI DUNG THEO TAB ADMIN */}
      {adminTab === 'pois' && (
        <div className="admin-poi-layout mt">
          {/* Form thêm / sửa quán */}
          <div className="card admin-form-card">
            <h3 className="card__title">
              {dangSua ? `Chỉnh sửa quán: ${form.name}` : 'Thêm điểm ẩm thực mới'}
            </h3>
            <p className="card__subtitle">
              Nhập thông tin chi tiết toạ độ và nội dung thuyết minh
            </p>

            <div className="field">
              <label className="field__label">Tên quán ăn / Điểm tham quan *</label>
              <input
                className="input"
                placeholder="Ví dụ: Ốc Oanh - Vĩnh Khánh"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            <div className="field">
              <label className="field__label">Mô tả đặc trưng & Giới thiệu</label>
              <textarea
                className="input textarea"
                rows={3}
                placeholder="Mô tả món ngon, phong cách ẩm thực đặc sắc..."
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>

            <div className="form-grid-2">
              <div className="field">
                <label className="field__label">Vĩ độ (Latitude) *</label>
                <input
                  className="input"
                  placeholder="10.7569"
                  type="number"
                  step="any"
                  value={form.lat}
                  onChange={(e) => setForm({ ...form, lat: Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label className="field__label">Kinh độ (Longitude) *</label>
                <input
                  className="input"
                  placeholder="106.7641"
                  type="number"
                  step="any"
                  value={form.lng}
                  onChange={(e) => setForm({ ...form, lng: Number(e.target.value) })}
                />
              </div>
            </div>

            <div className="form-grid-2">
              <div className="field">
                <label className="field__label">Bán kính quét (m) [5 - 200m]</label>
                <input
                  className="input"
                  type="number"
                  value={form.trigger_radius}
                  onChange={(e) => setForm({ ...form, trigger_radius: Number(e.target.value) })}
                />
              </div>
              <div className="field">
                <label className="field__label">Độ ưu tiên âm thanh</label>
                <input
                  className="input"
                  type="number"
                  value={form.audio_priority}
                  onChange={(e) => setForm({ ...form, audio_priority: Number(e.target.value) })}
                />
              </div>
            </div>

            <div className="row mt">
              <button className="btn btn--primary" type="button" onClick={() => void luu()}>
                {dangSua ? 'Cập nhật quán' : 'Tạo điểm quán mới'}
              </button>
              {dangSua && (
                <button
                  className="btn btn--secondary"
                  type="button"
                  onClick={() => {
                    setForm(TRONG)
                    setDangSua(false)
                  }}
                >
                  Hủy chỉnh sửa
                </button>
              )}
            </div>

            {loi !== '' && <div className="notice notice--error mt">{loi}</div>}
          </div>

          {/* Bảng danh sách quán */}
          <div className="card admin-table-card mt">
            <div className="section-header">
              <h3 className="card__title">Danh sách các quán ({pois.length})</h3>
              <span className="badge badge--neutral">Quận 4, TP.HCM</span>
            </div>

            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: 64 }}>Ảnh</th>
                    <th>Tên quán</th>
                    <th>Toạ độ / Bán kính</th>
                    <th style={{ textAlign: 'right' }}>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {pois.map((p) => {
                    const coAnh = p.images && p.images.length > 0
                    const anhThumb = coAnh ? layUrlAnh(p.images![0]) : null

                    return (
                      <tr key={p.id}>
                        <td>
                          {coAnh && anhThumb ? (
                            <img
                              {...{ src: anhThumb }}
                              alt=""
                              className="admin-table-thumb"
                              loading="lazy"
                            />
                          ) : (
                            <div className="admin-table-thumb-placeholder" title="Chưa có ảnh">
                              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                <circle cx="8.5" cy="8.5" r="1.5" />
                                <polyline points="21 15 16 10 5 21" />
                              </svg>
                            </div>
                          )}
                        </td>
                        <td>
                          <strong>{p.name}</strong>
                          <div className="muted" style={{ fontSize: '0.82rem' }}>
                            {p.images ? `${p.images.length}/8 ảnh` : '0/8 ảnh'} · {p.audio_url ? 'Đã có audio' : 'Chưa có audio'}
                          </div>
                        </td>
                        <td>
                          <span className="badge badge--neutral" style={{ fontSize: '0.78rem' }}>
                            {p.lat.toFixed(4)}, {p.lng.toFixed(4)}
                          </span>
                          <span className="badge badge--info ml" style={{ fontSize: '0.78rem' }}>
                            {p.trigger_radius}m
                          </span>
                        </td>
                        <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                          <button
                            className="btn btn--sm btn--accent"
                            type="button"
                            onClick={() => setPoiQuanLyAnh(p)}
                            title="Quản lý hình ảnh quán"
                          >
                            Ảnh ({p.images ? p.images.length : 0})
                          </button>{' '}
                          <button
                            className="btn btn--sm btn--secondary"
                            type="button"
                            onClick={() => {
                              setForm(p)
                              setDangSua(true)
                              window.scrollTo({ top: 0, behavior: 'smooth' })
                            }}
                          >
                            Sửa
                          </button>{' '}
                          <button
                            className="btn btn--sm btn--danger"
                            type="button"
                            onClick={() => void xoa(p.id)}
                          >
                            Xóa
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {adminTab === 'approvals' && (
        <div className="mt">
          <OwnerApprovals />
        </div>
      )}

      {adminTab === 'audio' && (
        <div className="mt">
          <AudioTasks />
        </div>
      )}

      {adminTab === 'analytics' && (
        <div className="mt">
          <AnalyticsPanel />
        </div>
      )}

      {/* Modal Quản lý hình ảnh POI */}
      {poiQuanLyAnh && (
        <PoiImageManager
          poiId={poiQuanLyAnh.id}
          poiName={poiQuanLyAnh.name}
          images={poiQuanLyAnh.images || []}
          onCapNhatAnh={capNhatAnhChoPoi}
          onDong={() => setPoiQuanLyAnh(null)}
        />
      )}
    </div>
  )
}
