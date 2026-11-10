"""Admin dashboard: consent-gated analytics and separate runtime diagnostics."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import doi_quyen
from app.postgres import get_db
from app.services import runtime_observability as ro
from app.services.analytics_read import thong_ke

router = APIRouter(prefix="/admin", tags=["admin-analytics"])

# Cả hai nhóm số liệu đều đòi cùng một quyền xem analytics.
DuocXemAnalytics = doi_quyen("analytics:view")

CUA_SO_RUNTIME = ("24h", "7d")


@router.get("/analytics/summary", summary="Tổng quan analytics hôm nay")
async def tong_quan(
    db: Annotated[AsyncSession, Depends(get_db)],
    ngay: str | None = None,
    so_ngay: int = 7,
    _user: dict = DuocXemAnalytics,
) -> dict:
    metric_date = ngay or datetime.now(UTC).strftime("%Y-%m-%d")
    so_ngay = max(1, min(so_ngay, 30))
    return await thong_ke(db, metric_date, so_ngay)


@router.get("/runtime-observability/location", summary="Cửa sổ quan sát vị trí runtime")
async def cua_so_runtime(
    db: Annotated[AsyncSession, Depends(get_db)],
    window: str = "24h",
    _user: dict = DuocXemAnalytics,
) -> dict:
    if window not in CUA_SO_RUNTIME:
        window = "24h"
    return await ro.doc_cua_so(db, window)
