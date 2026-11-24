import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth import lay_user_hien_tai
from app.permissions import _quyen_ung_dung
from app.postgres import get_db
from app.routers import admin_pois, owner
from app.services import publication
from tests_postgres.test_poi_write_workflows import FakeResult, FakeSession


def ready_english(**changes):
    return {
        "localized_name": "Cafe",
        "localized_description": "English description",
        "readiness_status": "ready",
        "is_fallback": False,
        "audio_status": "ready",
        "audio_url": "/static/audio/en.mp3",
        **changes,
    }


def poi_row(**changes):
    return {
        "id": uuid4(),
        "name": "Cafe",
        "description": "Tea",
        "owner_id": uuid4(),
        "publication_status": "unpublished",
        "is_active": False,
        "has_approval": True,
        **changes,
    }


@pytest.mark.parametrize(
    "english",
    [
        None,
        ready_english(localized_name=" \n"),
        ready_english(localized_description="\t"),
        ready_english(readiness_status="incomplete"),
        ready_english(readiness_status="draft"),
        ready_english(readiness_status="review_required"),
        ready_english(readiness_status="failed"),
        ready_english(is_fallback=True),
        ready_english(audio_url=None),
        ready_english(audio_url=" "),
        *[
            ready_english(audio_status=status)
            for status in ["not_generated", "queued", "processing", "failed", "unavailable"]
        ],
    ],
)
def test_readiness_rejects_incomplete_english_or_audio(english):
    result = publication.publication_readiness(poi_row(), english)
    assert not result["ready"]
    assert result["reasons"]


@pytest.mark.parametrize("status", ["ready", "published"])
def test_readiness_accepts_reviewed_real_english_and_ready_audio(status):
    result = publication.publication_readiness(poi_row(), ready_english(readiness_status=status))
    assert result["ready"]
    assert result["reasons"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"has_approval": False},
        {"publication_status": "archived"},
        {"publication_status": "rejected"},
        {"owner_id": None, "publication_status": "pending_review", "has_approval": False},
    ],
)
def test_ready_assets_do_not_bypass_review_or_archival(changes):
    assert not publication.publication_readiness(poi_row(**changes), ready_english())["ready"]


def test_admin_draft_and_legacy_approved_poi_can_publish():
    assert publication.publication_readiness(
        poi_row(owner_id=None, publication_status="draft", has_approval=False), ready_english()
    )["ready"]
    assert publication.publication_readiness(
        poi_row(publication_status="pending_review"), ready_english()
    )["ready"]


@pytest.mark.parametrize("action", ["publish", "unpublish", "readiness"])
@pytest.mark.parametrize("permissions", [[], ["poi:update"], ["poi:approve"]])
def test_publication_requires_its_own_permission(action, permissions):
    app = FastAPI()
    app.include_router(admin_pois.router)
    app.dependency_overrides[lay_user_hien_tai] = lambda: {
        "role": "poi_owner",
        "permissions": permissions,
    }
    session = FakeSession()
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        method = client.get if action == "readiness" else client.post
        assert method(f"/admin/pois/{uuid4()}/{action}").status_code == 403
    assert session.statements == []


def test_review_permission_is_separate_from_publish_permission():
    assert _quyen_ung_dung(["submissions.review"]) == ["poi:approve"]
    assert _quyen_ung_dung(["pois.publish"]) == ["poi:publish"]


def test_publish_failure_returns_reasons_without_side_effects():
    poi = poi_row()
    session = FakeSession(FakeResult(rows=[poi]), FakeResult())
    with pytest.raises(HTTPException) as error:
        asyncio.run(admin_pois.publish_poi(str(poi["id"]), session, {"id": str(uuid4())}))
    assert error.value.status_code == 409
    assert len(error.value.detail["readiness"]["reasons"]) == 2
    assert not session.committed
    assert len(session.statements) == 2
    assert "FOR UPDATE" in session.statements[0][0]
    assert "language_code = 'en'" in session.statements[1][0]
    assert "FOR SHARE" in session.statements[1][0]


