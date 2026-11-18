import { describe, expect, it } from 'vitest'
import { resolveApiBaseUrl } from './config'

describe('API base URL', () => {
  it('uses the frontend loopback hostname for local cookie requests', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:8000', 'localhost', false))
      .toBe('http://localhost:8000')
    expect(resolveApiBaseUrl('http://localhost:8000', '127.0.0.1', false))
      .toBe('http://127.0.0.1:8000')
  })

  it('preserves remote API hosts and production configuration', () => {
    expect(resolveApiBaseUrl('https://api.example.test/', 'localhost', false))
      .toBe('https://api.example.test')
    expect(resolveApiBaseUrl('https://api.example.test', 'localhost', true))
      .toBe('https://api.example.test')
  })

  it('requires an explicit production API URL', () => {
    expect(() => resolveApiBaseUrl(undefined, 'localhost', true))
      .toThrow('Missing VITE_API_URL')
  })
})
