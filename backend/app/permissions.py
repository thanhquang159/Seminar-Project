"""Đọc quyền từ quan hệ roles/permissions hiện có trong PostgreSQL."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.postgres import AsyncSessionLocal

_PERMISSIONS_FOR_API = {
    "analytics.read": {"analytics:view"},
    "audit_logs.read": {"audit:read"},
    "owner_registrations.review": {"user:update"},
    "pois.manage": {"poi:create", "poi:delete", "poi:update"},
    "pois.publish": {"poi:publish"},
    "pois.read": {"poi:read"},
    "roles.manage": {"role:read"},
    "submissions.review": {"poi:approve"},
    "users.manage": {"user:update"},
}


def _quyen_ung_dung(codes: list[str]) -> list[str]:
    """Map database permission codes to the permission identifiers used by routes."""
    expanded: list[str] = []
    seen: set[str] = set()
    for code in codes:
        for permission in sorted(_PERMISSIONS_FOR_API.get(code, {code})):
            if permission not in seen:
                expanded.append(permission)
                seen.add(permission)
    return expanded


async def dam_bao_roles(db: AsyncSession | None = None) -> None:
    """Compat no-op: inspect existing roles, never seed or mutate the live schema."""
    if db is None:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT id FROM roles LIMIT 0"))
        return
    await db.execute(text("SELECT id FROM roles LIMIT 0"))


async def quyen_cua_role(db: AsyncSession | None, ten_role: str) -> list[str]:
    """Return persisted permission codes for a role; unknown roles have no grants."""
    if db is None:
        async with AsyncSessionLocal() as session:
            return await quyen_cua_role(session, ten_role)

    result = await db.execute(
        text(
            """
            SELECT DISTINCT p.code
            FROM roles AS r
            JOIN role_permissions AS rp ON rp.role_id = r.id
            JOIN permissions AS p ON p.id = rp.permission_id
            WHERE r.code = :role_code OR r.name = :role_name
            ORDER BY p.code
            """
        ),
        {"role_code": ten_role, "role_name": ten_role},
    )
    return _quyen_ung_dung(list(result.scalars().all()))


async def quyen_cua_user(db: AsyncSession, username: str) -> list[str]:
    """Union grants from all roles assigned to the user through user_roles."""
    result = await db.execute(
        text(
            """
            SELECT DISTINCT p.code
            FROM users AS u
            JOIN user_roles AS ur ON ur.user_id = u.id
            JOIN role_permissions AS rp ON rp.role_id = ur.role_id
            JOIN permissions AS p ON p.id = rp.permission_id
            WHERE lower(u.email) = lower(:username)
            ORDER BY p.code
            """
        ),
        {"username": username},
    )
    return _quyen_ung_dung(list(result.scalars().all()))
