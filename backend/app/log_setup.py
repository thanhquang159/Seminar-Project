"""Một điểm nghẽn duy nhất cho mọi dòng log: che PII, token, mật khẩu (SEC-006).

Vì sao phải có: log là nơi dữ liệu sống lâu nhất mà không ai nghĩ tới. Dữ liệu
trong DB còn xoá được, còn log đã đẩy lên máy chủ, đẩy vào hệ thống gom log,
đẩy vào file backup — xoá ở nguồn không còn ý nghĩa. Với token còn tệ hơn: token
ghi trong log là token **còn dùng được**, đọc là xong.

Cách phòng ở đây không phải "nhớ cẩn thận khi viết log" — con người sẽ quên, và
quên đúng lúc đang sửa lỗi giữa đêm. Thay vào đó mọi dòng log đều đi qua một bộ
che, kể cả log do uvicorn phát ra chứ không phải code của mình.

Nguyên tắc:
- Che trước, ghi sau. Dòng đã ghi ra file thì không cứu được.
- Che cả ngoại suẩn (`exc_info`), vì traceback driver DB hay kèm giá trị tài liệu.
- Không che log bình thường: bộ che nuốt hết thì không ai đọc log nữa.

Giới hạn đã biết: chỉ che được thứ **có tên** (`token=...`, `email=...`, DSN, JWT,
chữ Bearer, 9–12 chữ số đứng riêng). Một chuỗi lạ dán thẳng vào log thì không che
được, và cố đoán theo độ hỗn loạn ký tự sẽ nuốt luôn ID dạng hex 24 ký tự, ETag,
hash. Quy ước thay cho phép đoán: log bằng tham số có tên (`"token=%s"`), đừng dán
giá trị thẳng vào chuỗi f-string.
"""

import logging
import re

# Nội dung thay thế. Nhìn thấy nó trong log là biết chỗ đó đã được che, không tưởng
# là dữ liệu thật còn nguyên.
DAU_DA_CHE = "[ĐÃ CHE]"

LOGGER_Uvicorn = ("uvicorn", "uvicorn.error", "uvicorn.access")
# Logger dùng chung của app: code trong `app/` gọi `logging.getLogger("app")`.
LOGGER_APP = "app"

# Thứ tự có ý thức: che cấu trúc cặp khoá/giá trị trước, rồi mới che mẫu thô.
# Nếu làm ngược lại thì `?email=...` bị luật email ăn mất phần `email=` và dòng log
# mất nghĩa.
_CAC_MAU = (
    # Cặp khoá/giá trị trong JSON, query string, header hay tên biến. Nhận cả tên
    # có dấu gạch dưới và không có (matkhau vs mat_khau), kể cả khoá đã được quote.
    re.compile(
        r"(?i)\b(pass(word|wd)?|mat_?khau|token|access_token|refresh_token|secret"
        r"|api_?key|authorization|cookie|session|cccd|cmnd|so_?dien_?thoai|sdt|phone"
        r"|email|thu_?dien_?thu|pii_key)"
        r"(\"?\s*[:=]\s*\"?)([^\"\s,;&}]+)"
    ),
    # `Cookie: access_token=xyz` — cookie luôn là `tên=giá trị` không có dấu `:`.
    re.compile(r"(?i)\b(access_token|refresh_token|sessionid|session_id|jwt)(=)([^\s;]+)"),
    # DSN có mật khẩu: postgresql://user:mat_khau@host
    re.compile(r"(?i)(://[^\s:/@]+:)([^\s@]+)(@)"),
    # JWT và chữ Bearer.
    re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"),
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}"),
    # Key MapTiler trong URL — mọi `VITE_*` đều nằm trong bundle gửi cho trình
    # duyệt, nên key này không phải bí mật nhưng vẫn là tài nguyên có chi phí.
    re.compile(r"(?i)([?&]key=)[A-Za-z0-9_-]{16,}"),
    # Số điện thoại / CCCD: 9–12 chữ số đứng riêng. Bề rộng có chủ đích — số dài
    # hơn (13 chữ số, ví dụ mốc thời gian mili giây) không phải PII.
    re.compile(r"(?<!\d)\d{9,12}(?!\d)"),
)


def _che_cap_khoa(ten: str, dau: str) -> str:
    return f"{ten}{dau}{DAU_DA_CHE}"


