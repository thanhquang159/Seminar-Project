import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../config'
import { useUiBundle } from '../i18n/bundles'
import {
  docThucDonCongKhai,
  luuThucDonCongKhai,
  type PublicPoiMenu,
  type PublicPoiMenuItem,
} from '../offline/idb'
import { usePoiStore } from '../stores/poiStore'

interface MenuState {
  poiId: string
  lang: string
  menus: PublicPoiMenu[]
  dangTai: boolean
  loi: boolean
}

function isMenuItem(value: unknown): value is PublicPoiMenuItem {
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

function isMenu(value: unknown): value is PublicPoiMenu {
  if (typeof value !== 'object' || value === null) return false
  const menu = value as Record<string, unknown>
  return (
    typeof menu.id === 'string'
    && typeof menu.poi_id === 'string'
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
    lang,
    menus: [],
    dangTai: true,
    loi: false,
  })
  const currentState = menuState.poiId === poiId && menuState.lang === lang
    ? menuState
    : { poiId, lang, menus: [], dangTai: true, loi: false }

  useEffect(() => {
    const controller = new AbortController()

    const taiMenu = async () => {
      let coCache = false
      try {
        const cached = await docThucDonCongKhai(lang)
        if (controller.signal.aborted) return
        if (cached !== null) {
          coCache = true
          setMenuState({
            poiId,
            lang,
            menus: cached[poiId] ?? [],
            dangTai: false,
            loi: false,
          })
        }
      } catch (error) {
        console.warn('Không đọc được thực đơn trong cache ngoại tuyến:', error)
      }

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
        if (controller.signal.aborted) return
        setMenuState({ poiId, lang, menus: payload, dangTai: false, loi: false })
        try {
          const cached = await docThucDonCongKhai(lang)
          await luuThucDonCongKhai(lang, {
            ...(cached ?? {}),
            [poiId]: payload,
          })
        } catch (error) {
          console.warn('Không lưu được thực đơn vào cache ngoại tuyến:', error)
        }
      } catch {
        if (!controller.signal.aborted && !coCache) {
          setMenuState({ poiId, lang, menus: [], dangTai: false, loi: true })
        }
      }
    }

    void taiMenu()
    return () => controller.abort()
  }, [lang, poiId])

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
