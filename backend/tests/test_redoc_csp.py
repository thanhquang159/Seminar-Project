import asyncio

import app.headers as headers


def _csp_for_path(path: str, monkeypatch) -> str:
    monkeypatch.setattr(headers, "_la_dev", lambda: True)
    messages = []

    async def app(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "path": path, "headers": []}
    asyncio.run(headers.HeaderBaoMat(app)(scope, receive, send))
    response_headers = dict(messages[0]["headers"])
    return response_headers[b"content-security-policy"].decode()


def test_redoc_csp_allows_its_external_bundle(monkeypatch) -> None:
    csp = _csp_for_path("/redoc", monkeypatch)

    assert "script-src 'self' https://cdn.jsdelivr.net" in csp


def test_swagger_docs_csp_allows_ui_assets_and_initialization(monkeypatch) -> None:
    csp = _csp_for_path("/docs", monkeypatch)

    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
    assert "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp


def test_other_paths_do_not_allow_external_scripts(monkeypatch) -> None:
    csp = _csp_for_path("/api/v1/health", monkeypatch)

    assert "script-src 'self';" in csp
    assert "cdn.jsdelivr.net" not in csp
    assert "'unsafe-inline'" not in csp.split("script-src ", 1)[1].split(";", 1)[0]
