"""API đọc POI dùng các bảng PostgreSQL hiện có."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.limits import LangQuery
from app.postgres import get_db
from app.services.sync import lay_phien_ban

router = APIRouter(prefix="/poi", tags=["poi"])

_POI_FIELDS = """
    p.id::text AS id,
    COALESCE(loc.localized_name, p.name) AS name,
    COALESCE(loc.localized_description, p.description, '') AS description,
    p.latitude::double precision AS lat,
    p.longitude::double precision AS lng,
    p.trigger_radius_m AS trigger_radius,
    p.audio_priority,
    COALESCE(img.images, '[]'::json) AS images,
    COALESCE(loc.language_code, 'vi') AS lang,
    (loc.language_code IS DISTINCT FROM :lang) AS is_fallback,
    CASE
        WHEN loc.language_code = 'vi' AND :lang <> 'vi' THEN NULL
        ELSE loc.audio_url
    END AS audio_url
"""

_POI_JOINS = """
LEFT JOIN LATERAL (
    SELECT l.language_code, l.localized_name, l.localized_description, l.audio_url
    FROM poi_localizations AS l
    WHERE l.poi_id = p.id
      AND (
          l.language_code = :lang
          OR (:lang <> 'en' AND l.language_code = 'en')
          OR (:lang <> 'vi' AND l.language_code = 'vi')
      )
    ORDER BY CASE
        WHEN l.language_code = :lang THEN 0
        WHEN l.language_code = 'en' THEN 1
        ELSE 2
    END
    LIMIT 1
) AS loc ON TRUE
LEFT JOIN LATERAL (
    SELECT json_agg(i.public_url ORDER BY i.sort_order, i.created_at)
           FILTER (WHERE i.public_url IS NOT NULL) AS images
    FROM poi_images AS i
    WHERE i.poi_id = p.id
) AS img ON TRUE
"""

_PUBLIC_FILTER = "p.is_active IS TRUE AND p.publication_status = 'published'"


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None


async def _fetch_pois(
    db: AsyncSession,
    lang: str,
    *,
    poi_id: UUID | None = None,
    limit: int,
) -> list[dict]:
    filters = [_PUBLIC_FILTER]
    params: dict[str, object] = {"lang": lang, "limit": limit}
    if poi_id is not None:
        filters.append("p.id = :poi_id")
        params["poi_id"] = poi_id
    query = text(
        f"SELECT {_POI_FIELDS} FROM pois AS p {_POI_JOINS} "
        f"WHERE {' AND '.join(filters)} ORDER BY p.id LIMIT :limit"
    )
    result = await db.execute(query, params)
    return [dict(row) for row in result.mappings().all()]


@router.get("", summary="Lấy danh sách POI")
async def lay_danh_sach(
    db: Annotated[AsyncSession, Depends(get_db)], lang: LangQuery = "vi"
) -> list[dict]:
    return await _fetch_pois(db, lang, limit=100)


@router.get("/count", summary="Lấy tổng số POI trên dashboard")
async def dem_poi() -> dict[str, int]:
    return {"count": 0}


@router.get("/load-all", summary="Tải toàn bộ POI kèm phiên bản sync")
async def tai_tat_ca(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: LangQuery = "vi",
) -> Response:
    version = await lay_phien_ban(db)
    etag = f'"{version}-{lang}"'
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    pois = await _fetch_pois(db, lang, limit=5000)
    return JSONResponse(
        content={"version": version, "sync_cursor": version, "pois": pois},
        headers={"ETag": etag},
    )


@router.get("/delta", summary="Chỉ tải phần đổi từ updated_after")
async def tai_delta(
    db: Annotated[AsyncSession, Depends(get_db)],
    updated_after: Annotated[int, Query(ge=0)],
    lang: LangQuery = "vi",
) -> dict:
    version = await lay_phien_ban(db)
    if updated_after > version:
        raise HTTPException(status_code=400, detail="Cursor mới hơn phiên bản dữ liệu hiện tại")

    result = await db.execute(
        text(
            f"""
            WITH latest_changes AS (
                SELECT DISTINCT ON (c.poi_id)
                       c.poi_id, c.operation, c.change_cursor
                FROM poi_sync_changes AS c
                WHERE c.change_cursor > :updated_after
                ORDER BY c.poi_id, c.change_cursor DESC
            )
            SELECT c.poi_id::text AS changed_poi_id,
                   c.operation,
                   {_POI_FIELDS}
            FROM latest_changes AS c
            LEFT JOIN pois AS p
              ON p.id = c.poi_id
             AND p.is_active IS TRUE
             AND p.publication_status = 'published'
            {_POI_JOINS}
            ORDER BY c.change_cursor
            """
        ),
        {"updated_after": updated_after, "lang": lang},
    )
    changes = result.mappings().all()
    updated = [
        {key: value for key, value in row.items() if key not in {"changed_poi_id", "operation"}}
        for row in changes
        if row["operation"] == "upsert" and row.get("id") is not None
    ]
    removed = [
        row["changed_poi_id"]
        for row in changes
        if row["operation"] == "delete" or row.get("id") is None
    ]
    return {
        "version": version,
        "sync_cursor": version,
        "updated": updated,
        "removed_poi_ids": removed,
    }


@router.get("/nearby", summary="POI gần nhất quanh vị trí")
async def gan_day(
    db: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_m: Annotated[float, Query(gt=0, le=5000)] = 1500,
    lang: LangQuery = "vi",
) -> list[dict]:
    query = text(
        f"""
        SELECT {_POI_FIELDS},
               ST_Distance(
                   COALESCE(
                       p.location,
                       ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography
                   ),
                   ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
               ) AS distance_m
        FROM pois AS p
        {_POI_JOINS}
        WHERE {_PUBLIC_FILTER}
          AND ST_DWithin(
              COALESCE(
                  p.location,
                  ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography
              ),
              ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
              :radius_m
          )
        ORDER BY distance_m, p.id
        LIMIT 100
        """
    )
    result = await db.execute(query, {"lang": lang, "lat": lat, "lng": lng, "radius_m": radius_m})
    return [dict(row) for row in result.mappings().all()]


@router.get("/hotset", summary="10 POI gần nhất trong 1.5km để hâm nóng")
async def hotset(
    db: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    lang: LangQuery = "vi",
) -> list[dict]:
    nearby = await gan_day(db, lat, lng, 1500, lang)
    return nearby[:10]


@router.get("/{poi_id}", summary="Lấy một POI theo id")
async def lay_mot(
    poi_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    lang: LangQuery = "vi",
) -> dict:
    rows = await _fetch_pois(db, lang, poi_id=_uuid(poi_id), limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy POI")
    return rows[0]
