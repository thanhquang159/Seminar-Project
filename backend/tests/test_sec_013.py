"""SEC-013 — điểm lại OWASP Top 10, tập trung vào khe giữa các lớp.

12 task SEC-001..012 đã vá từng lỗ hổng một. Cái chưa ai làm: hai lớp đều đúng
nhưng nối với nhau lại hở. Năm lỗ hổng dưới đây đều thuộc kiểu đó — không cái
nào là lỗi của riêng SEC-001 hay riêng SEC-004.

1. **A01 IDOR** — `POST /owner/registrations/{username}/approve` nhận `username`
   từ URL. Route kiểm quyền `user:update` nhưng KHÔNG đối chiếu `username` với
   user đang đăng nhập ⇒ kẻ có quyền duyệt đơn của bất kỳ ai. Khóa bằng cách
   đối chiếu, như `owner/submissions` đã làm với `owner_username`.
2. **A01 IDOR (cùng loại)** — `/owner/submissions/{sid}/approve` không kiểm
   submission đó thuộc về ai, và **dùng lại `poi_id` do chính owner gửi lên**:
   owner A gửi submission sửa POI gắn `poi_id` của quán owner B → admin duyệt →
   nội dung của A ghi đè lên quán của B. Lỗi nằm ở chỗ "gửi" có kiểm mà "duyệt"
   không kiểm lại.
3. **A03 phun thông tin nội bộ** — `LoiAnh` của SEC-012 mang thông báo đọc
   được từ đĩa vào response, và `mongo_error` của `/health` đọc nguyên chuỗi
   exception (kèm host/port). Che dần, không để lộ nội bộ.
4. **A07 chống brute force không hoàn chỉnh** — `doi_mat_khau` chỉ gọi
   `login_guard.xoa_that_bai` khi thành công, nên **lần SAI không bị đếm**:
   1000 lần đoán mật khẩu cũ trong 15 phút mà không bị chặn. SEC-002 chỉ bọc
   `/admin/auth/login`, không bọc route này.
5. **A04 cấu hình thiếu** — `ai_provider="http"` mà `ai_api_url` rỗng thì
   request đi tới URL rỗng, lỗi trả về client kèm chi tiết provider. Phải
   fail-fast lúc khởi động, như CORS đã làm trong SEC-003.
"""

import io

from fastapi.testclient import TestClient
from PIL import Image
from pymongo import MongoClient

from app.config import settings

settings.mongodb_db_name = "amds_test"

from app.auth import (  # noqa: E402
    bam_mat_khau,  # noqa: E402
    dung_mat_khau,
    tao_token,
)
from app.main import app  # noqa: E402


def _ket_noi():
    return MongoClient(settings.mongodb_uri)


def _don_sach(mongo) -> None:
    db = mongo[settings.mongodb_db_name]
    for ten in ("admin_users", "owner_registrations", "pois", "owner_submissions"):
        db[ten].delete_many({})


def _tao_user(mongo, username, role, quyen=None):
    db = mongo[settings.mongodb_db_name]
    doc = {
        "username": username,
        "password_hash": bam_mat_khau("pw123456"),
        "role": role,
        "phi_en_ver": 1,
    }
    if quyen is not None:
        doc["permissions"] = quyen
    db["admin_users"].insert_one(doc)


def bearer(username, role, quyen) -> dict[str, str]:
    return {"Authorization": f"Bearer {tao_token(username, role, 'access', quyen)}"}


def anh_nho() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (12, 12), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


# --- 1 + 2: IDOR ----------------------------------------------------------


def test_khong_tu_duyet_don_cua_minh() -> None:
    """A01. Chủ quán không được tự duyệt đơn của chính mình.

    Bối cảnh: đây là quyết định sau khi hỏi người ra đề. Route vốn là "admin
    duyệt đơn của người khác" nên `username` trên URL là bắt buộc phải tin —
    đòi `username == người gọi` sẽ khóa luôn cả luồng đúng. Vậy chặn đúng kịch
    bản nguy hiểm nhất: chủ quán tự nâng quyền mình. IDOR mức thấp (admin A
    duyệt đơn B) vẫn còn và đã ghi thành việc cần quyết định nghiệp vụ.
    """
    mongo = _ket_noi()
    _don_sach(mongo)
    db = mongo[settings.mongodb_db_name]
    _tao_user(mongo, "tu_duyet", "poi_owner", ["user:update"])
    db["owner_registrations"].insert_one(
        {"username": "tu_duyet", "status": "pending", "admin_note": "", "created_at": None}
    )
    mongo.close()

    with TestClient(app) as c:
        res = c.post(
            "/owner/registrations/tu_duyet/approve",
            headers=bearer("tu_duyet", "poi_owner", ["user:update"]),
        )
    assert res.status_code == 403, res.status_code
    mongo = _ket_noi()
    don = mongo[settings.mongodb_db_name]["owner_registrations"].find_one({"username": "tu_duyet"})
    assert don["status"] == "pending", "tự duyệt thành công"
    mongo.close()


