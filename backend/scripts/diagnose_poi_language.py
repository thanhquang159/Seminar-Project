"""Đối chiếu nguồn, bản dịch và API công khai theo VI/EN; chỉ đọc dữ liệu."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import app
from app.postgres import AsyncSessionLocal, engine, get_db


def output(label, value):
    print(json.dumps({label: value}, ensure_ascii=False, default=str))


async def main(poi_id):
    engine.echo = False
    try:
        async with asyncio.timeout(35), AsyncSessionLocal() as db:
            source = await db.execute(
                text("""
                SELECT id, name, description, publication_status, is_active
                FROM pois WHERE id=:id
            """),
                {"id": poi_id},
            )
            output("source", [dict(row) for row in source.mappings()])
            locales = await db.execute(
                text("""
                SELECT language_code, localized_name, localized_description,
                    readiness_status, is_fallback, audio_status, audio_url
                FROM poi_localizations WHERE poi_id=:id ORDER BY language_code
            """),
                {"id": poi_id},
            )
            output("localizations", [dict(row) for row in locales.mappings()])

            async def database():
                yield db

            app.dependency_overrides[get_db] = database
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    for lang in ("vi", "en"):
                        response = await client.get(f"/poi/{poi_id}?lang={lang}")
                        output(
                            f"public_{lang}",
                            {"status": response.status_code, "body": response.json()},
                        )
                        url = response.json().get("audio_url")
                        if url and url.startswith("/static/audio/"):
                            audio = await client.get(url)
                            output(
                                f"audio_{lang}",
                                {"status": audio.status_code, "bytes": len(audio.content)},
                            )
            finally:
                app.dependency_overrides.pop(get_db, None)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("poi_id", type=UUID)
    asyncio.run(main(parser.parse_args().poi_id))
