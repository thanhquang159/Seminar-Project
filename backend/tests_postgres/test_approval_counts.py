"""Kiểm tra API đếm bằng truy vấn SQL thật trên dữ liệu tạm trong bộ nhớ."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from app.auth import lay_user_hien_tai
from app.postgres import get_db
from app.routers import owner


@pytest.mark.parametrize(
    "permissions, expected",
    [
        (["user:update", "poi:approve"], {"registrations": 105, "submissions": 107, "total": 212}),
        (["user:update"], {"registrations": 105, "submissions": 0, "total": 105}),
        (["poi:approve"], {"registrations": 0, "submissions": 107, "total": 107}),
        ([], None),
        (None, None),
    ],
)
def test_counts_include_all_pending_requests_and_respect_permissions(permissions, expected):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            for table, pending in (("owner_registrations", 105), ("poi_submissions", 107)):
                connection.execute(text(f"CREATE TABLE {table} (status TEXT NOT NULL)"))
                connection.execute(
                    text(f"INSERT INTO {table} (status) VALUES (:status)"),
                    [{"status": "pending"}] * pending
                    + [{"status": "approved"}, {"status": "rejected"}],
                )
            db = SimpleNamespace(execute=AsyncMock(side_effect=connection.execute))
            app = FastAPI()
            app.include_router(owner.router)
            app.dependency_overrides[get_db] = lambda: db
            if permissions is not None:
                app.dependency_overrides[lay_user_hien_tai] = lambda: {
                    "username": "admin@example.test",
                    "role": "admin",
                    "permissions": permissions,
                }

            async def scenario():
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/owner/approvals/counts")
                    if expected is None:
                        assert response.status_code == (401 if permissions is None else 403)
                        db.execute.assert_not_called()
                        return
                    assert response.status_code == 200
                    assert response.json() == expected
                    # Duyệt hoặc từ chối xong thì các yêu cầu rời khỏi tổng chờ xử lý.
                    connection.execute(text("UPDATE owner_registrations SET status = 'approved'"))
                    connection.execute(text("UPDATE poi_submissions SET status = 'rejected'"))
                    response = await client.get("/owner/approvals/counts")
                    assert response.json() == {"registrations": 0, "submissions": 0, "total": 0}

            asyncio.run(scenario())
    finally:
        engine.dispose()
