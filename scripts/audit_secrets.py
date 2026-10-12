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
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

GOC_MAC_DINH = Path(__file__).resolve().parents[1]

# File nào được phép chứa chuỗi giống bí mật. `.example` để trống mẫu; còn
# `tests/` dùng mật khẩu giả cố định — quét nó vẫn được nhưng bằng luật chính xác
# (định dạng của nhà cung cấp), không dùng luật "gán biến" để tránh báo động.
BO_QUA_THU_MUC = {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", ".pi", ".omo"}
KICH_THUOC_TOI_DA = 2_000_000  # file > 2 MB coi như không quét (log, pack bản đồ)


@dataclass(frozen=True)
class PhatHien:
    """Một nghi vấn: quy tắc nào, ở đâu, dài bao nhiêu. Không giữ giá trị bí mật."""

    quy_tac: str
    mo_ta: str
    noi_dung: str
    do_dai: int
    doan_dau: str


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
    for quy_tac, mo_ta, mau in LUAT:
        for canh in mau.finditer(noi_dung):
            gia_tri = canh.group(1) if canh.groups() else canh.group(0)
            if gia_tri in GIA_TRI_MAU:
                continue
            ra.append(
                PhatHien(
                    quy_tac=quy_tac,
                    mo_ta=mo_ta,
                    noi_dung=f"{ten}:{noi_dung.count(chr(10), 0, canh.start()) + 1}",
                    do_dai=len(gia_tri),
                    doan_dau=gia_tri[:4],
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
    """Chỉ quét file git theo dõi — file trong `node_modules` hay build tạm không
    phải thứ sẽ bị đẩy lên, quét chúng chỉ làm chậm và gây báo động."""
    danh_sach = _git(goc, "ls-files").splitlines()
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Quét bí mật rò rỉ trong repo.")
    ap.add_argument("--goc", type=Path, default=GOC_MAC_DINH, help="thư mục gốc repo")
    ap.add_argument("--lich-su", action="store_true", help="quét cả lịch sử commit (chậm)")
    args = ap.parse_args(argv)

    goc: Path = args.goc.resolve()
    phat_hien = quet_file_dang_track(goc)
    if args.lich_su:
        phat_hien += quet_lich_su(goc)

    print(f"=== Quét bí mật (SEC-005): {goc} ===")
    print(f"Quét {len(_git(goc, 'ls-files').splitlines())} file được theo dõi"
          f"{' + lịch sử commit' if args.lich_su else ''}.")
    if phat_hien:
        print("!!! FAIL: có nghi vấn bí mật — giá trị bị che, sửa trước khi commit:")
        print(bao_cao(phat_hien))
        return 1
    print(bao_cao(phat_hien))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())