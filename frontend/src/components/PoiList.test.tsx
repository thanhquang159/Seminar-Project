import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it } from 'vitest'
import { PoiDetail, PoiList } from './PoiList'
import type { Poi } from '../stores/poiStore'

// OWN-005 (SEC-007): tên quán + mô tả do chủ quán gửi lên là dữ liệu không đáng
// tin. Nếu chỉ tin vào "React escape sẵn" thì không có gì chứng minh điều đó còn
// đúng sau mỗi lần sửa code — nên ở đây render thật rồi đọc DOM thật.

const DE_TAN_CONG:
  | string
  | null = '<img src=x onerror="window.__bi_mat_da_chay=true"><script>window.__bi_mat_da_chay=true</script>'

const POI: Poi = {
  id: 'p1',
  name: DE_TAN_CONG,
  description: 'Mô tả <b>đậm</b> & "nháy" <script>alert(1)</script>',
  lat: 10.7569,
  lng: 106.7641,
  trigger_radius: 30,
  audio_priority: 0,
  lang: 'vi',
  is_fallback: false,
  audio_url: null,
}

let goc: HTMLDivElement | null = null
let root: Root | null = null

function render(ui: React.ReactNode): HTMLDivElement {
  goc = document.createElement('div')
  document.body.appendChild(goc)
  root = createRoot(goc)
  act(() => root!.render(ui))
  return goc
}

afterEach(() => {
  if (root !== null) {
    act(() => root!.unmount())
    root = null
  }
  goc?.remove()
  goc = null
  delete (window as unknown as Record<string, unknown>).__bi_mat_da_chay
})

describe('OWN-005 — nội dung chủ quán không được thành mã chạy được', () => {
  it('danh sách: onerror/script trong tên quán không tạo phần tử HTML', () => {
    const dom = render(<PoiList pois={[POI]} onChon={() => {}} />)
    expect(dom.querySelector('script')).toBeNull()
    expect(dom.querySelector('img')).toBeNull()
    // Vẫn phải hiện đúng chữ cho người đọc, không phải bị xoá.
    expect(dom.textContent).toContain(DE_TAN_CONG)
  })

  it('chi tiết: thẻ trong mô tả không được thành phần tử HTML', () => {
    const dom = render(<PoiDetail poi={POI} onNghe={() => {}} />)
    expect(dom.querySelector('script')).toBeNull()
    expect(dom.querySelector('b')).toBeNull()
    expect(dom.textContent).toContain('<script>alert(1)</script>')
    expect(dom.textContent).toContain('Mô tả')
  })

  it('mô tả dài 20.000 ký tự không làm treo render', () => {
    const dai = { ...POI, description: 'x'.repeat(20_000) }
    const dom = render(<PoiDetail poi={dai} onNghe={() => {}} />)
    expect(dom.textContent).toContain('x'.repeat(20_000))
  })
})

// Chặn tái phạm: giả định "React escape sẵn" chỉ đúng khi không ai mở lại cửa
// sổ bằng tay. Giả định đó không hiện trong code review nên `eslint.config.js`
// chặn thẳng các sink HTML (kiểm bằng `tests/test_sec_007.py` ở backend).