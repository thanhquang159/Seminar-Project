# 05 — System Architecture (Kiến trúc hệ thống)

> Sơ đồ được thay bằng mô tả lời theo từng tầng và từng luồng dữ liệu.

## 1. Tổng quan

Hệ thống là **modular monolith** ở phía backend và **PWA offline-first** ở phía frontend.

Hình dung theo chiều từ người dùng vào trong:

1. **Trình duyệt/PWA của người dùng** chạy ứng dụng React. Giữa ứng dụng và mạng có **Service Worker** làm lớp chặn yêu cầu và cache. Dữ liệu lâu dài nằm trong **IndexedDB** và **Cache API**.
2. Yêu cầu đi qua mạng tới **một tiến trình backend FastAPI** duy nhất, trong đó mười router chia ranh giới theo nghiệp vụ.
3. Backend dùng **PostgreSQL/PostGIS** cho dữ liệu nghiệp vụ và truy vấn không gian; tệp audio, ảnh, bản đồ nằm trong kho tĩnh/runtime, có thể thay bằng kho tương thích S3.
4. Backend gọi ra **dịch vụ ngoài** khi cần: Edge-TTS, Google Translate (qua deep-translator), Gemini/ProxyPal, MapTiler, OpenWeather (tùy chọn).

## 2. Các thành phần

### 2.1 Frontend (PWA)

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Khung UI | React 19.2, React Router (catch-all) | Hiển thị màn hình, định tuyến |
| Build | Vite 7 + plugin PWA, Workbox `injectManifest` | Đóng gói, sinh Service Worker |
| State | Zustand (ví dụ `poiStore`) | Lưu trạng thái ứng dụng |
| Bản đồ | MapLibre GL JS, giao thức `pmtiles://` | Hiển thị vector map cloud/offline |
| Địa lý | Turf.js | Tính khoảng cách cho geofence |
| Offline | Service Worker, `idb` (IndexedDB), Cache API | 4 lớp phòng thủ offline |

Các module logic chính trong frontend:

- **LocationService**: theo dõi vị trí liên tục, throttle 5 giây, hàm lấy vị trí tốt nhất có thể.
- **GeofenceEngine**: phát hiện vào/ra vùng POI, debounce 3 giây, cooldown 5 phút, vòng reconcile 5 giây.
- **NarrationEngine + AudioQueueManager**: hàng đợi một ô, phát có fallback 4 tầng.
- **useGeofence**: gắn geofence vào React, điều phối prefetch nền.
- **LanguageHotsetService**: chuẩn bị hotset theo ngôn ngữ (10 POI, 1,5 km, 3 POI bắt buộc).
- **Startup coordinator và startupNetworkProbe**: tách trạng thái sẵn sàng giữa nội dung và UI bundle; thăm dò mạng.
- **AudioPackService, MapPackService**: tải, xác thực, kích hoạt gói offline.
- **mapConfig**: chọn chế độ bản đồ Cloud, Offline hoặc Hybrid.
- **db.js**: truy cập IndexedDB `Quan4DB v2`.

### 2.2 Backend (FastAPI)

Công nghệ: FastAPI (async), SQLAlchemy async, asyncpg, PostgreSQL/PostGIS, PyJWT (HS256), bcrypt, cryptography (Fernet), Edge-TTS, deep-translator, SDK Gemini hoặc cổng ProxyPal.

Mười router được mount:

| Router | Trách nhiệm |
|---|---|
| content | CRUD POI, đồng bộ delta, nearby, hydrate bản địa hóa, cổng kích hoạt, menu |
| audio | Edge-TTS, GoogleTranslator, task manager, danh sách giọng, pack manifest, SSE tác vụ |
| admin | Xác thực cookie, RBAC, người dùng, role, duyệt đăng ký/submission, audit log |
| owner | Cổng chủ quán: POI của mình, submission, thông báo, trạng thái đăng ký |
| ai_advisor | Cải thiện mô tả bằng AI, quota theo ngày |
| analytics | API thu thập có consent và tổng hợp số liệu từ PostgreSQL |
| localization | On-demand, hotset, warmup, cổng "sẵn sàng tiếng Anh công khai" |
| maps | Manifest tĩnh-first, PMTiles, glyph, sprite, chống path traversal |
| runtime_observability | Ingest vị trí công khai (tách riêng), rate limit, cửa sổ quan sát cho admin |
| ui_i18n | UI bundle theo locale, `source_hash`, trạng thái pending/ready, dịch long-tail |

