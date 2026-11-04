"""SEC-006 — rà log: log không được chứa PII, token, mật khẩu.

Kẻ tấn công ở đây là người đọc được file log: quản trị viên máy chủ, hoặc
dịch vụ gom log bên thứ ba, hoặc bản log bị đính kèm khi báo lỗi. Họ không cần
vào hệ thống — chỉ cần đọc.

Vì sao tệ nhất là **token**: token trong log là token *còn dùng được*. Người đọc
được không cần đoán mật khẩu, chỉ cần gửi lại chính dòng log đó. Còn PII (CCCD,
số điện thoại, email) thì vi phạm NFR-30 và nghị định 13/2023 về bảo vệ dữ
liệu cá nhân — dữ liệu đã ghi vào log thì coi như đã mất kiểm soát.

Codebase hiện tại **không** in PII ra log — nhưng cũng không có rào chắn nào: đó
là một may mắn, không phải một thiết kế. Task này dựng một điểm nghẽn duy nhất
(`app/log_setup.py`) để mọi dòng log đi ra đều qua một bộ che, kể cả log của
chính uvicorn (access log ghi nguyên query string, nên `?email=...` là rò rỉ
thật chứ không phải giả định).
"""

import io
import logging
from pathlib import Path

import pytest

from app.log_setup import CheBiMatLog, che_bi_mat, dat_cau_hinh_log, lay_logger

THU_MUC_APP = Path(__file__).resolve().parents[1] / "app"

TOKEN_GIA = "Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVwXyZ012345"  # audit_secrets: allow
JWT_GIA = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.9dQxKZ0mT3sVb7nLpQ1rXyE"  # audit_secrets: allow


# --- bộ che: che được thì mới yên ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dong", "khong_duoc_lo"),
    [
        # Access log của uvicorn ghi nguyên query string — đúng loại rò rỉ thật.
        (
            f'127.0.0.1 - "GET /owner?email=cuong%40x.com&token={TOKEN_GIA} HTTP/1.1" 200',
            ["cuong%40x.com", TOKEN_GIA],
        ),
        ('{"username":"cuong","password":"S3cr3t-Pass-123"}', ["S3cr3t-Pass-123"]),
        (f'Authorization: Bearer {JWT_GIA}', [JWT_GIA]),
        (f'{{"token": "{JWT_GIA}"}}', [JWT_GIA]),
        ("cccd=079012345678 sdt=0901234567", ["079012345678", "0901234567"]),
        ("mongodb://quan4:S3cret-do-mongo@localhost:27017", ["S3cret-do-mongo"]),
        (f"https://api.maptiler.com/maps/x/style.json?key={TOKEN_GIA}", [TOKEN_GIA]),
        ("Set-Cookie: access_token=xyz123; HttpOnly", ["xyz123"]),
    ],
)
def test_che_bi_mat_khong_lot_bi_mat(dong: str, khong_duoc_lo: list[str]) -> None:
    ket_qua = che_bi_mat(dong)
    for bi_mat in khong_duoc_lo:
        assert bi_mat not in ket_qua, f"còn lọt: {bi_mat}"
    assert "ĐÃ CHE" in ket_qua


@pytest.mark.parametrize(
    "dong",
    [
        "[startup] MongoDB connected ✅ (14 collections)",
        '127.0.0.1 - "GET /poi/65f1c2a3b4d5e6f7a8b9c0d1?lang=vi HTTP/1.1" 200',
        "POST /analytics HTTP/1.1 201 (events=12)",
        "[analytics] worker lỗi, thử lại: đã hết thời gian chờ server",
    ],
)
def test_che_bi_mat_giu_nguyen_log_binh_thuong(dong: str) -> None:
    """Bộ che mà nuốt cả log bình thường thì không ai đọc log nữa — và mù lòng
    thì lọt càng nhiều. Chỉ che đúng chỗ nhạy cảm."""
    assert che_bi_mat(dong) == dong


# --- đi qua hệ thống log thật ---------------------------------------------------------------------------


def _dong_log_uvicorn(full_path: str) -> str:
    """Phát một dòng access log **đúng kiểu uvicorn** rồi đọc lại chuỗi đã ghi.

    Uvicorn không nối sẵn thành chuỗi: nó đặt `msg` làm format string và đẩy 5 giá
    trị thật vào `args`, rồi mới dựng `request_line` trong `formatMessage`. Che ở
    tầng `msg` sẽ không bắt được gì — nên test phải đi đúng đường đó, dùng chính
    `AccessFormatter` của uvicorn, thay vì tự chế một dòng log giả.
    """
    from uvicorn.logging import AccessFormatter  # noqa: PLC0415 — nặng, chỉ test dùng

    dong = io.StringIO()
    handler = logging.StreamHandler(dong)
    handler.setFormatter(AccessFormatter(fmt="%(client_addr)s - \"%(request_line)s\" %(status_code)s", use_colors=False))
    logger = logging.getLogger("uvicorn.access")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1",
            "GET",
            full_path,
            "1.1",
            401,
        )
    finally:
        logger.removeHandler(handler)
    return dong.getvalue()


