import type { ReactNode } from 'react'

export interface PortalDashboardItem {
  key: string
  label: string
  icon: ReactNode
  badge?: number
}

interface PortalDashboardProps {
  role: 'admin' | 'owner'
  username: string
  title: string
  description: string
  activeItem: string
  items: PortalDashboardItem[]
  onNavigate: (key: string) => void
  onLogout: () => void
  children: ReactNode
}

export default function PortalDashboard({
  role,
  username,
  title,
  description,
  activeItem,
  items,
  onNavigate,
  onLogout,
  children,
}: PortalDashboardProps) {
  const isAdmin = role === 'admin'

  return (
    <div className={`portal-dashboard portal-dashboard--${role}`}>
      <aside className="portal-dashboard__sidebar">
        <a className="portal-dashboard__brand" href="/" aria-label="Về trang chủ Ẩm Thực Quận 4">
          <span className="portal-dashboard__brand-mark" aria-hidden="true">A</span>
          <span>Ẩm Thực Quận 4</span>
        </a>

        <span className="portal-dashboard__section-label">MENU</span>
        <nav className="portal-dashboard__nav" aria-label="Điều hướng cổng">
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`portal-dashboard__nav-item${activeItem === item.key ? ' portal-dashboard__nav-item--active' : ''}`}
              aria-current={activeItem === item.key ? 'page' : undefined}
              onClick={() => onNavigate(item.key)}
            >
              <span className="portal-dashboard__nav-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="portal-dashboard__nav-badge">{item.badge}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="portal-dashboard__sidebar-footer">
          <div className="portal-dashboard__help-card">
            <span className="portal-dashboard__help-icon" aria-hidden="true">
              {isAdmin ? 'Q4' : '♡'}
            </span>
            <strong>{isAdmin ? 'Cổng quản trị' : 'Đồng hành cùng quán'}</strong>
            <span>{isAdmin ? 'Quản lý hệ thống ẩm thực' : 'Cùng lan tỏa vị ngon địa phương'}</span>
          </div>
          <a className="portal-dashboard__home-link" href="/">← Về trang khám phá</a>
        </div>
      </aside>

      <div className="portal-dashboard__main">
        <header className="portal-dashboard__topbar">
          <div className="portal-dashboard__heading">
            <span className="portal-dashboard__mobile-brand">Ẩm Thực Quận 4</span>
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
          <div className="portal-dashboard__account">
            <div className="portal-dashboard__avatar" aria-hidden="true">
              {username.charAt(0).toUpperCase()}
            </div>
            <div className="portal-dashboard__account-copy">
              <strong>{username}</strong>
              <span>{isAdmin ? 'Quản trị viên' : 'Chủ quán'}</span>
            </div>
            <button className="portal-dashboard__logout" type="button" onClick={onLogout}>
              Đăng xuất
            </button>
          </div>
        </header>
        <div className="portal-dashboard__content">{children}</div>
      </div>
    </div>
  )
}
