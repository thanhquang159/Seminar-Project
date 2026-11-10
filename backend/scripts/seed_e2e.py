"""Reset and seed the dedicated PostgreSQL database used by Playwright."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import bam_mat_khau
from app.core.config import settings
from app.postgres import AsyncSessionLocal, close_db

ADMIN_E2E = "e2e-admin"
MAT_KHAU_E2E = "e2e123456"

POIS_E2E = [
    ("Bánh mì chảo Vĩnh Khánh", 10.7569, 106.7641),
    ("Ốc đêm Đào Vĩnh Khánh", 10.7590, 106.7650),
    ("Bún bò Gánh Cỏ Ởng", 10.7580, 106.7625),
    ("Cà phê sữa đá đường Lê Thánh Tôn", 10.7770, 106.7030),
    ("Cơm tấm Ba Ghiền", 10.7740, 106.7060),
]

BAN_DICH = {
    "vi": ("Bánh mì chảo pate trứng ốp la.", "Món ăn sáng nổi tiếng Vĩnh Khánh."),
    "en": ("Paté bread roll with fried egg.", "A famous breakfast in Vinh Khanh."),
    "zh": ("法式面包配煎蛋。", "滨贤著名的早餐。"),
}

_RESET_TABLES = """
    ai_advisor_requests, ai_usage_daily, analytics_consents, analytics_events,
    audio_tasks, audit_logs, auth_sessions, content_dataset_pois,
    content_dataset_versions, localization_request_logs, menu_items, menus,
    offline_pack_assets, offline_packs, owner_notifications,
    owner_registrations, poi_images, poi_localizations, poi_submissions, pois,
    runtime_observability_hourly, user_roles, users
"""


async def main() -> None:
    if not settings.DB_NAME.casefold().endswith("_e2e"):
        raise RuntimeError(
            "Từ chối xóa dữ liệu: DB_NAME phải kết thúc bằng '_e2e'. "
            "Hãy cấu hình một PostgreSQL database E2E riêng."
        )

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text(f"TRUNCATE TABLE {_RESET_TABLES} RESTART IDENTITY CASCADE"))

            role_id = await db.scalar(
                text("SELECT id FROM roles WHERE upper(code) = 'ADMIN' LIMIT 1")
            )
            if role_id is None:
                raise RuntimeError("PostgreSQL E2E chưa có role ADMIN.")

            admin_id = await db.scalar(
                text(
                    """
                    INSERT INTO users (email, password_hash, full_name, account_status)
                    VALUES (:email, :password_hash, :full_name, 'active')
                    RETURNING id
                    """
                ),
                {
                    "email": ADMIN_E2E,
                    "password_hash": bam_mat_khau(MAT_KHAU_E2E),
                    "full_name": ADMIN_E2E,
                },
            )
            await db.execute(
                text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
                {"user_id": admin_id, "role_id": role_id},
            )

            for index, (name, lat, lng) in enumerate(POIS_E2E):
                poi_id = await db.scalar(
                    text(
                        """
                        INSERT INTO pois (
                            name, description, category, address_line, latitude, longitude,
                            trigger_radius_m, audio_priority, publication_status, is_active,
                            created_by, updated_by, updated_at
                        )
                        VALUES (
                            :name, :description, 'other', '', :lat, :lng,
                            30, :audio_priority, 'published', TRUE,
                            :admin_id, :admin_id, now()
                        )
                        RETURNING id
                        """
                    ),
                    {
                        "name": name,
                        "description": BAN_DICH["vi"][0],
                        "lat": lat,
                        "lng": lng,
                        "audio_priority": index,
                        "admin_id": admin_id,
                    },
                )
                for language, (description, translated_name) in BAN_DICH.items():
                    await db.execute(
                        text(
                            """
                            INSERT INTO poi_localizations (
                                poi_id, language_code, localized_name, localized_description,
                                is_source_language, readiness_status, audio_status, updated_at
                            )
                            VALUES (
                                :poi_id, :language, :name, :description,
                                :is_source, 'published', 'ready', now()
                            )
                            """
                        ),
                        {
                            "poi_id": poi_id,
                            "language": language,
                            "name": name if language == "vi" else translated_name,
                            "description": description,
                            "is_source": language == "vi",
                        },
                    )

            await db.commit()
        print(f"[seed-e2e] Đã tạo {len(POIS_E2E)} POI và tài khoản '{ADMIN_E2E}'.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
