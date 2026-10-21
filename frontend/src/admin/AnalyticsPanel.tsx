import { useEffect, useState } from 'react'
import { api } from './api'

interface TongQuan {
  metric_date: string
  today_views: number
  audio_plays: number
  searches: number
  page_engaged: number
  devices_today: number
  sessions_today: number
  tracked_online_users: number | null
  presence_available: boolean
  top_pois: { poi_id: string; name: string; views: number; audio_plays: number }[]
  top_searches: { query: string; count: number }[]
  daily: { metric_date: string; views: number; audio_plays: number; searches: number }[]
}

interface CuaSoRuntime {
  window: string
  hours: number
  samples: number
  cells: number
  outcomes: Record<string, number>
}

const CUA_SO: { ma: '24h' | '7d'; ten: string }[] = [
  { ma: '24h', ten: '24 giờ' },
  { ma: '7d', ten: '7 ngày' },
]

function o(a?: number, b?: number): number {
  if (a === undefined || b === undefined || a === 0) return 0
  return Math.round((b / a) * 100)
}

// ADM-005: hai nhóm số liệu tách bạch có chủ đích — analytics chỉ có dữ liệu
// của thiết bị đã consent, còn cửa sổ runtime là chẩn đoán vận hành.
export default function AnalyticsPanel() {
  const [tq, setTQ] = useState<TongQuan | null>(null)
  const [cuaSo, setCuaSo] = useState<'24h' | '7d'>('24h')
  const [runtime, setRuntime] = useState<CuaSoRuntime | null>(null)
  const [loi, setLoi] = useState('')

  useEffect(() => {
    api<TongQuan>('/admin/analytics/summary')
      .then(setTQ)
      .catch(() => setLoi('Không xem được analytics (cần quyền analytics:view)'))
  }, [])

  useEffect(() => {
    api<CuaSoRuntime>(`/admin/runtime-observability/location?window=${cuaSo}`)
      .then(setRuntime)
      .catch(() => setRuntime(null))
  }, [cuaSo])

  if (loi !== '') return <div className="card notice notice--warn">{loi}</div>
  if (tq === null) {
    return (
      <div className="card">
        <div className="empty-state">
          <p className="muted">Đang tải dữ liệu phân tích hệ thống…</p>
        </div>
      </div>
    )
  }

  const lonNhat = Math.max(1, ...tq.daily.map((d) => d.views))

  return (
    <div className="analytics-container">
      {/* 1. Lưới chỉ số KPI Stat Cards */}
      <div className="stat-cards-grid">
        <div className="stat-card">
          <div className="stat-card__icon stat-card__icon--views">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
          <div className="stat-card__info">
            <strong className="stat-card__value">{tq.today_views}</strong>
            <span className="stat-card__label">Lượt xem hôm nay</span>
            <span className="stat-card__sub">{tq.metric_date}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card__icon stat-card__icon--audio">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
            </svg>
          </div>
          <div className="stat-card__info">
            <strong className="stat-card__value">{tq.audio_plays}</strong>
            <span className="stat-card__label">Lượt nghe audio</span>
            <span className="stat-card__sub">{o(tq.today_views, tq.audio_plays)}% tỷ lệ nghe</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card__icon stat-card__icon--devices">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <rect width="14" height="20" x="5" y="2" rx="2" ry="2" />
              <path d="M12 18h.01" />
            </svg>
          </div>
          <div className="stat-card__info">
            <strong className="stat-card__value">{tq.devices_today}</strong>
            <span className="stat-card__label">Thiết bị consent</span>
            <span className="stat-card__sub">{tq.sessions_today} phiên hôm nay</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card__icon stat-card__icon--online">
            <span className="status-indicator-dot" />
          </div>
          <div className="stat-card__info">
            <strong className="stat-card__value">
              {tq.presence_available && tq.tracked_online_users !== null ? tq.tracked_online_users : '0'}
            </strong>
            <span className="stat-card__label">Đang online</span>
            <span className="stat-card__sub">Cửa sổ 5 phút gần nhất</span>
          </div>
        </div>
      </div>

      {/* 2. Biểu đồ lượt xem 7 ngày */}
      <div className="card mt">
        <div className="section-header">
          <div>
            <h3 className="card__title">Xu hướng tương tác 7 ngày</h3>
            <p className="card__subtitle">So sánh lượt xem trang theo từng ngày</p>
          </div>
        </div>

        {tq.daily.length === 0 ? (
          <div className="empty-state">
            <p className="muted">Chưa có dữ liệu thống kê ngày.</p>
          </div>
        ) : (
          <div className="chart-bar-list mt">
            {tq.daily.map((d) => (
              <div key={d.metric_date} className="chart-bar-row">
                <span className="chart-bar-date">{d.metric_date.slice(5)}</span>
                <div className="chart-bar-track">
                  <div
                    className="chart-bar-fill"
                    style={{ width: `${Math.max(4, (d.views / lonNhat) * 100)}%` }}
                    title={`${d.views} lượt xem`}
                  />
                </div>
                <span className="chart-bar-value">{d.views}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Top quán được xem & nghe nhiều nhất */}
      <div className="card mt">
        <div className="section-header">
          <div>
            <h3 className="card__title">Địa điểm ẩm thực thu hút nhất</h3>
            <p className="card__subtitle">Xếp hạng quán có lượt quan tâm cao</p>
          </div>
        </div>

        {tq.top_pois.length === 0 ? (
          <div className="empty-state">
            <p className="muted">Chưa có dữ liệu tương tác quán ăn.</p>
          </div>
        ) : (
          <div className="table-responsive mt">
            <table className="table">
              <thead>
                <tr>
                  <th>Tên điểm quán</th>
                  <th style={{ textAlign: 'right' }}>Lượt xem</th>
                  <th style={{ textAlign: 'right' }}>Lượt nghe</th>
                  <th style={{ textAlign: 'right' }}>Tỷ lệ nghe</th>
                </tr>
              </thead>
              <tbody>
                {tq.top_pois.map((p, idx) => (
                  <tr key={p.poi_id}>
                    <td>
                      <span className="rank-badge">#{idx + 1}</span>
                      <strong>{p.name || p.poi_id}</strong>
                    </td>
                    <td style={{ textAlign: 'right' }}>{p.views}</td>
                    <td style={{ textAlign: 'right' }}>{p.audio_plays}</td>
                    <td style={{ textAlign: 'right' }}>
                      <span className="badge badge--ok">{o(p.views, p.audio_plays)}%</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4. Từ khóa tìm kiếm */}
      {tq.top_searches.length > 0 && (
        <div className="card mt">
          <h3 className="card__title">Từ khoá được tìm nhiều</h3>
          <div className="tags-cloud mt">
            {tq.top_searches.map((s) => (
              <span key={s.query} className="tag-pill">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'inline', marginRight: 4 }}>
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                {s.query} <strong className="tag-count">({s.count})</strong>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 5. Quan sát vị trí runtime */}
      <div className="card mt">
        <div className="spread">
          <div>
            <h3 className="card__title">Quan sát vị trí Runtime (Telemetry)</h3>
            <p className="card__subtitle">Chẩn đoán kỹ thuật vùng quét GPS</p>
          </div>
          <div className="segmented-control">
            {CUA_SO.map((c) => (
              <button
                key={c.ma}
                type="button"
                className={`segmented-btn${c.ma === cuaSo ? ' segmented-btn--active' : ''}`}
                onClick={() => setCuaSo(c.ma)}
              >
                {c.ten}
              </button>
            ))}
          </div>
        </div>

        {runtime && (
          <div className="runtime-metrics mt">
            <div className="row" style={{ gap: 12 }}>
              <div className="runtime-metric-badge">
                Mẫu nhận diện: <strong>{runtime.samples}</strong>
              </div>
              <div className="runtime-metric-badge">
                Ô lưới không gian: <strong>{runtime.cells}</strong>
              </div>
            </div>

            <div className="table-responsive mt">
              <table className="table table--compact">
                <thead>
                  <tr>
                    <th>Kết quả quét</th>
                    <th style={{ textAlign: 'right' }}>Số lượng</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(runtime.outcomes).map(([ketQua, dem]) => (
                    <tr key={ketQua}>
                      <td><code>{ketQua}</code></td>
                      <td style={{ textAlign: 'right' }}><strong>{dem}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
