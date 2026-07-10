from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data


def test_auth_login_not_implemented() -> None:
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"
