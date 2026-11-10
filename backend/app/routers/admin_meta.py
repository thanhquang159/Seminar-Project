"""Read roles and audit history from the existing PostgreSQL schema."""

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import DbSession, doi_quyen

router = APIRouter(prefix="/admin", tags=["admin-quan-tri"])

DuocXemRole = doi_quyen("role:read")
DuocXemAudit = doi_quyen("audit:read")


@router.get("/roles", summary="Liệt kê roles")
async def liet_ke_roles(_user: dict = DuocXemRole, db: AsyncSession = DbSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT r.code, r.name, p.code AS permission_code
            FROM roles AS r
            LEFT JOIN role_permissions AS rp ON rp.role_id = r.id
            LEFT JOIN permissions AS p ON p.id = rp.permission_id
            ORDER BY r.code, p.code
            """
        )
    )
    roles: dict[str, dict] = {}
    for row in result.mappings().all():
        code = row["code"]
        role = roles.setdefault(code, {"name": code, "priority": None, "permissions": []})
        if row["permission_code"] is not None:
            role["permissions"].append(row["permission_code"])
    return list(roles.values())


@router.get("/audit-logs", summary="Xem audit log")
async def xem_audit(_user: dict = DuocXemAudit, db: AsyncSession = DbSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT l.action, u.email AS username,
                   COALESCE(
                       l.after_data ->> 'resource',
                       l.resource_type || ':' || COALESCE(l.resource_id::text, '')
                   ) AS resource,
                   l.created_at
            FROM audit_logs AS l
            LEFT JOIN users AS u ON u.id = l.actor_user_id
            ORDER BY l.created_at DESC
            LIMIT 100
            """
        )
    )
    rows = result.mappings().all()
    return [
        {
            "action": row["action"],
            "username": row["username"],
            "resource": row["resource"],
            "timestamp": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]
