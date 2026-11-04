# AMDS — Hệ thống Du lịch Ẩm thực Quận 4

Ứng dụng web tiến bộ (PWA) giúp khách tham quan tự do khám phá ẩm thực đường phố Quận 4, TP.HCM: bản đồ POI, thuyết minh âm thanh tự động khi đi vào vùng quanh một điểm quan tâm, đa ngôn ngữ, dùng được khi mất mạng, chatbot hỏi đáp và kênh số cho chủ quán.

Kèm theo là giao diện quản trị cho admin/staff (duyệt nội dung, quản lý quán, theo dõi số liệu) và giao diện riêng cho chủ quán (đăng ký, gửi quán, nhận thông báo duyệt).

## Chức năng chính

- Hiển thị các điểm quan tâm ẩm thực (POI) trên bản đồ, kèm mô tả và thực đơn.
- Tự động phát thuyết minh khi người dùng đi vào bán kính quanh một POI, có hàng đợi và tôn trọng tầng phát âm thanh của trình duyệt.
- Đa ngôn ngữ `vi` / `en` / `zh` / `ja` / `ko` với chuỗi dự phòng 3 tầng (yêu cầu → tiếng Anh → tiếng Việt).
- Dịch và sinh audio (TTS) tự động ở phía server sau khi admin cập nhật nội dung; tiến độ xem được qua SSE.
- Gói offline (bản đồ PMTiles + dữ liệu POI + audio), dùng lại được khi mất mạng, có kiểm tra checksum.
- Chủ quán tự đăng ký và gửi quán mới; admin duyệt trước khi hiển thị.
- Đăng nhập admin/staff bằng cookie `httpOnly`, phân quyền theo vai trò (RBAC).
- Chatbot hỏi đáp về các quán (mặc định dùng provider `mock` khi phát triển).
- Số liệu thống kê chỉ ghi khi khách đồng ý (consent), có dashboard cho admin.
- Kênh quan sát hiện diện theo giờ, tách riêng khỏi analytics vì mục đích và ràng buộc khác nhau.

## Kiến trúc

```text
Trình duyệt / PWA (React 19 + TypeScript + Vite + MapLibre)
    |  REST/JSON, cookie httpOnly
    v
Backend API: Python 3.12 + FastAPI (chạy native để hot-reload)
    |
    +-- MongoDB 7.0     POI, bản dịch, tài khoản, chủ quán, sự kiện, số liệu
    +-- Redis 7.2       đếm hiện diện theo cửa sổ trượt, giới hạn tần suất
```

Đây là **modular monolith**: một tiến trình FastAPI duy nhất, chia thành module theo miền nghiệp vụ. Lý do không tách microservice được ghi ở ADR-001 của kế hoạch phát triển.

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Frontend | React 19, TypeScript ~6.0, Vite 8, Zustand 5 |
| Bản đồ | MapLibre GL 6 + PMTiles 4 (style nền MapTiler, có nền demo miễn phí khi thiếu key) |
| PWA | vite-plugin-pwa + Workbox (`injectManifest`) |
| Backend | Python 3.12, FastAPI 0.141, Motor 3.7 (async), uvicorn |
| Cơ sở dữ liệu | MongoDB 7.0 (dev chạy bằng Docker Compose; tích hợp cần replica set một node cho transaction) |
| Cache và hiện diện | Redis 7.2 |
| Dịch / TTS | deep-translator + edge-tts (miễn phí, đổi được qua adapter) |
| AI | adapter provider: `mock` khi phát triển, HTTP provider khi có key |
| Kiểm thử | pytest + Vitest + Playwright + GitHub Actions |
| Tiện ích | ruff (lint/format), ESLint 10 |

## Cấu trúc repository

```text
AMDS/
├── backend/                 # API và nghiệp vụ FastAPI
│   ├── app/                 # main.py, config.py, db.py, routers/, services/, models/
│   ├── scripts/             # seed dữ liệu mẫu, build gói bản đồ, migrate bản dịch
│   └── tests/               # 95 test (87 unit + 8 tích hợp)
├── frontend/                # web app khách tham quan + giao diện admin và chủ quán
│   ├── src/                 # geofence/, offline/, i18n/, analytics/, admin/, telemetry/
│   └── e2e/                 # kịch bản Playwright
├── scripts/verify.py        # một lệnh chạy lint + type + test cho cả hai vế
├── docs/system-doc/         # đặc tả yêu cầu, kiến trúc, API, dữ liệu, kiểm thử...
├── docker-compose.yml       # hạ tầng dev: MongoDB + Redis
├── docker-compose.test.yml  # hạ tầng test: Mongo replica set một node + Redis riêng
└── README.md
```

