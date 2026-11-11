"""Focused API contract tests for administrative user and role management."""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import lay_user_hien_tai
from app.postgres import get_db
from app.routers.admin_users import router

TARGET_ID = UUID("7f64a3c4-f187-4ce4-86a8-84655e9ae42d")
ADMIN_ROLE_ID = UUID("45e8a4c6-683f-48f5-91ae-7a114024143b")
OWNER_ROLE_ID = UUID("2ff04218-6ef7-41e6-aa17-1c8210bd0e50")
STAFF_ROLE_ID = UUID("4ab646ce-1421-45f1-b7d7-e955806f31ef")
READ_PERMISSION_ID = UUID("58e30ce0-84bb-4a81-a240-f10f6b6da4da")


class Result:
    def __init__(self, rows=None, scalars=None):
        self.rows = rows or []
        self.scalars = scalars or []

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def one_or_none(self):
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self):
        return self.scalars[0] if self.scalars else None


class FakeSession:
    def __init__(self):
        self.target = {
            "id": TARGET_ID,
            "email": "member@example.test",
            "full_name": "Member",
            "account_status": "active",
        }
        self.roles = {
            "ADMIN": {"id": ADMIN_ROLE_ID, "code": "ADMIN", "name": "Admin"},
            "OWNER": {"id": OWNER_ROLE_ID, "code": "OWNER", "name": "Owner"},
            "staff": {"id": STAFF_ROLE_ID, "code": "staff", "name": "Staff"},
        }
        self.role_permissions = {
            "ADMIN": {"users.manage", "roles.manage"},
            "OWNER": {"pois.own.read"},
            "staff": {"pois.read"},
        }
        self.permission_ids = {"pois.read": READ_PERMISSION_ID}
        self.user_role = "ADMIN"
        self.actor_role_code = None
        self.statements = []
        self.audit_actions = []
        self.committed = False

    async def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        params = params or {}
        self.statements.append((sql, params))

        if "assigned_role.code AS role_code" in sql:
            return Result(
                rows=[
                    {
                        "id": self.target["id"],
                        "email": self.target["email"],
                        "full_name": self.target["full_name"],
                        "account_status": self.target["account_status"],
                        "role_code": self.user_role,
                        "role_name": self.roles[self.user_role]["name"],
                    }
                ]
            )
        if "SELECT id, email, full_name, account_status FROM users" in sql:
            return Result(rows=[self.target] if params["user_id"] == self.target["id"] else [])
        if sql.startswith("SELECT r.id, r.code") or sql.startswith("SELECT id, code FROM roles"):
            code = params["role_code"].upper()
            role = self.roles.get(code) or self.roles.get(params["role_code"])
            return Result(rows=[role] if role else [])
        if "SELECT p.code FROM role_permissions AS rp" in sql:
            role_code = next(
                code for code, role in self.roles.items() if role["id"] == params["role_id"]
            )
            return Result(rows=[{"code": code} for code in self.role_permissions[role_code]])
        if "SELECT r.code FROM user_roles AS ur" in sql:
            return Result(scalars=[self.user_role] if self.user_role else [])
        if "SELECT id, code FROM permissions" in sql:
            return Result(
                rows=[
                    {"id": self.permission_ids[code], "code": code}
                    for code in params["permission_codes"]
                    if code in self.permission_ids
                ]
            )
        if sql.startswith("INSERT INTO roles"):
            code = params["code"]
            if code in self.roles:
                return Result()
            role_id = uuid4()
            self.roles[code] = {"id": role_id, "code": code, "name": params["name"]}
            self.role_permissions[code] = set()
            return Result(rows=[{"id": role_id, "code": code}])
        if "SELECT EXISTS (" in sql:
            is_actor_role = (
                self.actor_role_code is not None
                and params["role_id"] == self.roles[self.actor_role_code]["id"]
            )
            return Result(scalars=[is_actor_role])
        if "UPDATE users SET account_status" in sql:
            self.target["account_status"] = params["account_status"]
        elif sql.startswith("DELETE FROM user_roles"):
            self.user_role = None
        elif "INSERT INTO user_roles" in sql:
            self.user_role = params["role_code"]
        elif sql.startswith("DELETE FROM role_permissions"):
            role_code = next(
                code for code, role in self.roles.items() if role["id"] == params["role_id"]
            )
            self.role_permissions[role_code] = set()
        elif "INSERT INTO role_permissions" in sql:
            role_code = next(
                code for code, role in self.roles.items() if role["id"] == params["role_id"]
            )
            permission_code = next(
                code
                for code, permission_id in self.permission_ids.items()
                if permission_id == params["permission_id"]
            )
            self.role_permissions[role_code].add(permission_code)
        elif "INSERT INTO audit_logs" in sql:
            self.audit_actions.append(params["action"])
        return Result()

    async def commit(self):
        self.committed = True


@pytest.fixture
def api():
    db = FakeSession()
    actor = {
        "username": "admin@example.test",
        "permissions": ["users.read", "user:update", "role:read"],
    }
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[lay_user_hien_tai] = lambda: actor
    with TestClient(app) as client:
        yield client, db, actor


def test_list_users_contract_and_users_read_permission(api):
    client, db, _ = api
    response = client.get("/admin/users")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(TARGET_ID),
            "email": "member@example.test",
            "full_name": "Member",
            "account_status": "active",
            "role_code": "ADMIN",
            "role_name": "Admin",
        }
    ]
    query = db.statements[0][0]
    assert "password_hash" not in query
    assert "phone" not in query

    client.app.dependency_overrides[lay_user_hien_tai] = lambda: {
        "username": "reader@example.test",
        "permissions": [],
    }
    assert client.get("/admin/users").status_code == 403


