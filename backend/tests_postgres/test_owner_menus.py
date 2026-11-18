import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app import auth
from app.postgres import get_db
from app.routers import owner_menus


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def one_or_none(self):
        return self._rows[0] if self._rows else None

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


def _item_row(item_id, menu_id):
    return {
        "id": str(item_id),
        "menu_id": str(menu_id),
        "name": "Bánh mì",
        "description": "Bánh mì thịt",
        "price": Decimal("25000.00"),
        "currency_code": "VND",
        "image_url": "https://example.test/banh-mi.jpg",
        "is_available": True,
        "sort_order": 0,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def test_menu_listing_returns_only_the_owned_poi_menus_with_items():
    owner_id = uuid4()
    poi_id = uuid4()
    session = FakeSession(
        FakeResult(
            [
                {
                    "id": str(uuid4()),
                    "poi_id": str(uuid4()),
                    "name": "Món chính",
                    "description": None,
                    "is_active": True,
                    "created_at": None,
                    "updated_at": None,
                    "items": [_item_row(uuid4(), uuid4())],
                }
            ]
        )
    )

    menus = asyncio.run(
        owner_menus.list_poi_menus(
            str(poi_id),
            session,
            {"id": str(owner_id), "role": "poi_owner"},
        )
    )

    sql, params = session.statements[0]
    assert len(menus) == 1
    assert menus[0]["items"][0]["name"] == "Bánh mì"
    assert "JOIN pois AS p ON p.id = m.poi_id" in sql
    assert "WHERE p.id = :poi_id AND p.owner_id = :owner_id" in sql
    assert "ORDER BY m.name, m.id" in sql
    assert "ORDER BY p.name" not in sql
    assert params == {"poi_id": poi_id, "owner_id": owner_id}


def test_create_default_menu_requires_poi_ownership():
    owner_id = uuid4()
    poi_id = uuid4()
    menu_id = uuid4()
    session = FakeSession(
        FakeResult(
            [
                {
                    "id": str(menu_id),
                    "poi_id": str(poi_id),
                    "name": "Menu chính",
                    "description": None,
                    "is_active": True,
                    "created_at": None,
                    "updated_at": None,
                }
            ]
        )
    )

    result = asyncio.run(
        owner_menus.create_poi_menu(
            str(poi_id),
            session,
            None,
            {"id": str(owner_id), "role": "poi_owner"},
        )
    )

    sql, params = session.statements[0]
    assert result["id"] == str(menu_id)
    assert "INSERT INTO menus (poi_id, name, description, is_active)" in sql
    assert "WHERE p.id = :poi_id AND p.owner_id = :owner_id" in sql
    assert params == {
        "poi_id": poi_id,
        "owner_id": owner_id,
        "name": "Menu chính",
        "description": None,
        "is_active": True,
    }
    assert session.committed


def test_create_menu_item_scopes_to_authenticated_owner_and_existing_columns():
    owner_id = uuid4()
    menu_id = uuid4()
    item_id = uuid4()
    session = FakeSession(FakeResult([_item_row(item_id, menu_id)]))
    body = owner_menus.MenuItemCreate(
        name="Bánh mì",
        description="Bánh mì thịt",
        price="25000.00",
        image_url="https://example.test/banh-mi.jpg",
    )

    result = asyncio.run(
        owner_menus.create_menu_item(
            str(menu_id),
            body,
            session,
            {"id": str(owner_id), "role": "poi_owner"},
        )
    )

    sql, params = session.statements[0]
    assert result["id"] == str(item_id)
    assert result["price"] == Decimal("25000.00")
    assert "INSERT INTO menu_items" in sql
    assert "JOIN pois AS p ON p.id = m.poi_id" in sql
    assert "p.owner_id = :owner_id" in sql
    assert params["owner_id"] == owner_id
    assert params["menu_id"] == menu_id
    assert body.model_dump().get("owner_id") is None
    assert session.committed


def test_menu_item_input_rejects_arbitrary_owner_id():
    with pytest.raises(ValidationError):
        owner_menus.MenuItemCreate(name="Bánh mì", owner_id=str(uuid4()))


def test_update_menu_item_is_owner_scoped_and_only_updates_supplied_fields():
    owner_id = uuid4()
    item_id = uuid4()
    menu_id = uuid4()
    session = FakeSession(FakeResult([_item_row(item_id, menu_id)]))

    asyncio.run(
        owner_menus.update_menu_item(
            str(menu_id),
            str(item_id),
            owner_menus.MenuItemUpdate(is_available=False),
            session,
            {"id": str(owner_id), "role": "poi_owner"},
        )
    )

    sql, params = session.statements[0]
    assert "SET is_available = :is_available, updated_at = now()" in sql
    assert "m.id = :menu_id" in sql
    assert "p.owner_id = :owner_id" in sql
    assert params == {
        "item_id": item_id,
        "menu_id": menu_id,
        "owner_id": owner_id,
        "is_available": False,
    }
    assert session.committed


def test_update_menu_item_rejects_empty_patch_and_null_required_fields():
    owner_id = uuid4()
    with pytest.raises(HTTPException) as empty_error:
        asyncio.run(
            owner_menus.update_menu_item(
                str(uuid4()),
                str(uuid4()),
                owner_menus.MenuItemUpdate(),
                FakeSession(),
                {"id": str(owner_id), "role": "poi_owner"},
            )
        )
    assert empty_error.value.status_code == 422

    with pytest.raises(HTTPException) as null_error:
        asyncio.run(
            owner_menus.update_menu_item(
                str(uuid4()),
                str(uuid4()),
                owner_menus.MenuItemUpdate(is_available=None),
                FakeSession(),
                {"id": str(owner_id), "role": "poi_owner"},
            )
        )
    assert null_error.value.status_code == 422


def test_update_and_delete_hide_items_not_owned_by_authenticated_owner():
    owner_id = uuid4()
    item_id = uuid4()
    menu_id = uuid4()

    with pytest.raises(HTTPException) as update_error:
        asyncio.run(
            owner_menus.update_menu_item(
                str(menu_id),
                str(item_id),
                owner_menus.MenuItemUpdate(name="Đổi tên"),
                FakeSession(FakeResult()),
                {"id": str(owner_id), "role": "poi_owner"},
            )
        )
    assert update_error.value.status_code == 404

    session = FakeSession(FakeResult())
    with pytest.raises(HTTPException) as delete_error:
        asyncio.run(
            owner_menus.delete_menu_item(
                str(menu_id),
                str(item_id),
                session,
                {"id": str(owner_id), "role": "poi_owner"},
            )
        )
    sql, params = session.statements[0]
    assert delete_error.value.status_code == 404
    assert "p.owner_id = :owner_id" in sql
    assert params == {"item_id": item_id, "menu_id": menu_id, "owner_id": owner_id}
    assert not session.committed


def test_menu_routes_require_owner_role():
    with pytest.raises(HTTPException) as error:
        asyncio.run(owner_menus.require_approved_owner({"role": "admin"}))
    assert error.value.status_code == 403


def test_menu_endpoints_expose_owner_listing_and_create_contract(monkeypatch):
    owner_id = uuid4()
    poi_id = uuid4()
    menu_id = uuid4()
    item_id = uuid4()
    session = FakeSession(
        FakeResult(scalar=owner_id),
        FakeResult(
            [
                {
                    "id": str(menu_id),
                    "poi_id": str(uuid4()),
                    "name": "Món chính",
                    "description": None,
                    "is_active": True,
                    "created_at": None,
                    "updated_at": None,
                    "items": [],
                }
            ]
        ),
        FakeResult(scalar=owner_id),
        FakeResult(
            [
                {
                    "id": str(menu_id),
                    "poi_id": str(poi_id),
                    "name": "Menu chính",
                    "description": None,
                    "is_active": True,
                    "created_at": None,
                    "updated_at": None,
                }
            ]
        ),
        FakeResult(scalar=owner_id),
        FakeResult([_item_row(item_id, menu_id)]),
    )
    app = FastAPI()
    app.include_router(owner_menus.router)

    async def get_test_session():
        yield session

    app.dependency_overrides[get_db] = get_test_session
    app.dependency_overrides[auth.lay_user_hien_tai] = lambda: {
        "username": "owner@example.test",
        "role": "poi_owner",
        "permissions": [],
    }
    monkeypatch.setattr(
        auth,
        "lay_user_theo_ten",
        lambda username, db: asyncio.sleep(
            0,
            result={
                "is_poi_owner_verified": True,
            },
        ),
    )

    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            listing = await client.get(f"/owner/pois/{poi_id}/menus")
            created_menu = await client.post(f"/owner/pois/{poi_id}/menus")
            created = await client.post(
                f"/owner/menus/{menu_id}/items",
                json={"name": "Bánh mì", "price": 25000},
            )
            return listing, created_menu, created

    listing, created_menu, created = asyncio.run(request())
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == str(menu_id)
    assert created_menu.status_code == 201
    assert created_menu.json()["name"] == "Menu chính"
    assert created.status_code == 201
    assert created.json()["id"] == str(item_id)
