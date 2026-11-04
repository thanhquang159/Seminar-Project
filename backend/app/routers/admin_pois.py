"""Route quản trị POI: tạo, sửa, xóa. Mọi route đòi đăng nhập."""

from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.audit import ghi_audit
from app.auth import doi_quyen
from app.db import get_database
from app.routers.poi import doi_poi
from app.services import images
from app.services.sync import cham_dataset, ghi_mo_xoa

router = APIRouter(prefix="/admin/pois", tags=["admin-poi"])

DuocTaoPoi = doi_quyen("poi:create")
DuocSuaPoi = doi_quyen("poi:update")
DuocXoaPoi = doi_quyen("poi:delete")


class PoiNhap(BaseModel):
    """Dữ liệu admin nhập khi tạo/sửa, validate ở biên (POI-010)."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    trigger_radius: float = Field(default=30, ge=5, le=200)
    audio_priority: int = Field(default=0, ge=0, le=100)


def doi_id(poi_id: str) -> ObjectId:
    """Đổi chuỗi thành ObjectId, rác thì 400 chứ không 500."""
    try:
        return ObjectId(poi_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None


@router.post("", status_code=201, summary="Tạo POI")
async def tao_poi(body: PoiNhap, user: dict = DuocTaoPoi) -> dict:
    db = get_database()
    du_lieu = body.model_dump()
    du_lieu.update(
        {
            "is_active": False,
            "images": [],
            "audio_status": "processing",
            "activation_requested": True,
            "updated_at": datetime.now(UTC),
            "version": await cham_dataset(db),
        }
    )
    ket_qua = await db["pois"].insert_one(du_lieu)
    doc = await db["pois"].find_one({"_id": ket_qua.inserted_id})
    assert doc is not None
    await ghi_audit(db, user["username"], "poi:create", f"poi:{ket_qua.inserted_id}")
    from app.services.audio_svc import kich_hoat_sinh_audio

    await kich_hoat_sinh_audio(db, ket_qua.inserted_id)
    return doi_poi(doc)


@router.put("/{poi_id}", summary="Sửa POI")
async def sua_poi(poi_id: str, body: PoiNhap, user: dict = DuocSuaPoi) -> dict:
    db = get_database()
    oid = doi_id(poi_id)
    cu = await db["pois"].find_one({"_id": oid})
    if cu is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    du_lieu_sua = body.model_dump()
    du_lieu_sua["updated_at"] = datetime.now(UTC)
    ket_qua = await db["pois"].update_one({"_id": oid}, {"$set": du_lieu_sua})
    if ket_qua.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    # Mô tả đổi thì sinh lại audio, tạm ẩn chờ tiếng Anh.
    if body.description != cu.get("description", "") or body.name != cu.get("name", ""):
        from app.services.audio_svc import kich_hoat_sinh_audio

        await kich_hoat_sinh_audio(db, oid)
    await db["pois"].update_one({"_id": oid}, {"$set": {"version": await cham_dataset(db)}})
    doc = await db["pois"].find_one({"_id": oid})
    assert doc is not None
    await ghi_audit(db, user["username"], "poi:update", f"poi:{poi_id}")
    return doi_poi(doc)


@router.delete("/{poi_id}", status_code=204, summary="Xóa POI")
async def xoa_poi(poi_id: str, user: dict = DuocXoaPoi) -> Response:
    db = get_database()
    oid = doi_id(poi_id)
    ket_qua = await db["pois"].delete_one({"_id": oid})
    if ket_qua.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    # Dọn bản dịch liên quan, chưa transaction (cần replica set, PROD-004).
    await db["poi_localizations"].delete_many({"poi_id": oid})
    phien_ban = await cham_dataset(db)
    await ghi_mo_xoa(db, oid, phien_ban)
    await ghi_audit(db, user["username"], "poi:delete", f"poi:{poi_id}")
    return Response(status_code=204)


# --- Ảnh POI (SEC-012) --------------------------------------------------------
# Ba lớp phòng thủ theo đúng thứ tự: xác ảnh thật (magic bytes + Pillow) →
# đếm số lượng trên dữ liệu thật → mới ghi đĩa. Tên tệp sinh từ UUID nên
# tên người dùng gửi lên không bao giờ chạm vào đường dẫn.
@router.get("/{poi_id}/images", summary="Liệt kê ảnh của POI")
async def liet_ke_anh(poi_id: str, user: dict = DuocSuaPoi) -> dict:
    db = get_database()
    oid = doi_id(poi_id)
    doc = await db["pois"].find_one({"_id": oid}, {"images": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    return {"images": doc.get("images", [])}


@router.post("/{poi_id}/images", status_code=201, summary="Tải ảnh lên POI")
async def tai_anh(poi_id: str, file: UploadFile, user: dict = DuocSuaPoi) -> dict:
    db = get_database()
    oid = doi_id(poi_id)
    doc = await db["pois"].find_one({"_id": oid}, {"images": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")

    try:
        # Đếm trước khi đọc tệp: POI đã đủ 8 ảnh thì không cần nạp 5 MB vào RAM.
        images.kiem_tra_so_luong(len(doc.get("images") or []))
        du_lieu = await file.read()
        duoi = images.kiem_tra_anh(du_lieu, images.ten_tuyen_du_co_hinh(file.filename or ""))
    except images.LoiAnh as loi:
        raise HTTPException(status_code=loi.so_loi, detail=str(loi)) from None

    hien_co = doc.get("images") or []

    ten = images.ten_an_toan(du_lieu, duoi)
    tep = images.duong_dan_luu(poi_id, ten)
    tep.parent.mkdir(parents=True, exist_ok=True)
    tep.write_bytes(du_lieu)

    duong_dan = images.url_cua(ten, poi_id)
    await db["pois"].update_one(
        {"_id": oid}, {"$push": {"images": duong_dan}, "$set": {"updated_at": datetime.now(UTC)}}
    )
    await ghi_audit(db, user["username"], "poi:image_add", f"poi:{poi_id} {ten}")
    return {"images": [*hien_co, duong_dan], "moi_tai": duong_dan}


@router.delete("/{poi_id}/images/{ten}", summary="Xóa ảnh của POI")
async def xoa_anh(poi_id: str, ten: str, user: dict = DuocSuaPoi) -> dict:
    db = get_database()
    oid = doi_id(poi_id)
    doc = await db["pois"].find_one({"_id": oid}, {"images": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    hien_co = doc.get("images") or []
    duong_dan = images.url_cua(ten, poi_id)
    if duong_dan not in hien_co:
        duong_dan_cu = images.url_cua(ten)
        if duong_dan_cu in hien_co:
            duong_dan = duong_dan_cu
        else:
            raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")

    ket_qua = await db["pois"].update_one(
        {"_id": oid}, {"$pull": {"images": duong_dan}, "$set": {"updated_at": datetime.now(UTC)}}
    )
    if ket_qua.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    try:
        images.duong_dan_luu(poi_id, ten).unlink(missing_ok=True)
    except images.LoiAnh as loi:
        raise HTTPException(status_code=loi.so_loi, detail=str(loi)) from None
    await ghi_audit(db, user["username"], "poi:image_delete", f"poi:{poi_id} {ten}")
    con_lai = [d for d in hien_co if d != duong_dan]
    return {"images": con_lai}
