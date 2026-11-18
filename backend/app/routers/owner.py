"""PostgreSQL-backed owner registration, POI submission, and notification routes."""

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ghi_audit
from app.auth import (
    YeuCauDangNhap,
    YeuCauOwnerDuyet,
    bam_mat_khau,
    doi_quyen,
)
from app.limits import MAX_ADMIN_NOTE, MAX_MO_TA, MAX_TEN, MatKhauDangKy
from app.pii import giai_ma_pii, ma_hoa_pii
from app.postgres import get_db
from app.services.pg_identity import resolve_user_id, user_label

router = APIRouter(tags=["owner"])

DuocQuanLyUser = doi_quyen("user:update")
DuocDuyetPoi = doi_quyen("poi:approve")


class DangKyOwner(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: MatKhauDangKy
    cccd: str = Field(min_length=9, max_length=20, pattern=r"^[0-9]{9,20}$")


class XetDuyet(BaseModel):
    admin_note: str = Field(default="", max_length=MAX_ADMIN_NOTE)


class SubmissionMenuItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    price: float | None = Field(default=None, ge=0)


class SubmissionMenu(BaseModel):
    name: str = Field(default="Menu chính", min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    items: list[SubmissionMenuItem] = Field(default_factory=list, max_length=100)


class SubmissionNhap(BaseModel):
    poi_id: str | None = None
    name: str = Field(min_length=1, max_length=MAX_TEN)
    description: str = Field(default="", max_length=MAX_MO_TA)
    address_line: str = Field(default="", max_length=500)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    menu: SubmissionMenu | None = None


def doi_id(poi_id: str) -> UUID:
    try:
        return UUID(poi_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None


def _json_value(value: object) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@router.post("/owner/register", summary="Đăng ký làm chủ quán")
async def dang_ky(
    body: DangKyOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    encrypted_cccd = ma_hoa_pii(body.cccd)
    if encrypted_cccd is None:
        raise HTTPException(status_code=500, detail="Chưa cấu hình mã hóa PII")

    existing = await db.execute(
        text("SELECT id FROM users WHERE lower(email) = lower(:email) LIMIT 1"),
        {"email": body.username},
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã dùng")

    user_result = await db.execute(
        text(
            """
            INSERT INTO users (email, password_hash, full_name, account_status)
            VALUES (:email, :password_hash, :full_name, 'pending')
            RETURNING id
            """
        ),
        {
            "email": body.username,
            "password_hash": bam_mat_khau(body.password),
            "full_name": body.username,
        },
    )
    user_id = UUID(str(user_result.scalar_one()))
    await db.execute(
        text(
            """
            INSERT INTO owner_registrations (
                user_id, submitted_data, verification_data_enc
            )
            VALUES (:user_id, CAST(:submitted_data AS jsonb), :verification_data)
            """
        ),
        {
            "user_id": user_id,
            "submitted_data": json.dumps({"username": body.username}),
            "verification_data": encrypted_cccd.encode("utf-8"),
        },
    )
    await db.commit()
    return {"ok": True, "status": "pending"}


@router.get("/owner/registration-status", summary="Xem trạng thái duyệt")
async def xem_trang_thai(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauDangNhap,
) -> dict:
    user_id = await resolve_user_id(db, user)
    result = await db.execute(
        text(
            """
            SELECT status, COALESCE(admin_note, '') AS admin_note
            FROM owner_registrations
            WHERE user_id = :user_id
            ORDER BY submitted_at DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    registration = result.mappings().one_or_none()
    if registration is None:
        raise HTTPException(status_code=404, detail="Chưa đăng ký")
    return {"status": registration["status"], "admin_note": registration["admin_note"]}


@router.get("/owner/registrations", summary="Liệt kê đơn chờ duyệt")
async def liet_ke_don(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocQuanLyUser,
) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT COALESCE(r.submitted_data ->> 'username', u.email) AS username,
                   r.status
            FROM owner_registrations AS r
            JOIN users AS u ON u.id = r.user_id
            WHERE r.status = 'pending'
            ORDER BY r.submitted_at
            LIMIT 100
            """
        )
    )
    return [dict(row) for row in result.mappings().all()]


@router.post("/owner/registrations/{username}/approve", summary="Duyệt chủ quán")
async def duyet(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_duyet: dict = DuocQuanLyUser,
) -> dict:
    reviewer_id = await resolve_user_id(db, user_duyet)
    registration_result = await db.execute(
        text(
            """
            SELECT r.id, r.user_id
            FROM owner_registrations AS r
            JOIN users AS u ON u.id = r.user_id
            WHERE r.status = 'pending'
              AND lower(COALESCE(r.submitted_data ->> 'username', u.email))
                    = lower(:username)
            ORDER BY r.submitted_at DESC
            LIMIT 1
            FOR UPDATE OF r
            """
        ),
        {"username": username},
    )
    registration = registration_result.mappings().one_or_none()
    if registration is None:
        raise HTTPException(status_code=404, detail="Không có đơn chờ")
    owner_id = UUID(str(registration["user_id"]))
    if reviewer_id is not None and owner_id == reviewer_id:
        raise HTTPException(status_code=403, detail="Không được tự duyệt đơn của mình")

    await db.execute(
        text(
            """
            UPDATE owner_registrations
            SET status = 'approved', reviewed_by = :reviewer_id,
                reviewed_at = now(), updated_at = now()
            WHERE id = :registration_id
            """
        ),
        {"registration_id": registration["id"], "reviewer_id": reviewer_id},
    )
    await db.execute(
        text(
            """
            UPDATE users
            SET account_status = 'active', owner_verified_at = now(), updated_at = now()
            WHERE id = :owner_id
            """
        ),
        {"owner_id": owner_id},
    )
    await db.execute(
        text(
            """
            INSERT INTO user_roles (user_id, role_id, assigned_by)
            SELECT :owner_id, r.id, :reviewer_id
            FROM roles AS r
            WHERE upper(r.code) IN ('OWNER', 'POI_OWNER')
            ON CONFLICT (user_id, role_id) DO NOTHING
            """
        ),
        {"owner_id": owner_id, "reviewer_id": reviewer_id},
    )
    await ghi_audit(db, user_label(user_duyet), "owner:approve", f"owner:{username}")
    await db.commit()
    return {"ok": True}


@router.post("/owner/registrations/{username}/reject", summary="Từ chối đơn")
async def tu_choi(
    username: str,
    body: XetDuyet,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_duyet: dict = DuocQuanLyUser,
) -> dict:
    if not body.admin_note.strip():
        raise HTTPException(status_code=400, detail="Từ chối phải có ghi chú")
    reviewer_id = await resolve_user_id(db, user_duyet)
    result = await db.execute(
        text(
            """
            SELECT r.id, r.user_id
            FROM owner_registrations AS r
            JOIN users AS u ON u.id = r.user_id
            WHERE r.status = 'pending'
              AND lower(COALESCE(r.submitted_data ->> 'username', u.email))
                    = lower(:username)
            ORDER BY r.submitted_at DESC
            LIMIT 1
            FOR UPDATE OF r
            """
        ),
        {"username": username},
    )
    registration = result.mappings().one_or_none()
    if registration is None:
        raise HTTPException(status_code=404, detail="Không có đơn chờ")
    owner_id = UUID(str(registration["user_id"]))
    if reviewer_id is not None and owner_id == reviewer_id:
        raise HTTPException(status_code=403, detail="Không được tự xử đơn của mình")

    await db.execute(
        text(
            """
            UPDATE owner_registrations
            SET status = 'rejected', admin_note = :admin_note,
                reviewed_by = :reviewer_id, reviewed_at = now(), updated_at = now()
            WHERE id = :registration_id
            """
        ),
        {
            "admin_note": body.admin_note,
            "reviewer_id": reviewer_id,
            "registration_id": registration["id"],
        },
    )
    await db.execute(
        text(
            """
            UPDATE users SET account_status = 'rejected', updated_at = now()
            WHERE id = :owner_id AND account_status = 'pending'
            """
        ),
        {"owner_id": owner_id},
    )
    await ghi_audit(db, user_label(user_duyet), "owner:reject", f"owner:{username}")
    await db.commit()
    return {"ok": True}


@router.post("/owner/submissions", summary="Gửi tạo/sửa POI chờ duyệt")
async def gui_submission(
    body: SubmissionNhap,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauOwnerDuyet,
) -> dict:
    owner_id = await resolve_user_id(db, user)
    poi_id = doi_id(body.poi_id) if body.poi_id else None
    if poi_id is not None:
        result = await db.execute(
            text("SELECT owner_id FROM pois WHERE id = :poi_id"),
            {"poi_id": poi_id},
        )
        poi = result.mappings().one_or_none()
        if poi is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy POI")
        existing_owner = poi["owner_id"]
        if existing_owner is not None and UUID(str(existing_owner)) != owner_id:
            raise HTTPException(status_code=403, detail="Không phải quán của bạn")

    snapshot = {
        "name": body.name,
        "description": body.description,
        "address_line": body.address_line,
        "lat": body.lat,
        "lng": body.lng,
        "menu": body.menu.model_dump() if body.menu is not None else None,
    }
    result = await db.execute(
        text(
            """
            INSERT INTO poi_submissions (
                owner_id, poi_id, submission_type, content_snapshot, status
            )
            VALUES (
                :owner_id, :poi_id, :submission_type,
                CAST(:content_snapshot AS jsonb), 'pending'
            )
            RETURNING id
            """
        ),
        {
            "owner_id": owner_id,
            "poi_id": poi_id,
            "submission_type": "update" if poi_id else "create",
            "content_snapshot": json.dumps(snapshot),
        },
    )
    submission_id = result.scalar_one()
    await db.commit()
    return {"ok": True, "submission_id": str(submission_id)}


@router.get("/owner/pois", summary="Danh sách POI của tôi")
async def pois_cua_toi(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauOwnerDuyet,
) -> list[dict]:
    owner_id = await resolve_user_id(db, user)
    result = await db.execute(
        text(
            """
            SELECT p.id::text AS id, p.name, COALESCE(p.description, '') AS description,
                   COALESCE(p.address_line, '') AS address_line,
                   p.latitude::double precision AS lat,
                   p.longitude::double precision AS lng,
                   p.trigger_radius_m AS trigger_radius,
                   p.publication_status,
                   p.is_active,
                   COALESCE(img.images, '[]'::json) AS images,
                   loc.audio_url
            FROM pois AS p
            LEFT JOIN LATERAL (
                SELECT l.audio_url
                FROM poi_localizations AS l
                WHERE l.poi_id = p.id
                ORDER BY CASE WHEN l.language_code = 'vi' THEN 0 ELSE 1 END,
                         l.language_code
                LIMIT 1
            ) AS loc ON TRUE
            LEFT JOIN LATERAL (
                SELECT json_agg(i.public_url ORDER BY i.sort_order, i.created_at)
                       FILTER (WHERE i.public_url IS NOT NULL) AS images
                FROM poi_images AS i
                WHERE i.poi_id = p.id
            ) AS img ON TRUE
            WHERE p.owner_id = :owner_id
            ORDER BY p.name, p.id
            LIMIT 100
            """
        ),
        {"owner_id": owner_id},
    )
    return [dict(row) for row in result.mappings().all()]


@router.get("/owner/submissions/mine", summary="Submission của tôi")
async def submission_cua_toi(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauOwnerDuyet,
) -> list[dict]:
    owner_id = await resolve_user_id(db, user)
    result = await db.execute(
        text(
            """
            SELECT s.id::text AS id, s.owner_id::text AS owner_id,
                   s.poi_id::text AS poi_id, s.content_snapshot AS data,
                   s.status, COALESCE(s.admin_note, '') AS admin_note,
                   s.submitted_at, s.submitted_at AS created_at, u.email AS username
            FROM poi_submissions AS s
            JOIN users AS u ON u.id = s.owner_id
            WHERE s.owner_id = :owner_id
            ORDER BY s.submitted_at DESC
            LIMIT 100
            """
        ),
        {"owner_id": owner_id},
    )
    return [
        {
            **dict(row),
            "data": _json_value(row["data"]),
            "submitted_at": _iso(row["submitted_at"]),
            "created_at": _iso(row["created_at"]),
        }
        for row in result.mappings().all()
    ]


@router.post("/owner/submissions/{sid}/approve", summary="Duyệt submission vào POI")
async def duyet_submission(
    sid: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_duyet: dict = DuocDuyetPoi,
) -> dict:
    submission_id = doi_id(sid)
    reviewer_id = await resolve_user_id(db, user_duyet)
    result = await db.execute(
        text(
            """
            SELECT id, owner_id, poi_id, submission_type, content_snapshot
            FROM poi_submissions
            WHERE id = :submission_id AND status = 'pending'
            FOR UPDATE
            """
        ),
        {"submission_id": submission_id},
    )
    submission = result.mappings().one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Không có submission chờ")

    owner_id = UUID(str(submission["owner_id"]))
    snapshot = _json_value(submission["content_snapshot"])
    snapshot.setdefault("address_line", "")
    poi_id = submission["poi_id"]
    if poi_id is not None:
        poi_id = UUID(str(poi_id))
        poi_result = await db.execute(
            text("SELECT owner_id FROM pois WHERE id = :poi_id FOR UPDATE"),
            {"poi_id": poi_id},
        )
        poi = poi_result.mappings().one_or_none()
        if poi is None:
            raise HTTPException(
                status_code=409,
                detail="Đề xuất không còn khớp với quán hiện tại, cần gửi lại",
            )
        if poi["owner_id"] is not None and UUID(str(poi["owner_id"])) != owner_id:
            raise HTTPException(
                status_code=409,
                detail="Đề xuất không còn khớp với quán hiện tại, cần gửi lại",
            )
        poi_result = await db.execute(
            text(
                """
                UPDATE pois
                SET name = :name, description = :description,
                    address_line = :address_line,
                    latitude = :lat, longitude = :lng,
                    publication_status = 'published', is_active = TRUE,
                    updated_by = :reviewer_id, updated_at = now()
                WHERE id = :poi_id
                RETURNING id
                """
            ),
            {
                **snapshot,
                "poi_id": poi_id,
                "reviewer_id": reviewer_id,
            },
        )
        poi_id = UUID(str(poi_result.scalar_one()))
    else:
        poi_result = await db.execute(
            text(
                """
                INSERT INTO pois (
                    name, description, category, address_line, latitude, longitude,
                    owner_id, publication_status, is_active, created_by, updated_by,
                    updated_at
                )
                VALUES (
                    :name, :description, 'other', :address_line, :lat, :lng,
                    :owner_id, 'pending_review', FALSE, :owner_id, :reviewer_id,
                    now()
                )
                RETURNING id
                """
            ),
            {**snapshot, "owner_id": owner_id, "reviewer_id": reviewer_id},
        )
        poi_id = UUID(str(poi_result.scalar_one()))
        menu = snapshot.get("menu")
        if menu is not None:
            if not isinstance(menu, Mapping):
                raise HTTPException(status_code=409, detail="Thực đơn gửi lên không hợp lệ")
            menu_result = await db.execute(
                text(
                    """
                    INSERT INTO menus (poi_id, name, description, is_active)
                    VALUES (:poi_id, :name, :description, TRUE)
                    RETURNING id
                    """
                ),
                {
                    "poi_id": poi_id,
                    "name": menu.get("name", "Menu chính"),
                    "description": menu.get("description") or None,
                },
            )
            menu_id = menu_result.scalar_one()
            items = menu.get("items", [])
            if not isinstance(items, list):
                raise HTTPException(status_code=409, detail="Danh sách món gửi lên không hợp lệ")
            for sort_order, item in enumerate(items):
                if not isinstance(item, Mapping):
                    raise HTTPException(status_code=409, detail="Thông tin món gửi lên không hợp lệ")
                await db.execute(
                    text(
                        """
                        INSERT INTO menu_items (
                            menu_id, name, description, price, is_available, sort_order
                        )
                        VALUES (
                            :menu_id, :name, :description, :price, TRUE, :sort_order
                        )
                        """
                    ),
                    {
                        "menu_id": menu_id,
                        "name": item["name"],
                        "description": item.get("description") or None,
                        "price": item.get("price"),
                        "sort_order": sort_order,
                    },
                )

    await db.execute(
        text(
            """
            UPDATE poi_submissions
            SET status = 'approved', reviewed_by = :reviewer_id,
                reviewed_at = now(), updated_at = now()
            WHERE id = :submission_id
            """
        ),
        {"submission_id": submission_id, "reviewer_id": reviewer_id},
    )
    await db.execute(
        text(
            """
            INSERT INTO owner_notifications (
                owner_id, notification_type, title, message, reference_type, reference_id
            )
            VALUES (
                :owner_id, 'poi_submission_approved', 'Đề xuất POI đã được duyệt',
                :message, 'poi', :poi_id
            )
            """
        ),
        {
            "owner_id": owner_id,
            "poi_id": poi_id,
            "message": f"Đề xuất cho '{snapshot.get('name', '')}' đã được duyệt",
        },
    )
    await ghi_audit(db, user_label(user_duyet), "poi:approve", f"submission:{submission_id}")
    await db.commit()
    return {"ok": True, "poi_id": str(poi_id)}


@router.post("/owner/submissions/{sid}/reject", summary="Từ chối submission POI")
async def tu_choi_submission(
    sid: str,
    body: XetDuyet,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_duyet: dict = DuocDuyetPoi,
) -> dict:
    admin_note = body.admin_note.strip()
    if not admin_note:
        raise HTTPException(status_code=400, detail="Từ chối phải có ghi chú")

    submission_id = doi_id(sid)
    reviewer_id = await resolve_user_id(db, user_duyet)
    result = await db.execute(
        text(
            """
            SELECT id, owner_id
            FROM poi_submissions
            WHERE id = :submission_id AND status = 'pending'
            FOR UPDATE
            """
        ),
        {"submission_id": submission_id},
    )
    submission = result.mappings().one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Không có submission chờ")

    owner_id = UUID(str(submission["owner_id"]))
    await db.execute(
        text(
            """
            UPDATE poi_submissions
            SET status = 'rejected', admin_note = :admin_note,
                reviewed_by = :reviewer_id, reviewed_at = now(), updated_at = now()
            WHERE id = :submission_id AND status = 'pending'
            """
        ),
        {
            "submission_id": submission_id,
            "reviewer_id": reviewer_id,
            "admin_note": admin_note,
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO owner_notifications (
                owner_id, notification_type, title, message, reference_type, reference_id
            )
            VALUES (
                :owner_id, 'poi_submission_rejected', 'Đề xuất POI bị từ chối',
                :message, 'poi_submission', :submission_id
            )
            """
        ),
        {
            "owner_id": owner_id,
            "submission_id": submission_id,
            "message": f"Đề xuất POI bị từ chối: {admin_note}",
        },
    )
    await ghi_audit(db, user_label(user_duyet), "poi:reject", f"submission:{submission_id}")
    await db.commit()
    return {"ok": True}


@router.get("/owner/submissions/pending", summary="Submission chờ duyệt (admin)")
async def submission_cho_duyet(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_duyet: dict = DuocDuyetPoi,
) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT s.id::text AS id, u.email AS username,
                   COALESCE(s.content_snapshot ->> 'name', '') AS name,
                   s.content_snapshot AS data,
                   s.submitted_at AS created_at
            FROM poi_submissions AS s
            JOIN users AS u ON u.id = s.owner_id
            WHERE s.status = 'pending'
            ORDER BY s.submitted_at
            LIMIT 100
            """
        )
    )
    return [
        {
            **dict(row),
            "data": _json_value(row["data"]),
            "created_at": _iso(row["created_at"]),
        }
        for row in result.mappings().all()
    ]


@router.get("/owner/notifications", summary="Thông báo của tôi")
async def thong_bao(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauOwnerDuyet,
) -> list[dict]:
    owner_id = await resolve_user_id(db, user)
    result = await db.execute(
        text(
            """
            SELECT id::text AS id, owner_id::text AS owner_id, notification_type,
                   title, message, reference_type, reference_id::text AS reference_id,
                   is_read AS "read", created_at, read_at
            FROM owner_notifications
            WHERE owner_id = :owner_id
            ORDER BY created_at DESC
            LIMIT 50
            """
        ),
        {"owner_id": owner_id},
    )
    return [
        {**dict(row), "created_at": _iso(row["created_at"]), "read_at": _iso(row["read_at"])}
        for row in result.mappings().all()
    ]


@router.post("/owner/notifications/{nid}/read", summary="Đánh dấu đã đọc")
async def da_doc(
    nid: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauOwnerDuyet,
) -> dict:
    await db.execute(
        text(
            """
            UPDATE owner_notifications
            SET is_read = TRUE, read_at = now()
            WHERE id = :notification_id AND owner_id = :owner_id
            """
        ),
        {
            "notification_id": doi_id(nid),
            "owner_id": await resolve_user_id(db, user),
        },
    )
    await db.commit()
    return {"ok": True}


async def che_pii_cu(db: AsyncSession, gio_hien_tai: datetime) -> int:
    """Clear encrypted verification values older than the 180-day retention period."""
    threshold = gio_hien_tai - timedelta(days=180)
    result = await db.execute(
        text(
            """
            UPDATE owner_registrations
            SET verification_data_enc = NULL, updated_at = now()
            WHERE submitted_at < :threshold
              AND verification_data_enc IS NOT NULL
            RETURNING id
            """
        ),
        {"threshold": threshold},
    )
    count = len(result.scalars().all())
    await db.commit()
    return count


async def doc_cccd(username: str, db: AsyncSession) -> str | None:
    """Decrypt a registration's verification value only for an authorized caller."""
    result = await db.execute(
        text(
            """
            SELECT r.verification_data_enc
            FROM owner_registrations AS r
            JOIN users AS u ON u.id = r.user_id
            WHERE lower(COALESCE(r.submitted_data ->> 'username', u.email))
                    = lower(:username)
            ORDER BY r.submitted_at DESC
            LIMIT 1
            """
        ),
        {"username": username},
    )
    value = result.scalar_one_or_none()
    if value is None:
        return None
    try:
        encrypted = bytes(value).decode("utf-8")
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    return giai_ma_pii(encrypted)
