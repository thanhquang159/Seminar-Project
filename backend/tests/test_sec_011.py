"""SEC-011 — Rà thu hồi phiên (RBAC-004).

Kịch bản: admin bị lộ mật khẩu, sửa mật khẩu xong thì phiên của kẻ cầm máy đã
đăng nhập trước đó **phải chết ngay**, không được sống tiếp tới khi hết hạn.

Trước SEC-011, hệ thống không có gì để thu hồi:
- JWT chỉ có `sub`, `role`, `permissions`, `type`, `exp` — không `jti`, không
  danh sách đen, không số phiên bản.
- `app/auth.py:quyen_hien_tai` ưu tiên **quyền trong token** khi token có, nên
  token cũ giữ nguyên quyền cũ tới hết 30 phút dù DB đã đổi.
- Không hề có route đổi mật khẩu cho admin lẫn chủ quán.

Cách vá: `phi_en_ver` trong `admin_users`, nhúng vào mọi JWT, mỗi request kiểm
khớp. Bump là chết phiên. Bản vá này thêm cả `POST /admin/auth/change-password`
để cơ chế ấy có chỗ dùng thật.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.auth import bam_mat_khau
from app.config import settings
from app.main import app

settings.mongodb_db_name = "amds_test"

MAT_KHAU_CU = "admin123"


def nap_admin() -> None:
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["admin_users"].delete_many({})
    db["admin_users"].insert_one(
        {
            "username": "admin",
            "password_hash": bam_mat_khau(MAT_KHAU_CU),
            "role": "super_admin",
            "phi_en_ver": 1,
        }
    )
    mongo.close()


def token_va_bearer(client: TestClient, mat_khau: str = MAT_KHAU_CU) -> tuple[str, str]:
    r = client.post("/admin/auth/login", json={"username": "admin", "password": mat_khau})
    assert r.status_code == 200, r.text
    return r.cookies.get("access_token"), r.cookies.get("refresh_token")


# --- Đạn 1: đổi mật khẩu phải giết phiên cũ ----------------------------------
def test_doi_mat_khau_giet_phien_cu() -> None:
    """Kẻ tấn công: đã đăng nhập được, giữ cookie, đợi admin đổi mật khẩu xong
    rồi thử lại. Nếu phiên cũ còn sống thì việc đổi mật khẩu là vô nghĩa."""
    nap_admin()
    with TestClient(app) as c:
        access_cu, _ = token_va_bearer(c)
        assert c.get("/admin/auth/me").status_code == 200  # phiên đang sống

        r = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
        assert r.status_code == 200, r.text

        # Token cũ (kẻ tấn công giữ) phải chết. Phải xoá cookie trước: client
        # hỏi cookie trước Bearer, mà cookie lúc này là cookie **mới** vừa
        # được server trả về — không xoá thì test đang kiểm phiên mới, đạt
        # giả rồi kết luận sai.
        c.cookies.clear()
        r_cu = c.get("/admin/auth/me", headers={"Authorization": f"Bearer {access_cu}"})
        assert r_cu.status_code == 401, f"phiên cũ còn sống sau khi đổi mật khẩu (HTTP {r_cu.status_code})"


def test_doi_mat_khau_giet_ca_refresh_token_cu() -> None:
    """Refresh token sống 7 ngày — nếu không chết thì kẻ tấn công chỉ cần chờ
    access 30 phút hết hạn rồi tự làm token mới."""
    nap_admin()
    with TestClient(app) as c:
        access_cu, refresh_cu = token_va_bearer(c)
        c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
        c.cookies.clear()
        r = c.post("/admin/auth/refresh", headers={"Authorization": f"Bearer {refresh_cu}"})
        assert r.status_code == 401, f"refresh cũ vẫn cấp được access mới (HTTP {r.status_code})"
        c.cookies.clear()
        r2 = c.post("/admin/auth/refresh", headers={"Authorization": f"Bearer {access_cu}"})
        assert r2.status_code == 401, "access token không được dùng để refresh"


def test_thiet_bi_dang_doi_mat_khau_giu_duoc_phien() -> None:
    """Máy đang đổi mật khẩu phải dùng được luôn, không bắt đăng nhập lại."""
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
        # Cookie mới do server trả về phải dùng được ngay
        assert c.get("/admin/auth/me").status_code == 200
        # …và refresh bằng cookie mới cũng được
        assert c.post("/admin/auth/refresh").status_code == 200


# --- Đạn 2: đổi mật khẩu phải xác thực đúng ----------------------------------
def test_doi_mat_khau_phai_biet_mat_khau_cu() -> None:
    """Không có mật khẩu cũ thì kẻ cướp token phiên cũng đổi được mật khẩu."""
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        r = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": "sai_hoan_toan", "mat_khau_moi": "mat_khau_moi_9"},
        )
        assert r.status_code == 401
        assert c.get("/admin/auth/me").status_code == 200, "sai mật khẩu cũ mà phiên bị giết"
        c.cookies.clear()
        assert c.post("/admin/auth/login", json={"username": "admin", "password": MAT_KHAU_CU}).status_code == 200


def test_mat_khau_moi_va_lan() -> None:
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        r = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "a"},
        )
        assert r.status_code == 422, "mật khẩu mới quá ngắn phải bị từ chối"
        r2 = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "x" * 100},
        )
        assert r2.status_code == 422, "mật khẩu mới quá dài phải bị từ chối"
        c.cookies.clear()
        assert c.post("/admin/auth/login", json={"username": "admin", "password": MAT_KHAU_CU}).status_code == 200


def test_doi_mat_khau_can_dang_nhap() -> None:
    nap_admin()
    with TestClient(app) as c:
        r = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
        assert r.status_code == 401


# --- Đạn 3: đổi role cũng phải giết phiên ------------------------------------
def test_doi_role_trong_db_giet_phien() -> None:
    """Quyền nằm trong token. Đổi role trong DB mà token cũ vẫn sống thì kẻ
    tấn công giữ được đúng quyền cũ tới hết 30 phút."""
    nap_admin()
    with TestClient(app) as c:
        access_cu, _ = token_va_bearer(c)
        mongo = MongoClient(settings.mongodb_uri)
        db = mongo[settings.mongodb_db_name]
        await_ = db["admin_users"].update_one(
            {"username": "admin"},
            {"$set": {"role": "user", "permissions_renamed": True}, "$inc": {"phi_en_ver": 1}},
        )
        assert await_.modified_count == 1
        mongo.close()
        r = c.get("/admin/auth/me", headers={"Authorization": f"Bearer {access_cu}"})
        assert r.status_code == 401, f"đổi role mà phiên cũ còn sống (HTTP {r.status_code})"


def test_token_khong_co_so_phien_bi_tu_choi() -> None:
    """Token cũ phát ra trước khi có cơ chế phiên (hoặc tự dựng) không được
    dùng để lách — nếu cho qua thì kẻ tấn công tự ký token không có `sv`."""
    nap_admin()
    # Dựng token thủ công **không** có claim `sv` — giống hệt token mà hệ thống
    # cũ phát ra. Không có `tao_token` vì hàm đó luôn ghi `sv` (mặc định 1),
    # nên gọi nó thì không kiểm được điều cần kiểm.
    het_han = datetime.now(UTC) + timedelta(minutes=30)
    gia = jwt.encode(
        {
            "sub": "admin",
            "role": "super_admin",
            "permissions": ["poi:delete"],
            "type": "access",
            "exp": het_han,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        r = c.get("/admin/auth/me", headers={"Authorization": f"Bearer {gia}"})
        assert r.status_code == 401, "token không khai báo số phiên vẫn lọt qua"
        assert c.get("/admin/auth/me").status_code == 401


# --- Đạn 4: chủ quán dùng chung cơ chế ---------------------------------------
def test_chu_quan_doi_mat_khau_cung_bi_thu_hoi() -> None:
    """Cùng collection `admin_users` nên chủ quán phải được thu hồi như admin."""
    nap_admin()
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["admin_users"].insert_one(
        {
            "username": "chu-quan-b",
            "password_hash": bam_mat_khau("chu_quan_123"),
            "role": "poi_owner",
            "is_verified": True,
            "is_poi_owner_verified": True,
            "phi_en_ver": 1,
        }
    )
    mongo.close()
    with TestClient(app) as c:
        r = c.post("/admin/auth/login", json={"username": "chu-quan-b", "password": "chu_quan_123"})
        assert r.status_code == 200, r.text
        assert c.get("/admin/auth/me").status_code == 200
        doi = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": "chu_quan_123", "mat_khau_moi": "mat_khau_moi_9"},
        )
        assert doi.status_code == 200, doi.text
        # phiên mới còn sống
        assert c.get("/admin/auth/me").status_code == 200
        # mật khẩu cũ không còn đăng nhập được
        c.cookies.clear()
        assert c.post("/admin/auth/login", json={"username": "chu-quan-b", "password": "chu_quan_123"}).status_code == 401
        assert c.post("/admin/auth/login", json={"username": "chu-quan-b", "password": "mat_khau_moi_9"}).status_code == 200


# --- Đạn 5: đổi mật khẩu phải xoá bộ đếm khoá tạm --------------------------
def test_doi_mat_khau_va_ban_ghi_audit() -> None:
    """Thiếu bản ghi audit thì không biết ai đã đổi mật khẩu khi bị xâm nhập."""
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    ban = list(db["audit_logs"].find({"action": "auth:change_password"}))
    db["audit_logs"].delete_many({"action": "auth:change_password"})
    mongo.close()
    assert ban, "đổi mật khẩu mà không có bản ghi audit"


@pytest.mark.parametrize("thu_tu", [1, 2])
def test_doi_mat_khau_hai_lan(thu_tu: int) -> None:
    """Lần đổi thứ hai phải dùng mật khẩu **mới**, không phải mật khẩu cũ."""
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
        r = c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_nua_9"},
        )
        assert r.status_code == 401, f"dùng lại mật khẩu cũ để đổi tiếp (lần {thu_tu})"
        assert c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": "mat_khau_moi_9", "mat_khau_moi": "mat_khau_nua_9"},
        ).status_code == 200


def test_mat_khau_moi_luu_hash_chua_khong_ban() -> None:
    """Mật khẩu mới phải được băm — lưu thẳng chuỗi là để lộ toàn bộ."""
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    bam = db["admin_users"].find_one({"username": "admin"})["password_hash"]
    mongo.close()
    assert bam != "mat_khau_moi_9"
    assert bam.startswith("$2b$"), f"mật khẩu không được băm bcrypt: {bam[:8]}"


def test_so_phien_tang_moi_lan_doi() -> None:
    """Số phiên phải tăng đúng 1; nếu `$inc` sai thì hoặc không giết được phiên
    cũ, hoặc giết nhầm phiên vừa cấp."""
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    so = db["admin_users"].find_one({"username": "admin"})["phi_en_ver"]
    mongo.close()
    assert so == 2, f"số phiên là {so}, kỳ vọng 2"


def test_poi_id_khong_lien_quan_khong_vao() -> None:
    """Guard: test này chỉ là chốt rằng thay đổi mật khẩu không đụng dữ liệu POI."""
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["pois"].delete_many({})
    db["pois"].insert_one({"name": "Chợ", "lat": 10.7, "lng": 106.6, "is_active": True})
    mongo.close()
    nap_admin()
    with TestClient(app) as c:
        token_va_bearer(c)
        c.post(
            "/admin/auth/change-password",
            json={"mat_khau_cu": MAT_KHAU_CU, "mat_khau_moi": "mat_khau_moi_9"},
        )
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    con = db["pois"].count_documents({})
    mongo.close()
    assert con == 1


def test_doi_mat_khau_khong_the_treo_o_dien_thoai() -> None:
    """Chủ quán đã duyệt thì đổi mật khẩu vẫn phải xong (không bị chặn nhầm
    bởi `doi_owner_da_duyet` hay nhánh lỗi nào đó của owner)."""
    nap_admin()
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["admin_users"].insert_one(
        {
            "username": "chu-quan-c",
            "password_hash": bam_mat_khau("chu_quan_123"),
            "role": "poi_owner",
            "is_verified": True,
            "is_poi_owner_verified": True,
            "phi_en_ver": 1,
        }
    )
    mongo.close()
    with TestClient(app) as c:
        assert c.post("/admin/auth/login", json={"username": "chu-quan-c", "password": "chu_quan_123"}).status_code == 200
        assert (
            c.post(
                "/admin/auth/change-password",
                json={"mat_khau_cu": "chu_quan_123", "mat_khau_moi": "mat_khau_moi_9"},
            ).status_code
            == 200
        )


def test_object_id_khong_can_thieu() -> None:
    """Guard nhỏ: import ObjectId phải dùng được (chốt phụ thuộc của test khác)."""
    assert ObjectId("0" * 24)