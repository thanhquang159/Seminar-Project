from app.auth import _role_ung_dung
from app.permissions import _quyen_ung_dung


def test_postgres_role_codes_map_to_application_roles():
    assert _role_ung_dung("ADMIN") == "admin"
    assert _role_ung_dung("OWNER") == "poi_owner"
    assert _role_ung_dung("staff") == "staff"


def test_postgres_permission_codes_satisfy_route_permissions():
    assert set(
        _quyen_ung_dung(
            [
                "analytics.read",
                "audit_logs.read",
                "owner_registrations.review",
                "pois.manage",
                "pois.publish",
                "roles.manage",
                "submissions.review",
                "users.manage",
            ]
        )
    ) == {
        "analytics:view",
        "audit:read",
        "poi:approve",
        "poi:publish",
        "poi:create",
        "poi:delete",
        "poi:update",
        "role:read",
        "user:update",
    }