def test_admin_van_duyet_don_nguoi_khac_duoc() -> None:
    """Vá IDOR không được làm hỏng luồng đúng: admin vẫn duyệt đơn của người khác."""
    mongo = _ket_noi()
    _don_sach(mongo)
    db = mongo[settings.mongodb_db_name]
    _tao_user(mongo, "admin_duyet", "super_admin", ["user:update"])
    db["owner_registrations"].insert_one(
        {"username": "chuquan_khac", "status": "pending", "admin_note": "", "created_at": None}
    )
    mongo.close()

    with TestClient(app) as c:
        res = c.post(
            "/owner/registrations/chuquan_khac/approve",
            headers=bearer("admin_duyet", "super_admin", ["user:update"]),
        )
    assert res.status_code == 200, res.status_code
    mongo = _ket_noi()
    don = mongo[settings.mongodb_db_name]["owner_registrations"].find_one({"username": "chuquan_khac"})
    assert don["status"] == "approved"
    mongo.close()


def test_khong_tu_tu_choi_don_cua_minh() -> None:
    """A01. Cùng luật áp cho `/reject`, không chỉ `/approve`."""
    mongo = _ket_noi()
    _don_sach(mongo)
    db = mongo[settings.mongodb_db_name]
    _tao_user(mongo, "tu_choi", "poi_owner", ["user:update"])
    db["owner_registrations"].insert_one(
        {"username": "tu_choi", "status": "pending", "admin_note": "", "created_at": None}
    )
    mongo.close()

    with TestClient(app) as c:
        res = c.post(
            "/owner/registrations/tu_choi/reject",
            headers=bearer("tu_choi", "poi_owner", ["user:update"]),
            json={"admin_note": "tự từ chối"},
        )
    assert res.status_code == 403, res.status_code


def test_submission_khong_ghi_de_len_poi_cua_chu_khac() -> None:
    """A01. Đơn sửa POI của người này mà duyệt thì phải ghi lên POI của người đó.

    Cách tấn công: owner A gửi submission sửa POI, nhưng `poi_id` trỏ tới quán
    của owner B (owner B bị tấn công). Route "gửi" có kiểm `owner_username`, nên
    A không gửi trực tiếp được — nhưng A sửa được `poi_id` trong DB hoặc gửi
    trước khi B nhận quán. Chỗ an toàn là lúc DUYỆT phải đối chiếu lại.
    """
    from bson import ObjectId

    mongo = _ket_noi()
    _don_sach(mongo)
    db = mongo[settings.mongodb_db_name]
    _tao_user(mongo, "chuA", "poi_owner", ["poi:create"])
    _tao_user(mongo, "chuB", "poi_owner", ["poi:create"])
    _tao_user(mongo, "admin", "super_admin", ["poi:approve"])
    poi_b = db["pois"].insert_one(
        {"name": "Quán của B", "description": "ngon", "lat": 10.0, "lng": 106.0, "owner_username": "chuB"}
    ).inserted_id
    # Đơn của A nhưng lại gắn poi_id của B.
    sid = db["owner_submissions"].insert_one(
        {
            "username": "chuA",
            "poi_id": str(poi_b),
            "data": {"name": "Tên do A đặt", "description": "A sửa", "lat": 10.0, "lng": 106.0},
            "status": "pending",
            "created_at": None,
        }
    ).inserted_id
    mongo.close()

    with TestClient(app) as c:
        res = c.post(
            f"/owner/submissions/{sid}/approve",
            headers=bearer("admin", "super_admin", ["poi:approve"]),
        )
    assert res.status_code in (403, 409), res.status_code
    mongo = _ket_noi()
    poi = mongo[settings.mongodb_db_name]["pois"].find_one({"_id": poi_b})
    assert poi["name"] == "Quán của B", "nội dung của A ghi đè lên quán của B"
    assert poi.get("description") == "ngon"
    mongo.close()
    _ = ObjectId  # đánh dấu đã dùng


# --- 3: không phun nội bộ -------------------------------------------------


