// Use the browser's host so another device on the same LAN reaches this PC's API.
const defaultApiHost =
  typeof window !== 'undefined' && window.location.hostname !== ''
    ? window.location.hostname
    : 'localhost'

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) || `http://${defaultApiHost}:8000`
