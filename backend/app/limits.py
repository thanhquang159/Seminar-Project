"""Giới hạn input dùng chung cho mọi endpoint (SEC-001).

Rà soát SEC-001 cho thấy mỗi router tự chế ngưỡng riêng, nên chỗ thiếu rất
dễ xảy ra và rất khó kiểm soát. File này gom tất cả về một chỗ: thêm ngưỡng
mới thì sửa ở đây, không phải quét lại 17 router.

Nguyên tắc: **input không tin được**. Ký tự đến từ client, kể cả trong query
string — không có ngoại lệ cho "chỉ là endpoint nội bộ".
"""

from typing import Annotated

from fastapi import Query
from fastapi.responses import JSONResponse
from pydantic import AfterValidator, Field

# --- Ngôn ngữ -----------------------------------------------------------------
# BCP-47 rút gọn: `vi`, `en`, `zh`, `ja`, `ko`, `vi-VN`, `pt-BR`...
# Cố tình KHÔNG đóng danh sách 5 ngôn ngữ: `services/localization.py` đã có
# fallback 3 tầng cho ngôn ngữ chưa có bản dịch, chặn cứng ở đây sẽ phá vỡ
# tính năng dịch long-tail của UI bundle. Chỉ chặn cái không phải mã ngôn ngữ.
MA_NGON_NGU = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$"

# --- Kích thước ----------------------------------------------------------------
# Body lớn nhất hợp lệ là lô analytics 50 sự kiện (~2 KiB mỗi cái = 100 KiB
# là quá đã; thực tế client gửi vài trăm byte). 64 KiB chặn được payload vài MB
# mà vẫn không đụng vào request hợp lệ nào.
MAX_BODY_BYTES = 64 * 1024

# bcrypt chỉ đọc 72 byte đầu (`app/auth.py:bam_mat_khau`). Mật khẩu dài hơn sẽ
# bị cắt âm thầm, tức là "mật khẩu dài" và "mật khẩu dài + rác" là cùng một
# thứ — nên ta từ chối thay vì để bcrypt âm thầm cắt.
MAX_BYTE_MAT_KHAU = 72

# `ai.LamDepYeuCau` đã dùng 2000 cho một đoạn mô tả, TTS cùng cỡ đó là hợp lý.
MAX_TEXT_TTS = 2000
MAX_ADMIN_NOTE = 500
MAX_THUOC_TINH = 20
MAX_TEN = 200
MAX_MO_TA = 5000


def _mat_khau_trong_gioi_han(v: str) -> str:
    """Đếm **byte** chứ không đếm ký tự — bcrypt cắt theo byte."""
    if len(v.encode()) > MAX_BYTE_MAT_KHAU:
        raise ValueError(f"mật khẩu tối đa {MAX_BYTE_MAT_KHAU} byte")
    return v


# Kiểu dùng lại cho cả đăng nhập lẫn đăng ký để hai nơi không lệch nhau.
MatKhau = Annotated[
    str, Field(min_length=1, max_length=200), AfterValidator(_mat_khau_trong_gioi_han)
]
MatKhauDangKy = Annotated[
    str, Field(min_length=6, max_length=200), AfterValidator(_mat_khau_trong_gioi_han)
]

# Ngôn ngữ: dùng được cả cho body model (Field) lẫn query param (Query).
LangField = Annotated[str, Field(max_length=10, pattern=MA_NGON_NGU)]
LangQuery = Annotated[str, Query(max_length=10, pattern=MA_NGON_NGU)]


class GioiHanBody:
    """Chặn body vượt `MAX_BODY_BYTES` với 413, trước khi Pydantic phân tích.

    Cơ chế: đọc trọn body trước, vượt ngưỡng thì trả 413 luôn, không phát lại
    cho app; còn lại thì phát lại y hệt. Buffer tối đa `MAX_BODY_BYTES`, vì
    chunk vượt ngưỡng bị bỏ, không nối vào bộ nhớ.

    Vì sao không "đếm trong lúc đọc rồi ném lỗi": FastAPI bọc phần đọc body
    trong `except Exception` và biến **mọi** lỗi thành 400 "There was an error
    parsing the body" — lỗi của ta sẽ bị nuốt thành 400, sai ngữ nghĩa (client
    gửi body hợp lệ quá lớn, không phải body hỏng).

    Đặt middleware này TRONG CORS (đăng trước CORS ở `main.py`) để 413 vẫn
    mang header CORS — nếu ngoài CORS thì browser không đọc được lỗi.
    """

    def __init__(self, app, gioi_han: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.gioi_han = gioi_han

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Đường nhanh: Content-Length nói trước kích thước, chặn không cần đọc.
        khai_bao = dict(scope.get("headers") or {}).get(b"content-length")
        if khai_bao is not None:
            try:
                qua = int(khai_bao) > self.gioi_han
            except ValueError:
                qua = True  # Content-Length rác: coi như quá ngưỡng, đừng đoán
            if qua:
                await self._toi_cha(scope, receive, send)
                return

        chunks: list[bytes] = []
        tong = 0
        con = True
        while con:
            tin = await receive()
            if tin["type"] == "http.disconnect":
                return  # client bỏ giữa chừng, không cần trả lời ai
            khoi = tin.get("body", b"")
            tong += len(khoi)
            if tong > self.gioi_han:
                await self._toi_cha(scope, receive, send)
                return
            chunks.append(khoi)
            con = tin.get("more_body", False)

        da_doc = {"trai": False}

        async def phat_lai():
            """Phát lại body đã gom, đúng một lần, giống hệt request gốc."""
            if da_doc["trai"]:
                return {"type": "http.disconnect"}
            da_doc["trai"] = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

        await self.app(scope, phat_lai, send)

    async def _toi_cha(self, scope, receive, send) -> None:
        await JSONResponse(
            status_code=413,
            content={"detail": "Body vượt giới hạn kích thước", "gioi_han_bytes": self.gioi_han},
            headers={"Connection": "close"},
        )(scope, receive, send)