import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import owner
from tests_postgres.test_poi_write_workflows import FakeResult, FakeSession


def test_internal_admin_without_owner_registration_has_explicit_status():
    result = asyncio.run(owner.xem_trang_thai(FakeSession(), {"id": str(uuid4()), "role": "admin"}))
    assert result == {"status": "admin", "admin_note": ""}


def test_missing_registration_does_not_make_an_owner_an_admin():
    with pytest.raises(HTTPException) as error:
        asyncio.run(owner.xem_trang_thai(FakeSession(), {"id": str(uuid4()), "role": "poi_owner"}))
    assert error.value.status_code == 404


@pytest.mark.parametrize(
    "snapshot, reason",
    [
        ({"name": "Demo"}, "vĩ độ, kinh độ"),
        ({"name": "Demo", "lat": 100, "lng": 106}, "vĩ độ"),
        ({"name": "Demo", "lat": 10, "lng": 181}, "kinh độ"),
        (
            {
                "name": "Demo",
                "lat": 10,
                "lng": 106,
                "menu": {"items": [{"name": "Món", "price": -1}]},
            },
            "thực đơn",
        ),
        ("invalid json", "Nội dung đề xuất không hợp lệ"),
    ],
)
def test_invalid_stored_submission_has_reason_and_no_partial_writes(snapshot, reason):
    session = FakeSession(FakeResult(rows=[{"owner_id": uuid4(), "content_snapshot": snapshot}]))
    with pytest.raises(HTTPException) as error:
        asyncio.run(owner.duyet_submission(str(uuid4()), session, {"id": str(uuid4())}))
    assert error.value.status_code == 409
    assert reason in error.value.detail
    assert not session.committed
    assert len(session.statements) == 1


def test_pending_list_explains_self_review_and_missing_coordinates():
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": str(uuid4()),
                    "username": "Admin@example.test",
                    "name": "Demo",
                    "data": {"name": "Demo"},
                    "created_at": None,
                }
            ]
        )
    )
    result = asyncio.run(
        owner.submission_cho_duyet(session, {"username": "admin@example.test", "role": "poi_owner"})
    )
    assert result[0]["can_approve"] is False
    assert len(result[0]["approval_blockers"]) == 2
    assert "Chỉ Admin có quyền duyệt" in result[0]["approval_blockers"][0]
    assert "vĩ độ, kinh độ" in result[0]["approval_blockers"][1]


@pytest.mark.parametrize("valid_coordinates", [True, False])
def test_admin_can_review_own_submission_but_still_requires_valid_data(valid_coordinates):
    snapshot = {"name": "Demo"}
    if valid_coordinates:
        snapshot.update(lat=10.78, lng=106.69)
    session = FakeSession(
        FakeResult(
            rows=[
                {
                    "id": str(uuid4()),
                    "username": "Admin@example.test",
                    "name": "Demo",
                    "data": snapshot,
                    "created_at": None,
                }
            ]
        )
    )
    result = asyncio.run(
        owner.submission_cho_duyet(
            session,
            {
                "username": "admin@example.test",
                "role": "admin",
                "permissions": ["poi:approve"],
            },
        )
    )
    assert result[0]["can_approve"] is valid_coordinates
    blockers = result[0]["approval_blockers"]
    if valid_coordinates:
        assert blockers == []
    else:
        assert len(blockers) == 1 and "vĩ độ, kinh độ" in blockers[0]
