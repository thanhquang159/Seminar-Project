
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


DATABASE_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=settings.DB_USER,
    password=settings.DB_PASSWORD,
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    database=settings.DB_NAME,
    query={"ssl": "require"},
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def connect_db() -> None:
    """Kiểm tra kết nối PostgreSQL khi ứng dụng khởi động."""
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    version() AS postgres_version
                """
            )
        )

        db_info = result.mappings().one()

        if db_info["database_name"] != settings.DB_NAME:
            raise RuntimeError(
                f"Connected to database {db_info['database_name']!r}, "
                f"expected {settings.DB_NAME!r}"
            )


async def get_db() -> AsyncIterator[AsyncSession]:
    """Cung cấp database session cho FastAPI endpoint."""
    async with AsyncSessionLocal() as session:
        yield session


async def close_db() -> None:
    """Đóng connection pool khi ứng dụng dừng."""
    await engine.dispose()
