"""SEC-002: chặn đoán mật khẩu ở `POST /admin/auth/login`.

**Threat — kẻ tấn công làm gì.** `POST /admin/auth/login` xác thực bằng mật
khẩu bcrypt, mà trước SEC-002 route này **không có bất kỳ hạn chế nào**: kẻ tấn
công cứ gửi `{"username": "admin", "password": "..."}` liên tục, thử hết bộ
mật khẩu phổ biến, rồi dò tài khoản (`admin`, `mod`, `quan_tri`…) cho tới khi
đoán ra. Ba hệ quả cụ thể:

1. **Bộ đoán không bị chậm lại.** bcrypt chậm (~100 ms/lần) nên kẻ tấn công
   bị giới hạn bởi chính server, nhưng họ chỉ cần chạy nhiều tiến trình song
   song — vô hạn lượt đoán.
2. **Quét tài khoản miễn phí.** Tên sai và mật khẩu sai trả cùng thông báo nên
   không dò được từ nội dung lỗi, nhưng *thời gian* vẫn lộ (xem `test_thoi_gian_...`).
3. **Khoá tài khoản không tồn tại.** Không có khoá tạm ⇒ đoán không bao giờ bị
   ngắt giữa chừng, một IP/người dùng sai là cứ thử tiếp.

**Cách phòng (đã triển khai trong `app/services/login_guard.py`).** Hai bộ đếm
trượt trong cùng collection `rate_limits` (TTL sẵn có, không thêm schema):

| khoá        | ngưỡng            | cửa sổ  | chặn cái gì                                  |
|-------------|-------------------|---------|-----------------------------------------------|
| `ten:<user>`| 5 lần sai         | 15 phút | đoán trúng một tài khoản nào đó              |
| `ip:<ip>`   | 20 lần sai        | 15 phút | quét nhiều tài khoản, và nhiều IP để một IP |

Chỉ **lần sai** mới được tính; đăng nhập đúng thì xoá sạch bộ đếm (không phải
trả 429 cho người dùng thật chỉ vì trước đó đánh nhầm). Kiểm tra chạy **trước**
khi băm bcrypt nên tài nguyên không bị đốt vô ích, và thông báo khi khoá không
chứa tên đăng nhập nên không dò được tài khoản nào đang bị khoá.

**Cách thử tấn công thật (Verify).** Các test dưới đây tự đóng vai kẻ tấn
công: quét tài khoản, quét tên người dùng không tồn tại, đoán liên tục, và kiểm
tra rằng sau khi đúng mật khẩu thì bộ đếm được xoá.
"""

import bcrypt
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import settings

settings.mongodb_db_name = "amds_test"

from app.main import app  # noqa: E402

SAI = {"username": "admin", "password": "sai-sai-sai"}
DUNG = {"username": "admin", "password": "admin123"}


@pytest.fixture
def c():
    # Phải `with` để chạy lifespan (connect_db) — `TestClient(app)` trần thì
    # `get_database()` ném "MongoDB client chưa khởi tạo".
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def db_sach() -> None:
    """Mỗi test bắt đầu với DB sạch: chỉ có đúng một tài khoản admin."""
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["rate_limits"].delete_many({})
    db["admin_users"].delete_many({})
    db["admin_users"].insert_one(
        {
            "username": "admin",
            "password_hash": bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode(),
            "role": "super_admin",
        }
    )
    mongo.close()


def thu(c: TestClient, n: int, body: dict | None = None) -> list[int]:
    """Gửi n lần đăng nhập sai, trả về danh sách mã trảng thái."""
    return [c.post("/admin/auth/login", json=body or SAI).status_code for _ in range(n)]


# ── khoá theo tài khoản ────────────────────────────────────────────────────


def test_mot_ty_sai_van_binh_thuong(c: TestClient) -> None:
    """Vài lần đánh nhầm phải không bị phạt — nếu không thì admin thật bị chặn."""
    assert thu(c, 4) == [401, 401, 401, 401]


