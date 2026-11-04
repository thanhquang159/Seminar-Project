"""SEC-004 — CSRF: thao tác ghi từ trang khác.

Kịch bản tấn công không cần mật khẩu. Nạn nhân đã đăng nhập, phiên nằm trong
cookie httpOnly. Kẻ tấn công dựng trang ở miền của họ với đoạn này:

    fetch('http://127.0.0.1:8000/admin/pois', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Quán của tôi', lat: 1, lng: 1 })
    })

Nạn nhân chỉ cần mở trang đó. Đây là CSRF: yêu cầu đi **từ trình duyệt của
nạn nhân**, nên trình duyệt tự gắn cookie. CORS không cứu được: nó chỉ chặn
*đọc* phản hồi, còn lệnh ghi đã chạy xong rồi.

Hai lớp phòng thủ, test dưới đây kiểm cả hai:

1. `SameSite=lax` trên cookie — trình duyệt **không** gắn cookie khi trang gọi
   chéo miền bằng POST/fetch. Lớp này do trình duyệt thực thi, không kiểm tra
   được bằng `TestClient` — nên test chỉ chứng minh *cờ* được đặt đúng, còn
   "có thực sự chặn" thì phải thử bằng trình duyệt thật.
2. Chặn theo `Origin` ở server cho mọi thao tác ghi — lớp thứ hai, không phụ
   thuộc trình duyệt, và là lớp còn cần khi deploy thật: nếu sau này frontend và
   API cùng nằm trên một site (`app.amds.vn` + `api.amds.vn`) thì chúng khác
   *origin* nhưng **cùng site**, lúc đó SameSite vẫn gửi cookie.

Lưu ý về ranh giới: yêu cầu **không** kèm `Origin` thì cho qua (curl, script,
test). Không phải trình duyệt thì không dính CSRF; đổi lại phải có token hợp
lệ. Chặn cả những request đó sẽ làm hỏng mọi script gọi API mà không đổi gì
về an toàn.
"""

from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.auth import bam_mat_khau
from app.config import settings

settings.mongodb_db_name = "amds_test"

from app.main import app  # noqa: E402

XA = "https://evil.example"
HOP_LE = "http://localhost:5173"


def nap_admin() -> None:
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["admin_users"].delete_many({})
    db["admin_users"].insert_one(
        {"username": "admin", "password_hash": bam_mat_khau("admin123"), "role": "super_admin"}
    )
    db["pois"].delete_many({})
    mongo.close()


def dang_nhap(c: TestClient) -> None:
    assert c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200


def con_poi(ten: str) -> int:
    mongo = MongoClient(settings.mongodb_uri)
    n = mongo[settings.mongodb_db_name]["pois"].count_documents({"name": ten})
    mongo.close()
    return n


def tao(ten: str = "Quán của kẻ tấn công") -> dict:
    return {"name": ten, "description": "Chèn bởi trang khác", "lat": 10.75, "lng": 106.76}


# --- Lớp 1: cờ cookie -------------------------------------------------------


def test_cookie_phien_http_only_lax_va_host_only() -> None:
    """`HttpOnly` (JS không đọc được để chống XSS), `SameSite=lax` (trình duyệt
    không gửi khi chéo miền) và KHÔNG khai báo `Domain` — khai báo `Domain` thì
    mọi subdomain đều gửi kèm cookie, mở đường cho subdomain bị chiếm."""
    nap_admin()
    with TestClient(app) as c:
        res = c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"})
    cookie = res.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
    assert "Max-Age=" in cookie


def test_cookie_refresh_cung_co_cu_lax() -> None:
    """Access token hết hạn sớm thì FE gọi `/refresh` — cookie refresh là cửa
    để chiếm phiên nên phải có đủ cờ, không được lỏng hơn cookie access."""
    nap_admin()
    with TestClient(app) as c:
        c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"})
        res = c.post("/admin/auth/refresh")
    assert res.status_code == 200
    cookie = res.headers["set-cookie"]
    assert "HttpOnly" in cookie and "samesite=lax" in cookie.lower()


def test_cookie_co_secure_khi_khong_phai_dev(monkeypatch) -> None:
    """Ngoài dev, cookie phiên phải có `Secure` để không rơi qua http."""
    nap_admin()
    with TestClient(app) as c:  # mở trước: app_env=prod lúc khởi động sẽ fail-fast
        monkeypatch.setattr(settings, "app_env", "prod")
        res = c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"})
    assert "Secure" in res.headers["set-cookie"]


# --- Lớp 2: chặn thao tác ghi theo Origin ------------------------------------


def test_tao_poi_tu_trang_khac_bi_chan() -> None:
    """Đòn chính: trang của kẻ tấn công gửi POST kèm cookie của nạn nhân."""
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        r = c.post("/admin/pois", json=tao(), headers={"Origin": XA})
        assert r.status_code == 403
        # Quan trọng nhất: chặn trước khi ghi, không chỉ trả lỗi.
        assert con_poi("Quán của kẻ tấn công") == 0


def test_sua_va_xoa_poi_tu_trang_khac_cung_bi_chan() -> None:
    """Không chỉ POST: PUT và DELETE cũng là thao tác ghi."""
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        pid = c.post("/admin/pois", json=tao("Quán gốc")).json()["id"]
        sua = c.put(f"/admin/pois/{pid}", json={"name": "Bị sửa", "lat": 1, "lng": 1}, headers={"Origin": XA})
        assert sua.status_code == 403
        assert con_poi("Bị sửa") == 0
        xoa = c.delete(f"/admin/pois/{pid}", headers={"Origin": XA})
        assert xoa.status_code == 403
        assert con_poi("Quán gốc") == 1


def test_origin_null_bi_chan() -> None:
    """`Origin: null` xuất hiện khi trang nằm trong iframe sandbox hoặc mở bằng
    `file://` — không phải người dùng thật, nên cũng phải chặn."""
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        r = c.post("/admin/pois", json=tao(), headers={"Origin": "null"})
        assert r.status_code == 403
        assert con_poi("Quán của kẻ tấn công") == 0


def test_origin_hop_le_thi_ghi_duoc() -> None:
    """Chặn nhầm làm hỏng app: trang của chính hệ thống phải ghi được."""
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        r = c.post("/admin/pois", json=tao("Quán hợp lệ"), headers={"Origin": HOP_LE})
        assert r.status_code == 201
        assert con_poi("Quán hợp lệ") == 1


def test_khong_kem_origin_thi_van_chay() -> None:
    """curl/script/test không có `Origin` — không phải trình duyệt nên không
    dính CSRF, và phải còn token hợp lệ mới làm được việc."""
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        r = c.post("/admin/pois", json=tao("Quán từ script"))
        assert r.status_code == 201
        assert con_poi("Quán từ script") == 1


def test_yeu_cau_doc_khong_bi_chan() -> None:
    """GET không phải thao tác ghi. Origin lạ thì CORS lo (trình duyệt không đọc
    được phản hồi); server vẫn trả 200 — đúng ranh giới trách nhiệm."""
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        assert c.get("/admin/auth/me", headers={"Origin": XA}).status_code == 200


def test_thong_bao_chan_nói_ro_ly_do() -> None:
    """FE cần biết đây là chặn CORS/CSRF chứ không phải hết phiên, để không
    điền lại mật khẩu hoài."""
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        r = c.post("/admin/pois", json=tao(), headers={"Origin": XA})
        assert "rigin" in r.json()["detail"]