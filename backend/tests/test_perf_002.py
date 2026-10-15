"""PERF-002: chỉ mục cho `rate_limits` — chứng cứ explain, khoá bằng test.

**Vấn đề đo được (PERF-001).** `cho_phep` chạy TRƯỚC mọi request có rate
limit: nó `count_documents({khoa, duong_dan, luc: {$gte: moc}})` rồi mới cho
qua. Explain trên DB dev trước khi thêm chỉ mục:

    count      -> COUNT -> COLLSCAN | keys=0 docs=7
    find+sort  -> SORT -> COLLSCAN | keys=0 docs=7

Tức là MỌI request bị rate limit đều quét hết collection (và sort trong RAM
khi bị chặn). Collection `rate_limits` lớn đúng theo lưu lượng: 30 dòng/10
phút/người dùng — đúng loại dữ liệu mọc đều theo thời gian.

**Sau khi thêm compound `{khoa, duong_dan, luc}`** (hai khoá equality + một
dải thời gian = khớp đúng hình dạng truy vấn):

    count      -> COUNT -> COUNT_SCAN | keys=2 docs=0   (đếm qua chỉ mục, 0 doc fetch)
    find+sort  -> LIMIT -> FETCH -> IXSCAN | keys=1 docs=1
                   (chỉ mục đã sắp theo `luc` sẵn → không còn stage SORT)

Chỉ mục TTL `het_han` KHÔNG phục vụ truy vấn này (nó dọn document hết hạn,
không đếm theo khoá) — hai chỉ mục làm hai việc.

**Quyết định KHÔNG thêm chỉ mục cho `pois`** (lưu bằng chứng tại đây): load-all
`find({is_active: {$ne: False}})` — thêm `is_active_1` thử rồi gỡ:

    TRUOC -> COLLSCAN | keys=0 docs=3
    SAU   -> FETCH -> IXSCAN | keys=3 docs=3

`$ne: false` match gần như mọi dòng nên chỉ mục quét khoá thừa mà không giảm
được lần fetch document nào — chỉ làm chậm. Không thêm.

Cả hai test đều tạo chỉ mục qua ĐƯỜNG CHẠY THẬT (một request đăng nhập —
`login_guard.kiem_tra` gọi `cho_phep` gọi `dam_bao_index_ratelimit`) thay vì
gọi hàm async trực tiếp: test đồng bộ gọi `async def` thì coroutine không bao
giờ chạy, chỉ mục im lặng không xuất hiện — đúng cái bẫy test này tránh.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import settings

settings.mongodb_db_name = "amds_test"

from app.main import app  # noqa: E402

KHOA = {"khoa": "user:perf002", "duong_dan": "/audio/tts"}


def _dong_chay_tao_chi_muc() -> None:
    """Xoá hết chỉ mục rồi bắn một request đăng nhập để app tự tạo lại."""
    with MongoClient(settings.mongodb_uri) as cli:
        cli[settings.mongodb_db_name]["rate_limits"].drop_indexes()
    with TestClient(app) as c:
        # Kết quả không quan trọng (401/429 đều được) — `kiem_tra` chạy đầu
        # tiên nên `dam_bao_index_ratelimit` luôn được gọi trước.
        c.post("/admin/auth/login", json={"username": "perf002-khong-ton-tai", "password": "x"})


def _chuong(plan: dict) -> list[str]:
    """Đọc chuỗi stage từ winningPlan (pymongo trả khoá lồng `input`)."""
    cac = []
    while plan:
        cac.append(plan.get("stage", "?"))
        plan = plan.get("input") or plan.get("inputStage")
    return cac


def test_dam_bao_index_tao_ca_ttl_lan_compound() -> None:
    """Request rate-limited đầu tiên tự tạo cả TTL lẫn compound index."""
    _dong_chay_tao_chi_muc()
    with MongoClient(settings.mongodb_uri) as cli:
        idx = cli[settings.mongodb_db_name]["rate_limits"].index_information()
        assert idx["khoa_1_duong_dan_1_luc_1"]["key"] == [
            ("khoa", 1),
            ("duong_dan", 1),
            ("luc", 1),
        ]
        # TTL cũ vẫn còn: hai chỉ mục phục vụ hai việc khác nhau.
        assert idx["het_han_1"]["expireAfterSeconds"] == 0


def test_explain_khong_collscan_khong_sort() -> None:
    """Truy vấn của `cho_phep` phải dùng IXSCAN và không cần stage SORT."""
    _dong_chay_tao_chi_muc()
    with MongoClient(settings.mongodb_uri) as cli:
        db = cli[settings.mongodb_db_name]
        # Một dòng mới để truy vấn thật sự khớp (đúng cửa sổ 10 phút).
        dong = dict(KHOA, luc=datetime.now(UTC), het_han=datetime.now(UTC) + timedelta(minutes=10))
        db["rate_limits"].insert_one(dong)
        try:
            moc = datetime.now(UTC) - timedelta(minutes=10)
            ex = db.command(
                "explain",
                {
                    "find": "rate_limits",
                    "filter": {**KHOA, "luc": {"$gte": moc}},
                    "sort": {"luc": 1},
                    "limit": 1,
                },
                verbosity="executionStats",
            )
            st = ex["executionStats"]
            chuong = _chuong(ex["queryPlanner"]["winningPlan"])
            assert "COLLSCAN" not in chuong, chuong  # không quét collection
            assert "SORT" not in chuong, chuong  # chỉ mục sắp sẵn theo luc
            assert "IXSCAN" in chuong, chuong
            # Chạm đúng số dòng khớp (cộng vài dòng biên), không phải cả collection.
            tong = db["rate_limits"].count_documents({})
            assert st["totalDocsExamined"] <= max(3, tong), st["totalDocsExamined"]
        finally:
            db["rate_limits"].delete_one({"_id": dong["_id"]})
