"""Lưu ảnh POI (SEC-012).

Vì sao có file này: đặc tả (`system-presentation-standalone.html`) định nghĩa
`MAX_IMAGE_SIZE = 5 MB` và `MAX_POI_IMAGES = 8`, nhưng code Quận 4 chưa có
route nào nhận ảnh. Ba điều phải đúng, theo đúng thứ tự:

1. **Tệp có thật sự là ảnh không** — không tin đuôi file và không tin
   `Content-Type` do client gửi. Kẻ tấn công đổi tên `shell.jpg` rồi gửi
   `image/jpeg` là chuyện thường; nếu file này được phục vụ dưới `/static` thì
   nó chạy **dưới domain của chính site**, CSP `script-src 'self'` không cứu
   được. Nên ta đọc magic bytes, rồi mở bằng Pillow để xác nhận ảnh giải mã
   được. `<svg onload=...>` và HTML đều rơi ở bước này.
2. **Kích thước và số lượng** — 5 MB mỗi ảnh, 8 ảnh mỗi POI. Đếm lại từ DB mỗi
   lần tải, không tin mảng `images` lưu sẵn (dữ liệu cũ có thể đã vượt).
3. **Tên tệp** — không ghép tên người dùng vào đường dẫn. Tên sinh từ
   `uuid4().hex`; tên gốc chỉ dùng để báo lỗi cho dễ hiểu. Nhờ vậy
   `../../`, `a/b.jpg`, tên Unicode, `\x00` hay tên 300 ký tự đều vô hại.
"""

import io
import re
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.limits import MAX_BYTE_ANH

MAX_ANH = 8
THU_MUC_ANH = Path(__file__).resolve().parents[2] / "static" / "images"

# Đuôi được phép. Kiểm đuôi **và** magic bytes cùng lúc: đuôi bắt được ý định
# của người gửi (tải nhầm `.exe`), magic bytes bắt được nội dung giả. Chỉ kiểm
# magic bytes thì file `.exe` vẫn lọt — không nguy hiểm, nhưng nghĩa là server
# nhận mọi thứ tên ảnh; chỉ kiểm đuôi thì đổi tên là xong.
DUOI_DUOC_PHEP = frozenset({"jpg", "jpeg", "jfif", "png", "webp"})

THONG_BAO_KHONG_PHAI_ANH = "Tệp không phải ảnh hợp lệ (chỉ nhận JPEG, PNG, WebP)"
THONG_BAO_QUA_LON = f"Ảnh vượt {MAX_BYTE_ANH // (1024 * 1024)} MB"
THONG_BAO_QUA_NHIEU = f"Mỗi POI tối đa {MAX_ANH} ảnh"


class LoiAnh(ValueError):
    """Ảnh bị từ chối — `so_loi` là mã HTTP cần trả về.

    Phải tự đặt `self.so_loi`: `ValueError` nhận `*args` nên `LoiAnh(msg, 400)`
    chỉ đẩy vào `args`, truy cận `.so_loi` sẽ ném `AttributeError` — đúng loại
    lỗi 500 mà bài này cảnh báo.
    """

    def __init__(self, thong_bao: str, so_loi: int = 400) -> None:
        super().__init__(thong_bao)
        self.so_loi = so_loi


# Magic bytes: 8 ký tự đầu là đủ để phân biệt 3 định dạng này và loại mọi
# thứ còn lại (HTML, script, ZIP, PDF…). `imghdr` đã bị bỏ ở Python 3.13.
_MAGIC = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"RIFF", "webp"),
)


def _do_la_webp(du_lieu: bytes) -> bool:
    return len(du_lieu) >= 12 and du_lieu[:4] == b"RIFF" and du_lieu[8:12] == b"WEBP"


def _do_la_anh_that(du_lieu: bytes) -> bool:
    """Pillow là trọng tài: magic bytes khớp mà vẫn hỏng (file cắt dở) thì loại."""
    try:
        with Image.open(io.BytesIO(du_lieu)) as im:
            im.verify()  # verify() đủ để chặn file hỏng, không giải mã toàn bộ
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return False
    return True


def kiem_tra_anh(du_lieu: bytes, ten_tam: str = "") -> str:
    """Trả về đuôi file chuẩn hóa, hoặc ném `LoiAnh` khi không đạt.

    `ten_tam` chỉ dùng để báo lỗi dễ đọc — không bao giờ dùng làm tên tệp lưu.
    """
    if not du_lieu:
        raise LoiAnh(THONG_BAO_KHONG_PHAI_ANH, 400)
    if len(du_lieu) > MAX_BYTE_ANH:
        raise LoiAnh(THONG_BAO_QUA_LON, 413)

    duoi_goc = ten_tam.rsplit(".", 1)[-1].lower() if "." in ten_tam else ""
    if duoi_goc not in DUOI_DUOC_PHEP:
        raise LoiAnh(f"Chỉ nhận ảnh: {', '.join(sorted(DUOI_DUOC_PHEP))}", 415)

    duoi = ""
    for dau, ten_duoi in _MAGIC:
        if du_lieu.startswith(dau):
            duoi = ten_duoi
            break
    if not duoi and _do_la_webp(du_lieu):
        duoi = "webp"
    if not duoi:
        raise LoiAnh(THONG_BAO_KHONG_PHAI_ANH, 400)
    if not _do_la_anh_that(du_lieu):
        raise LoiAnh(THONG_BAO_KHONG_PHAI_ANH, 400)
    return duoi


def ten_an_toan(du_lieu: bytes, duoi: str) -> str:
    """Tên tệp sinh từ UUID — không suy ra từ tên người dùng gửi lên."""
    return f"{uuid.uuid4().hex}.{duoi}"


def duong_dan_luu(poi_id: str, ten: str) -> Path:
    """Ghép đường dẫn lưu, có chặn thoát khỏi thư mục ảnh.

    `poi_id` và `ten` đều đã do ta sinh, nhưng hàm này vẫn kiểm tra lại vì nó là
    chỗ duy nhất quyết định "ghi ra đâu trên đĩa" — một thay đổi ở tầng trên
    không được âm thầm biến nó thành đường dẫn tùy ý.
    """
    thu_muc = (THU_MUC_ANH / poi_id).resolve()
    tep = (thu_muc / ten).resolve()
    if thu_muc not in tep.parents:
        raise LoiAnh("Tên ảnh không hợp lệ", 400)
    return tep


def kiem_tra_so_luong(hien_co: int) -> None:
    """Đếm lại từ dữ liệu thật trong DB, không tin mảng lưu sẵn."""
    if hien_co >= MAX_ANH:
        raise LoiAnh(THONG_BAO_QUA_NHIEU, 400)


def url_cua(ten: str) -> str:
    return f"/static/images/{ten}"


def ten_tuyen_du_co_hinh(ten: str) -> str:
    """Chỉ dùng để nhận diện trong thông báo lỗi / log, không lưu."""
    lam_sach = re.sub(r"[^\w.\-]", "_", ten, flags=re.UNICODE)[:60]
    return lam_sach or "khong-ro-tep"


# metadata ảnh trong DB chỉ ghi tối đa bấy nhiêu trường.
