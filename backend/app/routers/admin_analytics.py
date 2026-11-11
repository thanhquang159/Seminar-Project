"""Admin dashboard: consent-gated analytics and separate runtime diagnostics."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import doi_quyen
from app.postgres import get_db
from app.services import runtime_observability as ro
from app.services.analytics_read import thong_ke

router = APIRouter(prefix="/admin", tags=["admin-analytics"])

# Cả hai nhóm số liệu đều đòi cùng một quyền xem analytics.
DuocXemAnalytics = doi_quyen("analytics:view")

CUA_SO_RUNTIME = ("24h", "7d")
TZ_VIETNAM = timezone(timedelta(hours=7))


@router.get("/analytics/summary", summary="Tổng quan analytics hôm nay")
async def tong_quan(
    db: Annotated[AsyncSession, Depends(get_db)],
    ngay: str | None = None,
    so_ngay: int = Query(default=7, ge=1, le=30),
    _user: dict = DuocXemAnalytics,
) -> dict:
    metric_date = ngay or datetime.now(TZ_VIETNAM).strftime("%Y-%m-%d")
    return await thong_ke(db, metric_date, so_ngay)


@router.get("/ai-usage", summary="Tổng quan mức sử dụng AI")
async def tong_quan_ai(
    db: Annotated[AsyncSession, Depends(get_db)],
    so_ngay: int = Query(default=7, ge=1, le=30),
    _user: dict = DuocXemAnalytics,
) -> dict:
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=so_ngay - 1)
    result = await db.execute(
        text(
            """
            SELECT usage_date::text AS metric_date,
                   SUM(request_count)::integer AS requests,
                   SUM(daily_limit)::integer AS daily_limit,
                   COUNT(*) FILTER (WHERE request_count > 0)::integer AS owners
            FROM ai_usage_daily
            WHERE usage_date BETWEEN :start_date AND :end_date
            GROUP BY usage_date
            ORDER BY usage_date
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    )
    return {"days": so_ngay, "daily": [dict(row) for row in result.mappings().all()]}


@router.get("/runtime-observability/location", summary="Cửa sổ quan sát vị trí runtime")
async def cua_so_runtime(
    db: Annotated[AsyncSession, Depends(get_db)],
    window: str = "24h",
    _user: dict = DuocXemAnalytics,
) -> dict:
    if window not in CUA_SO_RUNTIME:
        window = "24h"
    return await ro.doc_cua_so(db, window)
