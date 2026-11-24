"""Bản dịch POI trong ``poi_localizations`` (khóa unique: POI + ngôn ngữ)."""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.publication import notify_publication

NGON_NGU_UU_TIEN = ("vi", "en", "zh", "ja", "ko")


async def dam_bao_index(db: AsyncSession) -> None:
    """Schema đã có unique constraint; không tạo DDL lúc runtime."""
    return None


async def luu_ban_dich(db: AsyncSession, poi_id: UUID, lang: str, ten: str, mo_ta: str) -> dict:
    """Upsert bản dịch, sau đó xếp audio bền vững qua bảng audio_tasks."""
    # Khóa POI trước bản dịch, cùng thứ tự với publish để tránh kiểm tra dữ liệu cũ.
    result = await db.execute(
        text(
            "SELECT id, name, owner_id, publication_status, is_active FROM pois WHERE id = :poi_id FOR UPDATE"
        ),
        {"poi_id": poi_id},
    )
    poi = result.mappings().first()
    if lang == "en" and poi and poi["publication_status"] == "published":
        await db.execute(
            text(
                "UPDATE pois SET publication_status = 'unpublished', is_active = FALSE WHERE id = :poi_id"
            ),
            {"poi_id": poi_id},
        )
        await notify_publication(db, poi, published=False)
    await db.execute(
        text(
            """
            INSERT INTO poi_localizations
                (poi_id, language_code, localized_name, localized_description,
                 readiness_status, audio_url, audio_storage_key, audio_status, updated_at)
            VALUES
                (:poi_id, :lang, :name, :description, :readiness, NULL, NULL, 'queued', now())
            ON CONFLICT (poi_id, language_code)
            DO UPDATE SET
                localized_name = EXCLUDED.localized_name,
                localized_description = EXCLUDED.localized_description,
                readiness_status = EXCLUDED.readiness_status,
                is_fallback = FALSE,
                audio_url = NULL,
                audio_storage_key = NULL,
                audio_status = 'queued',
                updated_at = now()
            """
        ),
        {
            "poi_id": poi_id,
            "lang": lang,
            "name": ten,
            "description": mo_ta,
            "readiness": "ready" if ten.strip() and mo_ta.strip() else "incomplete",
        },
    )
    await db.execute(
        text("UPDATE pois SET updated_at = now() WHERE id = :poi_id"),
        {"poi_id": poi_id},
    )
    await db.commit()

    from app.services.tasks import quan_ly_tasks

    await quan_ly_tasks.xep_viec(str(poi_id), lang)
    return {
        "poi_id": poi_id,
        "lang": lang,
        "name": ten,
        "description": mo_ta,
        "audio_url": None,
    }


async def ghi_log_dich(db: AsyncSession, username: str, resource: str) -> None:
    """Lưu dấu vết bản dịch trong bảng log PostgreSQL hiện có."""
    metadata = json.dumps({"username": username, "resource": resource, "source": "localizations"})
    await db.execute(
        text(
            """
            INSERT INTO localization_request_logs
                (operation, was_allowed, request_metadata)
            VALUES
                ('poi:translate', true, CAST(:metadata AS jsonb))
            """
        ),
        {"metadata": metadata},
    )
    await db.commit()


async def lay_ban_dich(db: AsyncSession, poi_id: UUID, lang: str) -> tuple[dict | None, bool]:
    """Fallback 3 tầng: yêu cầu → en → vi, trả kèm cờ is_fallback."""
    languages = [lang]
    if lang not in ("vi", "en"):
        languages.append("en")
    if lang != "vi":
        languages.append("vi")
    result = await db.execute(
        text(
            """
            SELECT language_code AS lang,
                   localized_name AS name,
                   localized_description AS description,
                   audio_url
            FROM poi_localizations
            WHERE poi_id = :poi_id
              AND language_code = ANY(:languages)
            ORDER BY CASE
                WHEN language_code = :lang THEN 0
                WHEN language_code = 'en' THEN 1
                ELSE 2
            END
            LIMIT 1
            """
        ),
        {"poi_id": poi_id, "languages": languages, "lang": lang},
    )
    row = result.mappings().first()
    if row is None:
        return None, True
    localized = dict(row)
    return localized, localized["lang"] != lang


def ghep_poi(doc: dict, ban_dich: dict | None, is_fallback: bool, lang: str) -> dict:
    """Ghép POI với bản dịch, rơi về vi thì audio_url null."""
    poi_id = doc.get("_id", doc.get("id"))
    latitude = doc.get("lat", doc.get("latitude"))
    longitude = doc.get("lng", doc.get("longitude"))
    if ban_dich is None:
        return {
            "id": str(poi_id),
            "name": doc["name"],
            "description": doc.get("description", ""),
            "lat": latitude,
            "lng": longitude,
            "trigger_radius": doc.get("trigger_radius", doc.get("trigger_radius_m", 30)),
            "audio_priority": doc.get("audio_priority", 0),
            "images": doc.get("images") or [],
            "lang": "vi",
            "is_fallback": lang != "vi",
            "audio_url": None,
        }
    return {
        "id": str(poi_id),
        "name": ban_dich["name"],
        "description": ban_dich.get("description") or "",
        "lat": latitude,
        "lng": longitude,
        "trigger_radius": doc.get("trigger_radius", doc.get("trigger_radius_m", 30)),
        "audio_priority": doc.get("audio_priority", 0),
        "images": doc.get("images") or [],
        "lang": ban_dich["lang"],
        "is_fallback": is_fallback,
        "audio_url": None
        if (is_fallback and ban_dich["lang"] == "vi")
        else ban_dich.get("audio_url"),
    }
