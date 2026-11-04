import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../config'

const API_GOC = API_BASE_URL

// Bundle UI tĩnh trong `backend/static/ui/*.json`, 5 ngôn ngữ, không dịch máy.
// Trước SEC-010 hàm này poll mỗi 3s tối đa 10 lần chờ trạng thái `ready` vì
// server dịch nền locale lạ. Nay server trả `ready` ngay hoặc 404, nên một lần
// fetch là đủ — poll chỉ là chờ vô ích và giữ mạng sống thêm 30 giây mỗi lần đổi
// ngôn ngữ.
export function useUiBundle(locale: string): { t: (khoa: string) => string; sanSang: boolean } {
  const [bundle, setBundle] = useState<Record<string, string>>({})
  const [sanSang, setSanSang] = useState(false)

  useEffect(() => {
    let huy = false
    const tai = async () => {
      try {
        const res = await fetch(`${API_GOC}/ui-bundles/${locale}`)
        if (huy) return
        if (!res.ok) {
          setBundle({})
          setSanSang(false)
          return
        }
        const goi = (await res.json()) as { status: string; bundle: Record<string, string> }
        if (huy) return
        setBundle(goi.bundle)
        setSanSang(goi.status === 'ready')
      } catch {
        if (!huy) setSanSang(false)
      }
    }
    void tai()
    return () => {
      huy = true
    }
  }, [locale])

  return { t: (khoa: string) => bundle[khoa] ?? khoa, sanSang }
}