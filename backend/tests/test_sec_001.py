"""SEC-001 — Rà soát validate đầu vào mọi endpoint.

Mỗi test là một **đòn tấn công thật** vào endpoint thật, không phải kiểm tra
lại code đã ràng buộc. Ghi rõ "kẻ tấn công làm gì" rồi "đã chặn ở đâu" để sau
này ai cũng kiểm chứng lại được bằng `pytest tests/test_sec_001.py`.

Nguyên tắc: input không tin được. Mọi ký tự đều do client gửi, kể cả trong
query string — không có ngoại lệ cho "chỉ là endpoint nội bộ".
"""

from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import settings

settings.mongodb_db_name = "amds_test"

from app.main import app  # noqa: E402

MB = 1024 * 1024


def nap_admin() -> None:
    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["admin_users"].delete_many({})
    db["rate_limits"].delete_many({})
    from app.auth import bam_mat_khau

    db["admin_users"].insert_one(
        {"username": "admin", "password_hash": bam_mat_khau("admin123"), "role": "super_admin"}
    )
    mongo.close()


def dang_nhap(c: TestClient) -> None:
    r = c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"đăng nhập thất bại: {r.status_code} {r.text}"


# --- Đạn 1: TTS không giới hạn độ dài text ---------------------------------
# Kẻ tấn công: user đã đăng nhập gửi text 1 MB vào /audio/tts. Mỗi text khác
# nhau sinh một file MP3 mới trong static/audio/ và không bao giờ bị dọn, nên
# đủ vài trăm request là đầy đĩa server.
def test_tts_cho_phep_text_khong_gioi_han() -> None:
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        r = c.post("/audio/tts", json={"text": "A" * MB, "lang": "vi"})
        # 413 (middleware chặn trước) hoặc 422 (Pydantic chặn sau) đều đúng:
        # điều cần chứng minh là text không bao giờ tới được edge-tts.
        assert r.status_code in (413, 422), (
            f"text 1 MB vẫn qua được (HTTP {r.status_code}) — server phải đầy đĩa"
        )


# --- Đạn 2: lang không ràng buộc --------------------------------------------
# Kẻ tấn công: lang đi thẳng vào GoogleTranslator và tên cache. Chuỗi rác ở
# đây không chỉ hỏng tính năng mà còn làm loãng dữ liệu ngôn ngữ trong DB.
def test_tts_chan_lang_sai_dinh_dang() -> None:
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        for lang_bad in ["../../etc/passwd", "v" * 200, "vi; DROP TABLE"]:
            r = c.post("/audio/tts", json={"text": "Xin chào", "lang": lang_bad})
            assert r.status_code == 422, f"lang={lang_bad!r} lọt qua (HTTP {r.status_code})"


# --- Đạn 3: body khổng lồ ---------------------------------------------------
# Kẻ tấn công: không cần đăng nhập, POST thẳng 200 KB vào endpoint công khai.
# Chặn ở middleware trước khi Pydantic kịp phân tích.
def test_body_khong_content_length_bi_chan() -> None:
    with TestClient(app) as c:
        # Mọi trường đều hợp lệ riêng lẻ — payload phình lên nhờ độ dài giá trị,
        # đây mới đúng là loại tấn công mà middleware 64 KiB chặn được.
        r = c.post(
            "/analytics/collect",
            json={
                "anonymous_id": "a" * 64,
                "receipt": "b" * 200,
                "session_id": "c" * 64,
                "events": [{"name": "x", "properties": {"mo_ta": "y" * 2000}} for _ in range(40)],
            },
        )
        assert r.status_code == 413, f"body 100 KB lọt qua (HTTP {r.status_code})"


# --- Đạn 4: chunked transfer không khai báo Content-Length --------------------
# Kẻ tấn công: gửi body kiểu chunked để né kiểm tra Content-Length, đòi
# server đếm tay trong lúc đọc.
def test_body_chunked_bi_dem_tay() -> None:
    with TestClient(app) as c:
        # generator -> httpx dùng Transfer-Encoding: chunked, không có Content-Length
        r = c.post("/analytics/collect", content=(b"x" * 8192 for _ in range(32)))
        assert r.status_code == 413, f"body chunked lọt qua (HTTP {r.status_code})"


