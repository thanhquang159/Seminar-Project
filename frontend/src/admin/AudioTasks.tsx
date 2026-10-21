import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../config'
import { api, apiText } from './api'

interface Task {
  task_id: string
  poi_id: string
  lang: string
  status: string
  progress: number
}

export default function AudioTasks() {
  const [tasks, setTasks] = useState<Task[]>([])

  const tai = async () => {
    try {
      const danhSach = await api<Task[]>('/audio/tasks')
      setTasks(danhSach)
    } catch {
      // Bỏ qua lỗi
    }
  }

  useEffect(() => {
    api<Task[]>('/audio/tasks')
      .then(setTasks)
      .catch(() => {})
    const nguon = new EventSource(`${API_BASE_URL}/audio/tasks/stream`, { withCredentials: true })
    nguon.onmessage = () => void tai()
    nguon.onerror = () => nguon.close()
    return () => nguon.close()
  }, [])

  const lenh = async (id: string, l: string) => {
    await apiText(`/audio/tasks/${id}/${l}`, { method: 'POST' })
    await tai()
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
                    <strong className="audio-task-title">{t.poi_id}</strong>
                    <div className="row" style={{ gap: 6, marginTop: 4 }}>
                      <span className="badge badge--neutral">Ngôn ngữ: {t.lang.toUpperCase()}</span>
                      <span className={`badge badge--${t.status === 'done' ? 'ok' : t.status === 'error' ? 'error' : 'warn'}`}>
                        {t.status === 'done' ? 'Hoàn tất' : t.status === 'error' ? 'Lỗi' : 'Đang xử lý'} · {t.progress}%
                      </span>
                    </div>
                  </div>
                </div>

                <div className="row" style={{ gap: 6 }}>
                  <button
                    className="btn btn--sm btn--secondary"
                    type="button"
                    onClick={() => void lenh(t.task_id, 'pause')}
                  >
                    Tạm dừng
                  </button>
                  <button
                    className="btn btn--sm btn--secondary"
                    type="button"
                    onClick={() => void lenh(t.task_id, 'resume')}
                  >
                    Tiếp tục
                  </button>
                  <button
                    className="btn btn--sm btn--danger"
                    type="button"
                    onClick={() => void lenh(t.task_id, 'cancel')}
                  >
                    Hủy bỏ
                  </button>
                </div>
              </div>

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
