from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.postgres import get_db

router = APIRouter(prefix="/health", tags=["Health Check"])


@router.get("/database")
async def check_database(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        result = await db.execute(
            text("""
                SELECT
                    current_database() AS database_name,
                    (
                        SELECT extversion
                        FROM pg_extension
                        WHERE extname = 'postgis'
                    ) AS postgis_version
            """)
        )

        db_info = result.mappings().one()

        table_result = await db.execute(
            text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
            """)
        )

        table_count = table_result.scalar_one()

        return {
            "status": "success",
            "message": "Connected to PostgreSQL successfully!",
            "database": db_info["database_name"],
            "postgis": db_info["postgis_version"],
            "total_tables": table_count,
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": "Cannot connect to PostgreSQL",
            },
        ) from None
