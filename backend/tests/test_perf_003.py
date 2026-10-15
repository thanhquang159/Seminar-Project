"""PERF-003: nén gzip cho JSON — số đo, quy tắc loại trừ, không phá ETag.

**Số đo baseline (DB dev, 53 POI):**

    load-all (vi)          21 371 byte thô -> gzip(6)  1 474 byte  (-93%)
    load-all + ETag cũ                  0 byte (304)
    delta không đổi                    63 byte  (dưới ngưỡng nén 500)
    delta toàn bộ             21 395 byte  (to hơn load-all!)

**Quyết định theo số đo:**

- **Nén**: 21 KB -> 1,5 KB là đòi hỏi thật → bật `GZipMiddleware`.
- **Delta vs ETag**: "không đổi" thì ETag 304 = 0 byte thắng delta = 63 byte;
  delta chỉ thắng khi ít thay đổi (63 byte so với 21 KB gửi lại đủ). Cả hai
  endpoint đã có sẵn từ trước — không làm thêm cơ chế gì mới.
- **Không đổi thứ tự middleware**: kiểm `add_middleware` là `insert(0)`
  (thêm sau = lớp ngoài) và 403 CSRF không có ACAO là đúng ý đồ với origin
  lạ — ghi chú lại luôn ở `main.py` vì hai comment cũ mô tả ngược nhau.

**Loại trừ của Starlette** (`DEFAULT_EXCLUDED_CONTENT_TYPES`): `audio/*`,
`image/*`, `text/event-stream`, font — MP3 không bị nén thêm (đã nén sẵn,
tốn CPU oan), SSE không bị bóp; body < 500 byte không đụng tới.
"""

from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import settings

settings.mongodb_db_name = "amds_test"

from app.auth import bam_mat_khau  # noqa: E402
from app.main import app  # noqa: E402


def _c() -> TestClient:
    # `with` để chạy lifespan (connect_db) — TestClient trần thì
    # `get_database()` ném "MongoDB client chưa khởi tạo".
    return TestClient(app)


def test_json_bi_nen_khi_client_chap_nhan_gzip() -> None:
    """`Accept-Encoding: gzip` → body nén, header đúng, nội dung giữ nguyên."""
    # DB test có thể trống (load-all 39 byte < 500 → GZip bỏ qua đúng luật),
    # nên tự seed POI cho payload vượt ngưỡng rồi dọn lại.
    with MongoClient(settings.mongodb_uri) as cli:
        coll = cli[settings.mongodb_db_name]["pois"]
        coll.delete_many({"name": {"$regex": r"^\[perf003\]"}})
        coll.insert_many(
            {
                "name": f"[perf003] Quan an {i}",
                "description": "Mo ta day du ky tu de vuot nguong nen 500 byte " * 3,
                "lat": 10.76 + i * 0.001,
                "lng": 106.76 + i * 0.001,
                "trigger_radius": 30,
                "audio_priority": i,
                "is_active": True,
                "version": 1,
            }
            for i in range(3)
        )
    try:
        with _c() as c:
            nen = c.get("/poi/load-all", headers={"Accept-Encoding": "gzip"})
            khong = c.get("/poi/load-all", headers={"Accept-Encoding": "identity"})
        assert nen.status_code == 200
        assert len(khong.content) > 500, "payload phải vượt ngưỡng nén"
        assert nen.headers.get("content-encoding") == "gzip"
        assert "accept-encoding" in nen.headers.get("vary", "").lower()
        # httpx đã giải nén sẵn cho `.content` — nội dung phải giống hệt bản chưa nén.
        assert nen.content == khong.content
        assert nen.json()["pois"] == khong.json()["pois"]
    finally:
        with MongoClient(settings.mongodb_uri) as cli:
            cli[settings.mongodb_db_name]["pois"].delete_many(
                {"name": {"$regex": r"^\[perf003\]"}}
            )


def test_khong_nen_khi_client_khong_chap_nhan() -> None:
    """Client không gửi `Accept-Encoding: gzip` thì nhận nguyên bản."""
    with _c() as c:
        r = c.get("/poi/load-all", headers={"Accept-Encoding": "identity"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") is None


def test_etag_304_van_dung_duoi_lop_nen() -> None:
    """GZip không được phá luồng ETag: 304 không body, còn nguyên ETag."""
    with _c() as c:
        lan_dau = c.get("/poi/load-all", headers={"Accept-Encoding": "gzip"})
        etag = lan_dau.headers.get("ETag")
        assert etag
        lan_hai = c.get(
            "/poi/load-all", headers={"Accept-Encoding": "gzip", "If-None-Match": etag}
        )
    assert lan_hai.status_code == 304
    assert len(lan_hai.content) == 0
    assert lan_hai.headers.get("ETag") == etag


def test_delta_nho_khong_bi_nen() -> None:
    """Payload dưới 500 byte (delta rỗng ~63 byte) giữ nguyên — nén chỉ tốn."""
    with _c() as c:
        phien_ban = c.get("/poi/load-all").json()["version"]
        r = c.get(f"/poi/delta?updated_after={phien_ban}", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert len(r.content) < 500
    assert r.headers.get("content-encoding") is None  # dưới minimum_size


def test_mp3_khong_bi_nen() -> None:
    """`audio/*` bị loại trừ: MP3 đã nén sẵn, nén thêm chỉ tốn CPU."""
    # Tự seed admin (DB test sống dai giữa các lần chạy nhưng không đảm bảo
    # có sẵn khi chạy riêng file này).
    with MongoClient(settings.mongodb_uri) as cli:
        cli[settings.mongodb_db_name]["admin_users"].update_one(
            {"username": "admin"},
            {"$set": {"password_hash": bam_mat_khau("admin123"), "role": "super_admin"}},
            upsert=True,
        )
    with _c() as c:
        assert (
            c.post(
                "/admin/auth/login", json={"username": "admin", "password": "admin123"}
            ).status_code
            == 200
        )
        r = c.post("/audio/tts", json={"text": "Bánh mì chảo Quận 4", "lang": "vi"})
    assert r.status_code == 200, r.text
    assert "audio/mpeg" in r.headers["content-type"]
    assert r.headers.get("content-encoding") is None  # Starlette tự loại audio/*
