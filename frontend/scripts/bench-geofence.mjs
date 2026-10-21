// PERF-005: đo CPU vòng geofence ngoài trình duyệt — chạy được lặp lại ở PERF-007.
//
// Chạy: `node scripts/bench-geofence.mjs` (Node >= 22.18 tự strip type, import
// trực tiếp engine.ts — đo code THẬT, không sao chép logic).
//
// Mô phỏng đúng nhịp thật của useGeofence:
//   - watchPosition bắn ~1 giây/lần → updatePosition bị throttle 5s nên 4/5
//     lần là early-return O(1);
//   - interval reconcile mỗi 5s → luôn chạy hết vòng quyetDinh.
// Đo trường hợp tệ nhất: đang đi bộ giữa hai quán → toàn bộ POI NGOÀI vòng,
// mỗi tick phải tính Haversine cho hết (case "trong vòng + cooldown" rẻ hơn
// nhiều vì `continue` sớm).

import { performance } from 'node:perf_hooks'
import { GeofenceEngine } from '../src/geofence/engine.ts'

const TRUNG_TAM = { lat: 10.76, lng: 106.76 }

/** POI trải đều quanh trung tâm Quận 4, bán kính 2-6km — vẫn "ngoài vòng" 30-50m. */
function taoPois(n) {
  return Array.from({ length: n }, (_, i) => {
    const goc = (i / n) * 2 * Math.PI
    const khoang = 0.01 + (i % 40) * 0.0012 // 0.01~0.058 độ ~ 1.1-6.4 km
    return {
      id: `poi-${i}`,
      lat: TRUNG_TAM.lat + Math.sin(goc) * khoang,
      lng: TRUNG_TAM.lng + Math.cos(goc) * khoang,
      trigger_radius: 30 + (i % 3) * 10,
      audio_priority: i % 100,
    }
  })
}

function doTick(n, soTick) {
  const engine = new GeofenceEngine()
  engine.setPois(taoPois(n))
  let demEnter = 0
  engine.onEnter = () => {
    demEnter += 1
  }
  // 2 tick đầu là warm-up (JIT), không tính.
  for (let i = 0; i < 2; i += 1) engine.reconcile(TRUNG_TAM.lat, TRUNG_TAM.lng)
  const truoc = performance.now()
  for (let i = 0; i < soTick; i += 1) {
    // Giả lập di chuyển nhẹ để không lọt vào nhánh early-return tình cờ.
    engine.reconcile(TRUNG_TAM.lat + (i % 100) * 1e-7, TRUNG_TAM.lng)
  }
  const tong = performance.now() - truoc
  return { msMoiTick: tong / soTick, demEnter }
}

/** 60 gi mô phỏng GPS 1/s thật sự: bao nhiêu lần bị throttle, tốn bao nhiêu. */
function doGPS60gi(n) {
  let gio = 0
  const nowGia = () => gio
  const engineGia = new GeofenceEngine({ now: nowGia })
  engineGia.setPois(taoPois(n))
  const truoc = performance.now()
  for (let gi = 0; gi < 60; gi += 1) {
    gio = gi * 1000
    engineGia.updatePosition(TRUNG_TAM.lat, TRUNG_TAM.lng)
    if (gi % 5 === 0) engineGia.reconcile(TRUNG_TAM.lat, TRUNG_TAM.lng)
  }
  return performance.now() - truoc
}

const SO_TICK = 20000
console.log(`Node ${process.version} | ${SO_TICK} tick/cao độ | engine.ts thật\n`)
console.log('POIs | ms/tick (trường hợp tệ nhất, toàn POI ngoài vòng) | 24 tick/phút chiếm CPU')
console.log('-----|--------------------------------------------------|----------------------')
for (const n of [3, 50, 200, 1000]) {
  const { msMoiTick, demEnter } = doTick(n, SO_TICK)
  const phanTram = ((msMoiTick * 24) / 60000) * 100
  console.log(`${String(n).padStart(4)} | ${msMoiTick.toFixed(4).padStart(26)} ms | ${phanTram.toFixed(4)} %`)
  if (demEnter > 0) console.log(`      (lưu ý: ${demEnter} lần onEnter trong lúc đo — đáng lẽ 0 với POI ngoài vòng)`)
}
console.log('\n60 gi mô phỏng GPS 1/s + reconcile 5s:')
for (const n of [50, 1000]) {
  console.log(`  ${n} POI: ${doGPS60gi(n).toFixed(2)} ms`)
}
