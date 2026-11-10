"""Ghi audit log vào schema PostgreSQL hiện có, không lưu dữ liệu bí mật."""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _phan_tich_tai_nguyen(resource: str) -> tuple[str, str | None]:
    resource_type, separator, identifier = resource.partition(":")
    if not separator:
        return "application", None
    try:
        return resource_type or "application", str(UUID(identifier))
    except ValueError:
        return resource_type or "application", None


async def ghi_audit(db: AsyncSession, username: str, hanh_dong: str, tai_nguyen: str) -> None:
    """Write action/actor/resource and retain the original resource in JSONB."""
    resource_type, resource_id = _phan_tich_tai_nguyen(tai_nguyen)
    await db.execute(
        text(
            """
            INSERT INTO audit_logs
                (actor_user_id, action, resource_type, resource_id, after_data)
            VALUES (
                (SELECT id FROM users WHERE lower(email) = lower(:username) LIMIT 1),
                :action,
                :resource_type,
                CAST(:resource_id AS uuid),
                CAST(:after_data AS jsonb)
            )
            """
        ),
        {
            "username": username,
            "action": hanh_dong,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "after_data": json.dumps({"resource": tai_nguyen}),
        },
    )
