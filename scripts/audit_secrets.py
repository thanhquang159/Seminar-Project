#!/usr/bin/env python3
"""SEC-005 — quét bí mật rò rỉ trong repo và trong lịch sử git.

Lý do tồn tại: một lần rà soát bằng mắt chỉ nói được "lúc này sạch". Bí mật
lọt vào git thì **đã lọt** — xoá file ở commit sau không gỡ được khỏi lịch sử,
và repo đẩy lên GitHub thì bất kỳ ai cũng đọc được toàn bộ. Nên phải có máy
quét, chạy mỗi lần verify.

    python scripts/audit_secrets.py            # file đang được git theo dõi
    python scripts/audit_secrets.py --lich-su  # thêm cả lịch sử commit (chậm)
    python scripts/audit_secrets.py --goc DIR  # quét repo khác

Nguyên tắc: báo cáo **không** in ra bí mật đầy đủ (chỉ 4 ký tự đầu + độ dài).
Một công cụ quét bí mật mà làm rò bí mật vào log CI là công cụ tự hại mình.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

GOC_MAC_DINH = Path(__file__).resolve().parents[1]
# Danh sách chấp nhận: những phát hiện trong **lịch sử** đã biết và được chấp nhận.
# Lịch sử git không sửa được (không muốn rewrite lịch sử chỉ vì mẫu giả trong test),
# nên file này ghi vân tay của từng phát hiện cũ. Phát hiện mới — không có trong
# danh sách — vẫn làm verify FAIL như thường.
TEP_BASELINE = Path("scripts") / "audit_secrets_baseline.txt"

# File nào được phép chứa chuỗi giống bí mật. `.example` để trống mẫu; còn
# `tests/` dùng mật khẩu giả cố định — quét nó vẫn được nhưng bằng luật chính xác
# (định dạng của nhà cung cấp), không dùng luật "gán biến" để tránh báo động.
BO_QUA_THU_MUC = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", ".pi", ".omo"}
KICH_THUOC_TOI_DA = 2_000_000  # file > 2 MB coi như không quét (log, pack bản đồ)

# Dấu cho phép bỏ qua **một dòng**. Cần khi cố tình đặt bí mật giả vào mã (test của
# chính máy quét, ví dụ mẫu `ghp_...`). Bỏ qua theo dòng chứ không theo thư mục:
# thư mục test còn chứa nhiều thứ khác cần quét, còn "bỏ qua cả file" thì ai đó
# lỡ tay commit key vào đúng file đó là xong.
DAU_CHE_PHUONG = "audit_secrets: allow"


@dataclass(frozen=True)
class PhatHien:
    """Một nghi vấn: quy tắc nào, ở đâu, dài bao nhiêu. Không giữ giá trị bí mật.

    `van_tay` là hash của (quy tắc + giá trị) để so với danh sách chấp nhận mà
    không phải lưu giá trị bí mật vào file nào.
    """

    quy_tac: str
    mo_ta: str
    noi_dung: str
    do_dai: int
    doan_dau: str
    van_tay: str


# Mỗi luật bám theo **định dạng thật** của nhà cung cấp nên rất ít báo động.
# Luật cuối ("gán biến") là lưới thô, cố tình bỏ sót để không thành công cụ spam.
LUAT = [
    (
        "khoa-rieng-tu",
        "khoá riêng tư PEM",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    ("maptiler", "key MapTiler trong URL", re.compile(r"[?&]key=[A-Za-z0-9_-]{20,}")),
    ("jwt", "JWT", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("aws", "khoá truy cập AWS", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google", "khoá API Google", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("openai", "khoá OpenAI", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("github", "token GitHub", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack", "token Slack", re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}")),
    (
        "gan-bien",
        "biến tên kiểu bí mật được gán giá trị dài",
        re.compile(
            r"(?i)\b(?:secret|token|password|passwd|api[_-]?key|private[_-]?key|jwt[_-]?secret)"
            # [ \t] chứ không \s: \s nuốt cả dòng mới, nên `REFRESH_TOKEN_SECRET=`
            # rỗng sẽ "nhảy" xuống dòng dưới rồi ăn nhầm tên biến kế tiếp.
            r"\b[ \t]*[:=][ \t]*[\"']?([A-Za-z0-9_\-+/=]{20,})[\"']?"
        ),
    ),
    (
        # Biến môi trường viết kiểu SCREAMING_CASE (`MAPTILER_KEY=...`) — phải bắt
        # riêng: luật trên cố tình không khớp mọi thứ đuôi "key", vì `getMapLayerKey =`
        # trong mã nguồn là tên hàm chứ không phải bí mật. Ràng đầu dòng + tên viết
        # hoa là ranh giới giữa "khoá" và "biến trong code".
        "khoa-moi-truong",
        "khoá gán trong file cấu hình kiểu biến môi trường",
        re.compile(
            r"(?m)^[ \t]*(?:export[ \t]+)?[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD)[A-Z0-9_]*"
            r"[ \t]*[:=][ \t]*[\"']?([A-Za-z0-9_\-+/=]{20,})"
        ),
    ),
]

# Giá trị mẫu/giả đúng nghĩa — thấy thì không báo, nếu không bản thân file .example
# và test fixture sẽ làm công cụ vô dụng.
GIA_TRI_MAU = {
    "dev-access-secret-doi-khi-deploy",
    "dev-refresh-secret-doi-khi-deploy",
    "doi-khi-deploy-thi-can-doi",
    "chang-me-trong-moi-nay",
}


def _nen_dong_tinh(ten: str, noi_dung: str) -> list[PhatHien]:
    ra: list[PhatHien] = []
    dong = noi_dung.splitlines()
    for quy_tac, mo_ta, mau in LUAT:
        for canh in mau.finditer(noi_dung):
            so_dong = noi_dung.count("\n", 0, canh.start())
            if so_dong < len(dong) and DAU_CHE_PHUONG in dong[so_dong]:
                continue  # dòng đã được người viết đánh dấu là mẫu giả
            gia_tri = canh.group(1) if canh.groups() else canh.group(0)
            if gia_tri in GIA_TRI_MAU:
                continue
            ra.append(
                PhatHien(
                    quy_tac=quy_tac,
                    mo_ta=mo_ta,
                    noi_dung=f"{ten}:{so_dong + 1}",
                    do_dai=len(gia_tri),
                    doan_dau=gia_tri[:4],
                    van_tay=hashlib.sha256(f"{quy_tac}|{gia_tri}".encode()).hexdigest()[:16],
                )
            )
    return ra


def quet_noi_dung(ten: str, noi_dung: str) -> list[PhatHien]:
    """Quét một khối văn bản. Tách khỏi đọc file để test không cần file thật."""
    return _nen_dong_tinh(ten, noi_dung)


def quet_file(path: Path, goc: Path) -> list[PhatHien]:
    if any(phan in BO_QUA_THU_MUC for phan in path.parts):
        return []
    if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".ico"}:
        return []
    try:
        if path.stat().st_size > KICH_THUOC_TOI_DA:
            return []
        noi_dung = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return quet_noi_dung(str(path.relative_to(goc)).replace("\\", "/"), noi_dung)


def _git(goc: Path, *args: str) -> str:
    ket = subprocess.run(
        ["git", *args], cwd=goc, capture_output=True, text=True, check=False, encoding="utf-8"
    )
    return ket.stdout if ket.returncode == 0 else ""


def quet_file_dang_track(goc: Path) -> list[PhatHien]:
    """Quét file git theo dõi **và** file mới chưa `git add`.

    File trong `node_modules` hay thư mục build không phải thứ sẽ bị đẩy lên, quét
    chúng chỉ làm chậm và gây báo động. File chưa add thì phải quét: lúc đó người
    viết còn sửa được, và bắt được trước khi nó thành lịch sử vĩnh viễn.
    """
    danh_sach = _git(goc, "ls-files").splitlines()
    danh_sach += _git(goc, "ls-files", "--others", "--exclude-standard").splitlines()
    ra: list[PhatHien] = []
    for dong in danh_sach:
        if not dong:
            continue
        ra.extend(quet_file(goc / dong, goc))
    return ra


def _bo_tien_to_diff(noi_dung: str) -> str:
    """Cắt tiền tố `+`/`-`/` ` mà git thêm vào đầu mỗi dòng trong `log -p`.

    Không cắt thì luật bám đầu dòng (kiểu dòng cấu hình) không bao giờ khớp khi
    quét lịch sử: dòng `+MAPTILER_KEY=...` bắt đầu bằng dấu cộng.
    """
    return "\n".join(d[1:] if d[:1] in {"+", "-", " "} else d for d in noi_dung.splitlines())


def quet_lich_su(goc: Path) -> list[PhatHien]:
    """Quét nội dung mọi commit đã có.

    Đây là phần quan trọng nhất: bí mật bị commit rồi xoá file vẫn còn nguyên
    trong lịch sử, và ai clone repo cũng đọc được. Chậm hơn quét file hiện tại
    nên để sau `--lich-su`.
    """
    diff = _git(goc, "log", "-p", "--all", "--no-color")
    return quet_noi_dung("lich-su-git", _bo_tien_to_diff(diff))


def bao_cao(phat_hien: list[PhatHien]) -> str:
    if not phat_hien:
        return "Không thấy bí mật nào."
    dong = []
    for p in phat_hien:
        dong.append(
            f"  [{p.quy_tac}] {p.mo_ta} tại {p.noi_dung}"
            f" — dài {p.do_dai} ký tự, bắt đầu '{p.doan_dau}…'"
        )
    return "\n".join(dong)


def nap_danh_sach_chap_nhan(tep: Path) -> set[str]:
    """Đọc danh sách chấp nhận; dòng `#` là chú thích."""
    if not tep.is_file():
        return set()
    return {
        dong.split("#", 1)[0].split()[0]
        for dong in tep.read_text(encoding="utf-8").splitlines()
        if dong.strip() and not dong.lstrip().startswith("#")
    }


def ghi_danh_sach_chap_nhan(tep: Path, phat_hien: list[PhatHien]) -> None:
    # Một vân tay một dòng: cùng một bí mật giả có thể xuất hiện ở nhiều nơi, ghi
    # lặp lại chỉ làm file khó đọc.
    da_thay = {p.van_tay: p for p in phat_hien}
    tep.parent.mkdir(parents=True, exist_ok=True)
    tep.write_text(
        "# Danh sách chấp nhận cho scripts/audit_secrets.py -- lich-su.\n"
        "# Mỗi dòng: <vân tay> <quy tắc> <4 ký tự đầu> — mô tả.\n"
        "# CHỈ dùng cho thứ đã biết là không phải rò rỉ thật (mẫu giả trong test).\n"
        "# Bí mật thật thì phải đổi khoá/xoá lịch sử, không bao giờ ghi vào đây.\n"
        + "\n".join(
            f"{p.van_tay}  {p.quy_tac:<16} {p.doan_dau}…  — {p.mo_ta} ({p.noi_dung})"
            for p in sorted(da_thay.values(), key=lambda x: x.van_tay)
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Quét bí mật rò rỉ trong repo.")
    ap.add_argument("--goc", type=Path, default=GOC_MAC_DINH, help="thư mục gốc repo")
    ap.add_argument("--lich-su", action="store_true", help="quét cả lịch sử commit (chậm)")
    ap.add_argument(
        "--cap-nhat-danh-sach-chap-nhan",
        action="store_true",
        help="ghi lại phát hiện lịch sử hiện tại vào danh sách chấp nhận rồi thoát",
    )
    args = ap.parse_args(argv)

    goc: Path = args.goc.resolve()
    tep = goc / TEP_BASELINE
    phat_hien = quet_file_dang_track(goc)
    if args.lich_su:
        phat_hien += quet_lich_su(goc)

    print(f"=== Quét bí mật (SEC-005): {goc} ===")
    so_file = len(_git(goc, "ls-files").splitlines())
    print(f"Quét {so_file} file được theo dõi" f"{' + lịch sử commit' if args.lich_su else ''}.")

    if args.cap_nhat_danh_sach_chap_nhan:
        # Chỉ lịch sử mới cần danh sách chấp nhận: file đang theo dõi thì còn sửa
        # được, báo động giả ở đó phải đỏ để người viết dán dấu phù hợp.
        ghi_danh_sach_chap_nhan(tep, quet_lich_su(goc))
        print(f"Đã cập nhật {tep.relative_to(goc)}")
        return 0

    # Danh sách chấp nhận chỉ có tác dụng với lịch sử: file đang theo dõi thì báo
    # động giả cũng phải đỏ, vì đó là chỗ sẽ đẩy lên lần sau.
    da_chap_nhan = nap_danh_sach_chap_nhan(tep)
    moi = [p for p in phat_hien if p.van_tay not in da_chap_nhan]

    if not phat_hien:
        print("Không thấy bí mật nào.")
        return 0
    if moi:
        print("!!! FAIL: có nghi vấn bí mật — giá trị bị che, sửa trước khi commit:")
        print(bao_cao(moi))
    else:
        print("Không thấy bí mật mới nào.")
    da_bi_chap_nhan = len(phat_hien) - len(moi)
    print(f"({da_bi_chap_nhan} phát hiện cũ nằm trong danh sách chấp nhận, bỏ qua.)")
    return 1 if moi else 0


if __name__ == "__main__":
    raise SystemExit(main())