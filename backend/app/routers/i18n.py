"""UI bundle: 5 ngôn ngữ tĩnh trong `static/ui/*.json`, không dịch máy.

Trước SEC-010, locale ngoài 5 ngôn ngữ chính sẽ kích hoạt dịch nền bằng
deep-translator. Gói đó bị gỡ vì không có bản vá cho PYSEC-2022-252, nên nhánh
dịch nền biến mất hoàn toàn: locale lạ trả 404 thay vì "đang dịch, chờ thêm".
Có một hệ quả thuận lợi: `/ui-bundles/{locale}` giờ là endpoint thuần đọc file
tĩnh, không còn đường ghi vào DB — vector tấn công SEC-001 ở đây biến mất theo.
"""

import hashlib
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam

from app.limits import MA_NGON_NGU

router = APIRouter(prefix="/ui-bundles", tags=["i18n"])

THU_MUC_UI = Path(__file__).resolve().parents[2] / "static" / "ui"
NGON_NGU_CHINH = ("vi", "en", "zh", "ja", "ko")

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


@router.get("/{locale}", summary="Bundle UI của 1 trong 5 ngôn ngữ chính")
async def lay_bundle(locale: Locale) -> dict:
    if locale not in NGON_NGU_CHINH:
        raise HTTPException(
            status_code=404, detail=f"Không có bundle UI cho locale '{locale}'"
        )
    bundle_en = doc_bundle_tinh("en") or {}
    bundle = doc_bundle_tinh(locale) or bundle_en
    return {"locale": locale, "status": "ready", "bundle": bundle, "source_hash": source_hash(bundle_en)}
