import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.postgres import get_db
from app.routers import admin_pois, geo, owner


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def one(self):
        return self._rows[0]

    def one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar


class FakeSession:
    def __init__(self, *results):
        self.results = list(results)
        self.statements = []
        self.committed = False

    async def execute(self, statement, params=None):
        self.statements.append((str(statement), params or {}))
        if self.results:
            return self.results.pop(0)
        return FakeResult()

    async def commit(self):
        self.committed = True


def test_admin_create_uses_existing_postgres_columns_and_defaults(monkeypatch):
    poi_id = uuid4()
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": poi_id,
                    "name": "Cafe",
                    "description": "",
                    "lat": 10.7,
                    "lng": 106.6,
                    "trigger_radius": 30,
                    "audio_priority": 0,
                }
            ]
        )
    )
    audit = AsyncMock()
    monkeypatch.setattr(admin_pois, "ghi_audit", audit)

    result = asyncio.run(
        admin_pois.tao_poi(
            admin_pois.PoiNhap(name="Cafe", lat=10.7, lng=106.6),
            session,
            {"id": str(uuid4()), "username": "admin@example.test"},
        )
    )

    sql, params = session.statements[0]
    assert result["id"] == str(poi_id)
    assert "category, address_line" in sql
    assert "'draft', FALSE" in sql
    assert params["name"] == "Cafe"
    assert "Cafe" not in sql
    assert session.committed
    audit.assert_awaited_once()


def test_geo_query_uses_parameterized_postgis_distance():
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": str(uuid4()),
                    "distance_m": 21.26,
                    "name": "Cafe",
                    "lat": 10.7,
                    "lng": 106.6,
                }
            ]
        )
    )

    result = asyncio.run(geo.gan_khoang_cach(session, 10.7, 106.6, 1000, "vi"))

    sql, params = session.statements[0]
    assert result[0]["distance_m"] == 21.3
    assert "ST_DWithin" in sql
    assert "ST_Distance" in sql
    assert "p.publication_status = 'published'" in sql
    assert params == {"lang": "vi", "lat": 10.7, "lng": 106.6, "radius_m": 1000}


def test_owner_submission_maps_to_existing_poi_submissions_columns(monkeypatch):
    submission_id = uuid4()
    session = FakeSession(FakeResult(scalar=submission_id))
    body = owner.SubmissionNhap(name="Cafe", description="Tea", lat=10.7, lng=106.6)

    result = asyncio.run(
        owner.gui_submission(body, session, {"id": str(uuid4()), "username": "owner@example.test"})
    )

    sql, params = session.statements[0]
    assert result == {"ok": True, "submission_id": str(submission_id)}
    assert "INSERT INTO poi_submissions" in sql
    assert params["submission_type"] == "create"
    assert '"name": "Cafe"' in params["content_snapshot"]
    assert session.committed


def test_owner_notification_read_is_scoped_to_authenticated_owner():
    session = FakeSession()
    notification_id = uuid4()
    owner_id = uuid4()

    result = asyncio.run(
        owner.da_doc(
            str(notification_id),
            session,
            {"id": str(owner_id), "username": "owner@example.test"},
        )
    )

    sql, params = session.statements[0]
    assert result == {"ok": True}
    assert "owner_id = :owner_id" in sql
    assert params == {"notification_id": notification_id, "owner_id": owner_id}
    assert session.committed


def test_owner_registration_stores_encrypted_verification_bytes(monkeypatch):
    user_id = uuid4()
    session = FakeSession(
        FakeResult(scalar=None),
        FakeResult(scalar=user_id),
        FakeResult(),
    )
    monkeypatch.setattr(owner, "ma_hoa_pii", lambda value: "v1:encrypted-value")
    monkeypatch.setattr(owner, "bam_mat_khau", lambda value: "hashed-password")

    result = asyncio.run(
        owner.dang_ky(
            owner.DangKyOwner(
                username="owner@example.test", password="safe-password", cccd="123456789"
            ),
            session,
        )
    )

    registration_sql, params = session.statements[2]
    assert result == {"ok": True, "status": "pending"}
    assert "verification_data_enc" in registration_sql
    assert params["verification_data"] == b"v1:encrypted-value"
    assert "123456789" not in repr(params)
    assert session.committed


def test_owner_cannot_approve_own_registration():
    owner_id = uuid4()
    session = FakeSession(
        FakeResult(rows=[{"id": uuid4(), "user_id": owner_id}]),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            owner.duyet(
                "owner@example.test",
                session,
                {"id": str(owner_id), "username": "owner@example.test"},
            )
        )

    assert error.value.status_code == 403
    assert not session.committed
    assert len(session.statements) == 1


def test_submission_approval_creates_inactive_review_poi_and_notification(monkeypatch):
    submission_id = uuid4()
    owner_id = uuid4()
    poi_id = uuid4()
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": submission_id,
                    "owner_id": owner_id,
                    "poi_id": None,
                    "submission_type": "create",
                    "content_snapshot": {
                        "name": "Cafe",
                        "description": "Tea",
                        "lat": 10.7,
                        "lng": 106.6,
                    },
                }
            ]
        ),
        FakeResult(scalar=poi_id),
        FakeResult(),
        FakeResult(),
    )
    audit = AsyncMock()
    monkeypatch.setattr(owner, "ghi_audit", audit)

    result = asyncio.run(
        owner.duyet_submission(
            str(submission_id),
            session,
            {"id": str(uuid4()), "username": "admin@example.test"},
        )
    )

    poi_sql, poi_params = session.statements[1]
    notification_sql, notification_params = session.statements[3]
    assert result == {"ok": True, "poi_id": str(poi_id)}
    assert "publication_status, is_active" in poi_sql
    assert "'pending_review', FALSE" in poi_sql
    assert poi_params["owner_id"] == owner_id
    assert "INSERT INTO owner_notifications" in notification_sql
    assert notification_params["poi_id"] == poi_id
    assert session.committed
    audit.assert_awaited_once()


def test_admin_delete_archives_instead_of_breaking_foreign_keys(monkeypatch):
    poi_id = uuid4()
    session = FakeSession(FakeResult(rows=[{"id": poi_id}]))
    audit = AsyncMock()
    monkeypatch.setattr(admin_pois, "ghi_audit", audit)

    response = asyncio.run(
        admin_pois.xoa_poi(
            str(poi_id),
            session,
            {"id": str(uuid4()), "username": "admin@example.test"},
        )
    )

    sql, _ = session.statements[0]
    assert response.status_code == 204
    assert "publication_status = 'archived'" in sql
    assert "is_active = FALSE" in sql
    assert "DELETE FROM pois" not in sql
    assert session.committed


def test_admin_rejects_malformed_poi_uuid_before_query():
    session = FakeSession()

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            admin_pois.sua_poi(
                "not-a-uuid",
                admin_pois.PoiNhap(name="Cafe", lat=10.7, lng=106.6),
                session,
                {"id": str(uuid4())},
            )
        )

    assert error.value.status_code == 400
    assert session.statements == []


def test_geo_endpoint_responds_through_fastapi_with_injected_session():
    session = FakeSession(FakeResult(rows=[]))
    app = FastAPI()
    app.include_router(geo.router)

    async def get_test_session():
        yield session

    app.dependency_overrides[get_db] = get_test_session

    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.get("/poi/nearby?lat=10.7&lng=106.6")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json() == []
    assert "ST_DWithin" in session.statements[0][0]
