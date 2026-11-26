"""PostgreSQL-backed owner registration, POI submission, and notification routes."""

import hashlib
import io
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ghi_audit
from app.auth import (
    YeuCauOwnerDuyet,
    bam_mat_khau,
    doi_quyen,
    lay_user_hien_tai,
)
from app.limits import LangField, MAX_ADMIN_NOTE, MAX_MO_TA, MAX_TEN, MatKhauDangKy
from app.pii import giai_ma_pii, ma_hoa_pii
from app.postgres import get_db
from app.routers.owner_auth import YeuCauPhienOwner
from app.routers.owner_auth import router as owner_auth_router
from app.services import images
from app.services.pg_identity import resolve_user_id, user_label
from app.services.publication import invalidate_translations, notify_publication

router = APIRouter(tags=["owner"])
router.include_router(owner_auth_router)

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
    category: Literal[
        "restaurant",
        "cafe",
        "street_food",
        "bakery",
        "dessert",
        "seafood",
        "bar",
        "other",
    ] = "other"
    address_line: str = Field(default="", max_length=500)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    trigger_radius: float = Field(default=30, ge=5, le=200)
    source_language: LangField = "vi"
    collision_check: dict = Field(default_factory=dict)
    images: list[dict] = Field(default_factory=list, max_length=8)
    menu: SubmissionMenu | None = None


async def kiem_tra_va_bao_cao_collision(
    db: AsyncSession,
    lat: float,
    lng: float,
    trigger_radius: float,
    poi_id: UUID | None = None,
) -> dict:
    """Trùng gần 10 m bị chặn; geofence chồng lấn chỉ cảnh báo cho Admin."""
    exact_params = {"lat": lat, "lng": lng}
    exact_sql = """
        SELECT id::text AS id, name,
               ST_Distance(
                   ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                   ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
               )::double precision AS distance_m,
               trigger_radius_m
        FROM pois
        WHERE publication_status <> 'archived'
          AND is_active IS TRUE
          AND ST_DWithin(
              ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
              ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
              10
          )
    """
    if poi_id is not None:
        exact_sql += " AND id <> :poi_id"
        exact_params["poi_id"] = poi_id

    exact_rows = (await db.execute(text(exact_sql + " ORDER BY distance_m LIMIT 5"), exact_params)).mappings().all()
    exact = [
        {
            "poi_id": str(row["id"]),
            "name": row["name"],
            "distance_m": round(float(row["distance_m"]), 1),
        }
        for row in exact_rows
    ]
    if exact:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_coordinate",
                "message": "Tọa độ trùng hoặc cách POI hiện hữu quá gần (10 m).",
                "collisions": exact,
            },
        )

    overlap_params = {"lat": lat, "lng": lng, "radius": trigger_radius}
    overlap_sql = """
        SELECT id::text AS id, name,
               ST_Distance(
                   ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                   ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
               )::double precision AS distance_m,
               trigger_radius_m
        FROM pois
        WHERE publication_status <> 'archived'
          AND is_active IS TRUE
          AND ST_DWithin(
              ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
              ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
              :radius + trigger_radius_m
          )
    """
    if poi_id is not None:
        overlap_sql += " AND id <> :poi_id"
        overlap_params["poi_id"] = poi_id

    overlap_rows = (
        await db.execute(text(overlap_sql + " ORDER BY distance_m LIMIT 10"), overlap_params)
    ).mappings().all()
    overlaps = [
        {
            "poi_id": str(row["id"]),
            "name": row["name"],
            "distance_m": round(float(row["distance_m"]), 1),
            "existing_radius_m": int(row["trigger_radius_m"] or 30),
        }
        for row in overlap_rows
    ]
    return {"kind": "geofence_overlap" if overlaps else "none", "overlaps": overlaps}


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


