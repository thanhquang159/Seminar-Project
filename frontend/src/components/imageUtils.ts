import { API_BASE_URL } from '../config'

// Hàm chuẩn hóa URL ảnh: nếu là đường dẫn tĩnh cục bộ (/static/...) thì ghép host backend
export function layUrlAnh(url: string): string {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const apiGoc = API_BASE_URL
  return `${apiGoc}${url.startsWith('/') ? '' : '/'}${url}`
}
