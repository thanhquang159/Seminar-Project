import asyncio
from datetime import date
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import auth
from app.postgres import get_db
from app.routers.admin_analytics import router as admin_router
from app.routers.ai import con_luot
from app.routers.ai import router as ai_router
from app.routers.analytics import router as analytics_router
from app.routers.runtime_observability import router as runtime_router
from app.services import analytics_read, analytics_svc, presence, runtime_observability
from app.services.ai_svc import NhaCungCap
from app.services.process_rate_limit import reset_rate_limits


class FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):
        assert len(self._rows) == 1
        return self._rows[0]

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        return self.results.pop(0) if self.results else FakeResult()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_withdraw_consent_uses_existing_schema_status_and_advisory_lock():
    consent_id = uuid4()
    session = FakeSession([FakeResult(), FakeResult([{"id": consent_id}]), FakeResult()])

    asyncio.run(analytics_svc.dat_consent(session, "anonymous-device-1234", False))

    assert "pg_advisory_xact_lock" in session.calls[0][0]
    assert "UPDATE analytics_consents" in session.calls[2][0]
    assert "CAST(:now AS TIMESTAMPTZ)" in session.calls[2][0]
    assert session.calls[2][1]["status"] == "withdrawn"
    assert session.commits == 1


def test_new_consent_explicitly_types_postgres_timestamps():
    session = FakeSession([FakeResult(), FakeResult([]), FakeResult()])

    asyncio.run(analytics_svc.dat_consent(session, "anonymous-device-1234", True))

    insert_sql = session.calls[2][0]
    assert "INSERT INTO analytics_consents" in insert_sql
    assert insert_sql.count("CAST(:now AS TIMESTAMPTZ)") == 2
    assert session.calls[2][1]["granted"] is True
    assert session.commits == 1


def test_consent_status_maps_withdrawn_to_legacy_revoked_response():
    session = FakeSession([FakeResult([{"consent_status": "withdrawn"}])])

    status = asyncio.run(analytics_svc.trang_thai_consent(session, "anonymous-device-1234"))

    assert status == "revoked"
    assert "analytics_consents" in session.calls[0][0]


def test_event_insert_uses_consent_fk_and_strips_sensitive_properties():
    session = FakeSession([FakeResult([{"id": 1}])])

    accepted = asyncio.run(
        analytics_svc.ghi_su_kien(
            session,
            "anonymous-device-1234",
            "session-identifier-123",
            "search",
            {"query": "soup", "email": "not-stored"},
            None,
        )
    )

    sql, params = session.calls[0]
    assert accepted is True
    assert "INSERT INTO analytics_events" in sql
    assert "consent_id" in sql and "anonymous_visitor_id" in sql
    assert "session_id" not in sql
    assert params["event_properties"] == '{"query": "soup"}'
    assert session.commits == 1


def test_summary_uses_events_and_exposes_unavailable_session_count(monkeypatch):
    session = FakeSession(
        [
            FakeResult(
                [
                    {
                        "period_views": 8,
                        "period_audio_plays": 5,
                        "today_views": 4,
                        "today_audio_plays": 2,
                    }
                ]
            ),
            FakeResult(
                [
                    {"metric_date": "2026-11-03", "views": 0, "audio_plays": 0},
                    {"metric_date": "2026-11-09", "views": 4, "audio_plays": 2},
                ]
            ),
            FakeResult([{"poi_id": "poi-1", "name": "Place", "views": 4, "audio_plays": 2}]),
        ]
    )
    monkeypatch.setattr(analytics_read, "dem_online", lambda: asyncio.sleep(0, result=3))

    summary = asyncio.run(analytics_read.thong_ke(session, "2026-11-09", 7))

    assert summary["period_start"] == "2026-11-03"
    assert summary["period_days"] == 7
    assert summary["period_views"] == 8
    assert summary["period_audio_plays"] == 5
    assert summary["today_views"] == 4
    assert summary["today_audio_plays"] == 2
    assert summary["tracked_online_users"] == 3
    assert summary["top_pois"][0]["poi_id"] == "poi-1"
    assert summary["daily"][0]["views"] == 0
    assert all("analytics_events" in sql for sql, _ in session.calls)
    assert session.calls[0][1]["period_start"].isoformat() == "2026-11-03T00:00:00+07:00"
    assert session.calls[0][1]["today_start"].isoformat() == "2026-11-09T00:00:00+07:00"
    assert session.calls[1][1]["period_start_date"].isoformat() == "2026-11-03"
    assert "event_name = 'poi_viewed'" in session.calls[0][0]
    assert "generate_series" in session.calls[1][0]
    assert "Asia/Ho_Chi_Minh" in session.calls[1][0]
    assert "event_name IN ('poi_viewed', 'audio_played')" in session.calls[2][0]


