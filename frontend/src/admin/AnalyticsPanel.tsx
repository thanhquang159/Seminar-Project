import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import './AnalyticsPanel.css'

interface DailyMetric {
  metric_date: string
  views: number
  audio_plays: number
}

interface PoiMetric {
  poi_id: string
  name: string
  views: number
  audio_plays: number
}

interface AnalyticsSummary {
  metric_date: string
  period_start: string
  period_days: number
  period_views: number
  period_audio_plays: number
  today_views: number
  today_audio_plays: number
  tracked_online_users: number | null
  daily: DailyMetric[]
  top_pois: PoiMetric[]
}

const PERIODS = [7, 30] as const
type Period = (typeof PERIODS)[number]

function dinhDangSo(value: number): string {
  return new Intl.NumberFormat('vi-VN').format(value)
}

function dinhDangNgay(value: string): string {
  const [, month, day] = value.split('-')
  return `${day}/${month}`
}

export default function AnalyticsPanel() {
  const [period, setPeriod] = useState<Period>(7)
  const [refreshKey, setRefreshKey] = useState(0)
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const taiDuLieu = useCallback(async (isMounted: () => boolean) => {
    try {
      const summary = await api<AnalyticsSummary>(
        `/admin/analytics/summary?so_ngay=${period}`,
        { cache: 'no-store' },
      )
      if (!isMounted()) return
      setData(summary)
      setUpdatedAt(new Date())
      setError('')
    } catch {
      if (isMounted()) setError('Không tải được thống kê. Hãy kiểm tra quyền analytics:view và thử lại.')
    } finally {
      if (isMounted()) setLoading(false)
    }
  }, [period])

  useEffect(() => {
    let active = true
    const isMounted = () => active
    const firstLoad = window.setTimeout(() => void taiDuLieu(isMounted), 0)

    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void taiDuLieu(isMounted)
    }, 10000)

    return () => {
      active = false
      window.clearTimeout(firstLoad)
      window.clearInterval(timer)
    }
  }, [taiDuLieu, refreshKey])

  const maxDaily = useMemo(
    () => Math.max(1, ...(data?.daily.flatMap((day) => [day.views, day.audio_plays]) ?? [])),
    [data],
  )

  if (loading && data === null) {
    return (
      <section className="analytics-page" aria-live="polite">
        <div className="analytics-page__loading">
          <span className="analytics-page__spinner" aria-hidden="true" />
          <p>Đang tải thống kê lượt xem và lượt nghe…</p>
        </div>
      </section>
    )
  }

  if (data === null) {
    return (
      <section className="analytics-page">
        <div className="analytics-page__error" role="alert">
          <strong>Chưa tải được số liệu</strong>
          <p>{error}</p>
          <button
            className="btn btn--primary"
            type="button"
            onClick={() => {
              setError('')
              setLoading(true)
              setRefreshKey((key) => key + 1)
            }}
          >
            Thử lại
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="analytics-page" aria-label="Thống kê lượt xem và lượt nghe">
      <header className="analytics-page__header">
        <div>
          <span className="analytics-page__eyebrow">BÁO CÁO TƯƠNG TÁC</span>
          <h2 className="analytics-page__title">Thống kê địa điểm</h2>
          <p className="analytics-page__description">
            Theo dõi lượt mở POI và lượt bấm nghe thuyết minh.
          </p>
        </div>
        <div className="analytics-page__controls">
          <div className="analytics-period" role="group" aria-label="Khoảng thời gian thống kê">
            {PERIODS.map((days) => (
              <button
                key={days}
                type="button"
                className={`analytics-period__button${period === days ? ' is-active' : ''}`}
                aria-pressed={period === days}
                onClick={() => {
                  setError('')
                  setLoading(true)
                  setPeriod(days)
                }}
              >
                {days} ngày
              </button>
            ))}
          </div>
          <button
            className="btn btn--secondary"
            type="button"
            disabled={loading}
            onClick={() => {
              setError('')
              setLoading(true)
              setRefreshKey((key) => key + 1)
            }}
          >
            {loading ? 'Đang cập nhật…' : 'Làm mới'}
          </button>
        </div>
      </header>

      <div className="analytics-page__notice">
        Số liệu chỉ bao gồm sự kiện từ khách đã cho phép thu thập analytics. Cập nhật lần cuối:{' '}
        {updatedAt?.toLocaleTimeString('vi-VN') ?? '—'}.
        {error && <span className="analytics-page__stale"> Không tải được lần cập nhật mới nhất.</span>}
      </div>

      <div className="analytics-kpis">
        <article className="analytics-kpi analytics-kpi--views">
          <span className="analytics-kpi__label">Lượt xem POI · {period} ngày</span>
          <strong className="analytics-kpi__value">{dinhDangSo(data.period_views)}</strong>
          <span className="analytics-kpi__detail">Hôm nay: {dinhDangSo(data.today_views)}</span>
        </article>
        <article className="analytics-kpi analytics-kpi--audio">
          <span className="analytics-kpi__label">Lượt bấm nghe · {period} ngày</span>
          <strong className="analytics-kpi__value">{dinhDangSo(data.period_audio_plays)}</strong>
          <span className="analytics-kpi__detail">Hôm nay: {dinhDangSo(data.today_audio_plays)}</span>
        </article>
        <article className="analytics-kpi analytics-kpi--online">
          <span className="analytics-kpi__label">Thiết bị online</span>
          <strong className="analytics-kpi__value">
            {data.tracked_online_users === null ? '—' : dinhDangSo(data.tracked_online_users)}
          </strong>
          <span className="analytics-kpi__detail">Có analytics bật, hoạt động trong 5 phút</span>
        </article>
      </div>

      <div className="analytics-panels">
        <article className="analytics-panel">
          <header className="analytics-panel__header">
            <div>
              <h3 className="analytics-panel__title">Xu hướng theo ngày</h3>
              <p className="analytics-panel__subtitle">
                {dinhDangNgay(data.period_start)} – {dinhDangNgay(data.metric_date)}
              </p>
            </div>
            <div className="analytics-legend" aria-label="Chú giải biểu đồ">
              <span><i className="analytics-legend__swatch analytics-legend__swatch--views" />Lượt xem</span>
              <span><i className="analytics-legend__swatch analytics-legend__swatch--audio" />Lượt nghe</span>
            </div>
          </header>

          <div className="analytics-chart" role="list" aria-label={`Lượt xem và lượt nghe theo ngày trong ${period} ngày`}>
            {data.daily.map((day) => (
              <div className="analytics-chart__row" key={day.metric_date} role="listitem">
                <time className="analytics-chart__date" dateTime={day.metric_date}>
                  {dinhDangNgay(day.metric_date)}
                </time>
                <div className="analytics-chart__bars">
                  <div className="analytics-chart__track">
                    <span
                      className="analytics-chart__bar analytics-chart__bar--views"
                      style={{ width: `${(day.views / maxDaily) * 100}%` }}
                    />
                  </div>
                  <span className="analytics-chart__count">{dinhDangSo(day.views)}</span>
                  <div className="analytics-chart__track">
                    <span
                      className="analytics-chart__bar analytics-chart__bar--audio"
                      style={{ width: `${(day.audio_plays / maxDaily) * 100}%` }}
                    />
                  </div>
                  <span className="analytics-chart__count">{dinhDangSo(day.audio_plays)}</span>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="analytics-panel">
          <header className="analytics-panel__header">
            <div>
              <h3 className="analytics-panel__title">POI được quan tâm nhất</h3>
              <p className="analytics-panel__subtitle">Xếp hạng theo tổng lượt xem và nghe trong {period} ngày</p>
            </div>
          </header>

          {data.top_pois.length === 0 ? (
            <div className="analytics-empty">
              <strong>Chưa có lượt tương tác</strong>
              <p>Khi khách mở POI hoặc bấm nghe và đã cho phép analytics, dữ liệu sẽ xuất hiện tại đây.</p>
            </div>
          ) : (
            <div className="analytics-ranking">
              {data.top_pois.map((poi, index) => (
                <div className="analytics-ranking__row" key={poi.poi_id}>
                  <span className="analytics-ranking__position">{String(index + 1).padStart(2, '0')}</span>
                  <div className="analytics-ranking__name">
                    <strong>{poi.name || poi.poi_id}</strong>
                    <span>{dinhDangSo(poi.views)} lượt xem · {dinhDangSo(poi.audio_plays)} lượt nghe</span>
                  </div>
                  <strong className="analytics-ranking__total">
                    {dinhDangSo(poi.views + poi.audio_plays)}
                  </strong>
                </div>
              ))}
            </div>
          )}
        </article>
      </div>

      <p className="analytics-page__footnote">
        Lượt xem được ghi khi khách chọn một POI. Lượt nghe được ghi mỗi khi khách bấm nút nghe.
      </p>
    </section>
  )
}
