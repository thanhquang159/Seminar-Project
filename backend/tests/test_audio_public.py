from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.audio as audio_module
from app.postgres import get_db


class Result:
    def mappings(self):
        return self

    def first(self):
        return {"name": "Quan an", "description": "Mo ta", "lang": "vi"}


class FakeSession:
    async def execute(self, *_args, **_kwargs):
        return Result()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(audio_module.router)
    app.dependency_overrides[get_db] = lambda: FakeSession()
    return TestClient(app)


def _stub_audio_generation(monkeypatch, audio_file: Path) -> None:
    async def allow_audio(*_args, **_kwargs):
        return None

    async def generate_audio(*_args, **_kwargs):
        return audio_file, False

    async def save_audio(*_args, **_kwargs):
        return None

    monkeypatch.setattr(audio_module, "kiem_tra", allow_audio)
    monkeypatch.setattr(audio_module, "tao_mp3_cached", generate_audio)
    monkeypatch.setattr(audio_module, "hoan_tat_audio", save_audio)


def test_tts_is_available_without_login(tmp_path, monkeypatch) -> None:
    audio_file = tmp_path / "speech.mp3"
    audio_file.write_bytes(b"fake audio")
    _stub_audio_generation(monkeypatch, audio_file)

    response = _client().post("/audio/tts", json={"text": "Xin chao", "lang": "vi"})

    assert response.status_code == 200
    assert response.content == b"fake audio"
    assert response.headers["content-type"] == "audio/mpeg"


def test_on_demand_audio_is_available_without_login(tmp_path, monkeypatch) -> None:
    audio_file = tmp_path / "speech.mp3"
    audio_file.write_bytes(b"fake audio")
    _stub_audio_generation(monkeypatch, audio_file)

    response = _client().post(
        "/audio/on-demand",
        json={"poi_id": "00000000-0000-0000-0000-000000000001", "lang": "vi"},
    )

    assert response.status_code == 200
    assert response.json()["lang"] == "vi"
