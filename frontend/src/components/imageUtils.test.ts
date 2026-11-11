import { describe, expect, it } from 'vitest'
import { API_BASE_URL } from '../config'
import { layUrlAnh } from './imageUtils'

describe('layUrlAnh', () => {
  it('resolves local paths against the API host', () => {
    expect(layUrlAnh('/static/menu.jpg')).toBe(`${API_BASE_URL}/static/menu.jpg`)
  })

  it('keeps safe absolute HTTP URLs', () => {
    expect(layUrlAnh('https://cdn.example.test/menu.jpg')).toBe('https://cdn.example.test/menu.jpg')
  })

  it('rejects non-HTTP schemes and credentials', () => {
    expect(layUrlAnh('javascript:alert(1)')).toBe('')
    expect(layUrlAnh('data:image/svg+xml,test')).toBe('')
    expect(layUrlAnh('https://user:pass@example.test/image.jpg')).toBe('')
  })
})
