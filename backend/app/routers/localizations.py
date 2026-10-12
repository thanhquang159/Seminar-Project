"""Dịch on-demand: dịch và upsert bản dịch cho POI thiếu ngôn ngữ."""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import YeuCauDangNhap
from app.db import get_database
from app.limits import LangField
from app.services.localization import dam_bao_index, dich_va_luu
from app.services.ratelimit import khoa_cho, kiem_tra

router = APIRouter(prefix="/localizations", tags=["localizations"])


class DichYeuCau(BaseModel):
    # Chỉ giới hạn độ dài để chặn rác khổng lồ; hình dạng ObjectId vẫn do
    # `ObjectId()` bên dưới quyết định để giữ nguyên 400 cho id sai định dạng.
    poi_id: str = Field(min_length=1, max_length=64)
    lang: LangField


@router.post("/on-demand", summary="Dịch on-demand một POI sang ngôn ngữ mới")
async def dich_on_demand(body: DichYeuCau, request: Request, user: dict = YeuCauDangNhap) -> dict:
    try:
        oid = ObjectId(body.poi_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None
    db = get_database()
    await kiem_tra(db, khoa_cho(request, user), "/localizations/on-demand")
    await dam_bao_index(db)
    ban_dich = await dich_va_luu(db, oid, body.lang)
    return {"poi_id": body.poi_id, "lang": ban_dich["lang"], "name": ban_dich["name"]}
