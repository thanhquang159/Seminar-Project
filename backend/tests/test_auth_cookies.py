from http.cookies import SimpleCookie

from fastapi import Response

import app.routers.admin_auth as admin_auth


def _session_cookie(monkeypatch, *, is_dev: bool) -> SimpleCookie:
    monkeypatch.setattr(admin_auth, "la_dev", lambda: is_dev)
    response = Response()

    admin_auth.dat_cookie(response, "access_token", "test-token", 60)

    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie


def test_development_auth_cookie_uses_lax_without_secure(monkeypatch) -> None:
    cookie = _session_cookie(monkeypatch, is_dev=True)["access_token"]

    assert cookie["samesite"].lower() == "lax"
    assert not cookie["secure"]
    assert cookie["httponly"]


def test_production_auth_cookie_allows_cross_site_credentials_securely(monkeypatch) -> None:
    cookie = _session_cookie(monkeypatch, is_dev=False)["access_token"]

    assert cookie["samesite"].lower() == "none"
    assert cookie["secure"]
    assert cookie["httponly"]
