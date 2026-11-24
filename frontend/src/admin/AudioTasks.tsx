import { useCallback, useEffect, useState } from 'react'
import { API_BASE_URL } from '../config'
import { api, apiText } from './api'

interface Task {
  task_id: string
  poi_id: string
  poi_name?: string
  lang: string
  status: string
  progress: number
  loi?: string | null
  is_latest?: boolean
}

const STATUS_LABELS: Record<string, string> = {
  queued: 'Chờ chạy', running: 'Đang tạo audio', paused: 'Đã tạm dừng',
  done: 'Hoàn tất', error: 'Tạo thất bại', canceled: 'Đã hủy',
}

export default function AudioTasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  const tai = useCallback(async () => {
    try {
      const danhSach = await api<Task[]>('/audio/tasks')
      setTasks(danhSach)
    } catch {
      setError('Không tải được tác vụ audio. Kiểm tra kết nối và quyền quản lý audio.')
    }
  }, [])

  useEffect(() => {
    api<Task[]>('/audio/tasks')
      .then(setTasks)
      .catch(() => setError('Không tải được tác vụ audio. Kiểm tra kết nối và quyền quản lý audio.'))
    const nguon = new EventSource(`${API_BASE_URL}/audio/tasks/stream`, { withCredentials: true })
    nguon.onmessage = () => void tai()
    // EventSource tự nối lại; polling vẫn cập nhật khi proxy ngắt SSE.
    const timer = window.setInterval(() => void tai(), 5000)
    return () => {
      nguon.close()
      window.clearInterval(timer)
    }
  }, [tai])

  const lenh = async (id: string, l: string) => {
    if (busy) return
    setBusy(id)
    setError('')
    try {
      const response = await apiText(`/audio/tasks/${id}/${l}`, { method: 'POST' })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        setError(typeof body?.detail === 'string' ? body.detail : 'Không điều khiển được tác vụ. Vui lòng tải lại.')
      }
      await tai()
    } catch {
      setError('Không kết nối được máy chủ. Vui lòng thử lại.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="card">
      <div className="section-header">
        <div>
          <h3 className="card__title">Tiến trình sinh thuyết minh âm thanh</h3>
          <p className="card__subtitle">Quản lý các tác vụ Text-To-Speech (TTS) đang chạy ngầm trên máy chủ</p>
        </div>
        <span className="badge badge--neutral">{tasks.length} tác vụ</span>
      </div>
      <p className="muted">Chờ chạy: bấm Bắt đầu nếu cần. Tạm dừng: bấm Tiếp tục. Tạo thất bại: đọc lỗi và bấm Thử lại. POI đã xóa không chạy audio.</p>
      <button className="btn btn--sm btn--secondary" type="button" onClick={() => void tai()}>Tải lại tác vụ</button>
      {error && <p role="alert" className="notice notice--error">{error}</p>}

      {tasks.length === 0 ? (
        <div className="empty-state">
          <p className="muted">Hiện không có tác vụ âm thanh nào đang xử lý.</p>
        </div>
      ) : (
        <ul className="audio-task-list mt">
          {tasks.map((t) => (
            <li key={t.task_id} className="audio-task-item">
              <div className="spread">
                <div className="audio-task-meta">
                  <div className="audio-task-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                      <line x1="12" y1="19" x2="12" y2="22" />
                    </svg>
                  </div>
                  <div>
                    <strong className="audio-task-title">{t.poi_name || t.poi_id}</strong>
                    <div className="row" style={{ gap: 6, marginTop: 4 }}>
                      <span className="badge badge--neutral">Ngôn ngữ: {t.lang.toUpperCase()}</span>
                      <span className={`badge badge--${t.status === 'done' ? 'ok' : t.status === 'error' ? 'error' : 'warn'}`}>
                        {STATUS_LABELS[t.status] ?? t.status} · {t.progress}%
                      </span>
                    </div>
                  </div>
                </div>

                <div className="row" style={{ gap: 6 }}>
                  {(t.status === 'queued' || t.status === 'running') && <button
                    className="btn btn--sm btn--secondary"
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void lenh(t.task_id, 'pause')}
                  >
                    Tạm dừng
                  </button>}
                  {(t.status === 'paused' || t.status === 'queued') && <button
                    className="btn btn--sm btn--secondary"
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void lenh(t.task_id, 'resume')}
                  >
                    {t.status === 'queued' ? 'Bắt đầu' : 'Tiếp tục'}
                  </button>}
                  {t.is_latest !== false && (t.status === 'error' || t.status === 'canceled') && <button
                    className="btn btn--sm btn--primary" type="button" disabled={busy !== null}
                    onClick={() => void lenh(t.task_id, 'retry')}>Thử lại</button>}
                  {['queued', 'running', 'paused'].includes(t.status) && <button
                    className="btn btn--sm btn--danger"
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void lenh(t.task_id, 'cancel')}
                  >
                    Hủy bỏ
                  </button>}
                </div>
              </div>
              {t.loi && <p className={`notice ${t.status === 'error' ? 'notice--error' : 'notice--info'}`}>{t.loi}</p>}

              <div className="progress mt">
                <div
                  className={`progress__bar${t.status === 'done' ? ' progress__bar--success' : ''}`}
                  style={{ width: `${t.progress}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
