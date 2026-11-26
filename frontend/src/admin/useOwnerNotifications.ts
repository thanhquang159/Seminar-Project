import { useEffect, useRef, useState } from 'react'
import { api, apiText } from './api'

interface OwnerNotification {
  id: string
  message: string
  read: boolean
}

interface OwnerUpdates {
  username: string
  status: string
  adminNote: string
  notifications: OwnerNotification[]
  error: string
}

export const OWNER_POLL_INTERVAL = 5_000
const isVisible = () => document.visibilityState !== 'hidden'

export function useOwnerNotifications(user: string | null) {
  const [updates, setUpdates] = useState<OwnerUpdates | null>(null)
  const generation = useRef(0)
  const readIds = useRef(new Set<string>())

  useEffect(() => {
    const session = ++generation.current
    readIds.current = new Set()
    if (!user) return
    let active = true
    let running = false
    let expired = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let requestTimeout: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined

    const refresh = async () => {
      if (!active || running || expired || !isVisible()) return
      clearTimeout(timer)
      running = true
      controller = new AbortController()
      requestTimeout = setTimeout(() => controller?.abort(), 15_000)
      const results = await Promise.allSettled([
        api<{ status: string; admin_note: string }>('/owner/registration-status', { signal: controller.signal, cache: 'no-store' }),
        api<OwnerNotification[]>('/owner/notifications', { signal: controller.signal, cache: 'no-store' }),
      ])
      clearTimeout(requestTimeout)
      running = false
      if (!active) return
      const [registration, notifications] = results
      expired = results.some((result) => result.status === 'rejected'
        && result.reason instanceof Error && result.reason.message === 'HTTP 401')
      const unregistered = registration.status === 'rejected'
        && registration.reason instanceof Error && registration.reason.message === 'HTTP 404'
      setUpdates((previous) => {
        const old = previous?.username === user ? previous : null
        return {
          username: user,
          status: registration.status === 'fulfilled' ? registration.value.status
            : unregistered ? 'unregistered' : old?.status ?? 'unavailable',
          adminNote: registration.status === 'fulfilled' ? registration.value.admin_note ?? '' : old?.adminNote ?? '',
          notifications: notifications.status === 'fulfilled'
            ? notifications.value.map((item) => ({ ...item, read: item.read || readIds.current.has(item.id) }))
            : old?.notifications ?? [],
          error: expired ? 'Phiên đăng nhập đã hết hạn. Vui lòng đăng xuất và đăng nhập lại.'
            : (registration.status === 'rejected' && !unregistered) || notifications.status === 'rejected'
              ? 'Chưa cập nhật được thông báo hoặc trạng thái tài khoản. Hệ thống sẽ tự thử lại.' : '',
        }
      })
      if (!expired && isVisible()) timer = setTimeout(refresh, OWNER_POLL_INTERVAL)
    }
    const resume = () => {
      clearTimeout(timer)
      void refresh()
    }
    void refresh()
    window.addEventListener('focus', resume)
    window.addEventListener('online', resume)
    document.addEventListener('visibilitychange', resume)
    return () => {
      active = false
      generation.current = session + 1
      clearTimeout(timer)
      clearTimeout(requestTimeout)
      controller?.abort()
      window.removeEventListener('focus', resume)
      window.removeEventListener('online', resume)
      document.removeEventListener('visibilitychange', resume)
    }
  }, [user])

  const markRead = async (id: string) => {
    const session = generation.current
    try {
      const response = await apiText(`/owner/notifications/${id}/read`, { method: 'POST' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      if (session !== generation.current) return
      // Giữ kết quả đã đọc nếu một truy vấn bắt đầu trước thao tác này về muộn.
      readIds.current.add(id)
      setUpdates((previous) => previous && ({
        ...previous,
        notifications: previous.notifications.map((item) => item.id === id ? { ...item, read: true } : item),
      }))
    } catch {
      if (session !== generation.current) return
      setUpdates((previous) => previous && ({
        ...previous, error: 'Không thể cập nhật trạng thái thông báo. Vui lòng thử lại.',
      }))
    }
  }

  const current = updates?.username === user ? updates : null
  return {
    status: current?.status ?? '',
    adminNote: current?.adminNote ?? '',
    notifications: current?.notifications ?? [],
    error: current?.error ?? '',
    markRead,
  }
}
