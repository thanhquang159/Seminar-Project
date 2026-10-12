"""SEC-005 — quản lý bí mật: không có bí mật thật trong repo và trong lịch sử.

Kẻ tấn công ở đây không cần vào hệ thống. Chỉ cần một trình quét trên
GitHub, một lần tìm kiếm Google cho `key=...` trong các file công khai là ra
key MapTiler, token, mật khẩu. Key MapTiler mà không giới hạn domain còn tệ
hơn: kẻ tấn công dùng nó đắp đáy bản đồ tính phí của bạn, tới khi tài khoản bị
khoá.

Cách rò rỉ phổ biến nhất không phải hacker mà là **sự cẩu thả**: dán key vào
`.env` rồi lỡ `git add .`. Task này dựng `scripts/audit_secrets.py` để cái đó
bị chặn tự động mỗi lần chạy `scripts/verify.py`, và kiểm cả lịch sử commit —
vì xoá file ở commit sau **không** gỡ được bí mật khỏi lịch sử, ai clone repo
cũng đọc được.

Test dưới đây vừa kiểm máy quét có bắt được không (cắm bí mật thật vào rồi
xem nó có kêu không), vừa kiểm repo hiện tại có sạch không.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[2]


def _nap_bo_quet():
    """Nạp `scripts/audit_secrets.py` như module để test dùng được hàm của nó."""
    duong_dan = GOC / "scripts" / "audit_secrets.py"
    spec = importlib.util.spec_from_file_location("audit_secrets", duong_dan)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclass trong script cần tên module trong sys.modules để tra cứu; thiếu
    # bước này thì `@dataclass` ném AttributeError lúc import.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _nap_bo_quet()

BI_MAT_THAT = [
    ("maptiler", 'STYLE="https://api.maptiler.com/maps/streets-v2/style.json?key=Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVw"'),
    ("jwt", 'token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.9dQxKZ0mT3sVb7nLpQ1rXyE"'),
    ("aws", 'aws_key = "AKIAIOSFODNN7EXAMPLE"'),
    ("google", 'GAPI = "AIzaSyD-1234567890abcdefghijklmnopqrstu"'),
    ("openai", 'AI_API_KEY="sk-abcdefghijklmnopqrstuvwxyz123456"'),
    ("github", 'gh_token="ghp_abcdefghijklmnopqrstuvwxyz0123456789"'),
    ("slack", 'SLACK="xoxb-123456789012-1234567890123-AbCdEfGhIjKlMnOp"'),
    ("khoa-rieng-tu", '-----BEGIN RSA PRIVATE KEY-----\nMIIEow==\n-----END RSA PRIVATE KEY-----'),
    ("gan-bien", 'JWT_SECRET = "9fKq2xWv7bNm3ZpL8sTdR4yH1cJ6gF0eA"'),
]


# --- máy quét có bắt được không ----------------------------------------------


@pytest.mark.parametrize(("quy_tac", "mau_bi_mat"), BI_MAT_THAT)
def test_bam_bi_mat_that_thi_bi_bao(quy_tac: str, mau_bi_mat: str) -> None:
    hit = audit.quet_noi_dung("t.csv", mau_bi_mat)
    assert quy_tac in {p.quy_tac for p in hit}, f"cắm '{quy_tac}' mà không bị báo"


@pytest.mark.parametrize(
    "mau_sach",
    [
        "JWT_SECRET=",  # .env.example để trống
        "REFRESH_TOKEN_SECRET=\nJWT_SECRET=\nPII_KEY=",  # rỗng không được "ăn" dòng dưới
        "VITE_MAPTILER_KEY=",
        'jwt_secret: str = "dev-access-secret-doi-khi-deploy"',
        '{"username": "admin", "password_hash": bam_mat_khau("admin123")}',
        "admin_password=admin123",
    ],
)
def test_mau_rong_va_fixture_khong_bi_bao(mau_sach: str) -> None:
    """Báo động giả thì công cụ bị tắt trong một tuần là xong. Giá trị rỗng,
    giá trị mẫu và fixture test phải sạch."""
    assert audit.quet_noi_dung("t.txt", mau_sach) == []


def test_bao_cao_khong_in_ra_ban_ro_bi_mat() -> None:
    """Công cụ quét bí mật mà in nguyên bí mật vào log CI là tự rò lần hai."""
    mau = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    bao_cao = audit.bao_cao(audit.quet_noi_dung("t.txt", mau))
    assert mau not in bao_cao
    assert "ghp_"[:4] in bao_cao  # vẫn đủ để tìm


def test_xoa_file_roi_bi_mat_van_con_trong_lich_su(tmp_path: Path) -> None:
    """Tình huống quan trọng nhất: key bị commit lỡ rồi xoá file. Repo hiện tại
    sạch, nhưng lịch sử thì không — ai clone repo cũng đọc được key."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    (repo / ".env").write_text('MAPTILER_KEY="Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVw"\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "lỡ tay commit .env")
    (repo / ".env").unlink()  # xoá file ở commit sau
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "xoá .env, tưởng xong")

    assert audit.quet_file_dang_track(repo) == []  # cây hiện tại sạch
    assert audit.quet_lich_su(repo), "lịch sử phải vẫn còn dấu vết"


# --- repo thật có sạch không -------------------------------------------------


def test_toan_bo_repo_va_lich_su_khong_co_bi_mat() -> None:
    """Chạy đúng lệnh người vận hành sẽ chạy, trên chính repo này."""
    assert audit.main(["--goc", str(GOC), "--lich-su"]) == 0


def test_quet_file_da_bi_bo_qua_thu_muc_rac() -> None:
    assert audit.quet_file(GOC / "frontend" / "node_modules" / "x" / ".env", GOC) == []


# --- ngăn tái phạm -----------------------------------------------------------


def test_gitignore_che_khoa_rieng_tu() -> None:
    """.env đã được che; khoá riêng tư `.pem`/`.key` thì chưa — thêm vào."""
    noi_dung = (GOC / ".gitignore").read_text(encoding="utf-8")
    for dong in (".env", "*.pem", "*.key", "*.p12", "*.pfx", "secrets/"):
        assert dong in noi_dung, f".gitignore thiếu {dong}"


def test_verify_chay_buoc_quet_bi_mat() -> None:
    """Máy quét không được đứng rời: phải chạy trong `scripts/verify.py`,
    nếu không thì một ngày nào đó sẽ ai cũng quên chạy."""
    noi_dung = (GOC / "scripts" / "verify.py").read_text(encoding="utf-8")
    assert "audit_secrets" in noi_dung


def test_env_frontend_nhac_vi_tri_phia_client() -> None:
    """Mọi biến `VITE_*` đều nằm trong bundle gửi cho trình duyệt — không có
    bí mật nào ở đó được. `.env.example` phải nói rõ và chỉ đường giới hạn
    key theo domain."""
    noi_dung = (GOC / "frontend" / ".env.example").read_text(encoding="utf-8")
    assert "VITE_" in noi_dung
    assert "domain" in noi_dung.lower()


def _git(repo: Path, *args: str) -> None:
    ket = subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True)
    assert ket.returncode == 0, ket.stderr