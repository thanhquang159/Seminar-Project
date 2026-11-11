"""Administrative user and role permission management."""

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ghi_audit
from app.auth import DbSession, doi_quyen

router = APIRouter(prefix="/admin", tags=["admin-users"])

DuocXemUsers = doi_quyen("users.read")
DuocSuaUsers = doi_quyen("user:update")
DuocSuaRoles = doi_quyen("role:read")

_SYSTEM_ROLE_CODES = {"ADMIN", "OWNER", "SUPER_ADMIN", "POI_OWNER"}
_ADMIN_PERMISSION_CODES = {
    "analytics.read",
    "audit_logs.read",
    "owner_registrations.review",
    "pois.manage",
    "pois.publish",
    "roles.manage",
    "runtime.read",
    "submissions.review",
    "users.manage",
    "users.read",
    "role:read",
    "user:update",
}


class UserSummary(BaseModel):
    id: UUID
    email: str
    full_name: str
    account_status: str
    role_code: str | None
    role_name: str | None


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_status: Literal["pending", "active", "rejected"] | None = None
    role_code: str | None = Field(default=None, min_length=1, max_length=64)


class UserUpdateResult(BaseModel):
    id: UUID
    account_status: str
    role_code: str | None


class RolePermissionsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission_codes: list[str] = Field(max_length=100)


class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permission_codes: list[str] = Field(default_factory=list, max_length=100)


class RolePermissionsResult(BaseModel):
    role_code: str
    permission_codes: list[str]


class RoleCreateResult(BaseModel):
    role_code: str
    name: str
    description: str | None
    permission_codes: list[str]


@router.get("/users", summary="Liệt kê tài khoản")
async def list_users(
    _user: dict = DuocXemUsers,
    db: AsyncSession = DbSession,
) -> list[UserSummary]:
    result = await db.execute(
        text(
            """
            SELECT u.id, u.email, u.full_name, u.account_status,
                   assigned_role.code AS role_code, assigned_role.name AS role_name
            FROM users AS u
            LEFT JOIN LATERAL (
                SELECT r.code, r.name
                FROM user_roles AS ur
                JOIN roles AS r ON r.id = ur.role_id
                WHERE ur.user_id = u.id
                ORDER BY r.code
                LIMIT 1
            ) AS assigned_role ON TRUE
            ORDER BY lower(u.email), u.id
            """
        )
    )
    return [UserSummary.model_validate(row) for row in result.mappings().all()]


@router.post("/roles", status_code=201, summary="Tạo vai trò tùy chỉnh")
async def create_role(
    body: RoleCreate,
    db: AsyncSession = DbSession,
    user: dict = DuocSuaRoles,
) -> RoleCreateResult:
    if body.code.upper() in _SYSTEM_ROLE_CODES:
        raise HTTPException(status_code=403, detail="Không thể tạo mã vai trò hệ thống")
    role_name = body.name.strip()
    if not role_name:
        raise HTTPException(status_code=422, detail="Tên vai trò không được để trống")
    permission_codes = sorted(set(body.permission_codes))
    if any(not code.strip() or len(code) > 100 for code in permission_codes):
        raise HTTPException(status_code=422, detail="Mã permission không hợp lệ")
    if set(permission_codes) & _ADMIN_PERMISSION_CODES:
        raise HTTPException(status_code=403, detail="Không thể cấp permission quản trị")

    permission_rows: list[Mapping[str, object]] = []
    if permission_codes:
        permission_result = await db.execute(
            text("SELECT id, code FROM permissions WHERE code = ANY(:permission_codes)"),
            {"permission_codes": permission_codes},
        )
        permission_rows = permission_result.mappings().all()
        unknown_codes = sorted(
            set(permission_codes) - {str(row["code"]) for row in permission_rows}
        )
        if unknown_codes:
            raise HTTPException(
                status_code=422,
                detail={"message": "Permission không tồn tại", "permission_codes": unknown_codes},
            )

    role_result = await db.execute(
        text(
            """
            INSERT INTO roles (code, name, description, is_system, created_at, updated_at)
            VALUES (:code, :name, :description, FALSE, now(), now())
            ON CONFLICT (code) DO NOTHING
            RETURNING id, code
            """
        ),
        {
            "code": body.code,
            "name": role_name,
            "description": body.description,
        },
    )
    role = role_result.mappings().one_or_none()
    if role is None:
        raise HTTPException(status_code=409, detail="Mã vai trò đã tồn tại")

    for permission in permission_rows:
        await db.execute(
            text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (:role_id, :permission_id)
                """
            ),
            {"role_id": role["id"], "permission_id": permission["id"]},
        )

    await ghi_audit(db, user["username"], "role:create", f"role:{role['code']}")
    await db.commit()
    return RoleCreateResult(
        role_code=role["code"],
        name=role_name,
        description=body.description,
        permission_codes=permission_codes,
    )


@router.patch("/users/{user_id}", summary="Cập nhật tài khoản")
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = DbSession,
    user: dict = DuocSuaUsers,
) -> UserUpdateResult:
    fields = body.model_fields_set
    if not fields:
        raise HTTPException(status_code=422, detail="Cần cung cấp account_status hoặc role_code")
    if "account_status" in fields and body.account_status is None:
        raise HTTPException(status_code=422, detail="account_status không được để trống")
    if "role_code" in fields and body.role_code is not None and not body.role_code.strip():
        raise HTTPException(status_code=422, detail="role_code không được để trống")

    target_result = await db.execute(
        text(
            """
            SELECT id, email, full_name, account_status
            FROM users
            WHERE id = :user_id
            FOR UPDATE
            """
        ),
        {"user_id": user_id},
    )
    target = target_result.mappings().one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")

    is_self = target["email"].casefold() == str(user.get("username", "")).casefold()
    if is_self and (
        ("role_code" in fields) or ("account_status" in fields and body.account_status != "active")
    ):
        raise HTTPException(
            status_code=403, detail="Không thể tự thay đổi quyền hoặc khóa tài khoản"
        )

    assigned_role_code: str | None = None
    if "role_code" in fields and body.role_code is not None:
        role_result = await db.execute(
            text(
                """
                    SELECT r.id, r.code, r.name
                FROM roles AS r
                WHERE lower(r.code) = lower(:role_code)
                FOR SHARE
                """
            ),
            {"role_code": body.role_code.strip()},
        )
        role = role_result.mappings().one_or_none()
        if role is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy vai trò")
        if role["code"].upper() in _SYSTEM_ROLE_CODES:
            raise HTTPException(status_code=403, detail="Không thể gán vai trò hệ thống")

        permissions_result = await db.execute(
            text(
                """
                SELECT p.code
                FROM role_permissions AS rp
                JOIN permissions AS p ON p.id = rp.permission_id
                WHERE rp.role_id = :role_id
                """
            ),
            {"role_id": role["id"]},
        )
        permissions = {row["code"] for row in permissions_result.mappings().all()}
        if permissions & _ADMIN_PERMISSION_CODES:
            raise HTTPException(status_code=403, detail="Không thể gán vai trò có quyền quản trị")
        assigned_role_code = role["code"]

    if "account_status" in fields:
        await db.execute(
            text(
                """
                UPDATE users
                SET account_status = :account_status, updated_at = now()
                WHERE id = :user_id
                """
            ),
            {"account_status": body.account_status, "user_id": user_id},
        )

    if "role_code" in fields:
        await db.execute(
            text("DELETE FROM user_roles WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        if assigned_role_code is not None:
            await db.execute(
                text(
                    """
                    INSERT INTO user_roles (user_id, role_id, assigned_by)
                    SELECT :user_id, r.id,
                           (SELECT id FROM users WHERE lower(email) = lower(:actor_email))
                    FROM roles AS r
                    WHERE r.code = :role_code
                    """
                ),
                {
                    "user_id": user_id,
                    "actor_email": user["username"],
                    "role_code": assigned_role_code,
                },
            )

    if "role_code" not in fields:
        current_role_result = await db.execute(
            text(
                """
                SELECT r.code
                FROM user_roles AS ur
                JOIN roles AS r ON r.id = ur.role_id
                WHERE ur.user_id = :user_id
                ORDER BY r.code
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        )
        current_role = current_role_result.scalar_one_or_none()
        assigned_role_code = current_role

    status = body.account_status if "account_status" in fields else target["account_status"]
    await ghi_audit(db, user["username"], "user:update", f"user:{user_id}")
    await db.commit()
    return UserUpdateResult(
        id=user_id,
        account_status=status,
        role_code=assigned_role_code,
    )


