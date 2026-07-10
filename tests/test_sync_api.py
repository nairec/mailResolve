import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.deps import get_database, verify_api_key
from src.api.main import app
from src.models import User

client = TestClient(app)


def _override_api_key() -> str:
    return "test-key"


@patch("src.api.routes.sync.process_history.delay")
def test_force_sync_enqueues_task(mock_delay) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com", history_id=12345)
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = user
    mock_delay.return_value = MagicMock(id="task-abc")

    def override_get_database():
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[verify_api_key] = _override_api_key
    try:
        response = client.post("/sync", headers={"X-API-Key": "test-key"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "task-abc"
    mock_delay.assert_called_once_with(str(user.id), 12345)


def test_force_sync_requires_api_key() -> None:
    response = client.post("/sync")
    assert response.status_code in (401, 422, 503)
