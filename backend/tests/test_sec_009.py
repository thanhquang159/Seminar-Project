"""SEC-009 — header bảo mật (PROD-007).

Mỗi test ở đây chỉ ra một thứ trình duyệt sẽ tự làm nếu mình không bảo app
không làm: đoán kiểu nội dung, nhúng trang vào iframe, gửi URL của app sang
chỗ khác, tải mã về từ nơi lạ.

Có một chi tiết dễ chết âm thầm: CSP phải vừa chặt vừa không làm sập bản đồ.
MapLibre cần worker (blob:), React cần style inline, tile đến từ
`*.maptiler.com`. Nếu thiếu một trong ba thì app vẫn chạy ở bản demo miễn phí
và chỉ hỏng khi người dùng thêm key — nên test phải kiểm đúng danh sách đó.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _header(client: TestClient, ten: str, duong_dan: str = "/health") -> str | None:
    # health không cần tham số động nên phản ánh đúng response thật.
    return client.get(duong_dan).headers.get(ten)


def test_nosniff_chong_trinh_duyet_doan_loi(client: TestClient) -> None:
    """Không có nosniff, `GET /maps/…` trả JSON nhưng tải xuống rồi mở bằng
    trình duyệt có thể bị hiểu là HTML rồi chạy script."""
    assert _header(client, "x-content-type-options") == "nosniff"


def test_khong_cho_nhung_iframe(client: TestClient) -> None:
    """Overlay trong suốt phủ nút "duyệt đơn chủ quán" là kiểu clickjacking
    kinh điển khi app dùng cookie đăng nhập."""
    assert _header(client, "x-frame-options") == "DENY"


def test_referrer_chi_le_chinh_site(client: TestClient) -> None:
    """URL có `?poi_id=…`, `?anonymous_id=…` — không nên chảy sang site khác
    khi người dùng bấm liên kết ra ngoài."""
    assert _header(client, "referrer-policy") == "strict-origin-when-cross-origin"


def test_dung_quyen_dia_ly_micro(client: TestClient) -> None:
    """App cần `geolocation` để chấm điểm tham quan gần người dùng; không cần
    `microphone` — chặn luôn để iframe/nhúng không hứa thu được."""
    assert _header(client, "permissions-policy") == "geolocation=(self), microphone=()"


def _csp(client: TestClient) -> dict[str, str]:
    hieu = _header(client, "content-security-policy")
    assert hieu is not None, "thiếu CSP"
    return dict(mo_chi.split(None, 1) for mo_chi in hieu.split(";"))


def test_csp_chan_ma_tu_noi_la(client: TestClient) -> None:
    """`script-src 'self'`: không có `unsafe-inline`, không `*`. Đây là biện
    pháp bổ sung cho SEC-007 — nếu sau này có chỗ lỡ tay đưa HTML thô vào DOM
    thì CSP là chốt chặn cuối."""
    csp = _csp(client)
    assert csp["script-src"] == "'self'"
    assert csp["default-src"] == "'self'"
    assert "unsafe-eval" not in csp["script-src"]


def test_csp_cam_plugin_object_va_base_lai(client: TestClient) -> None:
    csp = _csp(client)
    assert csp["object-src"] == "'none'"  # không nhúng <object>/<embed>
    assert csp["base-uri"] == "'self'"  # chặn <base href> đổi gốc mọi đường dẫn
    assert csp["frame-ancestors"] == "'none'"  # trùng lớp phòng thủ với X-Frame-Options
    assert csp["form-action"] == "'self'"  # form không đẩy dữ liệu sang domain khác


def test_csp_khong_lam_sap_ban_do(client: TestClient) -> None:
    """Ba thứ app thật sự cần. Thiếu bất kỳ thứ nào thì bản demo vẫn chạy,
    chỉ hỏng khi có MapTiler key — nên phải kiểm đúng ba dòng này."""
    csp = _csp(client)
    # MapLibre nạp tile qua Web Worker tạo từ Blob.
    assert "blob:" in csp["worker-src"]
    # React đặt style cục bộ cho vòng tròn geofence, thanh tiến trình.
    assert csp["style-src"] == "'self' 'unsafe-inline'"
    # Tile và ảnh đến từ MapTiler.
    assert "https://*.maptiler.com" in csp["img-src"]
    # API của chính app + style bản đồ.
    assert "http://127.0.0.1:8000" in csp["connect-src"]
    assert "https://demotiles.maplibre.org" in csp["connect-src"]


def test_hsts_khong_bat_o_dev(client: TestClient) -> None:
    """Bật HSTS ở `http://127.0.0.1` thì trình duyệt ghim localhost sang HTTPS
    vĩnh viễn, và mọi lần chạy thử sau đó đều hỏng — không thể gỡ bằng cách
    xoá cấu hình."""
    assert _header(client, "strict-transport-security") is None


def test_hsts_bat_khi_co_proxy_https(client: TestClient) -> None:
    """Sau nài đặt sau nginx có TLS thì phải có, kể cả lúc cấu hình vẫn là dev."""
    r = client.get("/health", headers={"x-forwarded-proto": "https"})
    assert r.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_hsts_bat_khi_len_thuc_de(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Không qua proxy mà chạy thẳng HTTPS thì cũng phải bật — quyết định dựa
    trên môi trường chứ không dựa trên header mà chỉ reverse proxy mới thêm."""
    monkeypatch.setattr(settings, "app_env", "prod")
    try:
        r = client.get("/health")
    finally:
        monkeypatch.setattr(settings, "app_env", "dev")
    assert r.headers["strict-transport-security"].startswith("max-age=")


def test_header_co_tren_loi_413_va_403(client: TestClient) -> None:
    """Header phải do middleware gắn, không phải do từng handler ghi tay — nếu
    không thì lỗi 413/403 là loại response duy nhất không có header, tức là loại
    trình duyệt hay gặp nhất khi có việc bằng hơn."""
    qua_lon = client.post(
        "/analytics/collect",
        json={
            "anonymous_id": "a" * 64,
            "receipt": "b" * 200,
            "session_id": "c" * 64,
            "events": [{"name": "x", "properties": {"mo_ta": "y" * 2000}} for _ in range(40)],
        },
    )
    assert qua_lon.status_code == 413
    assert qua_lon.headers.get("x-content-type-options") == "nosniff"

    tu_origin_la = client.post(
        "/poi/warmup",
        json={"anonymous_id": "a" * 64},
        headers={"Origin": "https://evil.example"},
    )
    assert tu_origin_la.status_code == 403
    assert tu_origin_la.headers.get("x-content-type-options") == "nosniff"