import { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL } from '../config'

const API_GOC = API_BASE_URL
type UiBundle = Record<string, string>
type Translator = (khoa: string, thamSo?: Record<string, string | number>) => string

const boNhoBundle = new Map<string, UiBundle>()
const dangTaiBundle = new Map<string, Promise<UiBundle>>()

function laUiBundle(value: unknown): value is UiBundle {
  return (
    typeof value === 'object' &&
    value !== null &&
    Object.values(value).every((item) => typeof item === 'string')
  )
}

function docBundleDaLuu(locale: string): UiBundle | null {
  try {
    const raw = localStorage.getItem(`quan4-ui-${locale}`)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (!laUiBundle(parsed)) {
      throw new Error(`Bundle giao diện đã lưu cho ${locale} không hợp lệ`)
    }
    boNhoBundle.set(locale, parsed)
    return parsed
  } catch (error) {
    console.error(`Không đọc được bundle giao diện đã lưu cho ${locale}:`, error)
    return null
  }
}

function taiBundle(locale: string): Promise<UiBundle> {
  const daTai = dangTaiBundle.get(locale)
  if (daTai !== undefined) return daTai

  const request = (async () => {
    const res = await fetch(`${API_GOC}/ui-bundles/${locale}`)
    if (!res.ok) {
      throw new Error(`Tải bundle giao diện ${locale} thất bại: HTTP ${res.status}`)
    }
    const raw: unknown = await res.json()
    if (
      typeof raw !== 'object' ||
      raw === null ||
      !('status' in raw) ||
      raw.status !== 'ready' ||
      !('bundle' in raw) ||
      !laUiBundle(raw.bundle)
    ) {
      throw new Error(`Bundle giao diện ${locale} chưa sẵn sàng`)
    }
    boNhoBundle.set(locale, raw.bundle)
    try {
      localStorage.setItem(`quan4-ui-${locale}`, JSON.stringify(raw.bundle))
    } catch (error) {
      console.error(`Không lưu được bundle giao diện ${locale} để dùng ngoại tuyến:`, error)
    }
    return raw.bundle
  })()

  dangTaiBundle.set(locale, request)
  void request.then(
    () => dangTaiBundle.delete(locale),
    () => dangTaiBundle.delete(locale),
  )
  return request
}

// Bundle UI tĩnh trong `backend/static/ui/*.json`, 5 ngôn ngữ, không dịch máy.
// Trước SEC-010 hàm này poll mỗi 3s tối đa 10 lần chờ trạng thái `ready` vì
// server dịch nền locale lạ. Nay server trả `ready` ngay hoặc 404, nên một lần
// fetch là đủ — poll chỉ là chờ vô ích và giữ mạng sống thêm 30 giây mỗi lần đổi
// ngôn ngữ.
export function useUiBundle(locale: string): { t: Translator; sanSang: boolean } {
  const [bundleState, setBundleState] = useState(() => {
    const bundle = boNhoBundle.get(locale) ?? docBundleDaLuu(locale) ?? {}
    return { locale, bundle, sanSang: Object.keys(bundle).length > 0 }
  })

  useEffect(() => {
    let huy = false
    void taiBundle(locale)
      .then((goi) => {
        if (huy) return
        setBundleState({ locale, bundle: goi, sanSang: true })
      })
      .catch((error: unknown) => {
        if (huy) return
        console.error(`Không tải được bundle giao diện ${locale}:`, error)
        const daLuu = boNhoBundle.get(locale) ?? docBundleDaLuu(locale)
        setBundleState({ locale, bundle: daLuu ?? {}, sanSang: daLuu !== null })
      })
    return () => {
      huy = true
    }
  }, [locale])

  const sanSang =
    bundleState.locale === locale
      ? bundleState.sanSang
      : boNhoBundle.has(locale)

  const t = useMemo<Translator>(
    () => {
      const bundle =
        bundleState.locale === locale
          ? bundleState.bundle
          : boNhoBundle.get(locale) ?? {}
      return (khoa, thamSo) => {
        let chuoi = bundle[khoa] ?? khoa
        if (thamSo !== undefined) {
          chuoi = chuoi.replace(/\{(\w+)\}/g, (placeholder, ten: string) =>
            Object.hasOwn(thamSo, ten) ? String(thamSo[ten]) : placeholder,
          )
        }
        return chuoi
      }
    },
    [bundleState, locale],
  )

  return { t, sanSang }
}