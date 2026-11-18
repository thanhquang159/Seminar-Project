import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PublicPoiMenu from './PublicPoiMenu'

vi.mock('../i18n/bundles', () => ({
  useUiBundle: () => ({
    t: (key: string, values?: Record<string, string | number>) =>
      key.replace(/\{(\w+)\}/g, (_match, name: string) => String(values?.[name] ?? `{${name}}`)),
  }),
}))

Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', {
  configurable: true,
  value: true,
})

let container: HTMLDivElement | null = null
let root: Root | null = null

function renderMenu() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  return container
}

afterEach(() => {
  if (root !== null) {
    act(() => root!.unmount())
    root = null
  }
  container?.remove()
  container = null
  vi.unstubAllGlobals()
})

describe('PublicPoiMenu', () => {
  it('tải và hiển thị tên món, giá và tình trạng phục vụ', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{
        id: 'menu-1',
        name: 'Menu del dia',
        description: null,
        items: [{
          id: 'item-1',
          name: 'Banh mi',
          description: 'Hecho al momento',
          price: 25000,
          currency_code: 'VND',
          is_available: false,
        }],
      }],
    }))
    const dom = renderMenu()

    await act(async () => {
      root!.render(<PublicPoiMenu poiId="poi-1" />)
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(dom.textContent).toContain('Menu del dia')
    expect(dom.textContent).toContain('Banh mi')
    expect(dom.textContent).toContain('25,000 VND')
    expect(dom.textContent).toContain('menu_unavailable')
  })

  it('hiển thị thông báo khi POI chưa có thực đơn công khai', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    }))
    const dom = renderMenu()

    await act(async () => {
      root!.render(<PublicPoiMenu poiId="poi-2" />)
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(dom.textContent).toContain('menu_empty')
  })
})
