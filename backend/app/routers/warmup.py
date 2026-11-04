"""Báo cáo POI nào còn thiếu bản dịch — để admin biết cần nhập tay cái gì.

Trước SEC-010 route này chạy dịch nền toàn corpus. Sau khi gỡ deep-translator
thì không còn gì để "hâm nóng", nhưng danh sách thiếu vẫn có giá trị thật: đó
chính là việc cần làm, nên route đổi từ hành động sang báo cáo đọc-only.
"""

from fastapi import APIRouter

from app.auth import doi_quyen
from app.db import get_database
from app.services.localization import NGON_NGU_UU_TIEN

router = APIRouter(prefix="/localizations", tags=["localizations-warmup"])

DuocCapNhatPoi = doi_quyen("poi:update")


@router.get("/warmup-status", summary="Danh sách (POI, ngôn ngữ) còn thiếu bản dịch")
async def trang_thai_ham_nong(_user: dict = DuocCapNhatPoi) -> dict:
    db = get_database()
    co = {
        (d["poi_id"], d["lang"])
        async for d in db["poi_localizations"].find({}, {"poi_id": 1, "lang": 1})
    }
    thieu = []
    async for poi in db["pois"].find({}, {"name": 1, "localized": 1}).limit(5000):
        for lang in NGON_NGU_UU_TIEN:
            if (poi["_id"], lang) not in co:
                thieu.append({"poi_id": str(poi["_id"]), "lang": lang})
    return {"tong": len(thieu), "thieu": thieu}