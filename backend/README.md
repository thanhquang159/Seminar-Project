# Backend API

FastAPI service của dự án, runtime sử dụng PostgreSQL/PostGIS qua SQLAlchemy
async và `asyncpg`. Backend không tự tạo schema; PostgreSQL phải có sẵn schema
của ứng dụng và role/permission dữ liệu cần thiết. Khi startup, backend ping
database và kiểm tra tên database cấu hình.

## Yêu cầu

- Python 3.12
- PostgreSQL với PostGIS và schema ứng dụng đã provision

Docker, MongoDB và Redis không cần cho runtime. Backend dùng PostgreSQL duy
nhất cho dữ liệu nghiệp vụ; cấu hình được tập trung tại `app/core/config.py`.

## Cài đặt

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Trên macOS/Linux, tạo virtualenv bằng `python3 -m venv .venv` và kích hoạt bằng
`source .venv/bin/activate`.

## Cấu hình

Sửa `backend/.env` trước khi chạy:

| Biến | Ý nghĩa |
|---|---|
| `DB_HOST`, `DB_PORT` | PostgreSQL endpoint; mặc định `localhost:5432` |
| `DB_NAME` | Tên database; mặc định `quan4_culinary_tourism` |
| `DB_USER`, `DB_PASSWORD` | Tài khoản kết nối PostgreSQL |
| `APP_ENV` | Đặt `production` khi deploy; giá trị mặc định `dev` chỉ dành cho local |
| `JWT_SECRET`, `REFRESH_TOKEN_SECRET` | Khóa ký access/refresh token; phải đặt secret riêng ngoài dev |
| `PII_KEY` | Fernet key để mã hóa CCCD; bắt buộc cho luồng đăng ký chủ quán |
| `CORS_ORIGINS` | JSON array các origin frontend được phép; mặc định cho localhost:5173/4173 |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_API_URL` | Cấu hình provider AI; mặc định là mock |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Thông tin được `scripts/seed_admin.py` dùng khi tạo admin |

`env_file=".env"` được đọc tương đối với thư mục hiện hành; hãy chạy lệnh
backend từ `backend/`. Không commit `.env` hoặc chia sẻ nội dung chứa mật khẩu.
Trước khi bật đăng ký chủ quán, tạo `PII_KEY` bằng lệnh trong `.env.example`.
Giữ khóa này ổn định và sao lưu an toàn: mất khóa sẽ không giải mã được CCCD
đã mã hóa; không dùng chung khóa giữa các môi trường.

## Chạy và kiểm tra kết nối

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Để điện thoại cùng Wi-Fi truy cập bản dev, khởi động bằng
`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` và thêm origin chính
xác của frontend, ví dụ `http://192.168.1.20:5173`, vào `CORS_ORIGINS` trong
`.env`. Chỉ mở truy cập trên mạng riêng tin cậy; cho phép cổng 8000 qua Windows
Firewall ở profile Private. IP ví dụ phải được thay bằng IPv4 hiện tại của máy
chạy backend.

Ứng dụng dừng khởi động nếu không kết nối được PostgreSQL hoặc `DB_NAME` không
đúng. Kiểm tra database và PostGIS tại:

```text
http://127.0.0.1:8000/api/v1/health/database
```

`/docs` mở Swagger UI và `/redoc` mở tài liệu ReDoc. Database health trả tên DB,
phiên bản PostGIS và số bảng; nó không xác nhận dữ liệu nghiệp vụ đã được nạp.

## Admin user và role APIs

- `GET /admin/users` yêu cầu `users.read`; trả danh sách `{id, email, full_name,
  account_status, role_code, role_name}`.
- `POST /admin/roles` yêu cầu `role:read`; body
  `{code, name, description?, permission_codes?}` tạo role tùy chỉnh. Mã role
  hệ thống và quyền quản trị bị từ chối; mã trùng trả `409`.
- `PATCH /admin/users/{user_id}` yêu cầu `user:update` (permission
  `users.manage` được ánh xạ sang permission này). Body nhận
  `{account_status?: "pending" | "active" | "rejected", role_code?: string | null}`;
  `role_code: null` gỡ role của tài khoản. Role hệ thống và role có quyền
  quản trị không thể được gán. Trả `{id, account_status, role_code}`.
- `PUT /admin/roles/{role_code}/permissions` yêu cầu `role:read` (permission
  `roles.manage` được ánh xạ sang permission này). Body
  `{permission_codes: string[]}` thay thế toàn bộ permissions của role và trả
  `{role_code, permission_codes}`. Chỉ role không phải hệ thống mới được sửa;
  endpoint không cấp quyền `users.manage` hoặc `roles.manage`.

Các thay đổi thành công được ghi vào audit log trong cùng transaction; người
dùng hiện tại không thể tự khóa tài khoản, thay đổi role, hoặc sửa quyền của
role đang sử dụng.

## Báo cáo AI và tác vụ âm thanh

