"""Header bảo mật (PROD-007).

Mỗi header chặn một kiểu tấn công khác nhau; thiếu header không tự mở lỗ hổng,
nhưng để trình duyệt phải tự đoán:

- `X-Content-Type-Options: nosniff` — chặn việc trình duyệt tự đoán kiểu nội
  dung. Không có nó thì file JSON/ảnh tải lên có thể bị hiểu là HTML+script.
- `X-Frame-Options: DENY` — chặn nhúng trang vào iframe để dựng trang giả mạo
  khi bấm vào (clickjacking), chẳng hạn một overlay trong suốt phủ lên nút
  "duyệt đơn chủ quán".
- `Referrer-Policy` — URL của app có `?poi_id=…` và `?anonymous_id=…`; không
  muốn chúng chảy sang website khác.
- `Content-Security-Policy` — chặn tải và chạy mã từ nơi lạ. Đây là biện pháp
  **bổ sung** cho SEC-007 (chặn XSS), không thay thế: nếu có chỗ đưa HTML thô
  vào DOM thì CSP là lưới an toàn cuối.
- `Strict-Transport-Security` — chỉ bật ngoài dev. Bật cả ở localhost thì
  trình duyệt ghim `127.0.0.1` sang HTTPS vĩnh viễn và mọi lần chạy thử sau
  đó đều hỏng — nên cố ý bỏ qua ở dev.

CSP ở đây được viết khít theo những gì app thật sự cần (đọc từ mã nguồn, không
phải bản mẫu chung trên mạng):
- `script-src 'self'` — Vite xuất bundle tĩnh, không có script inline.
- `worker-src blob:` — MapLibre nạp tile qua Web Worker.
- `style-src 'self' 'unsafe-inline'` — React đặt style cục bộ (geofence).
- `img-src` — ảnh tile MapTiler hoặc OpenFreeMap.
- `connect-src` — API + style bản đồ cloud; danh sách suy ra từ
  `settings.CORS_ORIGINS` để không trở thành chỗ cấu hình trôi lệch nhau lần
  thứ ba (lần trước là analytics, lần trước nữa là CORS).
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Những nơi app thật sự gọi ra ngoài, ngoài API của chính nó.
GOC_NOI_DUNG = "'self'"
API_MAC_DINH = "http://127.0.0.1:8000 http://localhost:8000"


class HeaderBaoMat:
    """Gắn header lên mọi response, kể cả 4xx/5xx và response của static."""

    def __init__(self, app: ASGIApp, connect_src: str | None = None) -> None:
        self.app = app
        self.connect_src = connect_src or API_MAC_DINH
        self.csp = "; ".join(
            [
                "default-src 'self'",
                f"script-src {GOC_NOI_DUNG}",
                "worker-src 'self' blob:",
                # React đặt style cục bộ (vòng tròn, thanh tiến trình) — không
                # có cách nào tránh inline style trong JSX.
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: blob: https://*.maptiler.com https://tiles.openfreemap.org",
                f"connect-src {self.connect_src} https://*.maptiler.com https://demotiles.maplibre.org https://tiles.openfreemap.org",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        # Chỉ bật HSTS ngoài dev: bật cả ở localhost sẽ hỏng vĩnh viễn mọi
        # lần chạy thử sau (xem docstring).
        tu_khoa = scope.get("headers", [])
        la_https = any(k == b"x-forwarded-proto" and v == b"https" for k, v in tu_khoa)

        async def gui_phan_hoi(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                co = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"strict-origin-when-cross-origin",
                    b"permissions-policy": b"geolocation=(self), microphone=()",
                    b"content-security-policy": self.csp.encode(),
                }
                if la_https or not _la_dev():
                    co[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                for khoa, gia_tri in co.items():
                    if not any(k == khoa for k, _ in headers):
                        headers.append((khoa, gia_tri))
            await send(message)

        await self.app(scope, receive, gui_phan_hoi)


def _la_dev() -> bool:
    from app.core.config import la_dev

    return la_dev()
