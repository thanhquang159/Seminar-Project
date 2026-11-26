import { useCallback, useEffect, useState } from 'react'
import { api, apiText } from './api'
import AnalyticsPanel from './AnalyticsPanel'
import AudioTasks from './AudioTasks'
import OwnerApprovals from './OwnerApprovals'
import { useApprovalCount } from './useApprovalCount'
import PoiImageManager from './PoiImageManager'
import PoiTranslations from './PoiTranslations'
import PoiPublication, { type PublicationReadiness } from './PoiPublication'
import PortalDashboard, { type PortalDashboardItem } from './PortalDashboard'
import AdminGovernance from './AdminGovernance'
import AdminAccessManagement from './AdminAccessManagement'
import { layUrlAnh } from '../components/imageUtils'
import type { Poi } from '../stores/poiStore'
import {
  getAdminPortalPage,
  getPortalPath,
  isStaleLoginSessionCheck,
  navigateToPath,
} from './portalRoutes'

const TRONG: Poi = {
  id: '',
  name: '',
  description: '',
  category: 'other',
  lat: 10.7569,
  lng: 106.7641,
  trigger_radius: 30,
  audio_priority: 0,
  lang: 'vi',
  is_fallback: false,
  audio_url: null,
  images: [],
}

interface AdminPoi extends Poi {
  address_line: string
  publication_status: string
  is_active: boolean
  readiness?: PublicationReadiness
}

// Hai cổng dùng chung MỘT cookie phiên, nên phiên chủ quán có thể "tràn" sang
// tab Admin khi đổi tab: `/admin/auth/me` trả 200 cho mọi phiên đã đăng nhập
// (hợp đồng class A) nên client phải tự chặn phiên cổng khách khỏi render
// giao diện quản trị. Quyền thật vẫn do server giữ (test ma trận quyền) —
// đây chỉ là chặn hiển thị, không phải phân quyền.
const CONG_KHACH = new Set(['poi_owner', 'user'])

