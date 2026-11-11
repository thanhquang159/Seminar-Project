import { useEffect, useState } from 'react'
import { api, apiText } from './api'

interface DonDangKy {
  username: string
  status: string
}

interface SubmissionChoDuyet {
  id: string
  username: string
  name: string
  created_at: string | null
}

// Chủ quán đăng ký ở portal Owner; admin duyệt ở đây thì họ mới gửi được quán.
// Hai hàng đợi vì một chủ quán phải qua hai cổng: duyệt tài khoản, rồi duyệt
// từng quán. Thiếu một trong hai thì vòng lặp "gửi → thông báo" không đóng.
export default function OwnerApprovals() {
  const [don, setDon] = useState<DonDangKy[]>([])
  const [choDuyet, setChoDuyet] = useState<SubmissionChoDuyet[]>([])
  const [ghiChu, setGhiChu] = useState<Record<string, string>>({})
  const [lyDoTuChoi, setLyDoTuChoi] = useState<Record<string, string>>({})
  const [loi, setLoi] = useState('')

  const tai = async () => {
    try {
      setDon(await api<DonDangKy[]>('/owner/registrations'))
      setChoDuyet(await api<SubmissionChoDuyet[]>('/owner/submissions/pending'))
      setLoi('')
    } catch {
      setLoi('Không xem được danh sách duyệt (cần quyền user:update và poi:approve)')
    }
  }

  // Vào trang phải tải CẢ HAI hàng đợi: chỉ tải danh đăng ký thì hàng quán chờ
  // duyệt trống cho tới lần duyệt đầu, mà E2E kiểm đúng ô này.
  useEffect(() => {
    api<DonDangKy[]>('/owner/registrations')
      .then(setDon)
      .catch(() => setLoi('Không xem được danh sách đăng ký (cần quyền user:update)'))
    api<SubmissionChoDuyet[]>('/owner/submissions/pending')
      .then(setChoDuyet)
      .catch(() => setLoi('Không xem được danh sách quán chờ duyệt (cần quyền poi:approve)'))
  }, [])

  const duyetTaiKhoan = async (ten: string) => {
    await apiText(`/owner/registrations/${ten}/approve`, { method: 'POST' })
    await tai()
  }

  const tuChoi = async (ten: string) => {
    const note = (ghiChu[ten] ?? '').trim()
    if (note === '') {
      setLoi('Từ chối phải có ghi chú để chủ quán biết cần bổ sung gì')
      return
    }
    const res = await apiText(`/owner/registrations/${ten}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_note: note }),
    })
    if (!res.ok) {
      setLoi('Từ chối thất bại')
      return
    }
    await tai()
  }

  // Duyệt quán sẽ tạo POI và bắn thông báo cho chủ quán — đúng mốc mà E2E kiểm.
  const duyetQuan = async (id: string) => {
    const res = await apiText(`/owner/submissions/${id}/approve`, { method: 'POST' })
    if (!res.ok) {
      setLoi('Duyệt quán thất bại')
      return
    }
    await tai()
  }

  const tuChoiQuan = async (id: string) => {
    const admin_note = (lyDoTuChoi[id] ?? '').trim()
    if (admin_note === '') {
      setLoi('Vui lòng nhập lý do từ chối để chủ quán biết nội dung cần chỉnh sửa')
      return
    }
    const res = await apiText(`/owner/submissions/${id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_note }),
    })
    if (!res.ok) {
      setLoi('Từ chối quán thất bại')
      return
    }
    await tai()
  }

  return (
    <div className="card">
      <div className="section-header">
        <div>
          <h3 className="card__title">Kiểm duyệt chủ quán</h3>
          <p className="card__subtitle">Phê duyệt hồ sơ đăng ký tài khoản chủ quán và thẩm định quán ăn mới</p>
        </div>
      </div>

      {/* 1. Hàng đợi đơn đăng ký chủ quán */}
      <div className="approval-section mt">
        <div className="spread">
          <h4 className="approval-subtitle">
            1. Đơn đăng ký tài khoản chủ quán
          </h4>
          <span className="badge badge--neutral">{don.length} đơn</span>
        </div>

        {don.length === 0 ? (
          <div className="empty-state">
            <p className="muted">Không có đơn đăng ký nào đang chờ duyệt.</p>
          </div>
        ) : (
          <div className="table-responsive mt">
            <table className="table">
              <thead>
                <tr>
                  <th>Tài khoản & Ghi chú từ chối</th>
                  <th style={{ textAlign: 'right', width: 200 }}>Xử lý</th>
                </tr>
              </thead>
              <tbody>
                {don.map((d) => (
                  <tr key={d.username}>
                    <td>
                      <div className="user-approval-cell">
                        <span className="user-avatar-tag">
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                            <circle cx="12" cy="7" r="4" />
                          </svg>
                          {d.username}
                        </span>
                        <div className="field mt-xs">
                          <input
                            className="input input--sm"
                            placeholder="Ghi chú khi từ chối"
                            value={ghiChu[d.username] ?? ''}
                            onChange={(e) => setGhiChu({ ...ghiChu, [d.username]: e.target.value })}
                          />
                        </div>
                      </div>
                    </td>
                    <td style={{ textAlign: 'right', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                      <button
                        className="btn btn--sm btn--primary mr-xs"
                        type="button"
                        onClick={() => void duyetTaiKhoan(d.username)}
                      >
                        Duyệt
                      </button>
                      <button
                        className="btn btn--sm btn--danger"
                        type="button"
                        onClick={() => void tuChoi(d.username)}
                      >
                        Từ chối
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 2. Hàng đợi quán chờ duyệt */}
      <div className="approval-section mt-lg">
        <div className="spread">
          <h4 className="approval-subtitle">
            2. Quán ăn gửi lên chờ duyệt tạo POI
          </h4>
          <span className="badge badge--neutral">{choDuyet.length} quán</span>
        </div>

        {choDuyet.length === 0 ? (
          <div className="empty-state">
            <p className="muted">Không có quán nào đang chờ duyệt.</p>
          </div>
        ) : (
          <div className="table-responsive mt">
            <table className="table">
              <thead>
                <tr>
                  <th>Tên quán ăn đề xuất & lý do từ chối</th>
                  <th>Chủ quán gửi</th>
                  <th style={{ textAlign: 'right', width: 140 }}>Hành động</th>
                </tr>
              </thead>
              <tbody>
                {choDuyet.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <strong className="poi-title-cell">{s.name}</strong>
                      <input
                        className="input input--sm mt-xs"
                        aria-label={`Lý do từ chối ${s.name}`}
                        placeholder="Nhập lý do nếu từ chối"
                        value={lyDoTuChoi[s.id] ?? ''}
                        onChange={(event) => setLyDoTuChoi({ ...lyDoTuChoi, [s.id]: event.target.value })}
                      />
                    </td>
                    <td>
                      <span className="badge badge--neutral">{s.username}</span>
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button
                        className="btn btn--sm btn--primary"
                        type="button"
                        onClick={() => void duyetQuan(s.id)}
                      >
                        Duyệt quán
                      </button>
                      <button
                        className="btn btn--sm btn--danger ml"
                        type="button"
                        onClick={() => void tuChoiQuan(s.id)}
                      >
                        Từ chối
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {loi !== '' && <div className="notice notice--error mt">{loi}</div>}
    </div>
  )
}
