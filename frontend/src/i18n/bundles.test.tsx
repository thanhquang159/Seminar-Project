import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const idb = vi.hoisted(() => ({
  docUiBundle: vi.fn(),
  luuUiBundle: vi.fn(),
}))

vi.mock('../offline/idb', () => idb)

import { useUiBundle } from './bundles'

Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', {
  configurable: true,
  value: true,
})

function BundleText({ locale = 'en' }: { locale?: string }) {
  const { t, sanSang } = useUiBundle(locale)
  return <span>{sanSang ? t('place_count', { count: 3 }) : 'loading'}</span>
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  vi.resetAllMocks()
  idb.docUiBundle.mockResolvedValue(null)
  idb.luuUiBundle.mockResolvedValue(undefined)
  localStorage.clear()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('UI language bundles', () => {
  it('fetches a missing bundle and stores it in IndexedDB', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          status: 'ready',
          bundle: { place_count: '{count} restaurants' },
        }),
      }),
    )

    await act(async () => {
      root.render(<BundleText />)
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(container.textContent).toBe('3 restaurants')
    expect(idb.luuUiBundle).toHaveBeenCalledWith(
      'en',
      { place_count: '{count} restaurants' },
      '1',
    )
  })

  it('uses the IndexedDB bundle without requesting the backend', async () => {
    idb.docUiBundle.mockResolvedValue({
      translations: { place_count: '{count} cached places' },
    })
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await act(async () => {
      root.render(<BundleText locale="ja" />)
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(container.textContent).toBe('3 cached places')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
