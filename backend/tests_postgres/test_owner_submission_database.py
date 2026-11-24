"""Luồng gửi → lịch sử → duyệt/từ chối trên PostgreSQL thật, rollback toàn bộ dữ liệu test."""

import asyncio
import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import lay_user_hien_tai
from app.postgres import engine, get_db
from app.routers import owner


@pytest.mark.parametrize("self_approval", [True, False])
def test_owner_history_and_approval_reasons_on_postgres(pytestconfig, self_approval):
    if not pytestconfig.getoption("--run-publication-db"):
        pytest.skip("Thêm --run-publication-db để chạy luồng Owner trên PostgreSQL thật")

    async def scenario():
        engine.echo = False
        sender_id, reviewer_id = uuid4(), uuid4()
        sender_email = f"history-{sender_id}@example.test"
        reviewer_email = f"review-{reviewer_id}@example.test"
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    async with AsyncSession(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as db:
                        for user_id, email in (
                            (sender_id, sender_email),
                            (reviewer_id, reviewer_email),
                        ):
                            await db.execute(
                                text("""
                                INSERT INTO users (id,email,password_hash,full_name,account_status,owner_verified_at)
                                VALUES (:id,:email,'unused-test-hash','Owner history test','active',now())
                            """),
                                {"id": user_id, "email": email},
                            )
                        await db.commit()
                        sender = {
                            "username": sender_email,
                            "role": "admin",
                            "permissions": ["poi:approve"],
                        }
                        reviewer = {
                            "username": reviewer_email,
                            "role": "admin",
                            "permissions": ["poi:approve"],
                        }
                        current_user = sender
                        app = FastAPI()
                        app.include_router(owner.router)
                        app.dependency_overrides[get_db] = lambda: db
                        app.dependency_overrides[lay_user_hien_tai] = lambda: current_user
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as client:
                            status = await client.get("/owner/registration-status")
                            assert status.status_code == 200 and status.json()["status"] == "admin"
                            payload = {
                                "name": "History test cafe",
                                "description": "Description",
                                "address_line": "Test",
                                "lat": 10.78,
                                "lng": 106.69,
                                "menu": {
                                    "name": "Menu test",
                                    "items": [{"name": "Món test", "price": 25000}],
                                },
                            }
                            sent = await client.post("/owner/submissions", json=payload)
                            assert sent.status_code == 200, sent.text
                            sid = sent.json()["submission_id"]
                            history = (await client.get("/owner/submissions/mine")).json()
                            assert len(history) == 1
                            assert history[0]["id"] == sid and history[0]["status"] == "pending"
                            assert history[0]["submission_type"] == "create"
                            # Owner cannot self-approve even with an accidentally granted permission.
                            current_user = {**sender, "role": "poi_owner"}
                            pending = (await client.get("/owner/submissions/pending")).json()
                            own = next(row for row in pending if row["id"] == sid)
                            assert not own["can_approve"]
                            assert "Chỉ Admin có quyền duyệt" in own["approval_blockers"][0]
                            denied = await client.post(f"/owner/submissions/{sid}/approve")
                            assert denied.status_code == 403
                            assert "Chỉ Admin có quyền duyệt" in denied.json()["detail"]

                            # The admin role does not bypass the endpoint's permission dependency.
                            current_user = {**sender, "permissions": []}
                            denied = await client.post(f"/owner/submissions/{sid}/approve")
                            assert denied.status_code == 403
                            assert (
                                await client.get("/owner/submissions/pending")
                            ).status_code == 403
                            current_user = sender
                            pending = (await client.get("/owner/submissions/pending")).json()
                            own = next(row for row in pending if row["id"] == sid)
                            assert own["can_approve"] and own["approval_blockers"] == []
                            assert (await client.get("/owner/submissions/mine")).json()[0][
                                "status"
                            ] == "pending"

                            current_user = reviewer
                            assert (await client.get("/owner/submissions/mine")).json() == []
                            current_user = sender if self_approval else reviewer
                            pending = (await client.get("/owner/submissions/pending")).json()
                            assert next(row for row in pending if row["id"] == sid)["can_approve"]
                            approved = await client.post(f"/owner/submissions/{sid}/approve")
                            assert approved.status_code == 200, approved.text
                            poi_id = approved.json()["poi_id"]
                            poi = (
                                (
                                    await db.execute(
                                        text(
                                            "SELECT owner_id,publication_status,is_active FROM pois WHERE id=CAST(:id AS uuid)"
                                        ),
                                        {"id": poi_id},
                                    )
                                )
                                .mappings()
                                .one()
                            )
                            assert (
                                poi["publication_status"] == "unpublished" and not poi["is_active"]
                            )
                            assert poi["owner_id"] == sender_id
                            repeated = await client.post(f"/owner/submissions/{sid}/approve")
                            assert repeated.status_code == 404
                            assert (
                                await db.execute(
                                    text(
                                        "SELECT count(*) FROM menus WHERE poi_id=CAST(:id AS uuid)"
                                    ),
                                    {"id": poi_id},
                                )
                            ).scalar_one() == 1
                            current_user = sender
                            history = (await client.get("/owner/submissions/mine")).json()
                            assert (
                                history[0]["status"] == "approved"
                                and history[0]["poi_id"] == poi_id
                            )
                            assert history[0]["submission_type"] == "create"
                            assert (await client.get("/owner/notifications")).json()

                            # Seed cũ thiếu tọa độ: approve có lý do, reject vẫn lưu ghi chú và lịch sử.
                            broken_id = uuid4()
                            await db.execute(
                                text("""
                                INSERT INTO poi_submissions (id,owner_id,submission_type,content_snapshot,status)
                                VALUES (:id,:owner,'create',CAST(:snapshot AS jsonb),'pending')
                            """),
                                {
                                    "id": broken_id,
                                    "owner": sender_id,
                                    "snapshot": json.dumps({"name": "Missing coordinates"}),
                                },
                            )
                            await db.commit()
                            current_user = reviewer
                            denied = await client.post(f"/owner/submissions/{broken_id}/approve")
                            assert denied.status_code == 409, denied.text
                            assert "vĩ độ, kinh độ" in denied.json()["detail"]
                            rejected = await client.post(
                                f"/owner/submissions/{broken_id}/reject",
                                json={"admin_note": "Bổ sung tọa độ"},
                            )
                            assert rejected.status_code == 200, rejected.text
                            current_user = sender
                            history = (await client.get("/owner/submissions/mine")).json()
                            row = next(row for row in history if row["id"] == str(broken_id))
                            assert (
                                row["status"] == "rejected"
                                and row["admin_note"] == "Bổ sung tọa độ"
                            )
                finally:
                    await transaction.rollback()
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM users WHERE id IN (:a,:b)"),
                        {"a": sender_id, "b": reviewer_id},
                    )
                ).scalar_one() == 0
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=90))
