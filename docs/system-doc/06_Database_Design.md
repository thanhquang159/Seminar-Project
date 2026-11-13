# 06 — Database Design (Thiết kế cơ sở dữ liệu)

Cơ sở dữ liệu runtime là **PostgreSQL + PostGIS**, truy cập bất đồng bộ qua SQLAlchemy 2 và `asyncpg`. Backend dùng schema đã provision; startup chỉ kiểm tra kết nối và tên database, không tự tạo bảng hoặc tự chạy migration. Kiểu dữ liệu, constraint và index phải được đối chiếu với DDL của môi trường PostgreSQL trước khi triển khai.

## 1. Các nhóm bảng đang được backend sử dụng

Tên dưới đây được xác nhận từ truy vấn SQL và seed hiện tại; đây là danh sách theo nhóm nghiệp vụ, không thay thế DDL của database.

| Nhóm | Bảng | Mục đích |
|---|---|---|
| Định danh và RBAC | `users`, `auth_sessions`, `roles`, `permissions`, `user_roles`, `role_permissions` | Tài khoản, phiên đăng nhập và quan hệ role-permission |
| POI và bản địa hóa | `pois`, `poi_images`, `poi_localizations` | Nội dung POI, ảnh, bản dịch và audio theo ngôn ngữ |
| Đồng bộ POI | `poi_sync_state`, `poi_sync_changes` | Trạng thái cursor và các thay đổi phục vụ full/delta sync |
| Menu và Owner | `menus`, `menu_items`, `owner_registrations`, `poi_submissions`, `owner_notifications` | Thực đơn, đăng ký chủ quán, nội dung chờ duyệt và thông báo |
| Audio và giới hạn | `audio_tasks`, `localization_request_logs`, `ai_usage_daily` | Trạng thái tác vụ audio, giới hạn yêu cầu và lượt dùng AI |
| Quản trị và quan sát | `audit_logs`, `analytics_consents`, `analytics_events`, `runtime_observability_hourly` | Nhật ký kiểm toán, analytics có consent và số liệu quan sát runtime |
| Bản đồ offline | `offline_packs`, `offline_pack_assets` | Manifest và metadata tài sản bản đồ offline |

## 2. Quan hệ dữ liệu

- `user_roles` liên kết `users` với `roles`; `role_permissions` liên kết `roles` với `permissions`.
- `poi_images` và `poi_localizations` gắn với POI; `menus` và `menu_items` biểu diễn thực đơn của POI.
- `owner_registrations`, `poi_submissions` và `owner_notifications` liên kết chủ quán với quy trình duyệt và thông báo.
- `audio_tasks` lưu trạng thái tác vụ; tệp MP3 được lưu trong static/runtime storage, không lưu trong hàng cơ sở dữ liệu.
- Các thay đổi POI phục vụ đồng bộ được ghi trong `poi_sync_state` và `poi_sync_changes`.
- `analytics_events` chỉ nhận dữ liệu theo chính sách consent; bảng tổng hợp vị trí runtime được tách riêng.

Các ràng buộc khóa ngoại, cascade và transaction thuộc schema PostgreSQL đã provision. Không suy diễn chúng từ tài liệu này; kiểm tra DDL trước khi thay đổi schema.

## 3. Kết nối và truy vấn không gian

- Cấu hình kết nối qua `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` và `DB_PASSWORD`.
- `app.postgres` tạo engine `postgresql+asyncpg`, session factory `AsyncSessionLocal` và dependency `get_db`.
- API health kiểm tra database hiện tại, PostGIS và số bảng. Có thể kiểm tra tại `/api/v1/health/database`.
- API truy vấn POI gần vị trí dùng PostgreSQL/PostGIS, không dùng MongoDB geospatial query.
- Schema phải được provision trước khi chạy app; script seed và E2E cần được chạy đúng database.

## 4. Kiểm thử và bảo vệ dữ liệu

Các test backend thông thường không tự tạo hoặc migrate schema thật. Playwright E2E dùng database riêng có tên kết thúc bằng `_e2e`; `backend/scripts/seed_e2e.py` từ chối tên database khác và xóa dữ liệu trong database được chọn trước khi seed. Không chạy script này trên database dev hoặc production.

## 5. Dữ liệu phía trình duyệt

**IndexedDB `Quan4DB` phiên bản 2:**
- `pois_by_lang`: bản chụp POI theo từng ngôn ngữ.
- Kho UI bundle đã cache.

**Cache API (do Service Worker quản lý):**
- `poi-load-all-cache` (TTL 15 phút).
- `audio-cache-lang-{lang}` (tối đa 300 tệp mỗi ngôn ngữ, 3 ngôn ngữ).
- Cache ảnh, cache chunk tùy chọn, cache gói bản đồ bất biến, cache gói audio.
