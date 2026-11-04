// Cấu hình URL gốc API backend, ưu tiên biến môi trường VITE_API_URL
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) || 'http://127.0.0.1:8000'