def _snapshot_for_approval(value: object) -> dict:
    """Dữ liệu cũ/seed cũng phải hợp lệ trước khi bắt đầu tạo POI và menu."""
    try:
        return SubmissionNhap.model_validate(_json_value(value)).model_dump()
    except ValidationError as exc:
        labels = {
            "name": "tên quán",
            "lat": "vĩ độ",
            "lng": "kinh độ",
            "description": "mô tả",
            "category": "danh mục",
            "address_line": "địa chỉ",
            "trigger_radius": "bán kính kích hoạt",
            "source_language": "ngôn ngữ nguồn",
            "menu": "thực đơn",
        }
        fields = list(
            dict.fromkeys(labels.get(str(error["loc"][0]), "nội dung") for error in exc.errors())
        )
        detail = f"Đề xuất thiếu hoặc sai: {', '.join(fields)}. Chủ quán cần bổ sung và gửi lại."
    except (TypeError, ValueError):
        detail = "Nội dung đề xuất không hợp lệ. Chủ quán cần kiểm tra và gửi lại."
    raise HTTPException(status_code=409, detail=detail)


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
    user: dict = YeuCauPhienOwner,
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
        if user.get("role") == "admin":
            return {"status": "admin", "admin_note": ""}
        raise HTTPException(status_code=404, detail="Chưa đăng ký")
    return {"status": registration["status"], "admin_note": registration["admin_note"]}