def che_bi_mat(text: str) -> str:
    """Trả về bản đã che. Đây là hàm thuần: dùng được ở test, ở exception handler,
    ở mọi nơi cần trước khi ghi ra nơi khác."""
    ra = text
    ra = _CAC_MAU[0].sub(lambda m: _che_cap_khoa(m.group(1), m.group(3)), ra)
    ra = _CAC_MAU[1].sub(lambda m: f"{m.group(1)}{m.group(2)}{DAU_DA_CHE}", ra)
    ra = _CAC_MAU[2].sub(lambda m: f"{m.group(1)}{DAU_DA_CHE}{m.group(3)}", ra)
    ra = _CAC_MAU[3].sub(DAU_DA_CHE, ra)
    ra = _CAC_MAU[4].sub(lambda m: f"{m.group(1)} {DAU_DA_CHE}", ra)
    ra = _CAC_MAU[5].sub(lambda m: f"{m.group(1)}{DAU_DA_CHE}", ra)
    return _CAC_MAU[6].sub(DAU_DA_CHE, ra)


class CheBiMatLog(logging.Filter):
    """Bộ che gắn vào logger: mọi bản ghi đi qua đều đã che.

    Che **cả `args`**, không chỉ `msg`. Access log của uvicorn đặt giá trị thật vào
    `record.args = (client_addr, method, full_path, http_version, status_code)` rồi
    mới dựng `request_line` lúc format — che `msg` thì vô tác dụng với nhánh log
    quan trọng nhất. Cũng không gộp `msg` với `args`: uvicorn giải nén đúng 5 phần
    tử trong `args`, gộp lại là làm hỏng formatter của nó.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = che_bi_mat(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(che_bi_mat(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                k: (che_bi_mat(v) if isinstance(v, str) else v) for k, v in record.args.items()
            }
        if record.exc_info and not record.exc_text:
            # Nạp sẵn traceback đã che để Formatter dùng bản này thay vì dựng lại.
            record.exc_text = che_bi_mat(logging.Formatter().formatException(record.exc_info))
        return True


def _gan(filter_che: CheBiMatLog, logger: logging.Logger) -> None:
    """Gắn vào logger (chặn bản ghi sinh ra từ chính logger) và vào từng handler
    của nó (chặn bản ghi đến từ logger con truyền lên).

    Phải làm cả hai: filter cấp logger **không** chạy cho bản ghi của logger con,
    còn filter cấp handler thì không chạy khi bản ghi đi bằng `lastResort`.
    """
    if not any(isinstance(f, CheBiMatLog) for f in logger.filters):
        logger.addFilter(filter_che)
    for handler in logger.handlers:
        if not any(isinstance(f, CheBiMatLog) for f in handler.filters):
            handler.addFilter(filter_che)


def lay_logger(duong_dan: str = "") -> logging.Logger:
    """Logger đã gắn bộ che, dùng cho mọi dòng log của app.

    Vì sao có hàm này mà không gọi thẳng `getLogger`: filter gắn ở logger cha
    không có tác dụng với logger con — `logging` chỉ hỏi filter của chính logger
    phát ra bản ghi. Gọi qua đây thì logger nào cũng được che, kể cả khi người
    viết không biết mình đang dùng logger con.
    """
    ten = f"{LOGGER_APP}.{duong_dan}" if duong_dan else LOGGER_APP
    logger = logging.getLogger(ten)
    if not any(isinstance(f, CheBiMatLog) for f in logger.filters):
        logger.addFilter(CheBiMatLog())
    return logger


def dat_cau_hinh_log() -> None:
    """Gắn bộ che vào logger của app, logger gốc và logger của uvicorn.

    Gắn cho `uvicorn.access` vì request line của nó chứa nguyên query string —
    `GET /owner?email=...` là dòng log của uvicorn, không phải của app.
    Chạy nhiều lần vẫn một lần (`--reload` của uvicorn nạp lại app liên tục).
    """
    filter_che = CheBiMatLog()
    root = logging.getLogger()
    for ten in (LOGGER_APP, *LOGGER_Uvicorn):
        _gan(filter_che, logging.getLogger(ten))
    _gan(filter_che, root)
    if not any(isinstance(f, CheBiMatLog) for f in logging.lastResort.filters):
        logging.lastResort.addFilter(filter_che)