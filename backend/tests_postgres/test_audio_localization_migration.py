import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import auth
from app.postgres import get_db
from app.routers import audio as audio_router
from app.routers import localizations as localizations_router
from app.routers import maps as maps_router
from app.routers import warmup as warmup_router
from app.services import audio_svc, localization, maps, ratelimit, sync, tasks


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar
        self.rowcount = 1

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows

    def scalar_one(self):
        return self.scalar

    def scalar_one_or_none(self):
        return self.scalar


class FakeSession:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []
        self.commits = 0

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return self.results.pop(0) if self.results else FakeResult()

    async def commit(self):
        self.commits += 1


def test_rate_limit_records_allowed_requests_without_ddl():
    session = FakeSession([FakeResult(scalar=0), FakeResult()])

    async def run():
        return await ratelimit.cho_phep(session, "user:tester", "/audio/tts")

    assert asyncio.run(run()) == (True, 0)
    assert len(session.calls) == 2
    assert "localization_request_logs" in session.calls[0][0]
    assert "CREATE" not in session.calls[0][0].upper()
    assert "INSERT INTO localization_request_logs" in session.calls[1][0]
    assert session.calls[1][1]["metadata"] == '{"rate_limit_key": "user:tester"}'
    assert session.commits == 1


def test_rate_limit_rejection_returns_retry_after_without_insert():
    oldest = datetime.now(UTC) - timedelta(minutes=9)
    session = FakeSession([FakeResult(scalar=30), FakeResult(rows=[{"requested_at": oldest}])])

    async def run():
        return await ratelimit.cho_phep(session, "ip:127.0.0.1", "/audio/tts")

    allowed, retry_after = asyncio.run(run())
    assert not allowed
    assert 1 <= retry_after <= 60
    assert len(session.calls) == 2
    assert session.commits == 0


def test_localization_upsert_uses_existing_unique_key_and_queues_audio(monkeypatch):
    session = FakeSession()
    poi_id = uuid4()
    queued = []

    async def fake_xep_viec(poi_id_arg, lang):
        queued.append((poi_id_arg, lang))
        return "task-id"

    monkeypatch.setattr(tasks.quan_ly_tasks, "xep_viec", fake_xep_viec)

    async def run():
        return await localization.luu_ban_dich(
            session, poi_id, "en", "Translated", "Translated text"
        )

    result = asyncio.run(run())
    assert result["poi_id"] == poi_id
    assert result["lang"] == "en"
    assert "FOR UPDATE" in session.calls[0][0]
    assert "ON CONFLICT (poi_id, language_code)" in session.calls[1][0]
    assert session.calls[1][1]["name"] == "Translated"
    assert session.calls[1][1]["readiness"] == "ready"
    assert "UPDATE pois" in session.calls[2][0]
    assert queued == [(str(poi_id), "en")]
    assert session.commits == 1


def test_audio_completion_updates_localization_without_publishing():
    session = FakeSession()
    poi_id = uuid4()

    async def run():
        await audio_svc.hoan_tat_audio(
            session, poi_id, "en", "/static/audio/example.mp3?v=123&l=en"
        )

    asyncio.run(run())
    assert len(session.calls) == 3
    assert "FOR UPDATE" in session.calls[0][0]
    assert "UPDATE poi_localizations" in session.calls[1][0]
    assert session.calls[1][1]["audio_storage_key"] == "example.mp3"
    assert "UPDATE pois" in session.calls[2][0]
    assert session.calls[2][1]["poi_id"] == poi_id
    assert "is_active" not in session.calls[2][0]
    assert "publication_status" not in session.calls[2][0]
    assert session.commits == 1


def test_sync_cursor_uses_transactional_state_table():
    session = FakeSession([FakeResult(scalar=123456)])

    async def run():
        return await sync.lay_phien_ban(session)

    assert asyncio.run(run()) == 123456
    assert "FROM poi_sync_state" in session.calls[0][0]
    assert "singleton IS TRUE" in session.calls[0][0]
    assert "MAX(updated_at)" not in session.calls[0][0]


def test_audio_task_insert_uses_required_localization_foreign_key(monkeypatch):
    localization_id = uuid4()
    session = FakeSession([FakeResult(scalar=localization_id), FakeResult()])

    class FakeContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            return False

    manager = tasks.QuanLyTasks()
    manager.gan_db(lambda: FakeContext())

    async def no_op(_task_id):
        return None

    monkeypatch.setattr(manager, "_chay", no_op)

    async def run():
        return await manager.xep_viec(str(uuid4()), "vi")

    task_id = asyncio.run(run())
    assert len(task_id) == 32
    assert "JOIN poi_localizations" in session.calls[0][0]
    assert "INSERT INTO audio_tasks" in session.calls[2][0]
    assert session.calls[2][1]["localization_id"] == localization_id
    assert session.commits == 1


def test_audio_pack_reads_published_postgres_assets():
    session = FakeSession(
        [
            FakeResult(
                rows=[
                    {
                        "url": "/static/audio/example.mp3",
                        "sha256": "a" * 64,
                        "bytes": 42,
                    }
                ]
            )
        ]
    )

    async def run():
        return await maps.manifest_audio_pack(session, "en")

    assert asyncio.run(run()) == {
        "lang": "en",
        "files": [
            {
                "url": "/static/audio/example.mp3",
                "sha256": "a" * 64,
                "bytes": 42,
            }
        ],
    }
    assert "offline_pack_assets" in session.calls[0][0]
    assert "offline_packs" in session.calls[0][0]