## Trạng thái hiện tại

Đã hoàn thành **Phase 0 → 11** theo kế hoạch (16 phase): từ dựng môi trường tới lưới kiểm thử hợp nhất (lint, type, unit, tích hợp, ma trận quyền, ca biên, E2E, CI).

- Backend: 17 router, khoảng 55 endpoint, 95 test.
- Frontend: PWA có geofence, audio, i18n, offline, analytics, giao diện admin và chủ quán; khoảng 34 test Vitest và 4 kịch bản Playwright.
- Chưa làm: Phase 14 (chuẩn bị production), 15 (triển khai). Phase 12 (security hardening) đã xong. Phase 13 (hiệu năng) đang làm. Chưa có Dockerfile, chưa có reverse proxy, chưa đo hiệu năng.

Kế hoạch phát triển chi tiết nằm ở `docs/plan-task/` (thư mục này cố ý không commit vào git).

## Bắt đầu phát triển

Yêu cầu: Python 3.12, Node.js 22, Docker Desktop.

```powershell
# 1. Hạ tầng
docker compose up -d --wait

# 2. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload

# 3. Frontend (terminal khác)
cd frontend
npm install
npm run dev
```

Mở <http://localhost:5173>. API chạy ở <http://127.0.0.1:8000>, tài liệu endpoint ở `/docs`.

Nạp dữ liệu mẫu:

```powershell
cd backend
python scripts\seed_roles.py
python scripts\seed_admin.py
python scripts\seed_poi.py
python scripts\migrate_localizations.py
```

Biến môi trường chứa secret (`JWT_SECRET`, `REFRESH_TOKEN_SECRET`, `PII_KEY`, `AI_API_KEY`) không được commit; dùng file `.env` cục bộ hoặc secret manager khi triển khai. Ngoài `dev`, thiếu `JWT_SECRET`/`REFRESH_TOKEN_SECRET` thì backend từ chối khởi động (`kiem_tra_bi_mat` trong `backend/app/config.py`).

## Kiểm tra trước khi commit

```powershell
python scripts\verify.py
```

Lệnh này chạy ruff, ESLint, `tsc -b`, pytest, Vitest theo đúng thứ tự CI và dừng ngay ở bước hỏng.

Test tích hợp cần hạ tầng riêng (Mongo replica set một node + Redis cổng khác):

```powershell
docker compose -f docker-compose.test.yml up -d --wait
cd backend
pytest -m integration -o addopts="-ra"
```

## Tài liệu

- [Phạm vi đồ án](docs/system-doc/01_Project_Scope.md)
- [Yêu cầu hệ thống](docs/system-doc/02_Requirements.md)
- [User stories](docs/system-doc/03_User_Stories.md)
- [Use cases](docs/system-doc/04_Use_Cases.md)
- [Kiến trúc hệ thống](docs/system-doc/05_System_Architecture.md)
- [Thiết kế cơ sở dữ liệu](docs/system-doc/06_Database_Design.md)
- [Đặc tả API](docs/system-doc/07_API_Specification.md)
- [Đặc tả UI/UX](docs/system-doc/08_UI_UX_Specification.md)
- [Xác thực và phân quyền](docs/system-doc/09_Authentication_Authorization.md)
- [Dịch vụ bên ngoài](docs/system-doc/10_External_Services.md)
- [Kế hoạch kiểm thử](docs/system-doc/11_Test_Plan.md)
- [Kế hoạch triển khai](docs/system-doc/12_Deployment.md)

Tài liệu `01`–`12` được viết theo bản đặc tả gốc; đã đối chiếu và **giữ tên collection và tiền tố route của code** khi hai bên lệch nhau (ADR-015). Danh sách nợ kỹ thuật còn lại nằm ở mục O của kế hoạch phát triển.

