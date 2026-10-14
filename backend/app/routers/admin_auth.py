"""Route xác thực: login, me, refresh, logout, đổi mật khẩu (SEC-011)."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.audit import ghi_audit
from app.auth import (
    ACCESS_PHUT,
    REFRESH_NGAY,
    SO_PHIEN_MAC_DINH,
    YeuCauDangNhap,
    YeuCauRefresh,
    bam_mat_khau,
    dung_mat_khau,
    lay_user_theo_ten,
    tao_token,
)
from app.config import la_dev
from app.limits import MatKhau, MatKhauDangKy
from app.services import login_guard

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

THONG_BAO_SAI = "Sai tên đăng nhập hoặc mật khẩu"


class DangNhap(BaseModel):
    # SEC-001: bcrypt cắt cứng ở 72 byte, nên mật khẩu dài hơn phải bị từ chối
    # thay vì bị cắt âm thầm (xem app/limits.py:_mat_khau_trong_gioi_han).
    username: str = Field(min_length=1, max_length=50)
    password: MatKhau


def dat_cookie(response: Response, ten: str, token: str, tuoi_giay: int) -> None:
    """Cookie httpOnly, JS không đọc được để chống XSS lấy phiên."""
    response.set_cookie(
        ten,
        token,
        max_age=tuoi_giay,
        httponly=True,
        samesite="lax",
        secure=not la_dev(),
        path="/",
    )


@router.post("/login", summary="Đăng nhập admin")
async def dang_nhap(body: DangNhap, request: Request, response: Response) -> dict:
    from app.db import get_database

    db = get_database()
    ip = request.client.host if request.client else "la"
    # SEC-002: hỏi bộ đếm TRƯỚC khi băm bcrypt, để đoán sai không tốn CPU nữa.
    await login_guard.kiem_tra(db, body.username, ip)
    user = await lay_user_theo_ten(body.username)
    # Sai tên và sai mật khẩu trả cùng một thông báo để chống dò tài khoản.
    dung = (
        dung_mat_khau(body.password, user["password_hash"])
        if user
        else dung_mat_khau("gia", bam_mat_khau("gia"))
    )
    if user is None or not dung:
        await login_guard.ghi_nhan_that_bai(db, body.username, ip)
        raise HTTPException(status_code=401, detail=THONG_BAO_SAI)
    await login_guard.xoa_that_bai(db, body.username, ip)
    role = user.get("role", "admin")
    from app.permissions import quyen_cua_role

    quyen = await quyen_cua_role(get_database(), role)
    so_phien = user.get("phi_en_ver", SO_PHIEN_MAC_DINH)
    dat_cookie(
        response,
        "access_token",
        tao_token(user["username"], role, "access", quyen, so_phien),
        ACCESS_PHUT * 60,
    )
    dat_cookie(
        response,
        "refresh_token",
        tao_token(user["username"], role, "refresh", quyen, so_phien),
        REFRESH_NGAY * 86400,
    )
    return {"ok": True, "username": user["username"], "role": role}


class DoiMatKhau(BaseModel):
    """Bắt buộc có mật khẩu cũ: chỉ cần phiên hợp lệ thì kẻ cướp token phiên
    cũng đổi được mật khẩu, tức là chiếm tài khoản vĩnh viễn."""

    mat_khau_cu: MatKhau
    mat_khau_moi: MatKhauDangKy


@router.post("/change-password", summary="Đổi mật khẩu và thu hồi mọi phiên khác")
async def doi_mat_khau(
    body: DoiMatKhau, request: Request, response: Response, user: dict = YeuCauDangNhap
) -> dict:
    """Sau khi đổi, mọi token cũ chết; chỉ máy đang đổi được cấp token mới.

    Vì sao không huỷ phiên của chính máy này: người dùng đang sửa mật khẩu vì
    nghi ngờ lộ — bắt họ đăng nhập lại cũng được, nhưng thêm một bước vô ích.
    Cookie mới gửi kèm trong cùng response nên trải nghiệm liền mạch.
    """
    from app.db import get_database

    db = get_database()
    doc = await lay_user_theo_ten(user["username"])
    if doc is None:
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    ip = request.client.host if request.client else "la"
    # SEC-013 (A07): hỏi bộ đếm TRƯỚC khi băm, như `/admin/auth/login` đã làm.
    await login_guard.kiem_tra(db, user["username"], ip)
    if not dung_mat_khau(body.mat_khau_cu, doc.get("password_hash", "")):
        # SEC-013 (A07): SEC-002 chỉ bọc `/admin/auth/login` nên route này trước
        # đó KHÔNG đếm lần sai — 1000 lượt đoán mật khẩu cũ trong 15 phút không
        # bị chặn. Đếm cả lần sai ở đây nữa, cùng bộ đếm với đăng nhập.
        await login_guard.ghi_nhan_that_bai(db, user["username"], ip)
        raise HTTPException(status_code=401, detail="Mật khẩu cũ không đúng")
    if body.mat_khau_cu == body.mat_khau_moi:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải khác mật khẩu cũ")

    ket_qua = await db["admin_users"].update_one(
        {"username": user["username"]},
        {
            "$set": {
                "password_hash": bam_mat_khau(body.mat_khau_moi),
                "password_changed_at": datetime.now(UTC),
            },
            "$inc": {"phi_en_ver": 1},
        },
    )
    if ket_qua.matched_count == 0:
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    so_phien = doc.get("phi_en_ver", SO_PHIEN_MAC_DINH) + 1

    # Đổi mật khẩu thường đi kèm lần đăng nhập sai bị khoá tạm — dù xong thì
    # phải mở khoá, nếu không người dùng vừa sửa xong lại bị chặn 15 phút.
    ip = request.client.host if request.client else "la"
    await login_guard.xoa_that_bai(db, user["username"], ip)

    await ghi_audit(db, user["username"], "auth:change_password", f"user:{user['username']}")

    quyen = user.get("permissions", [])
    dat_cookie(
        response,
        "access_token",
        tao_token(user["username"], user["role"], "access", quyen, so_phien),
        ACCESS_PHUT * 60,
    )
    dat_cookie(
        response,
        "refresh_token",
        tao_token(user["username"], user["role"], "refresh", quyen, so_phien),
        REFRESH_NGAY * 86400,
    )
    return {"ok": True, "so_phien": so_phien}


@router.get("/me", summary="Xem phiên hiện tại")
async def xem_toi(user: dict = YeuCauDangNhap) -> dict:
    return user


@router.post("/refresh", summary="Cấp access mới từ refresh cookie")
async def lam_moi(response: Response, user: dict = YeuCauRefresh) -> dict:
    # SEC-011: quyền lấy từ DB chứ không từ token refresh cũ — token cũ có quyền
    # lúc nó được cấp, đã lỗi thời nếu role của tài khoản đã đổi.
    dat_cookie(
        response,
        "access_token",
        tao_token(
            user["username"],
            user["role"],
            "access",
            user.get("permissions", []),
            user.get("phi_en_ver", SO_PHIEN_MAC_DINH),
        ),
        ACCESS_PHUT * 60,
    )
    return {"ok": True}


@router.post("/logout", summary="Đăng xuất")
async def dang_xuat(response: Response) -> dict:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}
