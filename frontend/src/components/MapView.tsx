import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Poi } from '../stores/poiStore'

// Tâm Quận 4, khu Vĩnh Khánh ăn uống.
const TAM_Q4: [number, number] = [106.7641, 10.7569]
const STYLE_MIEN_PHI = 'https://demotiles.maplibre.org/style.json'

interface Props {
  pois: Poi[]
  selectedId: string | null
  onSelect: (id: string) => void
  // Style pack offline thắng style cloud khi có.
  stylePack?: maplibregl.StyleSpecification | null
}

// Lời hướng dẫn theo từng lỗi định vị của trình duyệt.
function loiDinhVi(code?: number): string {
  if (code === 1) return 'Bạn đã chặn quyền truy cập vị trí. Bật lại quyền vị trí trong trình duyệt để hiển thị chấm xanh.'
  if (code === 2) return 'Tín hiệu GPS chưa ổn định. Bản đồ vẫn tương tác bình thường.'
  if (code === 3) return 'Hết thời gian chờ phản hồi GPS. Bản đồ vẫn sử dụng tốt.'
  return ''
}

function MapIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ display: 'inline-block', verticalAlign: 'text-bottom', marginRight: '4px' }}>
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  )
}

export default function MapView({ pois, selectedId, onSelect, stylePack }: Props) {
  const khungRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [thongBaoViTri, setThongBaoViTri] = useState('')
  const [dungCloud, setDungCloud] = useState(false)

  // MAP-001 + MAP-006: dựng bản đồ một lần, pack tới sau thì effect dưới đổi style.
  const styleLanDau = useRef(stylePack)
  useEffect(() => {
    if (khungRef.current === null || mapRef.current !== null) return
    const key = import.meta.env.VITE_MAPTILER_KEY as string | undefined
    const style = key !== undefined && key !== '' ? `https://api.maptiler.com/maps/streets-v2/style.json?key=${key}` : STYLE_MIEN_PHI
    setDungCloud(style !== STYLE_MIEN_PHI)
    const map = new maplibregl.Map({
      container: khungRef.current,
      style: styleLanDau.current ?? style,
      center: TAM_Q4,
      zoom: 14.5,
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Pack offline cài sau thì đổi style khi có, markers giữ nguyên.
  useEffect(() => {
    if (mapRef.current !== null && stylePack !== undefined && stylePack !== null) {
      mapRef.current.setStyle(stylePack)
    }
  }, [stylePack])

  // MAP-002: một marker cho mỗi POI, chú ý thứ tự [lng, lat]. Dọn khi pois đổi.
  useEffect(() => {
    const map = mapRef.current
    if (map === null) return
    const markers: maplibregl.Marker[] = []
    for (const poi of pois) {
      const isSelected = poi.id === selectedId
      const marker = new maplibregl.Marker({
        color: isSelected ? '#ea580c' : '#0f766e',
      })
        .setLngLat([poi.lng, poi.lat])
        .addTo(map)
      // MAP-003: bấm marker thì báo id về App để mở panel.
      marker.getElement().addEventListener('click', () => onSelect(poi.id))
      markers.push(marker)
    }
    return () => {
      for (const m of markers) m.remove()
    }
  }, [pois, selectedId, onSelect])

  // MAP-004 + MAP-005: chấm xanh vị trí user, xử lý 3 lỗi mà bản đồ vẫn dùng được.
  useEffect(() => {
    if (!('geolocation' in navigator)) {
      queueMicrotask(() => setThongBaoViTri('Thiết bị không hỗ trợ định vị vị trí. Bản đồ vẫn xem bình thường.'))
      return
    }
    let cham: maplibregl.Marker | null = null
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const map = mapRef.current
        if (map === null) return
        setThongBaoViTri('')
        if (cham === null) {
          const el = document.createElement('div')
          el.className = 'user-location-pulse'
          cham = new maplibregl.Marker({ element: el }).setLngLat([pos.coords.longitude, pos.coords.latitude]).addTo(map)
        } else {
          cham.setLngLat([pos.coords.longitude, pos.coords.latitude])
        }
      },
      (err) => setThongBaoViTri(loiDinhVi(err.code)),
      { enableHighAccuracy: true, timeout: 8000 },
    )
    return () => {
      navigator.geolocation.clearWatch(id)
      cham?.remove()
    }
  }, [])

  return (
    <div className="map-view-card">
      <div className="map-frame">
        <div ref={khungRef} className="map-canvas" />
      </div>

      <div className="map-footer-bar">
        <span className="map-hint">
          <MapIcon />
          {dungCloud ? 'Bản đồ số MapTiler Cloud' : 'Bản đồ số OpenStreetMap (Quận 4)'}
        </span>
        <span className="badge badge--neutral" style={{ fontSize: '0.78rem' }}>
          Tâm: Phố Ẩm thực Vĩnh Khánh
        </span>
      </div>

      {thongBaoViTri !== '' && <div className="notice notice--warn mt">{thongBaoViTri}</div>}
    </div>
  )
}
