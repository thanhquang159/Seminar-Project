from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.api.health import router as health_router
from app.api.pois import router as poi_router
from app.core.config import kiem_tra_bi_mat, settings
from app.csrf import ChanGhiOrigin
from app.headers import HeaderBaoMat
from app.limits import GioiHanBody
from app.log_setup import dat_cau_hinh_log
from app.postgres import close_db, connect_db
from app.routers.admin_analytics import router as admin_analytics_router
from app.routers.admin_auth import router as admin_auth_router
from app.routers.admin_meta import router as admin_meta_router
from app.routers.admin_pois import router as admin_pois_router
from app.routers.admin_users import router as admin_users_router
from app.routers.ai import router as ai_router
from app.routers.analytics import router as analytics_router
from app.routers.audio import router as audio_router
from app.routers.health import router as root_health_router
from app.routers.i18n import router as ui_bundle_router
from app.routers.localizations import router as localizations_router
from app.routers.maps import router as maps_router
from app.routers.owner import router as owner_router
from app.routers.owner_menus import router as owner_menus_router
from app.routers.runtime_observability import router as runtime_observability_router
from app.routers.warmup import router as warmup_router
from app.services.tasks import quan_ly_tasks

dat_cau_hinh_log()


@asynccontextmanager
async def lifespan(app: FastAPI):
    kiem_tra_bi_mat()
    try:
        await connect_db()
        await quan_ly_tasks.start()
        yield
    finally:
        await quan_ly_tasks.stop()
        await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Quan4 Culinary Tourism",
    version="1.0.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)

app.add_middleware(GioiHanBody)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(ChanGhiOrigin)
app.add_middleware(HeaderBaoMat)
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(health_router, prefix="/api/v1")
app.include_router(root_health_router)
app.include_router(poi_router)
app.include_router(ui_bundle_router)
app.include_router(admin_auth_router)
app.include_router(admin_meta_router)
app.include_router(admin_pois_router)
app.include_router(admin_users_router)
app.include_router(owner_router)
app.include_router(owner_menus_router)
app.include_router(analytics_router)
app.include_router(admin_analytics_router)
app.include_router(runtime_observability_router)
app.include_router(ai_router)
app.include_router(audio_router)
app.include_router(localizations_router)
app.include_router(warmup_router)
app.include_router(maps_router)

static_dir = Path(__file__).resolve().parents[1] / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return {"message": "Welcome to Quan4 Culinary Tourism API", "status": "running"}