Ngoài ra: `/static` (tệp tĩnh), `/health`, `/health/ready`.

Mỗi domain tổ chức theo mẫu **router → service → store**, dùng chung tiến trình và PostgreSQL qua `AsyncSession`, nhưng ranh giới rõ ràng.

### 2.3 Cơ sở dữ liệu và lưu trữ

- **PostgreSQL/PostGIS**: kho dữ liệu nghiệp vụ và truy vấn không gian (chi tiết ở `06_Database_Design.md`). Backend kết nối qua SQLAlchemy async/asyncpg; schema phải được provision trước, ứng dụng không tự tạo schema.
- **Trạng thái tạm thời**: tác vụ và dữ liệu cần bền được lưu trong PostgreSQL; một số giới hạn tần suất/đếm tạm thời nằm trong tiến trình.
- **Kho media/runtime**: thư mục tĩnh chứa audio MP3, ảnh, gói bản đồ (`backend/app/static/maps/`, đổi bằng biến môi trường `MAP_PACK_DATA_DIR`). Có thể dùng backend tương thích S3, khi đó khi khởi động có kiểm tra sức khỏe kho (`media_storage.check_backend_health()`).

### 2.4 Dịch vụ ngoài

Xem `10_External_Services.md`.

## 3. Trình tự khởi động backend (theo tầng)

1. **Kiểm tra bí mật:** `kiem_tra_bi_mat()` xác thực `JWT_SECRET` và `REFRESH_TOKEN_SECRET` theo môi trường; cấu hình không hợp lệ làm startup thất bại.
2. **Kết nối cơ sở dữ liệu:** `connect_db()` mở kết nối PostgreSQL và xác nhận `DB_NAME`; ứng dụng dừng khởi động nếu kết nối lỗi hoặc tên database không khớp.
3. **Phục vụ yêu cầu:** router dùng `AsyncSession` lấy từ `app.postgres.get_db`; schema PostgreSQL phải có sẵn trước khi chạy.
4. **Đóng kết nối:** khi ứng dụng dừng, `close_db()` giải phóng connection pool.

## 4. Luồng dữ liệu chính (mô tả bằng lời)

### 4.1 Mở app và tải dữ liệu
Trình duyệt tải trang, Service Worker được đăng ký. Giao diện đọc ngay snapshot từ IndexedDB để hiển thị. Cùng lúc, frontend gọi `GET /poi/load-all` kèm ETag; backend so khớp phiên bản dataset, trả đầy đủ hoặc chỉ phần thay đổi và danh sách POI bị xóa. Frontend ghi lại vào IndexedDB. Service Worker cache phản hồi này theo chiến lược NetworkFirst (chờ mạng 8 giây, TTL 15 phút).

### 4.2 Thuyết minh theo vị trí
Dịch vụ vị trí đẩy tọa độ mỗi 5 giây vào bộ máy geofence. Bộ máy xác nhận ENTER, chọn POI tốt nhất, chuyển cho bộ phát. Bộ phát hỏi Service Worker audio đã có sẵn chưa; nếu chưa, gọi backend on-demand, rồi TTS stream, rồi cuối cùng dùng giọng của thiết bị.

### 4.3 Sinh audio phía backend
Khi admin lưu POI, backend cập nhật dữ liệu trong PostgreSQL. Trình quản lý tác vụ audio dịch văn bản, kiểm tra cache MD5 trên đĩa, gọi Edge-TTS khi cần, lưu MP3 và cập nhật bản địa hóa cùng trạng thái tác vụ trong các bảng PostgreSQL. Tiến độ được đẩy qua SSE; trạng thái tác vụ có thể được nạp lại từ PostgreSQL sau khi backend khởi động lại.

### 4.4 Gói offline
Frontend gọi manifest (audio, map) để biết danh sách tệp, kích thước và SHA-256. Map được tải vào cache phiên bản riêng, xác minh hash và cấu trúc PMTiles/style trước khi cập nhật chỉ mục pack đang hoạt động. Pack hiện tại được giữ nguyên nếu tải mới lỗi. Bộ đọc PMTiles dùng nguồn tùy biến để đọc các range từ Cache API, kể cả khi API khác origin với PWA.

