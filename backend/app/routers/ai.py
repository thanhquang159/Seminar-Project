"""AI mô tả: owner 10 lượt/ngày, admin không giới hạn, timeout 30s."""

from datetime import UTC, datetime
from time import monotonic
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import YeuCauDangNhap
from app.core.config import settings
from app.postgres import get_db
from app.services.ai_svc import lay_provider

router = APIRouter(prefix="/ai", tags=["ai"])

GIOI_HAN_OWNER_NGAY = 10


class LamDepYeuCau(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


async def _tai_khoan(db: AsyncSession, user: dict) -> dict | None:
    """Resolve the authenticated principal against the PostgreSQL users table."""
    user_id = user.get("id") or user.get("user_id")
    if user_id:
        try:
            normalized_id = UUID(str(user_id))
        except (ValueError, TypeError, AttributeError):
            return None
        result = await db.execute(
            text("SELECT id, owner_verified_at FROM users WHERE id = :user_id"),
            {"user_id": normalized_id},
        )
    else:
        identity = user.get("email") or user.get("username")
        if not identity:
            return None
        result = await db.execute(
            text(
                "SELECT id, owner_verified_at FROM users "
                "WHERE LOWER(email) = LOWER(:identity) LIMIT 1"
            ),
            {"identity": str(identity)},
        )
    return result.mappings().first()


async def con_luot(db: AsyncSession, user_id: UUID) -> bool:
    """Atomically consume one of the owner's ten daily AI requests."""
    result = await db.execute(
        text(
            """
            INSERT INTO ai_usage_daily (user_id, usage_date, request_count, daily_limit, updated_at)
            VALUES (:user_id, :usage_date, 1, :daily_limit, :now)
            ON CONFLICT (user_id, usage_date)
            DO UPDATE SET request_count = ai_usage_daily.request_count + 1,
                updated_at = EXCLUDED.updated_at
            WHERE ai_usage_daily.request_count < ai_usage_daily.daily_limit
            RETURNING request_count
            """
        ),
        {
            "user_id": user_id,
            "usage_date": datetime.now(UTC).date(),
            "daily_limit": GIOI_HAN_OWNER_NGAY,
            "now": datetime.now(UTC),
        },
    )
    consumed = result.mappings().first() is not None
    await db.commit()
    return consumed


async def _start_request(db: AsyncSession, user_id: UUID | None) -> UUID:
    result = await db.execute(
        text(
            "INSERT INTO ai_advisor_requests (user_id, provider, request_type, status) "
            "VALUES (:user_id, :provider, 'enhance_description', 'pending') RETURNING id"
        ),
        {"user_id": user_id, "provider": settings.AI_PROVIDER},
    )
    request = result.mappings().one()
    await db.commit()
    return request["id"]


async def _finish_request(
    db: AsyncSession,
    request_id: UUID,
    status: str,
    elapsed_ms: int,
    error_type: str | None = None,
) -> None:
    await db.execute(
        text(
            "UPDATE ai_advisor_requests SET status = :status, latency_ms = :latency_ms, "
            "error_message = :error_message, completed_at = :completed_at WHERE id = :request_id"
        ),
        {
            "request_id": request_id,
            "status": status,
            "latency_ms": max(0, elapsed_ms),
            # Store only an exception class, not provider error text that might contain secrets.
            "error_message": error_type,
            "completed_at": datetime.now(UTC),
        },
    )
    await db.commit()


@router.post("/enhance-description", summary="AI viết lại mô tả quán")
async def lam_dep_mo_ta(
    body: LamDepYeuCau,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauDangNhap,
) -> dict:
    account = await _tai_khoan(db, user)
    if user.get("role") == "poi_owner":
        if not account or account.get("owner_verified_at") is None:
            raise HTTPException(status_code=403, detail="Tài khoản chủ quán chưa được duyệt")
        if not await con_luot(db, account["id"]):
            raise HTTPException(status_code=429, detail="Hết 10 lượt AI hôm nay")

    user_id = account["id"] if account else None
    request_id = await _start_request(db, user_id)
    started = monotonic()
    try:
        ket_qua = await lay_provider().viet_lai(body.text)
    except RuntimeError as exc:
        status = "timeout" if "30 giây" in str(exc).lower() else "failed"
        await _finish_request(
            db, request_id, status, int((monotonic() - started) * 1000), type(exc).__name__
        )
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except Exception as exc:
        await _finish_request(
            db, request_id, "failed", int((monotonic() - started) * 1000), type(exc).__name__
        )
        raise
    await _finish_request(db, request_id, "completed", int((monotonic() - started) * 1000))
    return {"text": ket_qua}
