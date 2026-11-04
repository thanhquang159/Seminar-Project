"""SEC-002: chặn đoán mật khẩu ở `POST /admin/auth/login`.

Mật khẩu admin được băm bằng bcrypt nên khó bị đoán mù, nhưng "khó bằng CPU"
không phải là hạn chế truy cập: kẻ tấn công chỉ cần chạy nhiều tiến trình song
song là có vô hạn lượt đoán. Ở đây ta chặn theo **hai chiều** cùng lúc:

- theo **tài khoản** (`ten:<username>`): đoán trúng một tài khoản nào đó;
- theo **IP** (`ip:<ip>`): quét nhiều tài khoản, hoặc xoay nhiều IP để đẩy lượt
  đoán lên một tài khoản.

Chỉ lần **thất bại** mới được tính, và đăng nhập đúng sẽ xoá sạch bộ đếm —
nếu tính cả lần thành công thì người dùng thật đăng nhập hằng ngày sẽ bị
khoá oan, mà khoá oan admin lúc cần gấp còn tệ hơn là chậm vài giây.

Cả hai bộ đếm dùng chung collection `rate_limits` (đã có chỉ mục TTL) nên không
thêm schema, không thêm bảng dọn dẹp: hết cửa sổ thì chính Mongo xoá. Khoá là
**tạm thời**, không có trạng thái "đã khoá" lưu vĩnh viễn — đó là đánh đổi có
ý thức: khoá theo tài khoản tiết kiệm CPU cho server nhưng lợi dụng được để
DoS admin (đẩy admin ra khỏi hệ thống 15 phút bằng 5 lần gõ sai). Cửa sổ 15
phút ngắn và đăng nhập đúng sẽ xoá bộ đếm nên hậu quả bị giới hạn; nếu sau này
cần chịu đựng nhiều hơn thì phải thêm bằng chứng (sự cố thật), không thêm suy
đoán.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.services.ratelimit import cho_phep

DUONG_DAN = "/admin/auth/login"
CUA_SO_PHUT = 15
SAI_TOI_DA_TAI_KHOAN = 5
SAI_TOI_DA_MOT_IP = 20
THONG_BAO_KHOA = "Quá nhiều lần đăng nhập sai, thử lại sau"

TIEN_TO_TEN = "ten:"
TIEN_TO_IP = "ip:"


def moc_cu_thoi_diem(phut: int) -> datetime:
    """Mốc thời gian lùi `phut` phút — dùng cho cửa sổ trượt và cho test."""
    return datetime.now(UTC) - timedelta(minutes=phut)


async def _con(db, khoa: str, gioi_han: int) -> tuple[bool, int]:
    """Hỏi bộ đếm mà KHÔNG ghi nhận lượt này."""
    return await cho_phep(db, khoa, DUONG_DAN, gioi_han, CUA_SO_PHUT, ghi_nhan=False)


async def kiem_tra(db, username: str, ip: str) -> None:
    """Chặn trước khi băm mật khẩu: đã khoá thì trả 429, không tốn CPU.

    Thông báo không nhắc tên đăng nhập, nên kẻ dò tài khoản không biết tài
    khoản nào đang bị khoá.
    """
    ok_ten, cho_ten = await _con(db, TIEN_TO_TEN + username, SAI_TOI_DA_TAI_KHOAN)
    ok_ip, cho_ip = await _con(db, TIEN_TO_IP + ip, SAI_TOI_DA_MOT_IP)
    if not (ok_ten and ok_ip):
        raise HTTPException(
            status_code=429,
            detail=THONG_BAO_KHOA,
            headers={"Retry-After": str(max(cho_ten, cho_ip))},
        )


async def ghi_nhan_that_bai(db, username: str, ip: str) -> None:
    """Ghi một lần đoán sai vào cả hai bộ đếm."""
    await cho_phep(db, TIEN_TO_TEN + username, DUONG_DAN, SAI_TOI_DA_TAI_KHOAN, CUA_SO_PHUT)
    await cho_phep(db, TIEN_TO_IP + ip, DUONG_DAN, SAI_TOI_DA_MOT_IP, CUA_SO_PHUT)


async def xoa_that_bai(db, username: str, ip: str) -> None:
    """Đăng nhập đúng: xoá lịch sử sai của tài khoản đó (và của IP này)."""
    await db["rate_limits"].delete_many(
        {"duong_dan": DUONG_DAN, "khoa": {"$in": [TIEN_TO_TEN + username, TIEN_TO_IP + ip]}}
    )