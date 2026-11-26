import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiText } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('Làm mới phiên API', () => {
  it.each([
    ['/owner/notifications', '/owner/auth/refresh'],
    ['/owner/pois', '/owner/auth/refresh'],
    ['/admin/users', '/admin/auth/refresh'],
  ])('%s dùng đúng phiên và thử lại một lần', async (path, refreshPath) => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response('{}'))
      .mockResolvedValueOnce(new Response('[]'))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()
    expect((await apiText(path, { signal: controller.signal })).ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1][0]).toContain(refreshPath)
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ credentials: 'include', signal: controller.signal })
    expect(fetchMock.mock.calls[2][0]).toBe(fetchMock.mock.calls[0][0])
  })

  it('trả 401 khi phiên đã thu hồi, không lặp vô hạn', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)
    expect((await apiText('/owner/notifications')).status).toBe(401)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
