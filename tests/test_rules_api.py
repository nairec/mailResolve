import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.deps import get_database, verify_api_key
from src.api.main import app
from src.classifier.features import EmailFeatures
from src.models import Rule, User

client = TestClient(app)


def _override_api_key() -> str:
    return "test-key"


def _sample_rule(user_id: uuid.UUID) -> Rule:
    return Rule(
        id=uuid.uuid4(),
        user_id=user_id,
        name="newsletter",
        priority=10,
        conditions={"category": "newsletter", "header_exists": "List-Unsubscribe"},
        actions={"add_labels": ["mailresolve/newsletter"], "remove_labels": ["INBOX"]},
        enabled=True,
    )


def test_list_rules_returns_user_rules() -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    rule = _sample_rule(user.id)
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = user
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [rule]

    def override_get_database():
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[verify_api_key] = _override_api_key
    try:
        response = client.get("/rules", headers={"X-API-Key": "test-key"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "newsletter"


def test_create_rule_validates_and_persists() -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = user
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", uuid.uuid4())

    def override_get_database():
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[verify_api_key] = _override_api_key
    try:
        response = client.post(
            "/rules",
            headers={"X-API-Key": "test-key"},
            json={
                "name": "dev",
                "priority": 20,
                "conditions": {"category": "notification", "from_domain_in": ["github.com"]},
                "actions": {"add_labels": ["mailresolve/dev"]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_create_rule_rejects_invalid_conditions() -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = user

    def override_get_database():
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[verify_api_key] = _override_api_key
    try:
        response = client.post(
            "/rules",
            headers={"X-API-Key": "test-key"},
            json={
                "name": "bad",
                "conditions": {"category": "x"},
                "actions": {"add_labels": ["mailresolve/x"]},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@patch("src.api.routes.rules.extract_features")
@patch("src.api.routes.rules.evaluate_rules")
def test_test_rule_returns_match(mock_evaluate, mock_extract) -> None:
    user = User(id=uuid.uuid4(), email="user@example.com")
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = user
    mock_extract.return_value = MagicMock(spec=EmailFeatures)
    mock_evaluate.return_value = MagicMock(
        rule_id=uuid.uuid4(),
        rule_name="newsletter",
        category="newsletter",
        confidence=0.95,
        actions={"add_labels": ["mailresolve/newsletter"]},
        reasoning='Matched rule "newsletter"',
    )

    def override_get_database():
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[verify_api_key] = _override_api_key
    try:
        response = client.post(
            "/rules/test",
            headers={"X-API-Key": "test-key"},
            json={"message_id": "msg-123"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["rule_name"] == "newsletter"