def _client(session, *routers):
    app = FastAPI()
    for router in routers:
        app.include_router(router)

    async def fake_db():
        yield session

    async def fake_user():
        return {
            "username": "tester",
            "role": "admin",
            "permissions": ["poi:update", "user:update"],
        }

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[auth.lay_user_hien_tai] = fake_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_audio_on_demand_endpoint_uses_uuid_and_postgres(monkeypatch, tmp_path):
    poi_id = uuid4()
    audio_file = tmp_path / "voice.mp3"
    audio_file.write_bytes(b"mp3")
    session = FakeSession(
        [
            FakeResult(scalar=0),
            FakeResult(),
            FakeResult(rows=[{"name": "Name", "description": "Description", "lang": "en"}]),
            FakeResult(),
            FakeResult(),
        ]
    )

    async def fake_audio(_text, _lang):
        return audio_file, False

    monkeypatch.setattr(audio_router, "tao_mp3_cached", fake_audio)

    async def run():
        async with _client(session, audio_router.router) as client:
            return await client.post("/audio/on-demand", json={"poi_id": str(poi_id), "lang": "en"})

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json()["poi_id"] == str(poi_id)
    assert "FROM poi_localizations" in session.calls[2][0]


def test_tts_endpoint_rate_limits_through_postgres(monkeypatch, tmp_path):
    audio_file = tmp_path / "tts.mp3"
    audio_file.write_bytes(b"mp3-bytes")
    session = FakeSession([FakeResult(scalar=0), FakeResult()])

    async def fake_audio(_text, _lang):
        return audio_file, False

    monkeypatch.setattr(audio_router, "tao_mp3_cached", fake_audio)

    async def run():
        async with _client(session, audio_router.router) as client:
            return await client.post("/audio/tts", json={"text": "Hi", "lang": "en"})

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.content == b"mp3-bytes"
    assert response.headers["X-Cache"] == "MISS"
    assert "localization_request_logs" in session.calls[0][0]


def test_audio_task_list_endpoint_maps_postgres_columns_to_api_contract():
    task_id = uuid4()
    session = FakeSession(
        [
            FakeResult(
                rows=[
                    {
                        "task_id": str(task_id),
                        "poi_id": "poi-uuid",
                        "lang": "en",
                        "status": "running",
                        "progress": 50,
                        "loi": None,
                        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
                    }
                ]
            )
        ]
    )

    async def run():
        async with _client(session, audio_router.router) as client:
            return await client.get("/audio/tasks")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json()[0]["task_id"] == task_id.hex
    assert response.json()[0]["status"] == "running"
    assert response.json()[0]["updated_at"] == "2026-01-01T00:00:00+00:00"
    assert "FROM audio_tasks" in session.calls[0][0]


def test_localization_endpoint_keeps_permission_and_upsert_flow(monkeypatch):
    poi_id = uuid4()
    session = FakeSession(
        [
            FakeResult(scalar=0),
            FakeResult(),
            FakeResult(rows=[{"id": poi_id}]),
            FakeResult(),
            FakeResult(),
            FakeResult(),
        ]
    )
    queued = []

    async def fake_xep_viec(poi_id_arg, lang):
        queued.append((poi_id_arg, lang))
        return "task-id"

    monkeypatch.setattr(tasks.quan_ly_tasks, "xep_viec", fake_xep_viec)

    async def run():
        async with _client(session, localizations_router.router) as client:
            return await client.post(
                "/localizations/on-demand",
                json={
                    "poi_id": str(poi_id),
                    "lang": "ja",
                    "name": "名称",
                    "description": "説明",
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json() == {"poi_id": str(poi_id), "lang": "ja", "name": "名称"}
    assert queued == [(str(poi_id), "ja")]
    assert "ON CONFLICT (poi_id, language_code)" in session.calls[4][0]


def test_warmup_status_endpoint_lists_missing_language_pairs():
    poi_id = str(uuid4())
    session = FakeSession([FakeResult(rows=[{"poi_id": poi_id, "lang": "en"}])])

    async def run():
        async with _client(session, warmup_router.router) as client:
            return await client.get("/localizations/warmup-status")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json() == {
        "tong": 1,
        "thieu": [{"poi_id": poi_id, "lang": "en"}],
    }
    assert "LEFT JOIN poi_localizations" in session.calls[0][0]


def test_audio_pack_endpoint_returns_postgres_asset_manifest():
    session = FakeSession(
        [
            FakeResult(
                rows=[
                    {
                        "url": "/static/audio/example.mp3",
                        "sha256": "b" * 64,
                        "bytes": 18,
                    }
                ]
            )
        ]
    )

    async def run():
        async with _client(session, maps_router.router) as client:
            return await client.get("/maps/audio-pack?lang=en")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json()["files"][0]["url"] == "/static/audio/example.mp3"
    assert "offline_pack_assets" in session.calls[0][0]
