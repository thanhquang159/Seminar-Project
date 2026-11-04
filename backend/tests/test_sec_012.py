"""SEC-012 — Rà tải lên ảnh POI.

Nguồn yêu cầu: `system-presentation-standalone.html` mô tả rõ hai hằng số
`MAX_POI_IMAGES = 8` và `MAX_IMAGE_SIZE = 5 MB` (module `content/service.py`),
offline pack gồm "map + POI + images + audio", và plan Quận 4 dòng 66 ghi
kho tệp tĩnh "(MP3, ảnh, PMTiles)". Nhưng trong code hiện tại **không có
route nào nhận ảnh** — `PoiNhap` chỉ có name/description/lat/lng/
trigger_radius/audio_priority, `static/` chỉ có audio/maps/ui.

Nên task này gồm hai phần: (1) dựng tính năng upload ảnh, (2) rà nó.

Đòn tấn công mỗi test tương ứng:
- tệp .exe/.php/.html đổi tên .jpg  → nếu chỉ tin đuôi file thì web shell lên
  /static và CSP `script-src 'self'` không cứu được (file do chính site phục vụ)
- ảnh thật 5.1 MB                 → chặn đĩa
- 9 ảnh                           → chặn bảo mồi
- tên lạ / đường dẫn              → chặn path traversal ghi ra ngoài thư mục
- thiếu quyền                     → chặn ghi trộm
- ảnh không đọc được               → phải là ảnh thật (magic bytes), không phải
  file rỗng mang đuôi .png
"""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pymongo import MongoClient

from app.auth import bam_mat_khau, tao_token
from app.config import settings
from app.main import app

settings.mongodb_db_name = "amds_test"

THU_MUC_ANH = Path(__file__).resolve().parents[1] / "static" / "images"
MAT_KHAU_ADMIN = "admin123"


def anh_jpeg(canh=8) -> bytes:
    """Ảnh JPEG thật. Cạnh lớn dùng pixel ngẫu nhiên — ảnh phẳng nén cực mạnh
    nên 1500×1500 chỉ còn vài chục KB, không chạm được trần 5 MB."""
    import random

    buf = io.BytesIO()
    if canh <= 64:
        hinh = Image.new("RGB", (canh, canh), (200, 30, 30))
    else:
        rnd = random.Random(7)
        hinh = Image.frombytes(
            "RGB", (canh, canh), bytes(rnd.randrange(256) for _ in range(canh * canh * 3))
        )
    hinh.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def anh_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 200, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def nap_admin(db) -> None:
    db["admin_users"].delete_many({})
    db["admin_users"].insert_one(
        {
            "username": "admin",
            "password_hash": bam_mat_khau(MAT_KHAU_ADMIN),
            "role": "super_admin",
            "phi_en_ver": 1,
        }
    )


def tao_poi(db) -> str:
    db["pois"].delete_many({})
    r = db["pois"].insert_one(
        {
            "name": "Chợ Bến Thành",
            "description": "mô tả",
            "lat": 10.78,
            "lng": 106.7,
            "trigger_radius": 30,
            "audio_priority": 0,
            "images": [],
        }
    )
    return str(r.inserted_id)


def bearer(role: str = "super_admin", quyen=None) -> dict:
    tok = tao_token("admin", role, "access", quyen or ["poi:create", "poi:update", "poi:delete"])
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def moi():
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    nap_admin(db)
    poi_id = tao_poi(db)
    yield db, poi_id
    for anh in THU_MUC_ANH.glob("*"):
        if anh.is_dir():
            for f in anh.iterdir():
                f.unlink()
            anh.rmdir()
    db["pois"].delete_many({})
    db["admin_users"].delete_many({})
    mongo.close()


def tai(client, poi_id, ten, du_lieu: bytes, ct="image/jpeg", **kw):
    return client.post(
        f"/admin/pois/{poi_id}/images",
        files={"file": (ten, du_lieu, ct)},
        headers=kw.pop("headers", bearer()),
        **kw,
    )


# --- Chức năng cơ bản -------------------------------------------------------
def test_tai_anh_jpeg_thanh_cong(moi) -> None:
    db, poi_id = moi
    with TestClient(app) as c:
        r = tai(c, poi_id, "mat_cho.jpg", anh_jpeg())
        assert r.status_code == 201, r.text
        duong_dan = r.json()["images"][0]
        assert duong_dan.startswith("/static/images/")
        assert (THU_MUC_ANH / poi_id / duong_dan.rsplit("/", 1)[-1]).exists()


def test_tai_anh_png_thanh_cong(moi) -> None:
    db, poi_id = moi
    with TestClient(app) as c:
        r = tai(c, poi_id, "a.png", anh_png(), ct="image/png")
        assert r.status_code == 201, r.text
        assert r.json()["images"][0].endswith(".png")


def test_poi_co_anh_thi_hien_cho_khách(moi) -> None:
    """Ảnh tải lên mà khách không thấy thì tính năng vô dụng."""
    db, poi_id = moi
    with TestClient(app) as c:
        tai(c, poi_id, "a.jpg", anh_jpeg())
        r = c.get(f"/poi/{poi_id}")
        assert r.status_code == 200, r.text
        assert r.json()["images"], "POI công khai không trả ảnh đã tải lên"