def test_access_log_khong_con_ban_ro_bi_mat() -> None:
    dat_cau_hinh_log()
    ra = _dong_log_uvicorn(f"/owner?email=cuong%40x.com&token={TOKEN_GIA}")
    assert TOKEN_GIA not in ra, "token còn nguyên trong access log"
    assert "cuong%40x.com" not in ra, "email còn nguyên trong access log"
    assert "ĐÃ CHE" in ra


def test_log_giu_nguyen_request_linh_thuong() -> None:
    """Che có chọn lọc: dòng access log bình thường phải giữ nguyên để còn đọc
    được (số 9–12 chữ số trong id/ngày không phải PII)."""
    dat_cau_hinh_log()
    ra = _dong_log_uvicorn("/poi/65f1c2a3b4d5e6f7a8b9c0d1?lang=vi")
    assert "GET /poi/65f1c2a3b4d5e6f7a8b9c0d1?lang=vi HTTP/1.1" in ra


def test_log_vao_bien_che_roi_thi_ghi_ban_ro() -> None:
    """Trường hợp dễ quên nhất: dán chuỗi vào `msg` bằng f-string rồi truyền tham số
    `%s` cho phần động — chuỗi nằm trong msg nên phải che ở msg. Logger lấy từ
    `lay_logger("thu_nghiem")` là logger **con** của `app`: nếu chỉ gắn bộ che ở
    logger cha thì dòng này lọt nguyên."""
    dat_cau_hinh_log()
    dong = io.StringIO()
    handler = logging.StreamHandler(dong)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = lay_logger("thu_nghiem")
    logger.addHandler(handler)
    try:
        logger.warning(f"đăng nhập sai: token={TOKEN_GIA} sau %s lần", 3)
    finally:
        logger.removeHandler(handler)
    ra = dong.getvalue()
    assert TOKEN_GIA not in ra and "sau 3 lần" in ra


def test_chuoi_khong_nhan_dien_duoc_gi_nguyen() -> None:
    """Giới hạn đã biết, ghi ra để không ai tưởng là đã che hết: một chuỗi lạ
    không kèm tên biến thì không che được. Cố đoán theo độ hỗn loạn ký tự sẽ nuốt
    luôn ObjectId 24 ký tự hex, ETag, hash — log thành bảng chữ nhiệu. Quy ước
    thay cho phép đoán: log bằng tham số có tên (`token=%s`), đừng dán thẳng giá
    trị vào chuỗi."""
    dong = f"ghichu {TOKEN_GIA}"
    assert che_bi_mat(dong) == dong


def test_che_duoc_gan_vao_tat_ca_logger_va_uvicorn() -> None:
    """Bộ che phải bám vào logger của uvicorn, không chỉ logger của app: access log
    do uvicorn phát, không đi qua code của mình."""
    dat_cau_hinh_log()
    for ten in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        filters = logging.getLogger(ten).filters
        assert any(isinstance(f, CheBiMatLog) for f in filters), f"{ten} chưa gắn bộ che"


def test_exception_co_bi_mat_trong_ban_ghi() -> None:
    """Traceback từ driver DB có thể chứa giá trị tài liệu (ví dụ khoá trùng);
    uvicorn phát traceback, không qua bộ lọc mặc định."""
    dat_cau_hinh_log()
    dong = io.StringIO()
    handler = logging.StreamHandler(dong)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = lay_logger("thu_nghiem")
    logger.addHandler(handler)
    try:
        try:
            raise RuntimeError(f"E11000 duplicate key: token={TOKEN_GIA}")
        except RuntimeError:
            logger.exception("ghi analytics thất bại")
    finally:
        logger.removeHandler(handler)
    assert TOKEN_GIA not in dong.getvalue()


def test_dat_cau_hinh_log_chay_hai_lan_van_dung() -> None:
    """`--reload` của uvicorn nạp lại app nhiều lần; gắn bộ che hai lần làm log bị
    che hai lần (tệ) hoặc nhân bộn (rò)."""
    dat_cau_hinh_log()
    so_lan = len(logging.getLogger("uvicorn.access").filters)
    dat_cau_hinh_log()
    assert len(logging.getLogger("uvicorn.access").filters) == so_lan


# --- ngăn tái phạm: không viết log trực tiếp trong app ---------------------------------------------------


def test_app_khong_dung_print() -> None:
    """`print` lách khỏi hệ thống log nên không ai cấu hình được, không ai lọc
    được. Mọi dòng log phải đi qua `logging`."""
    lan = []
    for duong_dan in THU_MUC_APP.rglob("*.py"):
        for so_dong, dong in enumerate(duong_dan.read_text(encoding="utf-8").splitlines(), 1):
            if "print(" in dong:
                lan.append(f"{duong_dan.relative_to(THU_MUC_APP)}:{so_dong}")
    assert lan == [], f"còn print() trong app: {lan}"
