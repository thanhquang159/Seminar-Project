import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import owner


class FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def one_or_none(self):
        return self._rows[0] if self._rows else None


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


def test_owner_poi_list_is_scoped_to_authenticated_owner():
    owner_id = uuid4()
    poi_id = uuid4()
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": str(poi_id),
                    "name": "Cafe",
                    "description": "Tea",
                    "lat": 10.7,
                    "lng": 106.6,
                    "trigger_radius": 30,
                    "publication_status": "published",
                    "is_active": True,
                    "images": ["https://example.test/cafe.jpg"],
                    "audio_url": "https://example.test/cafe.mp3",
                }
            ]
        )
    )

    pois = asyncio.run(
        owner.pois_cua_toi(
            session,
            {"id": str(owner_id), "username": "owner@example.test"},
        )
    )

    sql, params = session.statements[0]
    assert params == {"owner_id": owner_id}
    assert "WHERE p.owner_id = :owner_id" in sql
    assert "p.publication_status" in sql
    assert "p.is_active" in sql
    assert "poi_images AS i" in sql
    assert "poi_localizations AS l" in sql
    assert pois == [
        {
            "id": str(poi_id),
            "name": "Cafe",
            "description": "Tea",
            "lat": 10.7,
            "lng": 106.6,
            "trigger_radius": 30,
            "publication_status": "published",
            "is_active": True,
            "images": ["https://example.test/cafe.jpg"],
            "audio_url": "https://example.test/cafe.mp3",
        }
    ]


def test_owner_submissions_include_review_note_and_submission_time():
    owner_id = uuid4()
    submitted_at = datetime(2026, 11, 10, 4, 30, tzinfo=UTC)
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": str(uuid4()),
                    "owner_id": str(owner_id),
                    "poi_id": None,
                    "data": {"name": "Cafe"},
                    "status": "rejected",
                    "admin_note": "Please revise the location",
                    "submitted_at": submitted_at,
                    "created_at": submitted_at,
                    "username": "owner@example.test",
                }
            ]
        )
    )

    submissions = asyncio.run(
        owner.submission_cua_toi(
            session,
            {"id": str(owner_id), "username": "owner@example.test"},
        )
    )

    sql, params = session.statements[0]
    assert params == {"owner_id": owner_id}
    assert "WHERE s.owner_id = :owner_id" in sql
    assert submissions[0]["status"] == "rejected"
    assert submissions[0]["admin_note"] == "Please revise the location"
    assert submissions[0]["submitted_at"] == submitted_at.isoformat()
    assert submissions[0]["created_at"] == submitted_at.isoformat()


def test_reject_submission_requires_a_non_empty_reason():
    session = FakeSession()

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            owner.tu_choi_submission(
                str(uuid4()),
                owner.XetDuyet(admin_note=" \t "),
                session,
                {"id": str(uuid4()), "username": "admin@example.test"},
            )
        )

    assert error.value.status_code == 400
    assert session.statements == []
    assert not session.committed


def test_reject_submission_updates_review_and_notifies_owner_atomically():
    submission_id = uuid4()
    owner_id = uuid4()
    reviewer_id = uuid4()
    session = FakeSession(
        FakeResult(rows=[{"id": submission_id, "owner_id": owner_id}]),
    )

    result = asyncio.run(
        owner.tu_choi_submission(
            str(submission_id),
            owner.XetDuyet(admin_note="  Update the address  "),
            session,
            {"id": str(reviewer_id), "username": "admin@example.test"},
        )
    )

    select_sql, select_params = session.statements[0]
    update_sql, update_params = session.statements[1]
    notification_sql, notification_params = session.statements[2]
    audit_sql, audit_params = session.statements[3]
    assert result == {"ok": True}
    assert "status = 'pending'" in select_sql
    assert select_params == {"submission_id": submission_id}
    assert "status = 'rejected'" in update_sql
    assert "admin_note = :admin_note" in update_sql
    assert "reviewed_by = :reviewer_id" in update_sql
    assert update_params == {
        "submission_id": submission_id,
        "reviewer_id": reviewer_id,
        "admin_note": "Update the address",
    }
    assert "INSERT INTO owner_notifications" in notification_sql
    assert notification_params["owner_id"] == owner_id
    assert notification_params["submission_id"] == submission_id
    assert notification_params["message"] == "Đề xuất POI bị từ chối: Update the address"
    assert "INSERT INTO audit_logs" in audit_sql
    assert audit_params["action"] == "poi:reject"
    assert session.committed


def test_reject_submission_returns_not_found_when_no_pending_record_exists():
    session = FakeSession()

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            owner.tu_choi_submission(
                str(uuid4()),
                owner.XetDuyet(admin_note="Not accepted"),
                session,
                {"id": str(uuid4()), "username": "admin@example.test"},
            )
        )

    assert error.value.status_code == 404
    assert len(session.statements) == 1
    assert not session.committed


def test_owner_management_routes_have_expected_paths_and_methods():
    routes = {
        (method, route.path)
        for route in owner.router.routes
        for method in getattr(route, "methods", set())
    }

    assert ("GET", "/owner/pois") in routes
    assert ("POST", "/owner/submissions/{sid}/reject") in routes
