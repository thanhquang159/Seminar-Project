"""Báo cáo POI nào còn thiếu bản dịch — để admin biết cần nhập tay cái gì.

Trước SEC-010 route này chạy dịch nền toàn corpus. Sau khi gỡ deep-translator
thì không còn gì để "hâm nóng", nhưng danh sách thiếu vẫn có giá trị thật: đó
chính là việc cần làm, nên route đổi từ hành động sang báo cáo đọc-only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import doi_quyen
from app.postgres import get_db
from app.services.localization import NGON_NGU_UU_TIEN

router = APIRouter(prefix="/localizations", tags=["localizations-warmup"])

DuocCapNhatPoi = doi_quyen("poi:update")


@router.get("/warmup-status", summary="Danh sách (POI, ngôn ngữ) còn thiếu bản dịch")
async def trang_thai_ham_nong(
    db: Annotated[AsyncSession, Depends(get_db)], _user: dict = DuocCapNhatPoi
) -> dict:
    languages = ", ".join(f"('{language}')" for language in NGON_NGU_UU_TIEN)
    result = await db.execute(
        text(
            f"""
            WITH poi_batch AS (
                SELECT id
                FROM pois
                ORDER BY id
                LIMIT 5000
            ),
            languages(language_code) AS (VALUES {languages})
            SELECT poi_batch.id::text AS poi_id, languages.language_code AS lang
            FROM poi_batch
            CROSS JOIN languages
            LEFT JOIN poi_localizations AS l
              ON l.poi_id = poi_batch.id
             AND l.language_code = languages.language_code
            WHERE l.id IS NULL
            ORDER BY poi_batch.id, languages.language_code
            """
        )
    )
    thieu = [dict(row) for row in result.mappings().all()]
    return {"tong": len(thieu), "thieu": thieu}
