import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../config'
import { useUiBundle } from '../i18n/bundles'
import { usePoiStore } from '../stores/poiStore'

interface PublicMenuItem {
  id: string
  name: string
  description: string | null
  price: number | string | null
  currency_code: string
  is_available: boolean
}

interface PublicMenu {
  id: string
  name: string
  description: string | null
  items: PublicMenuItem[]
}

interface MenuState {
  poiId: string
  menus: PublicMenu[]
  dangTai: boolean
  loi: boolean
}

function isMenuItem(value: unknown): value is PublicMenuItem {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  return (
    typeof item.id === 'string'
    && typeof item.name === 'string'
    && (typeof item.description === 'string' || item.description === null)
    && (typeof item.price === 'number' || typeof item.price === 'string' || item.price === null)
    && typeof item.currency_code === 'string'
    && typeof item.is_available === 'boolean'
  )
}

function isMenu(value: unknown): value is PublicMenu {
  if (typeof value !== 'object' || value === null) return false
  const menu = value as Record<string, unknown>
  return (
    typeof menu.id === 'string'
    && typeof menu.name === 'string'
    && (typeof menu.description === 'string' || menu.description === null)
    && Array.isArray(menu.items)
    && menu.items.every(isMenuItem)
  )
}

export default function PublicPoiMenu({ poiId }: { poiId: string }) {
  const lang = usePoiStore((state) => state.lang)
  const { t } = useUiBundle(lang)
  const [menuState, setMenuState] = useState<MenuState>({
    poiId,
    menus: [],
    dangTai: true,
    loi: false,
  })
  const currentState = menuState.poiId === poiId
    ? menuState
    : { poiId, menus: [], dangTai: true, loi: false }

  useEffect(() => {
    const controller = new AbortController()

    const taiMenu = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/poi/${encodeURIComponent(poiId)}/menus`,
          { signal: controller.signal },
        )
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const payload: unknown = await response.json()
        if (!Array.isArray(payload) || !payload.every(isMenu)) {
          throw new Error('Dữ liệu thực đơn không hợp lệ')
        }
        setMenuState({ poiId, menus: payload, dangTai: false, loi: false })
      } catch {
        if (!controller.signal.aborted) {
          setMenuState({ poiId, menus: [], dangTai: false, loi: true })
        }
      }
    }

    void taiMenu()
    return () => controller.abort()
  }, [poiId])

  return (
    <section className="poi-detail__menu" aria-label={t('menu_section')}>
      <div className="poi-detail__menu-heading">
        <span className="poi-detail__menu-eyebrow">{t('menu_section')}</span>
      </div>
      {currentState.dangTai ? (
        <p className="poi-detail__menu-message" role="status">{t('menu_loading')}</p>
      ) : currentState.loi ? (
        <p className="poi-detail__menu-message poi-detail__menu-message--error" role="alert">
          {t('menu_error')}
        </p>
      ) : currentState.menus.length === 0 ? (
        <p className="poi-detail__menu-message">{t('menu_empty')}</p>
      ) : (
        <div className="poi-detail__menus">
          {currentState.menus.map((menu) => (
            <section className="poi-detail__menu-list" key={menu.id}>
              <div className="poi-detail__menu-title-row">
                <div>
                  <h3 className="poi-detail__menu-title">{menu.name}</h3>
                  {menu.description && <p className="poi-detail__menu-description">{menu.description}</p>}
                </div>
                <span className="poi-detail__menu-count">
                  {t('menu_item_count', { count: menu.items.length })}
                </span>
              </div>
              {menu.items.length > 0 && (
                <ul className="poi-detail__menu-items">
                  {menu.items.map((item) => {
                    const price = item.price === null ? null : Number(item.price)
                    return (
                      <li className="poi-detail__menu-item" key={item.id}>
                        <div className="poi-detail__menu-item-copy">
                          <strong>{item.name}</strong>
                          {item.description && <p>{item.description}</p>}
                          {!item.is_available && (
                            <span className="poi-detail__menu-unavailable">{t('menu_unavailable')}</span>
                          )}
                        </div>
                        <span className="poi-detail__menu-price">
                          {price === null || !Number.isFinite(price)
                            ? t('menu_price_missing')
                            : `${new Intl.NumberFormat(lang).format(price)} ${item.currency_code}`}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>
          ))}
        </div>
      )}
    </section>
  )
}
