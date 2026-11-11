import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "quan4_culinary_tourism"
    DB_USER: str = "quan4_app"
    DB_PASSWORD: str

    APP_NAME: str = "Quan4 Culinary Tourism API"
    APP_DEBUG: bool = True
    APP_ENV: str = "dev"
    JWT_SECRET: str = "dev-access-secret-doi-khi-deploy"
    REFRESH_TOKEN_SECRET: str = "dev-refresh-secret-doi-khi-deploy"
    FRONTEND_URL: str = "http://localhost:5173"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    PII_KEY: str = ""
    AI_PROVIDER: str = "mock"
    AI_API_KEY: str = ""
    AI_API_URL: str = ""
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        valid_origins: list[str] = []
        for origin in origins:
            origin = origin.strip()
            if (
                not origin
                or "*" in origin
                or re.fullmatch(r"https?://[A-Za-z0-9.\-]+(:[0-9]{1,5})?", origin) is None
            ):
                raise ValueError(f"Invalid CORS origin: {origin!r}")
            if origin not in valid_origins:
                valid_origins.append(origin)
        return valid_origins


settings = Settings()


def la_dev() -> bool:
    return settings.APP_ENV.lower() == "dev"


def kiem_tra_bi_mat() -> None:
    development_secrets = {
        "dev-access-secret-doi-khi-deploy",
        "dev-refresh-secret-doi-khi-deploy",
    }
    missing = [
        name
        for name, value in (
            ("JWT_SECRET", settings.JWT_SECRET),
            ("REFRESH_TOKEN_SECRET", settings.REFRESH_TOKEN_SECRET),
        )
        if not value or (not la_dev() and value in development_secrets)
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
