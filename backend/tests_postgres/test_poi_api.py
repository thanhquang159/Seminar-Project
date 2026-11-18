import asyncio
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.pois import router
from app.postgres import get_db


class FakeResult:
    def __init__(self, rows=None, scalar=0):
        self._rows = rows or []
        self._scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalar_one(self):
        return self._scalar


class FakeSession:
    def __init__(self, rows=None, version=123, changes=None, count=0):
        self.rows = rows or []
        self.version = version
        self.changes = changes or []
        self.count = count
        self.statements = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if "SELECT count(*) FROM pois" in sql:
            return FakeResult(scalar=self.count)
        if "FROM poi_sync_state" in sql:
            return FakeResult(scalar=self.version)
        if "FROM latest_changes" in sql:
            return FakeResult(rows=self.changes)
        return FakeResult(rows=self.rows)


def create_client(session):
    app = FastAPI()
    app.include_router(router)

    async def fake_db():
        yield session

    app.dependency_overrides[get_db] = fake_db
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


def test_list_pois_uses_postgres_response_shape():
    poi_id = str(uuid4())
    session = FakeSession(
        rows=[
            {
                "id": poi_id,
                "name": "Quán ăn",
                "description": "Món địa phương",
                "lat": 10.76,
                "lng": 106.70,
                "trigger_radius": 30,
                "audio_priority": 0,
                "images": [],
                "lang": "vi",
                "is_fallback": True,
                "audio_url": None,
            }
        ]
    )

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi?lang=vi")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()[0]["id"] == poi_id
    assert response.json()[0]["name"] == "Quán ăn"
    assert "FROM pois AS p" in session.statements[0][0]
    assert "p.publication_status = 'published'" in session.statements[0][0]


def test_count_pois_counts_active_published_pois():
    session = FakeSession(count=7)

    async def request():
        async with create_client(session) as client:
            count = await client.get("/poi/count")
            return count

    count = asyncio.run(request())
    assert count.status_code == 200
    assert count.json() == {"count": 7}
    sql = session.statements[0][0]
    assert "p.is_active IS TRUE" in sql
    assert "p.publication_status = 'published'" in sql
    assert len(session.statements) == 1


def test_load_all_supports_etag_without_second_data_query():
    session = FakeSession(rows=[], version=456)

    async def request():
        async with create_client(session) as client:
            first = await client.get("/poi/load-all?lang=en")
            second = await client.get(
                "/poi/load-all?lang=en", headers={"If-None-Match": '"456-en"'}
            )
            return first, second

    first, second = asyncio.run(request())
    assert first.status_code == 200
    assert first.headers["etag"] == '"456-en"'
    assert first.json() == {"version": 456, "sync_cursor": 456, "pois": []}
    assert second.status_code == 304
    assert len(session.statements) == 3


def test_detail_rejects_non_uuid_id_without_querying_database():
    session = FakeSession()

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/not-a-uuid")

    response = asyncio.run(request())
    assert response.status_code == 400
    assert session.statements == []


def test_detail_returns_matching_poi():
    poi_id = str(uuid4())
    session = FakeSession(
        rows=[
            {
                "id": poi_id,
                "name": "Quán ăn",
                "description": "",
                "lat": 10.76,
                "lng": 106.70,
                "trigger_radius": 30,
                "audio_priority": 0,
                "images": [],
                "lang": "vi",
                "is_fallback": True,
                "audio_url": None,
            }
        ]
    )

    async def request():
        async with create_client(session) as client:
            return await client.get(f"/poi/{poi_id}")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()["id"] == poi_id
    assert session.statements[0][1]["poi_id"].hex == UUID(poi_id).hex


def test_public_menus_only_return_active_menus_for_published_pois():
    poi_id = str(uuid4())
    menu_id = str(uuid4())
    item_id = str(uuid4())
    session = FakeSession(
        rows=[
            {
                "id": menu_id,
                "poi_id": poi_id,
                "name": "Menu chính",
                "description": None,
                "is_active": True,
                "items": [
                    {
                        "id": item_id,
                        "menu_id": menu_id,
                        "name": "Bánh mì",
                        "price": 25000,
                        "currency_code": "VND",
                        "is_available": True,
                    }
                ],
            }
        ]
    )

    async def request():
        async with create_client(session) as client:
            return await client.get(f"/poi/{poi_id}/menus")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()[0]["items"][0]["id"] == item_id
    sql, params = session.statements[0]
    assert "p.is_active IS TRUE" in sql
    assert "p.publication_status = 'published'" in sql
    assert "m.is_active IS TRUE" in sql
    assert "GROUP BY m.id" in sql
    assert "ORDER BY m.name, m.id" in sql
    assert params["poi_id"].hex == UUID(poi_id).hex


