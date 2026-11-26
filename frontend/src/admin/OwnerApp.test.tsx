import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OwnerApp from './OwnerApp'
import { OWNER_POLL_INTERVAL } from './useOwnerNotifications'

const mocks = vi.hoisted(() => ({ api: vi.fn(), apiText: vi.fn() }))
vi.mock('./api', () => mocks)
vi.mock('./OwnerMenuManagement', () => ({ default: () => null }))
vi.mock('./OwnerPoiQrCodes', () => ({ default: () => null }))
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })

let dom: HTMLDivElement
let root: Root
let status: string
let history: ReturnType<typeof submission>[]
let notifications: { id: string; message: string; read: boolean }[]
const submission = (state = 'pending') => ({ id: 's1', poi_id: state === 'approved' ? 'p1' : null,
  submission_type: 'create', data: { name: '2632' }, status: state,
  created_at: '2026-11-24T03:00:00Z', admin_note: state === 'rejected' ? 'Cần bổ sung hình ảnh' : '' })

beforeEach(() => {
  status = 'approved'
  history = [submission()]
  notifications = []
  window.history.replaceState(null, '', '/owner/history')
  mocks.api.mockReset().mockImplementation(async (path: string) => {
    if (path === '/owner/auth/me') return { username: 'demo.admin@quan4.local' }
    if (path === '/owner/registration-status') return { status, admin_note: status === 'rejected' ? 'CCCD cần bổ sung' : '' }
    if (path === '/owner/notifications') return notifications
    if (path === '/owner/submissions/mine') return history
    return []
  })
  mocks.apiText.mockReset().mockResolvedValue({ ok: true })
  dom = document.createElement('div')
  document.body.appendChild(dom)
  root = createRoot(dom)
})

afterEach(() => {
  act(() => root.unmount())
  dom.remove()
  vi.useRealTimers()
  vi.restoreAllMocks()
  window.history.replaceState(null, '', '/')
})

