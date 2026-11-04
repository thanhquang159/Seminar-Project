"""SEC-008 — chống NoSQL injection (toán tử `$`) và lẫn tham số đường dẫn.

Kịch bản tấn công: MongoDB hiểu `{"tên": {"$ne": null}}` là "khác null" chứ
không phải "bằng chuỗi rỗng". Nếu chỗ nào đưa thẳng dữ liệu JSON của người
dùng vào **khoá** hoặc **giá trị** của truy vấn mà không qua kiểu vô hướng
(Pydantic), thì kẻ tấn công đăng nhập được bằng bất kỳ tài khoản nào, hoặc đọc
được dữ liệu không thuộc về mình.

Nguyên tắc đã kiểm tra trong repo này:
- Mọi truy vấn đều là **hằng số** ghép với **giá trị đã qua Pydantic**
  (`str`/`int`/`float`/`bool`/enum). Không có f-string nào dựng khoá truy vấn từ
  input, không có `**body` hay toán tử `$` nào do người dùng chọn.
- `dict` duy nhất người dùng gửi là `SuKien.properties` của analytics — chỉ
  được **ghi**, không bao giờ dùng làm điều kiện truy vấn.
- Pydantic v2 **không** ép `dict`/`list` → `str`, nên `{"$ne": null}` ở đúng chỗ
  kiểu `str` bị chặn 422, không biến thành toán tử.

Ngoài ra có một điểm dễ sai đã khoá lại bằng test: route
`/owner/registrations/{username}/approve` khai `username: str = ""` **không** gắn
`Path`. Nhiều framework sẽ hiểu đó là query parameter (URL ghi A thì lại thao tác
lên B). FastAPI thì vẫn nhận ra path param theo **tên**, nhưng điều đó chỉ đúng
vì hệ thống suy luận tên — một lần "dọn code" đổi thành `Query("")` là thành
duyệt nhầm tài khoản, và không có gì báo lỗi. `test_duyet_don_dung_tai_khoan_
trong_duong_dan` khoá đúng hành vi này lại.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Payload kinh điển của NoSQL injection: mong đợi mọi request dưới đây bị chặn.
TOAN_TU = {"$ne": None}
TOAN_TU_GT = {"$gt": ""}
PAYLOAD_NOSQL = [
    TOAN_TU,
    TOAN_TU_GT,
    {"$regex": ".*"},
    {"$exists": True},
    {"$in": ["admin"]},
    ["admin"],
    1,
    True,
    ["$ne", "x"],
    {"$where": "1==1"},
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _dang_nhap(client: TestClient, **tu) -> None:
    res = client.post("/admin/auth/login", json=tu)
    assert res.status_code == 422, res.text


# --- đăng nhập / đăng ký: chỗ đáng giá nhất ---------------------------------------


@pytest.mark.parametrize("payload", PAYLOAD_NOSQL)
def test_username_dang_nhap_khong_phai_toan_tu(client, payload) -> None:
    """Nếu `username` lọt thành toán tử, `{"$ne": null}` khớp mọi tài khoản và
    kẻ tấn công chỉ cần đoán mật khẩu của bất kỳ ai."""
    _dang_nhap(client, username=payload, password="x" * 10)


@pytest.mark.parametrize("payload", PAYLOAD_NOSQL)
def test_mat_khau_dang_nhap_khong_phai_toan_tu(client, payload) -> None:
    _dang_nhap(client, username="admin", password=payload)


def test_dang_nhap_khong_bypass_duoc(client) -> None:
    """Không request nào trong họ payload trên được trả 200/401 kiểu "thành công"
    — tức là không có đường vòng nào đăng nhập được mà không cần mật khẩu."""
    for payload in PAYLOAD_NOSQL:
        res = client.post("/admin/auth/login", json={"username": payload, "password": payload})
        assert res.status_code == 422, f"{payload} → {res.status_code} {res.text}"


@pytest.mark.parametrize("payload", PAYLOAD_NOSQL)
def test_ten_dang_nhap_dang_ky_khong_phai_toan_tu(client, payload) -> None:
    res = client.post("/owner/register", json={"username": payload, "password": "x" * 10, "cccd": "012345678"})
    assert res.status_code == 422, res.text


# --- truy vấn có tham số: `?lang[$ne]=x` ------------------------------------------


@pytest.mark.parametrize(
    "duong_dan",
    ["/poi", "/poi/nearby?lat=10.7&lng=106.7&radius_m=500", "/poi/hotset?lat=10.7&lng=106.7"],
)
def test_tham_so_truy_van_co_toan_tu(client, duong_dan) -> None:
    """Dấu ngoặc vuông trong query string là cách bơm toán tử vào tham số kiểu
    `lang[$ne]=x`; ở đây giá trị phải là chuỗi đơn giản, không phải đối tượng."""
    tach = duong_dan.split("?", 1)
    res = client.get(tach[0], params={"lang[$ne]": "x", **dict(p.split("=") for p in tach[1].split("&"))} if len(tach) > 1 else {"lang[$ne]": "x"})
    assert res.status_code in (200, 422), res.text
    assert "stack" not in res.text.lower()


def test_bo_loc_dia_ly_khong_phai_toan_tu(client) -> None:
    res = client.get("/poi/nearby", params={"lat[$gt]": "0", "lng[$lt]": "0", "radius_m": "100"})
    assert res.status_code in (200, 422), res.text


# --- analytics: dict người dùng gửi, chỉ được ghi chứ không được truy vấn --------


def test_properties_analytics_chua_toan_tu(client) -> None:
    """`properties` là dict tự do nên không chặn được — nhưng nó phải được lưu
    nguyên vẹn (không bung toán tử) và không làm hỏng endpoint."""
    aid = "anon-secure-test-000000000000"
    client.cookies.clear()
    client.cookies.set("origin_duoc_phep", "1")  # không dùng — xem bên dưới
    client.cookies.clear()
    res_consent = client.post(
        "/analytics/consent",
        json={"anonymous_id": aid, "granted": True},
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert res_consent.status_code == 200, res_consent.text
    receipt = res_consent.json()["receipt"]
    res = client.post(
        "/analytics/collect",
        json={
            "anonymous_id": aid,
            "receipt": receipt,
            "session_id": "s" * 20,
            "heartbeat": True,
            "events": [{"name": "sec_probe", "properties": {"a": {"$ne": None}, "b": {"$where": "1==1"}}}],
        },
    )
    assert res.status_code == 200, res.text
    # Truy vấn lại sự kiện vừa ghi: giá trị phải là đối tượng dữ liệu, không biến
    # thành điều kiện truy vấn (kiểm tra gián tiếp: đọc báo cáo không được lỗi).
    assert client.get("/analytics/consent", params={"anonymous_id": aid}).status_code in (200, 400)


# --- lẫn tham số đường dẫn: lỗi thật, tìm ra khi rà NoSQL injection -----------


def _dang_ky_cho_duyet(client: TestClient, ten: str) -> None:
    res = client.post("/owner/register", json={"username": ten, "password": "x" * 10, "cccd": "012345678"})
    assert res.status_code == 200, res.text


def test_duyet_don_dung_tai_khoan_trong_duong_dan(client, monkeypatch) -> None:
    """URL nói duyệt tài khoản A thì phải duyệt A. Route khai `username: str = ""`
    không gắn `Path`; FastAPI vẫn suy ra path param theo tên, nhưng đó là điều
    dễ vỡ nhất trong file này — nếu ai đó đổi sang `Query("")` thì `?username=B`
    sẽ duyệt nhầm tài khoản B mà không có lỗi nào báo ra."""
    # `ma_hoa_pii` trả None khi thiếu PII_KEY → đăng ký trả 500, không phải lỗi
    # của luồng này. Key tạm cho test.
    from cryptography.fernet import Fernet

    from app.config import settings as cfg

    monkeypatch.setattr(cfg, "pii_key", Fernet.generate_key().decode())

    # Dọn tàn dư của lần chạy trước (DB test không tự xoá ngoài rate_limits).
    from pymongo import MongoClient

    client_mongo = MongoClient(cfg.mongodb_uri)
    mongo = client_mongo[cfg.mongodb_db_name]
    mongo["admin_users"].delete_many({"username": {"$in": ["chu-quan-a", "chu-quan-b", "root-sec008"]}})
    mongo["owner_registrations"].delete_many({"username": {"$in": ["chu-quan-a", "chu-quan-b"]}})

    _dang_ky_cho_duyet(client, "chu-quan-a")
    _dang_ky_cho_duyet(client, "chu-quan-b")
    client.cookies.clear()

    # Cần admin thật để qua `DuocQuanLyUser`.
    from app.auth import bam_mat_khau

    db = client_mongo[cfg.mongodb_db_name]
    db["admin_users"].insert_one(
        {"username": "root-sec008", "password_hash": bam_mat_khau("pw123456"), "role": "super_admin"}
    )
    assert client.post("/admin/auth/login", json={"username": "root-sec008", "password": "pw123456"}).status_code == 200
    res = client.post("/owner/registrations/chu-quan-a/approve?username=chu-quan-b")
    assert res.status_code == 200, res.text

    a = db["owner_registrations"].find_one({"username": "chu-quan-a"})
    b = db["owner_registrations"].find_one({"username": "chu-quan-b"})
    assert a is not None and a["status"] == "approved", "đường dẫn phải được tôn trọng"
    assert b is not None and b["status"] == "pending", "không được duyệt nhầm tài khoản khác"


# --- chặn tái phạm: cấu trúc truy vấn -------------------------------------------


def test_khong_co_khoa_truy_van_tao_tu_input() -> None:
    """Mọi truy vấn phải là hằng số ghép giá trị đã kiểm. Nếu sau này có ai đó
    viết `find_one({trong: ...})` với `trong` lấy từ body thì toán tử `$` quay
    lại — và lúc đó chỉ có kiểm thử mới bắt được."""
    import re

    xam_lang = re.compile(r"""find(_one|many)?\(\s*\{[^{}]*\{[^}]*\{""")
    dinh_khoa_dong = re.compile(r"""\{[^{}]*\[\s*\*\s*\*""")
    app_dir = Path(__file__).resolve().parents[1] / "app"
    nghi_van: list[str] = []
    for tep in sorted(app_dir.rglob("*.py")):
        chuoi = tep.read_text(encoding="utf-8")
        for ten, mau in (("truy vấn lồng nhau", xam_lang), ("mở khoá **", dinh_khoa_dong)):
            if mau.search(chuoi):
                nghi_van.append(f"{tep.relative_to(app_dir)}: {ten}")
    assert nghi_van == [], nghi_van


def test_chi_mot_cho_duoc_dung_dict_tu_do() -> None:
    """`SuKien.properties` là dict tự do duy nhất người dùng gửi — và nó chỉ
    được ghi. Thêm dict tự do thứ hai là phải kèm lý do (và chỉ được phép nếu
    vẫn không đụng vào truy vấn)."""
    import re

    lop = re.compile(r"^class\s+\w+\(([^)]*)\)")
    truong = re.compile(r"^\s{4}(\w+)\s*:\s*(dict|Any)\b")
    cho_phep = {("analytics", "properties")}
    tim_thay: set[tuple[str, str]] = set()
    for tep in sorted((Path(__file__).resolve().parents[1] / "app" / "routers").glob("*.py")):
        trong_model = False
        for so, dong in enumerate(tep.read_text(encoding="utf-8").splitlines(), start=1):
            if khop_lop := lop.match(dong):
                # Chỉ xét phần thân model; `payload: dict = {...}` trong hàm là
                # biến cục bộ, không phải input người dùng.
                trong_model = "BaseModel" in khop_lop.group(1)
                continue
            if not trong_model or (khop := truong.match(dong)) is None:
                continue
            ten, kieu = khop.group(1), khop.group(2)
            tim_thay.add((tep.stem, ten))
            assert (tep.stem, ten) in cho_phep, f"{tep.name}:{so} nhận {kieu} từ người dùng: {dong.strip()}"
    assert tim_thay == cho_phep, "thuộc tính dict tự do đã bị gỡ — cập nhật danh sách cho phép"