def test_loi_anh_khong_phun_duong_dan_noi_bo() -> None:
    """A03. Thông báo lỗi ảnh không được chứa đường dẫn trên đĩa."""
    mongo = _ket_noi()
    _don_sach(mongo)
    db = mongo[settings.mongodb_db_name]
    _tao_user(mongo, "sua", "super_admin", ["poi:update"])
    poi_id = db["pois"].insert_one({"name": "Có ảnh", "lat": 10.0, "lng": 106.0, "images": []}).inserted_id
    mongo.close()

    with TestClient(app) as c:
        res = c.post(
            f"/admin/pois/{poi_id}/images",
            headers=bearer("sua", "super_admin", ["poi:update"]),
            files={"file": ("../../../../etc/passwd.jpg", anh_nho(), "image/jpeg")},
        )
    assert res.status_code == 201, res.status_code
    # Rồi xoá bằng tên chứa traversal: phải 400/404, và thông báo không kèm đường dẫn.
    with TestClient(app) as c:
        xoa = c.delete(
            f"/admin/pois/{poi_id}/images/..%2F..%2Fetc%2Fpasswd",
            headers=bearer("sua", "super_admin", ["poi:update"]),
        )
    assert xoa.status_code in (400, 404), xoa.status_code
    assert "D:\\" not in xoa.text and "/static/images" not in xoa.text, xoa.text


def test_health_khong_phun_chuan_bi_ket_noi() -> None:
    """A03. `/health` không được kể lại host/port/DSN của Mongo."""
    with TestClient(app) as c:
        res = c.get("/health")
    noi_dung = res.text
    assert "mongodb://" not in noi_dung.lower()
    assert "27017" not in noi_dung


# --- 4: brute force đổi mật khẩu ------------------------------------------


def test_doi_mat_khau_sai_bi_dem_va_bi_chan() -> None:
    """A07. Đoán mật khẩu cũ nhiều lần phải bị chặn như đăng nhập."""
    mongo = _ket_noi()
    _don_sach(mongo)
    _tao_user(mongo, "nan_nhan", "super_admin", ["poi:update"])
    mongo.close()

    ma_sai = [f"sai{i:04d}" for i in range(6)]
    with TestClient(app) as c:
        assert c.post(
            "/admin/auth/login", json={"username": "nan_nhan", "password": "pw123456"}
        ).status_code == 200
        # Xoá bộ đếm do lần đăng nhập đúng tạo ra (đăng nhập đúng thì bộ đếm sạch).
        for mk in ma_sai:
            res = c.post(
                "/admin/auth/change-password",
                json={"mat_khau_cu": mk, "mat_khau_moi": "matkhaumoi123"},
            )
            if res.status_code == 429:
                break
        # Lượt thứ 6 trở đi phải bị chặn, kể cả khi mật khẩu ĐÚNG.
        chan = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": "pw123456", "mat_khau_moi": "matkhaumoi123"},
        )
    assert chan.status_code == 429, chan.status_code
    mongo = _ket_noi()
    doc = mongo[settings.mongodb_db_name]["admin_users"].find_one({"username": "nan_nhan"})
    # Băm bcrypt có salt ngẫu nhiên nên hai lần băm cùng một mật khẩu ra hai chuỗi
    # khác nhau — so sánh chuỗi là so sánh sai. Phải dùng `dung_mat_khau`.
    assert dung_mat_khau("pw123456", doc["password_hash"]), "bị đổi dù đã bị chặn"
    mongo.close()


# --- 5: cấu hình thiếu fail-fast ------------------------------------------


def test_ai_http_thieu_url_phai_loi_ro_rang() -> None:
    """A04. Provider thật mà thiếu URL thì báo lỗi cấu hình, không đi request rỗng."""
    from app.services import ai_svc

    truoc = settings.ai_provider, settings.ai_api_url
    try:
        settings.ai_provider = "http"
        settings.ai_api_url = ""
        provider = ai_svc.lay_provider()
        assert isinstance(provider, ai_svc.HttpProvider)
        try:
            import anyio

            anyio.run(provider.viet_lai, "mô tả thử")
            da_loi, thong_bao = False, ""
        except RuntimeError as exc:
            da_loi, thong_bao = True, str(exc)
        assert da_loi, "request với URL rỗng mà không báo lỗi"
        assert "ai_api_url" in thong_bao or "AI_API_URL" in thong_bao, thong_bao
    finally:
        settings.ai_provider, settings.ai_api_url = truoc
