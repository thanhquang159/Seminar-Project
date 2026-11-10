"""Seed 3 POI mẫu ở Quận 4 vào PostgreSQL, chạy lại không nhân đôi.

Dữ liệu được tìm theo tên, sau đó cập nhật hoặc thêm mới cùng bản tiếng Việt.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

# Cho phép chạy `python scripts/seed_poi.py` từ thư mục backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.postgres import AsyncSessionLocal, close_db

# 3 quán thật ở Quận 4, tọa độ lấy xấp xỉ trung tâm khu ăn uống.
POIS_MAU = [
    {
        "name": "Bánh mì chảo Quận 4",
        "description": "Bánh mì chảo pate trứng ốp la ăn kèm dưa chua.",
        "lat": 10.7569,
        "lng": 106.7641,
        "trigger_radius": 30,
        "audio_priority": 0,
    },
    {
        "name": "Ốc Đào Quận 4",
        "description": "Quán ốc đêm đông khách ở Vĩnh Khánh.",
        "lat": 10.7582,
        "lng": 106.7663,
        "trigger_radius": 40,
        "audio_priority": 1,
    },
    {
        "name": "Bún mắm Quận 4",
        "description": "Bún mắm miền Tây thơm mắm cá linh.",
        "lat": 10.7545,
        "lng": 106.7628,
        "trigger_radius": 30,
        "audio_priority": 2,
    },
]


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db:
            for poi in POIS_MAU:
                poi_id = await db.scalar(
                    text("SELECT id FROM pois WHERE name = :name ORDER BY id LIMIT 1 FOR UPDATE"),
                    {"name": poi["name"]},
                )
                params = {
                    **poi,
                    "category": "other",
                    "address_line": "",
                    "publication_status": "published",
                    "is_active": True,
                }
                if poi_id is None:
                    poi_id = await db.scalar(
                        text(
                            """
                            INSERT INTO pois (
                                name, description, category, address_line, latitude, longitude,
                                trigger_radius_m, audio_priority, publication_status, is_active,
                                updated_at
                            )
                            VALUES (
                                :name, :description, :category, :address_line, :lat, :lng,
                                :trigger_radius, :audio_priority, :publication_status, :is_active,
                                now()
                            )
                            RETURNING id
                            """
                        ),
                        params,
                    )
                else:
                    await db.execute(
                        text(
                            """
                            UPDATE pois
                            SET description = :description,
                                category = :category,
                                address_line = :address_line,
                                latitude = :lat,
                                longitude = :lng,
                                trigger_radius_m = :trigger_radius,
                                audio_priority = :audio_priority,
                                publication_status = :publication_status,
                                is_active = :is_active,
                                updated_at = now()
                            WHERE id = :poi_id
                            """
                        ),
                        {**params, "poi_id": poi_id},
                    )
                await db.execute(
                    text(
                        """
                        INSERT INTO poi_localizations (
                            poi_id, language_code, localized_name, localized_description,
                            is_source_language, readiness_status, updated_at
                        )
                        VALUES (:poi_id, 'vi', :name, :description, TRUE, 'published', now())
                        ON CONFLICT (poi_id, language_code) DO UPDATE
                        SET localized_name = EXCLUDED.localized_name,
                            localized_description = EXCLUDED.localized_description,
                            is_source_language = TRUE,
                            readiness_status = 'published',
                            updated_at = now()
                        """
                    ),
                    {"poi_id": poi_id, "name": poi["name"], "description": poi["description"]},
                )

            await db.commit()
            total = await db.scalar(text("SELECT count(*) FROM pois"))
            print(f"Seed complete: {total} POIs in PostgreSQL.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
