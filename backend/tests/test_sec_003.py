"""SEC-003 — CORS: chỉ origin đã khai báo mới đọc được phản hồi.

Kẻ tấn công không cần chạm vào máy nạn nhân. Họ mua một miền (`evil.example`),
dựng trang web gọi thẳng vào `http://127.0.0.1:8000` — đúng cổng API của hệ
thống đang chạy trên máy nạn nhân — rồi mở trang đó trên trình duyệt của nạn
nhân. Admin đã đăng nhập nên phiên nằm trong cookie httpOnly; trang của kẻ tấn
công gọi `fetch(..., {credentials: 'include'})`.

CORS là hàng rào chặn **đọc trộm**: nếu API trả
`Access-Control-Allow-Origin: https://evil.example` (hoặc `*`), trình duyệt
đưa phản hồi cho script của kẻ tấn công — cả danh sách POI lẫn số liệu phân
tích, và các lệnh ghi cũng chạy được.

Hai điều dễ nhầm, test dưới đây khóa lại bằng hành vi thật:
- Server **không** trả 403 cho origin lạ. Nó trả 200 và *không* kèm header
  cho phép; trình duyệt mới là bên chặn. Test phải kiểm header, không kiểm
  status.
- Request **không** kèm `Origin` (curl, test, server-to-server) vẫn chạy bình
  thường. CORS không phải hàng rào bảo mật, chỉ là quyền đọc phía trình duyệt.

Phần bị chặt lại trong task này: danh sách origin nằm trong biến môi trường
`CORS_ORIGINS` thay vì viết cứng, có chốt chặn cấu hình sai lúc khởi động, và
analytics dùng chung đúng danh sách đó.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, settings
from app.main import app

XA = "https://evil.example"
HOP_LE = "http://localhost:5173"


@pytest.fixture
def c():
    # `with` để chạy lifespan (connect_db) — `TestClient(app)` trần thì
    # `get_database()` ném "MongoDB client chưa khởi tạo".
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("gia_tri", ["*", "https://*.example", "http://a.test/*"])
def test_sao_hoa_bi_tu_choi(gia_tri: str) -> None:
    """'*' là lỗi cấu hình chứ không phải lựa chọn: API chạy cookie nên
    '*' vừa bị trình duyệt bỏ qua vừa là lỗ hổng đọc dữ liệu."""
    with pytest.raises(ValidationError):
        Settings(cors_origins=[gia_tri])


@pytest.mark.parametrize(
    "gia_tri",
    [
        "",
        "   ",
        "http://localhost:5173/",  # dấu / cuối: không bao giờ khớp Origin
        "http://localhost:5173/api",  # có đường dẫn: Origin không có phần này
        "ftp://x.test",  # sai scheme
        "localhost:5173",  # thiếu scheme
    ],
)
def test_origin_sai_dang_bi_tu_choi(gia_tri: str) -> None:
    """Origin sai dạng sẽ im lặng không khớp — lỗi khó chẩn đoán nhất."""
    with pytest.raises(ValidationError):
        Settings(cors_origins=[gia_tri])


@pytest.mark.parametrize(
    "gia_tri", ["http://localhost:5173", "http://127.0.0.1:4173", "https://amds.vn"]
)
def test_origin_hop_le_duoc_chap_nhan(gia_tri: str) -> None:
    assert Settings(cors_origins=[gia_tri]).cors_origins == [gia_tri]


def test_origin_la_khong_bi_trinh_duyet_cho_doc(c: TestClient) -> None:
    r = c.get("/health", headers={"Origin": XA})
    assert r.status_code == 200  # server vẫn phục vụ...
    assert "access-control-allow-origin" not in r.headers  # ...trình duyệt mới chặn


def test_origin_hop_le_duoc_trinh_duyet_cho_doc(c: TestClient) -> None:
    r = c.get("/health", headers={"Origin": HOP_LE})
    assert r.headers["access-control-allow-origin"] == HOP_LE
    assert r.headers["access-control-allow-credentials"] == "true"


def test_preflight_origin_la_bi_tu_choi(c: TestClient) -> None:
    """Trang kẻ tấn công dùng `Content-Type: application/json` thì bắt buộc có
    preflight; không qua được preflight thì không gửi được request thật."""
    r = c.options(
        "/admin/pois", headers={"Origin": XA, "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in r.headers


def test_preflight_hop_le_thong_bao_dung_method_va_header(c: TestClient) -> None:
    """Đúng preflight mà frontend gửi thật: JSON body ⇒ cần `content-type`."""
    r = c.options(
        "/admin/pois",
        headers={
            "Origin": HOP_LE,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.headers["access-control-allow-origin"] == HOP_LE
    assert "POST" in r.headers["access-control-allow-methods"]
    assert "content-type" in r.headers["access-control-allow-headers"].lower()


def test_preflight_chi_duoc_duoc_header_duoc_phep(c: TestClient) -> None:
    """Header lạ phải bị chặn. `allow_headers=["*"]` sẽ **đẩy lại nguyên danh
    sách header mà trình duyệt xin**, tức cho phép cả `X-Tu-Do` — không cần
    thiết khi API chỉ dùng `Content-Type`."""
    r = c.options(
        "/admin/pois",
        headers={
            "Origin": HOP_LE,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, x-tu-do",
        },
    )
    assert "x-tu-do" not in r.headers["access-control-allow-headers"].lower()


def test_preflight_hoi_method_la_bi_tu_choi(c: TestClient) -> None:
    """Origin hợp lệ cũng không được xin method ngoài danh sách."""
    r = c.options(
        "/admin/pois", headers={"Origin": HOP_LE, "Access-Control-Request-Method": "TRACE"}
    )
    assert r.status_code == 400


def test_khong_kem_origin_van_chay(c: TestClient) -> None:
    """curl, script, test — không có Origin thì không có kiểm tra CORS nào."""
    assert c.get("/health").status_code == 200


def test_mac_dinh_khong_co_sao() -> None:
    assert "*" not in settings.cors_origins
    assert not any("/" == o[-1] or "*" in o for o in settings.cors_origins)
    assert all(o.startswith("http://") for o in settings.cors_origins)


def test_analytics_dung_chung_danh_sach_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đổi `CORS_ORIGINS` thì analytics đi theo, không phải sửa hai chỗ.

    Trước đây có hai danh sách độc lập trong config: sửa một bên quên bên kia
    thì analytics hoặc CORS im lặng ngừng chạy.
    """
    from app.services.presence import origin_duoc_phep

    assert asyncio.run(origin_duoc_phep(HOP_LE)) is True
    monkeypatch.setattr(settings, "cors_origins", ["https://amds.vn"])
    assert asyncio.run(origin_duoc_phep(HOP_LE)) is False
    assert asyncio.run(origin_duoc_phep("https://amds.vn")) is True