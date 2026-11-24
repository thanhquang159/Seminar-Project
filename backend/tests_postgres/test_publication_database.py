"""Kiểm thử HTTP + PostgreSQL thật; transaction ngoài luôn rollback dữ liệu test."""

import asyncio
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth
from app.api import pois as public_pois
from app.postgres import engine, get_db
from app.routers import admin_pois, localizations, owner
from app.services import audio_svc, tasks


def test_publication_workflow_on_postgres(pytestconfig, monkeypatch):
    if not pytestconfig.getoption("--run-publication-db"):
        pytest.skip("Thêm --run-publication-db để chạy PostgreSQL thật và rollback")

    # Không gửi nội dung đến TTS thật; vẫn dùng toàn bộ SQL lưu bản dịch/audio.
    monkeypatch.setattr(tasks.quan_ly_tasks, "xep_viec", AsyncMock(return_value="test-task"))
    monkeypatch.setattr(localizations, "kiem_tra", AsyncMock())

    async def scenario():
        admin_id, owner_id = uuid4(), uuid4()
        poi_id = None
        engine.echo = False
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                ) as db:
                    for user_id in (admin_id, owner_id):
                        await db.execute(
                            text("""
                            INSERT INTO users (id, email, password_hash, full_name, account_status, owner_verified_at)
                            VALUES (:id, :email, 'unused-test-hash', 'Publication test', 'active', now())
                        """),
                            {"id": user_id, "email": f"publish-test-{user_id}@example.test"},
                        )
                    await db.commit()
                    admin = {
                        "id": str(admin_id),
                        "username": f"publish-test-{admin_id}@example.test",
                        "role": "admin",
                        "permissions": ["poi:approve", "poi:publish", "poi:update", "poi:create"],
                    }
                    customer = {
                        "id": str(owner_id),
                        "username": f"publish-test-{owner_id}@example.test",
                        "role": "poi_owner",
                        "permissions": [],
                    }
                    current_user = customer
                    app = FastAPI()
                    for router in (
                        admin_pois.router,
                        owner.router,
                        localizations.router,
                        public_pois.router,
                    ):
                        app.include_router(router)
                    app.dependency_overrides[get_db] = lambda: db
                    app.dependency_overrides[auth.lay_user_hien_tai] = lambda: current_user
                    app.dependency_overrides[auth.doi_owner_da_duyet] = lambda: current_user

                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        payload = {
                            "name": "Publication test cafe",
                            "description": "Source content",
                            "address_line": "Test address",
                            "lat": 10.7569,
                            "lng": 106.7641,
                        }
                        submitted = await client.post("/owner/submissions", json=payload)
                        assert submitted.status_code == 200, submitted.text
                        sid = submitted.json()["submission_id"]
                        assert (
                            await client.post(f"/owner/submissions/{sid}/approve")
                        ).status_code == 403
                        current_user = admin
                        approved = await client.post(f"/owner/submissions/{sid}/approve")
                        assert approved.status_code == 200, approved.text
                        poi_id = approved.json()["poi_id"]
                        assert (await client.get(f"/poi/{poi_id}")).status_code == 404
                        listed = await client.get("/admin/pois")
                        assert listed.status_code == 200, listed.text
                        record = next(p for p in listed.json() if p["id"] == poi_id)
                        assert record["publication_status"] == "unpublished"
                        assert not record["readiness"]["ready"]
                        denied = await client.post(f"/admin/pois/{poi_id}/publish")
                        assert denied.status_code == 409

                        translated = await client.post(
                            "/localizations/on-demand",
                            json={
                                "poi_id": poi_id,
                                "lang": "en",
                                "name": "English cafe",
                                "description": "English content",
                            },
                        )
                        assert translated.status_code == 200, translated.text
                        assert (
                            await client.post(f"/admin/pois/{poi_id}/publish")
                        ).status_code == 409
                        await audio_svc.hoan_tat_audio(
                            db,
                            UUID(poi_id),
                            "en",
                            "/static/audio/test-en.mp3",
                            expected_text="English content",
                        )
                        # Worker hoàn tất vẫn chưa được tự công khai.
                        assert (await client.get(f"/poi/{poi_id}")).status_code == 404
                        readiness = (await client.get(f"/admin/pois/{poi_id}/readiness")).json()
                        assert readiness["readiness"]["ready"]
                        before_publish = await client.get("/poi/load-all")
                        assert before_publish.status_code == 200, before_publish.text
                        start_cursor = before_publish.json()["sync_cursor"]
                        published = await client.post(f"/admin/pois/{poi_id}/publish")
                        assert published.status_code == 200, published.text
                        assert published.json()["is_active"]
                        visible = await client.get(f"/poi/{poi_id}?lang=en")
                        assert visible.status_code == 200, visible.text
                        assert visible.json()["name"] == "English cafe"
                        assert any(
                            p["id"] == poi_id for p in (await client.get("/poi?lang=en")).json()
                        )
                        published_delta = (
                            await client.get(f"/poi/delta?updated_after={start_cursor}")
                        ).json()
                        assert any(p["id"] == poi_id for p in published_delta["updated"])
                        published_cursor = published_delta["sync_cursor"]
                        assert not (await client.post(f"/admin/pois/{poi_id}/publish")).json()[
                            "changed"
                        ]

                        current_user = customer
                        notifications = (await client.get("/owner/notifications")).json()
                        assert (
                            sum(n["notification_type"] == "poi_published" for n in notifications)
                            == 1
                        )
                        history = (await client.get("/owner/submissions/mine")).json()
                        assert history[0]["poi_id"] == poi_id
                        assert (
                            await client.post(f"/admin/pois/{poi_id}/unpublish")
                        ).status_code == 403
                        current_user = admin
                        unpublished = await client.post(f"/admin/pois/{poi_id}/unpublish")
                        assert unpublished.status_code == 200
                        await audio_svc.hoan_tat_audio(
                            db, UUID(poi_id), "en", "/static/audio/test-en.mp3"
                        )
                        assert (await client.get(f"/poi/{poi_id}")).status_code == 404
                        assert not any(p["id"] == poi_id for p in (await client.get("/poi")).json())
                        hidden_delta = (
                            await client.get(f"/poi/delta?updated_after={published_cursor}")
                        ).json()
                        assert poi_id in hidden_delta["removed_poi_ids"]
                        assert not (await client.post(f"/admin/pois/{poi_id}/unpublish")).json()[
                            "changed"
                        ]

                        # Duyệt cập nhật POI đang công khai phải ẩn và làm mất hiệu lực bản dịch cũ.
                        assert (
                            await client.post(f"/admin/pois/{poi_id}/publish")
                        ).status_code == 200
                        current_user = customer
                        update = await client.post(
                            "/owner/submissions",
                            json={**payload, "poi_id": poi_id, "description": "New source content"},
                        )
                        current_user = admin
                        approved_update = await client.post(
                            f"/owner/submissions/{update.json()['submission_id']}/approve"
                        )
                        assert approved_update.status_code == 200, approved_update.text
                        assert (await client.get(f"/poi/{poi_id}")).status_code == 404
                        assert (
                            await client.post(f"/admin/pois/{poi_id}/publish")
                        ).status_code == 409
                        current_user = customer
                        notifications = (await client.get("/owner/notifications")).json()
                        assert (
                            sum(n["notification_type"] == "poi_unpublished" for n in notifications)
                            == 2
                        )
                        assert any("chưa công khai" in n["message"] for n in notifications)
                        audit = (
                            (
                                await db.execute(
                                    text("SELECT action FROM audit_logs WHERE resource_id = :id"),
                                    {"id": UUID(poi_id)},
                                )
                            )
                            .scalars()
                            .all()
                        )
                        assert "poi:publish" in audit and "poi:unpublish" in audit

                        # Audio của nội dung cũ hoàn tất muộn không được làm bản dịch mới sẵn sàng.
                        current_user = admin
                        assert (
                            await client.post(
                                "/localizations/on-demand",
                                json={
                                    "poi_id": poi_id,
                                    "lang": "en",
                                    "name": "New cafe",
                                    "description": "New English content",
                                },
                            )
                        ).status_code == 200
                        await audio_svc.hoan_tat_audio(
                            db,
                            UUID(poi_id),
                            "en",
                            "/static/audio/old.mp3",
                            expected_text="English content",
                        )
                        assert (
                            await client.post(f"/admin/pois/{poi_id}/publish")
                        ).status_code == 409
                        await audio_svc.hoan_tat_audio(
                            db,
                            UUID(poi_id),
                            "en",
                            "/static/audio/new.mp3",
                            expected_text="New English content",
                        )
                        assert (
                            await client.post(f"/admin/pois/{poi_id}/publish")
                        ).status_code == 200
                        changed_by_admin = await client.put(
                            f"/admin/pois/{poi_id}",
                            json={**payload, "description": "Admin revision"},
                        )
                        assert changed_by_admin.status_code == 200, changed_by_admin.text
                        assert (await client.get(f"/poi/{poi_id}")).status_code == 404
                        assert (
                            await client.post(f"/admin/pois/{poi_id}/publish")
                        ).status_code == 409
            finally:
                await transaction.rollback()
            # Xác nhận dữ liệu tổng hợp thực sự được dọn, kể cả khi route đã gọi commit.
            assert (
                await connection.execute(
                    text("SELECT count(*) FROM users WHERE id IN (:admin, :owner)"),
                    {"admin": admin_id, "owner": owner_id},
                )
            ).scalar_one() == 0
            if poi_id:
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM pois WHERE id = :id"), {"id": UUID(poi_id)}
                    )
                ).scalar_one() == 0
        await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=90))
