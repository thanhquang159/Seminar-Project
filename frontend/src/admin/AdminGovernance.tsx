import { useEffect, useMemo, useState } from 'react'
import { api } from './api'

interface AuditLog {
  action: string
  username: string
  resource: string
  timestamp: string
}

interface Role {
  name: string
  priority: number | null
  permissions: string[]
}

export default function AdminGovernance({ section }: { section: 'audit' | 'roles' }) {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [loi, setLoi] = useState('')
  const [dangTai, setDangTai] = useState(true)
  const [nguoiDung, setNguoiDung] = useState('')
  const [hanhDong, setHanhDong] = useState('')
  const [ngay, setNgay] = useState('')

  useEffect(() => {
    let active = true
    const request = section === 'audit'
      ? api<AuditLog[]>('/admin/audit-logs').then((data) => {
          if (active) setLogs(data)
        })
      : api<Role[]>('/admin/roles').then((data) => {
          if (active) setRoles(data)
        })
    request
      .catch(() => {
        if (active) setLoi(section === 'audit'
          ? 'Không tải được audit log. Tài khoản cần quyền audit:read.'
          : 'Không tải được danh sách vai trò. Tài khoản cần quyền role:read.')
      })
      .finally(() => {
        if (active) setDangTai(false)
      })
    return () => {
      active = false
    }
  }, [section])

  const logsFiltered = useMemo(() => {
    const usernameFilter = nguoiDung.trim().toLocaleLowerCase()
    const actionFilter = hanhDong.trim().toLocaleLowerCase()
    return logs.filter((log) => {
      const time = new Date(log.timestamp)
      return (!usernameFilter || log.username.toLocaleLowerCase().includes(usernameFilter))
        && (!actionFilter || `${log.action} ${log.resource}`.toLocaleLowerCase().includes(actionFilter))
        && (!ngay || (!Number.isNaN(time.getTime()) && time.toISOString().slice(0, 10) === ngay))
    })
  }, [hanhDong, logs, ngay, nguoiDung])

  return (
    <section className="card admin-governance">
      <div className="section-header">
        <div>
          <h2 className="card__title">{section === 'audit' ? 'Nhật ký hoạt động' : 'Vai trò & quyền hạn'}</h2>
          <p className="card__subtitle">
            {section === 'audit'
              ? 'Tra cứu các thao tác quản trị được hệ thống ghi nhận.'
              : 'Danh sách vai trò và quyền đang được cấu hình trong hệ thống.'}
          </p>
        </div>
        {section === 'audit' && <span className="badge badge--neutral">{logsFiltered.length} bản ghi</span>}
      </div>

      {section === 'audit' && (
        <div className="admin-governance__filters">
          <div className="field">
            <label className="field__label" htmlFor="audit-user-filter">Người thực hiện</label>
            <input id="audit-user-filter" className="input" value={nguoiDung} onChange={(event) => setNguoiDung(event.target.value)} placeholder="Lọc theo tài khoản" />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="audit-action-filter">Thao tác / tài nguyên</label>
            <input id="audit-action-filter" className="input" value={hanhDong} onChange={(event) => setHanhDong(event.target.value)} placeholder="Ví dụ: approve, poi" />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="audit-date-filter">Ngày</label>
            <input id="audit-date-filter" className="input" type="date" value={ngay} onChange={(event) => setNgay(event.target.value)} />
          </div>
        </div>
      )}

      {loi && <div className="notice notice--error mt" role="alert">{loi}</div>}
      {dangTai ? (
        <div className="empty-state"><p className="muted">Đang tải dữ liệu…</p></div>
      ) : section === 'audit' ? (
        logsFiltered.length === 0 ? (
          <div className="empty-state"><p className="muted">Không có bản ghi phù hợp.</p></div>
        ) : (
          <div className="table-responsive mt">
            <table className="table">
              <thead>
                <tr><th>Thời gian</th><th>Người thực hiện</th><th>Thao tác</th><th>Tài nguyên</th></tr>
              </thead>
              <tbody>
                {logsFiltered.map((log, index) => (
                  <tr key={`${log.timestamp}-${log.username}-${index}`}>
                    <td>{new Date(log.timestamp).toLocaleString('vi-VN')}</td>
                    <td>{log.username}</td>
                    <td><span className="badge badge--info">{log.action}</span></td>
                    <td>{log.resource}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : roles.length === 0 ? (
        <div className="empty-state"><p className="muted">Chưa có vai trò nào.</p></div>
      ) : (
        <div className="admin-governance__roles">
          {roles.map((role) => (
            <article key={role.name} className="admin-governance__role-card">
              <div className="spread">
                <div>
                  <h3>{role.name}</h3>
                  {role.priority !== null && <span className="muted">Độ ưu tiên: {role.priority}</span>}
                </div>
                <span className="badge badge--neutral">{role.permissions.length} quyền</span>
              </div>
              <div className="admin-governance__permissions">
                {role.permissions.map((permission) => <span className="badge badge--info" key={permission}>{permission}</span>)}
              </div>
            </article>
          ))}
          <p className="muted admin-governance__readonly">
            Chỉnh sửa vai trò chưa được bật trong API hiện tại; danh sách này chỉ để xem.
          </p>
        </div>
      )}
    </section>
  )
}