`GET /admin/ai-usage?so_ngay=7` yêu cầu `analytics:view` và tổng hợp lượt dùng
AI theo ngày của chủ quán trong khoảng 1–30 ngày. API không trả nội dung prompt.
Danh sách, luồng tiến độ và lệnh điều khiển tác vụ âm thanh tại `/audio/tasks`
yêu cầu quyền `user:update`. `/audio/on-demand` và `/audio/tts` dành cho khách
không cần đăng nhập; request ẩn danh được giới hạn theo IP.

## Owner portal

- `GET /owner/pois` chỉ trả POI thuộc tài khoản chủ quán đã được duyệt.
- `GET /owner/submissions/mine` trả trạng thái, thời điểm gửi và `admin_note`;
  submission bị từ chối sẽ tạo thông báo cho chủ quán.
- `POST /owner/submissions/{sid}/reject` yêu cầu quyền `poi:approve` và lý do
  từ chối.
- Menu và món ăn được quản lý qua `/owner/pois/{poi_id}/menus` và
  `/owner/menus/{menu_id}/items`; API xác định quyền sở hữu từ phiên đăng nhập.

## Seed dữ liệu

Các script seed/migrate bên dưới dùng PostgreSQL; chạy từ `backend/`:

```powershell
python scripts\seed_roles.py           # xác nhận role ADMIN/OWNER đã được provision
python scripts\seed_admin.py           # tạo admin từ ADMIN_USERNAME/ADMIN_PASSWORD
python scripts\seed_poi.py             # upsert POI mẫu và bản tiếng Việt
python scripts\migrate_localizations.py # đồng bộ bản tiếng Việt từ bảng pois
python scripts\backfill_demo_poi_localizations.py # bổ sung dịch Bakery và ẩn POI nháp bị bật nhầm
```

`seed_roles.py` chỉ kiểm tra, không tạo hoặc sửa role/permission trong schema.
`seed_admin.py` không đổi mật khẩu khi user đã tồn tại; để cập nhật, dùng luồng
đổi mật khẩu trong ứng dụng. Các script seed dữ liệu thay đổi database; hãy
kiểm tra `DB_NAME` trước khi chạy.

`backfill_demo_poi_localizations.py` chỉ thêm các locale còn thiếu cho POI demo
Tiệm Bánh Khánh Hội, không ghi đè bản dịch đã có, và tắt trạng thái hoạt động
nếu POI Quầy Món Ngon nháp đang bị bật nhầm. Cả hai thay đổi làm POI sync trigger
cập nhật cursor để thiết bị hiện có nhận được dữ liệu mới.

## Đồng bộ POI

Trước khi dùng API đồng bộ (`/poi/load-all`, `/poi/delta`), áp dụng migration
một lần vào database đã provision. Migration tạo bộ đếm cursor và trigger/
nhật ký tombstone trong PostgreSQL; cập nhật, ẩn, archive và xóa cứng POI đều
được ghi cùng transaction. Khi cài lần đầu, migration tạo baseline cho POI
đang có và phát tombstone/upsert ban đầu để tương thích cursor đã lưu trên các
thiết bị từ phiên bản trước:

```powershell
cd backend
psql -h localhost -p 5432 -U postgres -d quan4_culinary_tourism -v ON_ERROR_STOP=1 -f scripts\migrations\001_poi_sync.sql
```

Thay host/user/database theo cấu hình thực tế; `psql` sẽ hỏi mật khẩu nếu cần.
Migration khóa ghi trên bảng `pois` trong lúc cài để baseline và trigger không
bỏ sót thay đổi đồng thời. Hãy dùng tài khoản sở hữu schema; nếu tài khoản
backend khác tài khoản chạy migration, cấp quyền `SELECT` trên hai bảng
`poi_sync_state` và `poi_sync_changes` cho tài khoản backend sau khi chạy.
Không áp dụng migration vào database production nếu chưa sao lưu và có phê
duyệt. Nhật ký thay đổi cần được giữ để các thiết bị offline lâu ngày nhận đủ
tombstone; chưa có chính sách dọn lịch sử vì xóa log có thể làm thiết bị bỏ lỡ
thay đổi.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`tests_postgres/` kiểm tra hợp đồng API PostgreSQL và role/permission mapping;
`tests/` giữ các kiểm thử bảo mật độc lập, không cần dịch vụ ngoài.

Playwright E2E cần một PostgreSQL database riêng đã provision schema như hướng
dẫn bên dưới; CI không khởi tạo schema ứng dụng thay bạn.

### Playwright E2E

E2E yêu cầu một database PostgreSQL riêng đã được provision schema và role
`ADMIN`. Mặc định tên là `quan4_culinary_tourism_e2e`; có thể đổi bằng
`E2E_DB_NAME`. Seed E2E xóa dữ liệu trong database được chọn, nên script từ chối
chạy nếu `DB_NAME` không kết thúc bằng `_e2e`.

```powershell
cd frontend
npm run test:e2e
```

Frontend tự truyền `E2E_DB_NAME` cho backend và script seed. PostgreSQL phải tồn
tại trước đó; backend không tạo database hoặc schema thay bạn.
