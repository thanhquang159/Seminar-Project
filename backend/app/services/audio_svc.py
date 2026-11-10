"""Sinh audio Edge-TTS, cache theo MD5(text:lang), lưu audio_url."""

import hashlib
import time
from pathlib import Path
from uuid import UUID

import edge_tts
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

THU_MUC_AUDIO = Path(__file__).resolve().parents[2] / "static" / "audio"
NGON_NGU_AUDIO = ("vi", "en", "zh", "ja", "ko")

GIONG: dict[str, str] = {
    "vi": "vi-VN-HoaiMyNeural",
    "en": "en-US-AriaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
}


def khoa_cache(van_ban: str, lang: str) -> str:
    """Tên tệp theo nội dung, quên lang là va chạm cache."""
    return hashlib.md5(f"{van_ban}:{lang}".encode()).hexdigest() + ".mp3"


async def tao_mp3(van_ban: str, lang: str) -> bytes:
    """Sinh MP3 bằng Edge-TTS, lỗi mạng trả lỗi có kiểm soát."""
    try:
        am_thanh = b""
        async for mieng in edge_tts.Communicate(van_ban, GIONG.get(lang, GIONG["vi"])).stream():
            if mieng["type"] == "audio":
                am_thanh += mieng["data"]
        if not am_thanh:
            raise RuntimeError("TTS không trả audio")
        return am_thanh
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"TTS lỗi: {exc}") from exc


async def tao_mp3_cached(van_ban: str, lang: str) -> tuple[Path, bool]:
    """Tồn tại thì dùng lại (HIT), không thì sinh (MISS)."""
    THU_MUC_AUDIO.mkdir(parents=True, exist_ok=True)
    tep = THU_MUC_AUDIO / khoa_cache(van_ban, lang)
    if tep.exists():
        return tep, True
    tep.write_bytes(await tao_mp3(van_ban, lang))
    return tep, False


def duong_audio_url(ten_tep: str, lang: str, ban: int | None = None) -> str:
    """audio_url phiên bản hóa để cache busting khi nội dung đổi."""
    return f"/static/audio/{ten_tep}?v={ban or int(time.time())}&l={lang}"


async def kich_hoat_sinh_audio(db, poi_id, langs: tuple[str, ...] = NGON_NGU_AUDIO) -> list[str]:
    """Mô tả đổi thì xóa audio cũ, tạm ẩn POI chờ tiếng Anh xong."""
    poi_uuid = poi_id if isinstance(poi_id, UUID) else UUID(str(poi_id))
    await db.execute(
        text(
            """
            UPDATE poi_localizations
            SET audio_url = NULL,
                audio_storage_key = NULL,
                audio_status = 'not_generated',
                updated_at = now()
            WHERE poi_id = :poi_id
            """
        ),
        {"poi_id": poi_uuid},
    )
    await db.execute(
        text("UPDATE pois SET is_active = false, updated_at = now() WHERE id = :poi_id"),
        {"poi_id": poi_uuid},
    )
    await db.commit()
    from app.services.tasks import quan_ly_tasks

    ids = []
    for lang in langs:
        try:
            ids.append(await quan_ly_tasks.xep_viec(str(poi_uuid), lang))
        except LookupError:
            # A PostgreSQL audio task must reference an existing localization.
            continue
    return ids


async def hoan_tat_audio(db: AsyncSession, poi_id: UUID, lang: str, audio_url: str) -> None:
    """Worker gọi khi xong một ngôn ngữ, đủ tiếng Anh thì bật lại POI."""
    poi_uuid = poi_id if isinstance(poi_id, UUID) else UUID(str(poi_id))
    audio_key = Path(audio_url.split("?", 1)[0]).name
    await db.execute(
        text(
            """
            UPDATE poi_localizations
            SET audio_url = :audio_url,
                audio_storage_key = :audio_storage_key,
                audio_status = 'ready',
                updated_at = now()
            WHERE poi_id = :poi_id AND language_code = :lang
            """
        ),
        {
            "audio_url": audio_url,
            "audio_storage_key": audio_key,
            "poi_id": poi_uuid,
            "lang": lang,
        },
    )
    if lang == "en":
        await db.execute(
            text(
                """
                UPDATE pois
                SET is_active = true, updated_at = now()
                WHERE id = :poi_id
                  AND EXISTS (
                      SELECT 1
                      FROM poi_localizations
                      WHERE poi_id = :poi_id
                        AND language_code = 'en'
                        AND audio_url IS NOT NULL
                  )
                """
            ),
            {"poi_id": poi_uuid},
        )
    await db.commit()
