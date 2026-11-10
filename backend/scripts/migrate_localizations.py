"""Tạo/cập nhật bản dịch tiếng Việt từ các POI trong PostgreSQL."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.postgres import AsyncSessionLocal, close_db


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    """
                    INSERT INTO poi_localizations (
                        poi_id, language_code, localized_name, localized_description,
                        is_source_language, readiness_status, updated_at
                    )
                    SELECT id, 'vi', name, COALESCE(description, ''),
                           TRUE,
                           CASE WHEN is_active THEN 'published' ELSE 'draft' END,
                           now()
                    FROM pois
                    ON CONFLICT (poi_id, language_code) DO UPDATE
                    SET localized_name = EXCLUDED.localized_name,
                        localized_description = EXCLUDED.localized_description,
                        is_source_language = TRUE,
                        readiness_status = EXCLUDED.readiness_status,
                        updated_at = now()
                    """
                )
            )
            await db.commit()
            print(f"Synchronized {result.rowcount} Vietnamese localizations from PostgreSQL.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
