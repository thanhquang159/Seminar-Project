from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import kiem_tra_bi_mat, settings
from app.csrf import ChanGhiOrigin
from app.db import close_db, connect_db, get_database
from app.limits import GioiHanBody
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
        print(f"[startup] MongoDB connected ✅ ({len(collections)} collections)")
        await dam_bao_roles(db)
        quan_ly_tasks.gan_db(db)
        await quan_ly_tasks.dam_bao_index()
        dem = await quan_ly_tasks.khoi_phuc()
        if dem:
            print(f"[startup] Phục hồi {dem} tác vụ audio treo.")
        # Tầng 4: index observability + analytics rồi mới bật worker nền.
        await dam_bao_index_runtime(db)
        await dam_bao_index_analytics(db)
        analytics_worker.gan_db(db)
        await analytics_worker.bat_dau()
    except Exception as e:
        print(f"[startup] MongoDB chưa sẵn sàng: {e}")
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

# Chặn thao tác ghi từ origin lạ (SEC-004). Đăng sau CORS nên nằm trong CORS:
# 403 vẫn mang header CORS để trình duyệt đọc được và báo đúng lý do.
app.add_middleware(ChanGhiOrigin)

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

THU_MUC_STATIC = Path(__file__).resolve().parents[2] / "static"
THU_MUC_STATIC.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(THU_MUC_STATIC)), name="static")


@app.get("/")
async def root():
    return {"status": "ok", "service": "amds-api"}