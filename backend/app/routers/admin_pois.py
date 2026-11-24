"""PostgreSQL-backed administrative POI and image workflows."""

import hashlib
import io
from collections.abc import Mapping
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ghi_audit
from app.auth import doi_quyen
from app.postgres import get_db
from app.services import images
from app.services.pg_identity import resolve_user_id, user_label
from app.services.publication import (
    APPROVAL_SQL,
    invalidate_translations,
    notify_publication,
    publication_readiness,
    read_publication,
    set_publication,
)

router = APIRouter(prefix="/admin/pois", tags=["admin-poi"])

DuocTaoPoi = doi_quyen("poi:create")
DuocSuaPoi = doi_quyen("poi:update")
DuocXoaPoi = doi_quyen("poi:delete")
DuocCongKhaiPoi = doi_quyen("poi:publish")

_POI_RETURNING = """
    id::text AS id,
    name,
    COALESCE(description, '') AS description,
    latitude::double precision AS lat,
    longitude::double precision AS lng,
    trigger_radius_m AS trigger_radius,
    audio_priority
"""


class PoiNhap(BaseModel):
    """Data accepted when an administrator creates or updates a POI."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    address_line: str = Field(default="", max_length=500)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    trigger_radius: float = Field(default=30, ge=5, le=200)
    audio_priority: int = Field(default=0, ge=0, le=100)


def doi_id(poi_id: str) -> UUID:
    """Parse UUID identifiers and return a client error for malformed values."""
    try:
        return UUID(poi_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None


def _poi_response(row: Mapping[str, object]) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description") or "",
        "lat": float(row["lat"]),
        "lng": float(row["lng"]),
        "trigger_radius": row.get("trigger_radius", 30),
        "audio_priority": row.get("audio_priority", 0),
    }


@router.get("", summary="Danh sách POI quản trị")
async def liet_ke_poi(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocSuaPoi,
) -> list[dict]:
    result = await db.execute(
        text(
            f"""
            SELECT p.id::text AS id, p.name,
                   COALESCE(p.description, '') AS description,
                   COALESCE(p.address_line, '') AS address_line,
                   p.latitude::double precision AS lat,
                   p.longitude::double precision AS lng,
                   p.trigger_radius_m AS trigger_radius, p.audio_priority,
                   p.publication_status, p.is_active,
                   COALESCE(img.images, '[]'::json) AS images,
                   COALESCE(loc.language_code, 'vi') AS lang,
                   FALSE AS is_fallback, loc.audio_url,
                   p.owner_id, {APPROVAL_SQL} AS has_approval,
                   to_jsonb(en) AS english
            FROM pois AS p
            LEFT JOIN poi_localizations en ON en.poi_id = p.id AND en.language_code = 'en'
            LEFT JOIN LATERAL (
                SELECT l.language_code, l.audio_url
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
            WHERE p.publication_status <> 'archived'
            ORDER BY p.name, p.id
            LIMIT 500
            """
        )
    )
    return [
        {
            **{
                key: value
                for key, value in row.items()
                if key not in {"english", "owner_id", "has_approval"}
            },
            "readiness": publication_readiness(row, row.get("english")),
        }
        for row in result.mappings().all()
    ]


@router.get("/{poi_id}/readiness", summary="Kiểm tra điều kiện công khai POI")
async def kiem_tra_cong_khai(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocCongKhaiPoi,
) -> dict:
    poi = await read_publication(db, doi_id(poi_id))
    return {
        "id": str(poi["id"]),
        "publication_status": poi["publication_status"],
        "is_active": poi["is_active"],
        "readiness": poi["readiness"],
    }


@router.post("/{poi_id}/publish", summary="Công khai POI sau khi kiểm tra English và audio")
async def publish_poi(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocCongKhaiPoi,
) -> dict:
    return await set_publication(db, doi_id(poi_id), user, published=True)


@router.post("/{poi_id}/unpublish", summary="Ẩn POI khỏi công khai")
async def unpublish_poi(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocCongKhaiPoi,
) -> dict:
    return await set_publication(db, doi_id(poi_id), user, published=False)


@router.post("", status_code=201, summary="Tạo POI")
async def tao_poi(
    body: PoiNhap,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocTaoPoi,
) -> dict:
    actor_id = await resolve_user_id(db, user)
    row = (
        (
            await db.execute(
                text(
                    f"""
                INSERT INTO pois (
                    name, description, category, address_line, latitude, longitude,
                    trigger_radius_m, audio_priority, publication_status, is_active,
                    created_by, updated_by, updated_at
                )
                VALUES (
                    :name, :description, 'other', :address_line, :lat, :lng,
                    :trigger_radius, :audio_priority, 'draft', FALSE,
                    :actor_id, :actor_id, now()
                )
                RETURNING {_POI_RETURNING}
                """
                ),
                {
                    **body.model_dump(),
                    "actor_id": actor_id,
                },
            )
        )
        .mappings()
        .one()
    )
    await ghi_audit(db, user_label(user), "poi:create", f"poi:{row['id']}")
    await db.commit()
    return _poi_response(row)


@router.put("/{poi_id}", summary="Sửa POI")
async def sua_poi(
    poi_id: str,
    body: PoiNhap,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocSuaPoi,
) -> dict:
    parsed_id = doi_id(poi_id)
    actor_id = await resolve_user_id(db, user)
    previous = (
        (
            await db.execute(
                text(
                    "SELECT id, name, description, owner_id, publication_status, is_active FROM pois WHERE id = :poi_id FOR UPDATE"
                ),
                {"poi_id": parsed_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if previous is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    content_changed = (
        previous["name"] != body.name or (previous["description"] or "") != body.description
    )
    if content_changed:
        await invalidate_translations(db, parsed_id, body.name, body.description)
        if previous["publication_status"] == "published":
            await db.execute(
                text(
                    "UPDATE pois SET publication_status = 'unpublished', is_active = FALSE WHERE id = :poi_id"
                ),
                {"poi_id": parsed_id},
            )
            await notify_publication(db, previous, published=False)
    row = (
        (
            await db.execute(
                text(
                    f"""
                UPDATE pois
                SET name = :name,
                    description = :description,
                    address_line = :address_line,
                    latitude = :lat,
                    longitude = :lng,
                    trigger_radius_m = :trigger_radius,
                    audio_priority = :audio_priority,
                    updated_by = :actor_id,
                    updated_at = now()
                WHERE id = :poi_id
                RETURNING {_POI_RETURNING}
                """
                ),
                {"poi_id": doi_id(poi_id), **body.model_dump(), "actor_id": actor_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    await ghi_audit(db, user_label(user), "poi:update", f"poi:{poi_id}")
    await db.commit()
    return _poi_response(row)


@router.delete("/{poi_id}", status_code=204, summary="Xóa POI")
async def xoa_poi(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocXoaPoi,
) -> Response:
    row = (
        (
            await db.execute(
                text(
                    """
                UPDATE pois
                SET is_active = FALSE,
                    publication_status = 'archived',
                    updated_by = :actor_id,
                    updated_at = now()
                WHERE id = :poi_id
                  AND publication_status <> 'archived'
                RETURNING id
                """
                ),
                {
                    "poi_id": doi_id(poi_id),
                    "actor_id": await resolve_user_id(db, user),
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    await db.execute(
        text("""
            UPDATE audio_tasks SET task_status='cancelled', completed_at=now(), updated_at=now(),
                error_message='POI đã xóa'
            WHERE poi_id=:poi_id AND task_status IN ('queued','processing','paused')
        """),
        {"poi_id": doi_id(poi_id)},
    )
    await ghi_audit(db, user_label(user), "poi:delete", f"poi:{poi_id}")
    await db.commit()
    return Response(status_code=204)


@router.get("/{poi_id}/images", summary="Liệt kê ảnh của POI")
async def liet_ke_anh(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocSuaPoi,
) -> dict:
    parsed_id = doi_id(poi_id)
    exists = await db.execute(
        text("SELECT id FROM pois WHERE id = :poi_id"),
        {"poi_id": parsed_id},
    )
    if exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    result = await db.execute(
        text(
            """
            SELECT COALESCE(public_url, storage_key) AS image
            FROM poi_images
            WHERE poi_id = :poi_id
            ORDER BY sort_order, created_at, id
            """
        ),
        {"poi_id": parsed_id},
    )
    return {"images": [row["image"] for row in result.mappings().all()]}


@router.post("/{poi_id}/images", status_code=201, summary="Tải ảnh lên POI")
async def tai_anh(
    poi_id: str,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocSuaPoi,
) -> dict:
    parsed_id = doi_id(poi_id)
    poi_row = (
        await db.execute(
            text("SELECT id FROM pois WHERE id = :poi_id FOR UPDATE"),
            {"poi_id": parsed_id},
        )
    ).scalar_one_or_none()
    if poi_row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")

    count = await db.execute(
        text("SELECT count(*) FROM poi_images WHERE poi_id = :poi_id"),
        {"poi_id": parsed_id},
    )
    try:
        images.kiem_tra_so_luong(int(count.scalar_one()))
        data = await file.read()
        extension = images.kiem_tra_anh(data, images.ten_tuyen_du_co_hinh(file.filename or ""))
    except images.LoiAnh as error:
        raise HTTPException(status_code=error.so_loi, detail=str(error)) from None

    name = images.ten_an_toan(data, extension)
    storage_key = f"{parsed_id}/{name}"
    public_url = images.url_cua(name, str(parsed_id))
    path = images.duong_dan_luu(str(parsed_id), name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    mime_type = {
        "jpg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }[extension]
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size

    try:
        existing = await db.execute(
            text("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM poi_images WHERE poi_id = :poi_id"),
            {"poi_id": parsed_id},
        )
        sort_order = int(existing.scalar_one())
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
                "poi_id": parsed_id,
                "storage_key": storage_key,
                "public_url": public_url,
                "mime_type": mime_type,
                "size_bytes": len(data),
                "width_px": width,
                "height_px": height,
                "checksum": hashlib.sha256(data).hexdigest(),
                "sort_order": sort_order,
            },
        )
        await db.execute(
            text("UPDATE pois SET updated_at = now() WHERE id = :poi_id"),
            {"poi_id": parsed_id},
        )
        await ghi_audit(db, user_label(user), "poi:image_add", f"poi:{poi_id} {name}")
        await db.commit()
    except Exception:
        await db.rollback()
        path.unlink(missing_ok=True)
        raise

    return {"images": await _image_urls(db, parsed_id), "moi_tai": public_url}


async def _image_urls(db: AsyncSession, poi_id: UUID) -> list[str | None]:
    result = await db.execute(
        text(
            """
            SELECT COALESCE(public_url, storage_key) AS image
            FROM poi_images
            WHERE poi_id = :poi_id
            ORDER BY sort_order, created_at, id
            """
        ),
        {"poi_id": poi_id},
    )
    return [row["image"] for row in result.mappings().all()]


@router.delete("/{poi_id}/images/{ten}", summary="Xóa ảnh của POI")
async def xoa_anh(
    poi_id: str,
    ten: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = DuocSuaPoi,
) -> dict:
    parsed_id = doi_id(poi_id)
    url = images.url_cua(ten, str(parsed_id))
    legacy_url = images.url_cua(ten)
    row = (
        (
            await db.execute(
                text(
                    """
                SELECT id, storage_key
                FROM poi_images
                WHERE poi_id = :poi_id
                  AND (storage_key = :storage_key OR public_url IN (:url, :legacy_url))
                LIMIT 1
                FOR UPDATE
                """
                ),
                {
                    "poi_id": parsed_id,
                    "storage_key": f"{parsed_id}/{ten}",
                    "url": url,
                    "legacy_url": legacy_url,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")

    await db.execute(
        text("DELETE FROM poi_images WHERE id = :image_id"),
        {"image_id": row["id"]},
    )
    await db.execute(
        text("UPDATE pois SET updated_at = now() WHERE id = :poi_id"),
        {"poi_id": parsed_id},
    )
    await ghi_audit(db, user_label(user), "poi:image_delete", f"poi:{poi_id} {ten}")
    await db.commit()
    try:
        images.duong_dan_luu(str(parsed_id), ten).unlink(missing_ok=True)
    except images.LoiAnh as error:
        raise HTTPException(status_code=error.so_loi, detail=str(error)) from None
    return {"images": await _image_urls(db, parsed_id)}
