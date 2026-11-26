"""Phiên Owner cho phép xem kết quả đăng ký khi chưa được cấp quyền quản lý."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    DbSession,
    _kiem_tra_auth_session,
    doc_token,
    kiem_tra_phien,
    lay_user_theo_ten,
)
from app.routers.admin_auth import DangNhap, dang_nhap_voi_pham_vi, lam_moi

router = APIRouter(prefix="/owner/auth", tags=["owner-auth"])


async def _owner_session(request: Request, token: str | None, db: AsyncSession, kind: str):
    if token is None:
        bearer = request.headers.get("Authorization", "")
        token = bearer[7:] if bearer.startswith("Bearer ") else None
    if token is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    data = doc_token(token, kind)
    username = data.get("sub")
    if not isinstance(username, str):
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    user = await lay_user_theo_ten(username, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    if user["account_status"] != "active":
        result = await db.execute(
            text("""
                SELECT status FROM owner_registrations
                WHERE user_id = :user_id ORDER BY submitted_at DESC LIMIT 1
            """),
            {"user_id": user["id"]},
        )
        if (
            user["account_status"] not in {"pending", "rejected"}
            or result.scalar_one_or_none() != user["account_status"]
            or user["is_poi_owner_verified"]
        ):
            raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    # Phiên đăng ký vẫn đọc được kết quả ngay sau khi Admin cấp role Owner.
    just_approved = (
        data.get("role") == "user"
        and user["role"] == "poi_owner"
        and user["account_status"] == "active"
        and user["is_poi_owner_verified"]
    )
    if not just_approved:
        kiem_tra_phien(data, user)
    session_id = await _kiem_tra_auth_session(db, data, user, kind, token)
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "permissions": [],
        "session_id": session_id,
    }


async def lay_phien_owner(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = DbSession,
):
    return await _owner_session(request, access_token, db, "access")


async def lay_refresh_owner(
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = DbSession,
):
    return await _owner_session(request, refresh_token, db, "refresh")


YeuCauPhienOwner = Depends(lay_phien_owner)
YeuCauRefreshOwner = Depends(lay_refresh_owner)


@router.post("/login", summary="Đăng nhập cổng Owner, kể cả đơn chờ hoặc bị từ chối")
async def dang_nhap_owner(
    body: DangNhap, request: Request, response: Response, db: AsyncSession = DbSession
):
    return await dang_nhap_voi_pham_vi(body, request, response, db, owner_portal=True)


@router.get("/me", summary="Xem phiên cổng Owner")
async def xem_phien_owner(user: dict = YeuCauPhienOwner):
    return {"username": user["username"], "role": user["role"]}


@router.post("/refresh", summary="Làm mới phiên cổng Owner")
async def lam_moi_owner(response: Response, user: dict = YeuCauRefreshOwner):
    return await lam_moi(response, user)
