"""SEC-004 — chặn thao tác ghi đến từ origin không khai báo.

Cookie phiên đã đặt `SameSite=lax`, và trình duyệt sẽ không gửi cookie khi
trang gọi chéo miền bằng `fetch`. Nhưng lớp đó **không đủ** ở hai tình huống:

- trình duyệt cũ hoặc cấu hình sai làm cookie trở thành `SameSite=None`;
- khi deploy thật, frontend và API cùng nằm trên một site (`app.amds.vn` và
  `api.amds.vn`): chúng khác *origin* nhưng **cùng site**, nên SameSite vẫn
  gửi kèm cookie.

Vì vậy thêm một lớp ở server: mọi thao tác ghi phải đến từ origin đã khai báo.
Cách này không phụ thuộc trình duyệt, chỉ cần trình duyệt gửi header `Origin` —
mà mọi lệnh `fetch`/`POST` từ JS đều gửi (kể cả `Origin: null` khi trang nằm
trong iframe sandbox).

Ranh giới có ý thức: yêu cầu **không** kèm `Origin` thì cho qua. Đó là curl,
script, test — không phải trình duyệt thì không dính CSRF, và vẫn phải có token
hợp lệ. Chặn luôn sẽ làm hỏng mọi script gọi API mà không thêm gì về an toàn.
Đổi lại, CORS (`app/main.py`) lo phần *đọc*: origin lạ vẫn gọi được, nhưng
trình duyệt không bàn giao phản hồi cho script.
"""

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings

METHOD_GHI = frozenset({"POST", "PUT", "PATCH", "DELETE"})
THONG_BAO = "Origin của trang không được phép thao tác ghi trên API này"


def _origin(scope: Scope) -> str | None:
    for ten, gia_tri in scope.get("headers") or ():
        if ten == b"origin":
            return gia_tri.decode("latin-1").strip()
    return None


class ChanGhiOrigin:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] == "http" and scope.get("method") in METHOD_GHI:
            origin = _origin(scope)
            if origin and origin not in settings.cors_origins:
                await JSONResponse({"detail": THONG_BAO}, status_code=403)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)