def test_lan_thu_sau_bi_khoa_tam(c: TestClient) -> None:
    """Đạt ngưỡng 5 lần sai thì lượt kế tiếp bị khoá, kể cả khi mật khẩu ĐÚNG."""
    assert thu(c, 5) == [401] * 5
    r = c.post("/admin/auth/login", json=DUNG)
    assert r.status_code == 429
    # Retry-After để client biết chờ bao lâu, không đoán mò.
    assert int(r.headers["Retry-After"]) > 0


def test_thong_bao_khoa_khong_lo_tai_khoan(c: TestClient) -> None:
    """Kẻ dò tài khoản không được biết tên nào đang bị khoá."""
    thu(c, 5)
    r = c.post("/admin/auth/login", json=DUNG)
    assert "admin" not in r.text.lower()


def test_ten_khong_ton_tai_cung_bi_khoa(c: TestClient) -> None:
    """Tên bịa ra phải bị khoá y hệt, nếu không thì kẻ tấn công chỉ cần quét
    tên thật là né được mọi hạn chế."""
    assert thu(c, 5, {"username": "khong_ton_tai", "password": "x"}) == [401] * 5
    assert c.post("/admin/auth/login", json={"username": "khong_ton_tai", "password": "x"}).status_code == 429


def test_dang_nhap_dung_thi_xoa_bo_dem(c: TestClient) -> None:
    """Đăng nhập đúng phải xoá lịch sử sai, không thì admin thật bị khoá oan."""
    assert thu(c, 4) == [401] * 4
    assert c.post("/admin/auth/login", json=DUNG).status_code == 200
    # Bộ đếm bắt đầu lại từ 0: 4 lần sai nữa vẫn chưa tới ngưỡng.
    assert thu(c, 4) == [401] * 4
    assert c.post("/admin/auth/login", json=DUNG).status_code == 200


# ── khoá theo IP ──────────────────────────────────────────────────────────


def test_quet_nhieu_tai_khoan_bi_khoa_theo_IP(c: TestClient) -> None:
    """Mỗi tên mới 4 lần sai (chưa tới ngưỡng tài khoản) — nhưng tổng từ một
    IP vẫn bị chặn. Nếu chỉ khoá theo tài khoản thì kẻ tấn công đổi tên là né."""
    for i in range(4):
        assert thu(c, 5, {"username": f"dung-{i}", "password": "x"}) == [401] * 5
    r = c.post("/admin/auth/login", json={"username": "dung-moi", "password": "x"})
    assert r.status_code == 429


# ── bền vững ──────────────────────────────────────────────────────────────


def test_quet_mat_khau_khong_gay_loi_500(c: TestClient) -> None:
    """Gõ 30 lần sai liên tục: hệ thống phải trả lỗi có kiểm soát, không sập."""
    trang_thai = thu(c, 30)
    assert set(trang_thai) <= {401, 429}
    assert 500 not in trang_thai


def test_khoa_tam_het_han_thi_vao_lai_duoc(c: TestClient) -> None:
    """Khoá là TẠM thời: hết cửa sổ thì vào lại được, không khoá vĩnh viễn."""
    from app.services import login_guard

    thu(c, 5)
    assert c.post("/admin/auth/login", json=DUNG).status_code == 429
    # Lùi mọi lần gõ sai ra ngoài cửa sổ 15 phút (cả bộ đếm tài khoản lẫn IP).
    # Lùi về QUÁ KHỨ chứ không phải về tương lai: cửa sổ trượt lọc `luc >= moc`,
    # nên muốn trượt khỏi cửa sổ thì mốc thời gian phải cũ hơn `now - 15p`.
    MongoClient(settings.mongodb_uri)[settings.mongodb_db_name]["rate_limits"].update_many(
        {"duong_dan": login_guard.DUONG_DAN},
        [
            {
                "$set": {
                    "luc": login_guard.moc_cu_thoi_diem(login_guard.CUA_SO_PHUT + 1),
                    "het_han": login_guard.moc_cu_thoi_diem(login_guard.CUA_SO_PHUT + 1),
                }
            }
        ],
    )
    assert c.post("/admin/auth/login", json=DUNG).status_code == 200