import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'

export const APPROVALS_POLL_INTERVAL = 5_000
const isVisible = () => document.visibilityState !== 'hidden'

export function useApprovalCount(user: string | null, permissions: string[]) {
  const enabled = Boolean(user) && permissions.some((permission) =>
    permission === 'user:update' || permission === 'poi:approve')
  const [count, setCount] = useState<{ user: string; total: number; version: number } | null>(null)
  const request = useRef<AbortController | null>(null)
  const expired = useRef(false)

  const refresh = useCallback(async () => {
    if (!user || !enabled) return
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    const timeout = setTimeout(() => controller.abort(), 15_000)
    try {
      const result = await api<{ total: number }>('/owner/approvals/counts', {
        signal: controller.signal, cache: 'no-store',
      })
      // Bỏ kết quả cũ nếu vừa tải lại sau thao tác duyệt hoặc đã đổi phiên.
      if (!controller.signal.aborted) {
        setCount((previous) => ({ user, total: result.total, version: (previous?.version ?? 0) + 1 }))
      }
    } catch (error) {
      // Lỗi mạng tạm thời giữ số gần nhất; dừng cập nhật nếu phiên hết hạn.
      if (!controller.signal.aborted && error instanceof Error) {
        expired.current = error.message === 'HTTP 401' || error.message === 'HTTP 403'
      }
    } finally {
      clearTimeout(timeout)
      if (request.current === controller) request.current = null
    }
  }, [user, enabled])

  useEffect(() => {
    if (!enabled) return
    expired.current = false
    const resume = () => {
      if (isVisible() && !request.current && !expired.current) void refresh()
    }
    resume()
    const timer = setInterval(resume, APPROVALS_POLL_INTERVAL)
    window.addEventListener('focus', resume)
    window.addEventListener('online', resume)
    document.addEventListener('visibilitychange', resume)
    return () => {
      clearInterval(timer)
      request.current?.abort()
      request.current = null
      window.removeEventListener('focus', resume)
      window.removeEventListener('online', resume)
      document.removeEventListener('visibilitychange', resume)
    }
  }, [enabled, refresh])

  const current = enabled && count?.user === user ? count : null
  return { count: current?.total ?? 0, refreshVersion: current?.version ?? 0, refresh }
}