# --- Đạn 5: bcrypt chỉ đọc 72 byte ------------------------------------------
# Kẻ tấn công / lỗi logic: bcrypt bỏ qua phần byte thứ 73 trở đi. Cho phép
# mật khẩu dài hơn 72 byte nghĩa là "mật khẩu 73 ký tự" và "mật khẩu 73 ký tự
# + 28 ký tự bất kỳ" là hai chuỗi khác nhau nhưng cùng đăng nhập được.
def test_mat_khau_tren_72_byte_bi_chan() -> None:
    nap_admin()
    with TestClient(app) as c:
        r = c.post("/admin/auth/login", json={"username": "admin", "password": "a" * 73})
        assert r.status_code == 422, f"mật khẩu 73 byte lọt qua (HTTP {r.status_code})"
        # Ký tự đa byte: 30 ký tự tiếng Việt = 60+ byte, 100 ký tự là > 72 byte.
        r = c.post("/admin/auth/login", json={"username": "admin", "password": "ẩ" * 100})
        assert r.status_code == 422, "mật khẩu nhiều byte lọt qua"
        # Còn mật khẩu hợp lệ vẫn phải vào được.
        assert c.post("/admin/auth/login", json={"username": "admin", "password": "a" * 72}).status_code == 401


# --- Đạn 6: username không giới hạn -----------------------------------------
def test_ten_dang_nhap_khong_gioi_han() -> None:
    with TestClient(app) as c:
        r = c.post("/admin/auth/login", json={"username": "a" * 5000, "password": "x"})
        assert r.status_code == 422, f"username 5000 ký tự lọt qua (HTTP {r.status_code})"


# --- Đạn 7: ghi chú duyệt không giới hạn -------------------------------------
# Kẻ tấn công: ghi chú 10 MB vào tài liệu POI của chủ quán, làm phình DB và
# làm hỏng mọi màn hình đọc lại POI đó.
def test_admin_note_khong_gioi_han() -> None:
    nap_admin()
    with TestClient(app) as c:
        dang_nhap(c)
        r = c.post("/owner/registrations/nguoi_dua/reject", json={"admin_note": "b" * 10000})
        assert r.status_code == 422, f"ghi chú 10000 ký tự lọt qua (HTTP {r.status_code})"


# --- Đạn 8: properties analytics không giới hạn ------------------------------
def test_thuoc_tinh_analytics_khong_gioi_han() -> None:
    with TestClient(app) as c:
        r = c.post(
            "/analytics/collect",
            json={
                "anonymous_id": "anon" + "0" * 20,
                "receipt": "receipt-" + "0" * 20,
                "session_id": "session-" + "0" * 20,
                "events": [
                    {"name": "x", "properties": {f"k{i}": i for i in range(200)}},
                ],
            },
        )
        assert r.status_code == 422, f"200 thuộc tính/sự kiện lọt qua (HTTP {r.status_code})"


# --- Đạn 9: locale của UI bundle --------------------------------------------
# Kẻ tấn công: GET một locale bất kỳ là server tự bắt đầu dịch nền cả bộ
# UI bằng Google Translate. Không cần đăng nhập, không cần rate limit.
def test_locale_rac_bi_chan() -> None:
    with TestClient(app) as c:
        r = c.get("/ui-bundles/" + "a" * 300)
        assert r.status_code == 422, f"locale rác lọt qua (HTTP {r.status_code})"


# --- Đạn 10: endpoint bundle UI không được ghi DB ----------------------------
# Kẻ tấn công: một request duy nhất tới /ui-bundles/xx từng kích hoạt dịch nền
# cả bộ UI bằng Google Translate, và còn upsert một bản ghi vào `ui_bundles`.
# SEC-010 đã gỡ deep-translator (PYSEC-2022-252) nên nhánh dịch nền biến mất;
# endpoint phải thành thao tác đọc thuần, locale lạ trả 404.
def test_bundle_ui_khong_ghi_db() -> None:
    mongo = MongoClient(settings.mongodb_uri)
    mongo[settings.mongodb_db_name]["ui_bundles"].delete_many({})
    mongo.close()
    with TestClient(app) as c:
        r = c.get("/ui-bundles/xx")
        assert r.status_code == 404, f"locale lạ phải bị từ chối (HTTP {r.status_code})"
        r2 = c.get("/ui-bundles/ja")
        assert r2.status_code == 200
    mongo = MongoClient(settings.mongodb_uri)
    dem = mongo[settings.mongodb_db_name]["ui_bundles"].count_documents({})
    mongo.close()
    assert dem == 0, f"endpoint vẫn ghi vào ui_bundles ({dem} bản ghi)"


# --- Đạn 11: query param không ràng buộc -------------------------------------
def test_query_param_rac_bi_chan() -> None:
    with TestClient(app) as c:
        assert c.get("/poi", params={"lang": "<script>alert(1)</script>"}).status_code == 422
        assert c.get("/poi/delta", params={"updated_after": -5}).status_code == 422
        assert c.get("/maps/audio-pack", params={"lang": "../../etc"}).status_code == 422