@pytest.mark.parametrize("published", [True, False])
@pytest.mark.parametrize("status", ["archived", "rejected"])
def test_publish_and_unpublish_cannot_restore_archived_or_rejected_poi(published, status):
    poi = poi_row(publication_status=status, is_active=False)
    session = FakeSession(FakeResult(rows=[poi]), FakeResult(rows=[ready_english()]))
    with pytest.raises(HTTPException) as error:
        asyncio.run(publication.set_publication(session, poi["id"], {}, published=published))
    assert error.value.status_code == 409
    assert len(session.statements) == 2
    assert not session.committed


@pytest.mark.parametrize("published", [True, False])
def test_publish_and_unpublish_write_state_notification_and_audit_atomically(
    monkeypatch, published
):
    poi = poi_row(
        publication_status="unpublished" if published else "published", is_active=not published
    )
    session = FakeSession(
        FakeResult(rows=[poi]), FakeResult(rows=[ready_english()] if published else [])
    )
    audit = AsyncMock()
    monkeypatch.setattr(publication, "ghi_audit", audit)
    result = asyncio.run(
        publication.set_publication(session, poi["id"], {"id": str(uuid4())}, published=published)
    )
    assert result["is_active"] is published
    assert result["publication_status"] == ("published" if published else "unpublished")
    assert session.statements[2][1]["active"] is published
    notification = session.statements[3][1]
    assert notification["owner_id"] == poi["owner_id"]
    assert notification["type"] == ("poi_published" if published else "poi_unpublished")
    assert session.committed
    audit.assert_awaited_once()


@pytest.mark.parametrize("published", [True, False])
def test_repeated_action_does_not_duplicate_notifications(monkeypatch, published):
    poi = poi_row(
        publication_status="published" if published else "unpublished", is_active=published
    )
    session = FakeSession(FakeResult(rows=[poi]), FakeResult(rows=[ready_english()]))
    audit = AsyncMock()
    monkeypatch.setattr(publication, "ghi_audit", audit)
    result = asyncio.run(publication.set_publication(session, poi["id"], {}, published=published))
    assert not result["changed"]
    assert len(session.statements) == 2
    audit.assert_not_awaited()


@pytest.mark.parametrize("identifier, expected", [("invalid", 400), (str(uuid4()), 404)])
def test_invalid_or_missing_poi(identifier, expected):
    session = FakeSession(FakeResult())
    with pytest.raises(HTTPException) as error:
        asyncio.run(admin_pois.publish_poi(identifier, session, {}))
    assert error.value.status_code == expected
    assert not session.committed


@pytest.mark.parametrize("status, changed", [("published", True), ("unpublished", False)])
def test_update_approval_never_publishes_and_invalidates_changed_content(
    monkeypatch, status, changed
):
    poi = poi_row(publication_status=status, is_active=status == "published")
    submission_id = uuid4()
    snapshot = {
        "name": "New cafe" if changed else poi["name"],
        "description": "Tea",
        "lat": 10.7,
        "lng": 106.6,
    }
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": submission_id,
                    "owner_id": poi["owner_id"],
                    "poi_id": poi["id"],
                    "content_snapshot": snapshot,
                }
            ]
        ),
        FakeResult(rows=[poi]),
        *([FakeResult(), FakeResult()] if changed else []),
        FakeResult(scalar=poi["id"]),
    )
    monkeypatch.setattr(owner, "ghi_audit", AsyncMock())
    asyncio.run(owner.duyet_submission(str(submission_id), session, {"id": str(uuid4())}))
    update_sql = next(sql for sql, _ in session.statements if "SET name = :name" in sql)
    assert "publication_status = 'unpublished', is_active = FALSE" in update_sql
    assert any("review_required" in sql for sql, _ in session.statements) is changed
    assert session.committed


def test_submission_owner_cannot_review_their_own_poi():
    owner_id = uuid4()
    session = FakeSession(FakeResult(rows=[{"owner_id": owner_id}]))
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            owner.duyet_submission(
                str(uuid4()), session, {"id": str(owner_id), "role": "poi_owner"}
            )
        )
    assert error.value.status_code == 403
    assert not session.committed