### 4.5 Duyệt nội dung chủ quán
Chủ quán gửi submission vào `poi_submissions`; admin duyệt; hệ thống cập nhật `poi`, tăng phiên bản dataset, xếp việc sinh audio, tạo `owner_notifications`. Thiết bị của du khách thấy thay đổi ở lần đồng bộ delta kế tiếp.

## 5. Chiến lược cache và offline (4 lớp)

1. **Service Worker (Workbox):** POI NetworkFirst; audio CacheFirst theo từng ngôn ngữ; ảnh và chunk tùy chọn CacheFirst. Map pack do trình quản lý pack sở hữu riêng, không bị cache trùng qua Workbox.
2. **Phân mảnh ngôn ngữ và đồng bộ build:** mỗi ngôn ngữ một cache, tối đa 300 tệp, tối đa 3 ngôn ngữ, LRU, ghim ngôn ngữ đang dùng; xóa chunk cũ khi build đổi.
3. **IndexedDB:** `pois_by_lang` và UI bundle; thứ tự dự phòng chọn, en, vi.
4. **Offline Pack:** bản đồ, POI, ảnh, audio; cài tuần tự, kiểm tra SHA-256, cache tách biệt. Khi hết quota, chỉ xóa phần tải dở và giữ pack đang hoạt động cùng cache ứng dụng.

Thông điệp giữa frontend và Service Worker: `SET_ACTIVE_LANGUAGE`, `APP_BUILD_SYNC`, `AUDIO_PACK_ACTIVATE`, `AUDIO_PACK_REMOVE_LANG`, `MAP_PACK_ACTIVATE`, `MAP_PACK_DEACTIVATE`.

## 6. Ba chế độ bản đồ (chuỗi bốn tầng)

1. **Chọn chế độ:** `mapConfig` quyết định Cloud, Offline hoặc Hybrid theo trạng thái mạng và pack đã kích hoạt.
2. **Công bố pack:** backend phục vụ `/static/maps/*` và lớp tương thích `/api/v1/maps/*`; manifest nêu phiên bản, checksum, scope, ngày nguồn, bbox, URL tuyệt đối.
3. **Kích hoạt pack:** frontend tải vào cache theo fingerprint, kiểm tra SHA-256 và đọc được PMTiles/style trước khi ghi chỉ mục active; lỗi tải/cài không thay đổi pack đang dùng.
4. **Hiển thị:** nguồn PMTiles tùy biến đọc byte range từ Cache API và dùng mạng làm fallback; hybrid giữ cloud làm dự phòng.

## 7. Ranh giới tin cậy và bảo mật kiến trúc

- Trình duyệt không đọc được token (cookie httpOnly).
- Backend là nơi duy nhất thực thi quyền; JWT mang danh sách quyền.
- PII chỉ giải mã khi cần và không rò rỉ khi lỗi.
- Đường dẫn tệp bản đồ phải nằm trong thư mục gốc cho phép.
- Kênh analytics (cần consent) tách khỏi kênh quan sát vị trí runtime.

## 8. Các mẫu thiết kế được áp dụng

Modular Monolith; Audio lai 4 tầng; Fallback nội dung 3 tầng (chọn, en, vi); Quốc tế hóa hai làn (nội dung và UI); Phân mảnh cache theo ngôn ngữ; Geofence reconcile; RBAC động; Analytics có consent; Cookie httpOnly; PWA offline-first; Theo dõi tiến độ bằng SSE; Mã hóa PII khi lưu.

## 9. Thuộc tính chất lượng và cách đạt được

| Thuộc tính | Cách đạt |
|---|---|
| Chạy offline | 4 lớp cache, pack, IndexedDB |
| Chi phí thấp | Công cụ miễn phí, cache MD5 chống sinh lại |
| Chịu lỗi | Fallback nhiều tầng, backoff, phục hồi tác vụ |
| Mở rộng | Ranh giới router/service/store cho phép tách service sau này |
| Bảo mật | Cookie httpOnly, RBAC, mã hóa PII, rate limit, path guard |
