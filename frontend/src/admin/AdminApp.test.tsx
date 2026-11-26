import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AdminApp from './AdminApp'
import { APPROVALS_POLL_INTERVAL } from './useApprovalCount'

const mocks = vi.hoisted(() => ({ api: vi.fn(), apiText: vi.fn() }))
vi.mock('./api', () => mocks)
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })

let dom: HTMLDivElement
let root: Root
let permissions: string[]
let registrations: { username: string; status: string }[]
let submissions: ReturnType<typeof submission>[]
const submission = () => ({ id: 's1', username: 'owner@example.test', name: 'Quán mới',
  created_at: null, data: { lat: 10.7, lng: 106.7 }, can_approve: true })
const onPoisChanged = vi.fn()
const badge = () => dom.querySelector('a[href="/admin/approvals"] .portal-dashboard__nav-badge')?.textContent
const countCalls = () => mocks.api.mock.calls.filter(([path]) => path === '/owner/approvals/counts').length
const button = (label: string, scope: ParentNode = dom) =>
  [...scope.querySelectorAll('button')].find((item) => item.textContent?.trim() === label)!
const render = () => act(async () => root.render(<AdminApp onPoisChanged={onPoisChanged} />))
const tick = () => act(async () => { await vi.advanceTimersByTimeAsync(APPROVALS_POLL_INTERVAL) })