@router.get("/owner/approvals/counts", summary="Số yêu cầu chờ duyệt theo quyền quản trị")
async def dem_yeu_cau_cho_duyet(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[dict, Depends(lay_user_hien_tai)],
) -> dict[str, int]:
    permissions = user.get("permissions", [])
    can_review_registrations = "user:update" in permissions
    can_review_submissions = "poi:approve" in permissions
    if not can_review_registrations and not can_review_submissions:
        raise HTTPException(status_code=403, detail="Không có quyền xem yêu cầu chờ duyệt")

    # Đếm toàn bộ hàng đợi, không bị giới hạn 100 bản ghi như API danh sách.
    result = await db.execute(
        text("""
            SELECT
                (SELECT count(*) FROM owner_registrations
                 WHERE status = 'pending' AND :can_review_registrations) AS registrations,
                (SELECT count(*) FROM poi_submissions
                 WHERE status = 'pending' AND :can_review_submissions) AS submissions
        """),
        {
            "can_review_registrations": can_review_registrations,
            "can_review_submissions": can_review_submissions,
        },
    )
    counts = dict(result.mappings().one())
    return {**counts, "total": counts["registrations"] + counts["submissions"]}


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
    await db.execute(
        text("""
            INSERT INTO owner_notifications
                (owner_id, notification_type, title, message, reference_type, reference_id)
            VALUES (:owner_id, 'owner_registration_approved', 'Tài khoản đã được duyệt',
                    :message, 'owner_registration', :registration_id)
        """),
        {
            "owner_id": owner_id,
            "registration_id": registration["id"],
            "message": "Đăng ký Chủ quán đã được duyệt. Bạn có thể gửi và quản lý thông tin quán.",
        },
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
    admin_note = body.admin_note.strip()
    if not admin_note:
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
            "admin_note": admin_note,
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
    await db.execute(
        text("""
            INSERT INTO owner_notifications
                (owner_id, notification_type, title, message, reference_type, reference_id)
            VALUES (:owner_id, 'owner_registration_rejected', 'Đăng ký Chủ quán bị từ chối',
                    :message, 'owner_registration', :registration_id)
        """),
        {
            "owner_id": owner_id,
            "registration_id": registration["id"],
            "message": f"Đăng ký Chủ quán bị từ chối: {admin_note}",
        },
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

    collision = await kiem_tra_va_bao_cao_collision(
        db,
        body.lat,
        body.lng,
        body.trigger_radius,
        poi_id,
    )
    snapshot = {
        "name": body.name,
        "description": body.description,
        "category": body.category,
        "address_line": body.address_line,
        "lat": body.lat,
        "lng": body.lng,
        "trigger_radius": body.trigger_radius,
        "source_language": body.source_language,
        "collision_check": collision,
        "images": [],
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
    return {
        "ok": True,
        "submission_id": str(submission_id),
        "collision_check": collision,
    }


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
                   COALESCE(p.category, 'other') AS category,
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
                   COALESCE(s.poi_id::text, s.content_snapshot ->> 'approved_poi_id') AS poi_id,
                   s.content_snapshot AS data, s.submission_type,
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
    if owner_id == reviewer_id and user_duyet.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Chỉ Admin có quyền duyệt mới được tự duyệt đề xuất POI của mình.",
        )
    snapshot = _snapshot_for_approval(submission["content_snapshot"])
    poi_id = submission["poi_id"]
    approval_collision = await kiem_tra_va_bao_cao_collision(
        db,
        float(snapshot["lat"]),
        float(snapshot["lng"]),
        float(snapshot["trigger_radius"]),
        UUID(str(poi_id)) if poi_id is not None else None,
    )
    snapshot["collision_check"] = approval_collision
    poi_id = submission["poi_id"]
    if poi_id is not None:
        poi_id = UUID(str(poi_id))
        poi_result = await db.execute(
            text(
                "SELECT id, owner_id, name, description, publication_status, is_active FROM pois WHERE id = :poi_id FOR UPDATE"
            ),
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
        if poi["publication_status"] == "archived":
            raise HTTPException(status_code=409, detail="POI đã lưu trữ, không thể duyệt cập nhật")
        if poi["name"] != snapshot["name"] or (poi["description"] or "") != snapshot.get(
            "description", ""
        ):
            await invalidate_translations(
                db, poi_id, snapshot["name"], snapshot.get("description", "")
            )
        if poi["publication_status"] == "published" and poi["is_active"]:
            await notify_publication(db, poi, published=False)
        poi_result = await db.execute(
            text(
                """
                UPDATE pois
                SET name = :name, description = :description,
                    category = :category, address_line = :address_line,
                    latitude = :lat, longitude = :lng,
                    trigger_radius_m = :trigger_radius,
                    publication_status = 'unpublished', is_active = FALSE,
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
                    trigger_radius_m, owner_id, publication_status, is_active,
                    created_by, updated_by, updated_at
                )
                VALUES (
                    :name, :description, :category, :address_line, :lat, :lng,
                    :trigger_radius, :owner_id, 'unpublished', FALSE, :owner_id, :reviewer_id,
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
                    raise HTTPException(
                        status_code=409, detail="Thông tin món gửi lên không hợp lệ"
                    )
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

    submitted_images = snapshot.get("images", [])
    if isinstance(submitted_images, list):
        existing_count = int(
            (
                await db.execute(
                    text("SELECT count(*) FROM poi_images WHERE poi_id = :poi_id"),
                    {"poi_id": poi_id},
                )
            ).scalar_one()
        )
        for sort_offset, image_meta in enumerate(submitted_images):
            if existing_count + sort_offset >= images.MAX_ANH:
                break
            if not isinstance(image_meta, Mapping):
                continue
            storage_key = str(image_meta.get("storage_key", ""))
            if not storage_key.startswith(f"submissions/{submission_id}/"):
                continue
            source_name = storage_key.rsplit("/", 1)[-1]
            source_path = (images.THU_MUC_ANH / "submissions" / str(submission_id) / source_name).resolve()
            if not source_path.is_file():
                continue
            extension = source_name.rsplit(".", 1)[-1].lower()
            destination_name = images.ten_an_toan(source_path.read_bytes(), extension)
            destination_path = images.duong_dan_luu(str(poi_id), destination_name)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            data = source_path.read_bytes()
            destination_path.write_bytes(data)
            public_url = images.url_cua(destination_name, str(poi_id))
            await db.execute(
                text(
                    """
                    INSERT INTO poi_images (
                        poi_id, storage_key, public_url, mime_type, size_bytes,
                        width_px, height_px, checksum_sha256, sort_order
                    )
                    VALUES (
                        :poi_id, :storage_key, :public_url, :mime_type, :size_bytes,
                        :width_px, :height_px, :checksum, :sort_order
                    )
                    """
                ),
                {
                    "poi_id": poi_id,
                    "storage_key": f"{poi_id}/{destination_name}",
                    "public_url": public_url,
                    "mime_type": image_meta.get("mime_type"),
                    "size_bytes": len(data),
                    "width_px": image_meta.get("width_px"),
                    "height_px": image_meta.get("height_px"),
                    "checksum": hashlib.sha256(data).hexdigest(),
                    "sort_order": existing_count + sort_offset,
                },
            )

    await db.execute(
        text(
            """
            UPDATE poi_submissions
            SET status = 'approved', reviewed_by = :reviewer_id,
                content_snapshot = content_snapshot ||
                    jsonb_build_object('approved_poi_id', CAST(CAST(:poi_id AS uuid) AS text)),
                reviewed_at = now(), updated_at = now()
            WHERE id = :submission_id
            """
        ),
        {"submission_id": submission_id, "reviewer_id": reviewer_id, "poi_id": poi_id},
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
            "message": f"Đề xuất cho '{snapshot.get('name', '')}' đã được duyệt. "
            "POI chưa công khai; Admin cần kiểm tra bản tiếng Anh, audio và bấm Công khai.",
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO poi_localizations
                (poi_id, language_code, localized_name, localized_description,
                 readiness_status, is_fallback, audio_status, updated_at)
            VALUES
                (:poi_id, :lang, :name, :description,
                 :readiness, FALSE, 'queued', now())
            ON CONFLICT (poi_id, language_code)
            DO UPDATE SET
                localized_name = EXCLUDED.localized_name,
                localized_description = EXCLUDED.localized_description,
                readiness_status = EXCLUDED.readiness_status,
                is_fallback = FALSE,
                audio_status = 'queued',
                updated_at = now()
            """
        ),
        {
            "poi_id": poi_id,
            "lang": snapshot.get("source_language", "vi"),
            "name": snapshot["name"],
            "description": snapshot.get("description", ""),
            "readiness": "ready" if snapshot.get("name") and snapshot.get("description") else "incomplete",
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
    submissions = []
    for row in result.mappings().all():
        blockers = []
        if (
            user_duyet.get("role") != "admin"
            and user_label(user_duyet)
            and row["username"].casefold() == user_label(user_duyet).casefold()
        ):
            blockers.append("Chỉ Admin có quyền duyệt mới được tự duyệt đề xuất POI của mình.")
        try:
            _snapshot_for_approval(row["data"])
        except HTTPException as exc:
            blockers.append(exc.detail)
        submissions.append(
            {
                **dict(row),
                "data": _json_value(row["data"]),
                "created_at": _iso(row["created_at"]),
                "can_approve": not blockers,
                "approval_blockers": blockers,
            }
        )
    return submissions


@router.get("/owner/notifications", summary="Thông báo của tôi")
async def thong_bao(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauPhienOwner,
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
            ORDER BY created_at DESC, id DESC
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
    user: dict = YeuCauPhienOwner,
) -> dict:
    await db.execute(
        text(
            """
            UPDATE owner_notifications
            SET is_read = TRUE, read_at = COALESCE(read_at, now())
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


@router.post("/owner/submissions/{sid}/images", status_code=201, summary="Tải ảnh cho submission chờ duyệt")
async def tai_anh_submission(
    sid: str,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauOwnerDuyet,
) -> dict:
    submission_id = doi_id(sid)
    owner_id = await resolve_user_id(db, user)
    row = (
        await db.execute(
            text(
                """
                SELECT content_snapshot
                FROM poi_submissions
                WHERE id = :submission_id AND owner_id = :owner_id AND status = 'pending'
                FOR UPDATE
                """
            ),
            {"submission_id": submission_id, "owner_id": owner_id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy submission chờ của bạn")

    snapshot = _snapshot_for_approval(row["content_snapshot"])
    existing_images = snapshot.get("images", [])
    if not isinstance(existing_images, list):
        existing_images = []
    try:
        images.kiem_tra_so_luong(len(existing_images))
        data = await file.read()
        extension = images.kiem_tra_anh(data, images.ten_tuyen_du_co_hinh(file.filename or ""))
    except images.LoiAnh as error:
        raise HTTPException(status_code=error.so_loi, detail=str(error)) from None

    name = images.ten_an_toan(data, extension)
    directory = (images.THU_MUC_ANH / "submissions" / str(submission_id)).resolve()
    path = (directory / name).resolve()
    if directory not in path.parents:
        raise HTTPException(status_code=400, detail="Tên ảnh không hợp lệ")
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[extension]
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size

    public_url = f"/static/images/submissions/{submission_id}/{name}"
    existing_images.append(
        {
            "storage_key": f"submissions/{submission_id}/{name}",
            "public_url": public_url,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "width_px": width,
            "height_px": height,
            "checksum_sha256": hashlib.sha256(data).hexdigest(),
        }
    )
    snapshot["images"] = existing_images
    await db.execute(
        text(
            """
            UPDATE poi_submissions
            SET content_snapshot = CAST(:snapshot AS jsonb), updated_at = now()
            WHERE id = :submission_id
            """
        ),
        {"submission_id": submission_id, "snapshot": json.dumps(snapshot)},
    )
    await db.commit()
    return {"images": existing_images}


# Khối legacy sau đây không được đăng ký như route.
async def tu_choi_submission_duplicate(
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
    if owner_id == reviewer_id and user_duyet.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Chỉ Admin có quyền duyệt mới được tự duyệt đề xuất POI của mình.",
        )
    snapshot = _snapshot_for_approval(submission["content_snapshot"])
    poi_id = submission["poi_id"]
    approval_collision = await kiem_tra_va_bao_cao_collision(
        db,
        float(snapshot["lat"]),
        float(snapshot["lng"]),
        float(snapshot["trigger_radius"]),
        UUID(str(poi_id)) if poi_id is not None else None,
    )
    snapshot["collision_check"] = approval_collision
    poi_id = submission["poi_id"]
    if poi_id is not None:
        poi_id = UUID(str(poi_id))
        poi_result = await db.execute(
            text(
                "SELECT id, owner_id, name, description, publication_status, is_active FROM pois WHERE id = :poi_id FOR UPDATE"
            ),
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
        if poi["publication_status"] == "archived":
            raise HTTPException(status_code=409, detail="POI đã lưu trữ, không thể duyệt cập nhật")
        if poi["name"] != snapshot["name"] or (poi["description"] or "") != snapshot.get(
            "description", ""
        ):
            await invalidate_translations(
                db, poi_id, snapshot["name"], snapshot.get("description", "")
            )
        if poi["publication_status"] == "published" and poi["is_active"]:
            await notify_publication(db, poi, published=False)
        poi_result = await db.execute(
            text(
                """
                UPDATE pois
                SET name = :name, description = :description,
                    category = :category, address_line = :address_line,
                    latitude = :lat, longitude = :lng,
                    trigger_radius_m = :trigger_radius,
                    publication_status = 'unpublished', is_active = FALSE,
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
                    trigger_radius_m, owner_id, publication_status, is_active,
                    created_by, updated_by, updated_at
                )
                VALUES (
                    :name, :description, :category, :address_line, :lat, :lng,
                    :trigger_radius, :owner_id, 'unpublished', FALSE, :owner_id, :reviewer_id,
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
                    raise HTTPException(
                        status_code=409, detail="Thông tin món gửi lên không hợp lệ"
                    )
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

    submitted_images = snapshot.get("images", [])
    if isinstance(submitted_images, list):
        existing_count = int(
            (
                await db.execute(
                    text("SELECT count(*) FROM poi_images WHERE poi_id = :poi_id"),
                    {"poi_id": poi_id},
                )
            ).scalar_one()
        )
        for sort_offset, image_meta in enumerate(submitted_images):
            if existing_count + sort_offset >= images.MAX_ANH:
                break
            if not isinstance(image_meta, Mapping):
                continue
            storage_key = str(image_meta.get("storage_key", ""))
            if not storage_key.startswith(f"submissions/{submission_id}/"):
                continue
            source_name = storage_key.rsplit("/", 1)[-1]
            source_path = (images.THU_MUC_ANH / "submissions" / str(submission_id) / source_name).resolve()
            if not source_path.is_file():
                continue
            extension = source_name.rsplit(".", 1)[-1].lower()
            destination_name = images.ten_an_toan(source_path.read_bytes(), extension)
            destination_path = images.duong_dan_luu(str(poi_id), destination_name)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            data = source_path.read_bytes()
            destination_path.write_bytes(data)
            public_url = images.url_cua(destination_name, str(poi_id))
            await db.execute(
                text(
                    """
                    INSERT INTO poi_images (
                        poi_id, storage_key, public_url, mime_type, size_bytes,
                        width_px, height_px, checksum_sha256, sort_order
                    )
                    VALUES (
                        :poi_id, :storage_key, :public_url, :mime_type, :size_bytes,
                        :width_px, :height_px, :checksum, :sort_order
                    )
                    """
                ),
                {
                    "poi_id": poi_id,
                    "storage_key": f"{poi_id}/{destination_name}",
                    "public_url": public_url,
                    "mime_type": image_meta.get("mime_type"),
                    "size_bytes": len(data),
                    "width_px": image_meta.get("width_px"),
                    "height_px": image_meta.get("height_px"),
                    "checksum": hashlib.sha256(data).hexdigest(),
                    "sort_order": existing_count + sort_offset,
                },
            )

    await db.execute(
        text(
            """
            UPDATE poi_submissions
            SET status = 'approved', reviewed_by = :reviewer_id,
                content_snapshot = content_snapshot ||
                    jsonb_build_object('approved_poi_id', CAST(CAST(:poi_id AS uuid) AS text)),
                reviewed_at = now(), updated_at = now()
            WHERE id = :submission_id
            """
        ),
        {"submission_id": submission_id, "reviewer_id": reviewer_id, "poi_id": poi_id},
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
            "message": f"Đề xuất cho '{snapshot.get('name', '')}' đã được duyệt. "
            "POI chưa công khai; Admin cần kiểm tra bản tiếng Anh, audio và bấm Công khai.",
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO poi_localizations
                (poi_id, language_code, localized_name, localized_description,
                 readiness_status, is_fallback, audio_status, updated_at)
            VALUES
                (:poi_id, :lang, :name, :description,
                 :readiness, FALSE, 'queued', now())
            ON CONFLICT (poi_id, language_code)
            DO UPDATE SET
                localized_name = EXCLUDED.localized_name,
                localized_description = EXCLUDED.localized_description,
                readiness_status = EXCLUDED.readiness_status,
                is_fallback = FALSE,
                audio_status = 'queued',
                updated_at = now()
            """
        ),
        {
            "poi_id": poi_id,
            "lang": snapshot.get("source_language", "vi"),
            "name": snapshot["name"],
            "description": snapshot.get("description", ""),
            "readiness": "ready" if snapshot.get("name") and snapshot.get("description") else "incomplete",
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
    submissions = []
    for row in result.mappings().all():
        blockers = []
        if (
            user_duyet.get("role") != "admin"
            and user_label(user_duyet)
            and row["username"].casefold() == user_label(user_duyet).casefold()
        ):
            blockers.append("Chỉ Admin có quyền duyệt mới được tự duyệt đề xuất POI của mình.")
        try:
            _snapshot_for_approval(row["data"])
        except HTTPException as exc:
            blockers.append(exc.detail)
        submissions.append(
            {
                **dict(row),
                "data": _json_value(row["data"]),
                "created_at": _iso(row["created_at"]),
                "can_approve": not blockers,
                "approval_blockers": blockers,
            }
        )
    return submissions


@router.get("/owner/notifications", summary="Thông báo của tôi")
async def thong_bao(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauPhienOwner,
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
            ORDER BY created_at DESC, id DESC
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
    user: dict = YeuCauPhienOwner,
) -> dict:
    await db.execute(
        text(
            """
            UPDATE owner_notifications
            SET is_read = TRUE, read_at = COALESCE(read_at, now())
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


@router.post("/owner/submissions/{sid}/images", status_code=201, summary="Tải ảnh cho submission chờ duyệt")
async def tai_anh_submission(
    sid: str,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauOwnerDuyet,
) -> dict:
    submission_id = doi_id(sid)
    owner_id = await resolve_user_id(db, user)
    row = (
        await db.execute(
            text(
                """
                SELECT content_snapshot
                FROM poi_submissions
                WHERE id = :submission_id AND owner_id = :owner_id AND status = 'pending'
                FOR UPDATE
                """
            ),
            {"submission_id": submission_id, "owner_id": owner_id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy submission chờ của bạn")

    snapshot = _snapshot_for_approval(row["content_snapshot"])
    existing_images = snapshot.get("images", [])
    if not isinstance(existing_images, list):
        existing_images = []
    try:
        images.kiem_tra_so_luong(len(existing_images))
        data = await file.read()
        extension = images.kiem_tra_anh(data, images.ten_tuyen_du_co_hinh(file.filename or ""))
    except images.LoiAnh as error:
        raise HTTPException(status_code=error.so_loi, detail=str(error)) from None

    name = images.ten_an_toan(data, extension)
    directory = (images.THU_MUC_ANH / "submissions" / str(submission_id)).resolve()
    path = (directory / name).resolve()
    if directory not in path.parents:
        raise HTTPException(status_code=400, detail="Tên ảnh không hợp lệ")
    directory.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[extension]
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size

    public_url = f"/static/images/submissions/{submission_id}/{name}"
    existing_images.append(
        {
            "storage_key": f"submissions/{submission_id}/{name}",
            "public_url": public_url,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "width_px": width,
            "height_px": height,
            "checksum_sha256": hashlib.sha256(data).hexdigest(),
        }
    )
    snapshot["images"] = existing_images
    await db.execute(
        text(
            """
            UPDATE poi_submissions
            SET content_snapshot = CAST(:snapshot AS jsonb), updated_at = now()
            WHERE id = :submission_id
            """
        ),
        {"submission_id": submission_id, "snapshot": json.dumps(snapshot)},
    )
    await db.commit()
    return {"images": existing_images}


# Khối legacy sau đây không được đăng ký như route.
async def tu_choi_submission_duplicate(
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
    if owner_id == reviewer_id and user_duyet.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Chỉ Admin có quyền duyệt mới được tự duyệt đề xuất POI của mình.",
        )
    snapshot = _snapshot_for_approval(submission["content_snapshot"])
    poi_id = submission["poi_id"]
    approval_collision = await kiem_tra_va_bao_cao_collision(
        db,
        float(snapshot["lat"]),
        float(snapshot["lng"]),
        float(snapshot["trigger_radius"]),
        UUID(str(poi_id)) if poi_id is not None else None,
    )
    snapshot["collision_check"] = approval_collision
    poi_id = submission["poi_id"]
    if poi_id is not None:
        poi_id = UUID(str(poi_id))
        poi_result = await db.execute(
            text(
                "SELECT id, owner_id, name, description, publication_status, is_active FROM pois WHERE id = :poi_id FOR UPDATE"
            ),
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
        if poi["publication_status"] == "archived":
            raise HTTPException(status_code=409, detail="POI đã lưu trữ, không thể duyệt cập nhật")
        if poi["name"] != snapshot["name"] or (poi["description"] or "") != snapshot.get(
            "description", ""
        ):
            await invalidate_translations(
                db, poi_id, snapshot["name"], snapshot.get("description", "")
            )
        if poi["publication_status"] == "published" and poi["is_active"]:
            await notify_publication(db, poi, published=False)
        poi_result = await db.execute(
            text(
                """
                UPDATE pois
                SET name = :name, description = :description,
                    category = :category, address_line = :address_line,
                    latitude = :lat, longitude = :lng,
                    trigger_radius_m = :trigger_radius,
                    publication_status = 'unpublished', is_active = FALSE,
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
                    trigger_radius_m, owner_id, publication_status, is_active,
                    created_by, updated_by, updated_at
                )
                VALUES (
                    :name, :description, :category, :address_line, :lat, :lng,
                    :trigger_radius, :owner_id, 'unpublished', FALSE, :owner_id, :reviewer_id,
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
                    raise HTTPException(
                        status_code=409, detail="Thông tin món gửi lên không hợp lệ"
                    )
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

    submitted_images = snapshot.get("images", [])
    if isinstance(submitted_images, list):
        existing_count = int(
            (
                await db.execute(
                    text("SELECT count(*) FROM poi_images WHERE poi_id = :poi_id"),
                    {"poi_id": poi_id},
                )
            ).scalar_one()
        )
        for sort_offset, image_meta in enumerate(submitted_images):
            if existing_count + sort_offset >= images.MAX_ANH:
                break
            if not isinstance(image_meta, Mapping):
                continue
            storage_key = str(image_meta.get("storage_key", ""))
            if not storage_key.startswith(f"submissions/{submission_id}/"):
                continue
            source_name = storage_key.rsplit("/", 1)[-1]
            source_path = (images.THU_MUC_ANH / "submissions" / str(submission_id) / source_name).resolve()
            if not source_path.is_file():
                continue
            extension = source_name.rsplit(".", 1)[-1].lower()
            destination_name = images.ten_an_toan(source_path.read_bytes(), extension)
            destination_path = images.duong_dan_luu(str(poi_id), destination_name)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            data = source_path.read_bytes()
            destination_path.write_bytes(data)
            public_url = images.url_cua(destination_name, str(poi_id))
            await db.execute(
                text(
                    """
                    INSERT INTO poi_images (
                        poi_id, storage_key, public_url, mime_type, size_bytes,
                        width_px, height_px, checksum_sha256, sort_order
                    )
                    VALUES (
                        :poi_id, :storage_key, :public_url, :mime_type, :size_bytes,
                        :width_px, :height_px, :checksum, :sort_order
                    )
                    """
                ),
                {
                    "poi_id": poi_id,
                    "storage_key": f"{poi_id}/{destination_name}",
                    "public_url": public_url,
                    "mime_type": image_meta.get("mime_type"),
                    "size_bytes": len(data),
                    "width_px": image_meta.get("width_px"),
                    "height_px": image_meta.get("height_px"),
                    "checksum": hashlib.sha256(data).hexdigest(),
                    "sort_order": existing_count + sort_offset,
                },
            )

    await db.execute(
        text(
            """
            UPDATE poi_submissions
            SET status = 'approved', reviewed_by = :reviewer_id,
                content_snapshot = content_snapshot ||
                    jsonb_build_object('approved_poi_id', CAST(CAST(:poi_id AS uuid) AS text)),
                reviewed_at = now(), updated_at = now()
            WHERE id = :submission_id
            """
        ),
        {"submission_id": submission_id, "reviewer_id": reviewer_id, "poi_id": poi_id},
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
            "message": f"Đề xuất cho '{snapshot.get('name', '')}' đã được duyệt. "
            "POI chưa công khai; Admin cần kiểm tra bản tiếng Anh, audio và bấm Công khai.",
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO poi_localizations
                (poi_id, language_code, localized_name, localized_description,
                 readiness_status, is_fallback, audio_status, updated_at)
            VALUES
                (:poi_id, :lang, :name, :description,
                 :readiness, FALSE, 'queued', now())
            ON CONFLICT (poi_id, language_code)
            DO UPDATE SET
                localized_name = EXCLUDED.localized_name,
                localized_description = EXCLUDED.localized_description,
                readiness_status = EXCLUDED.readiness_status,
                is_fallback = FALSE,
                audio_status = 'queued',
                updated_at = now()
            """
        ),
        {
            "poi_id": poi_id,
            "lang": snapshot.get("source_language", "vi"),
            "name": snapshot["name"],
            "description": snapshot.get("description", ""),
            "readiness": "ready" if snapshot.get("name") and snapshot.get("description") else "incomplete",
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
