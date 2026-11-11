"""API audio: TTS stream, on-demand dịch+TTS, tác vụ nền + SSE."""

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import YeuCauDangNhap, doi_quyen
from app.limits import MAX_TEXT_TTS, LangField
from app.postgres import get_db
from app.services.audio_svc import (
    NGON_NGU_AUDIO,
    THU_MUC_AUDIO,
    duong_audio_url,
    hoan_tat_audio,
    tao_mp3_cached,
)
from app.services.ratelimit import khoa_cho, kiem_tra
from app.services.tasks import quan_ly_tasks

router = APIRouter(prefix="/audio", tags=["audio"])
DuocQuanLyAudio = doi_quyen("user:update")


class TtsYeuCau(BaseModel):
    # SEC-001: không giới hạn thì mỗi text khác nhau sinh một file MP3 trong
    # static/audio/ và không bao giờ bị dọn — đủ vài trăm request là đầy đĩa.
    text: str = Field(min_length=1, max_length=MAX_TEXT_TTS)
    lang: LangField = "vi"


class OnDemandYeuCau(BaseModel):
    # Xem `localizations.DichYeuCau`: độ dài có chặn, hình dạng id để `UUID()`
    # lo, để mã 400 cũ của route giữ nguyên.
    poi_id: str = Field(min_length=1, max_length=64)
    lang: LangField


@router.post("/tts", summary="Văn bản thành MP3 stream (Tier 2)")
async def tts(
    body: TtsYeuCau,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauDangNhap,
) -> Response:
    await kiem_tra(db, khoa_cho(request, user), "/audio/tts")
    try:
        tep, hit = await tao_mp3_cached(body.text, body.lang)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return Response(
        content=tep.read_bytes(),
        media_type="audio/mpeg",
        headers={"X-Cache": "HIT" if hit else "MISS"},
    )


@router.post("/on-demand", summary="TTS cho POI đã có bản dịch (Tier 1.5)")
async def on_demand(
    body: OnDemandYeuCau,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: dict = YeuCauDangNhap,
) -> dict:
    try:
        oid = UUID(body.poi_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Id không đúng định dạng") from None
    await kiem_tra(db, khoa_cho(request, user), "/audio/on-demand")
    ban_dich = (
        (
            await db.execute(
                text(
                    """
                SELECT localized_name AS name,
                       localized_description AS description,
                       language_code AS lang
                FROM poi_localizations
                WHERE poi_id = :poi_id AND language_code = :lang
                """
                ),
                {"poi_id": oid, "lang": body.lang},
            )
        )
        .mappings()
        .first()
    )
    if not ban_dich:
        # Trước đây chỗ này tự dịch bằng Google Translate; deep-translator đã
        # bị gỡ ở SEC-010. Không có bản dịch thì không nên đọc nội dung tiếng
        # Việt bằng giọng tiếng Nhật — trả 409 để FE rơi về tầng dưới.
        raise HTTPException(
            status_code=409,
            detail=f"POI chưa có bản dịch '{body.lang}' — cần admin nhập tay trước",
        )
    try:
        tep, _hit = await tao_mp3_cached(
            ban_dich["description"] or ban_dich["name"] or "", body.lang
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    url = duong_audio_url(tep.name, body.lang)
    await hoan_tat_audio(db, oid, body.lang, url)
    return {"poi_id": body.poi_id, "lang": body.lang, "audio_url": url}


@router.get("/tasks", summary="Liệt kê tác vụ audio")
async def liet_ke_tasks(
    db: Annotated[AsyncSession, Depends(get_db)], _user: dict = DuocQuanLyAudio
) -> list[dict]:
    result = await db.execute(
        text(
            """
            SELECT id::text AS task_id,
                   poi_id::text AS poi_id,
                   language_code AS lang,
                   CASE task_status
                       WHEN 'processing' THEN 'running'
                       WHEN 'completed' THEN 'done'
                       WHEN 'failed' THEN 'error'
                       WHEN 'cancelled' THEN 'canceled'
                       ELSE task_status
                   END AS status,
                   progress_percent AS progress,
                   error_message AS loi,
                   updated_at
            FROM audio_tasks
            ORDER BY updated_at DESC
            LIMIT 100
            """
        )
    )
    docs = [dict(row) for row in result.mappings().all()]
    for doc in docs:
        doc["task_id"] = UUID(doc["task_id"]).hex
        ts = doc.get("updated_at")
        doc["updated_at"] = ts.isoformat() if ts else None
    return docs


@router.get("/tasks/stream", summary="SSE tiến độ tác vụ")
async def stream_tasks(_user: dict = DuocQuanLyAudio) -> StreamingResponse:
    hang_doi: asyncio.Queue = asyncio.Queue(maxsize=50)
    quan_ly_tasks.nguoi_nghe.add(hang_doi)

    async def sinh():
        try:
            yield ": mo ket noi\n\n"
            while True:
                try:
                    sk = await asyncio.wait_for(hang_doi.get(), timeout=5)
                    yield f"data: {sk['task_id']}:{sk['status']}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            quan_ly_tasks.nguoi_nghe.discard(hang_doi)

    return StreamingResponse(sinh(), media_type="text/event-stream")


@router.post("/tasks/{task_id}/{lenh}", summary="Pause/resume/cancel tác vụ")
async def dieu_khien_task(task_id: str, lenh: str, _user: dict = DuocQuanLyAudio) -> dict:
    if lenh not in ("pause", "resume", "cancel"):
        raise HTTPException(status_code=400, detail="Lệnh không hợp lệ")
    ok = await quan_ly_tasks.dieu_khien(task_id, lenh)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ")
    return {"ok": True}


@router.get("/giong", summary="Giọng TTS theo ngôn ngữ")
async def liet_ke_giong() -> dict:
    from app.services.audio_svc import GIONG

    return {"langs": list(NGON_NGU_AUDIO), "voices": GIONG, "cache_dir": str(THU_MUC_AUDIO)}
