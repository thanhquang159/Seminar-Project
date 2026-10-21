import { useState } from 'react'
import { api, apiText } from './api'

export default function OwnerApp() {
  const [user, setUser] = useState<string | null>(null)
  const [ten, setTen] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [cccd, setCccd] = useState('')
  const [loi, setLoi] = useState('')
  const [trangThai, setTrangThai] = useState('')
  const [tenQuan, setTenQuan] = useState('')
  const [moTa, setMoTa] = useState('')
  const [dangXuLyAI, setDangXuLyAI] = useState(false)
  const [thongBaoGui, setThongBaoGui] = useState('')
  const [thongBao, setThongBao] = useState<{ id: string; message: string; read: boolean }[]>([])

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
    setUser(ten)
    setMatKhau('')
    try {
      const st = await api<{ status: string }>('/owner/registration-status')
      setTrangThai(st.status)
    } catch {
      // 404 ở đây nghĩa là tài khoản không đăng ký chủ quán, tức admin.
      setTrangThai('admin')
      return
    }
    // Tách riêng vì chủ quán chưa duyệt bị 403 ở endpoint thông báo; nếu để
    // chung try thì lỗi này sẽ ghi đè trạng thái thật thành "admin" và giao
    // diện hiện sai (mất cảnh báo chờ duyệt lẫn ô gửi quán).
    setThongBao(await api<{ id: string; message: string; read: boolean }[]>('/owner/notifications').catch(() => []))
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
    setLoi(res.ok ? '' : 'Đăng ký thất bại (trùng tên tài khoản hoặc thiếu số CCCD)')
    if (res.ok) {
      setTrangThai('pending')
      setUser(ten)
    }
  }

  const guiQuan = async (dungAI: boolean) => {
    setLoi('')
    setThongBaoGui('')
    if (!tenQuan.trim()) {
      setLoi('Vui lòng nhập tên quán ăn')
      return
    }
    let moTaGui = moTa
    if (dungAI) {
      setDangXuLyAI(true)
      try {
        const goi = await api<{ text: string }>('/ai/enhance-description', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: moTa }),
        })
        moTaGui = goi.text
        setMoTa(goi.text)
      } catch {
        setLoi('AI bận hoặc hết lượt hôm nay')
        setDangXuLyAI(false)
        return
      } finally {
        setDangXuLyAI(false)
      }
    }
    try {
      await api('/owner/submissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: tenQuan, description: moTaGui, lat: 10.7569, lng: 106.7641 }),
      })
      setThongBaoGui('Đã gửi thông tin quán thành công! Quán đang chờ Admin phê duyệt.')
      setTenQuan('')
      setMoTa('')
    } catch {
      setLoi('Gửi quán thất bại, vui lòng kiểm tra lại thông tin')
    }
  }

  if (user === null) {
    return (
      <div className="login-card-wrapper">
        <div className="card login-card">
          <div className="login-card__header">
            <div className="login-card__icon-wrap login-card__icon-wrap--owner">
              <svg className="login-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 21h18M3 7v1a3 3 0 006 0V7m0 1a3 3 0 006 0V7m0 1a3 3 0 006 0V7M3 7l2-4h14l2 4M5 21V10.85M19 21V10.85M9 21v-4a2 2 0 012-2h2a2 2 0 012 2v4" />
              </svg>
            </div>
            <h2 className="card__title">Cổng Chủ Quán</h2>
            <p className="card__subtitle">Đăng nhập hoặc đăng ký tài khoản chủ quán để giới thiệu món ngon Quận 4</p>
          </div>

          <div className="field">
            <label className="field__label">Tên đăng nhập</label>
            <input
              className="input"
              placeholder="Tên đăng nhập"
              value={ten}
              onChange={(e) => setTen(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label">Mật khẩu</label>
            <input
              className="input"
              placeholder="Mật khẩu"
              type="password"
              value={matKhau}
              onChange={(e) => setMatKhau(e.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label">Số Căn cước công dân (CCCD)</label>
            <input
              className="input"
              placeholder="CCCD"
              value={cccd}
              onChange={(e) => setCccd(e.target.value)}
            />
            <span className="field__helper">Dữ liệu CCCD được mã hóa bảo mật chuẩn PII</span>
          </div>

          <div className="button-group mt">
            <button className="btn btn--primary" type="button" onClick={() => void dangNhap()}>
              Đăng nhập
            </button>
            <button className="btn btn--accent" type="button" onClick={() => void dangKy()}>
              Đăng ký chủ quán
            </button>
          </div>

          {loi !== '' && <div className="notice notice--error mt">{loi}</div>}
        </div>
      </div>
    )
  }

  const laDaDuyet = trangThai === 'approved' || trangThai === 'admin'

  return (
    <div className="owner-container">
      {/* Thẻ thông tin tài khoản */}
      <div className="card admin-header-card">
        <div className="spread">
          <div className="admin-user-info">
            <div className="admin-user-avatar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 21h18M3 7v1a3 3 0 006 0V7m0 1a3 3 0 006 0V7m0 1a3 3 0 006 0V7M3 7l2-4h14l2 4M5 21V10.85M19 21V10.85M9 21v-4a2 2 0 012-2h2a2 2 0 012 2v4" />
              </svg>
            </div>
            <div>
              <p className="admin-user-title">
                Chủ quán: <strong>{user}</strong>
              </p>
              <div className="row" style={{ gap: 6, marginTop: 4 }}>
                <span className={`badge badge--${laDaDuyet ? 'ok' : 'warn'}`}>
                  Trạng thái: {trangThai === 'approved' ? 'Đã được duyệt' : trangThai === 'pending' ? 'Đang chờ duyệt' : trangThai}
                </span>
              </div>
            </div>
          </div>
          <button className="btn btn--secondary btn--sm" type="button" onClick={() => setUser(null)}>
            Đăng xuất
          </button>
        </div>
      </div>

      {!laDaDuyet && (
        <div className="notice notice--warn mt">
          Tài khoản chờ duyệt, chưa gửi được quán.
        </div>
      )}

      {/* Form gửi quán mới */}
      <div className="card mt">
        <div className="section-header">
          <div>
            <h3 className="card__title">Gửi quán mới</h3>
            <p className="card__subtitle">Điền thông tin quán và món ngon đặc sắc để du khách ghé thăm</p>
          </div>
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
            onClick={() => void guiQuan(false)}
          >
            Gửi
          </button>
          <button
            className="btn btn--accent"
            type="button"
            disabled={!laDaDuyet || dangXuLyAI}
            onClick={() => void guiQuan(true)}
          >
            {dangXuLyAI ? 'Đang viết lại…' : 'AI viết lại rồi gửi'}
          </button>
        </div>

        {thongBaoGui !== '' && <div className="notice notice--ok mt">{thongBaoGui}</div>}
        {loi !== '' && <div className="notice notice--error mt">{loi}</div>}
      </div>

      {/* Hộp thư thông báo */}
      <div className="card mt">
        <div className="section-header">
          <h3 className="card__title">Thông báo</h3>
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
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
