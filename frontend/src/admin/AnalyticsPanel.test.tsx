import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import AnalyticsPanel from './AnalyticsPanel'

vi.mock('./api', () => ({ api: vi.fn() }))
Object.defineProperty(globalThis, 'IS_REACT_ACT_ENVIRONMENT', {
  configurable: true,
  value: true,
})

const SUMMARY = {
  metric_date: '2026-11-11',
  period_start: '2026-11-05',
  period_days: 7,
  period_views: 18,
  period_audio_plays: 9,
  today_views: 4,
  today_audio_plays: 2,
  tracked_online_users: 3,
  daily: [
    { metric_date: '2026-11-05', views: 0, audio_plays: 0 },
    { metric_date: '2026-11-11', views: 4, audio_plays: 2 },
  ],
  top_pois: [
    { poi_id: 'poi-1', name: 'Quán mẫu', views: 7, audio_plays: 3 },
  ],
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  vi.mocked(api).mockResolvedValue(SUMMARY)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
})

describe('admin analytics dashboard', () => {
  it('renders period totals, daily series and top POIs from the summary API', async () => {
    act(() => root.render(<AnalyticsPanel />))
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 20))
    })

    expect(container.textContent).toContain('Lượt xem POI · 7 ngày')
    expect(container.textContent).toContain('Lượt bấm nghe · 7 ngày')
    expect(container.textContent).toContain('Thiết bị online')
    expect(container.textContent).toContain('Có analytics bật, hoạt động trong 5 phút')
    expect(container.textContent).toContain('Xu hướng theo ngày')
    expect(container.textContent).toContain('Quán mẫu')
    expect(container.textContent).toContain('18')
    expect(container.textContent).not.toContain('Quan sát vị trí Runtime')
    expect(vi.mocked(api)).toHaveBeenCalledWith(
      '/admin/analytics/summary?so_ngay=7',
      { cache: 'no-store' },
    )
  })

  it('reloads the dashboard when the selected period changes', async () => {
    act(() => root.render(<AnalyticsPanel />))
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 20))
    })

    const periodButton = Array.from(container.querySelectorAll('button'))
      .find((button) => button.textContent === '30 ngày')
    expect(periodButton).toBeDefined()

    act(() => {
      periodButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 20))
    })

    expect(vi.mocked(api)).toHaveBeenLastCalledWith(
      '/admin/analytics/summary?so_ngay=30',
      { cache: 'no-store' },
    )
    expect(container.textContent).toContain('Lượt xem POI · 30 ngày')
  })
})