describe('Thông báo Owner tự cập nhật', () => {
  beforeEach(() => { vi.useFakeTimers() })
  const tick = () => act(async () => { await vi.advanceTimersByTimeAsync(OWNER_POLL_INTERVAL) })
  const notificationCalls = () => mocks.api.mock.calls.filter(([path]) => path === '/owner/notifications').length
  const badge = () => dom.querySelector('a[href="/owner/notifications"] .portal-dashboard__nav-badge')?.textContent

  it('tài khoản chờ duyệt mở lịch sử không bị kẹt trạng thái đang tải', async () => {
    status = 'pending'
    await render()
    expect(dom.textContent).toContain('Tài khoản cần được duyệt trước khi gửi nội dung quán')
    expect(dom.textContent).not.toContain('Đang tải lịch sử')
    expect(button('Tải lại lịch sử').disabled).toBe(true)
  })

  it('đang ở trang khác vẫn nhận số chưa đọc; ở trang thông báo vẫn nhận thư mới', async () => {
    await render()
    notifications = [{ id: 'n1', message: 'Đề xuất đã được duyệt', read: false }]
    await tick()
    expect(badge()).toBe('1')
    await act(async () => dom.querySelector<HTMLAnchorElement>('a[href="/owner/notifications"]')!.click())
    expect(dom.textContent).toContain('Đề xuất đã được duyệt')
    notifications = [{ id: 'n2', message: 'Đề xuất bị từ chối: thiếu ảnh', read: false }, ...notifications]
    await tick()
    expect(dom.textContent).toContain('Đề xuất bị từ chối: thiếu ảnh')
    expect(badge()).toBe('2')
    await act(async () => button('Đánh dấu đã đọc').click())
    expect(badge()).toBe('1')
  })

  it.each(['approved', 'rejected'])('Owner đang chờ tự nhận kết quả %s và notification', async (result) => {
    status = 'pending'
    window.history.replaceState(null, '', '/owner')
    await render()
    expect(dom.querySelector<HTMLButtonElement>('[placeholder="Tên quán"]')?.disabled).toBe(true)
    status = result
    notifications = [{ id: 'n1', message: `Kết quả đăng ký: ${result}`, read: false }]
    await tick()
    expect(badge()).toBe('1')
    expect(dom.querySelector<HTMLInputElement>('[placeholder="Tên quán"]')?.disabled).toBe(result !== 'approved')
    if (result === 'rejected') expect(dom.textContent).toContain('CCCD cần bổ sung')
    await act(async () => dom.querySelector<HTMLAnchorElement>('a[href="/owner/notifications"]')!.click())
    expect(dom.textContent).toContain(`Kết quả đăng ký: ${result}`)
  })

  it('giữ dữ liệu khi mất mạng và tự phục hồi', async () => {
    notifications = [{ id: 'n1', message: 'Thông báo cũ', read: false }]
    window.history.replaceState(null, '', '/owner/notifications')
    await render()
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/notifications' ? Promise.reject(new Error('offline')) : load(path))
    await tick()
    expect(dom.textContent).toContain('Thông báo cũ')
    expect(dom.textContent).toContain('Hệ thống sẽ tự thử lại')
    mocks.api.mockImplementation(load)
    notifications = [{ id: 'n2', message: 'Thông báo mới', read: false }]
    await tick()
    expect(dom.textContent).toContain('Thông báo mới')
    expect(dom.textContent).not.toContain('Hệ thống sẽ tự thử lại')
  })

  it('không gửi request chồng nhau và phản hồi cũ không làm mất trạng thái đã đọc', async () => {
    notifications = [{ id: 'n1', message: 'Đã duyệt', read: false }]
    window.history.replaceState(null, '', '/owner/notifications')
    await render()
    let complete: (value: unknown) => void = () => {}
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/notifications'
      ? new Promise((resolve) => { complete = resolve }) : load(path))
    await tick()
    const count = notificationCalls()
    await act(async () => { window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('online')) })
    await tick()
    expect(notificationCalls()).toBe(count)
    await act(async () => button('Đánh dấu đã đọc').click())
    await act(async () => complete(notifications))
    expect(badge()).toBeUndefined()
    expect(dom.querySelector('.notification-item--unread')).toBeNull()
  })

  it('tạm dừng khi tab ẩn, tải ngay khi hiện lại và dừng sau đăng xuất', async () => {
    await render()
    const visibility = vi.spyOn(document, 'visibilityState', 'get')
    visibility.mockReturnValue('hidden')
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    const count = notificationCalls()
    await tick()
    expect(notificationCalls()).toBe(count)
    visibility.mockReturnValue('visible')
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    expect(notificationCalls()).toBe(count + 1)
    await act(async () => button('Đăng xuất').click())
    await tick()
    expect(notificationCalls()).toBe(count + 1)
  })

  it('bỏ phản hồi đến sau đăng xuất và hủy request đang chờ', async () => {
    await render()
    let complete: (value: unknown) => void = () => {}
    let signal: AbortSignal | undefined
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string, init?: RequestInit) => {
      if (path !== '/owner/notifications') return load(path)
      signal = init?.signal as AbortSignal
      return new Promise((resolve) => { complete = resolve })
    })
    await tick()
    await act(async () => button('Đăng xuất').click())
    expect(signal?.aborted).toBe(true)
    expect(vi.getTimerCount()).toBe(0)
    await act(async () => complete([{ id: 'n1', message: 'Thông báo riêng', read: false }]))
    expect(dom.textContent).not.toContain('Thông báo riêng')
    expect(dom.textContent).toContain('Chào mừng trở lại!')
  })

  it('không đánh dấu đã đọc nếu API thất bại', async () => {
    notifications = [{ id: 'n1', message: 'Đã duyệt', read: false }]
    window.history.replaceState(null, '', '/owner/notifications')
    await render()
    mocks.apiText.mockResolvedValue({ ok: false, status: 500 })
    await act(async () => button('Đánh dấu đã đọc').click())
    expect(badge()).toBe('1')
    expect(dom.textContent).toContain('Không thể cập nhật trạng thái thông báo')
  })

  it('dừng truy vấn khi phiên hết hạn', async () => {
    await render()
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/notifications'
      ? Promise.reject(new Error('HTTP 401')) : load(path))
    await tick()
    expect(dom.textContent).toContain('Phiên đăng nhập đã hết hạn')
    const count = notificationCalls()
    await tick()
    await act(async () => { window.dispatchEvent(new Event('focus')) })
    expect(notificationCalls()).toBe(count)
  })

  it('dọn timer khi rời OwnerApp', async () => {
    await render()
    const count = notificationCalls()
    await act(async () => root.render(null))
    await tick()
    await act(async () => { window.dispatchEvent(new Event('focus')) })
    expect(notificationCalls()).toBe(count)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('đăng ký thành công tạo phiên thật trước khi theo dõi kết quả', async () => {
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/auth/me'
      ? Promise.reject(new Error('HTTP 401')) : load(path))
    status = 'pending'
    await render()
    await act(async () => button('Đăng ký chủ quán').click())
    enter('#owner-username', 'new-owner')
    enter('#owner-password', 'Password123!')
    enter('#owner-cccd', '012345678901')
    await act(async () => dom.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
    expect(mocks.apiText.mock.calls.map(([path]) => path)).toEqual(['/owner/register', '/owner/auth/login'])
    expect(dom.textContent).toContain('Đang chờ duyệt')
    expect(notificationCalls()).toBe(1)
  })
})

