"""VI phải dùng nội dung nguồn khi thiếu localization; kiểm tra SQL/HTTP thật, rollback."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pois import router
from app.postgres import engine, get_db
from app.services.sync import lay_phien_ban


def test_vietnamese_source_is_not_replaced_by_english(pytestconfig):
    if not pytestconfig.getoption("--run-publication-db"):
        pytest.skip("Thêm --run-publication-db để kiểm tra ngôn ngữ với PostgreSQL thật")

    async def scenario():
        engine.echo = False
        poi_id = uuid4()
        try:
            async with engine.connect() as connection:
                outer = await connection.begin()
                try:
                    async with AsyncSession(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as db:
                        cursor = await lay_phien_ban(db)
                        await db.execute(
                            text("""
                            INSERT INTO pois (id,name,description,category,address_line,latitude,longitude,
                                publication_status,is_active)
                            VALUES (:id,'Ốc Tô kiểm thử','Quán ốc lâu đời, giá cả bình dân','other','Test',
                                10.761,106.6795,'published',TRUE)
                        """),
                            {"id": poi_id},
                        )
                        await db.execute(
                            text("""
                            INSERT INTO poi_localizations (poi_id,language_code,localized_name,
                                localized_description,readiness_status,audio_status,audio_url)
                            VALUES (:id,'en','Snail Bowl test','A long-standing snail eatery',
                                'ready','ready','/static/audio/test-en.mp3?l=en')
                        """),
                            {"id": poi_id},
                        )
                        await db.commit()

                        app = FastAPI()
                        app.include_router(router)
                        app.dependency_overrides[get_db] = lambda: db
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as client:

                            def check_vi(item, audio=None):
                                assert item["name"] == "Ốc Tô kiểm thử"
                                assert item["description"] == "Quán ốc lâu đời, giá cả bình dân"
                                assert item["lang"] == "vi"
                                assert item["is_fallback"] is False
                                assert item["audio_url"] == audio

                            def mine(items):
                                return next(p for p in items if p["id"] == str(poi_id))

                            check_vi((await client.get(f"/poi/{poi_id}?lang=vi")).json())
                            check_vi(mine((await client.get("/poi?lang=vi")).json()))
                            check_vi(
                                mine((await client.get("/poi/load-all?lang=vi")).json()["pois"])
                            )
                            check_vi(
                                mine(
                                    (
                                        await client.get(
                                            f"/poi/delta?updated_after={cursor}&lang=vi"
                                        )
                                    ).json()["updated"]
                                )
                            )
                            check_vi(
                                mine(
                                    (
                                        await client.get(
                                            "/poi/nearby?lat=10.761&lng=106.6795&lang=vi"
                                        )
                                    ).json()
                                )
                            )
                            check_vi(
                                mine(
                                    (
                                        await client.get(
                                            "/poi/hotset?lat=10.761&lng=106.6795&lang=vi"
                                        )
                                    ).json()
                                )
                            )

                            english = (await client.get(f"/poi/{poi_id}?lang=en")).json()
                            assert english["name"] == "Snail Bowl test"
                            assert english["lang"] == "en" and not english["is_fallback"]
                            assert english["audio_url"].endswith("l=en")
                            japanese = (await client.get(f"/poi/{poi_id}?lang=ja")).json()
                            assert japanese["lang"] == "en" and japanese["is_fallback"]

                            await db.execute(
                                text("""
                                INSERT INTO poi_localizations (poi_id,language_code,localized_name,
                                    localized_description,is_source_language,readiness_status,audio_status,audio_url)
                                SELECT id,'vi',name,description,TRUE,'ready','ready','/static/audio/test-vi.mp3?l=vi'
                                FROM pois WHERE id=:id
                            """),
                                {"id": poi_id},
                            )
                            await db.commit()
                            check_vi(
                                (await client.get(f"/poi/{poi_id}?lang=vi")).json(),
                                "/static/audio/test-vi.mp3?l=vi",
                            )
                            assert (await client.get(f"/poi/{poi_id}?lang=en")).json() == english

                            # Không có bản dịch nào: vẫn biết nội dung nguồn là VI.
                            await db.execute(
                                text("DELETE FROM poi_localizations WHERE poi_id=:id"),
                                {"id": poi_id},
                            )
                            await db.commit()
                            check_vi((await client.get(f"/poi/{poi_id}?lang=vi")).json())
                            fallback = (await client.get(f"/poi/{poi_id}?lang=en")).json()
                            assert fallback["lang"] == "vi" and fallback["is_fallback"]
                            assert fallback["audio_url"] is None
                finally:
                    await outer.rollback()
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM pois WHERE id=:id"), {"id": poi_id}
                    )
                ).scalar_one() == 0
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=90))
