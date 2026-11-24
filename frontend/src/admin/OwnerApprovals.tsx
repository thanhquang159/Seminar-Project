import { useEffect, useState } from 'react'
import { api, apiText } from './api'
import { apiErrorMessage } from './apiErrors'

interface DonDangKy {
  username: string
  status: string
}

interface SubmissionChoDuyet {
  id: string
  username: string
  name: string
  created_at: string | null
  can_approve?: boolean
  approval_blockers?: string[]
  data: {
    address_line?: string
    lat?: number
    lng?: number
    menu?: {
      name?: string
      description?: string
      items?: { name: string; price?: number | null }[]
    } | null
  }
}

// Chủ quán đăng ký ở portal Owner; admin duyệt ở đây thì họ mới gửi được quán.
// Hai hàng đợi vì một chủ quán phải qua hai cổng: duyệt tài khoản, rồi duyệt
// từng quán. Thiếu một trong hai thì vòng lặp "gửi → thông báo" không đóng.
export default function OwnerApprovals({ onPoiApproved }: { onPoiApproved: () => void | Promise<void> }) {
  const [don, setDon] = useState<DonDangKy[]>([])
  const [choDuyet, setChoDuyet] = useState<SubmissionChoDuyet[]>([])
  const [ghiChu, setGhiChu] = useState<Record<string, string>>({})
  const [lyDoTuChoi, setLyDoTuChoi] = useState<Record<string, string>>({})
  const [loi, setLoi] = useState('')
  const [thongBaoDuyet, setThongBaoDuyet] = useState('')
  const [busy, setBusy] = useState(false)

  const tai = async () => {
    const [registrations, submissions] = await Promise.allSettled([
      api<DonDangKy[]>('/owner/registrations'), api<SubmissionChoDuyet[]>('/owner/submissions/pending'),
    ])
    const errors: string[] = []
    if (registrations.status === 'fulfilled') setDon(registrations.value)
    else errors.push('Không tải được đơn đăng ký (cần quyền user:update).')
    if (submissions.status === 'fulfilled') setChoDuyet(submissions.value)
    else errors.push('Không tải được quán chờ duyệt (cần quyền poi:approve).')
    setLoi(errors.join(' '))
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

  const thucHien = async (path: string, label: string, body?: object, poiApproved = false) => {
    if (busy) return
    setBusy(true)
    setLoi('')
    setThongBaoDuyet('')
    try {
      const res = await apiText(path, {
        method: 'POST',
        ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
      })
      if (!res.ok) {
        setLoi(await apiErrorMessage(res, `${label} thất bại`))
        return
      }
      setThongBaoDuyet(poiApproved
        ? 'Đã duyệt nội dung. POI chưa công khai: mở Quản lý POI, chuẩn bị English + Audio, kiểm tra điều kiện rồi bấm Công khai.'
        : `${label} thành công.`)
      await tai()
      if (poiApproved) {
        try { await onPoiApproved() }
        catch { setLoi('Đã duyệt thành công nhưng chưa tải lại được danh sách POI. Vui lòng tải lại trang.') }
      }
    } catch {
      setLoi('Không kết nối được máy chủ. Vui lòng kiểm tra kết nối và thử lại.')
    } finally {
      setBusy(false)
    }
  }

  const duyetTaiKhoan = async (ten: string) => {
    await thucHien(`/owner/registrations/${encodeURIComponent(ten)}/approve`, 'Duyệt tài khoản')
  }

  const tuChoi = async (ten: string) => {
    const note = (ghiChu[ten] ?? '').trim()
    if (note === '') {
      setLoi('Từ chối phải có ghi chú để chủ quán biết cần bổ sung gì')
      return
    }
    await thucHien(`/owner/registrations/${encodeURIComponent(ten)}/reject`, 'Từ chối tài khoản', { admin_note: note })
  }

  // Duyệt quán sẽ tạo POI và bắn thông báo cho chủ quán — đúng mốc mà E2E kiểm.
  const duyetQuan = async (id: string) => {
    await thucHien(`/owner/submissions/${id}/approve`, 'Duyệt quán', undefined, true)
  }

  const tuChoiQuan = async (id: string) => {
    const admin_note = (lyDoTuChoi[id] ?? '').trim()
    if (admin_note === '') {
      setLoi('Vui lòng nhập lý do từ chối để chủ quán biết nội dung cần chỉnh sửa')
      return
    }
    await thucHien(`/owner/submissions/${id}/reject`, 'Từ chối quán', { admin_note })
  }

  return (
    <div className="card">
      <div className="section-header">
        <div>
          <h3 className="card__title">Kiểm duyệt chủ quán</h3>
          <p className="card__subtitle">Chỉ hiển thị hồ sơ và đề xuất đang chờ duyệt. Quán đã duyệt được quản lý và công khai tại danh sách POI; quán do Admin tạo trực tiếp không có đơn Owner chờ duyệt.</p>
        </div>
        <button type="button" className="btn btn--secondary btn--sm" disabled={busy}
          onClick={() => void tai()}>Tải lại danh sách</button>
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
                        disabled={busy}
                        onClick={() => void duyetTaiKhoan(d.username)}
                      >
                        Duyệt
                      </button>
                      <button
                        className="btn btn--sm btn--danger"
                        type="button"
                        disabled={busy}
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
                      {s.approval_blockers?.map((reason) => <p key={reason} className="notice notice--warn">{reason}</p>)}
                      <div className="muted mt-xs">
                        {s.data.address_line || 'Chưa có địa chỉ'} ·{' '}
                        {typeof s.data.lat === 'number' && typeof s.data.lng === 'number'
                          ? `${s.data.lat}, ${s.data.lng}`
                          : 'Chưa có tọa độ'}
                      </div>
                      {s.data.menu && (
                        <div className="muted mt-xs">
                          {s.data.menu.name || 'Thực đơn'}
                          {s.data.menu.items?.length
                            ? ` · ${s.data.menu.items.map((item) => item.name).join(', ')}`
                            : ''}
                        </div>
                      )}
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
                        disabled={busy || s.can_approve === false}
                        onClick={() => void duyetQuan(s.id)}
                      >
                        Duyệt quán
                      </button>
                      <button
                        className="btn btn--sm btn--danger ml"
                        type="button"
                        disabled={busy}
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

      {thongBaoDuyet && <div className="notice notice--ok mt" role="status">{thongBaoDuyet}</div>}
      {loi !== '' && <div className="notice notice--error mt" role="alert">{loi}</div>}
    </div>
  )
}