def test_create_custom_role_with_provisioned_safe_permissions(api):
    client, db, _ = api
    response = client.post(
        "/admin/roles",
        json={
            "code": "content_editor",
            "name": "Content editor",
            "permission_codes": ["pois.read"],
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "role_code": "content_editor",
        "name": "Content editor",
        "description": None,
        "permission_codes": ["pois.read"],
    }
    assert db.role_permissions["content_editor"] == {"pois.read"}
    assert db.audit_actions == ["role:create"]
    assert db.committed


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"code": "staff", "name": "Duplicate"}, 409),
        ({"code": "bad-code", "name": "Invalid"}, 422),
        ({"code": "editor", "name": "   "}, 422),
        ({"code": "admin", "name": "Admin"}, 403),
        ({"code": "owner", "name": "Owner"}, 403),
        ({"code": "manager", "name": "Manager", "permission_codes": ["users.manage"]}, 403),
        (
            {
                "code": "translator",
                "name": "Translator",
                "permission_codes": ["missing.permission"],
            },
            422,
        ),
    ],
)
def test_create_custom_role_rejects_duplicate_or_unsafe_permissions(api, body, status):
    client, db, _ = api

    response = client.post("/admin/roles", json=body)

    assert response.status_code == status
    assert not db.committed
    assert db.audit_actions == []


def test_update_account_status_is_audited_and_committed(api):
    client, db, _ = api
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"account_status": "rejected"})

    assert response.status_code == 200
    assert response.json() == {
        "id": str(TARGET_ID),
        "account_status": "rejected",
        "role_code": "ADMIN",
    }
    assert db.target["account_status"] == "rejected"
    assert db.audit_actions == ["user:update"]
    assert db.committed
    assert db.statements[-2][0].startswith("SELECT r.code FROM user_roles")
    assert db.statements[-1][0].startswith("INSERT INTO audit_logs")


def test_update_rejects_unprovisioned_status_and_self_lockout(api):
    client, db, actor = api
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"account_status": "suspended"})
    assert response.status_code == 422
    assert not db.statements

    db.target["email"] = actor["username"]
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"account_status": "rejected"})
    assert response.status_code == 403
    assert not db.committed


def test_assign_and_remove_only_safe_roles(api):
    client, db, _ = api
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"role_code": "staff"})
    assert response.status_code == 200
    assert response.json()["role_code"] == "staff"
    assert db.user_role == "staff"
    assert db.audit_actions == ["user:update"]
    assert db.committed

    db.committed = False
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"role_code": None})
    assert response.status_code == 200
    assert response.json()["role_code"] is None
    assert db.user_role is None
    assert db.committed


def test_system_or_admin_roles_cannot_be_assigned(api):
    client, db, _ = api
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"role_code": "ADMIN"})
    assert response.status_code == 403
    assert not db.committed
    assert db.audit_actions == []

    response = client.patch(f"/admin/users/{TARGET_ID}", json={"role_code": "OWNER"})
    assert response.status_code == 403
    assert not db.committed

    db.role_permissions["staff"] = {"users.manage"}
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"role_code": "staff"})
    assert response.status_code == 403
    assert not db.committed

    db.role_permissions["staff"] = {"analytics.read"}
    response = client.patch(f"/admin/users/{TARGET_ID}", json={"role_code": "staff"})
    assert response.status_code == 403
    assert not db.committed


def test_role_permission_update_is_replacement_and_is_audited(api):
    client, db, _ = api
    response = client.put(
        "/admin/roles/staff/permissions",
        json={"permission_codes": ["pois.read"]},
    )

    assert response.status_code == 200
    assert response.json() == {"role_code": "staff", "permission_codes": ["pois.read"]}
    assert db.role_permissions["staff"] == {"pois.read"}
    assert db.audit_actions == ["role:permissions_update"]
    assert db.committed


@pytest.mark.parametrize(
    ("role_code", "permission_codes", "status"),
    [
        ("ADMIN", [], 403),
        ("OWNER", [], 403),
        ("staff", ["users.manage"], 403),
        ("staff", ["owner_registrations.review"], 403),
        (
            "staff",
            [
                "analytics.read",
                "audit_logs.read",
                "pois.manage",
                "pois.publish",
                "submissions.review",
                "runtime.read",
                "users.read",
            ],
            403,
        ),
        ("staff", ["missing.permission"], 422),
    ],
)
def test_role_permissions_reject_system_admin_and_unknown_grants(
    api, role_code, permission_codes, status
):
    client, db, _ = api
    response = client.put(
        f"/admin/roles/{role_code}/permissions",
        json={"permission_codes": permission_codes},
    )
    assert response.status_code == status
    assert not db.committed
    assert db.audit_actions == []


def test_role_permission_update_uses_roles_manage_mapping(api):
    client, db, actor = api
    client.app.dependency_overrides[lay_user_hien_tai] = lambda: {
        **actor,
        "permissions": [],
    }
    response = client.put("/admin/roles/staff/permissions", json={"permission_codes": []})
    assert response.status_code == 403
    assert not db.committed


def test_role_permission_update_cannot_lock_out_current_actor(api):
    client, db, _ = api
    db.actor_role_code = "staff"
    response = client.put("/admin/roles/staff/permissions", json={"permission_codes": []})
    assert response.status_code == 403
    assert not db.committed
    assert db.audit_actions == []


def test_empty_or_extra_user_patch_is_rejected(api):
    client, db, _ = api
    assert client.patch(f"/admin/users/{TARGET_ID}", json={}).status_code == 422
    assert (
        client.patch(
            f"/admin/users/{TARGET_ID}",
            json={"account_status": "active", "unknown": True},
        ).status_code
        == 422
    )
    assert not db.statements