def test_public_menu_endpoint_rejects_non_uuid_id_without_querying_database():
    session = FakeSession()

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/not-a-uuid/menus")

    response = asyncio.run(request())
    assert response.status_code == 400
    assert session.statements == []


def test_offline_menus_returns_only_published_pois_and_active_menus():
    poi_id = str(uuid4())
    menu_id = str(uuid4())
    session = FakeSession(
        rows=[
            {
                "id": menu_id,
                "poi_id": poi_id,
                "name": "Menu chính",
                "description": None,
                "items": [],
            }
        ]
    )

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/menus")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()[0]["poi_id"] == poi_id
    sql = session.statements[0][0]
    assert "p.is_active IS TRUE" in sql
    assert "p.publication_status = 'published'" in sql
    assert "m.is_active IS TRUE" in sql
    assert "GROUP BY m.id" in sql


def test_delta_returns_tombstones_and_current_pois_after_cursor():
    poi_id = str(uuid4())
    removed_id = str(uuid4())
    updated_poi = {
        "changed_poi_id": poi_id,
        "operation": "upsert",
        "id": poi_id,
        "name": "Quán mới",
        "description": "",
        "lat": 10.76,
        "lng": 106.70,
        "trigger_radius": 30,
        "audio_priority": 0,
        "images": [],
        "lang": "vi",
        "is_fallback": False,
        "audio_url": None,
    }
    session = FakeSession(
        version=789,
        changes=[
            updated_poi,
            {"changed_poi_id": removed_id, "operation": "delete"},
        ],
    )

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/delta?updated_after=123")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json() == {
        "version": 789,
        "sync_cursor": 789,
        "updated": [
            {
                key: value
                for key, value in updated_poi.items()
                if key not in {"changed_poi_id", "operation"}
            }
        ],
        "removed_poi_ids": [removed_id],
    }
    delta_sql, params = session.statements[1]
    assert "FROM poi_sync_changes AS c" in delta_sql
    assert "DISTINCT ON (c.poi_id)" in delta_sql
    assert "c.change_cursor > :updated_after" in delta_sql
    assert params["updated_after"] == 123


def test_delta_cursor_does_not_regress_when_active_poi_is_removed():
    removed_id = str(uuid4())
    session = FakeSession(
        version=790,
        changes=[{"changed_poi_id": removed_id, "operation": "delete"}],
    )

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/delta?updated_after=789")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()["sync_cursor"] == 790
    assert response.json()["removed_poi_ids"] == [removed_id]
    assert "FROM poi_sync_state" in session.statements[0][0]
    assert "WHERE c.change_cursor > :updated_after" in session.statements[1][0]


def test_delta_treats_unpublished_active_poi_as_removed():
    poi_id = str(uuid4())
    session = FakeSession(
        version=790,
        changes=[
            {
                "changed_poi_id": poi_id,
                "operation": "upsert",
                "id": None,
            }
        ],
    )

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/delta?updated_after=789")

    response = asyncio.run(request())
    assert response.status_code == 200
    assert response.json()["updated"] == []
    assert response.json()["removed_poi_ids"] == [poi_id]
    assert "p.publication_status = 'published'" in session.statements[1][0]


def test_delta_rejects_a_cursor_newer_than_database_state():
    session = FakeSession(version=789)

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/delta?updated_after=790")

    response = asyncio.run(request())
    assert response.status_code == 400
    assert len(session.statements) == 1


def test_nearby_uses_existing_postgis_column():
    session = FakeSession(rows=[])

    async def request():
        async with create_client(session) as client:
            return await client.get("/poi/nearby?lat=10.76&lng=106.70")

    response = asyncio.run(request())
    assert response.status_code == 200
    sql = session.statements[0][0]
    assert "ST_DWithin" in sql
    assert "p.location" in sql
