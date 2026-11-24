"""Điều kiện và chuyển trạng thái công khai POI trong cùng transaction."""

from collections.abc import Mapping
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import ghi_audit
from app.services.pg_identity import resolve_user_id, user_label

# Thông báo duyệt hỗ trợ POI cũ chưa được gắn poi_id vào submission.
APPROVAL_SQL = """
    (EXISTS (SELECT 1 FROM poi_submissions s
             WHERE (s.poi_id = p.id OR s.content_snapshot ->> 'approved_poi_id' = p.id::text)
               AND s.owner_id = p.owner_id AND s.status = 'approved')
     OR EXISTS (SELECT 1 FROM owner_notifications n
                WHERE n.owner_id = p.owner_id AND n.reference_id = p.id
                  AND n.reference_type = 'poi'
                  AND n.notification_type = 'poi_submission_approved'))
"""


def publication_readiness(poi: Mapping, english: Mapping | None) -> dict:
    """Chỉ bản EN thực sự, đã kiểm tra và có audio hoàn tất mới đạt điều kiện."""
    english = english or {}
    reasons = []
    status = poi["publication_status"]
    if status in {"archived", "rejected"}:
        reasons.append("POI đã lưu trữ hoặc bị từ chối, không thể công khai.")
    if (poi.get("owner_id") or status == "pending_review") and not poi.get("has_approval"):
        reasons.append("POI của Owner chưa được Admin duyệt nội dung.")
    english_ready = bool(
        str(english.get("localized_name") or "").strip()
        and str(english.get("localized_description") or "").strip()
        and english.get("readiness_status") in {"ready", "published"}
        and not english.get("is_fallback", False)
    )
    audio_ready = bool(
        english.get("audio_status") == "ready" and str(english.get("audio_url") or "").strip()
    )
    if not english_ready:
        reasons.append("Cần bản tiếng Anh có tên, mô tả và trạng thái sẵn sàng.")
    if not audio_ready:
        reasons.append("Cần audio tiếng Anh hoàn tất (ready) và có URL.")
    return {
        "ready": not reasons,
        "review_approved": bool(poi.get("has_approval")),
        "english_ready": english_ready,
        "audio_ready": audio_ready,
        "audio_status": english.get("audio_status") or "not_generated",
        "reasons": reasons,
    }


async def read_publication(db: AsyncSession, poi_id: UUID, *, lock: bool = False) -> dict:
    result = await db.execute(
        text(
            f"""
            SELECT p.id, p.name, p.owner_id, p.publication_status, p.is_active,
                   {APPROVAL_SQL} AS has_approval
            FROM pois p WHERE p.id = :poi_id
            {"FOR UPDATE OF p" if lock else ""}
            """
        ),
        {"poi_id": poi_id},
    )
    poi = result.mappings().one_or_none()
    if poi is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    result = await db.execute(
        text(
            """
            SELECT localized_name, localized_description, readiness_status, is_fallback, audio_status, audio_url
            FROM poi_localizations WHERE poi_id = :poi_id AND language_code = 'en'
            """
            + (" FOR SHARE" if lock else "")
        ),
        {"poi_id": poi_id},
    )
    return {**dict(poi), "readiness": publication_readiness(poi, result.mappings().one_or_none())}


async def notify_publication(db: AsyncSession, poi: Mapping, *, published: bool) -> None:
    if poi.get("owner_id") is None:
        return
    title = "POI đã được công khai" if published else "POI đã được ẩn khỏi công khai"
    await db.execute(
        text(
            """
            INSERT INTO owner_notifications
                (owner_id, notification_type, title, message, reference_type, reference_id)
            VALUES (:owner_id, :type, :title, :message, 'poi', :poi_id)
            """
        ),
        {
            "owner_id": poi["owner_id"],
            "poi_id": poi["id"],
            "type": "poi_published" if published else "poi_unpublished",
            "title": title,
            "message": f"{title}: '{poi['name']}'. "
            + (
                "Khách tham quan có thể tìm thấy POI trên bản đồ."
                if published
                else "POI chưa hiển thị cho khách; Admin cần công khai lại khi đủ điều kiện."
            ),
        },
    )


async def set_publication(db: AsyncSession, poi_id: UUID, user: dict, *, published: bool) -> dict:
    poi = await read_publication(db, poi_id, lock=True)
    if poi["publication_status"] in {"archived", "rejected"}:
        raise HTTPException(status_code=409, detail="POI đã lưu trữ hoặc bị từ chối")
    if published and not poi["readiness"]["ready"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "POI chưa đủ điều kiện công khai.",
                "readiness": poi["readiness"],
            },
        )
    target = "published" if published else "unpublished"
    changed = poi["publication_status"] != target or poi["is_active"] != published
    if changed:
        await db.execute(
            text("""
                UPDATE pois SET publication_status = :status, is_active = :active,
                    updated_by = :actor_id, updated_at = now()
                WHERE id = :poi_id
            """),
            {
                "poi_id": poi_id,
                "status": target,
                "active": published,
                "actor_id": await resolve_user_id(db, user),
            },
        )
        await notify_publication(db, poi, published=published)
        await ghi_audit(
            db, user_label(user), "poi:publish" if published else "poi:unpublish", f"poi:{poi_id}"
        )
    await db.commit()
    return {
        "id": str(poi_id),
        "publication_status": target,
        "is_active": published,
        "changed": changed,
        "readiness": poi["readiness"],
    }


async def invalidate_translations(
    db: AsyncSession, poi_id: UUID, name: str, description: str
) -> None:
    """Nội dung nguồn đổi: bắt buộc kiểm tra lại bản dịch và tạo audio mới."""
    await db.execute(
        text("""
            UPDATE poi_localizations
            SET readiness_status = 'review_required', audio_status = 'not_generated',
                localized_name = CASE WHEN language_code = 'vi' THEN :name ELSE localized_name END,
                localized_description = CASE WHEN language_code = 'vi' THEN :description ELSE localized_description END,
                audio_url = NULL, audio_storage_key = NULL, updated_at = now()
            WHERE poi_id = :poi_id
        """),
        {"poi_id": poi_id, "name": name, "description": description},
    )
