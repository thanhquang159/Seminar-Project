"""SEC-007 (OWN-005) — XSS từ nội dung chủ quán gửi lên.

Kịch bản tấn công: chủ quán đăng ký (hoặc tự nhận là chủ quán rồi gửi tên quán /
mô tả) chứa `<img src=x onerror=...>` hoặc `<script>`. Nếu nội dung đó được
đưa vào HTML thô ở bất kỳ tầng nào, kẻ tấn công chạy được mã trong trình duyệt
của khách — và với khách khác nếu admin duyệt rồi hiển thị (stored XSS).

Sự thật đã kiểm tra trong repo này:
- Backend KHÔNG sinh HTML ở đâu cả (grep `text/html`, `HTMLResponse`, `<script`).
- Frontend không có `dangerouslySetInnerHTML`, `innerHTML`, `setHTML`, `eval`,
  và không render URL động vào `href`/`src` (nên `javascript:` không có chỗ đứng).
- Chủ quán nhập tên/mô tả qua `<input>` → React giữ nguyên chuỗi → render bằng
  `{dangChon.description}` nên React escape.
- Vì vậy vá ở đây không phải "thêm sanitize": đó là vá mở đường cho dữ liệu
  không đáng tin đi vào HTML thô, chưa xảy ra. Việc đáng làm là **giữ cho nó không
  xảy ra được** và có máy canh, vì "React escape sẵn" là giả định vô hình.

Ba lớp giữ:
1. `frontend/eslint.config.js` cấm `dangerouslySetInnerHTML`, `innerHTML`,
   `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, `new Function`.
2. `frontend/src/components/PoiList.test.tsx` render thật với nội dung độc và
   đọc DOM thật: không có phần tử `<script>`/`<img>` sinh ra ra.
3. Các test dưới đây canh chỗ cấu hình và chỗ render không bị xoá lặng lẽ.

Quyết định có ý thức: KHÔNG sanitize/strip ở tầng lưu trữ. Strip sẽ hỏng
tìm kiếm sau này và tạo cảm giác an toàn giả (dữ liệu cũ đã lọt vẫn còn nguyên),
trong khi chỗ duy nhất nguy hiểm là chỗ hiển thị — và chỗ đó đã escape.
"""

from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
APP = GOC / "backend" / "app"
FE = GOC / "frontend"


def _tinh_lan(*mau: str) -> list[tuple[Path, int, str]]:
    ra: list[tuple[Path, int, str]] = []
    for tep in sorted(APP.rglob("*.py")):
        for so, dong in enumerate(tep.read_text(encoding="utf-8").splitlines(), start=1):
            for m in mau:
                if m in dong:
                    ra.append((tep, so, m))
    return ra


# --- tầng backend: không được sinh HTML ra từ dữ liệu ------------------------------


def test_backend_khong_sinh_html() -> None:
    """Backend trả JSON và file tĩnh, không trả trang HTML có dữ liệu người dùng."""
    nghi_van = _tinh_lan("text/html", "HTMLResponse", "<script", "jinja2", "Template(")
    assert nghi_van == [], f"backend không được dựng HTML: {nghi_van}"


def test_backend_khong_noi_html_vao_dom() -> None:
    assert _tinh_lan("innerHTML", "outerHTML", "document.write") == []


def test_ten_quan_va_mo_ta_duoc_giu_nguyen() -> None:
    """Tầng lưu trữ không sửa dữ liệu người dùng — có ý thức, xem docstring."""
    from app.routers.owner import SubmissionNhap

    rau = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
    ban = SubmissionNhap(name=rau, description=f"Mô tả {rau}", lat=10.7569, lng=106.7641)
    assert ban.name == rau
    assert rau in ban.description


# --- tầng frontend: cấu hình lint + test render ------------------------------------


def test_eslint_cam_mo_cua_so_html() -> None:
    cfg = (FE / "eslint.config.js").read_text(encoding="utf-8")
    assert "no-restricted-syntax" in cfg
    for mau in (
        'JSXAttribute[name.name="dangerouslySetInnerHTML"]',
        "(inner|outer)HTML",
        'callee.property.name="insertAdjacentHTML"',
        "callee.property.name='write'",
        'callee.name="eval"',
        "callee.callee.name='Function'",
    ):
        assert mau in cfg, f"eslint.config.js mất cấm `{mau}`"


def test_van_co_test_chung_minh_escape() -> None:
    tep = FE / "src" / "components" / "PoiList.test.tsx"
    assert tep.exists(), "mất file test chứng minh React escape nội dung owner"
    chuoi = tep.read_text(encoding="utf-8")
    assert "querySelector('script')" in chuoi


def test_ten_va_mo_ta_duoc_render_bang_text_node() -> None:
    """Hai chỗ duy nhất hiển thị nội dung chủ quán phải đặt trong `{...}`."""
    tep = FE / "src" / "components" / "PoiList.tsx"
    chuoi = tep.read_text(encoding="utf-8")
    assert "{poi.name}" in chuoi and "{poi.description}" in chuoi
    assert "dangerouslySetInnerHTML" not in chuoi


def test_khong_render_duong_dan_dong_vao_href() -> None:
    """`javascript:` chỉ nguy hiểm khi đi vào href/src — không có chỗ đứng là an toàn."""
    nghi_van: list[str] = []
    for tep in sorted(FE.joinpath("src").rglob("*.ts*")):
        if ".test." in tep.name:
            continue
        for so, dong in enumerate(tep.read_text(encoding="utf-8").splitlines(), start=1):
            if "href={" in dong or "src={" in dong or "javascript:" in dong:
                nghi_van.append(f"{tep.relative_to(GOC)}:{so} {dong.strip()}")
    assert nghi_van == [], nghi_van