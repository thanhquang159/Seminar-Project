import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OwnerApprovals from './OwnerApprovals'

const mocks = vi.hoisted(() => ({ api: vi.fn(), apiText: vi.fn() }))
vi.mock('./api', () => mocks)
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })
let dom: HTMLDivElement
let root: Root
const changed = vi.fn()
const row = { id: 's1', username: 'owner@example.test', name: '2632', created_at: null,
  data: { lat: 10.7, lng: 106.7 }, can_approve: true, approval_blockers: [] as string[] }

beforeEach(() => {
  mocks.api.mockReset().mockImplementation(async (path: string) => path.endsWith('/pending') ? [row] : [])
  mocks.apiText.mockReset().mockResolvedValue({ ok: true })
  changed.mockReset().mockResolvedValue(undefined)
  dom = document.createElement('div')
  document.body.appendChild(dom)
  root = createRoot(dom)
})
afterEach(() => { act(() => root.unmount()); dom.remove() })
async function render() { await act(async () => root.render(<OwnerApprovals onPoiApproved={changed} />)) }
function button(label: string) { return [...dom.querySelectorAll('button')].find((b) => b.textContent?.trim() === label)! }

describe('Duyệt đề xuất Owner', () => {
  it.each([[403, 'Không có quyền duyệt POI'], [409, 'Đề xuất thiếu hoặc sai: vĩ độ, kinh độ']])(
    'hiển thị lý do HTTP %s từ backend', async (status, detail) => {
      mocks.apiText.mockResolvedValue(new Response(JSON.stringify({ detail }), { status: Number(status) }))
      await render()
      await act(async () => button('Duyệt quán').click())
      expect(dom.querySelector('[role="alert"]')?.textContent).toContain(String(detail))
      expect(changed).not.toHaveBeenCalled()
    },
  )
  it('đơn bị chặn hiển thị lý do ngay trước khi bấm, vẫn cho từ chối', async () => {
    mocks.api.mockImplementation(async (path: string) => path.endsWith('/pending')
      ? [{ ...row, can_approve: false, approval_blockers: ['Đề xuất thiếu hoặc sai: vĩ độ, kinh độ.'] }] : [])
    await render()
    expect(button('Duyệt quán').disabled).toBe(true)
    expect(button('Từ chối').disabled).toBe(false)
    expect(dom.textContent).toContain('Đề xuất thiếu hoặc sai: vĩ độ, kinh độ.')
  })
  it('lỗi máy chủ không trả JSON vẫn hiện HTTP và không báo duyệt thành công', async () => {
    mocks.apiText.mockResolvedValue(new Response('Internal Server Error', { status: 500 }))
    await render()
    await act(async () => button('Duyệt quán').click())
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('HTTP 500')
    expect(changed).not.toHaveBeenCalled()
  })
  it('báo lỗi mạng và mở lại nút để thử', async () => {
    mocks.apiText.mockRejectedValue(new TypeError('Failed to fetch'))
    await render()
    await act(async () => button('Duyệt quán').click())
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Không kết nối được máy chủ')
    expect(button('Duyệt quán').disabled).toBe(false)
  })
  it('Admin duyệt đề xuất do mình gửi khi backend cho phép, làm mới danh sách và nhắc công khai', async () => {
    mocks.api.mockImplementation(async (path: string) => path.endsWith('/pending')
      ? [{ ...row, username: 'demo.admin@quan4.local' }] : [])
    await render()
    expect(button('Duyệt quán').disabled).toBe(false)
    expect(dom.textContent).not.toContain('Hãy dùng tài khoản Admin khác')
    await act(async () => button('Duyệt quán').click())
    expect(mocks.apiText).toHaveBeenCalledWith('/owner/submissions/s1/approve', { method: 'POST' })
    expect(changed).toHaveBeenCalledOnce()
    expect(dom.querySelector('[role="status"]')?.textContent).toContain('POI chưa công khai')
  })
  it('giữ luồng từ chối kèm lý do', async () => {
    await render()
    const input = dom.querySelector<HTMLInputElement>('[aria-label="Lý do từ chối 2632"]')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'Bổ sung tọa độ')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => button('Từ chối').click())
    expect(mocks.apiText).toHaveBeenCalledWith('/owner/submissions/s1/reject', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ admin_note: 'Bổ sung tọa độ' }),
    })
    expect(dom.querySelector('[role="status"]')?.textContent).toContain('Từ chối quán thành công')
  })
})
