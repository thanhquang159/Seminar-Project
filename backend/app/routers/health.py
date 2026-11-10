from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.postgres import get_db

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    description="Kiểm tra kết nối PostgreSQL; trả 503 khi database không sẵn sàng.",
)
async def health_check(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        database_name = await db.scalar(text("SELECT current_database()"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "database": "disconnected"},
        )
    return {"status": "ok", "database": "connected", "database_name": database_name}