export default function AdminApp({ onPoisChanged }: { onPoisChanged: () => void }) {
  const [user, setUser] = useState<string | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const { count: pendingApprovalCount, refreshVersion: approvalRefreshVersion, refresh: refreshApprovalCount } = useApprovalCount(user, permissions)
  const [checkingSession, setCheckingSession] = useState(true)
  const [ten, setTen] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [loi, setLoi] = useState('')
  const [dangDangNhap, setDangDangNhap] = useState(false)
  const [pois, setPois] = useState<AdminPoi[]>([])
  const [form, setForm] = useState<AdminPoi>({
    ...TRONG,
    address_line: '',
    publication_status: 'draft',
    is_active: false,
  })
  const [dangSua, setDangSua] = useState(false)
  const [poiQuanLyAnh, setPoiQuanLyAnh] = useState<Poi | null>(null)
  const [adminTab, setAdminTab] = useState(
    () => getAdminPortalPage(window.location.pathname) ?? 'pois',
  )

  const taiPois = useCallback(async () => {
    try {
      setPois(await api<AdminPoi[]>('/admin/pois'))
    } catch {
      setLoi('Không tải được danh sách POI quản trị. Vui lòng tải lại trang.')
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const syncRoute = () => {
      const page = getAdminPortalPage(window.location.pathname)
      if (page !== null) {
        setAdminTab(page)
      } else if (window.location.pathname.startsWith('/admin/') && window.location.pathname !== '/admin/login') {
        navigateToPath('/admin', true)
      }
    }
    window.addEventListener('popstate', syncRoute)
    syncRoute()

    const restoreSession = async () => {
      const pathAtStart = window.location.pathname
      try {
        const me = await api<{ username: string; role: string; permissions: string[] }>('/admin/auth/me')
        if (!mounted) return
        if (isStaleLoginSessionCheck(pathAtStart, window.location.pathname, '/admin/login')) return
        if (CONG_KHACH.has(me.role)) {
          if (window.location.pathname !== '/admin/login') {
            navigateToPath('/admin/login', true)
          }
          return
        }
        setUser(me.username)
        setPermissions(me.permissions ?? [])
        await taiPois()
        if (mounted && window.location.pathname === '/admin/login') {
          navigateToPath('/admin', true)
        }
      } catch {
        if (!mounted) return
        if (isStaleLoginSessionCheck(pathAtStart, window.location.pathname, '/admin/login')) return
        setUser(null)
        if (window.location.pathname !== '/admin/login') {
          navigateToPath('/admin/login', true)
        }
      } finally {
        if (mounted) setCheckingSession(false)
      }
    }
    void restoreSession()

    return () => {
      mounted = false
      window.removeEventListener('popstate', syncRoute)
    }
  }, [taiPois])

  const dangNhap = async () => {
    if (dangDangNhap) return
    setLoi('')
    setDangDangNhap(true)
    try {
      const res = await apiText('/admin/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: ten, password: matKhau }),
      })
      if (!res.ok) {
        setLoi('Sai tên đăng nhập hoặc mật khẩu')
        return
      }
      const me = await api<{ username: string; role: string; permissions: string[] }>('/admin/auth/me')
      if (CONG_KHACH.has(me.role)) {
        setLoi('Tài khoản này là chủ quán, không mở được cổng quản trị')
        return
      }
      setUser(me.username)
      setPermissions(me.permissions ?? [])
      setMatKhau('')
      await taiPois()
      navigateToPath('/admin')
    } catch {
      setLoi('Không kết nối được máy chủ. Hãy kiểm tra backend và thử lại.')
    } finally {
      setDangDangNhap(false)
    }
  }

  const dangXuat = async () => {
    try {
      const response = await apiText('/admin/auth/logout', { method: 'POST' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setUser(null)
      setPois([])
      navigateToPath('/admin/login', true)
    } catch {
      setLoi('Không thể đăng xuất. Vui lòng thử lại.')
    }
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
      setForm({ ...TRONG, address_line: '', publication_status: 'draft', is_active: false })
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

  if (user === null && checkingSession) {
    return <div className="notice notice--info">Đang khôi phục phiên quản trị…</div>
  }

  if (user === null) {
    return (
      <div className="login-card-wrapper login-card-wrapper--admin">
        <div className="card login-card">
          <div className="login-card__header">
            <div className="login-card__icon-wrap login-card__icon-wrap--admin">
              <svg className="login-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <span className="portal-login__eyebrow">CỔNG NỘI BỘ</span>
            <h2 className="card__title">Chào mừng trở lại!</h2>
            <p className="card__subtitle">Đăng nhập để quản lý hệ thống Ẩm Thực Quận 4.</p>
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault()
              void dangNhap()
            }}
          >
            <div className="field">
              <label className="field__label" htmlFor="admin-username">Email hoặc tên đăng nhập</label>
              <input
                id="admin-username"
                className="input"
                placeholder="Nhập email hoặc tên đăng nhập"
                autoComplete="username"
                required
                value={ten}
                onChange={(e) => setTen(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor="admin-password">Mật khẩu</label>
              <input
                id="admin-password"
                className="input"
                placeholder="Nhập mật khẩu"
                type="password"
                autoComplete="current-password"
                required
                value={matKhau}
                onChange={(e) => setMatKhau(e.target.value)}
              />
            </div>

            <button
              className="btn btn--primary btn--block btn--lg mt"
              type="submit"
              disabled={dangDangNhap}
            >
              {dangDangNhap ? 'Đang xác thực…' : 'Đăng nhập quản trị'}
            </button>
          </form>

          {loi !== '' && <div className="notice notice--error mt" role="alert">{loi}</div>}
          <p className="portal-login__security-note">
            Phiên quản trị được bảo vệ bằng cookie bảo mật. Không chia sẻ thông tin đăng nhập.
          </p>
        </div>
      </div>
    )
  }

  const navItems: PortalDashboardItem[] = [
    {
      key: 'pois',
      label: `Quản lý quán (${pois.length})`,
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0Z" /><circle cx="12" cy="10" r="3" /></svg>,
    },
    {
      key: 'approvals',
      label: 'Duyệt chủ quán',
      badge: pendingApprovalCount,
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" /></svg>,
    },
    {
      key: 'audio',
      label: 'Tác vụ âm thanh',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2m7 9v3" /></svg>,
    },
    {
      key: 'translations',
      label: 'Bản dịch POI',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M4 5h16M9 3v2m6 0c-.5 5-3 8-7 10m1-6c1 2 3 4 6 5m1 7 3-8 3 8m-5-2h4" /></svg>,
    },
    {
      key: 'analytics',
      label: 'Thống kê & Giám sát',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M4 19V9m8 10V4m8 15v-7" /></svg>,
    },
    {
      key: 'access',
      label: 'Tài khoản & quyền',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-4" /></svg>,
    },
    {
      key: 'audit',
      label: 'Nhật ký hoạt động',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5m4-1v5l3 2" /></svg>,
    },
  ]
  const pageInfo = {
    pois: ['Quản lý địa điểm', 'Theo dõi và cập nhật các điểm ẩm thực Quận 4.'],
    approvals: ['Kiểm duyệt', 'Xử lý hồ sơ chủ quán và địa điểm mới gửi lên.'],
    audio: ['Tác vụ âm thanh', 'Quản lý nội dung thuyết minh cho các điểm ẩm thực.'],
    translations: ['Bản dịch POI', 'Nhập bản dịch thủ công cho các ngôn ngữ khách hàng lựa chọn.'],
    analytics: ['Thống kê & Giám sát', 'Theo dõi tương tác và tình trạng vận hành hệ thống.'],
    access: ['Tài khoản & quyền', 'Quản lý trạng thái tài khoản và quyền vai trò.'],
    audit: ['Nhật ký hoạt động', 'Tra cứu lịch sử thao tác trong hệ thống.'],
  }[adminTab]
  const audioCount = pois.filter((poi) => Boolean(poi.audio_url)).length
  const imageCount = pois.reduce((total, poi) => total + (poi.images?.length ?? 0), 0)

  return (
    <PortalDashboard
      role="admin"
      username={user}
      title={pageInfo[0]}
      description={pageInfo[1]}
      activeItem={adminTab}
      items={navItems}
      onNavigate={(key) => {
        if (key === 'pois' || key === 'approvals' || key === 'audio' || key === 'translations' || key === 'analytics' || key === 'access' || key === 'audit') {
          setAdminTab(key)
          navigateToPath(getPortalPath('admin', key))
        }
      }}
      onLogout={() => void dangXuat()}
    >
      {adminTab === 'pois' && (
        <section className="dashboard-metrics" aria-label="Tổng quan địa điểm">
          <div className="dashboard-metric">
            <span className="dashboard-metric__icon dashboard-metric__icon--blue" aria-hidden="true">⌖</span>
            <span className="dashboard-metric__label">Tổng địa điểm</span>
            <strong>{pois.length}</strong>
            <span className="dashboard-metric__hint">điểm ẩm thực đang quản lý</span>
          </div>
          <div className="dashboard-metric">
            <span className="dashboard-metric__icon dashboard-metric__icon--green" aria-hidden="true">♫</span>
            <span className="dashboard-metric__label">Đã có thuyết minh</span>
            <strong>{audioCount}</strong>
            <span className="dashboard-metric__hint">địa điểm có audio</span>
          </div>
          <div className="dashboard-metric">
            <span className="dashboard-metric__icon dashboard-metric__icon--amber" aria-hidden="true">◷</span>
            <span className="dashboard-metric__label">Cần bổ sung audio</span>
            <strong>{pois.length - audioCount}</strong>
            <span className="dashboard-metric__hint">địa điểm chưa có audio</span>
          </div>
          <div className="dashboard-metric">
            <span className="dashboard-metric__icon dashboard-metric__icon--violet" aria-hidden="true">▧</span>
            <span className="dashboard-metric__label">Hình ảnh</span>
            <strong>{imageCount}</strong>
            <span className="dashboard-metric__hint">ảnh trên các địa điểm</span>
          </div>
        </section>
      )}
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

            <div className="field">
              <label className="field__label">Danh mục POI *</label>
              <select
                className="input"
                value={form.category ?? 'other'}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                <option value="restaurant">Nhà hàng</option>
                <option value="cafe">Cà phê</option>
                <option value="street_food">Ẩm thực đường phố</option>
                <option value="bakery">Tiệm bánh</option>
                <option value="dessert">Tráng miệng</option>
                <option value="seafood">Hải sản</option>
                <option value="bar">Quán bar</option>
                <option value="other">Khác</option>
              </select>
            </div>

            <div className="field">
              <label className="field__label">Địa chỉ</label>
              <input
                className="input"
                placeholder="Số nhà, đường, phường..."
                value={form.address_line}
                onChange={(e) => setForm({ ...form, address_line: e.target.value })}
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
                    setForm({ ...TRONG, address_line: '', publication_status: 'draft', is_active: false })
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
                    <th>Địa chỉ / Trạng thái</th>
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
                          <div>{p.address_line || 'Chưa có địa chỉ'}</div>
                          <PoiPublication poi={p} canPublish={permissions.includes('poi:publish')}
                            onChanged={async () => { await taiPois(); onPoisChanged() }} />
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
          <OwnerApprovals
            refreshVersion={approvalRefreshVersion}
            onPendingChanged={refreshApprovalCount}
            onPoiApproved={async () => {
              await taiPois()
              onPoisChanged()
            }}
          />
        </div>
      )}

      {adminTab === 'audio' && (
        <div className="mt">
          <AudioTasks />
        </div>
      )}

      {adminTab === 'translations' && (
        <div className="mt">
          <PoiTranslations
            pois={pois}
            onSaved={async () => {
              await taiPois()
              onPoisChanged()
            }}
          />
        </div>
      )}

      {adminTab === 'analytics' && (
        <div className="mt">
          <AnalyticsPanel />
        </div>
      )}

      {adminTab === 'access' && <AdminAccessManagement />}
      {adminTab === 'audit' && (
        <AdminGovernance key={adminTab} section={adminTab} />
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
    </PortalDashboard>
  )
}
