from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import lay_user_hien_tai
from app.postgres import get_db
from app.routers.audio import router as audio_router


class Result:
    def mappings(self):
        return self

    def all(self):
        return []


class FakeSession:
    async def execute(self, *_args, **_kwargs):
        return Result()


def _client(permissions: list[str]) -> TestClient:
    app = FastAPI()
    app.include_router(audio_router)
    app.dependency_overrides[lay_user_hien_tai] = lambda: {
        "username": "test@example.com",
        "role": "user",
        "permissions": permissions,
    }
    app.dependency_overrides[get_db] = lambda: FakeSession()
    return TestClient(app)


def test_audio_task_routes_require_admin_permission():
    client = _client([])

    assert client.get("/audio/tasks").status_code == 403
    assert client.get("/audio/tasks/stream").status_code == 403
    assert client.post("/audio/tasks/invalid/pause").status_code == 403


def test_audio_task_list_is_available_with_user_management_permission():
    client = _client(["user:update"])

    response = client.get("/audio/tasks")

    assert response.status_code == 200
    assert response.json() == []
