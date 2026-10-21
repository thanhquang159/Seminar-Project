# Backend API

FastAPI service của dự án. Chạy **native** trên máy (không Docker hoá) để hot-reload nhanh; MongoDB và Redis chạy bằng Docker Compose.

> Xem [`../README.md`](../README.md) để hiểu tổng quan. Tài liệu đặc tả nằm ở `docs/` (không commit vào git theo chủ ý).

---

## 1. Yêu cầu cài đặt

| Công cụ | Phiên bản | Bắt buộc | Ghi chú |
|---|---|---|---|
| Python | 3.12.x | Có | `pyproject.toml` đặt `target-version = "py312"` |
| pip | đi kèm Python | Có | dùng `python -m pip` cho chắc |
| Docker Desktop | 29.x hoặc mới hơn | Có | chỉ dùng để chạy MongoDB + Redis |

Kiểm tra trước khi bắt đầu:

```powershell
python --version
docker --version
docker compose version
```

Cài Docker Desktop tại <https://www.docker.com/products/docker-desktop/> (Windows cần bật WSL 2).

---

## 2. Cài đặt lần đầu

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Trên **macOS / Linux**:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Nếu PowerShell báo lỗi *"running scripts is disabled"*, chạy lệnh này một lần rồi thử activate lại:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Thư mục `.venv` có được commit không?

Không. `.gitignore` ở thư mục gốc đã loại `.venv/`, `__pycache__/` và `*.pyc`. Mỗi người tự tạo `.venv` riêng trên máy, không cần copy.

### Kiểm tra cài đặt thành công

```powershell
python -c "import fastapi, motor, pymongo; print('OK')"
ruff --version
```

---

## 3. Cấu hình biến môi trường

```powershell
Copy-Item .env.example .env          # PowerShell
# cp .env.example .env               # macOS / Linux
```

Nội dung `.env.example`:

| Biến | Bắt buộc | Ví dụ | Ý nghĩa |
|---|---|---|---|
| `MONGODB_URI` | Có | `mongodb://localhost:27017` | chuỗi kết nối MongoDB |
| `MONGODB_DB_NAME` | Có | `amds` | tên database sẽ dùng |
| `APP_ENV` | Ngoài dev là bắt buộc | `dev` | `dev` thì nới lỏng cookie `Secure` và secret mặc định |
| `JWT_SECRET` | Ngoài dev | *(để trống)* | ký access token; thiếu thì backend từ chối khởi động |
| `REFRESH_TOKEN_SECRET` | Ngoài dev | *(để trống)* | ký refresh token, tách khóa riêng |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Không | `admin` / `admin123` | tài khoản admin seed sẵn, **chỉ dùng cho dev** |
| `REDIS_URL` | Không | `redis://localhost:6379` | đếm hiện diện theo cửa sổ trượt |
| `PII_KEY` | Ngoài dev | khoá Fernet | mã hóa CCCD; để rỗng thì **không mã hóa** |
| `AI_PROVIDER` | Không | `mock` | `mock` khi phát triển, provider khác khi có key |
| `AI_API_KEY` / `AI_API_URL` | Không | *(để trống)* | thông tin provider AI |
| `CORS_ORIGINS` | Không | 4 origin `localhost`/`127.0.0.1` cổng `5173` (dev) và `4173` (preview) | danh sách JSON origin được phép gọi API và gửi analytics; chặn `*` và origin sai dạng ngay lúc khởi động |

Biến đọc từ biến môi trường sẽ đè lên giá trị trong `.env`.

### `.env` có được nạp không?

Có. Toàn bộ cấu hình nằm trong `app/config.py` dùng `pydantic-settings` với `env_file=".env"`. Code nghiệp vụ chỉ đọc qua `settings`, không gọi `os.getenv` rải rác.

Hai điều cần nhớ:

- `env_file=".env"` là đường dẫn **tương đối theo thư mục đang chạy**. Phải chạy `uvicorn` từ trong `backend/` thì mới nạp được; chạy từ thư mục gốc repo sẽ bỏ qua `.env`.
- `settings` được tạo lúc import module, tức là `.env` chỉ có tác dụng **trước khi khởi động server**. Sửa `.env` giữa chừng cần restart.

### Không bao giờ commit `.env`

`.env` chứa giá trị thật. Chỉ `.env.example` được commit. Nếu lỡ commit nhầm:

```powershell
git rm --cached .env
```

