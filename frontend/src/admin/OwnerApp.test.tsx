import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OwnerApp from './OwnerApp'

const mocks = vi.hoisted(() => ({ api: vi.fn(), apiText: vi.fn() }))
vi.mock('./api', () => mocks)
vi.mock('./OwnerMenuManagement', () => ({ default: () => null }))
vi.mock('./OwnerPoiQrCodes', () => ({ default: () => null }))
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })

let dom: HTMLDivElement
let root: Root
let status: string
let history: ReturnType<typeof submission>[]
const submission = (state = 'pending') => ({ id: 's1', poi_id: state === 'approved' ? 'p1' : null,
  submission_type: 'create', data: { name: '2632' }, status: state,
  created_at: '2026-11-24T03:00:00Z', admin_note: state === 'rejected' ? 'Cần bổ sung hình ảnh' : '' })

beforeEach(() => {
  status = 'approved'
  history = [submission()]
  window.history.replaceState(null, '', '/owner/history')
  mocks.api.mockReset().mockImplementation(async (path: string) => {
    if (path === '/admin/auth/me') return { username: 'demo.admin@quan4.local' }
    if (path === '/owner/registration-status') return { status }
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
  window.history.replaceState(null, '', '/')
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
