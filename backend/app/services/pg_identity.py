"""Helpers for resolving authenticated users against the PostgreSQL schema."""

from collections.abc import Mapping
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def user_label(user: Mapping[str, object]) -> str:
    """Return the stable login identifier expected by the audit API."""
    for key in ("username", "email"):
        value = user.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


async def resolve_user_id(
    db: AsyncSession,
    user: Mapping[str, object],
    *,
    required: bool = True,
) -> UUID | None:
    """Resolve UUID claims directly, or look up the user's email/login identifier."""
    for key in ("id", "user_id", "sub"):
        value = user.get(key)
        if value is not None:
            try:
                return UUID(str(value))
            except (TypeError, ValueError, AttributeError):
                continue

    identity = user_label(user)
    if identity:
        result = await db.execute(
            text("SELECT id FROM users WHERE lower(email) = lower(:identity) LIMIT 1"),
            {"identity": identity},
        )
        user_id = result.scalar_one_or_none()
        if user_id is not None:
            return UUID(str(user_id))

    if required:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ")
    return None