async function render() { await act(async () => root.render(<OwnerApp />)) }
function button(label: string) { return [...dom.querySelectorAll('button')].find((b) => b.textContent === label)! }
function enter(selector: string, value: string) {
  const input = dom.querySelector<HTMLInputElement>(selector)!
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
}
function fillSubmission() {
  enter('[placeholder="Tên quán"]', '2632')
  enter('#owner-poi-address', '88 Nguyễn Đình Chiểu')
  enter('#owner-poi-latitude', '10.78585')
  enter('#owner-poi-longitude', '106.69745')
}

describe('Lịch sử Owner', () => {
  it.each(['approved', 'admin'])('hiện đơn đang chờ của tài khoản %s', async (value) => {
    status = value
    await render()
    expect(dom.textContent).toContain('2632')
    expect(dom.textContent).toContain('Đang chờ duyệt')
    expect(dom.textContent).not.toContain('Bạn chưa gửi nội dung nào')
  })

  it('lỗi tải POI không làm mất lịch sử và lỗi hiện ngay trên trang lịch sử', async () => {
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/pois' ? Promise.reject(new Error('offline')) : load(path))
    await render()
    expect(dom.textContent).toContain('2632')
    expect(dom.querySelector('[role="alert"]')).not.toBeNull()
  })

  it('lỗi lịch sử không được hiển thị thành chưa gửi đơn; tải lại phục hồi được', async () => {
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/submissions/mine' ? Promise.reject(new Error('offline')) : load(path))
    await render()
    expect(dom.textContent).toContain('Không tải được lịch sử gửi duyệt')
    expect(dom.textContent).not.toContain('Bạn chưa gửi nội dung nào')
    mocks.api.mockImplementation(load)
    await act(async () => button('Tải lại lịch sử').click())
    expect(dom.textContent).toContain('2632')
    expect(dom.textContent).not.toContain('Không tải được lịch sử gửi duyệt')
  })

  it('trở lại tab lấy kết quả từ chối mới nhất', async () => {
    await render()
    history = [submission('rejected')]
    await act(async () => { window.dispatchEvent(new Event('focus')) })
    expect(dom.textContent).toContain('Cần chỉnh sửa')
    expect(dom.textContent).toContain('Cần bổ sung hình ảnh')
  })

  it('quán mới đã duyệt vẫn có loại Quán mới khi có poi_id', async () => {
    history = [submission('approved')]
    await render()
    expect(dom.querySelector('tbody')?.textContent).toContain('Quán mới')
    expect(dom.querySelector('tbody')?.textContent).not.toContain('Cập nhật quán')
  })

  it('response lịch sử cũ đến muộn không ghi đè kết quả duyệt mới', async () => {
    await render()
    let complete: (value: unknown) => void = () => {}
    let calls = 0
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => {
      if (path !== '/owner/submissions/mine') return load(path)
      if (++calls === 1) return new Promise((resolve) => { complete = resolve })
      return Promise.resolve([submission('rejected')])
    })
    await act(async () => { window.dispatchEvent(new Event('focus')) })
    await act(async () => { window.dispatchEvent(new Event('focus')) })
    await act(async () => complete([submission()]))
    expect(dom.querySelector('tbody')?.textContent).toContain('Cần chỉnh sửa')
    expect(dom.querySelector('tbody')?.textContent).not.toContain('Đang chờ duyệt')
  })

  it('gửi thành công thì cập nhật lịch sử ngay, không cần đăng nhập hay tải lại trang', async () => {
    window.history.replaceState(null, '', '/owner')
    history = []
    mocks.apiText.mockImplementation(async () => { history = [submission()]; return { ok: true } })
    await render()
    fillSubmission()
    await act(async () => button('Gửi').click())
    expect(dom.textContent).toContain('Đã gửi thông tin quán thành công')
    await act(async () => dom.querySelector<HTMLAnchorElement>('a[href="/owner/history"]')!.click())
    expect(dom.textContent).toContain('2632')
    expect(dom.textContent).toContain('Đang chờ duyệt')
    expect(mocks.apiText).toHaveBeenCalledOnce()
  })

  it('hiện lý do backend từ chối gửi đề xuất', async () => {
    window.history.replaceState(null, '', '/owner')
    mocks.apiText.mockResolvedValue(new Response(JSON.stringify({ detail: 'Không phải quán của bạn' }), { status: 403 }))
    await render()
    fillSubmission()
    await act(async () => button('Gửi').click())
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Không phải quán của bạn')
    expect(dom.textContent).not.toContain('Đã gửi thông tin quán thành công')
  })
})