@router.put("/roles/{role_code}/permissions", summary="Cập nhật quyền của vai trò")
async def update_role_permissions(
    role_code: str,
    body: RolePermissionsUpdate,
    db: AsyncSession = DbSession,
    user: dict = DuocSuaRoles,
) -> RolePermissionsResult:
    normalized_codes = sorted(set(body.permission_codes))
    if any(not code.strip() or len(code) > 100 for code in normalized_codes):
        raise HTTPException(status_code=422, detail="Mã permission không hợp lệ")
    if set(normalized_codes) & _ADMIN_PERMISSION_CODES:
        raise HTTPException(status_code=403, detail="Không thể cấp permission quản trị")

    role_result = await db.execute(
        text(
            """
            SELECT id, code
            FROM roles
            WHERE lower(code) = lower(:role_code)
            FOR UPDATE
            """
        ),
        {"role_code": role_code},
    )
    role = role_result.mappings().one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy vai trò")
    if role["code"].upper() in _SYSTEM_ROLE_CODES:
        raise HTTPException(status_code=403, detail="Không thể sửa quyền của vai trò hệ thống")

    actor_role_result = await db.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM user_roles AS ur
                JOIN users AS u ON u.id = ur.user_id
                WHERE ur.role_id = :role_id
                  AND lower(u.email) = lower(:actor_email)
            )
            """
        ),
        {"role_id": role["id"], "actor_email": user["username"]},
    )
    if actor_role_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Không thể sửa quyền của vai trò đang sử dụng")

    permission_rows: list[Mapping[str, object]] = []
    if normalized_codes:
        permission_result = await db.execute(
            text("SELECT id, code FROM permissions WHERE code = ANY(:permission_codes)"),
            {"permission_codes": normalized_codes},
        )
        permission_rows = permission_result.mappings().all()
        known_codes = {str(row["code"]) for row in permission_rows}
        unknown_codes = sorted(set(normalized_codes) - known_codes)
        if unknown_codes:
            raise HTTPException(
                status_code=422,
                detail={"message": "Permission không tồn tại", "permission_codes": unknown_codes},
            )

    await db.execute(
        text("DELETE FROM role_permissions WHERE role_id = :role_id"),
        {"role_id": role["id"]},
    )
    for permission in permission_rows:
        await db.execute(
            text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (:role_id, :permission_id)
                """
            ),
            {"role_id": role["id"], "permission_id": permission["id"]},
        )

    await ghi_audit(
        db,
        user["username"],
        "role:permissions_update",
        f"role:{role['code']}",
    )
    await db.commit()
    return RolePermissionsResult(role_code=role["code"], permission_codes=normalized_codes)
