import { useEffect, useState } from 'react'
import { api, apiText } from './api'
import { layUrlAnh } from '../components/imageUtils'

interface MenuItem {
  id: string
  menu_id: string
  name: string
  description: string | null
  price: number | null
  currency_code: string
  image_url: string | null
  is_available: boolean
  sort_order: number
}

interface OwnerMenu {
  id: string
  poi_id: string
  name: string
  description: string | null
  is_active: boolean
  items: MenuItem[]
}

interface ItemDraft {
  name: string
  description: string
  price: string
  image_url: string
  is_available: boolean
}

const EMPTY_DRAFT: ItemDraft = {
  name: '',
  description: '',
  price: '',
  image_url: '',
  is_available: true,
}

export default function OwnerMenuManagement({
  pois,
}: {
  pois: { id: string; name: string }[]
}) {
  const [poiId, setPoiId] = useState(pois[0]?.id ?? '')
  const [menus, setMenus] = useState<OwnerMenu[]>([])
  const [drafts, setDrafts] = useState<Record<string, ItemDraft>>({})
  const [editing, setEditing] = useState<Record<string, ItemDraft>>({})
  const [loi, setLoi] = useState('')
  const [thongBao, setThongBao] = useState('')
  const [dangTai, setDangTai] = useState(true)
  const selectedPoiId = pois.some((poi) => poi.id === poiId) ? poiId : pois[0]?.id ?? ''

  const taiMenus = async (targetPoi = selectedPoiId) => {
    if (!targetPoi) {
      setMenus([])
      return
    }
    setDangTai(true)
    setLoi('')
    try {
      setMenus(await api<OwnerMenu[]>(`/owner/pois/${targetPoi}/menus`))
    } catch {
      setLoi('Không tải được thực đơn của địa điểm này.')
    } finally {
      setDangTai(false)
    }
  }

  useEffect(() => {
    let active = true
    if (!selectedPoiId) return
    api<OwnerMenu[]>(`/owner/pois/${selectedPoiId}/menus`)
      .then((data) => {
        if (active) setMenus(data)
      })
      .catch(() => {
        if (active) setLoi('Không tải được thực đơn của địa điểm này.')
      })
      .finally(() => {
        if (active) setDangTai(false)
      })
    return () => {
      active = false
    }
  }, [selectedPoiId])

  const taoMenu = async () => {
    if (!selectedPoiId) return
    setLoi('')
    setThongBao('')
    try {
      await api<OwnerMenu>(`/owner/pois/${selectedPoiId}/menus`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Menu chính', is_active: true }),
      })
      setThongBao('Đã tạo thực đơn.')
      await taiMenus()
    } catch {
      setLoi('Tạo thực đơn thất bại. Vui lòng thử lại.')
    }
  }

  const luuMon = async (menuId: string, draft: ItemDraft, itemId?: string) => {
    if (!draft.name.trim()) {
      setLoi('Vui lòng nhập tên món.')
      return
    }
    const price = draft.price.trim() ? Number(draft.price) : null
    if (price !== null && (!Number.isFinite(price) || price < 0)) {
      setLoi('Giá món phải là số không âm.')
      return
    }
    setLoi('')
    setThongBao('')
    const payload = {
      name: draft.name.trim(),
      description: draft.description.trim() || null,
      price,
      image_url: draft.image_url.trim() || null,
      is_available: draft.is_available,
    }
    try {
      const response = await apiText(
        itemId
          ? `/owner/menus/${menuId}/items/${itemId}`
          : `/owner/menus/${menuId}/items`,
        {
          method: itemId ? 'PUT' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        },
      )
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setDrafts((all) => ({ ...all, [menuId]: EMPTY_DRAFT }))
      setEditing((all) => {
        const next = { ...all }
        if (itemId) delete next[itemId]
        return next
      })
      setThongBao(itemId ? 'Đã cập nhật món ăn.' : 'Đã thêm món ăn.')
      await taiMenus()
    } catch {
      setLoi('Không lưu được món ăn. Vui lòng kiểm tra thông tin và thử lại.')
    }
  }

  const xoaMon = async (menuId: string, itemId: string) => {
    if (!window.confirm('Bạn có chắc muốn xóa món này khỏi thực đơn?')) return
    setLoi('')
    try {
      const response = await apiText(`/owner/menus/${menuId}/items/${itemId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setThongBao('Đã xóa món ăn.')
      await taiMenus()
    } catch {
      setLoi('Không xóa được món ăn. Vui lòng thử lại.')
    }
  }

  return (
    <section className="card dashboard-content-card owner-menu-management">
      <div className="section-header">
        <div>
          <h2 className="card__title">Thực đơn</h2>
          <p className="card__subtitle">Quản lý món ăn, giá và tình trạng phục vụ tại địa điểm của bạn.</p>
        </div>
      </div>

      {pois.length === 0 ? (
        <div className="empty-state"><p className="muted">Tài khoản chưa có địa điểm để quản lý thực đơn.</p></div>
      ) : (
        <>
          <div className="owner-menu-management__toolbar">
            <label className="field">
              <span className="field__label">Địa điểm</span>
              <select
                className="input"
                value={selectedPoiId}
                onChange={(event) => {
                  setDangTai(true)
                  setLoi('')
                  setMenus([])
                  setPoiId(event.target.value)
                }}
              >
                {pois.map((poi) => <option value={poi.id} key={poi.id}>{poi.name}</option>)}
              </select>
            </label>
            <button className="btn btn--secondary" type="button" onClick={() => void taoMenu()} disabled={!selectedPoiId}>
              Tạo thực đơn
            </button>
          </div>

          {loi && <div className="notice notice--error mt" role="alert">{loi}</div>}
          {thongBao && <div className="notice notice--ok mt" role="status">{thongBao}</div>}

          {dangTai ? (
            <div className="empty-state"><p className="muted">Đang tải thực đơn…</p></div>
          ) : menus.length === 0 ? (
            <div className="empty-state"><p className="muted">Địa điểm này chưa có thực đơn. Tạo thực đơn để bắt đầu thêm món.</p></div>
          ) : (
            <div className="owner-menu-management__menus">
              {menus.map((menu) => (
                <section className="owner-menu-card" key={menu.id}>
                  <div className="spread">
                    <div>
                      <h3>{menu.name}</h3>
                      {menu.description && <p className="muted">{menu.description}</p>}
                    </div>
                    <span className={`badge badge--${menu.is_active ? 'ok' : 'neutral'}`}>
                      {menu.is_active ? 'Đang hiển thị' : 'Đã ẩn'}
                    </span>
                  </div>

                  {menu.items.length > 0 && (
                    <div className="owner-menu-card__items">
                      {menu.items.map((item) => {
                        const draft = editing[item.id]
                        return (
                          <article className="owner-menu-item" key={item.id}>
                            {draft ? (
                              <div className="owner-menu-item__edit">
                                <input className="input" aria-label="Tên món" value={draft.name} onChange={(event) => setEditing((all) => ({ ...all, [item.id]: { ...draft, name: event.target.value } }))} />
                                <textarea className="input textarea" aria-label="Mô tả món" rows={2} value={draft.description} onChange={(event) => setEditing((all) => ({ ...all, [item.id]: { ...draft, description: event.target.value } }))} />
                                <div className="form-grid-2">
                                  <input className="input" aria-label="Giá món" type="number" min="0" step="1000" value={draft.price} onChange={(event) => setEditing((all) => ({ ...all, [item.id]: { ...draft, price: event.target.value } }))} />
                                  <input className="input" aria-label="Ảnh món" type="url" placeholder="URL hình ảnh" value={draft.image_url} onChange={(event) => setEditing((all) => ({ ...all, [item.id]: { ...draft, image_url: event.target.value } }))} />
                                </div>
                                <label className="owner-menu-item__availability">
                                  <input type="checkbox" checked={draft.is_available} onChange={(event) => setEditing((all) => ({ ...all, [item.id]: { ...draft, is_available: event.target.checked } }))} />
                                  Đang phục vụ
                                </label>
                                <div className="row">
                                  <button className="btn btn--primary btn--sm" type="button" onClick={() => void luuMon(menu.id, draft, item.id)}>Lưu</button>
                                  <button className="btn btn--secondary btn--sm" type="button" onClick={() => setEditing((all) => { const next = { ...all }; delete next[item.id]; return next })}>Hủy</button>
                                </div>
                              </div>
                            ) : (
                              <>
                                <div className="owner-menu-item__details">
                                  {item.image_url && layUrlAnh(item.image_url) && (
                                    <img {...{ src: layUrlAnh(item.image_url) }} alt="" loading="lazy" />
                                  )}
                                  <div>
                                    <strong>{item.name}</strong>
                                    <p>{item.description || 'Chưa có mô tả.'}</p>
                                    <span>{item.price === null ? 'Chưa đặt giá' : `${new Intl.NumberFormat('vi-VN').format(item.price)} ${item.currency_code}`}</span>
                                  </div>
                                </div>
                                <div className="owner-menu-item__actions">
                                  <span className={`badge badge--${item.is_available ? 'ok' : 'neutral'}`}>{item.is_available ? 'Đang phục vụ' : 'Tạm hết'}</span>
                                  <button className="btn btn--secondary btn--sm" type="button" onClick={() => setEditing((all) => ({ ...all, [item.id]: {
                                    name: item.name,
                                    description: item.description ?? '',
                                    price: item.price === null ? '' : String(item.price),
                                    image_url: item.image_url ?? '',
                                    is_available: item.is_available,
                                  } }))}>Sửa</button>
                                  <button className="btn btn--danger btn--sm" type="button" onClick={() => void xoaMon(menu.id, item.id)}>Xóa</button>
                                </div>
                              </>
                            )}
                          </article>
                        )
                      })}
                    </div>
                  )}

                  <form
                    className="owner-menu-item__new"
                    onSubmit={(event) => {
                      event.preventDefault()
                      void luuMon(menu.id, drafts[menu.id] ?? EMPTY_DRAFT)
                    }}
                  >
                    <h4>Thêm món ăn</h4>
                    <div className="form-grid-2">
                      <input className="input" aria-label="Tên món mới" placeholder="Tên món *" required value={(drafts[menu.id] ?? EMPTY_DRAFT).name} onChange={(event) => setDrafts((all) => ({ ...all, [menu.id]: { ...EMPTY_DRAFT, ...all[menu.id], name: event.target.value } }))} />
                      <input className="input" aria-label="Giá món mới" type="number" min="0" step="1000" placeholder="Giá (VND)" value={(drafts[menu.id] ?? EMPTY_DRAFT).price} onChange={(event) => setDrafts((all) => ({ ...all, [menu.id]: { ...EMPTY_DRAFT, ...all[menu.id], price: event.target.value } }))} />
                    </div>
                    <textarea className="input textarea" aria-label="Mô tả món mới" rows={2} placeholder="Mô tả món" value={(drafts[menu.id] ?? EMPTY_DRAFT).description} onChange={(event) => setDrafts((all) => ({ ...all, [menu.id]: { ...EMPTY_DRAFT, ...all[menu.id], description: event.target.value } }))} />
                    <input className="input" aria-label="Ảnh món mới" type="url" placeholder="URL hình ảnh (tùy chọn)" value={(drafts[menu.id] ?? EMPTY_DRAFT).image_url} onChange={(event) => setDrafts((all) => ({ ...all, [menu.id]: { ...EMPTY_DRAFT, ...all[menu.id], image_url: event.target.value } }))} />
                    <button className="btn btn--primary btn--sm" type="submit">Thêm món</button>
                  </form>
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}
