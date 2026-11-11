import { API_BASE_URL } from '../config'

export function layUrlAnh(url: string): string {
  const value = url.trim()
  if (!value) return ''
  try {
    const resolved = new URL(value, `${API_BASE_URL}/`)
    if ((resolved.protocol !== 'http:' && resolved.protocol !== 'https:')
      || resolved.username !== ''
      || resolved.password !== '') return ''
    return resolved.href
  } catch {
    return ''
  }
}
