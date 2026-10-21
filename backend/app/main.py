import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.config import kiem_tra_bi_mat, settings
from app.csrf import ChanGhiOrigin
from app.db import close_db, connect_db, get_database
from app.headers import HeaderBaoMat
from app.limits import GioiHanBody
from app.log_setup import dat_cau_hinh_log
from app.permissions import dam_bao_roles
from app.routers import (
    admin_analytics,
    admin_auth,
    admin_meta,
    admin_pois,
    ai,
    analytics,
    audio,
    geo,
    health,
    i18n,
    localizations,
    maps,
    owner,
    poi,
    runtime_observability,
    warmup,
)
from app.services.analytics_read import analytics_worker
from app.services.analytics_svc import dam_bao_index as dam_bao_index_analytics
from app.services.runtime_observability import dam_bao_index as dam_bao_index_runtime
from app.services.tasks import quan_ly_tasks

log = logging.getLogger("app")

# Bọc log ngay lúc nạp module (không đợi vào lifespan) để access log của uvicorn —
# vào trước mọi request — cũng nằm trong bộ che (SEC-006).
dat_cau_hinh_log()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail-fast cấu hình trước khi mở kết nối.
    kiem_tra_bi_mat()
    # Startup — fail-soft để backend vẫn start được khi Mongo chưa lên
    try:
        await connect_db()
        # Gọi thử get_database() + list_collection_names() để xác nhận
        # kết nối + đọc DB hoạt động, đúng như Verification của DB-001.
        db = get_database()
        collections = await db.list_collection_names()
        log.info("[startup] MongoDB connected ✅ (%d collections)", len(collections))
        await dam_bao_roles(db)
        quan_ly_tasks.gan_db(db)
        await quan_ly_tasks.dam_bao_index()
        dem = await quan_ly_tasks.khoi_phuc()
        if dem:
            log.info("[startup] Phục hồi %d tác vụ audio treo.", dem)
        # Tầng 4: index observability + analytics rồi mới bật worker nền.
        await dam_bao_index_runtime(db)
        await dam_bao_index_analytics(db)
        analytics_worker.gan_db(db)
        await analytics_worker.bat_dau()
    except Exception as e:
        # Nội dung lỗi driver có thể chứa DSN (kèm mật khẩu) — bộ che SEC-006 xử lý.
        log.warning("[startup] MongoDB chưa sẵn sàng: %s", e)
    yield
    # Shutdown
    await analytics_worker.dung()
    await close_db()


app = FastAPI(
    title="AMDS API",
    version="0.1.0",
    lifespan=lifespan,
)

# Chặn body quá lớn (SEC-001). Đăng TRƯỚC CORS nên CORS vẫn là lớp ngoài:
# 413 phải mang header CORS cho browser đọc được lỗi.
app.add_middleware(GioiHanBody)

# Cookie cần origin cụ thể, không dùng "*" kèm credentials được (SEC-003).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    # Đủ dùng cho REST; không mở tất cả để bớt bề mặt.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Chỉ hai header API thật sự dùng. `["*"]` kèm credentials bị trình duyệt
    # bỏ qua, và nếu trình duyệt gửi header lạ thì cấu hình đó đẩy lại cả danh
    # sách header đó — tức cho phép thứ không cần.
    allow_headers=["Content-Type", "Authorization"],
)

# Chặn thao tác ghi từ origin lạ (SEC-004). `add_middleware` insert(0):
# đăng SAU CORS nên lớp này nằm NGOÀI CORS (nhãn "nằm trong CORS" ở bản cũ
# là sai). Hành vi vẫn đúng ý đồ: 403 chỉ dành cho origin KHÔNG nằm trong
# allowlist, mà origin đó CORS không bao giờ cấp ACAO — trình duyệt đọc
# response dưới dạng opaque là chính xác, không lộ lý do cho origin lạ.
# Origin hợp lệ không bao giờ rơi vào 403 này.
app.add_middleware(ChanGhiOrigin)

# Header bảo mật (SEC-009). Đăng cuối nên là lớp NGOÀI CÙNG (insert(0)) —
# đúng mục đích: 403 của ChanGhiOrigin hay 413 của GioiHanBody sinh ra
# bên dưới vẫn đi qua đây và nhận đủ nosniff/CSP.
app.add_middleware(HeaderBaoMat)

# Nén JSON trả về (PERF-003). Số đo baseline (53 POI): load-all 21 371 byte
# thô -> 1 474 byte gzip (-93%); trạng thái không đổi đã có ETag 304 về 0
# byte. Đăng cuối nên bọc ngoài cùng — nén được cả response lỗi. Starlette
# tự loại audio/*, image/*, text/event-stream (MP3 đã nén sẵn, SSE phải
# stream) và bỏ qua body < 500 byte (delta rỗng 63 byte không đụng tới);
# riêng gzip luôn thêm `Vary: Accept-Encoding` nên cache không tráo nhầm
# bản nén/chưa nén.
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(health.router)
app.include_router(geo.router)
app.include_router(poi.router)
app.include_router(admin_auth.router)
app.include_router(admin_pois.router)
app.include_router(admin_meta.router)
app.include_router(localizations.router)
app.include_router(warmup.router)
app.include_router(audio.router)
app.include_router(i18n.router)
app.include_router(maps.router)
app.include_router(owner.router)
app.include_router(ai.router)
app.include_router(analytics.router)
app.include_router(runtime_observability.router)
app.include_router(admin_analytics.router)

THU_MUC_STATIC = Path(__file__).resolve().parents[1] / "static"
THU_MUC_STATIC.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(THU_MUC_STATIC)), name="static")


@app.get("/")
async def root():
    return {"status": "ok", "service": "amds-api"}