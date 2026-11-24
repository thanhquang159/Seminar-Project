"""Tác vụ audio bền vững, điều khiển đúng trạng thái và phục hồi sau restart."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text

from app.postgres import AsyncSessionLocal

logger = logging.getLogger(__name__)
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
    """PostgreSQL giữ trạng thái; runner trong tiến trình xử lý các tác vụ đã nhận."""

    def __init__(self, toi_da: int = 3) -> None:
        self.toi_da = toi_da
        self._sem: asyncio.Semaphore | None = None
        self._sem_loop: asyncio.AbstractEventLoop | None = None
        self.db = AsyncSessionLocal
        self.nguoi_nghe: set[asyncio.Queue] = set()
        self._runners: dict[str, asyncio.Task] = {}
        self._recovery: asyncio.Task | None = None

    def _lay_sem(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._sem is None or self._sem_loop is not loop:
            self._sem = asyncio.Semaphore(self.toi_da)
            self._sem_loop = loop
        return self._sem

    def gan_db(self, db) -> None:
        if callable(db):
            self.db = db

    @staticmethod
    def _uuid(task_id: str) -> UUID | None:
        try:
            return UUID(str(task_id))
        except (ValueError, AttributeError):
            return None

    def _schedule(self, task_id: str) -> None:
        key = UUID(str(task_id)).hex
        existing = self._runners.get(key)
        if existing is not None and not existing.done():
            return
        runner = asyncio.create_task(self._chay(key))
        self._runners[key] = runner

        def finished(task):
            if self._runners.get(key) is task:
                self._runners.pop(key, None)
            if not task.cancelled() and task.exception():
                logger.error("Tác vụ audio %s dừng bất thường", key, exc_info=task.exception())

        runner.add_done_callback(finished)

    async def xep_viec(self, poi_id: str, lang: str) -> str:
        poi_uuid, task_uuid = UUID(str(poi_id)), uuid.uuid4()
        async with self.db() as session:
            localization = await session.execute(
                text("""
                SELECT l.id FROM pois p JOIN poi_localizations l ON l.poi_id=p.id
                WHERE p.id=:poi_id AND l.language_code=:lang
                  AND p.publication_status NOT IN ('archived', 'rejected')
                FOR UPDATE OF p, l
            """),
                {"poi_id": poi_uuid, "lang": lang},
            )
            localization_id = localization.scalar_one_or_none()
            if localization_id is None:
                raise LookupError("Không có bản dịch hoặc POI đã bị xóa/từ chối")
            # Bản dịch mới thay thế tác vụ cũ, kể cả tác vụ đang gọi TTS.
            await session.execute(
                text("""
                UPDATE audio_tasks SET task_status='cancelled', updated_at=now(), completed_at=now(),
                    error_message='Đã thay bằng yêu cầu audio mới'
                WHERE localization_id=:localization_id AND task_status IN ('queued','processing','paused')
            """),
                {"localization_id": localization_id},
            )
            await session.execute(
                text("""
                INSERT INTO audio_tasks
                    (id, poi_id, localization_id, language_code, task_status,
                     progress_percent, created_at, updated_at)
                VALUES (:id, :poi_id, :localization_id, :lang, 'queued', 0, clock_timestamp(), now())
            """),
                {
                    "id": task_uuid,
                    "poi_id": poi_uuid,
                    "localization_id": localization_id,
                    "lang": lang,
                },
            )
            await session.execute(
                text("""
                UPDATE poi_localizations SET audio_status='queued', updated_at=now()
                WHERE id=:localization_id
            """),
                {"localization_id": localization_id},
            )
            await session.commit()
        self._schedule(task_uuid.hex)
        await self._dang("queued", task_uuid.hex)
        return task_uuid.hex

    async def _doc(self, task_id: str) -> dict:
        task_uuid = self._uuid(task_id)
        if task_uuid is None:
            return {}
        async with self.db() as session:
            result = await session.execute(
                text("""
                SELECT t.id::text AS task_id, t.poi_id::text AS poi_id,
                       t.language_code AS lang, t.task_status, t.progress_percent AS progress,
                       t.error_message AS loi, t.updated_at, t.started_at, t.heartbeat_at,
                       p.publication_status, p.name AS poi_name
                FROM audio_tasks t JOIN pois p ON p.id=t.poi_id WHERE t.id=:task_id
            """),
                {"task_id": task_uuid},
            )
            row = result.mappings().first()
        if row is None:
            return {}
        doc = dict(row)
        doc["status"] = _API_STATUS[doc.pop("task_status")]
        return doc

    async def _noi_dung(self, task_id: str) -> dict | None:
        async with self.db() as session:
            result = await session.execute(
                text("""
                SELECT t.poi_id::text AS poi_id, t.language_code AS lang,
                       l.localized_name AS name, l.localized_description AS description
                FROM audio_tasks t JOIN poi_localizations l ON l.id=t.localization_id
                JOIN pois p ON p.id=t.poi_id
                WHERE t.id=:task_id AND p.publication_status NOT IN ('archived','rejected')
            """),
                {"task_id": self._uuid(task_id)},
            )
            row = result.mappings().first()
        return dict(row) if row is not None else None

    async def _doi_trang_thai(
        self,
        task_id: str,
        status: str,
        progress: int,
        *,
        allowed: tuple[str, ...],
        attempt: datetime | None = None,
        error: str | None = None,
    ) -> dict | None:
        """Đổi trạng thái có điều kiện; CAST thống nhất để asyncpg không nhầm text/varchar."""
        async with self.db() as session:
            # Các đường ghi đều khóa POI trước tác vụ/bản dịch để tránh deadlock.
            await session.execute(
                text("""
                SELECT p.id FROM pois p JOIN audio_tasks t ON t.poi_id=p.id
                WHERE t.id=:task_id FOR UPDATE OF p
            """),
                {"task_id": self._uuid(task_id)},
            )
            result = await session.execute(
                text("""
                UPDATE audio_tasks t
                SET task_status=CAST(:status AS varchar), progress_percent=:progress,
                    heartbeat_at=clock_timestamp(),
                    started_at=CASE WHEN CAST(:status AS varchar)='processing' AND t.task_status='queued'
                                    THEN clock_timestamp() ELSE started_at END,
                    completed_at=CASE WHEN CAST(:status AS varchar) IN ('completed','failed','cancelled')
                                      THEN now() ELSE NULL END,
                    error_message=:error, updated_at=now()
                WHERE t.id=:task_id AND t.task_status=ANY(CAST(:allowed AS varchar[]))
                  AND (CAST(:attempt AS timestamptz) IS NULL OR t.started_at=:attempt)
                  AND (CAST(:status AS varchar) NOT IN ('queued','processing') OR EXISTS (
                      SELECT 1 FROM pois p WHERE p.id=t.poi_id
                        AND p.publication_status NOT IN ('archived','rejected')))
                  AND (CAST(:status AS varchar) NOT IN ('queued','processing') OR NOT EXISTS (
                      SELECT 1 FROM audio_tasks newer WHERE newer.localization_id=t.localization_id
                        AND newer.created_at>t.created_at))
                RETURNING t.poi_id, t.localization_id, t.started_at
            """),
                {
                    "task_id": self._uuid(task_id),
                    "status": _DB_STATUS[status],
                    "progress": progress,
                    "error": error,
                    "allowed": list(allowed),
                    "attempt": attempt,
                },
            )
            row = result.mappings().first()
            if row is None:
                return None
            audio_status = {
                "running": "processing",
                "queued": "queued",
                "paused": "queued",
                "error": "failed",
                "canceled": "not_generated",
            }.get(status)
            if audio_status:
                await session.execute(
                    text("""
                    UPDATE poi_localizations SET audio_status=:audio_status, updated_at=now()
                    WHERE id=:localization_id
                """),
                    {"audio_status": audio_status, "localization_id": row["localization_id"]},
                )
            await session.commit()
        await self._dang(status, task_id)
        return dict(row)

    async def _cham(self, task_id: str, attempt: datetime) -> bool:
        async with self.db() as session:
            result = await session.execute(
                text("""
                UPDATE audio_tasks SET heartbeat_at=clock_timestamp()
                WHERE id=:task_id AND task_status='processing' AND started_at=:attempt
                RETURNING id
            """),
                {"task_id": self._uuid(task_id), "attempt": attempt},
            )
            alive = result.scalar_one_or_none() is not None
            await session.commit()
        return alive

    async def _finish(
        self, task_id: str, attempt: datetime, content: dict, spoken: str, url: str
    ) -> bool:
        from app.services.audio_svc import hoan_tat_audio

        async with self.db() as session:
            poi = await session.execute(
                text("""
                SELECT publication_status FROM pois WHERE id=:id FOR UPDATE
            """),
                {"id": UUID(content["poi_id"])},
            )
            if poi.scalar_one_or_none() in (None, "archived", "rejected"):
                return False
            result = await session.execute(
                text("""
                SELECT id FROM audio_tasks WHERE id=:task_id AND task_status='processing'
                  AND started_at=:attempt FOR UPDATE
            """),
                {"task_id": self._uuid(task_id), "attempt": attempt},
            )
            if result.scalar_one_or_none() is None:
                return False
            saved = await hoan_tat_audio(
                session,
                UUID(content["poi_id"]),
                content["lang"],
                url,
                expected_text=spoken,
                commit=False,
            )
            if not saved:
                await session.execute(
                    text("""
                    UPDATE poi_localizations SET audio_status='not_generated', updated_at=now()
                    WHERE poi_id=:poi_id AND language_code=:lang AND audio_status='processing'
                """),
                    {"poi_id": UUID(content["poi_id"]), "lang": content["lang"]},
                )
            await session.execute(
                text("""
                UPDATE audio_tasks SET task_status=:status, progress_percent=:progress,
                    completed_at=now(), updated_at=now(), error_message=:error
                WHERE id=:task_id
            """),
                {
                    "task_id": self._uuid(task_id),
                    "status": "completed" if saved else "cancelled",
                    "progress": 100 if saved else 0,
                    "error": None if saved else "Nội dung đã thay đổi; cần tạo audio mới",
                },
            )
            await session.commit()
        await self._dang("done" if saved else "canceled", task_id)
        return saved

    async def _chay(self, task_id: str) -> None:
        attempt = None
        try:
            async with self._lay_sem():
                claimed = await self._doi_trang_thai(task_id, "running", 10, allowed=("queued",))
                if not claimed:
                    return
                attempt = claimed["started_at"]
                content = await self._noi_dung(task_id)
                if not content:
                    await self._doi_trang_thai(
                        task_id,
                        "canceled",
                        0,
                        allowed=("processing",),
                        attempt=attempt,
                        error="POI đã xóa hoặc bản dịch không còn tồn tại",
                    )
                    return
                spoken = content.get("description") or content.get("name") or ""
                if not spoken.strip():
                    raise RuntimeError("Bản dịch không có nội dung để tạo audio")
                from app.services.audio_svc import duong_audio_url, tao_mp3_cached

                if not await self._doi_trang_thai(
                    task_id, "running", 50, allowed=("processing",), attempt=attempt
                ):
                    return
                synthesis = asyncio.create_task(tao_mp3_cached(spoken, content["lang"]))
                try:
                    async with asyncio.timeout(90):
                        while True:
                            done, _ = await asyncio.wait({synthesis}, timeout=5)
                            if done:
                                path, _ = synthesis.result()
                                break
                            if not await self._cham(task_id, attempt):
                                return
                        await self._finish(
                            task_id,
                            attempt,
                            content,
                            spoken,
                            duong_audio_url(path.name, content["lang"]),
                        )
                finally:
                    if not synthesis.done():
                        synthesis.cancel()
                    await asyncio.gather(synthesis, return_exceptions=True)
        except asyncio.CancelledError:
            if attempt is not None:
                await self._doi_trang_thai(
                    task_id, "queued", 0, allowed=("processing",), attempt=attempt
                )
            raise
        except Exception as exc:
            error = (
                "Tạo audio quá thời gian chờ (90 giây). Hãy thử lại."
                if isinstance(exc, TimeoutError)
                else str(exc)[:300]
            )
            logger.exception("Không tạo được audio cho tác vụ %s", task_id)
            try:
                await self._doi_trang_thai(
                    task_id,
                    "error",
                    0,
                    allowed=("queued", "processing"),
                    attempt=attempt,
                    error=error,
                )
            except Exception:
                logger.exception("Không ghi được lỗi audio %s; tác vụ sẽ được phục hồi", task_id)

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
        if doc["publication_status"] in ("archived", "rejected"):
            raise ValueError("POI đã xóa hoặc bị từ chối, không thể chạy audio")
        transitions = {
            "pause": ("paused", ("queued", "processing")),
            "resume": ("queued", ("paused", "queued")),
            "retry": ("queued", ("failed", "cancelled")),
            "cancel": ("canceled", ("queued", "processing", "paused")),
        }
        if lenh not in transitions:
            raise ValueError("Lệnh không hợp lệ")
        target, allowed = transitions[lenh]
        changed = await self._doi_trang_thai(
            task_id, target, 0 if target == "queued" else doc["progress"], allowed=allowed
        )
        if not changed:
            raise ValueError(
                "Trạng thái không hỗ trợ thao tác này hoặc đã có yêu cầu audio mới hơn. Hãy tải lại."
            )
        key = UUID(task_id).hex
        if lenh in ("pause", "cancel"):
            runner = self._runners.get(key)
            if runner is not None and not runner.done():
                runner.cancel()
                await asyncio.gather(runner, return_exceptions=True)
        else:
            self._schedule(key)
        return True

    async def khoi_phuc(self) -> int:
        """Chạy queued, thu hồi processing mất nhịp; giữ nguyên paused/terminal."""
        threshold = datetime.now(UTC) - timedelta(minutes=2)
        async with self.db() as session:
            await session.execute(
                text("""
                UPDATE audio_tasks t SET task_status='cancelled', completed_at=now(), updated_at=now(),
                    error_message='Đã thay bằng yêu cầu audio mới'
                WHERE t.task_status IN ('queued','processing','paused') AND EXISTS (
                    SELECT 1 FROM audio_tasks newer WHERE newer.localization_id=t.localization_id
                      AND newer.created_at>t.created_at)
            """)
            )
            await session.execute(
                text("""
                UPDATE audio_tasks t SET task_status='cancelled', completed_at=now(), updated_at=now(),
                    error_message='POI đã xóa hoặc bị từ chối'
                FROM pois p WHERE p.id=t.poi_id AND p.publication_status IN ('archived','rejected')
                  AND t.task_status IN ('queued','processing','paused')
            """)
            )
            await session.execute(
                text("""
                UPDATE audio_tasks SET task_status='queued', progress_percent=0, updated_at=now()
                WHERE task_status='processing' AND COALESCE(heartbeat_at, updated_at, created_at)<:threshold
            """),
                {"threshold": threshold},
            )
            result = await session.execute(
                text("""
                SELECT t.id::text AS task_id FROM audio_tasks t JOIN pois p ON p.id=t.poi_id
                WHERE t.task_status='queued' AND p.publication_status NOT IN ('archived','rejected')
                ORDER BY t.created_at LIMIT 100
            """)
            )
            ids = [row["task_id"] for row in result.mappings().all()]
            await session.commit()
        for task_id in ids:
            self._schedule(task_id)
        return len(ids)

    async def start(self) -> None:
        await self.khoi_phuc()

        async def recover_periodically():
            while True:
                await asyncio.sleep(30)
                try:
                    await self.khoi_phuc()
                except Exception:
                    logger.exception("Chưa phục hồi được hàng đợi audio; sẽ thử lại")

        self._recovery = asyncio.create_task(recover_periodically())

    async def stop(self) -> None:
        if self._recovery:
            self._recovery.cancel()
            await asyncio.gather(self._recovery, return_exceptions=True)
            self._recovery = None
        runners = list(self._runners.values())
        for runner in runners:
            runner.cancel()
        await asyncio.gather(*runners, return_exceptions=True)
        self._runners.clear()


quan_ly_tasks = QuanLyTasks()