## Lộ trình phát triển

1. [x] Môi trường, kết nối cơ sở dữ liệu, danh sách POI lên màn hình.
2. [x] Bản đồ, vị trí người dùng, chọn POI.
3. [x] Geofence và phát thuyết minh.
4. [x] Quản trị POI và đăng nhập bằng cookie `httpOnly`.
5. [x] Đa ngôn ngữ, dịch và TTS phía server.
6. [x] Phân quyền, cổng chủ quán, chatbot.
7. [x] Offline v1, đồng bộ delta, gói bản đồ và audio.
8. [x] i18n hai lớn, bộ nhớ nóng, giới hạn tần suất.
9. [x] Analytics có consent và dashboard.
10. [x] Lưới kiểm thử: CI, test tích hợp, ma trận quyền, ca biên, E2E.
11. [ ] Rà và vá bảo mật (Phase 12).
12. [ ] Đo rồi tối ưu hiệu năng (Phase 13).
13. [ ] Chuẩn bị production: log, transaction, container, sao lưu (Phase 14).
14. [ ] Triển khai và review cuối (Phase 15).

## Bảo mật

- Mật khẩu lưu dạng băm bcrypt; phiên admin dùng access token và refresh token trong cookie `httpOnly`.
- Phân quyền kiểm ở tầng route bằng `require_permission`, không chỉ ẩn nút trên giao diện.
- Dữ liệu cá nhân mã hóa bằng Fernet trước khi ghi; che sau 180 ngày; mọi thao tác quản trị ghi vào nhật ký kiểm toán.
- Giới hạn tần suất cho đăng nhập, dịch và sinh audio; chatbot có hạn mức.
- Chỉ ghi sự kiện thống kê khi khách đã đồng ý; từ chối thì không có request analytics nào đi ra.
- Không có cổng thanh toán và không lưu thông tin thẻ trong phạm vi dự án.
- Đã làm xong Phase 12 (13/13 task, SEC-001..013): validate đầu vào, chống brute force đăng nhập, thu hẹp CORS, chặn ghi từ origin lạ, quét bí mật, che dữ liệu nhạy cảm trong log, chặn XSS, chống NoSQL injection, header bảo mật và CSP, gỡ phụ thuộc có lỗ hổng, thu hồi phiên khi đổi mật khẩu, tải ảnh có kiểm tra, review tổng hợp.

### Việc còn treo của Phase 12

Ba lỗ hổng đã phát hiện nhưng chưa vá, ghi ở đây để khỏi tưởng là đã xử lý xong:

1. **Giao diện chưa hiển thị ảnh.** API `GET/POST/DELETE /admin/pois/{poi_id}/images` đã hoạt động và `ghep_poi()` đã trả trường `images` cho client, nhưng không có thành phần React nào đọc trường này. Nghĩa là ảnh tải lên được lưu, được trả về, nhưng người dùng chưa nhìn thấy ở đâu.
2. **Dữ liệu kinh doanh rời khỏi hệ thống khi bật AI thật.** `POST /ai/enhance-description` gửi nguyên văn mô tả quán (tên quán, đặc trưng kinh doanh) tới `AI_API_URL` — một nhà cung cấp bên ngoài. Môi trường dev đặt `AI_PROVIDER=mock` nên hiện chưa lộ dữ liệu nào; đổi sang `http` là lộ ngay. Đây là quyết định sản phẩm (có dùng AI ngoài hay không) chứ không phải lỗi code, nên chưa tự sửa.
3. **Người có quyền `user:update` vẫn duyệt được đơn của người khác.** `POST /owner/registrations/{username}/approve` nhận `username` từ URL và chỉ kiểm quyền, không kiểm đó là đơn của ai. Đã chặn được kịch bản nguy hiểm nhất (chủ quán tự duyệt đơn của chính mình), nhưng admin A vẫn duyệt được đơn của chủ quán B. Chặn triệt để thì phải bỏ `username` khỏi URL — đó là thay đổi API, cần quyết định trước khi làm.

## Giấy phép

Dự án được thực hiện trong phạm vi đồ án học tập. Thông tin về giấy phép phát hành sẽ được bổ sung khi dự án xác định chính sách phân phối mã nguồn.