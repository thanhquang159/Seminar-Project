"""Owner-scoped menu and menu-item management."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import YeuCauOwnerDuyet
from app.postgres import get_db
from app.services.pg_identity import resolve_user_id

router = APIRouter(tags=["owner"])


class MenuCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(default="Menu chính", min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class MenuItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=2048)
    is_available: bool = True
    sort_order: int = Field(default=0, ge=0, le=2_147_483_647)


class MenuItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    image_url: str | None = Field(default=None, max_length=2048)
    is_available: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=2_147_483_647)


async def require_approved_owner(user: dict = YeuCauOwnerDuyet) -> dict:
    if user.get("role") != "poi_owner":
        raise HTTPException(status_code=403, detail="Chỉ chủ quán được quản lý menu")
    return user


YeuCauChuQuanDuyet = Depends(require_approved_owner)


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None


def _item_values(item: dict) -> dict:
    return {
        "id": item["id"],
        "menu_id": item["menu_id"],
        "name": item["name"],
        "description": item["description"],
        "price": item["price"],
        "currency_code": item["currency_code"],
        "image_url": item["image_url"],
        "is_available": item["is_available"],
        "sort_order": item["sort_order"],
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


@router.get("/owner/pois/{poi_id}/menus", summary="Danh sách menu và món của tôi")
async def list_poi_menus(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauChuQuanDuyet,
) -> list[dict]:
    owner_id = await resolve_user_id(db, user)
    poi_uuid = _parse_uuid(poi_id)
    result = await db.execute(
        text(
            """
            SELECT m.id::text AS id, m.poi_id::text AS poi_id,
                   m.name, m.description, m.is_active, m.created_at, m.updated_at,
                   COALESCE(
                       jsonb_agg(
                           jsonb_build_object(
                               'id', mi.id::text,
                               'menu_id', mi.menu_id::text,
                               'name', mi.name,
                               'description', mi.description,
                               'price', mi.price,
                               'currency_code', mi.currency_code,
                               'image_url', mi.image_url,
                               'is_available', mi.is_available,
                               'sort_order', mi.sort_order,
                               'created_at', mi.created_at,
                               'updated_at', mi.updated_at
                           ) ORDER BY mi.sort_order, mi.created_at
                       ) FILTER (WHERE mi.id IS NOT NULL),
                       '[]'::jsonb
                   ) AS items
            FROM menus AS m
            JOIN pois AS p ON p.id = m.poi_id
            LEFT JOIN menu_items AS mi ON mi.menu_id = m.id
            WHERE p.id = :poi_id AND p.owner_id = :owner_id
            GROUP BY m.id
            ORDER BY m.name, m.id
            """
        ),
        {"poi_id": poi_uuid, "owner_id": owner_id},
    )
    return [dict(row) for row in result.mappings().all()]


@router.post(
    "/owner/pois/{poi_id}/menus",
    status_code=201,
    summary="Tạo menu cho quán của tôi",
)
async def create_poi_menu(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: MenuCreate | None = None,
    user: dict = YeuCauChuQuanDuyet,
) -> dict:
    owner_id = await resolve_user_id(db, user)
    poi_uuid = _parse_uuid(poi_id)
    menu = body or MenuCreate()
    result = await db.execute(
        text(
            """
            INSERT INTO menus (poi_id, name, description, is_active)
            SELECT p.id, :name, :description, :is_active
            FROM pois AS p
            WHERE p.id = :poi_id AND p.owner_id = :owner_id
            RETURNING id::text AS id, poi_id::text AS poi_id, name,
                      description, is_active, created_at, updated_at
            """
        ),
        {
            "poi_id": poi_uuid,
            "owner_id": owner_id,
            **menu.model_dump(),
        },
    )
    created = result.mappings().one_or_none()
    if created is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    await db.commit()
    return dict(created)


@router.get("/owner/menus/{menu_id}/items", summary="Danh sách món trong menu của tôi")
async def list_menu_items(
    menu_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauChuQuanDuyet,
) -> list[dict]:
    owner_id = await resolve_user_id(db, user)
    menu_uuid = _parse_uuid(menu_id)
    result = await db.execute(
        text(
            """
            SELECT mi.id::text AS id, mi.menu_id::text AS menu_id,
                   mi.name, mi.description, mi.price, mi.currency_code,
                   mi.image_url, mi.is_available, mi.sort_order,
                   mi.created_at, mi.updated_at
            FROM menu_items AS mi
            JOIN menus AS m ON m.id = mi.menu_id
            JOIN pois AS p ON p.id = m.poi_id
            WHERE m.id = CAST(:menu_id AS uuid) AND p.owner_id = :owner_id
            ORDER BY mi.sort_order, mi.created_at, mi.id
            """
        ),
        {"menu_id": menu_uuid, "owner_id": owner_id},
    )
    return [dict(row) for row in result.mappings().all()]


@router.post(
    "/owner/menus/{menu_id}/items",
    status_code=201,
    summary="Thêm món vào menu của tôi",
)
async def create_menu_item(
    menu_id: str,
    body: MenuItemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauChuQuanDuyet,
) -> dict:
    owner_id = await resolve_user_id(db, user)
    menu_uuid = _parse_uuid(menu_id)
    result = await db.execute(
        text(
            """
            INSERT INTO menu_items (
                menu_id, name, description, price, image_url, is_available, sort_order
            )
            SELECT m.id, :name, :description, :price, :image_url, :is_available, :sort_order
            FROM menus AS m
            JOIN pois AS p ON p.id = m.poi_id
            WHERE m.id = CAST(:menu_id AS uuid) AND p.owner_id = :owner_id
            RETURNING id::text AS id, menu_id::text AS menu_id, name, description,
                      price, currency_code, image_url, is_available, sort_order,
                      created_at, updated_at
            """
        ),
        {
            "menu_id": menu_uuid,
            "owner_id": owner_id,
            **body.model_dump(),
        },
    )
    item = result.mappings().one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy menu")
    await db.commit()
    return _item_values(dict(item))


@router.put(
    "/owner/menus/{menu_id}/items/{item_id}",
    summary="Cập nhật món của tôi",
)
async def update_menu_item(
    menu_id: str,
    item_id: str,
    body: MenuItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauChuQuanDuyet,
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Cần ít nhất một trường để cập nhật")
    if any(
        key in updates and updates[key] is None for key in ("name", "is_available", "sort_order")
    ):
        raise HTTPException(status_code=422, detail="Trường không được để trống")

    owner_id = await resolve_user_id(db, user)
    menu_uuid = _parse_uuid(menu_id)
    item_uuid = _parse_uuid(item_id)
    assignments = ", ".join(f"{key} = :{key}" for key in updates)
    result = await db.execute(
        text(
            f"""
            UPDATE menu_items AS mi
            SET {assignments}, updated_at = now()
            FROM menus AS m
            JOIN pois AS p ON p.id = m.poi_id
            WHERE mi.id = CAST(:item_id AS uuid)
              AND mi.menu_id = m.id AND m.id = :menu_id
              AND p.owner_id = :owner_id
            RETURNING mi.id::text AS id, mi.menu_id::text AS menu_id,
                      mi.name, mi.description, mi.price, mi.currency_code,
                      mi.image_url, mi.is_available, mi.sort_order,
                      mi.created_at, mi.updated_at
            """
        ),
        {
            "item_id": item_uuid,
            "menu_id": menu_uuid,
            "owner_id": owner_id,
            **updates,
        },
    )
    item = result.mappings().one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy món")
    await db.commit()
    return _item_values(dict(item))


@router.delete(
    "/owner/menus/{menu_id}/items/{item_id}",
    summary="Xóa món của tôi",
)
async def delete_menu_item(
    menu_id: str,
    item_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauChuQuanDuyet,
) -> dict:
    owner_id = await resolve_user_id(db, user)
    menu_uuid = _parse_uuid(menu_id)
    item_uuid = _parse_uuid(item_id)
    result = await db.execute(
        text(
            """
            DELETE FROM menu_items AS mi
            USING menus AS m
            JOIN pois AS p ON p.id = m.poi_id
            WHERE mi.id = CAST(:item_id AS uuid)
              AND mi.menu_id = m.id AND m.id = :menu_id
              AND p.owner_id = :owner_id
            RETURNING mi.id::text AS id
            """
        ),
        {"item_id": item_uuid, "menu_id": menu_uuid, "owner_id": owner_id},
    )
    if result.mappings().one_or_none() is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy món")
    await db.commit()
    return {"ok": True}
