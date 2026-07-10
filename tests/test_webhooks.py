import base64
import json
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.deps import get_database
from src.api.main import app
from src.models import User

client = TestClient(app)


def _pubsub_payload(email: str, history_id: int) -> dict:
    data = base64.b64encode(
        json.dumps({"emailAddress": email, "historyId": str(history_id)}).encode()
    ).decode()
    return {"message": {"data": data, "messageId": "test-msg-1"}}


@patch("src.api.routes.webhooks.process_history.delay")
def test_gmail_webhook_enqueues_celery_task(mock_delay) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = user

    def override_get_database():
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database
    try:
        response = client.post(
            "/webhooks/gmail",
            json=_pubsub_payload(user.email, 9999999),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    mock_delay.assert_called_once_with(str(user.id), 9999999)


@patch("src.api.routes.webhooks.process_history.delay")
def test_gmail_webhook_unknown_user_returns_204(mock_delay) -> None:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def override_get_database():
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database
    try:
        response = client.post(
            "/webhooks/gmail",
            json=_pubsub_payload("unknown@example.com", 123),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    mock_delay.assert_not_called()


def test_gmail_webhook_invalid_payload() -> None:
    response = client.post(
        "/webhooks/gmail",
        json={"message": {"data": "%%%"}},
    )

    assert response.status_code == 400
