"""Đọc trạng thái audio/duyệt POI để chẩn đoán; không sửa dữ liệu."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.postgres import engine
from app.services.publication import read_publication


async def main(poi_id=None):
    engine.echo = False
    queries = {
        "constraints": """SELECT conname, pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=r.relnamespace
            WHERE n.nspname='public' AND r.relname='audio_tasks' AND contype='c'""",
        "tasks": """SELECT t.id, p.name, p.publication_status, t.poi_id,
            t.language_code, t.task_status, t.progress_percent, t.error_message,
            t.heartbeat_at, t.updated_at, t.created_at, l.audio_status,
            l.readiness_status, l.audio_url
            FROM audio_tasks t JOIN pois p ON p.id=t.poi_id
            LEFT JOIN poi_localizations l ON l.id=t.localization_id
            ORDER BY t.updated_at DESC LIMIT 30""",
        "pois": """SELECT p.id, p.name, p.publication_status, p.is_active,
            EXISTS(SELECT 1 FROM poi_submissions s WHERE s.poi_id=p.id AND s.status='pending') AS pending_update,
            EXISTS(SELECT 1 FROM owner_notifications n WHERE n.reference_id=p.id
              AND n.notification_type='poi_submission_approved') AS approval_notification
            FROM pois p ORDER BY p.updated_at DESC LIMIT 30""",
        "submissions": """SELECT id, poi_id, submission_type, status,
            content_snapshot->>'name' AS name, submitted_at, reviewed_at
            FROM poi_submissions ORDER BY submitted_at DESC LIMIT 20""",
    }
    try:
        async with asyncio.timeout(25), engine.connect() as connection:
            if poi_id:
                async with AsyncSession(bind=connection) as db:
                    state = await read_publication(db, poi_id)
                    print(json.dumps({"publication": state}, ensure_ascii=False, default=str))
                    url = (
                        await db.execute(
                            text("""
                        SELECT audio_url FROM poi_localizations WHERE poi_id=:id AND language_code='en'
                    """),
                            {"id": poi_id},
                        )
                    ).scalar_one_or_none()
                    if url and url.startswith("/static/audio/"):
                        from httpx import ASGITransport, AsyncClient

                        from app.main import app

                        # Chỉ đọc file qua HTTP nội bộ; không chạy lifespan/khôi phục hàng đợi.
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as client:
                            response = await client.get(url)
                            print(
                                json.dumps(
                                    {
                                        "audio_http_status": response.status_code,
                                        "audio_content_type": response.headers.get("content-type"),
                                        "audio_bytes": len(response.content),
                                    }
                                )
                            )
                return
            for name, query in queries.items():
                rows = await connection.execute(text(query))
                print(
                    json.dumps(
                        {name: [dict(row) for row in rows.mappings()]},
                        ensure_ascii=False,
                        default=str,
                    )
                )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poi-id", type=UUID)
    args = parser.parse_args()
    asyncio.run(main(args.poi_id))
