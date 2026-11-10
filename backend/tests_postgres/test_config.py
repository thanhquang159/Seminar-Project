import pytest

from app.core.config import Settings, kiem_tra_bi_mat, settings


def test_production_rejects_default_development_token_secrets(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "JWT_SECRET", "dev-access-secret-doi-khi-deploy")
    monkeypatch.setattr(
        settings,
        "REFRESH_TOKEN_SECRET",
        "dev-refresh-secret-doi-khi-deploy",
    )

    with pytest.raises(RuntimeError, match="JWT_SECRET, REFRESH_TOKEN_SECRET"):
        kiem_tra_bi_mat()


def test_production_accepts_configured_token_secrets(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "JWT_SECRET", "configured-access-secret")
    monkeypatch.setattr(settings, "REFRESH_TOKEN_SECRET", "configured-refresh-secret")

    kiem_tra_bi_mat()


def test_cors_origins_are_validated_and_deduplicated():
    config = Settings(
        _env_file=None,
        DB_PASSWORD="test",
        CORS_ORIGINS=["http://localhost:5173", "http://localhost:5173"],
    )

    assert config.CORS_ORIGINS == ["http://localhost:5173"]


@pytest.mark.parametrize("origin", ["*", "http://localhost:5173/path", "localhost:5173"])
def test_cors_rejects_wildcard_and_invalid_origins(origin):
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        Settings(_env_file=None, DB_PASSWORD="test", CORS_ORIGINS=[origin])