beforeEach(() => {
  vi.useFakeTimers()
  permissions = ['user:update', 'poi:approve']
  registrations = [{ username: 'pending@example.test', status: 'pending' }]
  submissions = [submission()]
  window.history.replaceState(null, '', '/admin')
  mocks.api.mockReset().mockImplementation(async (path: string) => {
    if (path === '/admin/auth/me') return { username: 'admin@example.test', role: 'admin', permissions }
    if (path === '/owner/approvals/counts') return { total: registrations.length + submissions.length }
    if (path === '/owner/registrations') return registrations
    if (path === '/owner/submissions/pending') return submissions
    return []
  })
  mocks.apiText.mockReset().mockResolvedValue({ ok: true })
  onPoisChanged.mockReset()
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

describe('Số yêu cầu chờ duyệt trên menu Admin', () => {
  it.each(['registration', 'submission'])('tự hiện %s mới khi Admin đang mở trang duyệt trống', async (kind) => {
    window.history.replaceState(null, '', '/admin/approvals')
    registrations = []
    submissions = []
    await render()
    expect(badge()).toBeUndefined()
    if (kind === 'registration') registrations = [{ username: 'new-owner@example.test', status: 'pending' }]
    else submissions = [{ ...submission(), name: 'Quán vừa gửi' }]
    await tick()
    expect(badge()).toBe('1')
    expect(dom.textContent).toContain(kind === 'registration' ? 'new-owner@example.test' : 'Quán vừa gửi')
    expect(dom.textContent).toContain(kind === 'registration' ? '1 đơn' : '1 quán')
  })

  it('làm mới danh sách kể cả khi yêu cầu thay đổi nhưng tổng vẫn bằng nhau', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    await render()
    submissions = [{ ...submission(), id: 's2', name: 'Quán thay thế' }]
    await tick()
    expect(badge()).toBe('2')
    expect(dom.textContent).toContain('Quán thay thế')
    expect(dom.textContent).not.toContain('Quán mới')
  })

  it('hiện yêu cầu mới mà vẫn giữ lý do từ chối đang nhập', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    await render()
    const input = dom.querySelector<HTMLInputElement>('[aria-label="Lý do từ chối Quán mới"]')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'Cần bổ sung địa chỉ')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    submissions = [...submissions, { ...submission(), id: 's2', name: 'Quán vừa gửi' }]
    await tick()
    expect(dom.textContent).toContain('Quán vừa gửi')
    expect(dom.querySelector<HTMLInputElement>('[aria-label="Lý do từ chối Quán mới"]')?.value).toBe('Cần bổ sung địa chỉ')
  })

  it('bỏ danh sách cũ về muộn sau khi đã duyệt thành công', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    await render()
    let complete: (value: ReturnType<typeof submission>[]) => void = () => {}
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/submissions/pending'
      ? new Promise((resolve) => { complete = resolve }) : load(path))
    await tick()
    mocks.api.mockImplementation(load)
    mocks.apiText.mockImplementation(async () => { submissions = []; return { ok: true } })
    await act(async () => button('Duyệt quán').click())
    expect(dom.textContent).toContain('0 quán')
    await act(async () => complete([submission()]))
    expect(dom.textContent).toContain('0 quán')
    expect(dom.textContent).not.toContain('Quán mới')
    expect(badge()).toBe('1')
  })

  it('không hủy truy vấn danh sách chậm ở mỗi lần kiểm tra thông báo', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    await render()
    let complete: (value: ReturnType<typeof submission>[]) => void = () => {}
    let pendingSignal: AbortSignal | null | undefined
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string, options?: RequestInit) => {
      if (path !== '/owner/submissions/pending') return load(path)
      pendingSignal = options?.signal
      return new Promise((resolve) => { complete = resolve })
    })
    await tick()
    await tick()
    expect(pendingSignal?.aborted).toBe(false)
    await act(async () => complete([{ ...submission(), name: 'Quán từ truy vấn chậm' }]))
    expect(dom.textContent).toContain('Quán từ truy vấn chậm')
  })

  it('tự thử lại danh sách sau lỗi mạng và giữ các yêu cầu đã tải', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    await render()
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/submissions/pending'
      ? Promise.reject(new TypeError('Failed to fetch')) : load(path))
    await tick()
    expect(dom.textContent).toContain('Quán mới')
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Không tải được quán chờ duyệt')
    submissions = [...submissions, { ...submission(), id: 's2', name: 'Quán vừa gửi' }]
    mocks.api.mockImplementation(load)
    await tick()
    expect(dom.textContent).toContain('Quán vừa gửi')
    expect(dom.querySelector('[role="alert"]')).toBeNull()
  })

  it('hiện tổng ngay ở trang khác, cập nhật yêu cầu mới và ẩn khi không còn yêu cầu', async () => {
    await render()
    expect(badge()).toBe('2')
    submissions = [...submissions, { ...submission(), id: 's2' }]
    await tick()
    expect(badge()).toBe('3')
    await act(async () => dom.querySelector<HTMLAnchorElement>('a[href="/admin/approvals"]')!.click())
    expect(dom.textContent).toContain('1 đơn')
    expect(dom.textContent).toContain('2 quán')
    registrations = []
    submissions = []
    await act(async () => button('Tải lại danh sách').click())
    expect(badge()).toBeUndefined()
  })

  it.each([
    ['registration', 'approve', 'Duyệt'],
    ['registration', 'reject', 'Từ chối'],
    ['submission', 'approve', 'Duyệt quán'],
    ['submission', 'reject', 'Từ chối'],
  ])('cập nhật ngay sau %s %s thành công', async (kind, action, label) => {
    window.history.replaceState(null, '', '/admin/approvals')
    mocks.apiText.mockImplementation(async () => {
      if (kind === 'registration') registrations = []
      else submissions = []
      return { ok: true }
    })
    await render()
    const section = dom.querySelectorAll('.approval-section')[kind === 'registration' ? 0 : 1]
    if (action === 'reject') {
      const input = section.querySelector('input')!
      act(() => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'Cần bổ sung thông tin')
        input.dispatchEvent(new Event('input', { bubbles: true }))
      })
    }
    await act(async () => button(label, section).click())
    expect(badge()).toBe('1')
    expect(onPoisChanged).toHaveBeenCalledTimes(kind === 'submission' && action === 'approve' ? 1 : 0)
  })

  it('giữ số cũ nếu thao tác duyệt thất bại', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    mocks.apiText.mockResolvedValue(new Response(JSON.stringify({ detail: 'Không thể duyệt' }), { status: 409 }))
    await render()
    await act(async () => button('Duyệt quán').click())
    expect(badge()).toBe('2')
    expect(countCalls()).toBe(1)
    await tick()
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Không thể duyệt')
  })

  it('giữ số gần nhất khi lỗi mạng và cập nhật khi trở lại tab', async () => {
    await render()
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/approvals/counts'
      ? Promise.reject(new TypeError('Failed to fetch')) : load(path))
    await tick()
    expect(badge()).toBe('2')
    mocks.api.mockImplementation(load)
    registrations = []
    await act(async () => window.dispatchEvent(new Event('focus')))
    expect(badge()).toBe('1')
  })

  it('bỏ phản hồi cũ về muộn sau khi tải lại danh sách', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    await render()
    let complete: (value: { total: number }) => void = () => {}
    const load = mocks.api.getMockImplementation()!
    mocks.api.mockImplementation((path: string) => path === '/owner/approvals/counts'
      ? new Promise((resolve) => { complete = resolve }) : load(path))
    await act(async () => window.dispatchEvent(new Event('focus')))
    mocks.api.mockImplementation(load)
    registrations = []
    await act(async () => button('Tải lại danh sách').click())
    expect(badge()).toBe('1')
    await act(async () => complete({ total: 2 }))
    expect(badge()).toBe('1')
  })

  it('tạm ngừng khi tab ẩn, cập nhật khi hiện lại và dừng sau đăng xuất', async () => {
    window.history.replaceState(null, '', '/admin/approvals')
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    await render()
    visibility.mockReturnValue('hidden')
    await act(async () => document.dispatchEvent(new Event('visibilitychange')))
    await tick()
    expect(countCalls()).toBe(1)
    submissions = [...submissions, { ...submission(), id: 's2', name: 'Quán vừa gửi' }]
    visibility.mockReturnValue('visible')
    await act(async () => document.dispatchEvent(new Event('visibilitychange')))
    expect(countCalls()).toBe(2)
    expect(dom.textContent).toContain('Quán vừa gửi')
    await act(async () => button('Đăng xuất').click())
    await tick()
    await act(async () => window.dispatchEvent(new Event('focus')))
    expect(countCalls()).toBe(2)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('chỉ tải danh sách khi trang duyệt đang mở', async () => {
    await render()
    await tick()
    expect(mocks.api.mock.calls.filter(([path]) => path === '/owner/submissions/pending')).toHaveLength(0)
    await act(async () => dom.querySelector<HTMLAnchorElement>('a[href="/admin/approvals"]')!.click())
    const calls = mocks.api.mock.calls.filter(([path]) => path === '/owner/submissions/pending').length
    expect(calls).toBeGreaterThan(0)
    await act(async () => dom.querySelector<HTMLAnchorElement>('a[href="/admin"]')!.click())
    await tick()
    expect(mocks.api.mock.calls.filter(([path]) => path === '/owner/submissions/pending')).toHaveLength(calls)
  })

  it('không gọi API đếm nếu tài khoản không có quyền duyệt', async () => {
    permissions = []
    await render()
    await tick()
    expect(countCalls()).toBe(0)
    expect(badge()).toBeUndefined()
  })
})
