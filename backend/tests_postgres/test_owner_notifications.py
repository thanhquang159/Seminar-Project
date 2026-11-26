"""Kiểm thử kết quả đăng ký và giới hạn quyền của phiên đọc thông báo Owner."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.postgres import get_db
from app.routers import admin_auth, owner
from tests_postgres.test_auth_postgres import FakeSession as AuthSession
from tests_postgres.test_auth_postgres import Result
from tests_postgres.test_owner_management import FakeResult, FakeSession


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_registration_decision_creates_notification_before_commit(decision):
    owner_id, registration_id = uuid4(), uuid4()
    db = FakeSession(FakeResult([{"id": registration_id, "user_id": owner_id}]))
    reviewer = {"id": str(uuid4()), "username": "reviewer@example.test"}
    if decision == "approve":
        result = asyncio.run(owner.duyet("owner", db, reviewer))
    else:
        result = asyncio.run(
            owner.tu_choi("owner", owner.XetDuyet(admin_note="  Sai CCCD  "), db, reviewer)
        )
    assert result == {"ok": True} and db.committed
    inserted = [
        (sql, params) for sql, params in db.statements if "INSERT INTO owner_notifications" in sql
    ]
    assert len(inserted) == 1
    sql, params = inserted[0]
    assert f"owner_registration_{'approved' if decision == 'approve' else 'rejected'}" in sql
    assert params["owner_id"] == owner_id and params["registration_id"] == registration_id
    if decision == "reject":
        assert params["message"].endswith(": Sai CCCD")


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_no_duplicate_notification_for_already_reviewed_registration(decision):
    db = FakeSession()
    reviewer = {"id": str(uuid4()), "username": "reviewer@example.test"}
    with pytest.raises(HTTPException) as error:
        if decision == "approve":
            asyncio.run(owner.duyet("owner", db, reviewer))
        else:
            asyncio.run(owner.tu_choi("owner", owner.XetDuyet(admin_note="Sai CCCD"), db, reviewer))
    assert error.value.status_code == 404 and not db.committed
    assert not any("INSERT INTO owner_notifications" in sql for sql, _ in db.statements)


class OwnerAuthSession(AuthSession):
    registration_status = "pending"

    async def execute(self, statement, params=None):
        if "SELECT id FROM users" in str(statement):
            return Result(scalars=[self.user["id"]])
        if "SELECT status FROM owner_registrations" in str(statement):
            return Result(scalars=[self.registration_status] if self.registration_status else [])
        return await super().execute(statement, params)


@pytest.fixture
def portal():
    db = OwnerAuthSession()
    db.user.update(role="user", account_status="pending")
    app = FastAPI()
    app.include_router(admin_auth.router)
    app.include_router(owner.router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client, db


def login(client, path="/owner/auth/login", password="correct-password"):
    return client.post(path, json={"username": "admin@example.test", "password": password})


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_unapproved_owner_can_read_notifications_but_not_manage(portal, status):
    client, db = portal
    db.user["account_status"] = db.registration_status = status
    assert login(client, "/admin/auth/login").status_code == 401
    assert login(client).status_code == 200
    assert client.get("/owner/auth/me").status_code == 200
    assert client.get("/owner/notifications").status_code == 200
    assert client.post(f"/owner/notifications/{uuid4()}/read").status_code == 200
    assert client.post("/owner/auth/refresh").status_code == 200
    for path in (
        "/admin/auth/me",
        "/owner/pois",
        "/owner/registrations",
        "/owner/submissions/mine",
    ):
        assert client.get(path).status_code == 401
    old_token = client.cookies.get("access_token")
    assert client.post("/admin/auth/logout").status_code == 200
    assert (
        client.get(
            "/owner/notifications", headers={"Authorization": f"Bearer {old_token}"}
        ).status_code
        == 401
    )


def test_approval_updates_existing_session_without_logging_in_again(portal):
    client, db = portal
    assert login(client).status_code == 200
    db.user.update(account_status="active", role="owner", owner_verified_at="approved")
    db.registration_status = "approved"
    assert client.get("/owner/notifications").status_code == 200
    assert client.post("/owner/auth/refresh").status_code == 200
    assert client.get("/owner/pois").status_code == 200


@pytest.mark.parametrize(
    "status,registration,verified",
    [
        ("pending", None, None),
        ("rejected", "pending", None),
        ("disabled", "rejected", None),
        ("rejected", "rejected", "previously-approved"),
    ],
)
def test_non_registration_account_restrictions_are_not_bypassed(
    portal, status, registration, verified
):
    client, db = portal
    db.user.update(account_status=status, owner_verified_at=verified)
    db.registration_status = registration
    assert login(client).status_code == 401


def test_owner_login_still_checks_password_and_refresh_hash(portal):
    client, _ = portal
    assert login(client, password="wrong-password").status_code == 401
    assert login(client).status_code == 200
    access = client.cookies.get("access_token")
    client.cookies.clear()
    client.cookies.set("refresh_token", access)
    assert client.post("/owner/auth/refresh").status_code == 401