rồi thêm `.env` vào `.gitignore` (xem [Mục 9](#9-giới-hạn-và-nợ-kỹ-thuật)).

---

## 4. Chạy MongoDB và Redis bằng Docker Compose

Compose nằm ở **thư mục gốc**, không phải trong `backend/`:

```powershell
cd ..                 # về thư mục gốc
docker compose up -d --wait
docker compose ps
```

Kết quả mong đợi — cả hai service đều `running` (hoặc `healthy`):

```
NAME              IMAGE                STATUS
quan4-mongodb     mongo:7.0            running
quan4-redis       redis:7.2-alpine     running
```

Cổng được mở ra máy host:

| Service | Cổng host | Cổng trong container |
|---|---|---|
| MongoDB | `27017` | `27017` |
| Redis | `6379` | `6379` |

Dữ liệu được lưu bằng named volume nên **không mất khi `docker compose down`**. Xoá vĩnh viễn (kèm dữ liệu) thì dùng `docker compose down -v`.

### Lệnh Docker thường dùng

```powershell
docker compose up -d --wait     # khởi động, chờ healthcheck pass
docker compose ps               # xem trạng thái
docker compose logs -f mongodb  # theo dõi log MongoDB
docker compose stop             # dừng, giữ container
docker compose down             # xoá container, giữ volume
docker compose down -v          # xoá container VÀ volume (mất dữ liệu)
```

### Kết nối thử trực tiếp

```powershell
docker compose exec mongodb mongosh --quiet --eval "db.runCommand({ ping: 1 })"
docker compose exec redis redis-cli ping
```

Cả hai lệnh trả về `1` và `PONG` là được.

---

## 5. Chạy backend

Giữ terminal `docker compose` đã chạy, mở terminal mới:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Output mong đợi:

```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
[startup] MongoDB connected ✅
INFO:     Uvicorn running on http://127.0.0.1:8000
```

| Địa chỉ | Nội dung |
|---|---|
| <http://127.0.0.1:8000> | endpoint gốc, trả tên service |
| <http://127.0.0.1:8000/health> | health-check |
| <http://127.0.0.1:8000/docs> | Swagger UI — giao diện test API |

Dừng server bằng `Ctrl+C`.

### Về chế độ fail-soft

`app/main.py` cố tình **không crash** nếu MongoDB chưa sẵn sàng. Nếu kết nối thất bại, backend vẫn khởi động và in cảnh báo `[startup] MongoDB chưa sẵn sàng`. Điều này giúp bạn sửa code frontend khi chưa bật Docker. Nhưng `/health` vẫn trả **503** cho tới khi Mongo lên — dùng endpoint đó làm tín hiệu sẵn sàng.

---

## 6. Kiểm tra hoạt động

Health-check trả `200` khi MongoDB kết nối được, `503` khi không.

```powershell
curl.exe -i http://127.0.0.1:8000/health
```

> Trên Windows dùng `curl.exe` (không phải `curl`) — trong PowerShell, `curl` là alias của `Invoke-WebRequest` và sẽ không hiện status code. Trên macOS/Linux dùng `curl` bình thường.

Kết quả đúng (HTTP/1.1 200 OK):

```json
{
  "status": "ok",
  "mongo": "connected",
  "timestamp": "2026-09-27T08:00:00+00:00"
}
```

MongoDB chưa chạy (HTTP/1.1 503 Service Unavailable):

```json
{
  "status": "degraded",
  "mongo": "disconnected",
  "timestamp": "2026-09-27T08:00:00+00:00",
  "mongo_error": "ServerSelectionTimeoutError: ..."
}
```

Cách đọc nhanh trong PowerShell:

```powershell
(Invoke-WebRequest http://127.0.0.1:8000/health).StatusCode   # 200 hoặc 503
Invoke-RestMethod http://127.0.0.1:8000/                       # tên service
```

---

## 7. Cấu trúc thư mục

```text
backend/
├── .env.example              # mẫu biến môi trường — được commit
├── .env                      # biến thật — KHÔNG commit (tạo tay)
├── .venv/                    # môi trường ảo Python — KHÔNG commit
├── pyproject.toml            # cấu hình ruff + marker pytest
├── requirements.txt          # dependency đã ghim phiên bản
├── scripts/                  # seed dữ liệu mẫu, migrate bản dịch, build gói bản đồ
├── static/ui/                # bản dịch giao diện (en, ja, ko, vi, zh)
├── tests/                    # 95 test: 87 unit + 8 integration
└── app/
    ├── main.py               # tạo FastAPI app, lifespan 5 tầng, gắn router
    ├── config.py             # Settings (pydantic-settings), kiểm tra bí mật
    ├── db.py                 # kết nối Motor/MongoDB + close
    ├── auth.py               # ký/kiểm tra token, cookie, seed admin
    ├── permissions.py        # bảng quyền và `require_permission`, đảm bảo role
    ├── audit.py              # nhật ký kiểm toán
    ├── pii.py                # mã hóa PII bằng Fernet
    ├── redis_client.py       # kết nối Redis cho đếm hiện diện
    ├── models/               # mô hình dữ liệu
    ├── routers/              # 17 nhóm endpoint
    └── services/             # nghiệp vụ: audio, i18n, AI, analytics, sync, maps, rate limit
```

`app/` là *namespace package* — cố ý không có `__init__.py` ở đó.

### Endpoint hiện có

Tất cả route đều **không** có tiền tố `/api/v1` (xem ADR-015: giữ nguyên để không phá client; đặt `/api/v1` là task riêng ở Phase 14).

| Nhóm | Tiền tố | Nội dung |
|---|---|---|
| `health.py` | *(không)* | `GET /health` — 200 khi Mongo kết nối, 503 khi không |
| `geo.py` | `/poi` | tìm quán gần vị trí, khoảng cách |
| `poi.py` | `/poi` | danh sách, chi tiết, tạo, xoá |
| `localizations.py` | `/localizations` | bản dịch của một POI |
| `warmup.py` | `/localizations` | khởi động sớm tác vụ dịch/TTS nền |
| `audio.py` | `/audio` | phát audio, tiến độ tác vụ (SSE), các tầng audio |
| `i18n.py` | `/ui-bundles` | bản dịch giao diện theo ngôn ngữ |
| `maps.py` | `/maps` | pack bản đồ, kiểm tra checksum |
| `admin_auth.py` | `/admin/auth` | đăng nhập, đăng xuất, refresh |
| `admin_pois.py` | `/admin/pois` | CRUD POI cho quản trị |
| `admin_meta.py` | `/admin` | vai trò và quyền hiện có |
| `owner.py` | *(không)* | đăng ký chủ quán, gửi quán, duyệt, thông báo |
| `ai.py` | `/ai` | chatbot hỏi đáp |
| `analytics.py` | `/analytics` | consent, ghi sự kiện, sự kiện đã chờ gửi |
| `runtime_observability.py` | `/runtime-observability` | hiện diện theo giờ (tách khỏi analytics) |
| `admin_analytics.py` | `/admin/analytics` | dashboard và số liệu theo giờ/ngày |

### Seed dữ liệu mẫu

Chạy từ trong `backend/`, theo thứ tự:

```powershell
python scripts\seed_roles.py       # vai trò và quyền
python scripts\seed_admin.py       # tài khoản admin từ ADMIN_USERNAME/PASSWORD
python scripts\seed_poi.py         # các quán Quận 4 (idempotent, khóa theo tên)
python scripts\migrate_localizations.py   # tạo bản dịch rỗng để dịch/TTS nền lấp
python scripts\seed_e2e.py         # dữ liệu dùng cho kịch bản Playwright
python scripts\build_map_pack.py   # đóng gói bản đồ PMTiles
```

---

## 8. Lint, format và kiểm thử

Dùng `ruff` (đã nằm trong `requirements.txt`):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

ruff check .            # phát hiện lỗi: import thừa, biến chưa dùng, style
ruff check --fix .      # tự sửa phần lớn lỗi
ruff format .           # áp dụng format chuẩn (giống black)
ruff format --check .   # chỉ kiểm tra, không ghi file
```

Cấu hình nằm trong `pyproject.toml`:

- `line-length = 100`
- Rule bật: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `B` (bugbear), `UP` (pyupgrade)
- Bỏ qua: `E501` (để formatter lo)

**Chạy `ruff check .` và `ruff format .` trước khi commit.** Import được sắp xếp tự động theo `I` (isort).

### Chạy test

```powershell
pytest -q                                              # 87 unit test, mặc định loại integration
pytest -q -m integration -o addopts="-ra"               # 8 test tích hợp, cần hạ tầng riêng
pytest -q tests/test_ma_tran_quyen.py                  # một file cụ thể khi đang sửa ma trận quyền
```

`pyproject.toml` ghim `addopts = "-ra -m 'not integration'"`, nên `pytest -q` thường **không** chạy test tích hợp. Muốn chạy thì phải ghi đè `addopts` như trên.

Test tích hợp cần Mongo **replica set một node** (transaction chỉ chạy được trên replica set) ở cổng `27018` và Redis ở `6380`:

```powershell
cd <thư mục gốc repo>
docker compose -f docker-compose.test.yml up -d --wait
```

Nếu không bật hạ tầng, pytest dừng với `Không kết nối được MongoDB tại mongodb://localhost:27017`.

Có thể kiểm chứng cả hai vế repo bằng một lệnh ở thư mục gốc:

```powershell
python scripts\verify.py          # ruff + pytest + ESLint + tsc + Vitest
```

---

## 9. Giới hạn và nợ kỹ thuật

Những thứ **chưa** có, để bạn không tìm nhầm:

| Vấn đề | Chi tiết | Nên sửa ở |
|---|---|---|
| Backend vẫn start khi Mongo chưa lên | in `[startup] MongoDB chưa sẵn sàng` rồi chạy tiếp | dùng `/health` làm tín hiệu; chặn cứng thuộc PROD-003 |
| `PII_KEY` để rỗng thì **không mã hóa** PII | `app/pii.py` trả về giá trị gốc khi không có khoá | bắt buộc đặt khi triển khai thật (SEC-005) |
| `ADMIN_PASSWORD` mặc định `admin123` | chỉ dành cho dev; đổi trước khi lên môi trường thật | checklist Phase 14 |
| Redis tắt thì không đếm được hiện diện | `presence.py` trả `None` thay vì chặn | ADR-010 đã chốt fail-open cho hiện diện |
| Route chưa có tiền tố `/api/v1` | tài liệu 07 ghi `/api/v1`, code không có | task riêng ở Phase 14 (ADR-015) |
| Ảnh POI chưa hiển thị trên giao diện | API trả trường `images`, không có component React nào đọc | task riêng, xem README gốc |
| `/ai/enhance-description` gửi mô tả quán ra nhà cung cấp AI ngoài | dev dùng `AI_PROVIDER=mock` nên chưa lộ; đổi `http` là lộ | quyết định sản phẩm |
| Người có quyền `user:update` duyệt được đơn của người khác | `username` lấy từ URL, chỉ kiểm quyền không kiểm chủ sở hữu | cần bỏ `username` khỏi URL |
| `health.py` trả chi tiết lỗi | trường `mongo_error` có thể lộ host/port (SEC-013 đã có test khoá nhưng chưa che hết) | task hardening |
| `ruff` nằm trong `requirements.txt` | công cụ dev lẫn vào dependency runtime | tách `requirements-dev.txt` |
| Chưa có Dockerfile, chưa có reverse proxy | chạy native + Mongo/Redis qua Compose | Phase 14 (PROD-005..007) |

---

## 10. Xử lý sự cố

<details>
<summary><b>PowerShell: "running scripts is disabled"</b></summary>

Chính sách thực thi script chặn file `.ps1`. Chạy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Rồi activate lại. Lệnh này chỉ đổi thiết lập cho user hiện tại, không đụng hệ thống.
</details>

<details>
<summary><b><code>uvicorn: command not found</b></summary>

Chưa activate venv, hoặc cài thiếu dependency. Kiểm tra:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Thay vì gọi `uvicorn` trực tiếp, có thể dùng `python -m uvicorn app.main:app --reload` — cách này không phụ thuộc PATH.
</details>

<details>
<summary><b><code>ModuleNotFoundError: No module named 'app'</b></summary>

Chạy uvicorn sai thư mục. Phải đứng trong `backend/`, không phải thư mục gốc:

```powershell
cd backend
uvicorn app.main:app --reload
```
</details>

<details>
<summary><b><code>/health</code> trả 503, MongoDB chưa kết nối</b></summary>

Kiểm tra container có chạy không:

```powershell
docker compose ps
docker compose logs --tail 30 mongodb
```

Nếu container không chạy: `docker compose up -d --wait`.
Nếu cổng 27017 bị chiếm bởi MongoDB cài trực tiếp trên máy: dừng dịch vụ đó, hoặc sửa cổng trong `docker-compose.yml` và `MONGODB_URI` cho khớp.
</details>

<details>
<summary><b>Cổng 8000 hoặc 5173 đã bị chiếm</b></summary>

Đổi cổng khi chạy:

```powershell
uvicorn app.main:app --reload --port 8001
```
</details>

<details>
<summary><b>Cài lại từ đầu môi trường ảo</b></summary>

```powershell
cd backend
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
</details>

---

## 11. Quy trình làm việc hằng ngày

Mỗi lần bắt đầu làm việc, cần đúng 2 terminal:

```powershell
# Terminal 1 — hạ tầng
cd <thư mục gốc repo>
docker compose up -d --wait

# Terminal 2 — API
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Trước khi commit:

```powershell
ruff check .
ruff format .
pytest -q
git status
git add backend/ && git commit
```

Hoặc chạy một lệnh cho cả repo ở thư mục gốc: `python scripts\verify.py`.
