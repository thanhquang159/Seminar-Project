"""SEC-010 — Quét phụ thuộc, gỡ deep-translator.

Kể lại: `pip-audit` báo `deep-translator 1.11.4` dính PYSEC-2022-252. Mô tả
lỗ hổng là chính dự án bị chiếm tài khoản (phishing) năm 2022 để đăng bản độc
hại lên PyPI — bản 1.11.3 chạy mã độc ngay lúc `pip install`. Bản 1.11.4 là bản
sạch đăng lại năm 2023 nhưng **không có bản vá nào sau đó**, nên chọn phương án
gỡ hẳn thay vì giữ một gói không vá được.

Không phải mọi thứ đều mất đi cùng lúc. Cái mất thật sự là:
- POI chưa có bản dịch thì đọc bằng bản gốc (`is_fallback=true`), admin nhập
  tay qua `POST /localizations/on-demand`.
- `/audio/on-demand` trả 409 thay vì tự dịch rồi đọc.
- `/localizations/warmup` (dịch nền toàn corpus) bị xoá; route còn lại là
  `GET /localizations/warmup-status` giờ chỉ **báo cáo** cái còn thiếu.
- `/ui-bundles/{locale}` thuần đọc file tĩnh, locale lạ trả 404.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

settings.mongodb_db_name = "amds_test"

THU_MUC_BACKEND = Path(__file__).resolve().parents[1]
THU_MUC_APP = THU_MUC_BACKEND / "app"


def doi_ma_nguon() -> list[str]:
    return [
        str(p.relative_to(THU_MUC_BACKEND))
        for p in list((THU_MUC_APP / "routers").glob("*.py"))
        + list((THU_MUC_APP / "services").glob("*.py"))
    ]


# --- Đạn 1: gói không vá được phải biến mất khỏi requirements ---------------
# Kẻ tấn công: `pip install -r requirements.txt` trên máy dự án là đã chạy mã
# của bên thứ ba. requirements.txt là hợp đồng — để tên gói ở đó là mở cửa.
def test_requirements_khong_con_goi_ky_thuat_dich() -> None:
    dong = (THU_MUC_BACKEND / "requirements.txt").read_text(encoding="utf-8").lower()
    for ten in ("deep-translator", "deep_translator", "google-translate", "googletrans"):
        assert ten not in dong, f"requirements.txt còn {ten}"
    # Gỡ xong thì không được còn gói dịch nào đứng chung hàng
    assert "translat" not in dong, "còn gói dịch khác chưa rà"


def test_ma_nguon_khong_con_goi_dich_may() -> None:
    """Không chỉ gỡ khỏi requirements — mọi lời gọi dịch máy cũng phải biến mất."""
    nghi = ("GoogleTranslator", "deep_translator", "dich_van_ban(", "dich_va_luu(", "dich_nen(")
    sai = []
    for duong_dan in doi_ma_nguon():
        noi_dung = (THU_MUC_BACKEND / duong_dan).read_text(encoding="utf-8")
        for tu_khoa in nghi:
            if tu_khoa in noi_dung:
                sai.append(f"{duong_dan}: {tu_khoa}")
    assert not sai, f"còn dấu vết dịch máy: {sai}"


# --- Đạn 2: hành vi thay đổi phải thật, không chỉ là dọn code ---------------
def test_on_demand_409_khi_thieu_ban_dich() -> None:
    """Không có bản dịch thì không đọc nội dung tiếng Việt bằng giọng tiếng Nhật."""
    from pymongo import MongoClient

    mongo = MongoClient(settings.mongodb_uri)
    db = mongo[settings.mongodb_db_name]
    db["pois"].delete_many({})
    db["poi_localizations"].delete_many({})
    mongo.close()

    with TestClient(app) as c:
        assert c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        # Không có POI nào thì mọi id đều thiếu bản dịch → 409 là câu trả lời
        # đúng, chứ không phải 400/404 nhầm nguyên nhân.
        r = c.post("/audio/on-demand", json={"poi_id": "0" * 24, "lang": "ja"})
        assert r.status_code == 409
        assert "bản dịch" in r.json()["detail"]


def test_ban_dich_nhap_tay_bat_buoc_co_ten() -> None:
    with TestClient(app) as c:
        assert c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        r = c.post("/localizations/on-demand", json={"poi_id": "0" * 24, "lang": "ja"})
        assert r.status_code == 422, "thiếu `name` phải bị từ chối chứ không tự dịch"
        r2 = c.post("/localizations/on-demand", json={"poi_id": "0" * 24, "lang": "ja", "name": "A"})
        assert r2.status_code == 404, "POI không tồn tại phải báo 404"


def test_bundle_ui_la_thao_tac_doc() -> None:
    with TestClient(app) as c:
        assert c.get("/ui-bundles/ja").status_code == 200
        assert c.get("/ui-bundles/xx").status_code == 404


def test_warmup_chi_con_bao_cao() -> None:
    """Route dịch nền phải biến mất; route còn lại chỉ đọc, không ghi."""
    from pymongo import MongoClient

    with TestClient(app) as c:
        assert c.post("/admin/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        duong_dan = [r.path for r in app.routes if "localizations" in getattr(r, "path", "")]
        assert "/localizations/warmup" not in duong_dan, "route dịch nền phải bị gỡ"
        r = c.get("/localizations/warmup-status")
        assert r.status_code == 200
        assert "tong" in r.json() and isinstance(r.json()["thieu"], list)

    mongo = MongoClient(settings.mongodb_uri)
    mongo[settings.mongodb_db_name]["ui_bundles"].delete_many({})
    mongo.close()


def test_bundles_tinh_co_du_ngo_ngu_chinh() -> None:
    """5 ngôn ngữ phải có sẵn file tĩnh — không còn đường dịch bù thiếu."""
    thu_muc = THU_MUC_BACKEND / "static" / "ui"
    for locale in ("vi", "en", "zh", "ja", "ko"):
        tep = thu_muc / f"{locale}.json"
        assert tep.is_file(), f"thiếu bundle UI tĩnh cho {locale}"
        khoa = set(json.loads(tep.read_text(encoding="utf-8")))
        assert "app_title" in khoa


@pytest.mark.parametrize("tap", ["routers", "services"])
def test_khong_con_task_dich_chay_nen(tap: str) -> None:
    """SEC-001 đã cảnh báo endpoint công khai kích hoạt dịch nền; giờ không còn."""
    # Phải xét **theo dòng**: `tasks.py` có asyncio.create_task để chạy tác vụ
    # sinh audio, dính chữ "dịch" trong câu chữ thông báo lỗi — quét cả file
    # rồi kiểm "có cả hai từ" sẽ báo động giả.
    hinh_dang = ("dich_nen", "dich_va_luu", "dich_van_ban", "GoogleTranslator")
    sai = []
    for p in (THU_MUC_APP / tap).glob("*.py"):
        for so, dong in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "asyncio.create_task" in dong and any(t in dong for t in hinh_dang):
                sai.append(f"{p.name}:{so}")
    assert not sai, f"còn task dịch nền: {sai}"