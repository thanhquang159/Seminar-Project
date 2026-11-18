import { useCallback, useEffect, useState } from 'react'
import { api, apiText } from './api'
import PortalDashboard, { type PortalDashboardItem } from './PortalDashboard'
import OwnerMenuManagement from './OwnerMenuManagement'
import OwnerPoiQrCodes from './OwnerPoiQrCodes'
import { layUrlAnh } from '../components/imageUtils'
import {
  getOwnerPortalPage,
  getPortalPath,
  isStaleLoginSessionCheck,
  navigateToPath,
} from './portalRoutes'

type OwnerAuthMode = 'login' | 'register'
type OwnerDashboardTab = 'submission' | 'history' | 'places' | 'qr' | 'menu' | 'notifications'

interface OwnerSubmission {
  id: string
  poi_id: string | null
  data: Record<string, unknown>
  status: string
  created_at: string | null
  admin_note: string | null
}

interface OwnerPoi {
  id: string
  name: string
  description: string
  lat: number
  lng: number
  trigger_radius: number
  audio_url: string | null
  publication_status: string
  is_active: boolean
}

export default function OwnerApp() {
  const [user, setUser] = useState<string | null>(null)
  const [authMode, setAuthMode] = useState<OwnerAuthMode>('login')
  const [dashboardTab, setDashboardTab] = useState<OwnerDashboardTab>(
    () => getOwnerPortalPage(window.location.pathname) ?? 'submission',
  )
  const [checkingSession, setCheckingSession] = useState(true)
  const [ten, setTen] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [cccd, setCccd] = useState('')
  const [loi, setLoi] = useState('')
  const [trangThai, setTrangThai] = useState('')
  const [tenQuan, setTenQuan] = useState('')
  const [moTa, setMoTa] = useState('')
  const [poiDangSua, setPoiDangSua] = useState('')
  const [dangXuLyAI, setDangXuLyAI] = useState(false)
  const [goiYAI, setGoiYAI] = useState('')
  const [thongBaoGui, setThongBaoGui] = useState('')
  const [thongBao, setThongBao] = useState<{ id: string; message: string; read: boolean }[]>([])
  const [lichSu, setLichSu] = useState<OwnerSubmission[]>([])
  const [poisCuaToi, setPoisCuaToi] = useState<OwnerPoi[]>([])

  const taiThongTinChuQuan = useCallback(async (isActive: () => boolean = () => true) => {
    let ownerStatus: string
    try {
      const st = await api<{ status: string }>('/owner/registration-status')
      if (!isActive()) return
      ownerStatus = st.status
      setTrangThai(st.status)
    } catch (error) {
      if (!isActive()) return
      if (error instanceof Error && error.message === 'HTTP 404') {
        setTrangThai('admin')
      } else {
        setTrangThai('unavailable')
      }
      return
    }

    // Keep this separate: pending owners may get 403 from notifications and
    // must not lose the registration status already loaded above.
    try {
      const notifications = await api<{ id: string; message: string; read: boolean }[]>('/owner/notifications')
      if (!isActive()) return
      setThongBao(notifications)
      if (ownerStatus === 'approved') {
        const [submissions, pois] = await Promise.all([
          api<OwnerSubmission[]>('/owner/submissions/mine'),
          api<OwnerPoi[]>('/owner/pois'),
        ])
        if (!isActive()) return
        setLichSu(submissions)
        setPoisCuaToi(pois)
      } else {
        setLichSu([])
        setPoisCuaToi([])
      }
    } catch {
      if (isActive()) setLoi('Đăng nhập được nhưng chưa tải được thông tin Chủ quán. Hãy tải lại trang.')
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const syncRoute = () => {
      const page = getOwnerPortalPage(window.location.pathname)
      if (page !== null) {
        setDashboardTab(page)
      } else if (window.location.pathname.startsWith('/owner/') && window.location.pathname !== '/owner/login') {
        navigateToPath('/owner', true)
      }
    }
    window.addEventListener('popstate', syncRoute)
    syncRoute()

    const restoreSession = async () => {
      const pathAtStart = window.location.pathname
      try {
        const me = await api<{ username: string }>('/admin/auth/me')
        if (!mounted) return
        if (isStaleLoginSessionCheck(pathAtStart, window.location.pathname, '/owner/login')) return
        setUser(me.username)
        await taiThongTinChuQuan(() => mounted)
        if (mounted && window.location.pathname === '/owner/login') {
          navigateToPath('/owner', true)
        }
      } catch {
        if (!mounted) return
        if (isStaleLoginSessionCheck(pathAtStart, window.location.pathname, '/owner/login')) return
        setUser(null)
        if (window.location.pathname !== '/owner/login') {
          navigateToPath('/owner/login', true)
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
  }, [taiThongTinChuQuan])

  const dangNhap = async () => {
    setLoi('')
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
      setUser(ten)
      setMatKhau('')
      await taiThongTinChuQuan()
      navigateToPath('/owner')
    } catch {
      setLoi('Không kết nối được máy chủ. Hãy kiểm tra backend và thử lại.')
    }
  }

  const dangXuat = async () => {
    try {
      const response = await apiText('/admin/auth/logout', { method: 'POST' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setUser(null)
      navigateToPath('/owner/login', true)
    } catch {
      setLoi('Không thể đăng xuất. Vui lòng thử lại.')
    }
  }

  const danhDauDaDoc = async (id: string) => {
    try {
      const response = await apiText(`/owner/notifications/${id}/read`, { method: 'POST' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setThongBao((items) => items.map((item) => item.id === id ? { ...item, read: true } : item))
    } catch {
      setLoi('Không thể cập nhật trạng thái thông báo. Vui lòng thử lại.')
    }
  }

  const dangKy = async () => {
    setLoi('')
    if (!ten.trim() || !matKhau.trim() || !cccd.trim()) {
      setLoi('Vui lòng điền đầy đủ Tên đăng nhập, Mật khẩu và số CCCD')
      return
    }
    const res = await apiText('/owner/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: ten, password: matKhau, cccd }),
    })
    if (!res.ok) {
      const payload: unknown = await res.json().catch(() => null)
      const detail =
        typeof payload === 'object' && payload !== null && 'detail' in payload
          ? payload.detail
          : null
      setLoi(
        typeof detail === 'string'
          ? `Đăng ký thất bại: ${detail}`
          : `Đăng ký thất bại (HTTP ${res.status})`,
      )
      return
    }

    setLoi('')
    setTrangThai('pending')
    setUser(ten)
  }

  const aiAdvisor = async () => {
    setLoi('')
    setGoiYAI('')
    setDangXuLyAI(true)
    try {
      const goi = await api<{ text: string }>('/ai/enhance-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: moTa }),
      })
      setMoTa(goi.text)
      setGoiYAI('AI đã đề xuất bản mô tả. Bạn hãy xem lại và chỉnh sửa trước khi gửi.')
    } catch {
      setLoi('AI bận hoặc hết lượt hôm nay')
    } finally {
      setDangXuLyAI(false)
    }
  }

  const guiQuan = async () => {
    setLoi('')
    setThongBaoGui('')
    if (!tenQuan.trim()) {
      setLoi('Vui lòng nhập tên quán ăn')
      return
    }
    try {
      const poi = poisCuaToi.find((item) => item.id === poiDangSua)
      await api('/owner/submissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...(poiDangSua ? { poi_id: poiDangSua } : {}),
          name: tenQuan,
          description: moTa,
          lat: poi?.lat ?? 10.7569,
          lng: poi?.lng ?? 106.7641,
        }),
      })
      setThongBaoGui('Đã gửi thông tin quán thành công! Quán đang chờ Admin phê duyệt.')
      setTenQuan('')
      setMoTa('')
      setPoiDangSua('')
      setGoiYAI('')
    } catch {
      setLoi('Gửi quán thất bại, vui lòng kiểm tra lại thông tin')
    }
  }

  if (user === null && checkingSession) {
    return <div className="notice notice--info">Đang khôi phục phiên chủ quán…</div>
  }

  if (user === null) {
    return (
      <div className="login-card-wrapper login-card-wrapper--owner">
        <div className="card login-card owner-login-card">
          <div className="login-card__header">
            <div className="login-card__icon-wrap login-card__icon-wrap--owner">
              <svg className="login-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 21h18M3 7v1a3 3 0 006 0V7m0 1a3 3 0 006 0V7m0 1a3 3 0 006 0V7M3 7l2-4h14l2 4M5 21V10.85M19 21V10.85M9 21v-4a2 2 0 012-2h2a2 2 0 012 2v4" />
              </svg>
            </div>
            <span className="owner-login-card__eyebrow">CỔNG DÀNH CHO CHỦ QUÁN</span>
            <h2 className="card__title">
              {authMode === 'login' ? 'Chào mừng trở lại!' : 'Cùng kể chuyện quán bạn'}
            </h2>
            <p className="card__subtitle">
              {authMode === 'login'
                ? 'Đăng nhập để quản lý thông tin và chia sẻ món ngon của quán.'
                : 'Tạo tài khoản chủ quán để gửi địa điểm của bạn đến cộng đồng.'}
            </p>
          </div>

          <form
            className="owner-login-card__form"
            onSubmit={(event) => {
              event.preventDefault()
              if (authMode === 'login') void dangNhap()
              else void dangKy()
            }}
          >
            <div className="field">
              <label className="field__label" htmlFor="owner-username">Tên đăng nhập</label>
              <input
                id="owner-username"
                className="input"
                placeholder="Nhập tên đăng nhập"
                autoComplete="username"
                required
                value={ten}
                onChange={(e) => setTen(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor="owner-password">Mật khẩu</label>
              <input
                id="owner-password"
                className="input"
                placeholder="Nhập mật khẩu"
                type="password"
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                required
                value={matKhau}
                onChange={(e) => setMatKhau(e.target.value)}
              />
            </div>

            {authMode === 'register' && (
              <div className="field">
                <label className="field__label" htmlFor="owner-cccd">Số Căn cước công dân (CCCD)</label>
                <input
                  id="owner-cccd"
                  className="input"
                  placeholder="Nhập số CCCD"
                  autoComplete="off"
                  required
                  value={cccd}
                  onChange={(e) => setCccd(e.target.value)}
                />
                <span className="field__helper">Thông tin CCCD được mã hóa và chỉ dùng để xác minh chủ quán.</span>
              </div>
            )}

            <button className="btn btn--primary btn--block btn--lg owner-login-card__submit" type="submit">
              {authMode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản chủ quán'}
            </button>
          </form>

          {loi !== '' && <div className="notice notice--error mt" role="alert">{loi}</div>}
          <div className="owner-login-card__switch">
            <span>{authMode === 'login' ? 'Chưa có tài khoản?' : 'Đã có tài khoản?'}</span>
            <button
              type="button"
              onClick={() => {
                setLoi('')
                setAuthMode(authMode === 'login' ? 'register' : 'login')
              }}
            >
              {authMode === 'login' ? 'Đăng ký chủ quán' : 'Đăng nhập'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  const laDaDuyet = trangThai === 'approved' || trangThai === 'admin'
  const tenTrangThai = {
    approved: 'Đã được duyệt',
    pending: 'Đang chờ duyệt',
    admin: 'Tài khoản nội bộ',
    unavailable: 'Chưa xác minh',
  }[trangThai] ?? 'Chưa xác định'
  const navItems: PortalDashboardItem[] = [
    {
      key: 'submission',
      label: 'Gửi quán mới',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M3 21h18M3 7l2-4h14l2 4M4 7v1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7m0 1a3 3 0 0 0 6 0V7M5 11v10m14-10v10M9 21v-4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v4" /></svg>,
    },
    {
      key: 'history',
      label: 'Trạng thái gửi duyệt',
      badge: lichSu.filter((submission) => submission.status === 'pending').length,
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5m4-1v5l3 2" /></svg>,
    },
    {
      key: 'places',
      label: 'Địa điểm của tôi',
      badge: poisCuaToi.length,
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0Z" /><circle cx="12" cy="10" r="3" /></svg>,
    },
    {
      key: 'qr',
      label: 'Mã QR',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><path d="M14 14h3v3h-3zm5 0h2m-7 5h3m2-2v4" /></svg>,
    },
    {
      key: 'menu',
      label: 'Thực đơn',
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M4 3v7a4 4 0 0 0 8 0V3M8 3v18m8-18v18m0-18c3 2 4 5 4 9h-4" /></svg>,
    },
    {
      key: 'notifications',
      label: 'Thông báo',
      badge: thongBao.length,
      icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 13h4" /></svg>,
    },
  ]

  return (
    <PortalDashboard
      role="owner"
      username={user}
      title={{
        submission: 'Gửi quán mới',
        history: 'Trạng thái gửi duyệt',
        places: 'Địa điểm của tôi',
        qr: 'Mã QR địa điểm',
        menu: 'Quản lý thực đơn',
        notifications: 'Thông báo',
      }[dashboardTab]}
      description={dashboardTab === 'submission'
        ? 'Chia sẻ địa điểm ẩm thực của quán với cộng đồng Quận 4.'
        : dashboardTab === 'history'
          ? 'Theo dõi kết quả kiểm duyệt các nội dung bạn đã gửi.'
          : dashboardTab === 'places'
            ? 'Xem các địa điểm thuộc quyền quản lý và gửi nội dung cập nhật.'
            : dashboardTab === 'qr'
              ? 'Tạo mã QR dẫn đến trang khám phá của các địa điểm đã được duyệt.'
            : dashboardTab === 'menu'
              ? 'Thêm, chỉnh sửa món ăn và cập nhật giá trên thực đơn của quán.'
              : 'Cập nhật tình trạng duyệt và thông tin dành cho quán của bạn.'}
      activeItem={dashboardTab}
      items={navItems}
      onNavigate={(key) => {
        if (key === 'submission' || key === 'history' || key === 'places' || key === 'qr' || key === 'menu' || key === 'notifications') {
          setDashboardTab(key)
          navigateToPath(getPortalPath('owner', key))
        }
      }}
      onLogout={() => void dangXuat()}
    >
      <section className="dashboard-metrics dashboard-metrics--owner" aria-label="Tổng quan tài khoản">
        <div className="dashboard-metric">
          <span className="dashboard-metric__icon dashboard-metric__icon--blue" aria-hidden="true">✓</span>
          <span className="dashboard-metric__label">Trạng thái tài khoản</span>
          <strong className="dashboard-metric__status">{tenTrangThai}</strong>
          <span className="dashboard-metric__hint">Xác minh tài khoản chủ quán</span>
        </div>
        <div className="dashboard-metric">
          <span className="dashboard-metric__icon dashboard-metric__icon--violet" aria-hidden="true">♡</span>
          <span className="dashboard-metric__label">Thông báo</span>
          <strong>{thongBao.length}</strong>
          <span className="dashboard-metric__hint">cập nhật từ đội ngũ vận hành</span>
        </div>
      </section>

      {dashboardTab === 'submission' && (
        <>
          {!laDaDuyet && (
            <div className={`notice ${trangThai === 'unavailable' ? 'notice--error' : 'notice--warn'} dashboard-notice`}>
              {trangThai === 'unavailable'
                ? 'Không xác minh được trạng thái tài khoản. Vui lòng kiểm tra kết nối và đăng nhập lại.'
                : 'Tài khoản chưa được duyệt, vui lòng quay lại sau khi được duyệt.'}
            </div>
          )}

          <div className="card dashboard-content-card">
            <div className="section-header">
              <div>
                <h2 className="card__title">Thông tin quán</h2>
                <p className="card__subtitle">Điền thông tin quán và món ngon đặc sắc để du khách ghé thăm.</p>
              </div>
            </div>

            <div className="field">
              <label className="field__label" htmlFor="owner-submission-poi">Loại nội dung gửi</label>
              <select
                id="owner-submission-poi"
                className="input"
                value={poiDangSua}
                disabled={!laDaDuyet}
                onChange={(event) => {
                  const poiId = event.target.value
                  setPoiDangSua(poiId)
                  const poi = poisCuaToi.find((item) => item.id === poiId)
                  setTenQuan(poi?.name ?? '')
                  setMoTa(poi?.description ?? '')
                }}
              >
                <option value="">Đề xuất quán mới</option>
                {poisCuaToi.map((poi) => (
                  <option value={poi.id} key={poi.id}>Cập nhật: {poi.name}</option>
                ))}
              </select>
            </div>

            <div className="field">
              <label className="field__label">Tên quán ăn / Thương hiệu *</label>
              <input
                className="input"
                placeholder="Tên quán"
                value={tenQuan}
                disabled={!laDaDuyet}
                onChange={(e) => setTenQuan(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="field__label">Mô tả món ăn & Câu chuyện ẩm thực</label>
              <textarea
                className="input textarea"
                rows={4}
                placeholder="Mô tả"
                value={moTa}
                disabled={!laDaDuyet}
                onChange={(e) => setMoTa(e.target.value)}
              />
            </div>

            <div className="button-group mt">
              <button
                className="btn btn--primary"
                type="button"
                disabled={!laDaDuyet || dangXuLyAI}
                onClick={() => void guiQuan()}
              >
                Gửi
              </button>
              <button
                className="btn btn--accent"
                type="button"
                disabled={!laDaDuyet || dangXuLyAI}
                onClick={() => void aiAdvisor()}
              >
                {dangXuLyAI ? 'Đang tạo gợi ý…' : 'AI gợi ý mô tả'}
              </button>
            </div>

            {goiYAI !== '' && <div className="notice notice--info mt" role="status">{goiYAI}</div>}
            {thongBaoGui !== '' && <div className="notice notice--ok mt">{thongBaoGui}</div>}
            {loi !== '' && <div className="notice notice--error mt">{loi}</div>}
          </div>
        </>
      )}

      {dashboardTab === 'history' && (
        <div className="card dashboard-content-card">
          <div className="section-header">
            <div>
              <h2 className="card__title">Nội dung đã gửi</h2>
              <p className="card__subtitle">Theo dõi tiến trình xét duyệt từng đề xuất của bạn.</p>
            </div>
            <span className="badge badge--neutral">{lichSu.length} mục</span>
          </div>

          {lichSu.length === 0 ? (
            <div className="empty-state">
              <p className="muted">Bạn chưa gửi nội dung nào để kiểm duyệt.</p>
            </div>
          ) : (
            <div className="table-responsive mt">
              <table className="table">
                <thead>
                  <tr>
                    <th>Nội dung</th>
                    <th>Loại</th>
                    <th>Ngày gửi</th>
                    <th>Trạng thái</th>
                    <th>Phản hồi Admin</th>
                  </tr>
                </thead>
                <tbody>
                  {lichSu.map((submission) => {
                    const data = submission.data
                    const tenNoiDung = typeof data.name === 'string'
                      ? data.name
                      : typeof data.title === 'string'
                        ? data.title
                        : submission.poi_id ?? 'Nội dung quán'
                    const trangThaiLabel = {
                      pending: 'Đang chờ duyệt',
                      approved: 'Đã được duyệt',
                      rejected: 'Cần chỉnh sửa',
                      withdrawn: 'Đã rút',
                    }[submission.status] ?? submission.status
                    return (
                      <tr key={submission.id}>
                        <td><strong>{tenNoiDung}</strong></td>
                        <td>{submission.poi_id ? 'Cập nhật quán' : 'Quán mới'}</td>
                        <td>{submission.created_at ? new Date(submission.created_at).toLocaleDateString('vi-VN') : '—'}</td>
                        <td>
                          <span className={`badge badge--${submission.status === 'approved' ? 'ok' : submission.status === 'rejected' ? 'error' : 'warn'}`}>
                            {trangThaiLabel}
                          </span>
                        </td>
                        <td>{submission.admin_note || '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {dashboardTab === 'places' && (
        <div className="owner-poi-grid">
          {poisCuaToi.length === 0 ? (
            <div className="card dashboard-content-card">
              <div className="empty-state"><p className="muted">Tài khoản của bạn chưa có địa điểm được quản lý.</p></div>
            </div>
          ) : poisCuaToi.map((poi) => (
            <article key={poi.id} className="card owner-poi-card">
              <div className="owner-poi-card__heading">
                <div>
                  <h2>{poi.name}</h2>
                  <p>{poi.lat.toFixed(5)}, {poi.lng.toFixed(5)} · Bán kính {poi.trigger_radius}m</p>
                </div>
                <span className="badge badge--ok">Đang quản lý</span>
              </div>
              <p className="owner-poi-card__description">{poi.description || 'Chưa có mô tả.'}</p>
              {poi.audio_url && layUrlAnh(poi.audio_url) && (
                <audio {...{ src: layUrlAnh(poi.audio_url) }} className="owner-poi-card__audio" controls preload="none">
                  Trình duyệt không hỗ trợ phát audio.
                </audio>
              )}
              <button
                className="btn btn--secondary btn--sm"
                type="button"
                onClick={() => {
                  setPoiDangSua(poi.id)
                  setTenQuan(poi.name)
                  setMoTa(poi.description)
                  setDashboardTab('submission')
                }}
              >
                Gửi cập nhật
              </button>
            </article>
          ))}
        </div>
      )}

      {dashboardTab === 'menu' && (
        <OwnerMenuManagement pois={poisCuaToi.map(({ id, name }) => ({ id, name }))} />
      )}

      {dashboardTab === 'qr' && (
        <OwnerPoiQrCodes pois={poisCuaToi} />
      )}

      {dashboardTab === 'notifications' && (
        <div className="card dashboard-content-card">
          <div className="section-header">
            <div>
              <h2 className="card__title">Thông báo</h2>
              <p className="card__subtitle">Các cập nhật từ đội ngũ vận hành.</p>
            </div>
            <span className="badge badge--neutral">{thongBao.length} thư</span>
          </div>

          {thongBao.length === 0 ? (
            <div className="empty-state">
              <p className="muted">Bạn chưa có thông báo nào mới.</p>
            </div>
          ) : (
            <ul className="notification-list">
              {thongBao.map((t) => (
                <li key={t.id} className={`notification-item${!t.read ? ' notification-item--unread' : ''}`}>
                  <div className="spread">
                    <div className="notification-item__content">
                      {!t.read && <span className="badge badge--error mr">Mới</span>}
                      <span>{t.message}</span>
                    </div>
                    {!t.read && (
                      <button
                        className="btn btn--secondary btn--sm"
                        type="button"
                        onClick={() => void danhDauDaDoc(t.id)}
                      >
                        Đánh dấu đã đọc
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </PortalDashboard>
  )
}
