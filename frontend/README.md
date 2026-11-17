# Frontend Web App

Giao diện React + TypeScript + Vite. Chạy **native** trên máy (không Docker hoá) để hot-reload nhanh.

> Xem [`../README.md`](../README.md) để hiểu tổng quan. Tài liệu đặc tả nằm ở `docs/` (không commit vào git theo chủ ý).

---

## 1. Yêu cầu cài đặt

| Công cụ | Phiên bản | Bắt buộc | Ghi chú |
|---|---|---|---|
| Node.js | `^20.19.0` hoặc `>=22.12.0` | Có | ràng buộc do Vite 8, nâng cao hơn sẽ bị cảnh báo |
| npm | 10 trở lên | Có | đi kèm Node.js |

> **Không dùng Node 18 trở xuống.** Vite 8 sẽ báo lỗi ngay khi chạy. Nếu máy bạn còn Node 18, hãy cài [nvm-windows](https://github.com/coreybutler/nvm-windows) rồi `nvm install 22 && nvm use 22`.

Kiểm tra trước khi bắt đầu:

```powershell
node --version
npm --version
```

Cài Node.js tại <https://nodejs.org/> (bản LTS). Nếu `node` không được nhận, khởi động lại terminal sau khi cài.

---

## 2. Cài đặt lần đầu

```powershell
cd frontend
npm install
```

Lệnh này đọc `package.json` và tạo thư mục `node_modules/`. Mất khoảng 1–3 phút tuỳ tốc độ mạng.

### `node_modules` có được commit không?

Không. `frontend/.gitignore` đã loại `node_modules`, `dist`, `dist-ssr` và các file log. Mỗi người tự `npm install` trên máy.

Dùng `npm ci` thay vì `npm install` khi bạn chỉ muốn cài đúng phiên bản đã ghim trong `package-lock.json` — dùng trong CI hoặc sau khi người khác vừa push lockfile mới.

### Kiểm tra cài đặt thành công

```powershell
npm ls --depth=0
```

---

## 3. Chạy ở chế độ phát triển

```powershell
cd frontend
npm run dev
```

Mở trình duyệt tại <http://localhost:5173>.

Output mong đợi:

```
  VITE v8.x.x  ready in 300 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h + enter to show help
```

| Địa chỉ | Nội dung |
|---|---|
| <http://localhost:5173> | ứng dụng: tab Khám phá, Quản trị, Chủ quán, Gói offline, Cài đặt |
| <http://localhost:5173/admin/login> | cổng đăng nhập và quản trị Admin riêng |
| <http://localhost:5173/owner/login> | cổng đăng nhập, đăng ký và quản lý Chủ quán riêng |

Dừng server bằng `Ctrl+C`.

Sửa bất kỳ file nào trong `src/` và trình duyệt tự cập nhật — không cần reload tay.

---

## 4. Các lệnh npm

| Lệnh | Việc nó làm | Khi nào dùng |
|---|---|---|
| `npm run dev` | chạy dev server + hot reload | hằng ngày |
| `npm run build` | kiểm tra kiểu rồi build ra `dist/` | trước khi commit hoặc deploy |
| `npm run preview` | phục vụ bản build trong `dist/` ở cổng 4173 | kiểm tra bản build |
| `npm run lint` | chạy ESLint trên toàn bộ project | trước khi commit |
| `npm test` | chạy Vitest (34 test logic thuần) | trước khi commit |
| `npm run test:e2e` | chạy Playwright (4 kịch bản, tự bật backend và frontend) | khi sửa luồng chính |
| `npm run test:e2e:pwa` | build production rồi kiểm tra app shell và POI cache khi offline, không cần PostgreSQL | khi sửa Service Worker hoặc offline |

`test:e2e:pwa` cần Chromium của Playwright hoặc Chrome đã cài (`PW_CHANNEL=chrome`).

### Kiểm tra trước khi commit

```powershell
npm run lint
npm test
npm run build
```

`npm run build` chạy `tsc -b` trước — nghĩa là **lỗi TypeScript sẽ chặn build**. Không bỏ qua lệnh này.

### Deploy

`npm run build` tạo ra `dist/` — thư mục tĩnh kèm service worker, có thể đưa lên bất kỳ host tĩnh nào phục vụ qua HTTPS. `dist/` không được commit.

---

## 5. Cấu trúc thư mục

```text
frontend/
├── .env.example             # mẫu VITE_MAPTILER_KEY — được commit
├── .gitignore               # loại node_modules, dist, test-results, file log
├── eslint.config.js         # ESLint flat config
├── index.html               # entrypoint HTML, khai báo <title>
├── package.json             # scripts + dependency
├── package-lock.json        # ghim phiên bản chính xác — ĐƯỢC commit
├── playwright.config.ts     # E2E: tự bật backend + frontend, seed dữ liệu riêng
├── tsconfig.json            # file gốc, tham chiếu 2 file con
├── tsconfig.app.json        # cấu hình TS cho mã nguồn ứng dụng
├── tsconfig.node.json       # cấu hình TS cho mã nguồn build tool
├── vite.config.ts           # Vite + PWA plugin + cấu hình Vitest
├── e2e/                     # kịch bản Playwright: khám phá, offline, chủ quán, thực địa
└── src/
    ├── main.tsx             # điểm vào: mount React vào #root
    ├── App.tsx              # khung app, chuyển tab bằng state (không dùng router)
    ├── startup.ts           # điều phối lúc khởi động: sẵn sàng rồi mới bật geofence
    ├── sw.ts                # service worker (injectManifest của Workbox)
    ├── index.css            # style toàn cục
    ├── admin/               # giao diện admin và chủ quán
    ├── analytics/           # consent, outbox ghi sự kiện, dịch vụ analytics
    ├── audio/               # phát audio theo tầng, xử lý autoplay bị chặn
    ├── components/          # MapView, LanguagePicker, ConsentBanner, OfflinePacks, Settings
    ├── geofence/            # engine thuần, prefetch, âm thanh tự động, đọc vị trí
    ├── i18n/                # tải bản dịch giao diện
    ├── offline/             # IndexedDB, nhận biết mạng, đồng bộ delta
    ├── stores/              # zustand: POI, consent
    └── telemetry/           # kênh quan sát vị trí, tách khỏi analytics
```

`package-lock.json` **phải** commit — đó là thứ bảo đảm mọi người cài cùng phiên bản. Xoá nó sẽ khiến mỗi máy ra một phiên bản khác nhau.

File `*.test.ts` đặt cạnh code nó kiểm thử, không gom vào một thư mục riêng. Vitest chỉ quét `src/**/*.test.ts` — không quét `e2e/*.spec.ts`, vì hai runner dùng chung đuôi `.spec.ts`.

### Ngôn ngữ giao diện

Các chuỗi giao diện Visitor được lưu trong `backend/static/ui/{locale}.json` và tải qua `/ui-bundles/{locale}`. Hiện có `en`, `vi`, `zh`, `ja` và `ko`; các bundle cần giữ cùng tập khóa. Lựa chọn ngôn ngữ Visitor áp dụng cho giao diện, nội dung POI và thuyết minh; người dùng mới mặc định là tiếng Anh, còn lựa chọn đã lưu trong `quan4-lang` được giữ lại. Bundle đã tải được lưu trên thiết bị để dùng lại khi ngoại tuyến.

---

## 6. Công nghệ

| Thành phần | Phiên bản | Vai trò |
|---|---|---|
| React | 19.x | thư viện giao diện |
| TypeScript | ~6.0 | kiểu tĩnh |
| Vite | ^8.3 | dev server + bundler |
| `vite-plugin-pwa` + Workbox | ^2.0 / ^7.4 | service worker, precache, chiến lược offline |
| MapLibre GL | ^6.12 | hiển thị bản đồ vector |
| `pmtiles` | ^4.5 | đọc gói bản đồ dạng `.pmtiles` khi offline |
| Zustand | ^5.0 | state của POI và consent |
| Vitest + jsdom | ^5.0 | test logic thuần |
| Playwright | ^1.64 | test E2E trên Chromium |
| ESLint + typescript-eslint | ^10.x / ^8.x | lint |
| `eslint-plugin-react-hooks` / `-refresh` | ^7.x / ^0.5 | luật cho React Hooks và Fast Refresh |

Chưa cài: router (đang chuyển tab bằng `useState` trong `App.tsx`), CSS framework (đang dùng CSS thuần), thư viện bản đồ Leaflet. Xem [Mục 8](#8-giới-hạn-và-nợ-kỹ-thuật).

---

## 7. Kết nối với backend

### Trạng thái hiện tại

Frontend **đã** gọi backend. Không có proxy: mã nguồn gọi thẳng `http://127.0.0.1:8000`.

Hai điều phải đúng cùng lúc, nếu không trình duyệt sẽ chặn request:

1. **Backend đang chạy** ở cổng `8000`.
2. **Origin của trang nằm trong danh sách CORS** của backend. `app/main.py` hiện cho phép đúng `http://localhost:5173` và `http://127.0.0.1:5173` — đó là lý do `npm run dev` phải để cổng mặc định `5173`.

Địa chỉ API hiện được viết cứng ở nhiều chỗ (`src/startup.ts`, `src/offline/sync.ts`, `src/audio/playback.ts`, `src/i18n/bundles.ts`, `src/analytics/service.ts`, `src/telemetry/location.ts`, `src/admin/api.ts`, `src/components/useMapPack.ts`). Xem [Mục 8](#8-giới-hạn-và-nợ-kỹ-thuật).

Cookie phiên admin được backend đặt với `SameSite=Lax`; hai origin cùng site nên vẫn gửi kèm.

### Biến môi trường

Chỉ có một biến: `VITE_MAPTILER_KEY`.

```powershell
Copy-Item .env.example .env.local
```

Để trống thì bản đồ dùng style Liberty miễn phí của OpenFreeMap; có key thì
`MapView` dùng style cloud của MapTiler. Nếu tài nguyên MapTiler bị từ chối
(ví dụ key/domain không hợp lệ), ứng dụng tự chuyển sang OpenFreeMap.

Quy tắc của Vite: chỉ biến có tiền tố `VITE_` mới được đọc trong mã nguồn, và **giá trị đó được nhúng vào bundle gửi tới trình duyệt** — tức là ai cũng thấy. Key MapTiler vốn dĩ là công khai phía client, nên phải giới hạn theo domain ở phía MapTiler (task SEC-005). Không bao giờ đặt secret thật vào biến `VITE_`.

Khi deploy lên Vercel, thêm `VITE_MAPTILER_KEY` trong Project Settings → Environment Variables, rồi cho phép domain production của ứng dụng ở phần HTTP referrers trong MapTiler. Nếu cần bản Preview cũng dùng MapTiler, thêm domain Preview tương ứng. Sau khi đổi biến, phải tạo deployment mới.

### Chạy E2E

```powershell
npm run test:e2e
```

`playwright.config.ts` tự bật backend (`uvicorn`) và dev server, rồi `e2e/global-setup.ts` nạp dữ liệu vào PostgreSQL database riêng `quan4_culinary_tourism_e2e` bằng `backend/scripts/seed_e2e.py`. Database này phải được tạo và provision schema/role `ADMIN` trước. Có thể chọn tên khác qua `E2E_DB_NAME`; seed script chỉ chạy với tên kết thúc bằng `_e2e` và xóa dữ liệu trong database đó. Đặt `E2E_SKIP_WEBSERVER=1` khi hai server đã chạy sẵn (CI làm vậy).

---

## 8. Giới hạn và nợ kỹ thuật

| Vấn đề | Chi tiết | Nên sửa ở |
|---|---|---|
| Địa chỉ API viết cứng ở 8 chỗ | đổi cổng hoặc deploy thật thì phải sửa từng file | gom vào một module cấu hình, đọc `VITE_API_BASE` |
| Không có proxy | phụ thuộc CORS của backend đúng danh sách origin | thu hẹp/thu rộng CORS khi có domain thật (SEC-003) |
| Không có router | 5 tab dùng `useState` trong `App.tsx` | khi cần điều hướng có URL, ví dụ gửi link sâu vào một quán |
| CSS thuần | style nằm trong `index.css`, không có CSS framework | khi giao diện phức tạp hơn |
| ESLint chưa bật type-aware rules | đang dùng `tseslint.configs.recommended`; bản nâng cao cần `parserOptions.project` | khi codebase lớn dần |
| Không có path alias | đang import tương đối (`../components/...`) | khi cấu trúc thư mục sâu hơn |
| Chưa có hình minh hoạ POI | `icons: []` trong manifest PWA | trước khi demo trước giám khảo |
| E2E chỉ chạy Chromium | `playwright.config.ts` khai báo một project | khi cần kiểm trên Safari/Firefox |

---

## 9. Xử lý sự cố

<details>
<summary><b><code>npm</code> hoặc <code>node</code> không được nhận</b></summary>

Cài Node.js, mở lại terminal, kiểm tra `node --version`. Kiểm tra Node có nằm trong PATH không:

```powershell
$env:Path -split ';' | Select-String 'nodejs'
```
</details>

<details>
<summary><b>Vite báo lỗi phiên bản Node</b></summary>

Vite 8 cần `^20.19.0 || >=22.12.0`. Kiểm tra:

```powershell
node --version
```

Dùng [nvm-windows](https://github.com/coreybutler/nvm-windows) để cài và chuyển phiên bản:

```powershell
nvm install 22
nvm use 22
```
</details>

<details>
<summary><b>Cổng 5173 đã bị chiếm</b></summary>

Vite tự chọn cổng trống kế tiếp và in ra cổng mới. Ép cổng cụ thể:

```powershell
npm run dev -- --port 5174
```
</details>

<details>
<summary><b><code>npm run build</code> lỗi TypeScript</b></summary>

Báo lỗi kiểu dữ liệu sẽ chặn build. Xem file và dòng lỗi trong output. Kiểm tra nhanh mà không build:

```powershell
npx tsc -b --noEmit
```
</details>

<details>
<summary><b>Dependency lỗi sau khi kéo code mới</b></summary>

Thường là do `package-lock.json` đã cập nhật. Cài lại từ đầu:

```powershell
Remove-Item -Recurse -Force node_modules
npm ci
```

Nếu vẫn lỗi, xoá cache rồi thử lại:

```powershell
npm cache clean --force
npm install
```
</details>

<details>
<summary><b>Sửa <code>eslint.config.js</code> mà ESLint không nhận thay đổi</b></summary>

Kiểm tra đang lint đúng thư mục không:

```powershell
npx eslint src --debug
```
</details>

---

## 10. Quy trình làm việc hằng ngày

```powershell
# Terminal 1 — hạ tầng (chỉ khi backend cần MongoDB/Redis)
cd <thư mục gốc repo>
docker compose up -d --wait

# Terminal 2 — API
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload

# Terminal 3 — web app
cd frontend
npm run dev
```

Trước khi commit:

```powershell
npm run lint
npm test
npm run build
git status
git add frontend/ && git commit
```

Hoặc chạy một lệnh cho cả repo ở thư mục gốc: `python scripts\verify.py`.