def test_runtime_location_aggregates_rounded_cells_and_reads_postgres():
    session = FakeSession()
    samples = [
        runtime_observability.lam_sach_mau(
            {"lat": 10.7654, "lng": 106.7014, "outcome": "ok", "environment": "secret"}
        ),
        runtime_observability.lam_sach_mau({"lat": 10.7652, "lng": 106.7012, "outcome": "ok"}),
        None,
    ]

    written = asyncio.run(runtime_observability.ghi_vi_tri(session, samples))

    sql, rows = session.calls[0]
    assert written == 2
    assert "INSERT INTO runtime_observability_hourly" in sql
    assert "ON CONFLICT" in sql
    assert len(rows) == 1
    assert rows[0]["sample_count"] == 2
    assert "environment" not in rows[0]["metric_dimensions"]
    assert session.commits == 1


def test_runtime_window_returns_aggregated_outcomes():
    session = FakeSession(
        [
            FakeResult([{"samples": 5, "cells": 3}]),
            FakeResult(
                [{"outcome": "ok", "sample_count": 4}, {"outcome": "denied", "sample_count": 1}]
            ),
        ]
    )

    result = asyncio.run(runtime_observability.doc_cua_so(session, "7d"))

    assert result == {
        "window": "7d",
        "hours": 168,
        "samples": 5,
        "cells": 3,
        "outcomes": {"ok": 4, "denied": 1},
    }


def test_presence_and_rate_limits_are_process_local():
    async def run():
        await presence.xoa_het()
        assert await presence.heartbeat("anonymous-device-1234") == 1
        assert await presence.dem_online() == 1
        await presence.xoa_thiet_bi("anonymous-device-1234")
        assert await presence.dem_online() == 0
        reset_rate_limits()
        allowed = [
            runtime_observability.kiem_tra_tan_suat(None, "127.0.0.1", "session-12345")
            for _ in range(runtime_observability.GIOI_HAN_PHIEN_MOT_PHUT + 1)
        ]
        results = [await check for check in allowed]
        assert all(result[0] for result in results[:-1])
        assert results[-1][0] is False
        await presence.xoa_het()

    asyncio.run(run())


def test_owner_daily_quota_uses_atomic_postgres_upsert():
    session = FakeSession([FakeResult([{"request_count": 10}])])
    user_id = uuid4()

    consumed = asyncio.run(con_luot(session, user_id))

    sql, params = session.calls[0]
    assert consumed is True
    assert "INSERT INTO ai_usage_daily" in sql
    assert "ON CONFLICT (user_id, usage_date)" in sql
    assert params["user_id"] == user_id
    assert params["daily_limit"] == 10
    assert session.commits == 1


def test_public_routes_can_execute_with_mocked_postgres_session():
    session = FakeSession([FakeResult([])])
    app = FastAPI()
    app.include_router(analytics_router)
    app.include_router(runtime_router)

    async def fake_db():
        yield session

    app.dependency_overrides[get_db] = fake_db

    async def request_routes():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            consent = await client.get(
                "/analytics/consent", params={"anonymous_id": "anonymous-device-1234"}
            )
            location = await client.post(
                "/runtime-observability/location",
                json={
                    "session_id": "session-identifier-123",
                    "samples": [{"lat": 10.76, "lng": 106.7, "outcome": "ok"}],
                },
            )
            return consent, location

    reset_rate_limits()
    consent, location = asyncio.run(request_routes())

    assert consent.status_code == 200
    assert consent.json()["status"] == "unknown"
    assert location.status_code == 200
    assert location.json() == {"accepted": 1, "rejected": 0}
    assert any("runtime_observability_hourly" in sql for sql, _ in session.calls)


