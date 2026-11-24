"""Chạy SQL của worker thật trong transaction rollback; chỉ mô phỏng provider TTS."""

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.postgres import engine
from app.services import audio_svc
from app.services.tasks import QuanLyTasks


def test_audio_worker_transitions_on_postgres(pytestconfig, monkeypatch, tmp_path):
    if not pytestconfig.getoption("--run-publication-db"):
        pytest.skip("Thêm --run-publication-db để kiểm tra worker với PostgreSQL thật")

    audio_file = tmp_path / "test-worker.mp3"
    audio_file.write_bytes(b"audio-fixture")
    spoken = []

    async def generate(content, lang):
        spoken.append((content, lang))
        return audio_file, False

    monkeypatch.setattr(audio_svc, "tao_mp3_cached", generate)

    async def scenario():
        engine.echo = False
        poi_id = uuid4()
        manager = QuanLyTasks()
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()

                @asynccontextmanager
                async def session_factory():
                    async with AsyncSession(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                        expire_on_commit=False,
                    ) as db:
                        yield db

                manager.gan_db(session_factory)

                async def execute(sql, **params):
                    async with session_factory() as db:
                        result = await db.execute(text(sql), params)
                        await db.commit()
                        return result

                async def locale():
                    return (
                        (
                            await execute(
                                "SELECT audio_status, audio_url FROM poi_localizations WHERE poi_id=:id AND language_code='en'",
                                id=poi_id,
                            )
                        )
                        .mappings()
                        .one()
                    )

                try:
                    await execute(
                        """
                        INSERT INTO pois (id,name,description,category,address_line,latitude,longitude,publication_status,is_active)
                        VALUES (:id,'Audio worker test','Source','other','Test',10.75,106.76,'unpublished',FALSE)
                    """,
                        id=poi_id,
                    )
                    await execute(
                        """
                        INSERT INTO poi_localizations (poi_id,language_code,localized_name,localized_description,readiness_status)
                        VALUES (:id,'en','English name','English content','ready')
                    """,
                        id=poi_id,
                    )

                    # Xếp việc thực sự phải tự chạy: kiểm tra cả _schedule và toàn bộ SQL worker.
                    task_id = await manager.xep_viec(str(poi_id), "en")
                    await manager._runners[task_id]
                    assert (await manager._doc(task_id))["status"] == "done"
                    assert (await locale())["audio_status"] == "ready"
                    assert (await locale())["audio_url"]
                    assert spoken == [("English content", "en")]
                    assert (
                        await execute("SELECT is_active FROM pois WHERE id=:id", id=poi_id)
                    ).scalar_one() is False
                    await manager._chay(task_id)
                    assert len(spoken) == 1
                    with pytest.raises(ValueError):
                        await manager.dieu_khien(task_id, "resume")

                    scheduled = []
                    monkeypatch.setattr(manager, "_schedule", scheduled.append)
                    failed = await manager.xep_viec(str(poi_id), "en")

                    async def unavailable(*_args):
                        raise RuntimeError("TTS test unavailable")

                    monkeypatch.setattr(audio_svc, "tao_mp3_cached", unavailable)
                    await manager._chay(failed)
                    assert (await manager._doc(failed))["status"] == "error"
                    assert "TTS test unavailable" in (await manager._doc(failed))["loi"]
                    assert (await locale())["audio_status"] == "failed"
                    assert await manager.dieu_khien(failed, "retry")
                    assert (await manager._doc(failed))["loi"] is None
                    monkeypatch.setattr(audio_svc, "tao_mp3_cached", generate)
                    await manager._chay(failed)
                    assert (await manager._doc(failed))["status"] == "done"

                    paused = await manager.xep_viec(str(poi_id), "en")
                    assert await manager.dieu_khien(paused, "pause")
                    await manager._chay(paused)
                    assert (await manager._doc(paused))["status"] == "paused"
                    assert await manager.dieu_khien(paused, "resume")

                    # Người dùng tạm dừng trong khi provider chạy: kết quả đến muộn không được hoàn tất tác vụ.
                    async def pause_during_synthesis(*_args):
                        await manager.dieu_khien(paused, "pause")
                        return audio_file, False

                    monkeypatch.setattr(audio_svc, "tao_mp3_cached", pause_during_synthesis)
                    await manager._chay(paused)
                    assert (await manager._doc(paused))["status"] == "paused"
                    assert await manager.dieu_khien(paused, "resume")
                    monkeypatch.setattr(audio_svc, "tao_mp3_cached", generate)
                    await manager._chay(paused)
                    assert (await manager._doc(paused))["status"] == "done"

                    cancelled = await manager.xep_viec(str(poi_id), "en")

                    async def cancel_during_synthesis(*_args):
                        await manager.dieu_khien(cancelled, "cancel")
                        return audio_file, False

                    monkeypatch.setattr(audio_svc, "tao_mp3_cached", cancel_during_synthesis)
                    await manager._chay(cancelled)
                    assert (await manager._doc(cancelled))["status"] == "canceled"
                    assert (await locale())["audio_status"] == "not_generated"

                    stale = await manager.xep_viec(str(poi_id), "en")
                    # Không cho retry một tác vụ đã bị yêu cầu mới thay thế.
                    with pytest.raises(ValueError, match="yêu cầu audio mới"):
                        await manager.dieu_khien(cancelled, "retry")
                    assert (await locale())["audio_status"] == "queued"

                    async def change_content(*_args):
                        await execute(
                            "UPDATE poi_localizations SET localized_description='New content' WHERE poi_id=:id",
                            id=poi_id,
                        )
                        return audio_file, False

                    monkeypatch.setattr(audio_svc, "tao_mp3_cached", change_content)
                    await manager._chay(stale)
                    assert (await manager._doc(stale))["status"] == "canceled"
                    assert (await locale())["audio_status"] == "not_generated"

                    # Mỗi lần nhận lại việc có mã lần chạy riêng bằng started_at.
                    retry = await manager.xep_viec(str(poi_id), "en")
                    first = await manager._doi_trang_thai(retry, "running", 10, allowed=("queued",))
                    assert not await manager._doi_trang_thai(
                        retry, "running", 10, allowed=("queued",)
                    )
                    await manager.dieu_khien(retry, "pause")
                    await manager.dieu_khien(retry, "resume")
                    second = await manager._doi_trang_thai(
                        retry, "running", 10, allowed=("queued",)
                    )
                    assert first["started_at"] != second["started_at"]
                    assert not await manager._doi_trang_thai(
                        retry,
                        "error",
                        0,
                        allowed=("processing",),
                        attempt=first["started_at"],
                        error="Old attempt",
                    )
                    assert (await manager._doc(retry))["status"] == "running"

                    await execute(
                        "UPDATE audio_tasks SET heartbeat_at=now()-interval '10 minutes' WHERE id=:id",
                        id=UUID(retry),
                    )
                    # Tạo paused ở POI khác để kiểm tra recovery không tự bỏ lệnh tạm dừng.
                    paused_poi = uuid4()
                    await execute(
                        """
                        INSERT INTO pois (id,name,category,address_line,latitude,longitude,publication_status,is_active)
                        VALUES (:id,'Paused test','other','Test',10.75,106.76,'unpublished',FALSE)
                    """,
                        id=paused_poi,
                    )
                    await execute(
                        """INSERT INTO poi_localizations (poi_id,language_code,localized_name)
                        VALUES (:id,'en','Paused name')""",
                        id=paused_poi,
                    )
                    paused_job = await manager.xep_viec(str(paused_poi), "en")
                    await manager.dieu_khien(paused_job, "pause")
                    scheduled.clear()
                    await manager.khoi_phuc()
                    assert retry in [UUID(item).hex for item in scheduled]
                    assert paused_job not in [UUID(item).hex for item in scheduled]
                    assert (await manager._doc(paused_job))["status"] == "paused"

                    await execute(
                        "UPDATE pois SET publication_status='archived' WHERE id=:id", id=poi_id
                    )
                    scheduled.clear()
                    await manager.khoi_phuc()
                    assert (await manager._doc(retry))["status"] == "canceled"
                    assert retry not in [UUID(item).hex for item in scheduled]
                    with pytest.raises(ValueError):
                        await manager.dieu_khien(retry, "retry")
                finally:
                    await manager.stop()
                    await transaction.rollback()
                assert (
                    await connection.execute(
                        text("SELECT count(*) FROM pois WHERE id=:id"), {"id": poi_id}
                    )
                ).scalar_one() == 0
        finally:
            await engine.dispose()

    asyncio.run(asyncio.wait_for(scenario(), timeout=100))
