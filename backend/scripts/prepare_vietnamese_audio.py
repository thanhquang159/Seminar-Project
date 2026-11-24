"""Bổ sung VI còn thiếu từ nội dung gốc cho một POI và tạo audio; mặc định chỉ xem trước."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.postgres import AsyncSessionLocal, engine
from app.services.tasks import QuanLyTasks


async def main(poi_id, apply):
    engine.echo = False
    manager = QuanLyTasks()
    try:
        async with asyncio.timeout(120):
            async with AsyncSessionLocal() as db:
                poi = (
                    (
                        await db.execute(
                            text("""
                    SELECT id,name,description,publication_status,is_active FROM pois
                    WHERE id=:id FOR UPDATE
                """),
                            {"id": poi_id},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if not poi or poi["publication_status"] in ("archived", "rejected"):
                    raise RuntimeError("Không tìm thấy POI hợp lệ; không khôi phục POI đã xóa")
                existing = (
                    (
                        await db.execute(
                            text("""
                    SELECT id,audio_status,audio_url FROM poi_localizations
                    WHERE poi_id=:id AND language_code='vi'
                """),
                            {"id": poi_id},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                print(
                    json.dumps(
                        {
                            "poi": dict(poi),
                            "existing_vi": dict(existing) if existing else None,
                            "apply": apply,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                )
                if existing or not apply:
                    return
                await db.execute(
                    text("""
                    INSERT INTO poi_localizations (poi_id,language_code,localized_name,localized_description,
                        is_source_language,readiness_status,audio_status)
                    SELECT id,'vi',name,COALESCE(description,''),TRUE,
                        CASE WHEN btrim(name)<>'' AND btrim(COALESCE(description,''))<>''
                             THEN 'ready' ELSE 'incomplete' END, 'not_generated'
                    FROM pois WHERE id=:id
                    ON CONFLICT (poi_id,language_code) DO NOTHING
                """),
                    {"id": poi_id},
                )
                # Bump sync cursor để các máy đang lưu snapshot EN sai trong lane VI nhận lại POI.
                await db.execute(
                    text("UPDATE pois SET updated_at=now() WHERE id=:id"), {"id": poi_id}
                )
                await db.commit()
            task_id = await manager.xep_viec(str(poi_id), "vi")
            await manager._runners[task_id]
            result = await manager._doc(task_id)
            print(json.dumps(result, ensure_ascii=False, default=str))
            if result["status"] != "done":
                raise RuntimeError(
                    "Audio chưa hoàn tất; xem lỗi tác vụ và dùng Thử lại trong Admin"
                )
    finally:
        await manager.stop()
        await engine.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("poi_id", type=UUID)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.poi_id, args.apply))
