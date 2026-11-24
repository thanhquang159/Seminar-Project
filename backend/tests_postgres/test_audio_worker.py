import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import lay_user_hien_tai
from app.routers import audio
from app.services import audio_svc
from app.services.tasks import QuanLyTasks


def test_initial_claim_error_is_reported_instead_of_leaving_queued(monkeypatch):
    manager = QuanLyTasks()
    transition = AsyncMock(side_effect=[RuntimeError("database failure"), {}])
    monkeypatch.setattr(manager, "_doi_trang_thai", transition)
    asyncio.run(manager._chay(str(uuid4())))
    assert transition.await_args_list[1].args[1] == "error"
    assert "database failure" in transition.await_args_list[1].kwargs["error"]


def test_cannot_run_a_paused_cancelled_or_completed_task(monkeypatch):
    manager = QuanLyTasks()
    monkeypatch.setattr(manager, "_doi_trang_thai", AsyncMock(return_value=None))
    generate = AsyncMock()
    monkeypatch.setattr(audio_svc, "tao_mp3_cached", generate)
    asyncio.run(manager._chay(str(uuid4())))
    generate.assert_not_awaited()


def test_provider_failure_changes_task_and_localization_state(monkeypatch):
    manager = QuanLyTasks()
    attempt = datetime.now(UTC)
    transition = AsyncMock(return_value={"started_at": attempt})
    monkeypatch.setattr(manager, "_doi_trang_thai", transition)
    monkeypatch.setattr(
        manager, "_noi_dung", AsyncMock(return_value={"description": "English", "lang": "en"})
    )
    monkeypatch.setattr(
        audio_svc, "tao_mp3_cached", AsyncMock(side_effect=RuntimeError("TTS unavailable"))
    )
    asyncio.run(manager._chay(str(uuid4())))
    assert transition.await_args_list[-1].args[1] == "error"
    assert transition.await_args_list[-1].kwargs["attempt"] == attempt


def test_scheduler_holds_one_runner_per_task(monkeypatch):
    manager = QuanLyTasks()
    started = []

    async def running(task_id):
        started.append(task_id)
        await asyncio.Event().wait()

    monkeypatch.setattr(manager, "_chay", running)

    async def run():
        task_id = str(uuid4())
        manager._schedule(task_id)
        manager._schedule(task_id)
        await asyncio.sleep(0)
        assert len(manager._runners) == 1
        await manager.stop()
        assert not manager._runners

    asyncio.run(run())
    assert len(started) == 1


def test_startup_and_shutdown_enable_recovery(monkeypatch):
    manager = QuanLyTasks()
    recover = AsyncMock()
    monkeypatch.setattr(manager, "khoi_phuc", recover)

    async def run():
        await manager.start()
        recover.assert_awaited_once()
        assert manager._recovery is not None
        await manager.stop()
        assert manager._recovery is None

    asyncio.run(run())


@pytest.mark.parametrize("action", ["resume", "retry"])
def test_control_schedules_accepted_transition(monkeypatch, action):
    manager = QuanLyTasks()
    monkeypatch.setattr(
        manager,
        "_doc",
        AsyncMock(return_value={"publication_status": "unpublished", "progress": 0}),
    )
    monkeypatch.setattr(manager, "_doi_trang_thai", AsyncMock(return_value={"started_at": None}))
    schedule = Mock()
    monkeypatch.setattr(manager, "_schedule", schedule)
    assert asyncio.run(manager.dieu_khien(str(uuid4()), action))
    schedule.assert_called_once()


@pytest.mark.parametrize("status", ["archived", "rejected"])
def test_control_rejects_deleted_poi(monkeypatch, status):
    manager = QuanLyTasks()
    monkeypatch.setattr(manager, "_doc", AsyncMock(return_value={"publication_status": status}))
    with pytest.raises(ValueError, match="POI đã xóa"):
        asyncio.run(manager.dieu_khien(str(uuid4()), "resume"))


def test_control_route_returns_conflict_instead_of_fake_success(monkeypatch):
    app = FastAPI()
    app.include_router(audio.router)
    app.dependency_overrides[lay_user_hien_tai] = lambda: {"permissions": ["user:update"]}
    monkeypatch.setattr(
        audio.quan_ly_tasks,
        "dieu_khien",
        AsyncMock(side_effect=ValueError("Không thể tiếp tục tác vụ hoàn tất")),
    )
    with TestClient(app) as client:
        response = client.post(f"/audio/tasks/{uuid4()}/resume")
    assert response.status_code == 409
    assert response.json()["detail"] == "Không thể tiếp tục tác vụ hoàn tất"
