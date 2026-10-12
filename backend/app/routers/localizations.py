"""Nhập bản dịch POI: admin gửi tên + mô tả đã dịch, server upsert."""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.audit import ghi_audit
from app.auth import doi_quyen
from app.db import get_database
from app.limits import LangField
from app.services.localization import dam_bao_index, luu_ban_dich
from app.services.ratelimit import khoa_cho, kiem_tra

router = APIRouter(prefix="/localizations", tags=["localizations"])

DuocSuaPoi = doi_quyen("poi:update")


class DichYeuCau(BaseModel):
    # `poi_id` chỉ giới hạn độ dài để chặn rác khổng lồ; hình dạng ObjectId vẫn
    # do `ObjectId()` bên dưới quyết định để giữ nguyên 400 cho id sai định dạng.
    poi_id: str = Field(min_length=1, max_length=64)
    lang: LangField
    # Bắt buộc có nội dung: trước đây server tự dịch nên không cần người nhập,
    # giờ không có nội dung thì upsert ra một bản rỗng rồi POI treo ở
    # `audio_status=processing` mãi (hoan_tat_audio không bao giờ thấy audio).
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


@router.post("/on-demand", summary="Nhập bản dịch POI (admin gửi nội dung đã dịch)")
async def dich_on_demand(body: DichYeuCau, request: Request, user: dict = DuocSuaPoi) -> dict:
    try:
        oid = ObjectId(body.poi_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None
    db = get_database()
    await kiem_tra(db, khoa_cho(request, user), "/localizations/on-demand")
    await dam_bao_index(db)
    if await db["pois"].find_one({"_id": oid}, {"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    ban_dich = await luu_ban_dich(db, oid, body.lang, body.name, body.description)
    await ghi_audit(db, user["username"], "poi:translate", f"poi:{body.poi_id}:{body.lang}")
    return {"poi_id": body.poi_id, "lang": ban_dich["lang"], "name": ban_dich["name"]}