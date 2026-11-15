
// API configuration for local development and production.

// Read API URL from Vite environment variables.
const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();

// Preserve LAN access during local development.
const defaultApiHost =
  typeof window !== 'undefined' && window.location.hostname !== ''
    ? window.location.hostname
    : 'localhost';

const localApiUrl = `http://${defaultApiHost}:8000`;

// In production, VITE_API_URL must be explicitly configured.
if (!configuredApiUrl && import.meta.env.PROD) {
  throw new Error(
    'Missing VITE_API_URL. Please configure it in Vercel Environment Variables.'
  );
}

// Remove trailing slash to avoid duplicated slashes in API requests.
export const API_BASE_URL = (
  configuredApiUrl || localApiUrl
).replace(/\/+$/, '');
