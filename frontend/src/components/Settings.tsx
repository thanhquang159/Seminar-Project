import { useState } from 'react'
import { NGON_NGU, usePoiStore } from '../stores/poiStore'
import { useConsentStore } from '../stores/consentStore'
import { xinDongY, thuHoiDongY } from '../analytics/service'
import { type PackHook, type CheDo } from './useMapPack'

const MA_NGON_NGU: Record<string, string> = {
  vi: 'VI',
  en: 'EN',
  zh: 'ZH',
  ja: 'JA',
  ko: 'KO',
}

interface SettingsProps {
  pack?: PackHook
}

export default function Settings({ pack }: SettingsProps) {
  const { lang, setLang } = usePoiStore()
  const trangThaiConsent = useConsentStore((s) => s.trangThai)
  const [dangCapNhatConsent, setDangCapNhatConsent] = useState(false)

  const cheDoBanDo = pack ? pack.cheDo : (localStorage.getItem('quan4-mapmode') as CheDo) ?? 'hybrid'

  const doiBanDo = (c: CheDo) => {
    localStorage.setItem('quan4-mapmode', c)
    if (pack) {
      pack.setCheDo(c)
    }
  }

  const doiRiengTu = async (muc: 'granted' | 'revoked') => {
    setDangCapNhatConsent(true)
    try {
      if (muc === 'granted') {
        await xinDongY()
      } else {
        await thuHoiDongY()
      }
    } finally {
      setDangCapNhatConsent(false)
    }
  }

  return (
    <div className="settings-container">
      <div className="section-header">
        <div>
          <h2 className="section-title">Cài đặt Ứng dụng</h2>
          <p className="card__subtitle">Tùy chỉnh ngôn ngữ hiển thị, phương thức tải bản đồ và quyền riêng tư</p>
        </div>
      </div>

      {/* 1. Ngôn ngữ nội dung */}
      <div className="card mt">
        <h3 className="card__title">Ngôn ngữ thuyết minh & Hiển thị</h3>
        <p className="card__subtitle">Ứng dụng sẽ đồng bộ bản dịch và âm thanh theo ngôn ngữ bạn chọn</p>

        <div className="settings-pill-group mt">
          {NGON_NGU.map((n) => {
            const isSelected = n.ma === lang
            return (
              <button
                key={n.ma}
                type="button"
                className={`settings-pill${isSelected ? ' settings-pill--active' : ''}`}
                disabled={isSelected}
                onClick={() => setLang(n.ma)}
              >
                <span className="settings-pill__code">
                  {MA_NGON_NGU[n.ma] || n.ma.toUpperCase()}
                </span>
                <span>{n.ten}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* 2. Chế độ bản đồ */}
      <div className="card mt">
        <h3 className="card__title">Cấu hình bản đồ số</h3>
        <p className="card__subtitle">
          Chế độ hiện tại: <strong>{cheDoBanDo.toUpperCase()}</strong>
          {pack?.trangThai && ` · ${pack.trangThai}`}
        </p>

        <div className="settings-pill-group mt">
          {([
            { ma: 'cloud', ten: 'Cloud Trực tuyến', desc: 'Dùng MapTiler Cloud' },
            { ma: 'hybrid', ten: 'Lai (Hybrid)', desc: 'Tự động chuyển khi mất mạng' },
            { ma: 'offline', ten: 'Ngoại tuyến (Offline)', desc: 'Chỉ dùng gói tải sẵn' },
          ] as const).map((c) => {
            const isSelected = c.ma === cheDoBanDo
            return (
              <button
                key={c.ma}
                type="button"
                className={`settings-pill${isSelected ? ' settings-pill--active' : ''}`}
                disabled={isSelected}
                onClick={() => doiBanDo(c.ma)}
              >
                <span>{c.ten}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* 3. Chính sách quyền riêng tư */}
      <div className="card mt">
        <h3 className="card__title">Chính sách Riêng tư & Đo lường</h3>
        <p className="card__subtitle">
          Mức độ hiện tại:{' '}
          <strong>
            {trangThaiConsent === 'granted'
              ? 'Tiêu chuẩn ẩn danh (Đang chia sẻ)'
              : trangThaiConsent === 'revoked'
              ? 'Chặn hoàn toàn (Không chia sẻ)'
              : 'Chưa thiết lập'}
          </strong>
        </p>

        <div className="settings-pill-group mt">
          {[
            { ma: 'granted', ten: 'Tiêu chuẩn (Góp phần cải thiện chất lượng)' },
            { ma: 'revoked', ten: 'Chặn hoàn toàn (Không chia sẻ)' },
          ].map((m) => {
            const isSelected = m.ma === trangThaiConsent
            return (
              <button
                key={m.ma}
                type="button"
                className={`settings-pill${isSelected ? ' settings-pill--active' : ''}`}
                disabled={isSelected || dangCapNhatConsent}
                onClick={() => void doiRiengTu(m.ma as 'granted' | 'revoked')}
              >
                <span>{m.ten}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
