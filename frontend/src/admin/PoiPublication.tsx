import { useState } from 'react'
import { apiText } from './api'
import { navigateToPath } from './portalRoutes'

export interface PublicationReadiness {
  ready: boolean
  review_approved?: boolean
  english_ready: boolean
  audio_ready: boolean
  audio_status: string
  reasons: string[]
}

interface Props {
  poi: {
    id: string
    publication_status: string
    is_active: boolean
    readiness?: PublicationReadiness
  }
  canPublish: boolean
  onChanged: () => Promise<void>
}

function publicationLabel(status: string, active: boolean): string {
  if (status === 'published' && active) return 'Đang công khai'
  if (status === 'unpublished') return 'Chưa công khai'
  if (status === 'pending_review') return 'Chờ công khai · cần kiểm tra duyệt'
  if (status === 'draft') return 'Bản nháp'
  if (status === 'archived') return 'Đã lưu trữ'
  if (status === 'rejected') return 'Đã từ chối'
  return 'Chưa công khai'
}

export default function PoiPublication({ poi, canPublish, onChanged }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const published = poi.publication_status === 'published' && poi.is_active

  const changePublication = async () => {
    if (busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await apiText(`/admin/pois/${poi.id}/${published ? 'unpublish' : 'publish'}`, { method: 'POST' })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const detail = body?.detail
        setError(typeof detail === 'string' ? detail : detail?.readiness?.reasons?.join(' ') || 'Không thể đổi trạng thái công khai. Vui lòng thử lại.')
        await onChanged()
        return
      }
      setNotice(published ? 'Đã ẩn POI khỏi bản đồ công khai.' : 'Đã công khai POI trên bản đồ.')
      await onChanged()
    } catch {
      setError('Không kết nối được máy chủ. Vui lòng thử lại.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="poi-publication">
      <span className={`badge badge--${published ? 'ok' : 'warn'}`}>
        {poi.publication_status === 'pending_review' && poi.readiness?.review_approved
          ? 'Đã duyệt · chờ công khai'
          : publicationLabel(poi.publication_status, poi.is_active)}
      </span>
      {poi.readiness && (
        <div className="muted mt-xs">
          English: {poi.readiness.english_ready ? 'Sẵn sàng' : 'Cần bổ sung / kiểm tra'} · Audio EN: {poi.readiness.audio_ready ? 'Sẵn sàng' : ({ queued: 'Chờ chạy', processing: 'Đang tạo', failed: 'Tạo thất bại', not_generated: 'Chưa tạo', unavailable: 'Chưa khả dụng' }[poi.readiness.audio_status] ?? poi.readiness.audio_status)}
          {!published && poi.readiness.reasons.map((reason) => <p key={reason}>{reason}</p>)}
        </div>
      )}
      <div className="row mt-xs">
        {canPublish && (
          <button className={`btn btn--sm ${published ? 'btn--secondary' : 'btn--primary'}`}
            type="button" disabled={busy || (!published && !poi.readiness?.ready)}
            onClick={() => void changePublication()}>
            {busy ? 'Đang xử lý…' : published ? 'Ẩn khỏi công khai' : 'Công khai'}
          </button>
        )}
        {!published && (
          <button className="btn btn--sm btn--secondary" type="button" disabled={busy}
            onClick={() => navigateToPath(`/admin/translations?poi=${encodeURIComponent(poi.id)}&lang=en`)}>
            Chuẩn bị English + Audio
          </button>
        )}
        {!poi.readiness?.audio_ready && <button className="btn btn--sm btn--secondary" type="button"
          onClick={() => navigateToPath('/admin/audio')}>Xem tác vụ audio</button>}
        <button className="btn btn--sm btn--secondary" type="button" disabled={busy}
          onClick={() => void onChanged()}>Kiểm tra lại</button>
      </div>
      {!canPublish && <p className="muted">Cần quyền công khai POI để đổi trạng thái.</p>}
      {error && <p role="alert" className="notice notice--error">{error}</p>}
      {notice && <p role="status" className="notice notice--ok">{notice}</p>}
    </div>
  )
}
