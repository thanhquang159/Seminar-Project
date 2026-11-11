import asyncio

from app.limits import GioiHanBody


def test_gioi_han_body_chuyen_tiep_disconnect_sau_khi_phat_lai() -> None:
    messages = iter(
        [
            {"type": "http.request", "body": b"", "more_body": False},
            {"type": "http.disconnect"},
        ]
    )
    so_lan_nhan = 0

    async def receive():
        nonlocal so_lan_nhan
        so_lan_nhan += 1
        return next(messages)

    async def send(_message):
        pass

    async def app(_scope, app_receive, _send):
        assert await app_receive() == {"type": "http.request", "body": b"", "more_body": False}
        assert await app_receive() == {"type": "http.disconnect"}

    scope = {"type": "http", "method": "GET", "path": "/static/audio/test.mp3", "headers": []}
    asyncio.run(GioiHanBody(app)(scope, receive, send))

    assert so_lan_nhan == 2
