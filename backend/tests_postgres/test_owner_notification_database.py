"""Kiểm thử phiên thật, duyệt đăng ký và thông báo; rollback mọi dữ liệu tạo ra."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import bam_mat_khau
from app.postgres import engine, get_db
from app.routers import admin_auth, owner


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_registration_notifications_with_real_sessions(pytestconfig, monkeypatch, decision):
    if not pytestconfig.getoption("--run-publication-db"):
        pytest.skip("Thêm --run-publication-db để kiểm tra PostgreSQL thật")
    # Mã hóa PII được kiểm thử riêng; test này không cần khóa PII của môi trường.
    monkeypatch.setattr(owner, "ma_hoa_pii", lambda value: "encrypted-test-value")

    async def scenario():
        engine.echo = False
        reviewer_id = uuid4()
        reviewer_email = f"review-{reviewer_id.hex[:12]}@test.local"
        owner_email = f"owner-{uuid4().hex[:12]}@test.local"
        password = uuid4().hex
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    async with AsyncSession(
                        bind=connection, join_transaction_mode="create_savepoint"
                    ) as db:
                        await db.execute(
                            text("""
                            INSERT INTO users (id,email,password_hash,full_name,account_status)
                            VALUES (:id,:email,:password,'Notification test reviewer','active')
                        """),
                            {
                                "id": reviewer_id,
                                "email": reviewer_email,
                                "password": bam_mat_khau(password),
                            },
                        )
                        await db.execute(
                            text("""
                            INSERT INTO user_roles (user_id,role_id)
                            SELECT :user_id,id FROM roles WHERE lower(code)='admin'
                        """),
                            {"user_id": reviewer_id},
                        )
                        await db.commit()
                        app = FastAPI()
                        app.include_router(admin_auth.router)
                        app.include_router(owner.router)
                        app.dependency_overrides[get_db] = lambda: db
                        transport = ASGITransport(app=app)
                        async with (
                            AsyncClient(transport=transport, base_url="http://test") as client,
                            AsyncClient(transport=transport, base_url="http://test") as admin,
                        ):
                            assert (await client.get("/owner/notifications")).status_code == 401
                            registered = await client.post(
                                "/owner/register",
                                json={
                                    "username": owner_email,
                                    "password": password,
                                    "cccd": "012345678901",
                                },
                            )
                            assert registered.status_code == 200, registered.text
                            credentials = {"username": owner_email, "password": password}
                            assert (
                                await client.post("/admin/auth/login", json=credentials)
                            ).status_code == 401
                            logged_in = await client.post("/owner/auth/login", json=credentials)
                            assert logged_in.status_code == 200, logged_in.text
                            assert (await client.get("/owner/registration-status")).json()[
                                "status"
                            ] == "pending"
                            assert (await client.get("/owner/notifications")).json() == []
                            assert (await client.get("/owner/pois")).status_code == 401
                            assert (await client.get("/owner/registrations")).status_code == 401
                            assert (await client.post("/owner/auth/refresh")).status_code == 200
                            admin_login = await admin.post(
                                "/admin/auth/login",
                                json={
                                    "username": reviewer_email,
                                    "password": password,
                                },
                            )
                            assert admin_login.status_code == 200, admin_login.text
                            review_path = f"/owner/registrations/{owner_email}/{decision}"
                            body = (
                                {"admin_note": "  Bổ sung CCCD  "} if decision == "reject" else None
                            )
                            reviewed = await admin.post(review_path, json=body)
                            assert reviewed.status_code == 200, reviewed.text
                            assert (await admin.post(review_path, json=body)).status_code == 404
                            # Cookie trước khi duyệt vẫn xem được kết quả mới.
                            expected_status = "approved" if decision == "approve" else "rejected"
                            status = await client.get("/owner/registration-status")
                            assert (
                                status.status_code == 200
                                and status.json()["status"] == expected_status
                            )
                            response = await client.get("/owner/notifications")
                            assert response.status_code == 200, response.text
                            notifications = response.json()
                            assert len(notifications) == 1
                            notification = notifications[0]
                            assert (
                                notification["notification_type"]
                                == f"owner_registration_{expected_status}"
                            )
                            assert notification["reference_type"] == "owner_registration"
                            assert not notification["read"]
                            if decision == "reject":
                                assert notification["message"].endswith(": Bổ sung CCCD")
                            # Tài khoản khác không xem hoặc đánh dấu thư của Owner.
                            assert (await admin.get("/owner/notifications")).json() == []
                            read_path = f"/owner/notifications/{notification['id']}/read"
                            await admin.post(read_path)
                            assert not (await client.get("/owner/notifications")).json()[0]["read"]
                            assert (await client.post(read_path)).status_code == 200
                            read = (await client.get("/owner/notifications")).json()[0]
                            assert read["read"] and read["read_at"]
                            await client.post(read_path)
                            assert (await client.get("/owner/notifications")).json()[0][
                                "read_at"
                            ] == read["read_at"]
                            assert (await client.post("/owner/auth/refresh")).status_code == 200
                            assert (await client.get("/owner/pois")).status_code == (
                                200 if decision == "approve" else 401
                            )
                            # Đăng nhập lại vẫn đọc được kết quả từ chối.
                            assert (await client.post("/admin/auth/logout")).status_code == 200
                            assert (await client.get("/owner/notifications")).status_code == 401
                            assert (
                                await client.post("/owner/auth/login", json=credentials)
                            ).status_code == 200
                            assert (await client.get("/owner/notifications")).json()[0]["read"]
                finally:
                    await transaction.rollback()
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM users WHERE email IN (:owner,:reviewer)"),
                        {"owner": owner_email, "reviewer": reviewer_email},
                    )
                ).scalar_one() == 0
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=90))
