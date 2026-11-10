"""Tạo tài khoản quản trị đầu tiên trong PostgreSQL, chạy lại không đổi mật khẩu."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import bam_mat_khau
from app.core.config import settings
from app.postgres import AsyncSessionLocal, close_db


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db:
            role_id = await db.scalar(
                text("SELECT id FROM roles WHERE upper(code) = 'ADMIN' LIMIT 1")
            )
            if role_id is None:
                raise RuntimeError("PostgreSQL chưa có role ADMIN; kiểm tra schema/role seed.")

            user_id = await db.scalar(
                text("SELECT id FROM users WHERE lower(email) = lower(:email) LIMIT 1"),
                {"email": settings.ADMIN_USERNAME},
            )
            created = user_id is None
            if created:
                user_id = await db.scalar(
                    text(
                        """
                        INSERT INTO users (email, password_hash, full_name, account_status)
                        VALUES (:email, :password_hash, :full_name, 'active')
                        RETURNING id
                        """
                    ),
                    {
                        "email": settings.ADMIN_USERNAME,
                        "password_hash": bam_mat_khau(settings.ADMIN_PASSWORD),
                        "full_name": settings.ADMIN_USERNAME,
                    },
                )

            await db.execute(
                text(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    VALUES (:user_id, :role_id)
                    ON CONFLICT (user_id, role_id) DO NOTHING
                    """
                ),
                {"user_id": user_id, "role_id": role_id},
            )
            await db.commit()

        if created:
            print("Created PostgreSQL admin user.")
        else:
            print("Admin user already exists; password left unchanged.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
