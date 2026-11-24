import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PoiPublication from './PoiPublication'

const apiMock = vi.hoisted(() => ({ apiText: vi.fn() }))
vi.mock('./api', () => apiMock)

Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', { configurable: true, value: true })

const readiness = { ready: true, english_ready: true, audio_ready: true, audio_status: 'ready', reasons: [] as string[] }
const poi = { id: 'poi-1', publication_status: 'unpublished', is_active: false, readiness }
let dom: HTMLDivElement
let root: Root

beforeEach(() => {
  dom = document.createElement('div')
  document.body.appendChild(dom)
  root = createRoot(dom)
  apiMock.apiText.mockReset().mockResolvedValue({ ok: true })
})

afterEach(() => {
  act(() => root.unmount())
  dom.remove()
  window.history.replaceState({}, '', '/')
})

function button(label: string) {
  return [...dom.querySelectorAll('button')].find((item) => item.textContent === label)!
}

describe('Công khai POI', () => {
  it('giải thích POI cũ đã duyệt đang chờ công khai và mở được trang audio', async () => {
    await act(async () => root.render(<PoiPublication poi={{ ...poi, publication_status: 'pending_review',
      readiness: { ...readiness, ready: false, audio_ready: false, audio_status: 'queued', review_approved: true },
    }} canPublish onChanged={vi.fn()} />))
    expect(dom.textContent).toContain('Đã duyệt · chờ công khai')
    await act(async () => button('Xem tác vụ audio').click())
    expect(window.location.pathname).toBe('/admin/audio')
  })

  it('chặn nút công khai và giải thích English/audio còn thiếu', async () => {
    await act(async () => root.render(<PoiPublication poi={{ ...poi, readiness: {
      ...readiness, ready: false, english_ready: false, audio_ready: false,
      audio_status: 'queued', reasons: ['Cần bản tiếng Anh.', 'Cần audio tiếng Anh.'],
    } }} canPublish onChanged={vi.fn()} />))
    expect(button('Công khai').disabled).toBe(true)
    expect(dom.textContent).toContain('Cần bản tiếng Anh.')
    expect(dom.textContent).toContain('Cần audio tiếng Anh.')
    expect(apiMock.apiText).not.toHaveBeenCalled()
  })

  it('gọi publish rồi làm mới dữ liệu công khai', async () => {
    const onChanged = vi.fn().mockResolvedValue(undefined)
    await act(async () => root.render(<PoiPublication poi={poi} canPublish onChanged={onChanged} />))
    await act(async () => button('Công khai').click())
    expect(apiMock.apiText).toHaveBeenCalledWith('/admin/pois/poi-1/publish', { method: 'POST' })
    expect(onChanged).toHaveBeenCalledOnce()
    expect(dom.textContent).toContain('Đã công khai POI trên bản đồ.')
  })

  it('cho phép ẩn ngay cả khi audio đang lỗi', async () => {
    await act(async () => root.render(<PoiPublication poi={{ ...poi, publication_status: 'published', is_active: true,
      readiness: { ...readiness, ready: false, audio_ready: false, audio_status: 'failed' },
    }} canPublish onChanged={vi.fn()} />))
    expect(button('Ẩn khỏi công khai').disabled).toBe(false)
    await act(async () => button('Ẩn khỏi công khai').click())
    expect(apiMock.apiText).toHaveBeenCalledWith('/admin/pois/poi-1/unpublish', { method: 'POST' })
  })

  it('ẩn thao tác đổi trạng thái khi thiếu quyền publish', async () => {
    await act(async () => root.render(<PoiPublication poi={poi} canPublish={false} onChanged={vi.fn()} />))
    expect(button('Công khai')).toBeUndefined()
    expect(dom.textContent).toContain('Cần quyền công khai POI')
  })

  it('hiển thị lý do backend trả về khi readiness đã thay đổi', async () => {
    apiMock.apiText.mockResolvedValue({ ok: false, json: async () => ({ detail: {
      readiness: { reasons: ['Audio tiếng Anh chưa hoàn tất.'] },
    } }) })
    const onChanged = vi.fn()
    await act(async () => root.render(<PoiPublication poi={poi} canPublish onChanged={onChanged} />))
    await act(async () => button('Công khai').click())
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Audio tiếng Anh chưa hoàn tất.')
    expect(dom.querySelector('[role="status"]')).toBeNull()
    expect(onChanged).toHaveBeenCalledOnce()
  })

  it('xử lý lỗi mạng và cho phép thử lại', async () => {
    apiMock.apiText.mockRejectedValue(new Error('offline'))
    await act(async () => root.render(<PoiPublication poi={poi} canPublish onChanged={vi.fn()} />))
    await act(async () => button('Công khai').click())
    expect(dom.querySelector('[role="alert"]')?.textContent).toContain('Không kết nối được máy chủ')
    expect(button('Công khai').disabled).toBe(false)
  })

  it('kiểm tra lại và mở đúng POI để chuẩn bị English', async () => {
    const onChanged = vi.fn()
    await act(async () => root.render(<PoiPublication poi={poi} canPublish onChanged={onChanged} />))
    await act(async () => button('Kiểm tra lại').click())
    expect(onChanged).toHaveBeenCalledOnce()
    await act(async () => button('Chuẩn bị English + Audio').click())
    expect(window.location.pathname + window.location.search).toBe('/admin/translations?poi=poi-1&lang=en')
  })

  it('khóa thao tác trong lúc request đang chờ', async () => {
    let complete: (value: unknown) => void = () => {}
    apiMock.apiText.mockReturnValue(new Promise((resolve) => { complete = resolve }))
    await act(async () => root.render(<PoiPublication poi={poi} canPublish onChanged={vi.fn()} />))
    await act(async () => button('Công khai').click())
    expect(button('Đang xử lý…').disabled).toBe(true)
    await act(async () => complete({ ok: true }))
    expect(apiMock.apiText).toHaveBeenCalledOnce()
  })
})
