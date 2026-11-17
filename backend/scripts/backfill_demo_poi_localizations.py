"""Add missing translations for the published Khanh Hoi demo bakery."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.postgres import AsyncSessionLocal, close_db

SOURCE_NAME = "tiệm bánh khánh hội (demo)"
DRAFT_SOURCE_NAME = "quầy món ngon (draft demo)"
TRANSLATIONS = (
    (
        "en",
        "Khanh Hoi Bakery (Demo)",
        "A sample bakery featuring a selection of sweet pastries.",
    ),
    (
        "zh",
        "庆会面包店（演示）",
        "介绍一家提供多种甜点的示范面包店。",
    ),
    (
        "ja",
        "カインホイのベーカリー（デモ）",
        "さまざまな甘いパンやお菓子を紹介するサンプルのベーカリーです。",
    ),
    (
        "ko",
        "카인호이 베이커리(데모)",
        "다양한 달콤한 빵과 디저트를 소개하는 예시 베이커리입니다.",
    ),
)


async def backfill(db: AsyncSession) -> tuple[list[str], bool]:
    result = await db.execute(
        text(
            """
            SELECT id
            FROM pois
            WHERE lower(regexp_replace(btrim(name), '\\s+', ' ', 'g')) = :name
              AND publication_status = 'published'
              AND is_active IS TRUE
            """
        ),
        {"name": SOURCE_NAME},
    )
    target_ids = result.scalars().all()
    if len(target_ids) != 1:
        raise RuntimeError(
            "Expected exactly one active, published Khanh Hoi demo bakery; "
            f"found {len(target_ids)}."
        )
    poi_id = target_ids[0]

    inserted = await db.execute(
        text(
            """
            INSERT INTO poi_localizations (
                poi_id, language_code, localized_name, localized_description,
                is_source_language, readiness_status, updated_at
            )
            VALUES
                (:poi_id, 'en', :en_name, :en_description, FALSE, 'published', now()),
                (:poi_id, 'zh', :zh_name, :zh_description, FALSE, 'published', now()),
                (:poi_id, 'ja', :ja_name, :ja_description, FALSE, 'published', now()),
                (:poi_id, 'ko', :ko_name, :ko_description, FALSE, 'published', now())
            ON CONFLICT (poi_id, language_code) DO NOTHING
            RETURNING language_code
            """
        ),
        {
            "poi_id": poi_id,
            **{
                f"{language}_{field}": value
                for language, name, description in TRANSLATIONS
                for field, value in (("name", name), ("description", description))
            },
        },
    )
    languages_added = [row[0] for row in inserted.all()]
    if languages_added:
        await db.execute(
            text("UPDATE pois SET updated_at = now() WHERE id = :poi_id"),
            {"poi_id": poi_id},
        )

    draft_result = await db.execute(
        text(
            """
            SELECT id
            FROM pois
            WHERE lower(regexp_replace(btrim(name), '\\s+', ' ', 'g')) = :name
              AND publication_status = 'draft'
              AND is_active IS TRUE
            """
        ),
        {"name": DRAFT_SOURCE_NAME},
    )
    draft_ids = draft_result.scalars().all()
    if len(draft_ids) > 1:
        raise RuntimeError(
            "Expected at most one active Quay Mon Ngon draft demo POI; "
            f"found {len(draft_ids)}."
        )
    draft_deactivated = bool(draft_ids)
    if draft_deactivated:
        await db.execute(
            text(
                """
                UPDATE pois
                SET is_active = FALSE, updated_at = now()
                WHERE id = :poi_id
                """
            ),
            {"poi_id": draft_ids[0]},
        )

    await db.commit()
    return languages_added, draft_deactivated


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db:
            languages_added, draft_deactivated = await backfill(db)
            print(
                "Added missing Khanh Hoi bakery translations: "
                + (", ".join(languages_added) if languages_added else "none")
            )
            if draft_deactivated:
                print("Deactivated the incorrectly active Quay Mon Ngon draft POI.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
