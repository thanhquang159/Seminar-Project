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
    ("maptiler", 'STYLE="https://api.maptiler.com/maps/streets-v2/style.json?key=Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVw"'),  # audit_secrets: allow
    ("jwt", 'token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.9dQxKZ0mT3sVb7nLpQ1rXyE"'),  # audit_secrets: allow
    ("aws", 'aws_key = "AKIAIOSFODNN7EXAMPLE"'),  # audit_secrets: allow
    ("google", 'GAPI = "AIzaSyD-1234567890abcdefghijklmnopqrstu"'),  # audit_secrets: allow
    ("openai", 'AI_API_KEY="sk-abcdefghijklmnopqrstuvwxyz123456"'),  # audit_secrets: allow
    ("github", 'gh_token="ghp_abcdefghijklmnopqrstuvwxyz0123456789"'),  # audit_secrets: allow
    ("slack", 'SLACK="xoxb-123456789012-1234567890123-AbCdEfGhIjKlMnOp"'),  # audit_secrets: allow
    ("khoa-rieng-tu", '-----BEGIN RSA PRIVATE KEY-----\nMIIEow==\n-----END RSA PRIVATE KEY-----'),  # audit_secrets: allow
    ("gan-bien", 'JWT_SECRET = "9fKq2xWv7bNm3ZpL8sTdR4yH1cJ6gF0eA"'),  # audit_secrets: allow
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
    mau = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"  # audit_secrets: allow
    bao_cao = audit.bao_cao(audit.quet_noi_dung("t.txt", mau))
    assert mau not in bao_cao
    assert "ghp_"[:4] in bao_cao  # vẫn đủ để tìm


def test_xoa_file_roi_bi_mat_van_con_trong_lich_su(tmp_path: Path) -> None:
    """Tình huống quan trọng nhất: key bị commit lỡ rồi xoá file. Repo hiện tại
    sạch, nhưng lịch sử thì không — ai clone repo cũng đọc được key."""
    repo = tmp_path / "repo"
    repo = tmp_repo(tmp_path / "repo")
    (repo / ".gitkeep").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "khung")
    (repo / ".env").write_text('MAPTILER_KEY="Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVw"\n', encoding="utf-8")  # audit_secrets: allow
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


def test_dau_cho_phep_bi_mat_gia() -> None:
    """Bỏ qua theo **dòng** bằng dấu tường minh — cần vì chính file test của máy
    quét buộc phải chứa mẫu giả, mà bỏ qua cả thư mục test thì lỡ tay lỡ key
    vào đó là không ai thấy."""
    dong_co_dau = f'MAPTILER_KEY="Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVw"  # {audit.DAU_CHE_PHUONG}'
    assert audit.quet_noi_dung("t.env", dong_co_dau) == []
    assert audit.quet_noi_dung("t.env", 'MAPTILER_KEY="Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVw"')


def test_file_chua_git_add_cung_duoc_quet(tmp_path: Path) -> None:
    """Chỉ quét file đã track thì bí mật trong file mới sẽ lọt tới lúc commit —
    lúc đó nó đã vào lịch sử, mà lịch sử thì không sửa được."""
    repo = tmp_repo(tmp_path / "moi")
    (repo / ".gitkeep").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "khung")
    (repo / "config.env").write_text(
        'MAPTILER_KEY="Ab3dEf9hIj2Kl4Mn6Pq8Rs0TuVw"\n', encoding="utf-8"
    )
    assert audit.quet_file_dang_track(repo)


def test_phat_hien_co_trong_danh_sach_bao_lo_thi_van_do(tmp_path: Path) -> None:
    """Danh sách chấp nhận chỉ có tác dụng với phát hiện đã biết; bí mật mới trong
    lịch sử vẫn phải đỏ. Đây là cơ chế giữ cho `verify.py --lich-su` chạy được mà
    không tắt máy quét."""
    repo = tmp_repo(tmp_path / "lich_su")
    (repo / ".gitkeep").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "khung")
    (repo / ".env").write_text(
        'GITHUB_TOKEN="ghp_zzzz0123456789abcdefghijklmnop"\n'  # audit_secrets: allow
        , encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "lỡ")
    _git(repo, "rm", "-q", ".env")
    _git(repo, "commit", "-q", "-m", "xoá")

    assert audit.main(["--goc", str(repo), "--lich-su"]) == 1, "bí mật mới phải làm đỏ"
    vt = audit.quet_lich_su(repo)
    # Cùng một token bị nhiều luật bắt và xuất hiện ở nhiều dòng lịch sử: điều ta
    # cần kiểm là "có tìm thấy", không phải "đúng bằng 1 phát hiện".
    assert vt and {p.quy_tac for p in vt} <= {"github", "khoa-moi-truong"}
    assert audit.main(["--goc", str(repo), "--lich-su", "--cap-nhat-danh-sach-chap-nhan"]) == 0
    assert audit.main(["--goc", str(repo), "--lich-su"]) == 0, "có trong danh sách thì bỏ qua"


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


def tmp_repo(duong_dan: Path) -> Path:
    """Repo git tạm đủ dùng (không cần remote, không cần mạng)."""
    repo = duong_dan / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    return repo


def _git(repo: Path, *args: str) -> None:
    ket = subprocess.run(["git", *args], cwd=repo, check=False, capture_output=True)
    assert ket.returncode == 0, ket.stderr
