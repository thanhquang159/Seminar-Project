"""Xác nhận các role nghiệp vụ đã được provision trong PostgreSQL."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.postgres import AsyncSessionLocal, close_db


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT upper(code) FROM roles WHERE upper(code) IN ('ADMIN', 'OWNER')")
            )
            roles = set(result.scalars().all())
        missing = {"ADMIN", "OWNER"} - roles
        if missing:
            raise RuntimeError("PostgreSQL chưa provision role: " + ", ".join(sorted(missing)))
        print("Verified PostgreSQL roles ADMIN and OWNER; schema unchanged.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
