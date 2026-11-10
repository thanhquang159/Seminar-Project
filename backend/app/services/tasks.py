"""Quản lý tác vụ sinh audio bằng bảng PostgreSQL ``audio_tasks``."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text

from app.postgres import AsyncSessionLocal

_API_STATUS = {
    "queued": "queued",
    "processing": "running",
    "completed": "done",
    "failed": "error",
    "paused": "paused",
    "cancelled": "canceled",
}
_DB_STATUS = {value: key for key, value in _API_STATUS.items()}


class QuanLyTasks:
    """Hàng đợi trong tiến trình, trạng thái bền trong PostgreSQL, SSE, phục hồi."""

    def __init__(self, toi_da: int = 3) -> None:
        self.toi_da = toi_da
        self._sem: asyncio.Semaphore | None = None
        self._sem_loop: asyncio.AbstractEventLoop | None = None
        self.db = AsyncSessionLocal
        self.nguoi_nghe: set[asyncio.Queue] = set()

    def _lay_sem(self) -> asyncio.Semaphore:
        """Semaphore thuộc event loop đang chạy và được dựng lại nếu loop đổi."""
        loop = asyncio.get_running_loop()
        if self._sem is None or self._sem_loop is not loop:
            self._sem = asyncio.Semaphore(self.toi_da)
            self._sem_loop = loop
        return self._sem

    def gan_db(self, db) -> None:
        """Thiết lập session factory; database handle cũ không được giữ lại."""
        if callable(db):
            self.db = db

    @staticmethod
    def _uuid(task_id: str) -> UUID | None:
        try:
            return UUID(str(task_id))
        except (ValueError, AttributeError):
            return None

    async def xep_viec(self, poi_id: str, lang: str) -> str:
        poi_uuid = UUID(str(poi_id))
        task_uuid = uuid.uuid4()
        async with self.db() as session:
            localization = await session.execute(
                text(
                    """
                    SELECT id
                    FROM poi_localizations
                    WHERE poi_id = :poi_id AND language_code = :lang
                    """
                ),
                {"poi_id": poi_uuid, "lang": lang},
            )
            localization_id = localization.scalar_one_or_none()
            if localization_id is None:
                raise LookupError(f"Không có bản dịch '{lang}' cho POI {poi_id}")
            await session.execute(
                text(
                    """
                    INSERT INTO audio_tasks
                        (id, poi_id, localization_id, language_code, task_status,
                         progress_percent, created_at, updated_at)
                    VALUES
                        (:id, :poi_id, :localization_id, :lang, 'queued', 0, now(), now())
                    """
                ),
                {
                    "id": task_uuid,
                    "poi_id": poi_uuid,
                    "localization_id": localization_id,
                    "lang": lang,
                },
            )
            await session.commit()
        task_id = task_uuid.hex
        asyncio.create_task(self._chay(task_id))
        return task_id

    async def _doc(self, task_id: str) -> dict:
        task_uuid = self._uuid(task_id)
        if task_uuid is None:
            return {}
        async with self.db() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id::text AS task_id,
                           poi_id::text AS poi_id,
                           language_code AS lang,
                           task_status,
                           progress_percent AS progress,
                           error_message AS loi,
                           updated_at
                    FROM audio_tasks
                    WHERE id = :task_id
                    """
                ),
                {"task_id": task_uuid},
            )
            row = result.mappings().first()
        if row is None:
            return {}
        doc = dict(row)
        doc["status"] = _API_STATUS[doc.pop("task_status")]
        return doc

    async def _noi_dung(self, task_id: str) -> dict | None:
        task_uuid = self._uuid(task_id)
        if task_uuid is None:
            return None
        async with self.db() as session:
            result = await session.execute(
                text(
                    """
                    SELECT t.poi_id::text AS poi_id,
                           t.language_code AS lang,
                           l.localized_name AS name,
                           l.localized_description AS description
                    FROM audio_tasks AS t
                    JOIN poi_localizations AS l ON l.id = t.localization_id
                    WHERE t.id = :task_id
                    """
                ),
                {"task_id": task_uuid},
            )
            row = result.mappings().first()
        return dict(row) if row is not None else None

    async def _chay(self, task_id: str) -> None:
        async with self._lay_sem():
            doc = await self._doc(task_id)
            if not doc:
                return
            await self._doi_trang_thai(task_id, "running", 10)
            try:
                while (await self._doc(task_id)).get("status") == "paused":
                    await self._cham(task_id)
                    await asyncio.sleep(1)
                if (await self._doc(task_id)).get("status") == "canceled":
                    return

                content = await self._noi_dung(task_id)
                if not content:
                    raise RuntimeError("Không tìm thấy bản dịch cho tác vụ audio")
                text_to_speak = content.get("description") or content.get("name") or ""
                if not text_to_speak.strip():
                    raise RuntimeError("Bản dịch không có nội dung để tạo audio")

                from app.services.audio_svc import (
                    duong_audio_url,
                    hoan_tat_audio,
                    tao_mp3_cached,
                )

                await self._doi_trang_thai(task_id, "running", 50)
                tep, _hit = await tao_mp3_cached(text_to_speak, content["lang"])
                url = duong_audio_url(tep.name, content["lang"])
                async with self.db() as session:
                    await hoan_tat_audio(session, UUID(content["poi_id"]), content["lang"], url)
                await self._doi_trang_thai(task_id, "done", 100)
            except Exception as exc:
                task_uuid = self._uuid(task_id)
                if task_uuid is not None:
                    async with self.db() as session:
                        await session.execute(
                            text(
                                """
                                UPDATE audio_tasks
                                SET task_status = 'failed',
                                    error_message = :error,
                                    updated_at = now(),
                                    completed_at = now()
                                WHERE id = :task_id
                                """
                            ),
                            {"task_id": task_uuid, "error": str(exc)[:300]},
                        )
                        await session.commit()
                await self._dang("error", task_id)

    async def _cham(self, task_id: str) -> None:
        task_uuid = self._uuid(task_id)
        if task_uuid is None:
            return
        async with self.db() as session:
            await session.execute(
                text(
                    """
                    UPDATE audio_tasks
                    SET heartbeat_at = now(), updated_at = now()
                    WHERE id = :task_id
                    """
                ),
                {"task_id": task_uuid},
            )
            await session.commit()

    async def _doi_trang_thai(self, task_id: str, status: str, progress: int) -> None:
        task_uuid = self._uuid(task_id)
        db_status = _DB_STATUS.get(status)
        if task_uuid is None or db_status is None:
            return
        async with self.db() as session:
            await session.execute(
                text(
                    """
                    UPDATE audio_tasks
                    SET task_status = :status,
                        progress_percent = :progress,
                        heartbeat_at = CASE WHEN :status = 'processing'
                                            THEN now() ELSE heartbeat_at END,
                        started_at = CASE WHEN :status = 'processing'
                                          THEN COALESCE(started_at, now()) ELSE started_at END,
                        completed_at = CASE WHEN :status IN ('completed', 'failed', 'cancelled')
                                            THEN now() ELSE completed_at END,
                        updated_at = now()
                    WHERE id = :task_id
                    """
                ),
                {"task_id": task_uuid, "status": db_status, "progress": progress},
            )
            await session.commit()
        await self._dang(status, task_id)

    async def _dang(self, status: str, task_id: str) -> None:
        for queue in list(self.nguoi_nghe):
            try:
                queue.put_nowait({"task_id": task_id, "status": status})
            except asyncio.QueueFull:
                pass

    async def dieu_khien(self, task_id: str, lenh: str) -> bool:
        doc = await self._doc(task_id)
        if not doc:
            return False
        status = doc["status"]
        if lenh == "pause" and status in ("queued", "running"):
            await self._doi_trang_thai(task_id, "paused", doc.get("progress", 0))
        elif lenh == "resume" and status == "paused":
            await self._doi_trang_thai(task_id, "queued", doc.get("progress", 0))
            asyncio.create_task(self._chay(task_id))
        elif lenh == "cancel" and status not in ("done", "error", "canceled"):
            await self._doi_trang_thai(task_id, "canceled", doc.get("progress", 0))
        return True

    async def khoi_phuc(self) -> int:
        """Phục hồi tác vụ chưa terminal nếu nhịp cuối đã cũ hơn năm phút."""
        threshold = datetime.now(UTC) - timedelta(minutes=5)
        async with self.db() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id::text AS task_id
                    FROM audio_tasks
                    WHERE task_status IN ('running', 'paused', 'queued')
                      AND COALESCE(heartbeat_at, updated_at, created_at) < :threshold
                    ORDER BY created_at
                    """
                ),
                {"threshold": threshold},
            )
            task_ids = [row["task_id"] for row in result.mappings().all()]
        for task_id in task_ids:
            await self._doi_trang_thai(task_id, "queued", 0)
            asyncio.create_task(self._chay(task_id))
        return len(task_ids)


quan_ly_tasks = QuanLyTasks()
