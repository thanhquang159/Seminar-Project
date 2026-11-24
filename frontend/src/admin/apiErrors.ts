// Giữ nguyên lý do nghiệp vụ từ backend; không hiển thị HTML/traceback của lỗi máy chủ.
export async function apiErrorMessage(response: Response, fallback: string): Promise<string> {
  const payload: unknown = await response.json().catch(() => null)
  const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
    ? payload.detail : null
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item: unknown) => {
      if (typeof item !== 'object' || item === null || !('msg' in item) || typeof item.msg !== 'string') return []
      const field = 'loc' in item && Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
      return [`${field ? `${field}: ` : ''}${item.msg}`]
    })
    if (messages.length) return messages.join('; ')
  }
  return `${fallback} (HTTP ${response.status}). Vui lòng tải lại và thử lại.`
}
