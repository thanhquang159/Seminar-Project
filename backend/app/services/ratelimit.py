"""Giới hạn tần suất dùng chung qua ``localization_request_logs`` PostgreSQL."""

import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GIOI_HAN = 30
CUA_SO_PHUT = 10


async def dam_bao_index_ratelimit(db: AsyncSession) -> None:
    """Không tạo DDL lúc runtime; dùng schema/index hiện có."""
    return None


def khoa_cho(request: Request, user: dict | None = None) -> str:
    """Đếm theo user đăng nhập, ẩn danh thì theo IP."""
    if user and user.get("username"):
        return f"user:{user['username']}"
    ip = request.client.host if request.client else "la"
    return f"ip:{ip}"


def _giay_cho_lai(cu: dict, cua_so_phut: int) -> int:
    """Còn bao lâu nữa thì request cũ trượt khỏi cửa sổ, tối thiểu 1 giây."""
    luc = cu.get("requested_at", cu.get("luc"))
    if luc is None:
        return cua_so_phut * 60
    if luc.tzinfo is None:
        luc = luc.replace(tzinfo=UTC)
    remaining = (luc + timedelta(minutes=cua_so_phut) - datetime.now(UTC)).total_seconds()
    return max(1, int(remaining))


async def cho_phep(
    db: AsyncSession,
    khoa: str,
    duong_dan: str,
    gioi_han: int = GIOI_HAN,
    cua_so_phut: int = CUA_SO_PHUT,
    ghi_nhan: bool = True,
) -> tuple[bool, int]:
    """Đếm request được phép trong cửa sổ trượt rồi ghi nhận, nếu cần."""
    await dam_bao_index_ratelimit(db)
    now = datetime.now(UTC)
    threshold = now - timedelta(minutes=cua_so_phut)
    result = await db.execute(
        text(
            """
            SELECT count(*)
            FROM localization_request_logs
            WHERE operation = :operation
              AND requested_at >= :threshold
              AND was_allowed IS TRUE
              AND request_metadata->>'rate_limit_key' = :rate_limit_key
            """
        ),
        {
            "operation": duong_dan,
            "threshold": threshold,
            "rate_limit_key": khoa,
        },
    )
    count = int(result.scalar_one())
    if count >= gioi_han:
        oldest = await db.execute(
            text(
                """
                SELECT requested_at
                FROM localization_request_logs
                WHERE operation = :operation
                  AND requested_at >= :threshold
                  AND was_allowed IS TRUE
                  AND request_metadata->>'rate_limit_key' = :rate_limit_key
                ORDER BY requested_at
                LIMIT 1
                """
            ),
            {
                "operation": duong_dan,
                "threshold": threshold,
                "rate_limit_key": khoa,
            },
        )
        row = oldest.mappings().first()
        return (
            False,
            _giay_cho_lai(dict(row), cua_so_phut) if row else cua_so_phut * 60,
        )
    if ghi_nhan:
        metadata = json.dumps({"rate_limit_key": khoa})
        await db.execute(
            text(
                """
                INSERT INTO localization_request_logs
                    (operation, requested_at, was_allowed, request_metadata)
                VALUES (:operation, :requested_at, true, CAST(:metadata AS jsonb))
                """
            ),
            {
                "operation": duong_dan,
                "requested_at": now,
                "metadata": metadata,
            },
        )
        await db.commit()
    return True, 0


async def kiem_tra(db: AsyncSession, khoa: str, duong_dan: str) -> None:
    """Quá ngưỡng thì 429 kèm Retry-After."""
    ok, wait_seconds = await cho_phep(db, khoa, duong_dan)
    if not ok:
        raise HTTPException(
            status_code=429,
            detail="Quá nhiều yêu cầu, thử lại sau",
            headers={"Retry-After": str(wait_seconds)},
        )
