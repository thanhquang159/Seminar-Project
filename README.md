# AMDS — Hệ thống Du lịch Ẩm thực Quận 4

Ứng dụng web tiến bộ (PWA) giúp khách tham quan tự do khám phá ẩm thực đường phố Quận 4, TP.HCM: bản đồ POI, thuyết minh âm thanh tự động khi đi vào vùng quanh một điểm quan tâm, đa ngôn ngữ, dùng được khi mất mạng, chatbot hỏi đáp và kênh số cho chủ quán.

Kèm theo là giao diện quản trị cho admin/staff (duyệt nội dung, quản lý quán, theo dõi số liệu) và giao diện riêng cho chủ quán (đăng ký, gửi quán, nhận thông báo duyệt).

> **Database runtime:** backend và các script seed/migrate nghiệp vụ sử dụng PostgreSQL/PostGIS. MongoDB và Redis đã được loại khỏi runtime; test backend gồm bộ kiểm thử PostgreSQL và kiểm thử bảo mật độc lập.

## Chức năng chính

- Hiển thị các điểm quan tâm ẩm thực (POI) trên bản đồ, kèm mô tả và thực đơn.
- Tự động phát thuyết minh khi người dùng đi vào bán kính quanh một POI, có hàng đợi và tôn trọng tầng phát âm thanh của trình duyệt.
- Đa ngôn ngữ `vi` / `en` / `zh` / `ja` / `ko` với chuỗi dự phòng 3 tầng (yêu cầu → tiếng Anh → tiếng Việt).
- Dịch và sinh audio (TTS) tự động ở phía server sau khi admin cập nhật nội dung; tiến độ xem được qua SSE.
- PWA cache dữ liệu POI và audio để dùng khi mất mạng; gói nền bản đồ PMTiles hiện chưa có tile thực và cần được tạo/cài trước khi dùng bản đồ offline.
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
    +-- PostgreSQL + PostGIS     database quan4_culinary_tourism
```

Đây là **modular monolith**: một tiến trình FastAPI duy nhất, chia thành module theo miền nghiệp vụ. Lý do không tách microservice được ghi ở ADR-001 của kế hoạch phát triển.

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Frontend | React 19, TypeScript ~6.0, Vite 8, Zustand 5 |
| Bản đồ | MapLibre GL 6 + PMTiles 4 (OpenFreeMap khi online, PMTiles khi offline) |
| PWA | vite-plugin-pwa + Workbox (`injectManifest`) |
| Backend | Python 3.12, FastAPI 0.141, SQLAlchemy async, asyncpg, uvicorn |
| Cơ sở dữ liệu | PostgreSQL + PostGIS |
| Dịch / TTS | deep-translator + edge-tts (miễn phí, đổi được qua adapter) |
| AI | adapter provider: `mock` khi phát triển, HTTP provider khi có key |
| Kiểm thử | pytest + Vitest + Playwright + GitHub Actions |
| Tiện ích | ruff (lint/format), ESLint 10 |

## Cấu trúc repository

```text
AMDS/
├── backend/                 # API và nghiệp vụ FastAPI
│   ├── app/                 # main.py, api/, core/, postgres.py, routers/, services/
│   ├── scripts/             # seed dữ liệu mẫu, build gói bản đồ, migrate bản dịch
│   ├── tests/               # test bảo mật độc lập
│   └── tests_postgres/      # test hợp đồng runtime PostgreSQL
├── frontend/                # web app khách tham quan + giao diện admin và chủ quán
│   ├── src/                 # geofence/, offline/, i18n/, analytics/, admin/, telemetry/
│   └── e2e/                 # kịch bản Playwright
├── scripts/verify.py        # một lệnh chạy lint + type + test cho cả hai vế
├── docs/system-doc/         # đặc tả yêu cầu, kiến trúc, API, dữ liệu, kiểm thử...
└── README.md
```

## Trạng thái hiện tại

Đã hoàn thành **Phase 0 → 11** theo kế hoạch (16 phase): từ dựng môi trường tới lưới kiểm thử hợp nhất (lint, type, unit, tích hợp, ma trận quyền, ca biên, E2E, CI).

- Backend: các router nghiệp vụ runtime kết nối PostgreSQL; test PostgreSQL riêng nằm trong `backend/tests_postgres/`.
- Frontend: PWA có geofence, audio, i18n, offline, analytics, giao diện admin và chủ quán; khoảng 34 test Vitest và 4 kịch bản Playwright.
- Chưa làm: Phase 14 (chuẩn bị production), 15 (triển khai). Phase 12 (security hardening) đã xong. Phase 13 (hiệu năng) đang làm. Chưa có Dockerfile, chưa có reverse proxy, chưa đo hiệu năng.

Kế hoạch phát triển chi tiết nằm ở `docs/plan-task/` (thư mục này cố ý không commit vào git).

## Bắt đầu phát triển

Yêu cầu: Python 3.12, Node.js 22 và PostgreSQL/PostGIS đang chạy.

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Cập nhật DB_HOST, DB_PORT, DB_NAME, DB_USER và DB_PASSWORD trong .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (terminal khác, nếu cần)
cd frontend
npm install
npm run dev:lan
```

Trên cùng máy, mở <http://localhost:5173>. Để truy cập từ điện thoại cùng Wi-Fi,
lấy IPv4 của máy tính bằng `ipconfig`, thêm origin
`http://<IP-máy-tính>:5173` vào mảng `CORS_ORIGINS` trong `backend/.env`, rồi
khởi động lại backend. Trên điện thoại mở
`http://<IP-máy-tính>:5173` (ví dụ `http://192.168.1.20:5173`). Frontend sẽ
dùng cùng địa chỉ IP đó để gọi API cổng 8000. Chỉ làm trên mạng riêng tin cậy;
Windows Firewall cần cho phép cổng 5173 và 8000 trên profile Private. Nếu DHCP
đổi IP, cập nhật lại `CORS_ORIGINS`. API tài liệu endpoint ở `/docs`.

Kiểm tra kết nối: <http://127.0.0.1:8000/api/v1/health/database>. Schema PostgreSQL phải được provision trước; các script `seed_roles.py`, `seed_admin.py`, `seed_poi.py` và `migrate_localizations.py` hiện thao tác trên PostgreSQL. Đọc [hướng dẫn backend](backend/README.md) trước khi chạy seed vì chúng có thể thay đổi dữ liệu.

## Kiểm tra trước khi commit

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Lệnh trên chạy cả test độc lập và `tests_postgres/`; không kết nối hoặc sửa database thật.

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

Tài liệu `01`–`12` mô tả phạm vi, yêu cầu và hướng dẫn của đồ án; backend runtime hiện dùng PostgreSQL/PostGIS. Hướng dẫn backend và mã nguồn là nguồn chuẩn cho cấu hình, schema và cách chạy.

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

## Link Domain Vercel
https://seminar-project-tau.vercel.app/

## Tài khoản 
Admin: demo.admin@quan4.local
Pass: Quan4Demo@123

Owner: demo.owner@quan4.local
Pass: Quan4Demo@123

Owner chờ duyệt: demo.pending@quan4.local
Pass: Quan4Demo@123