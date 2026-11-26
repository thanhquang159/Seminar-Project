"""PostgreSQL-backed login, session management and password change routes."""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ghi_audit
from app.auth import (
    ACCESS_PHUT,
    REFRESH_NGAY,
    SO_PHIEN_MAC_DINH,
    DbSession,
    YeuCauDangNhap,
    YeuCauRefresh,
    bam_mat_khau,
    doc_token,
    dung_mat_khau,
    lay_user_theo_ten,
    tao_auth_session,
    tao_token,
)
from app.core.config import la_dev
from app.limits import MatKhau, MatKhauDangKy
from app.services import login_guard

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

THONG_BAO_SAI = "Sai tên đăng nhập hoặc mật khẩu"


class DangNhap(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: MatKhau


def dat_cookie(response: Response, ten: str, token: str, tuoi_giay: int) -> None:
    """Set httpOnly cookies that work across the deployed frontend/API sites."""
    response.set_cookie(
        ten,
        token,
        max_age=tuoi_giay,
        httponly=True,
        samesite="lax" if la_dev() else "none",
        secure=not la_dev(),
        path="/",
    )


def _ip(request: Request) -> str:
    return request.client.host if request.client else "127.0.0.1"


@router.post("/login", summary="Đăng nhập admin")
async def dang_nhap(
    body: DangNhap,
    request: Request,
    response: Response,
    db: AsyncSession = DbSession,
) -> dict:
    return await dang_nhap_voi_pham_vi(body, request, response, db)


async def dang_nhap_voi_pham_vi(
    body: DangNhap,
    request: Request,
    response: Response,
    db: AsyncSession,
    *,
    owner_portal: bool = False,
) -> dict:
    ip = _ip(request)
    await login_guard.kiem_tra(db, body.username, ip)
    user = await lay_user_theo_ten(body.username, db)
    valid_password = (
        dung_mat_khau(body.password, user["password_hash"])
        if user
        else dung_mat_khau("gia", bam_mat_khau("gia"))
    )
    allowed = user is not None and user["account_status"] == "active"
    if (
        owner_portal
        and user
        and valid_password
        and user["account_status"] in {"pending", "rejected"}
        and not user["is_poi_owner_verified"]
    ):
        registration = await db.execute(
            text("""
                SELECT status FROM owner_registrations
                WHERE user_id = :user_id ORDER BY submitted_at DESC LIMIT 1
            """),
            {"user_id": user["id"]},
        )
        allowed = registration.scalar_one_or_none() == user["account_status"]
    if not allowed or not valid_password:
        await login_guard.ghi_nhan_that_bai(db, body.username, ip)
        raise HTTPException(status_code=401, detail=THONG_BAO_SAI)

    await login_guard.xoa_that_bai(db, body.username, ip)
    session_id = uuid4()
    session_version = int(user.get("phi_en_ver", SO_PHIEN_MAC_DINH))
    refresh = tao_token(user["username"], user["role"], "refresh", [], session_version, session_id)
    access = tao_token(user["username"], user["role"], "access", [], session_version, session_id)
    await tao_auth_session(db, user["id"], refresh, ip, session_id)
    await db.commit()
    dat_cookie(response, "access_token", access, ACCESS_PHUT * 60)
    dat_cookie(response, "refresh_token", refresh, REFRESH_NGAY * 86400)
    return {"ok": True, "username": user["username"], "role": user["role"]}


class DoiMatKhau(BaseModel):
    mat_khau_cu: MatKhau
    mat_khau_moi: MatKhauDangKy


@router.post("/change-password", summary="Đổi mật khẩu và thu hồi mọi phiên khác")
async def doi_mat_khau(
    body: DoiMatKhau,
    request: Request,
    response: Response,
    user: dict = YeuCauDangNhap,
    db: AsyncSession = DbSession,
) -> dict:
    doc = await lay_user_theo_ten(user["username"], db)
    if doc is None or not dung_mat_khau(body.mat_khau_cu, doc["password_hash"]):
        ip = _ip(request)
        await login_guard.kiem_tra(db, user["username"], ip)
        await login_guard.ghi_nhan_that_bai(db, user["username"], ip)
        raise HTTPException(status_code=401, detail="Mật khẩu cũ không đúng")
    if body.mat_khau_cu == body.mat_khau_moi:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải khác mật khẩu cũ")

    ip = _ip(request)
    await login_guard.xoa_that_bai(db, user["username"], ip)
    await login_guard.kiem_tra(db, user["username"], ip)
    await db.execute(
        text(
            """
            UPDATE users
            SET password_hash = :password_hash, updated_at = now()
            WHERE id = CAST(:user_id AS uuid)
            """
        ),
        {"password_hash": bam_mat_khau(body.mat_khau_moi), "user_id": str(doc["id"])},
    )
    await db.execute(
        text(
            """
            UPDATE auth_sessions
            SET revoked_at = COALESCE(revoked_at, now())
            WHERE user_id = CAST(:user_id AS uuid) AND revoked_at IS NULL
            """
        ),
        {"user_id": str(doc["id"])},
    )
    version = int(doc.get("phi_en_ver", SO_PHIEN_MAC_DINH))
    session_id = uuid4()
    refresh = tao_token(
        user["username"], user["role"], "refresh", user["permissions"], version, session_id
    )
    access = tao_token(
        user["username"], user["role"], "access", user["permissions"], version, session_id
    )
    await tao_auth_session(db, doc["id"], refresh, ip, session_id)
    await ghi_audit(db, user["username"], "auth:change_password", f"user:{user['username']}")
    await db.commit()

    dat_cookie(response, "access_token", access, ACCESS_PHUT * 60)
    dat_cookie(response, "refresh_token", refresh, REFRESH_NGAY * 86400)
    return {"ok": True, "so_phien": version + 1}


@router.get("/me", summary="Xem phiên hiện tại")
async def xem_toi(user: dict = YeuCauDangNhap) -> dict:
    return user


@router.post("/refresh", summary="Cấp access mới từ refresh cookie")
async def lam_moi(response: Response, user: dict = YeuCauRefresh) -> dict:
    access = tao_token(
        user["username"],
        user["role"],
        "access",
        user.get("permissions", []),
        user.get("phi_en_ver", SO_PHIEN_MAC_DINH),
        user["session_id"],
    )
    dat_cookie(response, "access_token", access, ACCESS_PHUT * 60)
    return {"ok": True}


@router.post("/logout", summary="Đăng xuất")
async def dang_xuat(
    request: Request,
    response: Response,
    db: AsyncSession = DbSession,
) -> dict:
    token = request.cookies.get("access_token")
    token_type = "access"
    if token is None:
        token = request.cookies.get("refresh_token")
        token_type = "refresh"
    if token is not None:
        try:
            data = doc_token(token, token_type)
            session_id = UUID(str(data["sid"]))
        except (HTTPException, KeyError, ValueError, TypeError):
            pass
        else:
            await db.execute(
                text(
                    """
                    UPDATE auth_sessions
                    SET revoked_at = COALESCE(revoked_at, now())
                    WHERE id = CAST(:session_id AS uuid)
                    """
                ),
                {"session_id": str(session_id)},
            )
            await db.commit()
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}
