"""Focused, database-free contract tests for the PostgreSQL auth routers."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit import ghi_audit
from app.auth import bam_mat_khau, dung_mat_khau
from app.permissions import dam_bao_roles, quyen_cua_role, quyen_cua_user
from app.postgres import get_db
from app.routers.admin_auth import router as auth_router
from app.routers.admin_meta import router as meta_router
from app.services import login_guard

USER_ID = UUID("4263e7d3-3342-45ef-a521-34486b3ebf8a")


class Result:
    def __init__(self, rows=None, scalars=None, rowcount=1):
        self._rows = rows or []
        self._scalars = scalars or []
        self.rowcount = rowcount

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):
        return self._rows[0]

    def all(self):
        return self._rows if self._rows else self._scalars

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._scalars[0] if self._scalars else None


class FakeSession:
    def __init__(self):
        self.user = {
            "id": USER_ID,
            "email": "admin@example.test",
            "password_hash": bam_mat_khau("correct-password"),
            "account_status": "active",
            "owner_verified_at": None,
            "role": "super_admin",
        }
        self.sessions = {}
        self.audit = []
        self.statements = []
        self.failures_for_username = 0

    async def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        self.statements.append((sql, params))
        if "SELECT COUNT(*) AS attempts" in sql:
            return Result(
                rows=[
                    {
                        "attempts": (
                            self.failures_for_username if params.get("username") is not None else 0
                        ),
                        "oldest": datetime.now(UTC),
                    }
                ]
            )
        if "SELECT u.id, u.email, u.password_hash" in sql:
            return Result(
                rows=[self.user] if params["username"].lower() == self.user["email"] else []
            )
        if "SELECT DISTINCT p.code" in sql:
            if params.get("role_code") == "missing":
                return Result()
            return Result(scalars=["audit:read", "role:read", "poi:read"])
        if "SELECT refresh_token_hash" in sql:
            session = self.sessions.get(params["session_id"])
            if session and session["user_id"] == params["user_id"] and not session["revoked"]:
                return Result(scalars=[session["refresh_token_hash"]])
            return Result()
        if "INSERT INTO auth_sessions" in sql:
            self.sessions[params["session_id"]] = {
                "user_id": params["user_id"],
                "refresh_token_hash": params["refresh_token_hash"],
                "revoked": False,
            }
            return Result()
        if "UPDATE auth_sessions" in sql:
            target = params.get("session_id")
            for session_id, session in self.sessions.items():
                if target is None or session_id == target:
                    session["revoked"] = True
            return Result()
        if "UPDATE users" in sql:
            self.user["password_hash"] = params["password_hash"]
            return Result()
        if "INSERT INTO audit_logs" in sql:
            self.audit.append(
                {
                    "action": params["action"],
                    "username": params.get("username"),
                    "after_data": params.get("after_data"),
                    "created_at": datetime.now(UTC),
                }
            )
            return Result()
        if "SELECT r.code, r.name, p.code AS permission_code" in sql:
            return Result(
                rows=[
                    {"code": "super_admin", "name": "Super Admin", "permission_code": "role:read"},
                    {"code": "super_admin", "name": "Super Admin", "permission_code": "audit:read"},
                ]
            )
        if "FROM audit_logs AS l" in sql:
            rows = [
                {
                    "action": item["action"],
                    "username": item["username"],
                    "resource": "user:admin@example.test",
                    "created_at": item["created_at"],
                }
                for item in reversed(self.audit)
            ]
            return Result(rows=rows[:100])
        return Result()

    async def commit(self):
        return None


@pytest.fixture
def client():
    db = FakeSession()
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(meta_router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client, db


def test_login_me_refresh_and_logout_use_postgres_session(client):
    test_client, db = client
    response = test_client.post(
        "/admin/auth/login",
        json={"username": "admin@example.test", "password": "correct-password"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "super_admin"
    assert "access_token" in test_client.cookies
    assert "refresh_token" in test_client.cookies

    me = test_client.get("/admin/auth/me")
    assert me.status_code == 200
    assert me.json() == {
        "username": "admin@example.test",
        "role": "super_admin",
        "permissions": ["audit:read", "role:read", "poi:read"],
    }
    assert test_client.post("/admin/auth/refresh").status_code == 200
    assert len(db.sessions) == 1

    assert test_client.post("/admin/auth/logout").status_code == 200
    test_client.cookies.clear()
    assert test_client.get("/admin/auth/me").status_code == 401
    assert next(iter(db.sessions.values()))["revoked"] is True


def test_login_failure_is_generic_and_throttled(client):
    test_client, db = client
    response = test_client.post(
        "/admin/auth/login",
        json={"username": "admin@example.test", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Sai tên đăng nhập hoặc mật khẩu"
    assert db.audit[0]["action"] == "auth:login_failed"

    db.failures_for_username = login_guard.SAI_TOI_DA_TAI_KHOAN
    locked = test_client.post(
        "/admin/auth/login",
        json={"username": "admin@example.test", "password": "wrong-password"},
    )
    assert locked.status_code == 429
    assert locked.headers["Retry-After"]


def test_password_change_revokes_old_session_and_reissues_current_session(client):
    test_client, db = client
    login = test_client.post(
        "/admin/auth/login",
        json={"username": "admin@example.test", "password": "correct-password"},
    )
    assert login.status_code == 200
    old_access = test_client.cookies.get("access_token")
    old_refresh = test_client.cookies.get("refresh_token")
    old_session_id = next(iter(db.sessions))

    changed = test_client.post(
        "/admin/auth/change-password",
        json={"mat_khau_cu": "correct-password", "mat_khau_moi": "new-password-123"},
    )
    assert changed.status_code == 200
    assert db.sessions[old_session_id]["revoked"] is True
    assert len(db.sessions) == 2
    assert dung_mat_khau("new-password-123", db.user["password_hash"])
    assert test_client.get("/admin/auth/me").status_code == 200

    test_client.cookies.set("refresh_token", old_refresh)
    assert test_client.post("/admin/auth/refresh").status_code == 401
    test_client.cookies.clear()
    assert (
        test_client.get(
            "/admin/auth/me", headers={"Authorization": f"Bearer {old_access}"}
        ).status_code
        == 401
    )


def test_meta_routes_and_audit_helper_use_existing_relations(client):
    test_client, db = client
    assert (
        test_client.post(
            "/admin/auth/login",
            json={"username": "admin@example.test", "password": "correct-password"},
        ).status_code
        == 200
    )
    roles = test_client.get("/admin/roles")
    assert roles.status_code == 200
    assert roles.json() == [
        {"name": "super_admin", "priority": None, "permissions": ["role:read", "audit:read"]}
    ]
    assert test_client.get("/admin/audit-logs").status_code == 200

    asyncio.run(ghi_audit(db, "admin@example.test", "poi:update", "poi:123"))
    insert_sql = next(sql for sql, _ in reversed(db.statements) if "INSERT INTO audit_logs" in sql)
    assert "actor_user_id" in insert_sql
    assert "resource_id" in insert_sql


def test_unknown_role_returns_no_permissions_and_seed_helper_does_not_mutate(client):
    _, db = client
    assert asyncio.run(quyen_cua_role(db, "missing")) == []
    assert asyncio.run(quyen_cua_user(db, "admin@example.test")) == [
        "audit:read",
        "role:read",
        "poi:read",
    ]
    asyncio.run(dam_bao_roles(db))
    assert any("JOIN user_roles" in sql for sql, _ in db.statements)
    assert not any(
        word in sql.lower()
        for sql, _ in db.statements
        for word in ("insert ", "update ", "delete ", "create ", "drop ")
    )
