import type { Poi } from '../stores/poiStore'

// OWN-005: tên quán và mô tả là dữ liệu chủ quán gửi lên — tức là nội dung
// không đáng tin. Ở đây chỉ đặt chúng vào vị trí text của JSX (React escape sẵn),
// tuyệt đối không đưa vào HTML dạng thô. `PoiList.test.tsx` kiểm đúng điều đó.

interface DanhSachProps {
  pois: Poi[]
  onChon: (id: string) => void
}

export function PoiList({ pois, onChon }: DanhSachProps) {
  return (
    <ul className="poi-list">
      {pois.map((poi) => (
        <li key={poi.id} className="poi-item">
          <button type="button" className="poi-btn" onClick={() => onChon(poi.id)}>
            <span className="poi-btn__name">{poi.name}</span>
            <span className="poi-btn__arrow">›</span>
            <span className="poi-btn__desc">{poi.description}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

interface ChiTietProps {
  poi: Poi
  onNghe: (id: string) => void
}

export function PoiDetail({ poi, onNghe }: ChiTietProps) {
  return (
    <section className="card" aria-label="Chi tiết điểm tham quan">
      <div className="spread">
        <h2 className="card__title">{poi.name}</h2>
        {poi.is_fallback && <span className="badge badge--warn">Nội dung thay thế</span>}
      </div>
      <p className="card__subtitle">{poi.description}</p>
      <button className="btn btn--accent" type="button" onClick={() => onNghe(poi.id)}>
        ▶ Nghe thuyết minh
      </button>
    </section>
  )
}