import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api } from './api'

interface AdminUser {
  id: string
  email: string
  full_name: string
  account_status: 'pending' | 'active' | 'rejected'
  role_code: string | null
  role_name: string | null
}

interface AdminRole {
  name: string
  priority: number | null
  permissions: string[]
}

interface RoleCreateResult {
  role_code: string
  name: string
  description: string | null
  permission_codes: string[]
}

const SYSTEM_ROLES = new Set(['ADMIN', 'OWNER', 'SUPER_ADMIN', 'POI_OWNER'])
// Keep in sync with backend/app/routers/admin_users.py; server checks remain authoritative.
const ADMIN_PERMISSIONS = new Set([
  'analytics.read',
  'audit_logs.read',
  'owner_registrations.review',
  'pois.manage',
  'pois.publish',
  'runtime.read',
  'submissions.review',
  'users.read',
  'roles.manage',
  'users.manage',
  'role:read',
  'user:update',
])

function isSystemRole(role: AdminRole): boolean {
  return SYSTEM_ROLES.has(role.name.toUpperCase())
}

export default function AdminAccessManagement() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [roles, setRoles] = useState<AdminRole[]>([])
  const [drafts, setDrafts] = useState<Record<string, { account_status: string; role_code: string }>>({})
  const [selectedRole, setSelectedRole] = useState('')
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [savingUser, setSavingUser] = useState('')
  const [savingRole, setSavingRole] = useState(false)
  const [savingNewRole, setSavingNewRole] = useState(false)
  const [newRoleCode, setNewRoleCode] = useState('')
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleDescription, setNewRoleDescription] = useState('')
  const [newRolePermissions, setNewRolePermissions] = useState<string[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([api<AdminUser[]>('/admin/users'), api<AdminRole[]>('/admin/roles')])
      .then(([userRows, roleRows]) => {
        if (!active) return
        setUsers(userRows)
        setRoles(roleRows)
        const editableRole = roleRows.find((role) => !isSystemRole(role))
        if (editableRole) {
          setSelectedRole(editableRole.name)
          setSelectedPermissions(editableRole.permissions.filter((permission) => !ADMIN_PERMISSIONS.has(permission)))
        }
      })
      .catch(() => {
        if (active) setError('Không tải được tài khoản hoặc vai trò. Cần quyền quản lý tương ứng.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const editableRoles = useMemo(
    () => roles.filter((role) => !isSystemRole(role) && !role.permissions.some((permission) => ADMIN_PERMISSIONS.has(permission))),
    [roles],
  )
  const permissionCatalog = useMemo(
    () => Array.from(new Set(roles.flatMap((role) => role.permissions)))
      .filter((permission) => !ADMIN_PERMISSIONS.has(permission))
      .sort(),
    [roles],
  )
  const selectedRoleData = roles.find((role) => role.name === selectedRole)
  const assignableRoles = editableRoles.filter((role) => !role.permissions.some((permission) => ADMIN_PERMISSIONS.has(permission)))

  function updateDraft(user: AdminUser, key: 'account_status' | 'role_code', value: string) {
    setDrafts((current) => ({
      ...current,
      [user.id]: {
        account_status: current[user.id]?.account_status ?? user.account_status,
        role_code: current[user.id]?.role_code ?? user.role_code ?? '',
        [key]: value,
      },
    }))
  }

  async function saveUser(user: AdminUser) {
    const draft = drafts[user.id]
    if (!draft) return
    const body: { account_status?: string; role_code?: string | null } = {}
    if (draft.account_status !== user.account_status) body.account_status = draft.account_status
    if (draft.role_code !== (user.role_code ?? '')) body.role_code = draft.role_code || null
    if (Object.keys(body).length === 0) return
    setSavingUser(user.id)
    setError('')
    setNotice('')
    try {
      const updated = await api<Pick<AdminUser, 'id' | 'account_status' | 'role_code'>>(`/admin/users/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      setUsers((current) => current.map((item) => item.id === updated.id
        ? {
            ...item,
            account_status: updated.account_status,
            role_code: updated.role_code,
            role_name: updated.role_code === user.role_code
              ? user.role_name
              : assignableRoles.find((role) => role.name === updated.role_code)?.name ?? null,
          }
        : item))
      setDrafts((current) => {
        const next = { ...current }
        delete next[user.id]
        return next
      })
      setNotice('Đã cập nhật tài khoản.')
    } catch {
      setError('Không thể cập nhật tài khoản. Hãy kiểm tra quyền, trạng thái và vai trò được phép gán.')
    } finally {
      setSavingUser('')
    }
  }

  async function saveRolePermissions() {
    if (!selectedRole) return
    setSavingRole(true)
    setError('')
    setNotice('')
    try {
      await api(`/admin/roles/${encodeURIComponent(selectedRole)}/permissions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ permission_codes: selectedPermissions }),
      })
      setRoles((current) => current.map((role) => role.name === selectedRole
        ? { ...role, permissions: selectedPermissions }
        : role))
      setNotice('Đã cập nhật quyền của vai trò.')
    } catch {
      setError('Không thể cập nhật quyền. Chỉ vai trò không phải hệ thống và không có quyền quản trị mới được sửa.')
    } finally {
      setSavingRole(false)
    }
  }

  async function createRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSavingNewRole(true)
    setError('')
    setNotice('')
    try {
      const created = await api<RoleCreateResult>('/admin/roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: newRoleCode.trim(),
          name: newRoleName.trim(),
          description: newRoleDescription.trim() || null,
          permission_codes: newRolePermissions,
        }),
      })
      const role: AdminRole = {
        name: created.role_code,
        priority: null,
        permissions: created.permission_codes,
      }
      setRoles((current) => [...current, role])
      setSelectedRole(role.name)
      setSelectedPermissions(role.permissions)
      setNewRoleCode('')
      setNewRoleName('')
      setNewRoleDescription('')
      setNewRolePermissions([])
      setNotice('Đã tạo vai trò tùy chỉnh.')
    } catch {
      setError('Không thể tạo vai trò. Mã có thể đã tồn tại hoặc quyền không được cấp phép.')
    } finally {
      setSavingNewRole(false)
    }
  }

  function changeRole(roleName: string) {
    setSelectedRole(roleName)
    const role = roles.find((item) => item.name === roleName)
    setSelectedPermissions(role?.permissions.filter((permission) => !ADMIN_PERMISSIONS.has(permission)) ?? [])
  }

  return (
    <section className="card admin-governance">
      <div className="section-header">
        <div>
          <h2 className="card__title">Tài khoản, vai trò & quyền</h2>
          <p className="card__subtitle">Quản lý trạng thái tài khoản và quyền của các vai trò không đặc quyền.</p>
        </div>
        <span className="badge badge--neutral">{users.length} tài khoản</span>
      </div>

      {error && <div className="notice notice--error mt" role="alert">{error}</div>}
      {notice && <div className="notice notice--success mt" role="status">{notice}</div>}
      {loading ? (
        <div className="empty-state"><p className="muted">Đang tải tài khoản…</p></div>
      ) : users.length === 0 ? (
        <div className="empty-state"><p className="muted">Chưa có tài khoản để quản lý.</p></div>
      ) : (
        <div className="table-responsive mt">
          <table className="table">
            <thead>
              <tr><th>Tài khoản</th><th>Trạng thái</th><th>Vai trò</th><th>Thao tác</th></tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const draft = drafts[user.id]
                const hasProtectedRole = Boolean(
                  user.role_code && !assignableRoles.some((role) => role.name === user.role_code),
                )
                return (
                  <tr key={user.id}>
                    <td><strong>{user.full_name || user.email}</strong><br /><span className="muted">{user.email}</span></td>
                    <td>
                      <select
                        className="input"
                        aria-label={`Trạng thái ${user.email}`}
                        value={draft?.account_status ?? user.account_status}
                        onChange={(event) => updateDraft(user, 'account_status', event.target.value)}
                      >
                        <option value="pending">Chờ duyệt</option>
                        <option value="active">Hoạt động</option>
                        <option value="rejected">Từ chối</option>
                      </select>
                    </td>
                    <td>
                      <select
                        className="input"
                        aria-label={`Vai trò ${user.email}`}
                        value={draft?.role_code ?? user.role_code ?? ''}
                        disabled={hasProtectedRole}
                        onChange={(event) => updateDraft(user, 'role_code', event.target.value)}
                      >
                        {hasProtectedRole ? (
                          <option value={user.role_code ?? ''}>{user.role_name || user.role_code} (không thể gán lại)</option>
                        ) : <option value="">Không gán vai trò</option>}
                        {assignableRoles.map((role) => <option key={role.name} value={role.name}>{role.name}</option>)}
                      </select>
                    </td>
                    <td>
                      <button
                        className="btn btn--primary btn--sm"
                        type="button"
                        disabled={!draft || (
                          draft.account_status === user.account_status
                          && draft.role_code === (user.role_code ?? '')
                        ) || savingUser === user.id}
                        onClick={() => void saveUser(user)}
                      >
                        {savingUser === user.id ? 'Đang lưu…' : 'Lưu'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <form className="admin-governance__role-create mt" onSubmit={(event) => void createRole(event)}>
        <div>
          <h3 className="card__title">Tạo vai trò tùy chỉnh</h3>
          <p className="card__subtitle">Chỉ quyền đã được provision và không đặc quyền mới được cấp.</p>
        </div>
        <div className="admin-governance__role-fields">
          <label className="field">
            <span className="field__label">Mã vai trò</span>
            <input
              className="input"
              required
              minLength={2}
              maxLength={64}
              pattern="[a-z][a-z0-9_]{1,63}"
              value={newRoleCode}
              onChange={(event) => setNewRoleCode(event.target.value)}
              placeholder="content_editor"
            />
          </label>
          <label className="field">
            <span className="field__label">Tên vai trò</span>
            <input
              className="input"
              required
              maxLength={120}
              value={newRoleName}
              onChange={(event) => setNewRoleName(event.target.value)}
              placeholder="Biên tập nội dung"
            />
          </label>
          <label className="field">
            <span className="field__label">Mô tả (không bắt buộc)</span>
            <input
              className="input"
              maxLength={500}
              value={newRoleDescription}
              onChange={(event) => setNewRoleDescription(event.target.value)}
            />
          </label>
        </div>
        {permissionCatalog.length > 0 && (
          <div className="admin-governance__permissions">
            {permissionCatalog.map((permission) => (
              <label className="admin-governance__permission-option" key={permission}>
                <input
                  type="checkbox"
                  checked={newRolePermissions.includes(permission)}
                  onChange={(event) => setNewRolePermissions((current) => event.target.checked
                    ? [...current, permission].sort()
                    : current.filter((item) => item !== permission))}
                />
                <span>{permission}</span>
              </label>
            ))}
          </div>
        )}
        <button className="btn btn--primary mt" type="submit" disabled={savingNewRole}>
          {savingNewRole ? 'Đang tạo…' : 'Tạo vai trò'}
        </button>
      </form>

      <div className="admin-governance__role-editor mt">
        <div className="section-header">
          <div>
            <h3 className="card__title">Quyền vai trò</h3>
            <p className="card__subtitle">Chỉ dùng các quyền đã được provision; quyền quản trị và vai trò hệ thống không thể sửa.</p>
          </div>
        </div>
        {editableRoles.length === 0 ? (
          <div className="empty-state"><p className="muted">Không có vai trò tùy chỉnh đủ điều kiện chỉnh sửa.</p></div>
        ) : (
          <>
            <label className="field">
              <span className="field__label">Vai trò cần sửa</span>
              <select className="input" value={selectedRole} onChange={(event) => changeRole(event.target.value)}>
                {editableRoles.map((role) => <option key={role.name} value={role.name}>{role.name}</option>)}
              </select>
            </label>
            {selectedRoleData && permissionCatalog.length > 0 ? (
              <div className="admin-governance__permissions mt">
                {permissionCatalog.map((permission) => (
                  <label className="admin-governance__permission-option" key={permission}>
                    <input
                      type="checkbox"
                      checked={selectedPermissions.includes(permission)}
                      onChange={(event) => setSelectedPermissions((current) => event.target.checked
                        ? [...current, permission].sort()
                        : current.filter((item) => item !== permission))}
                    />
                    <span>{permission}</span>
                  </label>
                ))}
              </div>
            ) : <p className="muted">Chưa có danh mục quyền đã provision để chỉnh sửa.</p>}
            <button className="btn btn--primary mt" type="button" disabled={savingRole} onClick={() => void saveRolePermissions()}>
              {savingRole ? 'Đang lưu…' : 'Lưu quyền vai trò'}
            </button>
          </>
        )}
      </div>
    </section>
  )
}
