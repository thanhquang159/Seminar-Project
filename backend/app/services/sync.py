"""Cursor đồng bộ POI được cấp phát trong transaction PostgreSQL."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lay_phien_ban(db: AsyncSession) -> int:
    """Đọc cursor bền vững, đơn điệu từ bảng trạng thái đồng bộ."""
    result = await db.execute(
        text(
            """
            SELECT last_cursor
            FROM poi_sync_state
            WHERE singleton IS TRUE
            """
        )
    )
    return int(result.scalar_one())


async def cham_dataset(db: AsyncSession) -> int:
    """Trả cursor sau khi trigger ghi nhận thay đổi POI trong transaction."""
    return await lay_phien_ban(db)


def etag_cho(version: int, lang: str) -> str:
    """Dấu vân tay dữ liệu theo cursor và ngôn ngữ."""
    return f'"{version}-{lang}"'
