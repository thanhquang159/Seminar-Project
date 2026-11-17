"""PostGIS-backed nearby and hotset POI routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pois import _POI_FIELDS, _POI_JOINS
from app.limits import LangQuery
from app.postgres import get_db

router = APIRouter(prefix="/poi", tags=["poi-geo"])


async def gan_khoang_cach(
    db: AsyncSession,
    lat: float,
    lng: float,
    gioi_han_m: float,
    lang: str,
) -> list[dict]:
    """Return public POIs ordered by their PostGIS geography distance."""
    result = await db.execute(
        text(
            f"""
            SELECT {_POI_FIELDS},
                   ST_Distance(
                       COALESCE(
                           p.location,
                           ST_SetSRID(ST_MakePoint(p.longitude, p.latitude), 4326)::geography
                       ),
                       ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                   )::double precision AS distance_m
            FROM pois AS p
            {_POI_JOINS}
            WHERE p.is_active IS TRUE
              AND p.publication_status = 'published'
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
        ),
        {"lang": lang, "lat": lat, "lng": lng, "radius_m": gioi_han_m},
    )
    pois = [dict(row) for row in result.mappings().all()]
    for poi in pois:
        poi["distance_m"] = round(float(poi["distance_m"]), 1)
    return pois


@router.get("/nearby", summary="POI gần nhất quanh vị trí")
async def gan_day(
    db: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query()],
    lng: Annotated[float, Query()],
    radius_m: Annotated[float, Query()] = 1500,
    lang: LangQuery = "vi",
) -> list[dict]:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="Tọa độ không hợp lệ")
    if not (0 < radius_m <= 5000):
        raise HTTPException(status_code=400, detail="Bán kính 1-5000m")
    return await gan_khoang_cach(db, lat, lng, radius_m, lang)


@router.get("/hotset", summary="10 POI gần nhất trong 1.5km để hâm nóng")
async def hotset(
    db: Annotated[AsyncSession, Depends(get_db)],
    lat: Annotated[float, Query()],
    lng: Annotated[float, Query()],
    lang: LangQuery = "vi",
) -> list[dict]:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(status_code=400, detail="Tọa độ không hợp lệ")
    nearby = await gan_khoang_cach(db, lat, lng, 1500, lang)
    return nearby[:10]
