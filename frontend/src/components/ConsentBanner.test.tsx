import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ConsentBanner from './ConsentBanner'
import { useConsentStore } from '../stores/consentStore'

const consentActions = vi.hoisted(() => ({
  xinDongY: vi.fn(),
  thuHoiDongY: vi.fn().mockResolvedValue(true),
}))

vi.mock('../analytics/service', () => consentActions)
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', {
  configurable: true,
  value: true,
})

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  useConsentStore.setState({
    trangThai: 'revoked',
    receipt: null,
    trackedOnlineUsers: null,
  })
  consentActions.xinDongY.mockResolvedValue(true)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
})

describe('consent status control', () => {
  it('offers an enable button after consent has been turned off', async () => {
    act(() => root.render(<ConsentBanner />))

    const enableButton = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent === 'Bật chia sẻ')
    expect(enableButton).toBeDefined()

    await act(async () => {
      enableButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })

    expect(consentActions.xinDongY).toHaveBeenCalledOnce()
  })

  it('shows an error and stays disabled when consent cannot be renewed', async () => {
    consentActions.xinDongY.mockResolvedValue(false)
    act(() => root.render(<ConsentBanner />))

    const enableButton = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent === 'Bật chia sẻ')
    await act(async () => {
      enableButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })

    expect(container.textContent).toContain('Chưa bật được chia sẻ dữ liệu')
    expect(useConsentStore.getState().trangThai).toBe('revoked')
  })
})