def test_analytics_consent_and_collect_routes_use_mocked_postgres():
    session = FakeSession(
        [
            FakeResult(),
            FakeResult(),
            FakeResult(),
            FakeResult([{"consent_status": "granted"}]),
            FakeResult([{"id": 1}]),
            FakeResult([{"id": 2}]),
        ]
    )
    app = FastAPI()
    app.include_router(analytics_router)

    async def fake_db():
        yield session

    app.dependency_overrides[get_db] = fake_db
    anonymous_id = "anonymous-device-5678"
    receipt = analytics_svc.lam_receipt(anonymous_id)

    async def request_routes():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            consent = await client.post(
                "/analytics/consent",
                json={"anonymous_id": anonymous_id, "granted": True},
            )
            collected = await client.post(
                "/analytics/collect",
                json={
                    "anonymous_id": anonymous_id,
                    "receipt": receipt,
                    "session_id": "session-identifier-123",
                    "heartbeat": False,
                    "events": [
                        {"name": "poi_viewed", "properties": {"poi_id": "poi-1"}},
                        {"name": "audio_played", "properties": {"poi_id": "poi-1"}},
                    ],
                },
            )
            return consent, collected

    reset_rate_limits()
    consent, collected = asyncio.run(request_routes())

    assert consent.status_code == 200
    assert consent.json()["status"] == "granted"
    assert collected.status_code == 200
    assert collected.json()["accepted"] == 2
    assert any("INSERT INTO analytics_events" in sql for sql, _ in session.calls)


def test_ai_route_uses_postgres_quota_and_records_request(monkeypatch):
    user_id = uuid4()
    request_id = uuid4()
    session = FakeSession(
        [
            FakeResult([{"id": user_id, "owner_verified_at": "2026-01-01T00:00:00+00:00"}]),
            FakeResult([{"request_count": 1}]),
            FakeResult([{"id": request_id}]),
            FakeResult(),
        ]
    )
    app = FastAPI()
    app.include_router(ai_router)

    async def fake_db():
        yield session

    async def fake_user():
        return {"id": str(user_id), "role": "poi_owner", "username": "owner@example.test"}

    class FakeProvider(NhaCungCap):
        async def viet_lai(self, mo_ta: str) -> str:
            return f"Improved: {mo_ta}"

    monkeypatch.setattr("app.routers.ai.lay_provider", FakeProvider)
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[auth.lay_user_hien_tai] = fake_user

    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.post("/ai/enhance-description", json={"text": "Good food"})

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json() == {"text": "Improved: Good food"}
    assert "ai_usage_daily" in session.calls[1][0]
    assert "ai_advisor_requests" in session.calls[2][0]
    assert session.calls[3][1]["status"] == "completed"
    assert session.commits == 3


def test_admin_analytics_routes_retain_permission_dependency(monkeypatch):
    session = FakeSession(
        [
            FakeResult(
                [{
                    "period_views": 3,
                    "period_audio_plays": 1,
                    "today_views": 1,
                    "today_audio_plays": 0,
                    "tracked_online_users": 2,
                }]
            ),
            FakeResult(),
            FakeResult(),
            FakeResult([{"samples": 0, "cells": 0}]),
            FakeResult(),
        ]
    )
    app = FastAPI()
    app.include_router(admin_router)

    async def fake_db():
        yield session

    async def analytics_viewer():
        return {"username": "admin", "role": "admin", "permissions": ["analytics:view"]}

    async def online():
        return 2

    monkeypatch.setattr(analytics_read, "dem_online", online)
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[auth.lay_user_hien_tai] = analytics_viewer

    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            summary = await client.get("/admin/analytics/summary?so_ngay=30")
            runtime = await client.get("/admin/runtime-observability/location")
            return summary, runtime

    summary, runtime = asyncio.run(request())

    assert summary.status_code == 200
    assert summary.json()["period_days"] == 30
    assert summary.json()["period_views"] == 3
    assert summary.json()["today_views"] == 1
    assert summary.json()["tracked_online_users"] == 2
    assert runtime.status_code == 200
    assert runtime.json()["samples"] == 0


def test_admin_ai_usage_returns_daily_owner_totals():
    session = FakeSession(
        [FakeResult([{"metric_date": "2026-03-10", "requests": 4, "daily_limit": 10, "owners": 1}])]
    )
    app = FastAPI()
    app.include_router(admin_router)

    async def fake_db():
        yield session

    async def analytics_viewer():
        return {"username": "admin", "role": "admin", "permissions": ["analytics:view"]}

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[auth.lay_user_hien_tai] = analytics_viewer

    async def request():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get("/admin/ai-usage?so_ngay=14")

    response = asyncio.run(request())

    assert response.status_code == 200
    assert response.json() == {
        "days": 14,
        "daily": [{"metric_date": "2026-03-10", "requests": 4, "daily_limit": 10, "owners": 1}],
    }
    params = session.calls[0][1]
    assert isinstance(params["start_date"], date)
    assert isinstance(params["end_date"], date)
    assert (params["end_date"] - params["start_date"]).days == 13
    assert "ai_usage_daily" in session.calls[0][0]
