"""Bản dịch POI ở collection riêng, khóa unique (poi_id, lang) (ADR-004).

Bản dịch do người quản trị nhập tay. Trước đây thiếu bản dịch thì server tự
gọi Google Translate (deep-translator) — và gói đó từng bị chiếm tài khoản
năm 2022 (PYSEC-2022-252): bản 1.11.3 độc hại được đăng lên PyPI, chạy mã độc
ngay lúc `pip install`. Bản 1.11.4 là bản sạch nhưng không có bản vá nào sau
đó, nên thay vì giữ một gói không vá được, dịch nền bị gỡ hẳn.

Hệ quả cần nói rõ: POI mà chưa có bản dịch thì đọc bằng bản gốc (tiếng Việt)
và giao diện báo `is_fallback`; admin nhập bản dịch thì `luu_ban_dich` upsert
và tự kích hoạt sinh audio cho ngôn ngữ đó.
"""

from datetime import UTC, datetime

from bson import ObjectId

NGON_NGU_UU_TIEN = ("vi", "en", "zh", "ja", "ko")


async def dam_bao_index(db) -> None:
    """Index unique để chèn trùng (poi_id, lang) bị từ chối."""
    await db["poi_localizations"].create_index([("poi_id", 1), ("lang", 1)], unique=True)


async def luu_ban_dich(db, poi_id: ObjectId, lang: str, ten: str, mo_ta: str) -> dict:
    """Upsert bản dịch do admin nhập, rồi kích hoạt sinh audio cho ngôn ngữ đó.

    Sinh audio ngay là để giữ nguyên luồng cũ: tạo POI xong vài phút là nghe
    được. Nếu chờ ai đó bấm tay thì POI sẽ kẹt ở `audio_status=processing` vĩnh
    viễn vì `hoan_tat_audio` chỉ bật lại POI khi có audio.
    """
    ban_dich = {
        "poi_id": poi_id,
        "lang": lang,
        "name": ten,
        "description": mo_ta,
        "audio_url": None,
    }
    await db["poi_localizations"].update_one(
        {"poi_id": poi_id, "lang": lang}, {"$set": ban_dich}, upsert=True
    )
    await db["pois"].update_one(
        {"_id": poi_id},
        {"$set": {"audio_status": "processing", "updated_at": datetime.now(UTC)}},
    )
    from app.services.tasks import quan_ly_tasks

    quan_ly_tasks.gan_db(db)
    await quan_ly_tasks.xep_viec(str(poi_id), lang)
    return ban_dich


async def lay_ban_dich(db, poi_id: ObjectId, lang: str) -> tuple[dict | None, bool]:
    """Fallback 3 tầng: yêu cầu → en → vi, trả kèm cờ is_fallback."""
    truc_tiep = await db["poi_localizations"].find_one({"poi_id": poi_id, "lang": lang})
    if truc_tiep:
        return truc_tiep, False
    if lang != "en":
        tieng_anh = await db["poi_localizations"].find_one({"poi_id": poi_id, "lang": "en"})
        if tieng_anh:
            return tieng_anh, True
    if lang != "vi":
        tieng_viet = await db["poi_localizations"].find_one({"poi_id": poi_id, "lang": "vi"})
        if tieng_viet:
            return tieng_viet, lang != "vi"
    return None, True


def ghep_poi(doc: dict, ban_dich: dict | None, is_fallback: bool, lang: str) -> dict:
    """Ghép POI gốc với bản dịch, rơi về vi thì audio_url null."""
    if ban_dich is None:
        return {
            "id": str(doc["_id"]),
            "name": doc["name"],
            "description": doc.get("description", ""),
            "lat": doc["lat"],
            "lng": doc["lng"],
            "trigger_radius": doc.get("trigger_radius", 30),
            "audio_priority": doc.get("audio_priority", 0),
            "lang": lang,
            "is_fallback": True,
            "audio_url": None,
        }
    return {
        "id": str(doc["_id"]),
        "name": ban_dich["name"],
        "description": ban_dich["description"],
        "lat": doc["lat"],
        "lng": doc["lng"],
        "trigger_radius": doc.get("trigger_radius", 30),
        "audio_priority": doc.get("audio_priority", 0),
        "lang": ban_dich["lang"],
        "is_fallback": is_fallback,
        "audio_url": None if (is_fallback and ban_dich["lang"] == "vi") else ban_dich.get("audio_url"),
    }


