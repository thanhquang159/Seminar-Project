import { useEffect, useMemo, useState } from 'react'
import { API_BASE_URL } from '../config'
import { docUiBundle, luuUiBundle } from '../offline/idb'

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

async function docBundleDaLuu(locale: string): Promise<UiBundle | null> {
  try {
    const saved = await docUiBundle(locale)
    if (saved === null) return null
    if (!laUiBundle(saved.translations)) {
      throw new Error(`Bundle giao diện đã lưu cho ${locale} không hợp lệ`)
    }
    boNhoBundle.set(locale, saved.translations)
    return saved.translations
  } catch (error) {
    console.error(`Không đọc được bundle giao diện trong IndexedDB cho ${locale}:`, error)
    return null
  }
}

function taiBundle(locale: string): Promise<UiBundle> {
  const daTai = dangTaiBundle.get(locale)
  if (daTai !== undefined) return daTai

  const request = (async () => {
    const daLuu = boNhoBundle.get(locale) ?? await docBundleDaLuu(locale)
    if (daLuu !== null && daLuu !== undefined) return daLuu

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
      const version =
        'source_hash' in raw && typeof raw.source_hash === 'string'
          ? raw.source_hash
          : '1'
      await luuUiBundle(locale, raw.bundle, version)
    } catch (error) {
      console.error(`Không lưu được bundle giao diện ${locale} vào IndexedDB:`, error)
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
    const bundle = boNhoBundle.get(locale) ?? {}
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
        const daLuu = boNhoBundle.get(locale) ?? null
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