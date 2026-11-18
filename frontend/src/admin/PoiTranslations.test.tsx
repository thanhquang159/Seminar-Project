import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Poi } from '../stores/poiStore'
import PoiTranslations from './PoiTranslations'

const apiMock = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('./api', () => apiMock)

Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', {
  configurable: true,
  value: true,
})

const poi: Poi = {
  id: 'poi-1',
  name: 'Quán gốc',
  description: 'Mô tả gốc',
  lat: 10,
  lng: 106,
  trigger_radius: 30,
  audio_priority: 0,
  lang: 'vi',
  is_fallback: false,
  audio_url: null,
}

let container: HTMLDivElement | null = null
let root: Root | null = null

function render() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  return container
}

function enterValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set
  act(() => {
    setter?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

beforeEach(() => {
  apiMock.api.mockReset()
  apiMock.api.mockResolvedValue({
    tong: 1,
    thieu: [{ poi_id: poi.id, lang: 'ja' }],
  })
})

afterEach(() => {
  if (root !== null) {
    act(() => root!.unmount())
    root = null
  }
  container?.remove()
  container = null
})

describe('PoiTranslations', () => {
  it('hiển thị nguồn và gửi bản dịch thủ công đến API được phân quyền', async () => {
    const onSaved = vi.fn().mockResolvedValue(undefined)
    const dom = render()

    await act(async () => {
      root!.render(<PoiTranslations pois={[poi]} onSaved={onSaved} />)
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(dom.textContent).toContain('Quán gốc')
    expect(dom.textContent).toContain('Mô tả gốc')

    const name = dom.querySelector<HTMLInputElement>('#poi-translation-name')
    expect(name).not.toBeNull()
    enterValue(name!, 'カフェ')

    const button = [...dom.querySelectorAll('button')].find((item) =>
      item.textContent?.includes('Lưu bản dịch'),
    )
    expect(button).toBeDefined()
    await act(async () => {
      button!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(apiMock.api).toHaveBeenNthCalledWith(2, '/localizations/on-demand', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        poi_id: poi.id,
        lang: 'ja',
        name: 'カフェ',
        description: '',
      }),
    })
    expect(onSaved).toHaveBeenCalledOnce()
    expect(dom.textContent).toContain('Đã lưu bản dịch JA')
  })
})
