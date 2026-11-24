import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AudioTasks from './AudioTasks'

const mocks = vi.hoisted(() => ({ api: vi.fn(), apiText: vi.fn() }))
vi.mock('./api', () => mocks)
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })

let dom: HTMLDivElement
let root: Root
class FakeEvents {
  static current: FakeEvents
  onmessage: (() => void) | null = null
  close = vi.fn()
  constructor() { FakeEvents.current = this }
}

const task = (status: string) => ({ task_id: status, poi_id: 'poi-1', poi_name: `Quán ${status}`,
  lang: 'en', status, progress: status === 'done' ? 100 : 0, loi: status === 'error' ? 'TTS không kết nối được' : null })

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('EventSource', FakeEvents)
  mocks.api.mockReset().mockResolvedValue(['queued', 'running', 'paused', 'done', 'error', 'canceled'].map(task))
  mocks.apiText.mockReset().mockResolvedValue({ ok: true })
  dom = document.createElement('div')
  document.body.appendChild(dom)
  root = createRoot(dom)
})

afterEach(() => {
  act(() => root.unmount())
  dom.remove()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

async function render() {
  await act(async () => root.render(<AudioTasks />))
}

function row(status: string) {
  return [...dom.querySelectorAll('li')].find((item) => item.textContent?.includes(`Quán ${status}`))!
}

function button(status: string, label: string) {
  return [...row(status).querySelectorAll('button')].find((item) => item.textContent === label)!
}

describe('AudioTasks', () => {
  it('hiển thị tên quán, đúng trạng thái và chỉ các nút hợp lệ', async () => {
    await render()
    expect(row('queued').textContent).toContain('Chờ chạy')
    expect(button('queued', 'Bắt đầu')).toBeDefined()
    expect(button('queued', 'Tiếp tục')).toBeUndefined()
    expect(row('running').textContent).toContain('Đang tạo audio')
    expect(button('running', 'Tiếp tục')).toBeUndefined()
    expect(button('paused', 'Tiếp tục')).toBeDefined()
    expect(row('done').querySelectorAll('button')).toHaveLength(0)
    expect(row('error').textContent).toContain('TTS không kết nối được')
    expect(button('error', 'Thử lại')).toBeDefined()
    expect(button('canceled', 'Thử lại')).toBeDefined()
  })

  it.each([['queued', 'Bắt đầu', 'resume'], ['paused', 'Tiếp tục', 'resume'],
    ['error', 'Thử lại', 'retry'], ['running', 'Tạm dừng', 'pause'], ['running', 'Hủy bỏ', 'cancel']])(
    'gửi đúng lệnh cho trạng thái %s với nút %s', async (status, label, command) => {
      await render()
      await act(async () => button(status, label).click())
      expect(mocks.apiText).toHaveBeenCalledWith(`/audio/tasks/${status}/${command}`, { method: 'POST' })
      expect(mocks.api).toHaveBeenCalledTimes(2)
    },
  )

  it('hiển thị lỗi 409 thay vì coi lệnh đã thành công', async () => {
    mocks.apiText.mockResolvedValue({ ok: false, json: async () => ({ detail: 'Trạng thái tác vụ đã thay đổi' }) })
    await render()
    await act(async () => button('paused', 'Tiếp tục').click())
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Trạng thái tác vụ đã thay đổi')
  })

  it('không cho thử lại tác vụ đã được thay bằng yêu cầu mới', async () => {
    mocks.api.mockResolvedValue([{ ...task('canceled'), is_latest: false, loi: 'Đã thay bằng yêu cầu audio mới' }])
    await render()
    expect(button('canceled', 'Thử lại')).toBeUndefined()
    expect(row('canceled').textContent).toContain('Đã thay bằng yêu cầu audio mới')
  })

  it('tiếp tục polling khi SSE không có thông báo và dọn khi unmount', async () => {
    await render()
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(mocks.api).toHaveBeenCalledTimes(2)
    await act(async () => FakeEvents.current.onmessage?.())
    expect(mocks.api).toHaveBeenCalledTimes(3)
    act(() => root.unmount())
    expect(FakeEvents.current.close).toHaveBeenCalledOnce()
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(mocks.api).toHaveBeenCalledTimes(3)
  })

  it('hiển thị lỗi mạng', async () => {
    mocks.apiText.mockRejectedValue(new Error('offline'))
    await render()
    await act(async () => button('error', 'Thử lại').click())
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Không kết nối được máy chủ')
  })
})
