"""UI bundle hai làn: 5 ngôn ngữ tĩnh, còn lại dịch nền + source_hash."""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter
from fastapi import Path as PathParam

from app.db import get_database
from app.limits import MA_NGON_NGU
from app.services.localization import dich_van_ban

router = APIRouter(prefix="/ui-bundles", tags=["i18n"])

THU_MUC_UI = Path(__file__).resolve().parents[2] / "static" / "ui"
NGON_NGU_CHINH = ("vi", "en", "zh", "ja", "ko")

# SEC-001: endpoint này công khai và locale lạ sẽ kích hoạt dịch nền cả bộ UI.
# Không chặn thì một kẻ tấn công chỉ cần quét locale để biến server thành máy
# gọi Google Translate hàng trăm nghìn lần từ IP của mình. Giữ một số task
# dịch chạy song song là đủ để có tác dụng, nhiều hơn chỉ tự đốt bản thân.
DICH_NEN_DONG_CONG = 1
_sem_dich = asyncio.Semaphore(DICH_NEN_DONG_CONG)

# `Path(...)` không dùng làm giá trị mặc định được (FastAPI cấm), nên ràng buộc
# phải nằm trong Annotated.
Locale = Annotated[str, PathParam(min_length=2, max_length=10, pattern=MA_NGON_NGU)]


def doc_bundle_tinh(locale: str) -> dict | None:
    tep = THU_MUC_UI / f"{locale}.json"
    if not tep.is_file():
        return None
    return json.loads(tep.read_text(encoding="utf-8"))


def source_hash(bundle_en: dict) -> str:
    return hashlib.md5(json.dumps(bundle_en, sort_keys=True).encode()).hexdigest()


@router.get("/{locale}", summary="Bundle UI, lạ thì tiếng Anh + pending")
async def lay_bundle(locale: Locale) -> dict:
    bundle_en = doc_bundle_tinh("en") or {}
    if locale in NGON_NGU_CHINH:
        bundle = doc_bundle_tinh(locale) or bundle_en
        return {"locale": locale, "status": "ready", "bundle": bundle, "source_hash": source_hash(bundle_en)}
    db = get_database()
    ban = await db["ui_bundles"].find_one({"locale": locale})
    hash_hien_tai = source_hash(bundle_en)
    if ban and ban.get("status") == "ready" and ban.get("source_hash") == hash_hien_tai:
        return {"locale": locale, "status": "ready", "bundle": ban["bundle"], "source_hash": hash_hien_tai}
    if not ban or ban.get("status") != "translating":
        await db["ui_bundles"].update_one(
            {"locale": locale},
            {"$set": {"locale": locale, "status": "translating", "source_hash": hash_hien_tai}},
            upsert=True,
        )
        asyncio.create_task(dich_nen(locale, bundle_en, hash_hien_tai))
    return {"locale": locale, "status": "pending", "bundle": bundle_en, "source_hash": hash_hien_tai}


async def dich_nen(locale: str, bundle_en: dict, hash_moi: str) -> None:
    """Dịch long-tail nền từng khóa, xong thì ready.

    `dich_van_ban` là blocking I/O (deep-translator gọi thẳng Google), chạy
    thẳng trong event loop sẽ treo **toàn bộ API** suốt thời gian dịch
    (hàng trăm khóa × vài trăm ms). Vì vậy đẩy sang thread và giới hạn số
    task dịch chạy song song.
    """
    async with _sem_dich:
        try:
            from app.db import get_database as _db

            db = _db()
            ket_qua = {}
            for khoa, gia_tri in bundle_en.items():
                try:
                    ket_qua[khoa] = await asyncio.to_thread(dich_van_ban, str(gia_tri), locale)
                except Exception:
                    ket_qua[khoa] = gia_tri
            await db["ui_bundles"].update_one(
                {"locale": locale},
                {"$set": {"bundle": ket_qua, "status": "ready", "source_hash": hash_moi}},
            )
        except Exception:
            pass
