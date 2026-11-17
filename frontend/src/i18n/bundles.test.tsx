import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useUiBundle } from './bundles'

Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', {
  configurable: true,
  value: true,
})

function BundleText() {
  const { t, sanSang } = useUiBundle('en')
  return <span>{sanSang ? t('place_count', { count: 3 }) : 'loading'}</span>
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
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
  it('loads the selected bundle and interpolates values', async () => {
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
    expect(localStorage.getItem('quan4-ui-en')).toContain('place_count')
  })
})
