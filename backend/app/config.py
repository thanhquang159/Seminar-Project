"""Cấu hình ứng dụng đọc từ biến môi trường và tệp .env.

Mọi thông số thay theo môi trường (dev, staging, production) nằm ở đây,
code nghiệp vụ chỉ đọc qua `settings`, không gọi `os.getenv` rải rác.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Origin hợp lệ = scheme + host + port. Không đường dẫn, không dấu `/` cuối,
# không ký tự đại diện — vì Origin do trình duyệt gửi có đúng những phần đó.
MAU_ORIGIN = r"https?://[A-Za-z0-9.\-]+(:[0-9]{1,5})?"


class Settings(BaseSettings):
    """Thông số Phase 0-4: MongoDB, môi trường, bí mật JWT, seed admin."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "amds"
    # Môi trường chạy: dev thì nới lỏng (cookie không Secure, secret mặc định).
    app_env: str = "dev"
    jwt_secret: str = "dev-access-secret-doi-khi-deploy"
    refresh_secret: str = "dev-refresh-secret-doi-khi-deploy"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    redis_url: str = "redis://localhost:6379"
    # Fernet mã hóa PII, AI provider: mock cho dev, proxypal/gemini khi có key.
    pii_key: str = ""
    ai_provider: str = "mock"
    ai_api_key: str = ""
    ai_api_url: str = ""
    # SEC-003: origin được phép gọi API (và gửi analytics — cùng một danh sách).
    # Rỗng nghĩa là chỉ nhận request không kèm Origin: curl, script, test.
    cors_origins: list[str] = [
        "http://localhost:5173",  # `npm run dev`
        "http://127.0.0.1:5173",  # frontend gọi 127.0.0.1 nên origin cũng vậy
        "http://localhost:4173",  # `npm run preview` — PWA chỉ thử trên bản build
        "http://127.0.0.1:4173",
    ]

    @field_validator("cors_origins")
    @classmethod
    def kiem_tra_origin(cls, v: list[str]) -> list[str]:
        """Chặn origin sai dạng lúc khởi động, không đợi tới lúc gặp lỗi CORS.

        `*` là lỗi cấu hình chứ không phải lựa chọn: API chạy cookie httpOnly
        (`credentials: include`) nên `*` bị trình duyệt bỏ qua, còn nếu ai đó
        "sửa cho chạy được" bằng cách liệt kê domain rộng thì trang kẻ tấn công
        đọc được dữ liệu. Origin sai dạng (thừa `/`, kèm đường dẫn, thiếu
        scheme) sẽ **không bao giờ khớp** — lỗi khó chẩn đoán nhất, nên chặn
        sớm và báo rõ.
        """
        import re

        sach: list[str] = []
        for o in v:
            o = o.strip()
            if "*" in o or not o or re.fullmatch(MAU_ORIGIN, o) is None:
                raise ValueError(
                    f"CORS_ORIGINS={o!r} không phải origin hợp lệ. Cần dạng "
                    "'scheme://host[:port]' với http/https, không đường dẫn, "
                    "không dấu '/' cuối. Không dùng '*': API chạy cookie nên "
                    "'*' vô hiệu và là lỗ hổng đọc dữ liệu."
                )
            if o not in sach:
                sach.append(o)
        return sach


settings = Settings()


def la_dev() -> bool:
    """Chạy local thì nới lỏng Secure cookie và secret mặc định."""
    return settings.app_env == "dev"


def kiem_tra_bi_mat() -> None:
    """Fail-fast: ngoài dev mà thiếu secret thì từ chối khởi động."""
    if la_dev():
        return
    thieu = [
        ten
        for ten, gia_tri in (
            ("JWT_SECRET", settings.jwt_secret),
            ("REFRESH_TOKEN_SECRET", settings.refresh_secret),
        )
        if gia_tri == ""
    ]
    if thieu:
        raise RuntimeError(f"Thiếu biến môi trường bắt buộc: {', '.join(thieu)}")