# --- Đạn 1: đuôi file giả --------------------------------------------------
def test_trai_phan_tich_vao_anh_bi_tu_choi(moi) -> None:
    """Kẻ tấn công: đặt tên `shell.jpg` nhưng nội dung là script/HTML.
    Nếu server phục vụ `/static` thì file này chạy dưới domain của chính site."""
    db, poi_id = moi
    with TestClient(app) as c:
        r = tai(c, poi_id, "shell.jpg", b"<?php system($_GET[0]); ?>", ct="image/jpeg")
        assert r.status_code in (400, 415), f"script đổi đuôi .jpg lọt qua (HTTP {r.status_code})"
        assert c.get(f"/admin/pois/{poi_id}/images", headers=bearer()).status_code in (200, 404)


def test_magic_bytes_dung_chinh_chuan_html_bi_tu_choi(moi) -> None:
    """File bắt đầu bằng `<!DOCTYPE html>` hoặc `<svg onload=…>` là HTML/JS,
    không phải ảnh — đây là dạng XSS tự chạy khi người dùng mở ảnh."""
    db, poi_id = moi
    with TestClient(app) as c:
        r = tai(c, poi_id, "xss.jpg", b"<!DOCTYPE html><script>alert(1)</script>", ct="image/jpeg")
        assert r.status_code in (400, 415), f"HTML đổi đuôi .jpg lọt qua (HTTP {r.status_code})"
        r2 = tai(c, poi_id, "xss2.png", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>", ct="image/png")
        assert r2.status_code in (400, 415), f"SVG gắn script đổi đuôi .png lọt qua (HTTP {r2.status_code})"


def test_file_rong_mang_duoi_anh_bi_tu_choi(moi) -> None:
    db, poi_id = moi
    with TestClient(app) as c:
        r = tai(c, poi_id, "rong.jpg", b"", ct="image/jpeg")
        assert r.status_code in (400, 415), "file rộng 0 byte được nhận là ảnh"


def test_duoi_khong_duoc_phep_bi_tu_choi(moi) -> None:
    db, poi_id = moi
    with TestClient(app) as c:
        for ten in ["a.exe", "a.php", "a.html", "a.svg", "a.webp2", "a"]:
            r = tai(c, poi_id, ten, anh_jpeg(), ct="image/jpeg")
            assert r.status_code in (400, 415), f"{ten} được nhận (HTTP {r.status_code})"


# --- Đạn 2: kích thước -----------------------------------------------------
def test_anh_qua_5mb_bi_tu_choi(moi) -> None:
    """Kẻ tấn công đẩy 200 tệp 5 MB để làm đầy đĩa máy chủ."""
    db, poi_id = moi
    with TestClient(app) as c:
        lon = b"\xff\xd8\xff\xe0" + b"\x00" * (5 * 1024 * 1024 + 1024)
        r = tai(c, poi_id, "lon.jpg", lon, ct="image/jpeg")
        assert r.status_code == 413, f"ảnh >5 MB lọt qua (HTTP {r.status_code})"


def test_anh_lon_hop_le_khong_bi_chan_oi(moi) -> None:
    """Ảnh thật ~4.5 MB phải lọt — chứng minh đây không phải chặn sớm cho chắc:
    cùng kích thước đó nhưng nội dung không phải ảnh thì vẫn bị loại."""
    db, poi_id = moi
    du_lieu = anh_jpeg(canh=1900)
    assert 4 * 1024 * 1024 < len(du_lieu) < 5 * 1024 * 1024, f"anh mau {len(du_lieu)} byte"
    with TestClient(app) as c:
        r = tai(c, poi_id, "lon_that.jpg", du_lieu)
        assert r.status_code == 201, f"anh {len(du_lieu)} byte bi tu choi (HTTP {r.status_code}: {r.text})"


# --- Đạn 3: số lượng -------------------------------------------------------
def test_toi_da_8_anh_bi_tu_choi(moi) -> None:
    db, poi_id = moi
    with TestClient(app) as c:
        for i in range(8):
            r = tai(c, poi_id, f"a{i}.jpg", anh_jpeg())
            assert r.status_code == 201, f"ảnh {i} bị từ chối sớm: {r.status_code} {r.text}"
        assert len(c.get(f"/admin/pois/{poi_id}/images", headers=bearer()).json()["images"]) == 8
        r9 = tai(c, poi_id, "a8.jpg", anh_jpeg())
        assert r9.status_code in (400, 409), f"ảnh thứ 9 lọt qua (HTTP {r9.status_code})"


# --- Đạn 4: path traversal --------------------------------------------------
def test_ten_tuyen_du_cho_pha_thu_muc(moi) -> None:
    """Tên file do người dùng kiểm soát — phải sinh tên ngẫu nhiên, không ghép
    thẳng vào đường dẫn, nếu không `../../` ghi đè được file ngoài thư mục."""
    db, poi_id = moi
    with TestClient(app) as c:
        r = tai(c, poi_id, "../../../../evil.jpg", anh_jpeg())
        if r.status_code == 201:
            ngoai = (THU_MUC_ANH / poi_id).parent.parent / "evil.jpg"
            assert not ngoai.exists(), "ghi được file ra ngoài thư mục ảnh"
            assert ".." not in r.json()["images"][0], f"URL chứa '..': {r.json()['images'][0]}"
        else:
            assert r.status_code in (400, 415)
        r2 = tai(c, poi_id, "a/b.jpg", anh_jpeg())
        assert r2.status_code in (400, 415, 201)
        if r2.status_code == 201:
            assert "a/" not in r2.json()["images"][0]


def test_ten_tuyen_du_unicode_va_ky_tu_la(moi) -> None:
    """Tên rác không được làm sập server (exception 500)."""
    db, poi_id = moi
    with TestClient(app) as c:
        for ten in ["a b.jpg", "ảnh đẹp.jpg", "a%20b.jpg", "a\x00b.jpg", "CON.jpg", "x" * 300 + ".jpg"]:
            r = tai(c, poi_id, ten, anh_jpeg())
            assert r.status_code < 500, f"{ten!r} làm server lỗi 500"


# --- Đạn 5: quyền ----------------------------------------------------------
def test_tai_anh_can_quyen(moi) -> None:
    db, poi_id = moi
    with TestClient(app) as c:
        assert tai(c, poi_id, "a.jpg", anh_jpeg(), headers={}).status_code == 401
        r = tai(c, poi_id, "a.jpg", anh_jpeg(), headers=bearer("super_admin", ["poi:read"]))
        assert r.status_code == 403, f"không có quyền mà vẫn tải được (HTTP {r.status_code})"


def test_origin_lai_bi_chan(moi) -> None:
    """Kiểm tra CSRF của SEC-004 phải áp cả cho upload — nếu không, trang lạ
    gửi form multipart tới endpoint này bằng cookie của người đã đăng nhập."""
    db, poi_id = moi
    with TestClient(app) as c:
        hd = {**bearer(), "Origin": "https://evil.example"}
        r = tai(c, poi_id, "a.jpg", anh_jpeg(), headers=hd)
        assert r.status_code == 403, f"origin lạ vẫn tải được ảnh (HTTP {r.status_code})"


# --- Đạn 6: dọn dẹp -------------------------------------------------------
def test_xoa_anh_xoa_hoi_ca_file_tren_dia(moi) -> None:
    db, poi_id = moi
    with TestClient(app) as c:
        r = tai(c, poi_id, "a.jpg", anh_jpeg())
        ten = r.json()["images"][0].rsplit("/", 1)[-1]
        assert (THU_MUC_ANH / poi_id / ten).exists()
        x = c.delete(f"/admin/pois/{poi_id}/images/{ten}", headers=bearer())
        assert x.status_code == 200, x.text
        assert not (THU_MUC_ANH / poi_id / ten).exists(), "xoá trong DB nhưng file còn trên đĩa"
        assert c.get(f"/admin/pois/{poi_id}/images", headers=bearer()).json()["images"] == []


def test_xoa_anh_path_traversal_khong_duoc_xoa_file_ngoai(moi) -> None:
    db, poi_id = moi
    ngoai = THU_MUC_ANH.parent / "khong_duoc_xoa.jpg"
    ngoai.parent.mkdir(parents=True, exist_ok=True)
    ngoai.write_bytes(anh_jpeg())
    try:
        with TestClient(app) as c:
            r = c.delete(f"/admin/pois/{poi_id}/images/..%2F..%2Fkhong_duoc_xoa.jpg", headers=bearer())
            assert r.status_code in (400, 404), f"traversal qua đường dẫn xoá file ngoài (HTTP {r.status_code})"
            assert ngoai.exists(), "file ngoài thư mục bị xoá"
    finally:
        ngoai.unlink(missing_ok=True)


def test_tai_anh_vao_poi_khong_ton_tai_bi_404(moi) -> None:
    db, _ = moi
    with TestClient(app) as c:
        r = tai(c, "0" * 24, "a.jpg", anh_jpeg())
        assert r.status_code == 404
        r2 = tai(c, "khong-phai-objectid", "a.jpg", anh_jpeg())
        assert r2.status_code in (400, 404), f"id rác trả {r2.status_code}"


def test_so_anh_trong_db_khong_bao_loi(moi) -> None:
    """Không được để lọt số ảnh vượt trần do dữ liệu cũ — đếm lại mỗi lần tải."""
    db, poi_id = moi
    db["pois"].update_one({"_id": __import__("bson").ObjectId(poi_id)}, {"$set": {"images": ["a"] * 30}})
    with TestClient(app) as c:
        r = tai(c, poi_id, "a.jpg", anh_jpeg())
        assert r.status_code in (400, 409), f"dữ liệu sẵn 30 ảnh mà vẫn nhận thêm (HTTP {r.status_code})"